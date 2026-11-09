from django import forms

from .models import ContactMessage


class ContactForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ["name", "email", "phone", "subject", "message"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Your full name"}),
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "you@example.com"}),
            "phone": forms.TextInput(attrs={"class": "form-control", "placeholder": "98765 43210 (optional)"}),
            "subject": forms.TextInput(attrs={"class": "form-control", "placeholder": "How can we help?"}),
            "message": forms.Textarea(
                attrs={"class": "form-control", "rows": 5, "placeholder": "Write your message..."}
            ),
        }


class NewsletterForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={"class": "form-control", "placeholder": "Enter your email address", "aria-label": "Email address"}
        )
    )
