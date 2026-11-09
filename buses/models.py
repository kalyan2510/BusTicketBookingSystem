import math
import os
import uuid
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone


def bus_image_upload_to(instance, filename):
    ext = os.path.splitext(filename)[1].lower() or ".jpg"
    return f"buses/bus_{uuid.uuid4().hex[:10]}{ext}"


def operator_logo_upload_to(instance, filename):
    ext = os.path.splitext(filename)[1].lower() or ".png"
    return f"operators/logo_{uuid.uuid4().hex[:10]}{ext}"


class BusOperator(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to=operator_logo_upload_to, blank=True, null=True)
    logo_static = models.CharField(
        max_length=200, default="images/bus-1.jpg", help_text="Fallback image under static/."
    )
    rating = models.DecimalField(
        max_digits=2, decimal_places=1, default=4.5, validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify

            base = slugify(self.name) or "operator"
            slug = base
            n = 1
            while BusOperator.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                n += 1
                slug = f"{base}-{n}"
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def logo_url(self):
        if self.logo and hasattr(self.logo, "url"):
            return self.logo.url
        return f"{settings.STATIC_URL}{self.logo_static}"


class Route(models.Model):
    source = models.CharField(max_length=80, db_index=True)
    destination = models.CharField(max_length=80, db_index=True)
    distance_km = models.PositiveIntegerField(default=0)
    duration_minutes = models.PositiveIntegerField(default=0)
    base_fare = models.DecimalField(max_digits=10, decimal_places=2, default=499)
    description = models.TextField(blank=True)
    image = models.CharField(
        max_length=200, default="images/about-travel.jpg", help_text="Static image path, e.g. images/route-1.jpg"
    )
    is_popular = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["source", "destination"]
        unique_together = [("source", "destination")]
        indexes = [models.Index(fields=["source", "destination"])]

    def __str__(self):
        return f"{self.source} → {self.destination}"

    @property
    def image_url(self):
        if self.image:
            if self.image.startswith(("http://", "https://")):
                return self.image
            return f"{settings.STATIC_URL}{self.image.lstrip('/')}"
        return f"{settings.STATIC_URL}images/about-travel.jpg"

    @property
    def duration_display(self):
        mins = self.duration_minutes or 0
        h, m = divmod(mins, 60)
        if h and m:
            return f"{h}h {m}m"
        if h:
            return f"{h}h"
        return f"{m}m"

    @property
    def slug_from(self):
        return self.source.lower().replace(" ", "-")

    @property
    def slug_to(self):
        return self.destination.lower().replace(" ", "-")


class Bus(models.Model):
    class BusType(models.TextChoices):
        AC_SEATER = "AC Seater", "AC Seater"
        AC_SLEEPER = "AC Sleeper", "AC Sleeper"
        AC_SEMI_SLEEPER = "AC Semi-Sleeper", "AC Semi-Sleeper"
        NON_AC_SEATER = "Non-AC Seater", "Non-AC Seater"
        NON_AC_SLEEPER = "Non-AC Sleeper", "Non-AC Sleeper"

    class Layout(models.TextChoices):
        SEATER_2X2 = "SEATER_2X2", "Seater 2 + 2 (40 seats)"
        SLEEPER_2X1 = "SLEEPER_2X1", "Sleeper 2 + 1 · Lower + Upper (36 berths)"

    operator = models.ForeignKey(BusOperator, on_delete=models.PROTECT, related_name="buses")
    name = models.CharField(max_length=120, help_text="e.g. Volvo 9600 Multi-Axle")
    registration_number = models.CharField(max_length=30, unique=True)
    bus_type = models.CharField(max_length=30, choices=BusType.choices, default=BusType.AC_SEATER)
    layout = models.CharField(max_length=20, choices=Layout.choices, default=Layout.SEATER_2X2)
    total_seats = models.PositiveIntegerField(default=40)
    amenities = models.TextField(
        default="Air Conditioning,Charging Point,Water Bottle,Reading Light",
        help_text="Comma-separated list, e.g. WiFi, Charging Point, Blanket",
    )
    image = models.ImageField(upload_to=bus_image_upload_to, blank=True, null=True)
    image_static = models.CharField(max_length=200, default="images/bus-1.jpg")
    rating = models.DecimalField(
        max_digits=2, decimal_places=1, default=4.5, validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["operator__name", "name"]

    def __str__(self):
        return f"{self.name} ({self.registration_number})"

    @property
    def image_url(self):
        if self.image and hasattr(self.image, "url"):
            return self.image.url
        return f"{settings.STATIC_URL}{self.image_static}"

    @property
    def amenities_list(self):
        return [a.strip() for a in (self.amenities or "").split(",") if a.strip()]

    @property
    def is_ac(self):
        return self.bus_type.startswith("AC")

    @property
    def is_sleeper(self):
        return "Sleeper" in self.bus_type

    @property
    def seat_rows(self):
        return 6 if self.layout == Bus.Layout.SLEEPER_2X1 else 10

    @property
    def layout_columns(self):
        return [0, 1, 4] if self.layout == Bus.Layout.SLEEPER_2X1 else [0, 1, 3, 4]

    def seat_specs(self):
        """Return a deterministic list of seat definitions for this layout."""
        specs = []
        if self.layout == Bus.Layout.SLEEPER_2X1:
            letters = ["A", "B", "C"]
            for deck in ("Lower", "Upper"):
                prefix = "L" if deck == "Lower" else "U"
                n = 1
                for row in range(1, 7):
                    for idx, col in enumerate([0, 1, 4]):
                        specs.append(
                            {
                                "seat_number": f"{prefix}{n}",
                                "deck": deck,
                                "seat_type": "Sleeper",
                                "row": row,
                                "col": col,
                                "is_window": idx in (0, 2),
                                "price_multiplier": "1.00" if deck == "Lower" else "0.95",
                            }
                        )
                        n += 1
        else:
            letters = ["A", "B", "C", "D"]
            for row in range(1, 11):
                for idx, col in enumerate([0, 1, 3, 4]):
                    specs.append(
                        {
                            "seat_number": f"{row}{letters[idx]}",
                            "deck": "Lower",
                            "seat_type": "Seater",
                            "row": row,
                            "col": col,
                            "is_window": idx in (0, 3),
                            "price_multiplier": "1.00",
                        }
                    )
        return specs


class BusSchedule(models.Model):
    bus = models.ForeignKey(Bus, on_delete=models.CASCADE, related_name="schedules")
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name="schedules")
    travel_date = models.DateField(db_index=True)
    departure_time = models.TimeField()
    arrival_time = models.TimeField()
    fare = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["travel_date", "departure_time"]
        unique_together = [("bus", "route", "travel_date", "departure_time")]
        indexes = [models.Index(fields=["route", "travel_date"])]

    def __str__(self):
        return f"{self.bus} · {self.route} · {self.travel_date} {self.departure_time:%H:%M}"

    @property
    def departure_datetime(self):
        naive = datetime.combine(self.travel_date, self.departure_time)
        if timezone.is_naive(naive):
            return timezone.make_aware(naive, timezone.get_current_timezone())
        return naive

    @property
    def arrival_datetime(self):
        naive = datetime.combine(self.travel_date, self.arrival_time)
        if timezone.is_naive(naive):
            aware = timezone.make_aware(naive, timezone.get_current_timezone())
        else:
            aware = naive
        if self.arrival_time <= self.departure_time:
            aware += timedelta(days=1)
        return aware

    @property
    def duration_minutes(self):
        delta = self.arrival_datetime - self.departure_datetime
        return max(int(delta.total_seconds() // 60), 0)

    @property
    def duration_display(self):
        h, m = divmod(self.duration_minutes, 60)
        return f"{h}h {m:02d}m" if h else f"{m}m"

    @property
    def is_departed(self):
        return self.departure_datetime <= timezone.now()

    def get_absolute_url(self):
        return reverse("buses:bus_details", args=[self.pk])

    @property
    def total_seat_count(self):
        return self.seats.filter(is_active=True).count()

    @property
    def booked_seat_ids(self):
        from bookings.models import Booking, BookingSeat

        return set(
            BookingSeat.objects.filter(
                seat__schedule=self,
                seat__is_active=True,
                booking__status__in=[Booking.Status.PENDING, Booking.Status.CONFIRMED],
            )
            .exclude(booking__status=Booking.Status.PENDING, booking__expires_at__lt=timezone.now())
            .values_list("seat_id", flat=True)
        )

    @property
    def available_seat_count(self):
        from bookings.models import Booking, BookingSeat

        booked = (
            BookingSeat.objects.filter(
                seat__schedule=self,
                seat__is_active=True,
                booking__status__in=[Booking.Status.PENDING, Booking.Status.CONFIRMED],
            )
            .exclude(booking__status=Booking.Status.PENDING, booking__expires_at__lt=timezone.now())
            .count()
        )
        return max(self.seats.filter(is_active=True).count() - booked, 0)

    @property
    def occupancy_percent(self):
        total = self.total_seat_count or 1
        return min(round(((total - self.available_seat_count) / total) * 100), 100)

    def ensure_seats(self):
        """Create the physical seat rows for this schedule (idempotent)."""
        existing = set(self.seats.values_list("seat_number", flat=True))
        new = []
        for spec in self.bus.seat_specs():
            if spec["seat_number"] not in existing:
                new.append(Seat(schedule=self, **spec))
        if new:
            Seat.objects.bulk_create(new, ignore_conflicts=True)
        return self.seats.count()


class Seat(models.Model):
    class Deck(models.TextChoices):
        LOWER = "Lower", "Lower deck"
        UPPER = "Upper", "Upper deck"

    class SeatType(models.TextChoices):
        SEATER = "Seater", "Seater"
        SLEEPER = "Sleeper", "Sleeper"

    schedule = models.ForeignKey(BusSchedule, on_delete=models.CASCADE, related_name="seats")
    seat_number = models.CharField(max_length=10)
    deck = models.CharField(max_length=10, choices=Deck.choices, default=Deck.LOWER)
    seat_type = models.CharField(max_length=10, choices=SeatType.choices, default=SeatType.SEATER)
    row = models.PositiveSmallIntegerField(default=1)
    col = models.PositiveSmallIntegerField(default=0)
    is_window = models.BooleanField(default=False)
    is_active = models.BooleanField(
        default=True, help_text="Uncheck to block this seat (shown grey / unavailable)."
    )
    price_multiplier = models.DecimalField(max_digits=4, decimal_places=2, default=1)

    class Meta:
        ordering = ["deck", "row", "col"]
        unique_together = [("schedule", "seat_number")]
        indexes = [models.Index(fields=["schedule", "is_active"])]

    def __str__(self):
        return f"{self.seat_number} · {self.schedule_id}"

    @property
    def price(self):
        from decimal import Decimal

        return (self.schedule.fare * self.price_multiplier).quantize(Decimal("0.01"))


class Review(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bus_reviews")
    bus = models.ForeignKey(Bus, on_delete=models.CASCADE, related_name="reviews", null=True, blank=True)
    schedule = models.ForeignKey(
        BusSchedule, on_delete=models.SET_NULL, related_name="reviews", null=True, blank=True
    )
    rating = models.PositiveSmallIntegerField(
        default=5, validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    title = models.CharField(max_length=120, blank=True)
    comment = models.TextField()
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["is_approved", "-created_at"])]

    def __str__(self):
        return f"{self.user} · {self.rating}★"

    @property
    def stars(self):
        return range(1, 6)


class NewsletterSubscriber(models.Model):
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.email


class ContactMessage(models.Model):
    name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    subject = models.CharField(max_length=160)
    message = models.TextField()
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} · {self.subject}"
