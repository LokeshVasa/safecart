from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from .models import Address

class RegisterForm(forms.ModelForm):
    first_name = forms.CharField(required=True, label="First Name")
    last_name = forms.CharField(required=True, label="Last Name")
    username = forms.CharField(required=True, label="Username")
    email = forms.EmailField(required=True, label="Email")
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Enter password'}),
        label="Password",
        min_length=5,
        required=True
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Confirm password'}),
        label="Confirm Password",
        required=True
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email', 'password']

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise ValidationError("Username already exists")
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("Email already exists")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm = cleaned_data.get("confirm_password")

        if password and confirm and password != confirm:
            self.add_error("confirm_password", "Passwords do not match")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])  # Hash the password
        if commit:
            user.save()
        return user

class ForgotPasswordForm(forms.Form):
    email = forms.EmailField(required=True, label="Email", widget=forms.EmailInput(attrs={
        'class': 'form-control',
        'placeholder': 'Enter your email'
    }))

class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = ["street", "city", "state", "pincode"]

        widgets = {
            "street": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "city": forms.TextInput(attrs={"class": "form-control"}),
            "state": forms.TextInput(attrs={"class": "form-control"}),
            "pincode": forms.TextInput(attrs={"class": "form-control"}),
        }
