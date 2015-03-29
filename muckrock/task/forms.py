"""
Forms for Task app
"""

from django import forms
from django.contrib.auth.models import User

from muckrock.forms import MRFilterForm

class TaskFilterForm(MRFilterForm):
    """Extends MRFilterForm with an 'assigned' filter"""
    assigned = forms.ModelChoiceField(
        required=False,
        queryset=User.objects.filter(is_staff=True)
    )