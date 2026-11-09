from datetime import date as date_cls
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Count, Min, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from bookings.models import Booking, BookingSeat
from bookings.services import release_expired_bookings

from .forms import ContactForm, NewsletterForm
from .models import Bus, BusOperator, BusSchedule, ContactMessage, NewsletterSubscriber, Review, Route

DEPARTURE_SLOTS = [
    ("early", "Before 6 AM", 0, 6),
    ("morning", "6 AM – 12 PM", 6, 12),
    ("afternoon", "12 PM – 5 PM", 12, 17),
    ("evening", "5 PM – 9 PM", 17, 21),
    ("night", "After 9 PM", 21, 24),
]


def _cities():
    sources = list(Route.objects.filter(is_active=True).values_list("source", flat=True).distinct())
    destinations = list(Route.objects.filter(is_active=True).values_list("destination", flat=True).distinct())
    return sorted(set(sources + destinations), key=str.lower)


def _attach_availability(schedules, now=None):
    """Attach booked/available counts to schedules using one aggregate query."""
    now = now or timezone.now()
    ids = [s.id for s in schedules]
    booked_counts = {}
    if ids:
        rows = (
            BookingSeat.objects.filter(
                seat__schedule_id__in=ids,
                seat__is_active=True,
                booking__status__in=[Booking.Status.PENDING, Booking.Status.CONFIRMED],
            )
            .exclude(booking__status=Booking.Status.PENDING, booking__expires_at__lt=now)
            .values("seat__schedule_id")
            .annotate(total=Count("id"))
        )
        booked_counts = {row["seat__schedule_id"]: row["total"] for row in rows}
    for schedule in schedules:
        booked = booked_counts.get(schedule.id, 0)
        total = getattr(schedule, "seat_total", None)
        if total is None:
            total = schedule.seats.filter(is_active=True).count()
        schedule.booked_count = booked
        schedule.available_count = max(total - booked, 0)
    return schedules


def home(request):
    release_expired_bookings()
    today = timezone.localdate()

    popular_routes = list(
        Route.objects.filter(is_active=True)
        .annotate(min_fare=Min("schedules__fare", filter=Q(schedules__travel_date__gte=today, schedules__is_active=True)))
        .order_by("-is_popular", "source")[:6]
    )

    now = timezone.now()
    upcoming = list(
        BusSchedule.objects.filter(
            travel_date__gte=today,
            is_active=True,
            bus__is_active=True,
            bus__operator__is_active=True,
        )
        .select_related("bus__operator", "route")
        .annotate(seat_total=Count("seats", filter=Q(seats__is_active=True), distinct=True))
        .order_by("travel_date", "departure_time")[:180]
    )
    # Date-only lookups include departures earlier today — hide those.
    upcoming = [s for s in upcoming if s.departure_datetime > now]
    _attach_availability(upcoming, now=now)

    featured = []
    seen_buses = set()
    for schedule in upcoming:
        if schedule.bus_id in seen_buses or schedule.available_count <= 0:
            continue
        seen_buses.add(schedule.bus_id)
        featured.append(schedule)
        if len(featured) >= 6:
            break

    reviews = (
        Review.objects.filter(is_approved=True)
        .select_related("user__profile", "bus")
        .order_by("-created_at")[:6]
    )

    stats = {
        "buses": Bus.objects.filter(is_active=True).count(),
        "routes": Route.objects.filter(is_active=True).count(),
        "travellers": User.objects.filter(is_active=True).count(),
        "bookings": Booking.objects.filter(status=Booking.Status.CONFIRMED).count(),
    }

    return render(
        request,
        "home.html",
        {
            "popular_routes": popular_routes,
            "featured": featured,
            "reviews": reviews,
            "stats": stats,
            "cities": _cities(),
            "today": today,
            "offers": [
                {
                    "image": "images/offer-1.jpg",
                    "tag": "FIRST TRIP",
                    "title": "Flat 15% off your first journey",
                    "code": "BUSGO15",
                    "text": "New to BUSGO? Save on your very first booking across any route.",
                },
                {
                    "image": "images/offer-2.jpg",
                    "tag": "WEEKEND ESCAPE",
                    "title": "Weekend getaways from ₹499",
                    "code": "WEEKEND",
                    "text": "Handpicked hill stations, beaches and heritage cities every Friday–Sunday.",
                },
                {
                    "image": "images/offer-3.jpg",
                    "tag": "SLEEPER SPECIAL",
                    "title": "Up to 20% off AC sleeper berths",
                    "code": "DREAMRIDE",
                    "text": "Lie back, relax and arrive refreshed with our premium sleeper partners.",
                },
            ],
        },
    )


def search(request):
    release_expired_bookings()
    today = timezone.localdate()
    source = (request.GET.get("from") or "").strip()
    destination = (request.GET.get("to") or "").strip()
    date_raw = (request.GET.get("date") or "").strip()

    selected_date = today
    if date_raw:
        try:
            selected_date = datetime.strptime(date_raw, "%Y-%m-%d").date()
        except ValueError:
            messages.warning(request, "Invalid journey date. Showing buses for today instead.")
    if selected_date < today:
        messages.warning(request, "Journey date cannot be in the past. Showing buses for today.")
        selected_date = today

    schedules = []
    no_route = False
    if source and destination:
        if source.lower() == destination.lower():
            messages.error(request, "Source and destination cannot be the same.")
        else:
            routes = Route.objects.filter(
                source__iexact=source, destination__iexact=destination, is_active=True
            )
            if not routes.exists():
                no_route = True
            schedules = list(
                BusSchedule.objects.filter(
                    route__in=routes,
                    travel_date=selected_date,
                    is_active=True,
                    bus__is_active=True,
                    bus__operator__is_active=True,
                )
                .select_related("bus__operator", "route")
                .annotate(seat_total=Count("seats", filter=Q(seats__is_active=True), distinct=True))
                .order_by("departure_time")
            )
            now = timezone.now()
            # Never show a departure that has already left, even if it is today.
            schedules = [s for s in schedules if s.departure_datetime > now]
            _attach_availability(schedules, now=now)

    bus_types = sorted({s.bus.bus_type for s in schedules})
    operators = sorted({s.bus.operator.name for s in schedules})

    selected_bus_type = request.GET.get("bus_type", "")
    selected_ac = request.GET.get("ac", "")
    selected_slot = request.GET.get("departure", "")
    selected_operator = request.GET.get("operator", "")
    min_price = request.GET.get("min_price", "")
    max_price = request.GET.get("max_price", "")
    hide_sold_out = request.GET.get("available", "1") != "0"
    sort = request.GET.get("sort", "departure")

    if selected_bus_type:
        schedules = [s for s in schedules if s.bus.bus_type == selected_bus_type]
    if selected_ac == "ac":
        schedules = [s for s in schedules if s.bus.is_ac]
    elif selected_ac == "non-ac":
        schedules = [s for s in schedules if not s.bus.is_ac]
    if selected_operator:
        schedules = [s for s in schedules if s.bus.operator.name == selected_operator]
    if selected_slot:
        slot = next((s for s in DEPARTURE_SLOTS if s[0] == selected_slot), None)
        if slot:
            schedules = [s for s in schedules if slot[2] <= s.departure_time.hour < slot[3]]
    try:
        if min_price:
            schedules = [s for s in schedules if float(s.fare) >= float(min_price)]
        if max_price:
            schedules = [s for s in schedules if float(s.fare) <= float(max_price)]
    except ValueError:
        messages.warning(request, "Price filters were invalid and have been ignored.")
    if hide_sold_out:
        schedules = [s for s in schedules if s.available_count > 0]

    if sort == "price_asc":
        schedules.sort(key=lambda s: s.fare)
    elif sort == "price_desc":
        schedules.sort(key=lambda s: s.fare, reverse=True)
    elif sort == "rating":
        schedules.sort(key=lambda s: s.bus.rating, reverse=True)
    elif sort == "seats":
        schedules.sort(key=lambda s: s.available_count, reverse=True)
    else:
        schedules.sort(key=lambda s: s.departure_time)

    paginator = Paginator(schedules, 8)
    page_obj = paginator.get_page(request.GET.get("page"))

    query = request.GET.copy()
    query.pop("page", None)
    querystring = query.urlencode()

    return render(
        request,
        "buses/bus_search.html",
        {
            "source": source,
            "destination": destination,
            "selected_date": selected_date,
            "today": today,
            "schedules": schedules,
            "page_obj": page_obj,
            "paginator": paginator,
            "no_route": no_route,
            "cities": _cities(),
            "bus_types": bus_types,
            "operators": operators,
            "departure_slots": DEPARTURE_SLOTS,
            "selected_bus_type": selected_bus_type,
            "selected_ac": selected_ac,
            "selected_slot": selected_slot,
            "selected_operator": selected_operator,
            "min_price": min_price,
            "max_price": max_price,
            "hide_sold_out": hide_sold_out,
            "sort": sort,
            "querystring": querystring,
            "result_count": len(schedules),
        },
    )


def bus_details(request, schedule_id):
    release_expired_bookings()
    schedule = get_object_or_404(
        BusSchedule.objects.select_related("bus__operator", "route").prefetch_related("seats"),
        pk=schedule_id,
        is_active=True,
    )
    schedule.ensure_seats()
    booked_ids = schedule.booked_seat_ids
    total = schedule.seats.filter(is_active=True).count()
    schedule.booked_count = len(booked_ids)
    schedule.available_count = max(total - len(booked_ids), 0)
    schedule.seat_total = total

    reviews = (
        Review.objects.filter(is_approved=True)
        .filter(Q(bus=schedule.bus) | Q(schedule__route=schedule.route))
        .select_related("user__profile")
        .distinct()[:4]
    )
    similar = list(
        BusSchedule.objects.filter(
            route=schedule.route,
            travel_date__gte=timezone.localdate(),
            is_active=True,
            bus__is_active=True,
        )
        .exclude(pk=schedule.pk)
        .select_related("bus__operator", "route")
        .annotate(seat_total=Count("seats", filter=Q(seats__is_active=True), distinct=True))
        .order_by("travel_date", "departure_time")[:4]
    )
    _attach_availability(similar)

    return render(
        request,
        "buses/bus_details.html",
        {"schedule": schedule, "reviews": reviews, "similar": similar},
    )


def about(request):
    stats = {
        "buses": Bus.objects.filter(is_active=True).count(),
        "routes": Route.objects.filter(is_active=True).count(),
        "travellers": User.objects.filter(is_active=True).count(),
        "bookings": Booking.objects.filter(status=Booking.Status.CONFIRMED).count(),
    }
    reviews = Review.objects.filter(is_approved=True).select_related("user__profile").order_by("-rating")[:3]
    operators = BusOperator.objects.filter(is_active=True)[:8]
    return render(request, "about.html", {"stats": stats, "reviews": reviews, "operators": operators})


def contact(request):
    form = ContactForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            ContactMessage.objects.create(**form.cleaned_data)
            messages.success(
                request,
                "Thank you for reaching out! Our travel support team will reply within 24 hours.",
            )
            return redirect("contact")
        messages.error(request, "Please correct the highlighted fields.")
    return render(request, "contact.html", {"form": form})


def policies(request):
    return render(
        request,
        "policies.html",
        {
            "reservation_minutes": settings.SEAT_RESERVATION_MINUTES,
            "max_seats": settings.MAX_SEATS_PER_BOOKING,
        },
    )


@require_POST
def newsletter_subscribe(request):
    form = NewsletterForm(request.POST)
    if form.is_valid():
        email = form.cleaned_data["email"].strip().lower()
        obj, created = NewsletterSubscriber.objects.get_or_create(email=email, defaults={"is_active": True})
        if not created and not obj.is_active:
            obj.is_active = True
            obj.save(update_fields=["is_active"])
            created = True
        if created:
            messages.success(request, "You're on the list! Travel deals are on their way to your inbox.")
        else:
            messages.info(request, "You're already subscribed to BUSGO travel offers.")
    else:
        messages.error(request, "Please enter a valid email address.")
    return redirect(request.META.get("HTTP_REFERER", "/"))


def error_404(request, exception=None):
    return render(request, "404.html", status=404)


def error_500(request):
    return render(request, "500.html", status=500)
