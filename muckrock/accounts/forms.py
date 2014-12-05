"""
Forms for accounts application
"""

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.contrib.localflavor.us.forms import USZipCodeField

from muckrock.accounts.models import Profile
from muckrock.fields import CCExpField

class ProfileForm(forms.ModelForm):
    """A form for a user profile"""
    zip_code = USZipCodeField(required=False)

    class Meta:
        # pylint: disable=R0903
        model = Profile

class UserChangeForm(ProfileForm):
    """A form for updating user information"""
    first_name = forms.CharField(max_length=30)
    last_name = forms.CharField(max_length=30)
    email = forms.EmailField()

    class Meta(ProfileForm.Meta):
        # pylint: disable=R0903
        fields = ['first_name', 'last_name', 'email', 'address1', 'address2', 'city', 'state',
                  'zip_code', 'phone', 'email_pref', 'use_autologin']

    def clean_email(self):
        """Validates that a user does not exist with the given e-mail address"""
        email = self.cleaned_data['email']
        users = User.objects.filter(email__iexact=email)
        if len(users) == 1 and users[0] != self.instance.user:
            raise forms.ValidationError('A user with that e-mail address already exists.')
        if len(users) > 1: # pragma: no cover
            # this should never happen
            raise forms.ValidationError('A user with that e-mail address already exists.')

        return email

class RegisterForm(UserCreationForm):
    """Register for a community account"""

    username = forms.CharField(widget=forms.TextInput(attrs={'class': 'required'}))
    email = forms.EmailField(widget=forms.TextInput(attrs={'class': 'required'}))
    first_name = forms.CharField(widget=forms.TextInput(attrs={'class': 'required'}))
    last_name = forms.CharField(widget=forms.TextInput(attrs={'class': 'required'}))
    password1 = forms.CharField(label='Password',
                                widget=forms.PasswordInput(attrs={'class': 'required'}))
    password2 = forms.CharField(label='Password Confirmation',
                                widget=forms.PasswordInput(attrs={'class': 'required'}))

    class Meta(UserCreationForm.Meta):
        # pylint: disable=R0903
        fields = ['username', 'email', 'first_name', 'last_name', 'password1', 'password2']

    def clean_username(self):
        """Do a case insensitive uniqueness check"""
        username = self.cleaned_data['username']
        if User.objects.filter(username__iexact=username):
            raise forms.ValidationError("User with this Username already exists.")
        return username

    def clean_email(self):
        """Do a case insensitive uniqueness check"""
        email = self.cleaned_data['email']
        if User.objects.filter(email__iexact=email):
            raise forms.ValidationError("User with this Email already exists.")
        return email