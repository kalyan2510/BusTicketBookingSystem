from django import forms
from django.utils import timezone

from buses.models import Bus, BusOperator, BusSchedule, Route
from bookings.models import Cancellation


class BootstrapMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select")
            else:
                widget.attrs.setdefault("class", "form-control")


class OperatorForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = BusOperator
        fields = [
            "name",
            "description",
            "rating",
            "contact_email",
            "contact_phone",
            "logo",
            "logo_static",
            "is_active",
        ]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class BusForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Bus
        fields = [
            "operator",
            "name",
            "registration_number",
            "bus_type",
            "layout",
            "total_seats",
            "amenities",
            "image",
            "image_static",
            "rating",
            "is_active",
        ]
        widgets = {"amenities": forms.Textarea(attrs={"rows": 3})}

    def clean(self):
        cleaned = super().clean()
        layout = cleaned.get("layout")
        if layout == Bus.Layout.SEATER_2X2:
            cleaned["total_seats"] = 40
        elif layout == Bus.Layout.SLEEPER_2X1:
            cleaned["total_seats"] = 36
        return cleaned


class RouteForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Route
        fields = [
            "source",
            "destination",
            "distance_km",
            "duration_minutes",
            "base_fare",
            "description",
            "image",
            "is_popular",
            "is_active",
        ]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def clean(self):
        cleaned = super().clean()
        source = (cleaned.get("source") or "").strip()
        destination = (cleaned.get("destination") or "").strip()
        if source and destination and source.lower() == destination.lower():
            raise forms.ValidationError("Source and destination must be different.")
        return cleaned


class ScheduleForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = BusSchedule
        fields = ["bus", "route", "travel_date", "departure_time", "arrival_time", "fare", "is_active"]
        widgets = {
            "travel_date": forms.DateInput(attrs={"type": "date"}),
            "departure_time": forms.TimeInput(attrs={"type": "time"}),
            "arrival_time": forms.TimeInput(attrs={"type": "time"}),
        }

    def clean(self):
        cleaned = super().clean()
        fare = cleaned.get("fare")
        if fare is not None and fare <= 0:
            self.add_error("fare", "Fare must be greater than zero.")
        dep = cleaned.get("departure_time")
        arr = cleaned.get("arrival_time")
        if dep and arr and dep == arr:
            self.add_error("arrival_time", "Arrival time cannot equal departure time.")
        return cleaned


class CancellationProcessForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Cancellation
        fields = ["status", "admin_note"]
        widgets = {"admin_note": forms.Textarea(attrs={"rows": 3})}
