# -*- coding: utf-8 -*-
"""
Models for the FOIA application
"""

from django.core.files.base import ContentFile
from django.db import models
from django.shortcuts import get_object_or_404

import chardet
from datetime import datetime
import logging
import mimetypes
import os

from muckrock.communication.models import (
        EmailCommunication,
        FaxCommunication,
        MailCommunication,
        WebCommunication,
        )
from muckrock.foia.models.request import FOIARequest, STATUS
from muckrock.utils import new_action

logger = logging.getLogger(__name__)

DELIVERED = (
    ('fax', 'Fax'),
    ('email', 'Email'),
    ('mail', 'Mail'),
    ('web', 'Web'),
)


class FOIACommunication(models.Model):
    """A single communication of a FOIA request"""

    foia = models.ForeignKey(FOIARequest, related_name='communications', blank=True, null=True)

    from_user = models.ForeignKey(
            'auth.User',
            related_name='sent_communications',
            null=True,
            blank=True,
            )
    to_user = models.ForeignKey(
            'auth.User',
            related_name='received_communications',
            null=True,
            blank=True,
            )

    subject = models.CharField(max_length=255, blank=True)
    date = models.DateTimeField(db_index=True)

    response = models.BooleanField(default=False,
            help_text='Is this a response (or a request)?')

    autogenerated = models.BooleanField(default=False)
    thanks = models.BooleanField(default=False)
    full_html = models.BooleanField(default=False)
    communication = models.TextField(blank=True)

    # what status this communication should set the request to - used for machine learning
    status = models.CharField(max_length=10, choices=STATUS, blank=True, null=True)

    # only used for orphans
    likely_foia = models.ForeignKey(
        FOIARequest,
        related_name='likely_communications',
        blank=True,
        null=True
    )

    # Depreacted fields
    # keep these for old communications
    from_who = models.CharField(max_length=255, blank=True)
    to_who = models.CharField(max_length=255, blank=True)
    priv_from_who = models.CharField(max_length=255, blank=True)
    priv_to_who = models.CharField(max_length=255, blank=True)

    # these can be deleted eventually
    delivered = models.CharField(max_length=10, choices=DELIVERED, blank=True, null=True)
    fax_id = models.CharField(max_length=10, blank=True, default='')
    confirmed = models.DateTimeField(blank=True, null=True)
    opened = models.BooleanField(default=False,
            help_text='DEPRECATED: If emailed, did we receive an open notification?'
                      ' If faxed, did we recieve a confirmation?')

    def __unicode__(self):
        return u'%s - %s' % (self.date, self.subject)

    def get_absolute_url(self):
        """The url for this object"""
        return self.foia.get_absolute_url() + ('#comm-%d' % self.pk)

    def save(self, *args, **kwargs):
        """Remove controls characters from text before saving"""
        remove_control = dict.fromkeys(range(0, 9) + range(11, 13) + range(14, 32))
        self.communication = unicode(self.communication).translate(remove_control)
        # limit communication length to 150k
        self.communication = self.communication[:150000]
        # special handling for certain agencies
        self._presave_special_handling()
        # update foia's date updated if this is the latest communication
        if (self.foia and
                (self.foia.date_updated is None or
                 self.date.date() > self.foia.date_updated)):
            self.foia.date_updated = self.date.date()
            self.foia.save(comment='update date_updated due to new comm')
        super(FOIACommunication, self).save(*args, **kwargs)

    def anchor(self):
        """Anchor name"""
        return 'comm-%d' % self.pk

    def get_source(self):
        """Get the source line for an attached file"""
        if self.foia and self.foia.agency:
            return self.foia.agency.name[:70]
        elif self.from_user:
            return self.from_user.get_full_name()[:70]
        else:
            return ''

    def move(self, foia_pks):
        """
        Move this communication. If more than one foia_pk is given, move the
        communication to the first request, then clone it across the rest of
        the requests. Returns the moved and cloned communications.
        """
        # avoid circular imports
        from muckrock.foia.tasks import upload_document_cloud
        if not foia_pks:
            raise ValueError('Expected a request to move the communication to.')
        if not isinstance(foia_pks, list):
            foia_pks = [foia_pks]
        move_to_request = get_object_or_404(FOIARequest, pk=foia_pks[0])
        old_foia = self.foia
        self.foia = move_to_request
        # if this was an orphan, it has not yet been uploaded
        # to document cloud
        change = old_foia is not None

        access = 'private' if self.foia.embargo else 'public'
        for each_file in self.files.all():
            each_file.foia = move_to_request
            each_file.access = access
            each_file.source = self.get_source()
            each_file.save()
            upload_document_cloud.apply_async(
                    args=[each_file.pk, change], countdown=3)
        self.save()
        logger.info('Communication #%d moved to request #%d', self.id, self.foia.id)
        # if cloning happens, self gets overwritten. so we save it to a variable here
        this_comm = FOIACommunication.objects.get(pk=self.pk)
        moved = [this_comm]
        cloned = []
        if foia_pks[1:]:
            cloned = self.clone(foia_pks[1:])
        return moved + cloned

    def clone(self, foia_pks):
        """
        Copies the communication to each request in the list,
        then returns all the new communications.
        ---
        When setting self.pk to None and then calling self.save(),
        Django will clone the communication along with all of its data
        and give it a new primary key. On the next iteration of the loop,
        the clone will be cloned along with its data, and so on. Same thing
        goes for each file attached to the communication.
        """
        # pylint: disable=too-many-locals
        # avoid circular imports
        from muckrock.foia.tasks import upload_document_cloud
        request_list = FOIARequest.objects.filter(pk__in=foia_pks)
        if not request_list:
            raise ValueError('No valid request(s) provided for cloning.')
        cloned_comms = []
        original_pk = self.pk
        files = self.files.all()
        emails = self.emails.all()
        faxes = self.faxes.all()
        mails = self.mails.all()
        web_comms = self.web_comms.all()
        for request in request_list:
            this_clone = FOIACommunication.objects.get(pk=original_pk)
            this_clone.pk = None
            this_clone.foia = request
            this_clone.save()
            access = 'private' if request.embargo else 'public'
            for file_ in files:
                original_file_id = file_.id
                file_.pk = None
                file_.foia = request
                file_.comm = this_clone
                file_.access = access
                file_.source = this_clone.get_source()
                # make a copy of the file on the storage backend
                try:
                    new_ffile = ContentFile(file_.ffile.read())
                except ValueError:
                    error_msg = ('FOIAFile #%s has no data in its ffile field. '
                                'It has not been cloned.')
                    logger.error(error_msg, original_file_id)
                    continue
                new_ffile.name = file_.ffile.name
                file_.ffile = new_ffile
                file_.save()
                upload_document_cloud.apply_async(args=[file_.pk, False], countdown=3)
            # clone all sub communications as well
            for comms in [emails, faxes, mails, web_comms]:
                for comm in comms:
                    comm.pk = None
                    comm.communication = this_clone
                    comm.save()
            # for each clone, self gets overwritten. each clone needs to be stored explicitly.
            cloned_comms.append(this_clone)
            logger.info('Communication #%d cloned to request #%d', original_pk, this_clone.foia.id)
        return cloned_comms

    def resend(self, email_or_fax=None):
        """Resend the communication"""
        foia = self.foia
        if not foia:
            logger.warn('Tried resending an orphaned communication.')
            raise ValueError('This communication has no FOIA to submit.', 'no_foia')
        if not foia.agency or not foia.agency.status == 'approved':
            logger.warn('Tried resending a communication with an unapproved agency')
            raise ValueError('This communication has no approved agency.', 'no_agency')
        snail = False
        if email_or_fax is None:
            snail = True
        else:
            foia.update_address(email_or_fax)
        foia.submit(snail=snail)
        logger.info('Communication #%d resent.', self.id)

    def make_sender_primary_contact(self):
        """Makes the communication's sender the primary contact of its FOIA."""
        if not self.foia:
            raise ValueError('Communication is an orphan and has no associated request.')

        email_comm = self.emails.first()
        if email_comm and email_comm.from_email:
            self.foia.email = email_comm.from_email
            self.foia.cc_emails.set(email_comm.to_emails.all())
            self.foia.cc_emails.add(*email_comm.cc_emails.all())
            self.foia.save(comment='update primary contact from comm')
        else:
            raise ValueError('Communication was not sent from a valid email.')

    def _presave_special_handling(self):
        """Special handling before saving
        For example, strip out BoP excessive quoting"""

        def test_agency_name(name):
            """Match on agency name"""
            return (self.foia and self.foia.agency and
                    self.foia.agency.name == name)

        def until_string(string):
            """Cut communication off after string"""
            def modify():
                """Run the modification on self.communication"""
                if string in self.communication:
                    idx = self.communication.index(string)
                    self.communication = self.communication[:idx]
            return modify

        special_cases = [
            # BoP: strip everything after '>>>'
            (test_agency_name('Bureau of Prisons'),
             until_string('>>>')),
            # Phoneix Police: strip everything after '_'*32
            (test_agency_name('Phoenix Police Department'),
             until_string('_' * 32)),
        ]

        for test, modify in special_cases:
            if test:
                modify()

    def process_attachments(self, files):
        """Given uploaded files, turn them into FOIAFiles attached to the comm"""

        ignore_types = [('application/x-pkcs7-signature', 'p7s')]

        for file_ in files.itervalues():
            if not any(file_.content_type == t or file_.name.endswith(s)
                    for t, s in ignore_types):
                self.upload_file(file_)

    def upload_file(self, file_):
        """Upload and attach a file"""
        # avoid circular imports
        from muckrock.foia.tasks import upload_document_cloud
        # make orphans and embargoed documents private
        access = 'private' if not self.foia or self.foia.embargo else 'public'
        source = self.get_source()

        foia_file = self.files.create(
                foia=self.foia,
                title=os.path.splitext(file_.name)[0][:70],
                date=datetime.now(),
                source=source[:70],
                access=access)
        # max db size of 255, - 22 for folder name
        foia_file.ffile.save(file_.name[:233].encode('ascii', 'ignore'), file_)
        foia_file.save()
        if self.foia:
            upload_document_cloud.apply_async(
                    args=[foia_file.pk, False], countdown=3)

    def create_agency_notifications(self):
        """Create the notifications for when an agency creates a new comm"""
        if self.foia and self.foia.agency:
            action = new_action(
                self.foia.agency,
                'sent a communication',
                action_object=self,
                target=self.foia)
            self.foia.notify(action)
        if self.foia:
            self.foia.update(self.anchor())

    def attach_files(self, msg):
        """Attach all of this communications files to the email message"""
        for file_ in self.files.all():
            name = file_.name()
            content = file_.ffile.read()
            mimetype, _ = mimetypes.guess_type(name)
            if mimetype and mimetype.startswith('text/'):
                enc = chardet.detect(content)['encoding']
                content = content.decode(enc)
            msg.attach(name, content)

    def get_raw_email(self):
        """Get the raw email associated with this communication, if there is one"""
        return RawEmail.objects.filter(
                email__communication=self).first()

    def from_line(self):
        """What to display for who this communication is from"""
        if self.from_user and self.from_user.profile.acct_type == 'agency':
            return self.from_user.profile.agency.name
        elif self.from_user:
            return self.from_user.get_full_name()
        else:
            return self.from_who

    def get_delivered(self):
        """Get how this comm was delivered"""
        # sort all types of comms by sent datetime,
        # and return the type of the latest
        sorted_comms = sorted(
                list(self.emails.all()) +
                list(self.faxes.all()) +
                list(self.mails.all()) +
                list(self.web_comms.all()),
                key=lambda x: x.sent_datetime,
                reverse=True,
                )
        if not sorted_comms:
            return None
        type_dict = {
                EmailCommunication: 'email',
                FaxCommunication: 'fax',
                MailCommunication: 'mail',
                WebCommunication: 'web',
                type(None): None,
                }
        return type_dict[type(sorted_comms[0])]
    # for the admin
    get_delivered.short_description = 'delivered'

    class Meta:
        # pylint: disable=too-few-public-methods
        ordering = ['date']
        verbose_name = 'FOIA Communication'
        app_label = 'foia'


class RawEmail(models.Model):
    """The raw email text for a communication - stored seperately for performance"""
    # nullable during transition
    # communication is depreacted and should be removed
    communication = models.OneToOneField(FOIACommunication, null=True)
    email = models.OneToOneField('communication.EmailCommunication', null=True)
    raw_email = models.TextField(blank=True)

    def __unicode__(self):
        return 'Raw Email: %d' % self.pk

    class Meta:
        app_label = 'foia'
        permissions = (
            ('view_rawemail', 'Can view the raw email for communications'),
            )


class FOIANote(models.Model):
    """A private note on a FOIA request"""

    foia = models.ForeignKey(FOIARequest, related_name='notes')
    author = models.ForeignKey('auth.User', related_name='notes', null=True)
    datetime = models.DateTimeField(auto_now_add=True)
    note = models.TextField()

    def __unicode__(self):
        # pylint: disable=redefined-variable-type
        if self.author:
            user = self.author
        else:
            user = self.foia.user
        return 'Note by %s on %s' % (user.get_full_name(), self.foia.title)

    class Meta:
        # pylint: disable=too-few-public-methods
        ordering = ['foia', 'datetime']
        verbose_name = 'FOIA Note'
        app_label = 'foia'


class CommunicationError(models.Model):
    """An error has occured delivering this communication"""
    # Depreacted
    communication = models.ForeignKey(
            FOIACommunication,
            related_name='errors',
            )
    date = models.DateTimeField()

    recipient = models.CharField(max_length=255)
    code = models.CharField(max_length=10)
    error = models.TextField(blank=True)
    event = models.CharField(max_length=10)
    reason = models.CharField(max_length=255)

    def __unicode__(self):
        return u'CommunicationError: %s - %s' % (self.communication.pk, self.date)

    class Meta:
        ordering = ['date']
        app_label = 'foia'


class CommunicationOpen(models.Model):
    """A communication has been opened"""
    # Depreacted
    communication = models.ForeignKey(
            FOIACommunication,
            related_name='opens',
            )
    date = models.DateTimeField()

    recipient = models.EmailField()
    city = models.CharField(max_length=50)
    region = models.CharField(max_length=50)
    country = models.CharField(max_length=10)

    client_type = models.CharField(max_length=15)
    client_name = models.CharField(max_length=50)
    client_os = models.CharField(max_length=10, verbose_name='Client OS')

    device_type = models.CharField(max_length=10)
    user_agent = models.CharField(max_length=255)
    ip_address = models.CharField(max_length=15, verbose_name='IP Address')

    def __unicode__(self):
        return u'CommunicationOpen: %s - %s' % (self.communication.pk, self.date)

    class Meta:
        ordering = ['date']
        app_label = 'foia'
