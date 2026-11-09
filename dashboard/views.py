import json
from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate, TruncMonth
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from bookings.models import Booking, BookingSeat, Cancellation, Passenger
from bookings.services import release_expired_bookings
from buses.models import Bus, BusOperator, BusSchedule, Route, Seat
from payments.models import Payment

from .forms import BusForm, CancellationProcessForm, OperatorForm, RouteForm, ScheduleForm

staff_required = staff_member_required(login_url="accounts:login")


def _month_start(value):
    return value.replace(day=1)


def _add_months(value, months):
    month = value.month - 1 + months
    year = value.year + month // 12
    month = month % 12 + 1
    return value.replace(year=year, month=month, day=1)


@staff_required
def dashboard_home(request):
    release_expired_bookings()
    today = timezone.localdate()
    now = timezone.now()

    revenue = Payment.objects.filter(status=Payment.Status.SUCCESS).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    refunds = Payment.objects.filter(status=Payment.Status.REFUNDED).aggregate(total=Sum("refund_amount"))["total"] or Decimal("0")
    today_revenue = (
        Payment.objects.filter(status=Payment.Status.SUCCESS, paid_at__date=today).aggregate(total=Sum("amount"))["total"]
        or Decimal("0")
    )

    stats = {
        "users": User.objects.filter(is_staff=False).count(),
        "buses": Bus.objects.count(),
        "routes": Route.objects.count(),
        "schedules": BusSchedule.objects.filter(travel_date__gte=today).count(),
        "bookings": Booking.objects.count(),
        "confirmed": Booking.objects.filter(status=Booking.Status.CONFIRMED).count(),
        "today_bookings": Booking.objects.filter(created_at__date=today).count(),
        "revenue": revenue,
        "refunds": refunds,
        "net_revenue": revenue - refunds,
        "today_revenue": today_revenue,
        "pending_cancellations": Cancellation.objects.filter(status=Cancellation.Status.REQUESTED).count(),
    }

    # 14-day booking + revenue trend
    start = today - timedelta(days=13)
    daily_bookings = {
        row["day"]: row["count"]
        for row in Booking.objects.filter(created_at__date__gte=start)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(count=Count("id"))
    }
    daily_revenue = {
        row["day"]: float(row["total"] or 0)
        for row in Payment.objects.filter(
            status=Payment.Status.SUCCESS, paid_at__date__gte=start
        )
        .annotate(day=TruncDate("paid_at"))
        .values("day")
        .annotate(total=Sum("amount"))
    }
    trend_labels, trend_bookings, trend_revenue = [], [], []
    for i in range(14):
        day = start + timedelta(days=i)
        trend_labels.append(day.strftime("%d %b"))
        trend_bookings.append(daily_bookings.get(day, 0))
        trend_revenue.append(round(daily_revenue.get(day, 0), 2))

    status_rows = Booking.objects.values("status").annotate(count=Count("id"))
    status_map = dict(Booking.Status.choices)
    status_labels = [status_map.get(row["status"], row["status"]) for row in status_rows]
    status_counts = [row["count"] for row in status_rows]

    # 6-month revenue
    month_start = _add_months(_month_start(today), -5)
    monthly = {}
    for row in (
        Payment.objects.filter(status=Payment.Status.SUCCESS, paid_at__date__gte=month_start)
        .annotate(month=TruncMonth("paid_at"))
        .values("month")
        .annotate(total=Sum("amount"))
    ):
        key = row["month"].date() if hasattr(row["month"], "date") else row["month"]
        monthly[key] = float(row["total"] or 0)
    monthly_labels, monthly_values = [], []
    for i in range(6):
        month = _add_months(month_start, i)
        monthly_labels.append(month.strftime("%b %Y"))
        monthly_values.append(round(monthly.get(month, 0), 2))

    top_routes = (
        Booking.objects.filter(status=Booking.Status.CONFIRMED)
        .values("schedule__route__source", "schedule__route__destination")
        .annotate(bookings=Count("id"), revenue=Sum("total_amount"))
        .order_by("-bookings")[:5]
    )

    charts = {
        "trend": {"labels": trend_labels, "bookings": trend_bookings, "revenue": trend_revenue},
        "status": {"labels": status_labels, "counts": status_counts},
        "monthly": {"labels": monthly_labels, "values": monthly_values},
        "routes": {
            "labels": [f"{r['schedule__route__source']} → {r['schedule__route__destination']}" for r in top_routes],
            "counts": [r["bookings"] for r in top_routes],
        },
    }

    recent_bookings = (
        Booking.objects.select_related("user", "schedule__route", "schedule__bus__operator")
        .order_by("-created_at")[:8]
    )
    upcoming = (
        BusSchedule.objects.filter(travel_date__gte=today, is_active=True)
        .select_related("bus__operator", "route")
        .order_by("travel_date", "departure_time")[:6]
    )
    recent_cancellations = Cancellation.objects.select_related("booking__user").order_by("-requested_at")[:5]

    return render(
        request,
        "dashboard/index.html",
        {
            "stats": stats,
            "charts": charts,
            "charts_json": json.dumps(charts),
            "recent_bookings": recent_bookings,
            "upcoming": upcoming,
            "recent_cancellations": recent_cancellations,
            "active": "dashboard",
        },
    )


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------
@staff_required
def operator_list(request):
    query = request.GET.get("q", "").strip()
    operators = BusOperator.objects.annotate(bus_count=Count("buses")).order_by("name")
    if query:
        operators = operators.filter(Q(name__icontains=query) | Q(contact_email__icontains=query))
    page = Paginator(operators, 12).get_page(request.GET.get("page"))
    return render(
        request,
        "dashboard/operators.html",
        {"page_obj": page, "query": query, "active": "operators"},
    )


@staff_required
def operator_form(request, pk=None):
    operator = get_object_or_404(BusOperator, pk=pk) if pk else None
    form = OperatorForm(request.POST or None, request.FILES or None, instance=operator)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        messages.success(request, f"Operator '{obj.name}' saved successfully.")
        return redirect("dashboard:operator_list")
    return render(
        request,
        "dashboard/form.html",
        {
            "form": form,
            "title": "Edit operator" if operator else "Add bus operator",
            "subtitle": "Operators own the buses and are shown on every search result.",
            "cancel_url": reverse("dashboard:operator_list"),
            "active": "operators",
        },
    )


@staff_required
@require_POST
def operator_delete(request, pk):
    operator = get_object_or_404(BusOperator, pk=pk)
    try:
        name = operator.name
        operator.delete()
        messages.success(request, f"Operator '{name}' deleted.")
    except ProtectedError:
        messages.error(request, "This operator has buses attached and cannot be deleted. Deactivate it instead.")
    return redirect("dashboard:operator_list")


# ---------------------------------------------------------------------------
# Buses
# ---------------------------------------------------------------------------
@staff_required
def bus_list(request):
    query = request.GET.get("q", "").strip()
    buses = Bus.objects.select_related("operator").order_by("operator__name", "name")
    if query:
        buses = buses.filter(
            Q(name__icontains=query)
            | Q(registration_number__icontains=query)
            | Q(operator__name__icontains=query)
        )
    page = Paginator(buses, 12).get_page(request.GET.get("page"))
    return render(request, "dashboard/buses.html", {"page_obj": page, "query": query, "active": "buses"})


@staff_required
def bus_form(request, pk=None):
    bus = get_object_or_404(Bus, pk=pk) if pk else None
    form = BusForm(request.POST or None, request.FILES or None, instance=bus)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        messages.success(request, f"Bus '{obj.name}' saved successfully.")
        return redirect("dashboard:bus_list")
    return render(
        request,
        "dashboard/form.html",
        {
            "form": form,
            "title": "Edit bus" if bus else "Add a bus",
            "subtitle": "Choose a seat layout — 40-seater 2+2 or 36-berth sleeper 2+1.",
            "cancel_url": reverse("dashboard:bus_list"),
            "active": "buses",
        },
    )


@staff_required
@require_POST
def bus_delete(request, pk):
    bus = get_object_or_404(Bus, pk=pk)
    try:
        name = bus.name
        bus.delete()
        messages.success(request, f"Bus '{name}' deleted.")
    except ProtectedError:
        messages.error(request, "This bus is referenced by existing bookings and cannot be deleted.")
    return redirect("dashboard:bus_list")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@staff_required
def route_list(request):
    query = request.GET.get("q", "").strip()
    routes = Route.objects.annotate(schedule_count=Count("schedules")).order_by("source", "destination")
    if query:
        routes = routes.filter(Q(source__icontains=query) | Q(destination__icontains=query))
    page = Paginator(routes, 12).get_page(request.GET.get("page"))
    return render(request, "dashboard/routes.html", {"page_obj": page, "query": query, "active": "routes"})


@staff_required
def route_form(request, pk=None):
    route = get_object_or_404(Route, pk=pk) if pk else None
    form = RouteForm(request.POST or None, instance=route)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        messages.success(request, f"Route {obj} saved successfully.")
        return redirect("dashboard:route_list")
    return render(
        request,
        "dashboard/form.html",
        {
            "form": form,
            "title": "Edit route" if route else "Add a route",
            "subtitle": "Routes power the homepage search and popular destinations.",
            "cancel_url": reverse("dashboard:route_list"),
            "active": "routes",
        },
    )


@staff_required
@require_POST
def route_delete(request, pk):
    route = get_object_or_404(Route, pk=pk)
    try:
        name = str(route)
        route.delete()
        messages.success(request, f"Route {name} deleted.")
    except ProtectedError:
        messages.error(request, "This route has bookings and cannot be deleted. Deactivate it instead.")
    return redirect("dashboard:route_list")


# ---------------------------------------------------------------------------
# Schedules & seat layout
# ---------------------------------------------------------------------------
@staff_required
def schedule_list(request):
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    schedules = BusSchedule.objects.select_related("bus__operator", "route").order_by("-travel_date", "departure_time")
    if query:
        schedules = schedules.filter(
            Q(route__source__icontains=query)
            | Q(route__destination__icontains=query)
            | Q(bus__name__icontains=query)
            | Q(bus__operator__name__icontains=query)
        )
    if status == "upcoming":
        schedules = schedules.filter(travel_date__gte=timezone.localdate())
    elif status == "past":
        schedules = schedules.filter(travel_date__lt=timezone.localdate())
    page = Paginator(schedules, 15).get_page(request.GET.get("page"))
    return render(
        request,
        "dashboard/schedules.html",
        {"page_obj": page, "query": query, "status": status, "active": "schedules"},
    )


@staff_required
def schedule_form(request, pk=None):
    schedule = get_object_or_404(BusSchedule, pk=pk) if pk else None
    old_bus_id = schedule.bus_id if schedule else None
    form = ScheduleForm(request.POST or None, instance=schedule)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        if old_bus_id and old_bus_id != obj.bus_id:
            linked = BookingSeat.objects.filter(seat__schedule=obj).exists()
            if linked:
                messages.warning(request, "Bus changed, but existing seats were kept because bookings reference them.")
            else:
                obj.seats.all().delete()
        obj.ensure_seats()
        messages.success(request, f"Schedule saved with {obj.seats.count()} seats ready.")
        return redirect("dashboard:schedule_list")
    return render(
        request,
        "dashboard/form.html",
        {
            "form": form,
            "title": "Edit schedule" if schedule else "Add a schedule",
            "subtitle": "Seats are generated automatically from the bus layout when you save.",
            "cancel_url": reverse("dashboard:schedule_list"),
            "active": "schedules",
        },
    )


@staff_required
@require_POST
def schedule_delete(request, pk):
    schedule = get_object_or_404(BusSchedule, pk=pk)
    try:
        label = str(schedule)
        schedule.delete()
        messages.success(request, f"Schedule {label} deleted.")
    except ProtectedError:
        messages.error(request, "This schedule has bookings and cannot be deleted.")
    return redirect("dashboard:schedule_list")


@staff_required
def seat_layout(request, pk):
    schedule = get_object_or_404(
        BusSchedule.objects.select_related("bus__operator", "route"), pk=pk
    )
    schedule.ensure_seats()
    booked_ids = set(
        BookingSeat.objects.filter(
            seat__schedule=schedule,
            booking__status__in=[Booking.Status.PENDING, Booking.Status.CONFIRMED],
        ).values_list("seat_id", flat=True)
    )
    decks = {}
    for seat in schedule.seats.order_by("deck", "row", "col"):
        decks.setdefault(seat.deck, []).append(
            {"seat": seat, "booked": seat.id in booked_ids}
        )
    return render(
        request,
        "dashboard/seat_layout.html",
        {
            "schedule": schedule,
            "decks": decks,
            "booked_ids": booked_ids,
            "active": "schedules",
        },
    )


@staff_required
@require_POST
def seat_layout_action(request, pk):
    schedule = get_object_or_404(BusSchedule, pk=pk)
    action = request.POST.get("action")
    seat_ids = request.POST.getlist("seat_ids")

    if action == "regenerate":
        linked = BookingSeat.objects.filter(seat__schedule=schedule).exists()
        if linked:
            messages.error(request, "Cannot regenerate seats while bookings reference this schedule.")
        else:
            schedule.seats.all().delete()
            schedule.ensure_seats()
            messages.success(request, f"Seat layout regenerated ({schedule.seats.count()} seats).")
        return redirect("dashboard:seat_layout", pk=schedule.pk)

    if action in ("block", "unblock"):
        if not seat_ids:
            messages.warning(request, "Select at least one seat first.")
            return redirect("dashboard:seat_layout", pk=schedule.pk)
        seats = schedule.seats.filter(id__in=seat_ids)
        if action == "block":
            blocked_booked = seats.filter(id__in=BookingSeat.objects.filter(seat__schedule=schedule).values("seat_id")).count()
            updated = seats.exclude(
                id__in=BookingSeat.objects.filter(seat__schedule=schedule).values("seat_id")
            ).update(is_active=False)
            messages.success(request, f"{updated} seat(s) blocked. {blocked_booked} booked seat(s) were left untouched.")
        else:
            updated = seats.update(is_active=True)
            messages.success(request, f"{updated} seat(s) re-opened for sale.")
        return redirect("dashboard:seat_layout", pk=schedule.pk)

    messages.error(request, "Unknown seat action.")
    return redirect("dashboard:seat_layout", pk=schedule.pk)


# ---------------------------------------------------------------------------
# Bookings, passengers, payments, cancellations
# ---------------------------------------------------------------------------
@staff_required
def booking_list(request):
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    bookings = Booking.objects.select_related("user", "schedule__route", "schedule__bus__operator").order_by("-created_at")
    if query:
        bookings = bookings.filter(
            Q(booking_id__icontains=query)
            | Q(ticket_number__icontains=query)
            | Q(contact_name__icontains=query)
            | Q(contact_email__icontains=query)
            | Q(contact_phone__icontains=query)
        )
    if status:
        bookings = bookings.filter(status=status)
    page = Paginator(bookings, 15).get_page(request.GET.get("page"))
    return render(
        request,
        "dashboard/bookings.html",
        {
            "page_obj": page,
            "query": query,
            "status": status,
            "status_choices": Booking.Status.choices,
            "active": "bookings",
        },
    )


@staff_required
def booking_detail(request, booking_id):
    booking = get_object_or_404(
        Booking.objects.select_related("user", "schedule__bus__operator", "schedule__route").prefetch_related(
            "booking_seats__seat", "passengers", "payments"
        ),
        booking_id=booking_id,
    )
    cancellation = getattr(booking, "cancellation", None)
    return render(
        request,
        "dashboard/booking_detail.html",
        {"booking": booking, "cancellation": cancellation, "active": "bookings"},
    )


@staff_required
def passenger_list(request):
    query = request.GET.get("q", "").strip()
    passengers = Passenger.objects.select_related("booking", "booking_seat__seat").order_by("-created_at")
    if query:
        passengers = passengers.filter(
            Q(name__icontains=query)
            | Q(phone__icontains=query)
            | Q(booking__booking_id__icontains=query)
        )
    page = Paginator(passengers, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "dashboard/passengers.html",
        {"page_obj": page, "query": query, "active": "passengers"},
    )


@staff_required
def payment_list(request):
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    payments = Payment.objects.select_related("booking__user").order_by("-created_at")
    if query:
        payments = payments.filter(
            Q(payment_id__icontains=query)
            | Q(booking__booking_id__icontains=query)
            | Q(gateway_payment_id__icontains=query)
        )
    if status:
        payments = payments.filter(status=status)
    totals = payments.aggregate(total=Sum("amount"))
    page = Paginator(payments, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "dashboard/payments.html",
        {
            "page_obj": page,
            "query": query,
            "status": status,
            "status_choices": Payment.Status.choices,
            "filtered_total": totals["total"] or 0,
            "active": "payments",
        },
    )


@staff_required
def cancellation_list(request):
    status = request.GET.get("status", "")
    cancellations = Cancellation.objects.select_related("booking__user", "booking__schedule__route").order_by(
        "-requested_at"
    )
    if status:
        cancellations = cancellations.filter(status=status)
    page = Paginator(cancellations, 15).get_page(request.GET.get("page"))
    return render(
        request,
        "dashboard/cancellations.html",
        {
            "page_obj": page,
            "status": status,
            "status_choices": Cancellation.Status.choices,
            "active": "cancellations",
        },
    )


@staff_required
def cancellation_process(request, pk):
    cancellation = get_object_or_404(
        Cancellation.objects.select_related("booking__user", "booking__schedule__route"), pk=pk
    )
    form = CancellationProcessForm(request.POST or None, instance=cancellation)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        if obj.status != Cancellation.Status.REQUESTED and not obj.processed_at:
            obj.processed_at = timezone.now()
        obj.save()
        messages.success(request, f"Cancellation request for {obj.booking.booking_id} updated.")
        return redirect("dashboard:cancellation_list")
    return render(
        request,
        "dashboard/form.html",
        {
            "form": form,
            "title": f"Process cancellation · {cancellation.booking.booking_id}",
            "subtitle": "Refunds for auto-approved cancellations are initiated immediately to the original method.",
            "cancel_url": reverse("dashboard:cancellation_list"),
            "active": "cancellations",
        },
    )
