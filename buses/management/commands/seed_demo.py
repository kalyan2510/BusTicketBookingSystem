"""Seed BUSGO with realistic operators, routes, schedules, seats and demo bookings."""
import random
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from bookings.models import Booking, BookingSeat, Passenger
from bookings.services import (
    _unique_booking_id,
    _unique_ticket_number,
    calculate_charges,
    cancel_booking,
)
from buses.models import Bus, BusOperator, BusSchedule, Review, Route
from payments.models import Payment

random.seed(42)

OPERATORS = [
    {
        "name": "BUSGO Express",
        "description": "Our flagship premium fleet with trained captains, onboard refreshments and live tracking.",
        "rating": "4.9",
        "contact_email": "care@busgoexpress.in",
        "contact_phone": "+91 98765 10001",
        "logo_static": "images/bus-1.jpg",
    },
    {
        "name": "Volvo Travels India",
        "description": "Multi-axle Volvo coaches built for smooth, quiet intercity travel.",
        "rating": "4.7",
        "contact_email": "hello@volvotravels.in",
        "contact_phone": "+91 98765 10002",
        "logo_static": "images/bus-2.jpg",
    },
    {
        "name": "Sharma Transports",
        "description": "Trusted for over two decades on North India's busiest corridors.",
        "rating": "4.4",
        "contact_email": "bookings@sharmatransports.in",
        "contact_phone": "+91 98765 10003",
        "logo_static": "images/bus-4.jpg",
    },
    {
        "name": "Orange Tours & Travels",
        "description": "Award-winning sleeper coaches with privacy curtains and charging points.",
        "rating": "4.6",
        "contact_email": "support@orangetours.in",
        "contact_phone": "+91 98765 10004",
        "logo_static": "images/bus-3.jpg",
    },
    {
        "name": "IntrCity SmartBus",
        "description": "Smart buses with app-based boarding, clean washrooms and punctual departures.",
        "rating": "4.8",
        "contact_email": "care@intrcity.in",
        "contact_phone": "+91 98765 10005",
        "logo_static": "images/bus-1.jpg",
    },
    {
        "name": "SRS Travels",
        "description": "South India's dependable seater and sleeper network.",
        "rating": "4.3",
        "contact_email": "help@srstravels.in",
        "contact_phone": "+91 98765 10006",
        "logo_static": "images/bus-2.jpg",
    },
]

BUSES = [
    {
        "operator": "BUSGO Express",
        "name": "Volvo 9600 Multi-Axle",
        "registration_number": "KA01BG9600",
        "bus_type": Bus.BusType.AC_SLEEPER,
        "layout": Bus.Layout.SLEEPER_2X1,
        "total_seats": 36,
        "amenities": "Air Conditioning,WiFi,Charging Point,Blanket,Water Bottle,Live Tracking,Reading Light",
        "image_static": "images/bus-1.jpg",
        "rating": "4.9",
    },
    {
        "operator": "Volvo Travels India",
        "name": "Scania Metrolink HD",
        "registration_number": "MH12VT2024",
        "bus_type": Bus.BusType.AC_SEMI_SLEEPER,
        "layout": Bus.Layout.SEATER_2X2,
        "total_seats": 40,
        "amenities": "Air Conditioning,Charging Point,Water Bottle,Reading Light,Emergency Exit",
        "image_static": "images/bus-2.jpg",
        "rating": "4.7",
    },
    {
        "operator": "Orange Tours & Travels",
        "name": "Mercedes-Benz Sleeper",
        "registration_number": "TN09OT7788",
        "bus_type": Bus.BusType.AC_SLEEPER,
        "layout": Bus.Layout.SLEEPER_2X1,
        "total_seats": 36,
        "amenities": "Air Conditioning,Privacy Curtains,Charging Point,Blanket,Water Bottle,Reading Light",
        "image_static": "images/bus-3.jpg",
        "rating": "4.6",
    },
    {
        "operator": "Sharma Transports",
        "name": "Bharat Benz A/C Seater",
        "registration_number": "DL01ST4521",
        "bus_type": Bus.BusType.AC_SEATER,
        "layout": Bus.Layout.SEATER_2X2,
        "total_seats": 40,
        "amenities": "Air Conditioning,Charging Point,Water Bottle,First Aid,Reading Light",
        "image_static": "images/bus-4.jpg",
        "rating": "4.4",
    },
    {
        "operator": "IntrCity SmartBus",
        "name": "IntrCity Smart Sleeper",
        "registration_number": "KA05IC9090",
        "bus_type": Bus.BusType.AC_SLEEPER,
        "layout": Bus.Layout.SLEEPER_2X1,
        "total_seats": 36,
        "amenities": "Air Conditioning,WiFi,Washroom,Charging Point,Blanket,Live Tracking,CCTV",
        "image_static": "images/hero-bus.jpg",
        "rating": "4.8",
    },
    {
        "operator": "SRS Travels",
        "name": "SRS Non-AC Sleeper",
        "registration_number": "KA51SR1122",
        "bus_type": Bus.BusType.NON_AC_SLEEPER,
        "layout": Bus.Layout.SLEEPER_2X1,
        "total_seats": 36,
        "amenities": "Charging Point,Water Bottle,Reading Light,First Aid",
        "image_static": "images/bus-2.jpg",
        "rating": "4.2",
    },
]

ROUTES = [
    ("Delhi", "Jaipur", 280, 330, 799, "images/bus-1.jpg", True, "The classic Golden Triangle hop through the Aravalli foothills."),
    ("Mumbai", "Pune", 150, 195, 499, "images/bus-2.jpg", True, "India's busiest expressway corridor with departures every hour."),
    ("Bengaluru", "Chennai", 350, 390, 899, "images/bus-3.jpg", True, "A smooth highway run between two southern tech hubs."),
    ("Hyderabad", "Vijayawada", 275, 300, 749, "images/bus-4.jpg", True, "Fast, frequent and famous for its roadside filter-coffee stops."),
    ("Delhi", "Agra", 233, 240, 649, "images/hero-bus.jpg", True, "Visit the Taj Mahal on a comfortable same-day coach."),
    ("Pune", "Goa", 450, 540, 1199, "images/offer-2.jpg", True, "Overnight coaches to the Konkan coast and its beaches."),
    ("Chennai", "Coimbatore", 500, 510, 1099, "images/bus-1.jpg", False, "A scenic run through Tamil Nadu's textile heartland."),
    ("Ahmedabad", "Surat", 265, 270, 599, "images/bus-2.jpg", False, "Reliable daily service on the industrial corridor."),
    ("Kolkata", "Digha", 185, 240, 549, "images/bus-3.jpg", False, "Weekend beach escape from the City of Joy."),
    ("Jaipur", "Udaipur", 395, 420, 999, "images/bus-4.jpg", True, "Royal Rajasthan road trip past lakes and palaces."),
    ("Mumbai", "Goa", 590, 660, 1399, "images/hero-bus.jpg", True, "The legendary overnight coastal route."),
    ("Bengaluru", "Hyderabad", 570, 570, 1299, "images/bus-2.jpg", False, "Overnight sleeper service on NH-44."),
]

DEPARTURES = [time(6, 30), time(14, 15), time(21, 45)]

REVIEWS = [
    ("Priya Menon", "priya.menon@example.com", "Bengaluru → Chennai", 5, "Spotless coach and a very polite captain", "The sleeper berth was clean, the blanket was fresh and we reached Chennai ten minutes early. Booking on BUSGO took less than two minutes."),
    ("Rohan Kapoor", "rohan.kapoor@example.com", "Delhi → Jaipur", 5, "Perfect weekend start", "Loved the live tracking and the boarding reminder. The bus was a Volvo double-axle and the seats reclined beautifully."),
    ("Sneha Iyer", "sneha.iyer@example.com", "Mumbai → Pune", 4, "Quick and comfortable", "Left on time, arrived on time. The charging point worked and the AC was just right. Would book again."),
    ("Vikram Singh", "vikram.singh@example.com", "Jaipur → Udaipur", 5, "Great value for money", "The QR ticket was so convenient — no printout needed. The operator even called to confirm the boarding point."),
    ("Ananya Rao", "ananya.rao@example.com", "Hyderabad → Vijayawada", 4, "Smooth overnight ride", "Clean washroom, friendly staff and a smooth ride. The only thing missing was a USB-C port."),
    ("Karan Mehta", "karan.mehta@example.com", "Pune → Goa", 5, "The best way to reach Goa", "Booked a lower berth, slept peacefully and woke up to palm trees. BUSGO's seat map made choosing easy."),
]


class Command(BaseCommand):
    help = "Seed BUSGO with demo operators, buses, routes, schedules, seats, reviews and bookings."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=21,
            help="Number of upcoming days to generate schedules for (default: 21).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        days = max(options["days"], 7)
        today = timezone.localdate()
        now = timezone.now()
        self.stdout.write("Creating accounts...")

        admin, created = User.objects.get_or_create(
            username="admin@busgo.com",
            defaults={
                "email": "admin@busgo.com",
                "first_name": "BUSGO",
                "last_name": "Admin",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if created:
            admin.set_password("Admin@12345")
            admin.save()
        else:
            admin.is_staff = True
            admin.is_superuser = True
            admin.save(update_fields=["is_staff", "is_superuser"])

        demo, created = User.objects.get_or_create(
            username="demo@busgo.com",
            defaults={"email": "demo@busgo.com", "first_name": "Aarav", "last_name": "Sharma"},
        )
        if created:
            demo.set_password("Demo@12345")
            demo.save()
        demo.profile.phone = "9876543210"
        demo.profile.city = "Bengaluru"
        demo.profile.save()

        reviewers = []
        for name, email, *_ in REVIEWS:
            first, last = name.split(" ", 1)
            user, created = User.objects.get_or_create(
                username=email,
                defaults={"email": email, "first_name": first, "last_name": last},
            )
            if created:
                user.set_password("Demo@12345")
                user.save()
            reviewers.append(user)

        self.stdout.write("Creating operators and buses...")
        operators = {}
        for data in OPERATORS:
            operator, _ = BusOperator.objects.update_or_create(name=data["name"], defaults=data)
            operators[operator.name] = operator

        buses = {}
        for data in BUSES:
            operator = operators[data["operator"]]
            defaults = {k: v for k, v in data.items() if k != "operator"}
            bus, _ = Bus.objects.update_or_create(
                registration_number=data["registration_number"], defaults={"operator": operator, **defaults}
            )
            buses[bus.name] = bus

        self.stdout.write("Creating routes...")
        routes = []
        for source, destination, distance, duration, fare, image, popular, description in ROUTES:
            route, _ = Route.objects.update_or_create(
                source=source,
                destination=destination,
                defaults={
                    "distance_km": distance,
                    "duration_minutes": duration,
                    "base_fare": Decimal(fare),
                    "image": image,
                    "is_popular": popular,
                    "is_active": True,
                    "description": description,
                },
            )
            routes.append(route)

        self.stdout.write(f"Creating schedules for the next {days} days and past demo journeys...")
        schedule_count = 0
        seat_count = 0
        bus_list = list(buses.values())

        for r_idx, route in enumerate(routes):
            for d in range(days):
                travel_date = today + timedelta(days=d)
                for s_idx in range(2):
                    bus = bus_list[(r_idx + s_idx * 2) % len(bus_list)]
                    dep = DEPARTURES[(r_idx + s_idx) % len(DEPARTURES)]
                    departure_dt = datetime.combine(travel_date, dep)
                    arrival_dt = departure_dt + timedelta(minutes=route.duration_minutes)
                    fare = route.base_fare + Decimal(s_idx * 120)
                    schedule, created = BusSchedule.objects.get_or_create(
                        bus=bus,
                        route=route,
                        travel_date=travel_date,
                        departure_time=dep,
                        defaults={"arrival_time": arrival_dt.time(), "fare": fare, "is_active": True},
                    )
                    if created:
                        schedule_count += 1
                    seat_count += schedule.ensure_seats()

        # A handful of past schedules for completed journeys and revenue analytics.
        past_offsets = [26, 19, 13, 9, 5, 2]
        for idx, offset in enumerate(past_offsets):
            route = routes[idx % len(routes)]
            bus = bus_list[(idx + 1) % len(bus_list)]
            travel_date = today - timedelta(days=offset)
            dep = DEPARTURES[idx % len(DEPARTURES)]
            departure_dt = datetime.combine(travel_date, dep)
            arrival_dt = departure_dt + timedelta(minutes=route.duration_minutes)
            schedule, created = BusSchedule.objects.get_or_create(
                bus=bus,
                route=route,
                travel_date=travel_date,
                departure_time=dep,
                defaults={
                    "arrival_time": arrival_dt.time(),
                    "fare": route.base_fare,
                    "is_active": True,
                },
            )
            if created:
                schedule_count += 1
            seat_count += schedule.ensure_seats()

        self.stdout.write("Creating reviews...")
        approved_reviews = 0
        for idx, (name, email, route_text, rating, title, comment) in enumerate(REVIEWS):
            user = reviewers[idx]
            route = next((r for r in routes if f"{r.source} → {r.destination}" == route_text), routes[idx % len(routes)])
            schedule = BusSchedule.objects.filter(route=route).order_by("-travel_date").first()
            review, created = Review.objects.get_or_create(
                user=user,
                schedule=schedule,
                defaults={
                    "bus": schedule.bus if schedule else None,
                    "rating": rating,
                    "title": title,
                    "comment": comment,
                    "is_approved": True,
                },
            )
            if not created and not review.is_approved:
                review.is_approved = True
                review.save(update_fields=["is_approved"])
            approved_reviews += 1

        self.stdout.write("Creating demo bookings...")
        if not Booking.objects.filter(user=demo).exists():
            self._create_demo_bookings(demo, routes, now)

        self.stdout.write(self.style.SUCCESS("\nBUSGO demo data ready!"))
        self.stdout.write(f"  Operators: {BusOperator.objects.count()}")
        self.stdout.write(f"  Buses: {Bus.objects.count()}")
        self.stdout.write(f"  Routes: {Route.objects.count()}")
        self.stdout.write(f"  Schedules: {BusSchedule.objects.count()} (new this run: {schedule_count})")
        self.stdout.write(f"  Seats: {seat_count} ensured")
        self.stdout.write(f"  Reviews: {approved_reviews}")
        self.stdout.write("")
        self.stdout.write(self.style.WARNING("Login credentials"))
        self.stdout.write("  Admin : admin@busgo.com / Admin@12345  (also /admin/)")
        self.stdout.write("  Demo  : demo@busgo.com / Demo@12345")

    def _create_demo_bookings(self, demo, routes, now):
        future_specs = [(0, 2, 2), (1, 4, 2), (2, 6, 1)]
        past_specs = [(0, 12, 1), (1, 5, 2), (2, 2, 1)]

        def build(schedule, count, offset, names, days_ago=0, method=Payment.Method.UPI):
            seats = list(schedule.seats.order_by("deck", "row", "col")[offset : offset + count])
            if len(seats) < count:
                return None
            subtotal, fee, gst, total = calculate_charges(seats)
            booking = Booking.objects.create(
                booking_id=_unique_booking_id(),
                user=demo,
                schedule=schedule,
                journey_date=schedule.travel_date,
                journey_source=schedule.route.source,
                journey_destination=schedule.route.destination,
                status=Booking.Status.CONFIRMED,
                contact_name="Aarav Sharma",
                contact_email="demo@busgo.com",
                contact_phone="9876543210",
                seat_subtotal=subtotal,
                convenience_fee=fee,
                gst_amount=gst,
                total_amount=total,
                ticket_number=_unique_ticket_number(),
                confirmed_at=now - timedelta(days=days_ago),
            )
            BookingSeat.objects.bulk_create(
                [BookingSeat(booking=booking, seat=seat, fare=seat.price) for seat in seats]
            )
            for seat, name in zip(seats, names):
                Passenger.objects.create(
                    booking=booking,
                    booking_seat=BookingSeat.objects.get(booking=booking, seat=seat),
                    name=name,
                    age=random.randint(21, 48),
                    gender="Female" if name.split()[0].endswith("a") else "Male",
                    phone="9876543210",
                    email="demo@busgo.com",
                )
            Payment.objects.create(
                booking=booking,
                method=method,
                amount=total,
                status=Payment.Status.SUCCESS,
                gateway=Payment.Gateway.SIMULATED,
                paid_at=now - timedelta(days=days_ago),
            )
            return booking

        future_names = [
            ["Aarav Sharma", "Meera Sharma"],
            ["Aarav Sharma", "Raghav Sharma"],
            ["Aarav Sharma"],
        ]
        for (r_idx, offset_days, count), names in zip(future_specs, future_names):
            route = routes[r_idx]
            schedule = (
                BusSchedule.objects.filter(route=route, travel_date__gte=timezone.localdate())
                .order_by("travel_date", "departure_time")
                .first()
            )
            if schedule:
                build(schedule, count, offset_days % 4, names)

        past_names = [["Aarav Sharma"], ["Aarav Sharma", "Meera Sharma"], ["Aarav Sharma"]]
        for (r_idx, offset_days, count), names in zip(past_specs, past_names):
            route = routes[r_idx]
            schedule = (
                BusSchedule.objects.filter(route=route, travel_date__lt=timezone.localdate())
                .order_by("-travel_date")
                .first()
            )
            if schedule:
                build(schedule, count, offset_days % 3, names, days_ago=offset_days, method=Payment.Method.CREDIT_CARD)

        # One cancelled future booking so the dashboard shows cancellations/refunds.
        route = routes[3]
        schedule = (
            BusSchedule.objects.filter(route=route, travel_date__gte=timezone.localdate())
            .order_by("travel_date", "departure_time")
            .first()
        )
        if schedule:
            cancelled = build(schedule, 1, 5, ["Aarav Sharma"])
            if cancelled:
                try:
                    cancel_booking(cancelled.booking_id, demo, "Change of travel plans.")
                except Exception:
                    cancelled.status = Booking.Status.CANCELLED
                    cancelled.save(update_fields=["status"])
