import secrets
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.urls import reverse
from django.utils import timezone

from buses.models import BusSchedule, Seat


def generate_booking_id():
    return "BG" + timezone.localtime().strftime("%y%m%d") + secrets.token_hex(3).upper()


def generate_ticket_number():
    return "TKT-" + timezone.localtime().strftime("%Y%m") + "-" + secrets.token_hex(3).upper()


class Booking(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Payment pending"
        CONFIRMED = "CONFIRMED", "Confirmed"
        CANCELLED = "CANCELLED", "Cancelled"
        EXPIRED = "EXPIRED", "Expired"
        FAILED = "FAILED", "Failed"

    booking_id = models.CharField(max_length=20, unique=True, default=generate_booking_id, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bookings")
    schedule = models.ForeignKey(BusSchedule, on_delete=models.PROTECT, related_name="bookings")
    journey_date = models.DateField()
    journey_source = models.CharField(max_length=80, blank=True)
    journey_destination = models.CharField(max_length=80, blank=True)

    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    contact_name = models.CharField(max_length=120)
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=20)

    seat_subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    convenience_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    gst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    ticket_number = models.CharField(max_length=30, unique=True, null=True, blank=True)
    qr_code = models.ImageField(upload_to="qrcodes/", blank=True, null=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["status", "expires_at"]),
        ]

    def __str__(self):
        return f"{self.booking_id} · {self.user} · {self.status}"

    def get_absolute_url(self):
        return reverse("bookings:detail", args=[self.booking_id])

    @property
    def is_expired(self):
        return bool(self.status == self.Status.PENDING and self.expires_at and self.expires_at < timezone.now())

    @property
    def passenger_count(self):
        return self.booking_seats.count()

    @property
    def seats_summary(self):
        return ", ".join(bs.seat.seat_number for bs in self.booking_seats.select_related("seat").all())

    @property
    def seat_numbers(self):
        return [bs.seat.seat_number for bs in self.booking_seats.select_related("seat").all()]

    @property
    def route_text(self):
        src = self.journey_source or self.schedule.route.source
        dst = self.journey_destination or self.schedule.route.destination
        return f"{src} → {dst}"

    @property
    def departure_datetime(self):
        return self.schedule.departure_datetime

    @property
    def arrival_datetime(self):
        return self.schedule.arrival_datetime

    @property
    def hours_to_departure(self):
        return (self.departure_datetime - timezone.now()).total_seconds() / 3600

    @property
    def is_completed(self):
        return self.status == self.Status.CONFIRMED and self.departure_datetime < timezone.now()

    @property
    def is_upcoming(self):
        return self.status == self.Status.CONFIRMED and self.departure_datetime >= timezone.now()

    @property
    def can_cancel(self):
        return self.status == self.Status.CONFIRMED and self.hours_to_departure >= 6

    @property
    def refund_percent(self):
        hours = self.hours_to_departure
        if hours >= 24:
            return 90
        if hours >= 6:
            return 50
        return 0

    @property
    def estimated_refund(self):
        percent = Decimal(self.refund_percent)
        return (self.total_amount * percent / Decimal("100")).quantize(Decimal("0.01"))

    @property
    def status_badge(self):
        return {
            self.Status.PENDING: "warning",
            self.Status.CONFIRMED: "success",
            self.Status.CANCELLED: "danger",
            self.Status.EXPIRED: "secondary",
            self.Status.FAILED: "dark",
        }.get(self.status, "secondary")

    @property
    def payment_status_label(self):
        payment = self.payments.filter(status="SUCCESS").order_by("-created_at").first()
        if payment:
            return "Paid"
        if self.status == self.Status.CANCELLED:
            return "Refunded"
        return "Unpaid"


class BookingSeat(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="booking_seats")
    seat = models.ForeignKey(Seat, on_delete=models.PROTECT, related_name="booking_seats")
    fare = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        unique_together = [("booking", "seat")]
        indexes = [models.Index(fields=["seat"])]

    def __str__(self):
        return f"{self.booking.booking_id} · seat {self.seat.seat_number}"


class Passenger(models.Model):
    class Gender(models.TextChoices):
        MALE = "Male", "Male"
        FEMALE = "Female", "Female"
        OTHER = "Other", "Other"

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="passengers")
    booking_seat = models.OneToOneField(
        BookingSeat, on_delete=models.CASCADE, related_name="passenger", null=True, blank=True
    )
    name = models.CharField(max_length=120)
    age = models.PositiveSmallIntegerField()
    gender = models.CharField(max_length=10, choices=Gender.choices, default=Gender.MALE)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.name} ({self.booking.booking_id})"

    @property
    def seat_number(self):
        return self.booking_seat.seat.seat_number if self.booking_seat_id else "—"


class Cancellation(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "REQUESTED", "Requested"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name="cancellation")
    reason = models.TextField()
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cancellation_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    refund_percent = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.APPROVED)
    admin_note = models.TextField(blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-requested_at"]

    def __str__(self):
        return f"Cancellation · {self.booking.booking_id}"
