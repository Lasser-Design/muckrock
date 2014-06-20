"""
Serilizers for the FOIA application API
"""

from rest_framework import serializers, permissions

from muckrock.foia.models import FOIARequest, FOIACommunication, FOIAFile, FOIANote

# pylint: disable=R0903

class FOIAPermissions(permissions.DjangoModelPermissionsOrAnonReadOnly):
    """
    Object-level permission to allow owners of an object partially update it
    Also allows authenticated users to submit requests
    Assumes the model instance has a `user` attribute.
    """

    def has_permission(self, request, view):
        """Allow authenticated users to submit requests and update their own requests"""
        if request.user.is_authenticated() and request.method in ['POST', 'PATCH']:
            return True
        return super(FOIAPermissions, self).has_permission(request, view)

    def has_object_permission(self, request, view, obj):
        """Grant permission?"""
        # Instance must have an attribute named `user`.
        if obj.user == request.user and request.method == 'PATCH':
            return True

        # check non-object has permission here if the user doesn't own the object
        return super(FOIAPermissions, self).has_permission(request, view)


class IsOwner(permissions.BasePermission):
    """
    Object-level permission to allow access only to owners of an object
    """

    def has_object_permission(self, request, view, obj):
        """Grant permission?"""
        # Instance must have an attribute named `user`.
        return obj.user == request.user


class FOIAFileSerializer(serializers.ModelSerializer):
    """Serializer for FOIA File model"""
    ffile = serializers.CharField(source='ffile.url', read_only=True)
    class Meta:
        model = FOIAFile
        exclude = ('foia', 'comm')


class FOIACommunicationSerializer(serializers.ModelSerializer):
    """Serializer for FOIA Communication model"""
    files = FOIAFileSerializer(many=True)
    class Meta:
        model = FOIACommunication


class FOIANoteSerializer(serializers.ModelSerializer):
    """Serializer for FOIA Note model"""
    class Meta:
        model = FOIANote
        exclude = ('id', 'foia')


class FOIARequestSerializer(serializers.ModelSerializer):
    """Serializer for FOIA Request model"""
    user = serializers.RelatedField()
    tags = serializers.RelatedField(many=True)
    communications = FOIACommunicationSerializer(many=True)
    notes = FOIANoteSerializer(many=True)

    def __init__(self, *args, **kwargs):
        # pylint: disable=E1101
        # pylint: disable=E1002
        super(FOIARequestSerializer, self).__init__(*args, **kwargs)
        if args:
            foia = args[0]
        else:
            foia = None

        if 'request' not in self.context:
            self.fields.pop('mail_id')
            self.fields.pop('email')
            self.fields.pop('notes')
            return

        request = self.context['request']

        if not request.user.is_staff:
            self.fields.pop('mail_id')
            self.fields.pop('email')
        if not request.user.is_staff and 'raw_email' in self.fields['communications'].fields:
            self.fields['communications'].fields.pop('raw_email')

        if foia and request.user != foia.user and not request.user.is_staff:
            self.fields.pop('notes')
        if not foia:
            self.fields.pop('notes')

        if foia and request.method == 'PATCH' and request.user == foia.user \
                and not request.user.is_staff:
            allowed = ['notes', 'tags', 'embargo']
            for field in self.fields.keys():
                if field not in allowed:
                    self.fields.pop(field)


    class Meta:
        model = FOIARequest
        fields = ('id', 'user', 'title', 'slug', 'status', 'communications', 'jurisdiction',
                  'agency', 'date_submitted', 'date_done', 'date_due', 'days_until_due',
                  'date_followup', 'embargo', 'date_embargo', 'price', 'requested_docs',
                  'description', 'tracking_id', 'tags', 'mail_id', 'email', 'notes',
                  'disable_autofollowups')
