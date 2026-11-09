from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm, SetPasswordForm
from django.contrib.auth.models import User
from django import forms

from .models import Profile

INPUT = "form-control form-control-lg"
SELECT = "form-select form-select-lg"


class RegisterForm(forms.Form):
    full_name = forms.CharField(
        max_length=120,
        widget=forms.TextInput(attrs={"class": INPUT, "placeholder": "e.g. Aarav Sharma", "autocomplete": "name"}),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"class": INPUT, "placeholder": "you@example.com", "autocomplete": "email"})
    )
    phone = forms.RegexField(
        regex=r"^[6-9]\d{9}$",
        error_messages={"invalid": "Enter a valid 10-digit Indian mobile number."},
        widget=forms.TextInput(attrs={"class": INPUT, "placeholder": "98765 43210", "autocomplete": "tel"}),
    )
    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": INPUT, "placeholder": "Create a strong password", "autocomplete": "new-password", "id": "id_password1"}),
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": INPUT, "placeholder": "Re-enter password", "autocomplete": "new-password", "id": "id_password2"}),
    )
    terms = forms.BooleanField(
        required=True,
        error_messages={"required": "Please accept the Terms of Service and Privacy Policy."},
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    def clean_full_name(self):
        name = " ".join(self.cleaned_data["full_name"].split())
        if len(name) < 3:
            raise forms.ValidationError("Please enter your full name.")
        return name

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists. Please sign in.")
        return email

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "The two passwords do not match.")
        if p1:
            from django.contrib.auth.password_validation import validate_password

            try:
                validate_password(p1)
            except forms.ValidationError as exc:
                self.add_error("password1", exc)
        return cleaned

    def save(self, request=None):
        data = self.cleaned_data
        name_parts = data["full_name"].split(" ", 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""
        user = User.objects.create_user(
            username=data["email"],
            email=data["email"],
            password=data["password1"],
            first_name=first_name[:150],
            last_name=last_name[:150],
        )
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.phone = data["phone"]
        profile.save(update_fields=["phone", "updated_at"])
        return user


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Email or username",
        widget=forms.TextInput(
            attrs={"class": INPUT, "placeholder": "you@example.com", "autocomplete": "username", "autofocus": True}
        ),
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(
            attrs={"class": INPUT, "placeholder": "Enter your password", "autocomplete": "current-password", "id": "id_login_password"}
        ),
    )
    remember_me = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    error_messages = {
        "invalid_login": "Incorrect email/username or password. Please try again.",
        "inactive": "This account has been disabled. Contact support@busgo.in.",
    }


class ProfileForm(forms.ModelForm):
    first_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "First name"}),
    )
    last_name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Last name"}),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "you@example.com"}),
    )

    class Meta:
        model = Profile
        fields = ["phone", "city", "avatar"]
        widgets = {
            "phone": forms.TextInput(attrs={"class": "form-control", "placeholder": "98765 43210"}),
            "city": forms.TextInput(attrs={"class": "form-control", "placeholder": "Bengaluru"}),
            "avatar": forms.ClearableFileInput(attrs={"class": "form-control", "accept": "image/*"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user_id:
            self.fields["first_name"].initial = self.instance.user.first_name
            self.fields["last_name"].initial = self.instance.user.last_name
            self.fields["email"].initial = self.instance.user.email
            self.fields["email"].label = "Email address"

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.user_id).exists():
            raise forms.ValidationError("This email is already used by another account.")
        return email

    def clean_phone(self):
        phone = (self.cleaned_data.get("phone") or "").strip()
        if phone and not phone.isdigit():
            raise forms.ValidationError("Phone number should contain digits only.")
        return phone

    def save(self, commit=True):
        profile = super().save(commit=False)
        user = profile.user
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data["email"]
        user.username = self.cleaned_data["email"]
        user.save()
        if commit:
            profile.save()
        return profile


class BusgoPasswordResetForm(PasswordResetForm):
    email = forms.EmailField(
        max_length=254,
        widget=forms.EmailInput(
            attrs={"class": INPUT, "placeholder": "you@example.com", "autocomplete": "email"}
        ),
    )


class BusgoSetPasswordForm(SetPasswordForm):
    new_password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": INPUT, "autocomplete": "new-password", "placeholder": "New password"}),
    )
    new_password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": INPUT, "autocomplete": "new-password", "placeholder": "Confirm new password"}),
    )
