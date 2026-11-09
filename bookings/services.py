"""Transactional services for seat reservation, confirmation and cancellation."""
import secrets
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from buses.models import BusSchedule, Seat

from .models import Booking, BookingSeat, Cancellation, generate_booking_id, generate_ticket_number


class BookingError(Exception):
    """Base error for booking operations."""


class SeatUnavailableError(BookingError):
    """Raised when one or more requested seats are no longer available."""


class BookingExpiredError(BookingError):
    """Raised when the payment window for a booking has elapsed."""


class CancellationError(BookingError):
    """Raised when a booking cannot be cancelled."""


def release_expired_bookings(now=None):
    """Release seats held by unpaid bookings whose reservation window elapsed."""
    from payments.models import Payment

    now = now or timezone.now()
    expired_ids = list(
        Booking.objects.filter(status=Booking.Status.PENDING, expires_at__lt=now).values_list("id", flat=True)
    )
    if not expired_ids:
        return 0
    with transaction.atomic():
        updated = Booking.objects.filter(id__in=expired_ids, status=Booking.Status.PENDING).update(
            status=Booking.Status.EXPIRED, updated_at=now
        )
        Payment.objects.filter(
            booking_id__in=expired_ids,
            status__in=[Payment.Status.INITIATED, Payment.Status.PENDING],
        ).update(status=Payment.Status.FAILED, failure_reason="Reservation expired before payment.")
    return updated


def _unique_booking_id():
    for _ in range(20):
        candidate = generate_booking_id()
        if not Booking.objects.filter(booking_id=candidate).exists():
            return candidate
    return "BG" + secrets.token_hex(5).upper()


def _unique_ticket_number():
    for _ in range(20):
        candidate = generate_ticket_number()
        if not Booking.objects.filter(ticket_number=candidate).exists():
            return candidate
    return "TKT-" + secrets.token_hex(6).upper()


def calculate_charges(seats):
    """Return (subtotal, convenience_fee, gst, total) for a list of Seat objects."""
    subtotal = sum((seat.price for seat in seats), Decimal("0.00"))
    fee = Decimal(str(settings.CONVENIENCE_FEE_PER_SEAT)) * len(seats)
    gst = (subtotal * Decimal(str(settings.GST_PERCENT)) / Decimal("100")).quantize(Decimal("0.01"))
    total = (subtotal + fee + gst).quantize(Decimal("0.01"))
    return subtotal, fee, gst, total


@transaction.atomic
def create_booking(user, schedule_id, seat_ids):
    """Lock the schedule + seats, validate availability and create a PENDING hold."""
    release_expired_bookings()
    seat_ids = [int(s) for s in seat_ids if str(s).isdigit()]
    if not seat_ids:
        raise SeatUnavailableError("Please select at least one seat.")
    if len(set(seat_ids)) > settings.MAX_SEATS_PER_BOOKING:
        raise BookingError(f"You can book a maximum of {settings.MAX_SEATS_PER_BOOKING} seats per transaction.")

    try:
        schedule = (
            BusSchedule.objects.select_for_update()
            .select_related("bus__operator", "route")
            .get(pk=schedule_id, is_active=True)
        )
    except BusSchedule.DoesNotExist:
        raise BookingError("This bus schedule is no longer available.")

    if schedule.departure_datetime <= timezone.now():
        raise BookingError("This bus has already departed. Please choose another journey.")

    seats = list(
        Seat.objects.select_for_update()
        .filter(schedule=schedule, id__in=seat_ids, is_active=True)
        .select_related("schedule")
        .order_by("deck", "row", "col")
    )
    if len(seats) != len(set(seat_ids)):
        raise SeatUnavailableError("One or more selected seats are no longer available.")

    now = timezone.now()
    conflicting = (
        BookingSeat.objects.filter(
            seat__in=seats,
            booking__status__in=[Booking.Status.PENDING, Booking.Status.CONFIRMED],
        )
        .exclude(booking__status=Booking.Status.PENDING, booking__expires_at__lt=now)
        .exists()
    )
    if conflicting:
        raise SeatUnavailableError("Someone just booked one of those seats. Please pick different seats.")

    subtotal, fee, gst, total = calculate_charges(seats)
    booking = Booking.objects.create(
        booking_id=_unique_booking_id(),
        user=user,
        schedule=schedule,
        journey_date=schedule.travel_date,
        journey_source=schedule.route.source,
        journey_destination=schedule.route.destination,
        status=Booking.Status.PENDING,
        contact_name=user.get_full_name() or user.username,
        contact_email=user.email,
        contact_phone=getattr(getattr(user, "profile", None), "phone", "") or "",
        seat_subtotal=subtotal,
        convenience_fee=fee,
        gst_amount=gst,
        total_amount=total,
        expires_at=now + timedelta(minutes=settings.SEAT_RESERVATION_MINUTES),
    )
    BookingSeat.objects.bulk_create(
        [BookingSeat(booking=booking, seat=seat, fare=seat.price) for seat in seats]
    )
    return booking


@transaction.atomic
def confirm_booking_payment(booking_id, payment):
    """Revalidate seats under row locks and confirm a booking after verified payment."""
    from payments.models import Payment

    try:
        booking = (
            Booking.objects.select_for_update()
            .select_related("schedule__bus__operator", "schedule__route", "user")
            .get(booking_id=booking_id)
        )
    except Booking.DoesNotExist:
        raise BookingError("Booking not found.")

    if booking.status == Booking.Status.CONFIRMED:
        return booking

    if booking.status != Booking.Status.PENDING:
        raise BookingExpiredError("This booking is no longer awaiting payment.")

    now = timezone.now()
    if booking.expires_at and booking.expires_at < now:
        booking.status = Booking.Status.EXPIRED
        booking.save(update_fields=["status", "updated_at"])
        payment.mark_failed("Reservation expired before payment confirmation.")
        raise BookingExpiredError("Your seat hold expired. Please search again and rebook.")

    seat_ids = list(booking.booking_seats.values_list("seat_id", flat=True))
    locked_seats = list(
        Seat.objects.select_for_update()
        .filter(id__in=seat_ids, schedule=booking.schedule, is_active=True)
        .select_related("schedule")
    )
    if len(locked_seats) != len(seat_ids):
        payment.mark_failed("One or more seats became unavailable.")
        raise SeatUnavailableError("One or more seats are no longer available. Please contact support.")

    conflicting = (
        BookingSeat.objects.filter(
            seat_id__in=seat_ids,
            booking__status__in=[Booking.Status.PENDING, Booking.Status.CONFIRMED],
        )
        .exclude(booking=booking)
        .exists()
    )
    if conflicting:
        payment.mark_failed("Seat conflict detected during confirmation.")
        raise SeatUnavailableError("Another traveller booked one of these seats. No payment was captured.")

    booking.status = Booking.Status.CONFIRMED
    booking.confirmed_at = now
    booking.ticket_number = booking.ticket_number or _unique_ticket_number()
    booking.expires_at = None
    booking.save(update_fields=["status", "confirmed_at", "ticket_number", "expires_at", "updated_at"])

    payment.status = Payment.Status.SUCCESS
    payment.paid_at = now
    payment.failure_reason = ""
    payment.save(update_fields=["status", "paid_at", "failure_reason", "updated_at"])
    return booking


@transaction.atomic
def release_booking_hold(booking_id, user, reason="Seat hold released by traveller."):
    """Release a pending seat hold so the traveller can change their selection.

    The booking is kept (as EXPIRED) for audit purposes but its seats immediately
    become available again. Any unfinished payment attempts are marked failed.
    Returns ``(booking, seat_ids)`` so the caller can pre-select the same seats
    on the seat map.
    """
    from payments.models import Payment

    try:
        booking = Booking.objects.select_for_update().get(booking_id=booking_id, user=user)
    except Booking.DoesNotExist:
        raise BookingError("Booking not found.")

    if booking.status != Booking.Status.PENDING:
        return booking, []

    seat_ids = list(booking.booking_seats.values_list("seat_id", flat=True))
    now = timezone.now()
    booking.status = Booking.Status.EXPIRED
    booking.expires_at = now
    booking.save(update_fields=["status", "expires_at", "updated_at"])

    Payment.objects.filter(
        booking=booking,
        status__in=[Payment.Status.INITIATED, Payment.Status.PENDING],
    ).update(status=Payment.Status.FAILED, failure_reason=reason[:255])
    return booking, seat_ids


@transaction.atomic
def cancel_booking(booking_id, user, reason):
    """Cancel a confirmed booking, apply the refund policy and release its seats."""
    from payments.models import Payment

    try:
        booking = Booking.objects.select_for_update().select_related("schedule__route").get(booking_id=booking_id)
    except Booking.DoesNotExist:
        raise BookingError("Booking not found.")

    if booking.user_id != user.id:
        raise BookingError("You can only cancel your own bookings.")
    if booking.status == Booking.Status.CANCELLED:
        raise CancellationError("This booking is already cancelled.")
    if booking.status != Booking.Status.CONFIRMED:
        raise CancellationError("Only confirmed bookings can be cancelled.")
    if booking.hours_to_departure < 6:
        raise CancellationError(
            "Cancellations are not permitted within 6 hours of departure. Please contact customer care."
        )

    percent = booking.refund_percent
    refund = (booking.total_amount * Decimal(percent) / Decimal("100")).quantize(Decimal("0.01"))
    fee = (booking.total_amount - refund).quantize(Decimal("0.01"))
    now = timezone.now()

    booking.status = Booking.Status.CANCELLED
    booking.cancelled_at = now
    booking.save(update_fields=["status", "cancelled_at", "updated_at"])

    cancellation, _ = Cancellation.objects.update_or_create(
        booking=booking,
        defaults={
            "reason": reason.strip() or "Traveller requested cancellation.",
            "refund_amount": refund,
            "cancellation_fee": fee,
            "refund_percent": percent,
            "status": Cancellation.Status.APPROVED,
            "processed_at": now,
            "admin_note": "Auto-approved as per BUSGO refund policy.",
        },
    )

    payment = booking.payments.filter(status=Payment.Status.SUCCESS).order_by("-created_at").first()
    if payment:
        payment.status = Payment.Status.REFUNDED
        payment.refund_amount = refund
        payment.refunded_at = now
        payment.save(update_fields=["status", "refund_amount", "refunded_at", "updated_at"])

    return cancellation
