"""
Views for the FOIA application
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.mail import send_mail
from django.core.urlresolvers import reverse
from django.http import Http404
from django.shortcuts import render_to_response, get_object_or_404, redirect
from django.template.defaultfilters import slugify
from django.template.loader import render_to_string
from django.template import RequestContext
from django.views.generic.detail import DetailView

from datetime import datetime
import logging
import stripe

from muckrock.foia.codes import CODES
from muckrock.foia.forms import RequestFilterForm
from muckrock.foia.models import \
    FOIARequest, \
    FOIAMultiRequest, \
    STATUS
from muckrock.foia.views.comms import move_comm, delete_comm, save_foia_comm, resend_comm
from muckrock.foia.views.composers import get_foia
from muckrock.qanda.models import Question
from muckrock.settings import STRIPE_PUB_KEY, STRIPE_SECRET_KEY
from muckrock.tags.models import Tag
from muckrock.views import class_view_decorator, MRFilterableListView

# pylint: disable=R0901

logger = logging.getLogger(__name__)
stripe.api_key = STRIPE_SECRET_KEY
STATUS_NODRAFT = [st for st in STATUS if st != ('started', 'Draft')]

class RequestList(MRFilterableListView):
    """Base list view for other list views to inherit from"""
    model = FOIARequest
    title = 'Requests'
    template_name = 'lists/request_list.html'

    def get_filters(self):
        """Adds request-specific filter fields"""
        base_filters = super(RequestList, self).get_filters()
        new_filters = [{'field': 'status', 'lookup': 'exact'}]
        return base_filters + new_filters

    def get_context_data(self, **kwargs):
        """Changes filter_form to use RequestFilterForm instead of the default"""
        context = super(RequestList, self).get_context_data(**kwargs)
        filter_data = self.get_filter_data()
        context['filter_form'] = RequestFilterForm(initial=filter_data['filter_initials'])
        return context

    def get_queryset(self):
        """Limits requests to those visible by current user"""
        objects = super(RequestList, self).get_queryset()
        return objects.get_viewable(self.request.user)

@class_view_decorator(login_required)
class MyRequestList(RequestList):
    """View requests owned by current user"""
    # TODO: Add multirequests back to my requests list view

    template_name = 'lists/request_my_list.html'

    def set_read_status(self, foia_pks, status):
        """Mark requests as read or unread"""
        for foia_pk in foia_pks:
            foia = FOIARequest.objects.get(pk=foia_pk, user=self.request.user)
            foia.updated = status
            foia.save()

    def post(self, request):
        """Handle updating read status"""
        try:
            post = request.POST
            foia_pks = post.getlist('foia')
            if post.get('submit') == 'Mark as Read':
                self.set_read_status(foia_pks, False)
            elif post.get('submit') == 'Mark as Unread':
                self.set_read_status(foia_pks, True)
            elif post.get('submit') == 'Mark All as Read':
                foia_requests = FOIARequest.objects.filter(user=self.request.user, updated=True)
                all_unread = [foia.pk for foia in foia_requests]
                self.set_read_status(all_unread, False)
        except FOIARequest.DoesNotExist:
            pass
        return redirect('foia-mylist')

    def get_filters(self):
        """Removes the 'users' filter, because its _my_ requests"""
        filters = super(MyRequestList, self).get_filters()
        for filter_dict in filters:
            if 'user' in filter_dict.values():
                filters.pop(filters.index(filter_dict))
        return filters

    def get_queryset(self):
        """Limits requests to just those by the current user"""
        objects = super(MyRequestList, self).get_queryset()
        return objects.filter(user=self.request.user)

@class_view_decorator(login_required)
class FollowingRequestList(RequestList):
    """List of all FOIA requests the user is following"""
    def get_queryset(self):
        """Limits FOIAs to those followed by the current user"""
        objects = super(FollowingRequestList, self).get_queryset()
        profile = self.request.user.get_profile()
        return objects.filter(followed_by=profile)

# pylint: disable=no-self-use
class Detail(DetailView):
    """Details of a single FOIA request as well
    as handling post actions for the request"""

    model = FOIARequest
    context_object_name = 'foia'

    def dispatch(self, request, *args, **kwargs):
        """If request is a draft, then redirect to drafting interface"""
        if request.POST:
            return self.post(request)
        foia = get_foia(
            self.kwargs['jurisdiction'],
            self.kwargs['jidx'],
            self.kwargs['slug'],
            self.kwargs['idx']
        )
        if foia.status == 'started':
            return redirect(
                'foia-draft',
                jurisdiction=self.kwargs['jurisdiction'],
                jidx=self.kwargs['jidx'],
                slug=self.kwargs['slug'],
                idx=self.kwargs['idx']
            )
        else:
            return super(Detail, self).dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        """Get the FOIA Request"""
        # pylint: disable=W0613
        foia = get_foia(
            self.kwargs['jurisdiction'],
            self.kwargs['jidx'],
            self.kwargs['slug'],
            self.kwargs['idx']
        )
        if not foia.is_viewable(self.request.user):
            raise Http404()
        if foia.user == self.request.user:
            if foia.updated:
                foia.updated = False
                foia.save()
        return foia

    def get_context_data(self, **kwargs):
        """Add extra context data"""
        context = super(Detail, self).get_context_data(**kwargs)
        foia = context['foia']
        user = self.request.user
        is_past_due = foia.date_due < datetime.now().date() if foia.date_due else False
        context['all_tags'] = Tag.objects.all()
        context['past_due'] = is_past_due
        context['admin_actions'] = foia.admin_actions(user)
        context['user_actions'] = foia.user_actions(user)
        context['noncontextual_request_actions'] = foia.noncontextual_request_actions(user)
        context['contextual_request_actions'] = foia.contextual_request_actions(user)
        context['choices'] = STATUS if user.is_staff or foia.status == 'started' else STATUS_NODRAFT
        context['stripe_pk'] = STRIPE_PUB_KEY
        context['sidebar_admin_url'] = reverse('admin:foia_foiarequest_change', args=(foia.pk,))
        if foia.sidebar_html:
            messages.info(self.request, foia.sidebar_html)
        return context

    def post(self, request):
        """Handle form submissions"""
        foia = self.get_object()
        actions = {
            'status': self._status,
            'tags': self._tags,
            'follow_up': self._follow_up,
            'question': self._question,
            'flag': self._flag,
            'appeal': self._appeal,
            'move_comm': move_comm,
            'delete_comm': delete_comm,
            'resend_comm': resend_comm
        }
        try:
            return actions[request.POST['action']](request, foia)
        except KeyError: # if submitting form from web page improperly
            return redirect(foia)

    def _tags(self, request, foia):
        """Handle updating tags"""
        # pylint: disable=R0201
        if foia.editable_by(request.user) or request.user.is_staff:
            foia.update_tags(request.POST.get('tags'))
        return redirect(foia)

    # pylint: disable=line-too-long
    def _status(self, request, foia):
        """Handle updating status"""
        status = request.POST.get('status')
        old_status = foia.get_status_display()
        if foia.status not in ['started', 'submitted'] and ((foia.editable_by(request.user) and status in [s for s, _ in STATUS_NODRAFT]) or (request.user.is_staff and status in [s for s, _ in STATUS])):
            foia.status = status
            foia.save()

            subject = '%s changed the status of "%s" to %s' % (
                request.user.username,
                foia.title,
                foia.get_status_display()
            )
            args = {
                'request': foia,
                'old_status': old_status,
                'user': request.user
            }
            send_mail(
                subject,
                render_to_string('text/foia/status_change.txt', args),
                'info@muckrock.com',
                ['requests@muckrock.com'],
                fail_silently=False
            )
        return redirect(foia)

    def _follow_up(self, request, foia):
        """Handle submitting follow ups"""
        text = request.POST.get('text', False)
        can_follow_up = foia.editable_by(request.user) or request.user.is_staff
        if can_follow_up and foia.status != 'started' and text:
            save_foia_comm(
                request,
                foia,
                foia.user.get_full_name(),
                text,
                'Your follow up has been sent.'
            )
        return redirect(foia)

    def _question(self, request, foia):
        """Handle asking a question"""
        text = request.POST.get('text')
        if foia.editable_by(request.user) and text:
            title = 'Question about request: %s' % foia.title
            question = Question.objects.create(
                user=request.user,
                title=title,
                slug=slugify(title),
                foia=foia,
                question=text,
                date=datetime.now()
            )
            messages.success(request, 'Your question has been posted.')
            question.notify_new()
            return redirect(question)

        return redirect(foia)

    def _flag(self, request, foia):
        """Allow a user to notify us of a problem with the request"""
        text = request.POST.get('text')
        if request.user.is_authenticated() and text:
            args = {
                'request': foia,
                'user': request.user,
                'reason': text
            }
            send_mail(
                '[FLAG] Freedom of Information Request: %s' % foia.title,
                render_to_string('text/foia/flag.txt', args),
                'info@muckrock.com',
                ['requests@muckrock.com'],
                fail_silently=False
            )
            messages.success(request, 'Problem succesfully reported')
        return redirect(foia)

    def _appeal(self, request, foia):
        """Handle submitting an appeal"""
        text = request.POST.get('text')
        if foia.editable_by(request.user) and foia.is_appealable() and text:
            save_foia_comm(
                request,
                foia,
                foia.user.get_full_name(),
                text,
                'Appeal succesfully sent',
                appeal=True
            )
        return redirect(foia)

def redirect_old(request, jurisdiction, slug, idx, action):
    """Redirect old urls to new urls"""
    # pylint: disable=W0612
    # pylint: disable=W0613

    # some jurisdiction slugs changed, just ignore the jurisdiction slug passed in
    foia = get_object_or_404(FOIARequest, pk=idx)
    jurisdiction = foia.jurisdiction.slug
    jidx = foia.jurisdiction.pk

    if action == 'view':
        return redirect('/foi/%(jurisdiction)s-%(jidx)s/%(slug)s-%(idx)s/' % locals())

    if action == 'admin-fix':
        action = 'admin_fix'

    return redirect('/foi/%(jurisdiction)s-%(jidx)s/%(slug)s-%(idx)s/%(action)s/' % locals())

@user_passes_test(lambda u: u.is_staff)
def acronyms(request):
    """A page with all the acronyms explained"""
    status_dict = dict(STATUS)
    codes = [(acro, name, status_dict.get(status, ''), desc)
             for acro, (name, status, desc) in CODES.iteritems()]
    codes.sort()
    return render_to_response(
        'staff/acronyms.html',
        {'codes': codes},
        context_instance=RequestContext(request)
    )
