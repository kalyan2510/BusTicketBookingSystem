from django import forms

from .models import Passenger


class ContactForm(forms.Form):
    contact_name = forms.CharField(
        max_length=120,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Full name"}),
    )
    contact_email = forms.EmailField(
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "you@example.com"}),
    )
    contact_phone = forms.RegexField(
        regex=r"^[6-9]\d{9}$",
        error_messages={"invalid": "Enter a valid 10-digit Indian mobile number."},
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "98765 43210"}),
    )


class PassengerForm(forms.Form):
    name = forms.CharField(
        max_length=120,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Passenger full name", "autocomplete": "off"}
        ),
    )
    age = forms.IntegerField(
        min_value=1,
        max_value=120,
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "Age", "min": 1, "max": 120}),
    )
    gender = forms.ChoiceField(
        choices=Passenger.Gender.choices,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    phone = forms.RegexField(
        regex=r"^[6-9]\d{9}$",
        required=True,
        error_messages={"invalid": "Enter a valid 10-digit mobile number."},
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Mobile number"}),
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "Email address"}),
    )


class CancellationForm(forms.Form):
    reason = forms.CharField(
        min_length=5,
        max_length=500,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Tell us why you need to cancel (min. 5 characters)",
            }
        ),
    )


class ReviewForm(forms.Form):
    rating = forms.ChoiceField(
        choices=[(i, f"{i} star{'s' if i > 1 else ''}") for i in range(5, 0, -1)],
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    title = forms.CharField(
        max_length=120,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Summarise your experience"}),
    )
    comment = forms.CharField(
        min_length=10,
        max_length=1000,
        widget=forms.Textarea(
            attrs={"class": "form-control", "rows": 3, "placeholder": "What did you like or dislike?"}
        ),
    )
