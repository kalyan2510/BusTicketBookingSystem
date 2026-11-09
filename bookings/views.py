from collections import OrderedDict

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from buses.models import BusSchedule, Review
from payments.ticket import build_ticket_pdf, ensure_ticket_qr

from .forms import CancellationForm, ContactForm, PassengerForm, ReviewForm
from .models import Booking, Passenger
from .services import (
    BookingError,
    CancellationError,
    SeatUnavailableError,
    cancel_booking,
    create_booking,
    release_booking_hold,
    release_expired_bookings,
)


def _seat_decks(schedule, booked_ids):
    decks = OrderedDict()
    for seat in schedule.seats.filter(is_active=True).order_by("deck", "row", "col"):
        decks.setdefault(seat.deck, OrderedDict()).setdefault(seat.row, []).append(
            {
                "id": seat.id,
                "number": seat.seat_number,
                "row": seat.row,
                "col": seat.col,
                "deck": seat.deck,
                "window": seat.is_window,
                "price": str(seat.price),
                "booked": seat.id in booked_ids,
            }
        )
    return [{"name": deck, "rows": [{"number": r, "seats": s} for r, s in rows.items()]} for deck, rows in decks.items()]


@login_required
def seat_selection(request, schedule_id):
    release_expired_bookings()
    schedule = get_object_or_404(
        BusSchedule.objects.select_related("bus__operator", "route"),
        pk=schedule_id,
        is_active=True,
    )
    if schedule.departure_datetime <= timezone.now():
        messages.error(request, "This bus has already departed. Please search for another journey.")
        return redirect("buses:search")

    schedule.ensure_seats()
    active_seat_ids = set(schedule.seats.filter(is_active=True).values_list("id", flat=True))
    booked_ids = schedule.booked_seat_ids & active_seat_ids
    total_active = len(active_seat_ids)
    seats_json = [
        {
            "id": seat.id,
            "number": seat.seat_number,
            "price": str(seat.price),
            "deck": seat.deck,
            "booked": seat.id in booked_ids,
        }
        for seat in schedule.seats.filter(is_active=True).order_by("deck", "row", "col")
    ]

    # Seats carried over from a released hold (the "Back to seats" flow). Only
    # keep ids that genuinely belong to this schedule and are still available.
    available_ids = {str(item["id"]) for item in seats_json if not item["booked"]}
    preselect_ids = [
        value
        for value in (request.GET.get("preselect") or "").split(",")
        if value.strip() and value.strip() in available_ids
    ]

    return render(
        request,
        "bookings/seat_selection.html",
        {
            "schedule": schedule,
            "decks": _seat_decks(schedule, booked_ids),
            "booked_count": len(booked_ids),
            "available_count": max(total_active - len(booked_ids), 0),
            "total_count": total_active,
            "seats_json": seats_json,
            "preselect_ids": preselect_ids,
            "max_seats": settings.MAX_SEATS_PER_BOOKING,
            "convenience_fee": settings.CONVENIENCE_FEE_PER_SEAT,
            "gst_percent": settings.GST_PERCENT,
        },
    )


@login_required
@require_POST
def release_hold(request, booking_id):
    """Release a pending hold and return to the seat map with seats preselected."""
    try:
        booking, seat_ids = release_booking_hold(booking_id, request.user)
    except BookingError as exc:
        messages.error(request, str(exc))
        return redirect("bookings:my_bookings")

    if not seat_ids:
        messages.info(request, "That reservation is no longer awaiting payment.")
        return redirect("bookings:my_bookings")

    messages.info(
        request,
        "Your previous seat hold was released. Your seats are preselected below — adjust them and continue.",
    )
    target = reverse("bookings:seat_selection", args=[booking.schedule_id])
    if seat_ids:
        target = f"{target}?preselect={','.join(str(pk) for pk in seat_ids)}"
    return redirect(target)


@login_required
@require_POST
def create_booking_view(request, schedule_id):
    seat_ids = request.POST.getlist("seat_ids")
    if not seat_ids:
        messages.error(request, "Please select at least one seat to continue.")
        return redirect("bookings:seat_selection", schedule_id=schedule_id)
    try:
        booking = create_booking(request.user, schedule_id, seat_ids)
    except SeatUnavailableError as exc:
        messages.error(request, str(exc))
        return redirect("bookings:seat_selection", schedule_id=schedule_id)
    except BookingError as exc:
        messages.error(request, str(exc))
        return redirect("buses:search")
    messages.success(
        request,
        f"Seats held for {settings.SEAT_RESERVATION_MINUTES} minutes. Enter passenger details to continue.",
    )
    return redirect("bookings:passenger_details", booking_id=booking.booking_id)


@login_required
def passenger_details(request, booking_id):
    release_expired_bookings()
    booking = get_object_or_404(
        Booking.objects.select_related("schedule__bus__operator", "schedule__route").prefetch_related(
            "booking_seats__seat", "passengers"
        ),
        booking_id=booking_id,
        user=request.user,
    )
    if booking.status != Booking.Status.PENDING or booking.is_expired:
        messages.error(request, "This reservation has expired. Please select your seats again.")
        return redirect("bookings:seat_selection", schedule_id=booking.schedule_id)

    booking_seats = list(booking.booking_seats.select_related("seat").order_by("seat__deck", "seat__row", "seat__col"))
    existing = {p.booking_seat_id: p for p in booking.passengers.all()}

    contact_initial = {
        "contact_name": booking.contact_name,
        "contact_email": booking.contact_email,
        "contact_phone": booking.contact_phone,
    }

    if request.method == "POST":
        contact_form = ContactForm(request.POST)
        passenger_forms = [
            PassengerForm(request.POST, prefix=f"seat{bs.id}", initial=None) for bs in booking_seats
        ]
        if contact_form.is_valid() and all(f.is_valid() for f in passenger_forms):
            booking.contact_name = contact_form.cleaned_data["contact_name"]
            booking.contact_email = contact_form.cleaned_data["contact_email"]
            booking.contact_phone = contact_form.cleaned_data["contact_phone"]
            booking.save(update_fields=["contact_name", "contact_email", "contact_phone", "updated_at"])
            for bs, form in zip(booking_seats, passenger_forms):
                data = form.cleaned_data
                Passenger.objects.update_or_create(
                    booking_seat=bs,
                    defaults={
                        "booking": booking,
                        "name": data["name"],
                        "age": data["age"],
                        "gender": data["gender"],
                        "phone": data.get("phone") or booking.contact_phone,
                        "email": data.get("email") or booking.contact_email,
                    },
                )
            messages.success(request, "Passenger details saved. Choose a payment method to confirm your booking.")
            return redirect("payments:checkout", booking_id=booking.booking_id)
        messages.error(request, "Please correct the highlighted passenger details.")
    else:
        contact_form = ContactForm(initial=contact_initial)
        passenger_forms = []
        for bs in booking_seats:
            p = existing.get(bs.id)
            passenger_forms.append(
                PassengerForm(
                    prefix=f"seat{bs.id}",
                    initial={
                        "name": p.name if p else "",
                        "age": p.age if p else "",
                        "gender": p.gender if p else "Male",
                        "phone": p.phone if p else booking.contact_phone,
                        "email": p.email if p else booking.contact_email,
                    },
                )
            )

    seat_forms = list(zip(booking_seats, passenger_forms))
    minutes_left = max(int((booking.expires_at - timezone.now()).total_seconds() // 60), 0)
    return render(
        request,
        "bookings/passenger_details.html",
        {
            "booking": booking,
            "contact_form": contact_form,
            "seat_forms": seat_forms,
            "minutes_left": minutes_left,
        },
    )


@login_required
def booking_detail(request, booking_id):
    booking = get_object_or_404(
        Booking.objects.select_related("schedule__bus__operator", "schedule__route").prefetch_related(
            "booking_seats__seat", "passengers", "payments"
        ),
        booking_id=booking_id,
        user=request.user,
    )
    if booking.status == Booking.Status.CONFIRMED:
        return redirect("bookings:ticket", booking_id=booking.booking_id)
    return render(request, "bookings/booking_detail.html", {"booking": booking})


@login_required
def my_bookings(request):
    release_expired_bookings()
    bookings = list(
        Booking.objects.filter(user=request.user)
        .select_related("schedule__bus__operator", "schedule__route")
        .prefetch_related("booking_seats__seat", "passengers", "payments")
        .order_by("-created_at")
    )
    now = timezone.now()
    upcoming = [b for b in bookings if b.status == Booking.Status.CONFIRMED and b.departure_datetime >= now]
    completed = [b for b in bookings if b.status == Booking.Status.CONFIRMED and b.departure_datetime < now]
    cancelled = [b for b in bookings if b.status in (Booking.Status.CANCELLED, Booking.Status.EXPIRED)]
    pending = [b for b in bookings if b.status == Booking.Status.PENDING and not b.is_expired]
    reviewed_schedule_ids = set(
        Review.objects.filter(user=request.user).values_list("schedule_id", flat=True)
    )

    return render(
        request,
        "bookings/my_bookings.html",
        {
            "upcoming": upcoming,
            "completed": completed,
            "cancelled": cancelled,
            "pending": pending,
            "all_bookings": bookings,
            "review_form": ReviewForm(),
            "reviewed_schedule_ids": reviewed_schedule_ids,
            "total_spent": sum(
                (b.total_amount for b in bookings if b.status == Booking.Status.CONFIRMED), start=0
            ),
        },
    )


@login_required
def ticket(request, booking_id):
    booking = get_object_or_404(
        Booking.objects.select_related("schedule__bus__operator", "schedule__route", "user").prefetch_related(
            "booking_seats__seat", "passengers"
        ),
        booking_id=booking_id,
    )
    if booking.user_id != request.user.id and not request.user.is_staff:
        raise Http404("Ticket not found.")
    if booking.status not in (Booking.Status.CONFIRMED, Booking.Status.CANCELLED):
        messages.info(request, "Your e-ticket will be available once payment is confirmed.")
        return redirect("bookings:detail", booking_id=booking.booking_id)
    if booking.status == Booking.Status.CONFIRMED:
        ensure_ticket_qr(booking, request)
    payment = booking.payments.filter(status__in=["SUCCESS", "REFUNDED"]).order_by("-created_at").first()
    return render(
        request,
        "bookings/ticket.html",
        {"booking": booking, "payment": payment},
    )


@login_required
def ticket_pdf(request, booking_id):
    booking = get_object_or_404(
        Booking.objects.select_related("schedule__bus__operator", "schedule__route", "user").prefetch_related(
            "booking_seats__seat", "passengers"
        ),
        booking_id=booking_id,
    )
    if booking.user_id != request.user.id and not request.user.is_staff:
        raise Http404("Ticket not found.")
    if booking.status != Booking.Status.CONFIRMED:
        messages.error(request, "Only confirmed bookings have a downloadable PDF ticket.")
        return redirect("bookings:detail", booking_id=booking.booking_id)
    pdf = build_ticket_pdf(booking, request)
    filename = f"BUSGO-{booking.ticket_number or booking.booking_id}.pdf"
    return FileResponse(pdf, as_attachment=True, filename=filename, content_type="application/pdf")


@login_required
@require_POST
def cancel_booking_view(request, booking_id):
    form = CancellationForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Please provide a valid cancellation reason.")
        return redirect("bookings:my_bookings")
    try:
        cancellation = cancel_booking(booking_id, request.user, form.cleaned_data["reason"])
    except CancellationError as exc:
        messages.error(request, str(exc))
        return redirect("bookings:my_bookings")
    except BookingError as exc:
        messages.error(request, str(exc))
        return redirect("bookings:my_bookings")
    messages.success(
        request,
        f"Booking cancelled. Refund of Rs. {cancellation.refund_amount:,.2f} "
        f"({cancellation.refund_percent}%) has been initiated to your original payment method.",
    )
    return redirect("bookings:my_bookings")


@login_required
@require_POST
def review_create(request, booking_id):
    booking = get_object_or_404(Booking, booking_id=booking_id, user=request.user)
    if not booking.is_completed:
        messages.error(request, "You can review a journey after it is completed.")
        return redirect("bookings:my_bookings")
    form = ReviewForm(request.POST)
    if form.is_valid():
        Review.objects.update_or_create(
            user=request.user,
            schedule=booking.schedule,
            defaults={
                "bus": booking.schedule.bus,
                "rating": int(form.cleaned_data["rating"]),
                "title": form.cleaned_data.get("title", ""),
                "comment": form.cleaned_data["comment"],
                "is_approved": False,
            },
        )
        messages.success(request, "Thanks! Your review is awaiting moderation and will appear on the site shortly.")
    else:
        messages.error(request, "Please write at least 10 characters in your review.")
    return redirect("bookings:my_bookings")


def verify_ticket(request, ticket_number):
    booking = (
        Booking.objects.select_related("schedule__bus__operator", "schedule__route")
        .prefetch_related("booking_seats__seat", "passengers")
        .filter(ticket_number=ticket_number)
        .first()
    )
    return render(
        request,
        "bookings/verify_ticket.html",
        {"booking": booking, "ticket_number": ticket_number},
    )
