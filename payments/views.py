import base64
import io
import json
import logging
from urllib.parse import quote

import qrcode
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from bookings.models import Booking
from bookings.services import (
    BookingError,
    BookingExpiredError,
    SeatUnavailableError,
    confirm_booking_payment,
    release_expired_bookings,
)

from . import gateway
from .models import Payment
from .ticket import ensure_ticket_qr

logger = logging.getLogger(__name__)

PAYMENT_SALT = "busgo-payment-token"
METHOD_ICONS = {
    "UPI": "fa-solid fa-at",
    "GOOGLEPAY": "fa-brands fa-google-pay",
    "PHONEPE": "fa-solid fa-mobile-screen-button",
    "PAYTM": "fa-solid fa-wallet",
    "QR": "fa-solid fa-qrcode",
    "DEBIT_CARD": "fa-regular fa-credit-card",
    "CREDIT_CARD": "fa-solid fa-credit-card",
    "NETBANKING": "fa-solid fa-building-columns",
}


def _booking_for(request, booking_id):
    return get_object_or_404(
        Booking.objects.select_related(
            "schedule__bus__operator", "schedule__route", "user", "user__profile"
        ),
        booking_id=booking_id,
        user=request.user,
    )


def _signed_payment_token(payment):
    return signing.dumps(
        {
            "payment_id": payment.payment_id,
            "booking_id": payment.booking.booking_id,
            "amount": str(payment.amount),
        },
        salt=PAYMENT_SALT,
    )


def _upi_qr_data_uri(booking, amount):
    """Return a demo UPI payment QR as a data URI.

    The simulated gateway is explicitly a demo, so this QR uses a placeholder
    VPA. It never asks for or stores a UPI PIN.
    """
    upi_uri = (
        "upi://pay?pa=busgo.demo@upi"
        "&pn=BUSGO"
        f"&am={amount:.2f}"
        "&cu=INR"
        f"&tn={quote('BUSGO booking ' + booking.booking_id)}"
    )
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=7,
        border=2,
    )
    qr.add_data(upi_uri)
    qr.make(fit=True)
    image = qr.make_image(fill_color="#0B1F3A", back_color="white").convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def _passengers_ready(booking):
    return booking.passengers.count() >= booking.booking_seats.count()


@login_required
def checkout(request, booking_id):
    release_expired_bookings()
    booking = _booking_for(request, booking_id)

    if booking.status == Booking.Status.CONFIRMED:
        return redirect("payments:success", booking_id=booking.booking_id)
    if booking.status != Booking.Status.PENDING or booking.is_expired:
        messages.error(request, "This booking is no longer awaiting payment. Please start a new search.")
        return redirect("bookings:my_bookings")

    # Never let a booking reach payment without a passenger for every seat.
    if not _passengers_ready(booking):
        messages.warning(request, "Please complete the passenger details for every seat before payment.")
        return redirect("bookings:passenger_details", booking_id=booking.booking_id)

    payment = (
        booking.payments.filter(status__in=[Payment.Status.INITIATED, Payment.Status.PENDING])
        .order_by("-created_at")
        .first()
    )
    if payment is None:
        payment = Payment.objects.create(
            booking=booking,
            amount=booking.total_amount,
            method=Payment.Method.UPI,
            status=Payment.Status.INITIATED,
            gateway=Payment.Gateway.RAZORPAY
            if settings.PAYMENT_MODE == "razorpay" and gateway.razorpay_configured()
            else Payment.Gateway.SIMULATED,
        )

    razorpay_ready = settings.PAYMENT_MODE == "razorpay" and gateway.razorpay_configured()
    if razorpay_ready and not payment.gateway_order_id:
        try:
            order = gateway.create_order(payment)
            payment.gateway_order_id = order.get("id", "")
            payment.save(update_fields=["gateway_order_id", "updated_at"])
        except RuntimeError as exc:
            messages.warning(request, f"{exc} The demo gateway is available below.")
            razorpay_ready = False
            payment.gateway = Payment.Gateway.SIMULATED
            payment.save(update_fields=["gateway", "updated_at"])

    methods = [
        {
            "code": code,
            "label": label,
            "icon": METHOD_ICONS.get(code, "fa-solid fa-wallet"),
            "slug": code.lower(),
        }
        for code, label in Payment.Method.choices
    ]

    return render(
        request,
        "payments/payment.html",
        {
            "booking": booking,
            "payment": payment,
            "methods": methods,
            "passengers": booking.passengers.select_related("booking_seat__seat"),
            "signed_token": _signed_payment_token(payment),
            "razorpay_ready": razorpay_ready,
            "razorpay_key": settings.RAZORPAY_KEY_ID if razorpay_ready else "",
            "razorpay_order_id": payment.gateway_order_id if razorpay_ready else "",
            "payment_mode": "razorpay" if razorpay_ready else "simulated",
            "upi_qr": "" if razorpay_ready else _upi_qr_data_uri(booking, booking.total_amount),
            "minutes_left": max(int((booking.expires_at - timezone.now()).total_seconds() // 60), 0),
        },
    )


@login_required
@require_POST
def process_payment(request, booking_id):
    """Handle the clearly-labelled simulated gateway callback."""
    release_expired_bookings()
    booking = _booking_for(request, booking_id)

    if booking.status != Booking.Status.PENDING or booking.is_expired:
        messages.error(request, "Your reservation expired. Please search again and rebook.")
        return redirect("bookings:my_bookings")

    if not _passengers_ready(booking):
        messages.warning(request, "Please complete the passenger details for every seat before payment.")
        return redirect("bookings:passenger_details", booking_id=booking.booking_id)

    token = request.POST.get("token", "")
    try:
        payload = signing.loads(token, salt=PAYMENT_SALT, max_age=60 * 60 * 2)
    except signing.BadSignature:
        messages.error(request, "Invalid payment session. Please reopen the payment page.")
        return redirect("payments:checkout", booking_id=booking.booking_id)

    payment = booking.payments.filter(payment_id=payload.get("payment_id")).first()
    if not payment or payload.get("booking_id") != booking.booking_id or payload.get("amount") != str(payment.amount):
        messages.error(request, "Payment verification failed. No amount was captured.")
        return redirect("payments:checkout", booking_id=booking.booking_id)

    method = request.POST.get("method", Payment.Method.UPI)
    valid_methods = {code for code, _ in Payment.Method.choices}
    if method not in valid_methods:
        method = Payment.Method.UPI
    payment.method = method
    payment.gateway = Payment.Gateway.SIMULATED
    payment.save(update_fields=["method", "gateway", "updated_at"])

    action = request.POST.get("action", "failure")

    if action == "failure":
        payment.mark_failed("Simulated payment failure requested by traveller.")
        messages.error(request, "The simulated payment failed. No money was charged. You can retry.")
        return redirect("payments:failed", booking_id=booking.booking_id)

    if action == "pending":
        payment.status = Payment.Status.PENDING
        payment.failure_reason = "Awaiting confirmation from the simulated gateway."
        payment.save(update_fields=["status", "failure_reason", "updated_at"])
        messages.warning(request, "Payment is pending. Your seats are held until the reservation timer expires.")
        return redirect("payments:pending", booking_id=booking.booking_id)

    try:
        confirm_booking_payment(booking.booking_id, payment)
    except (SeatUnavailableError, BookingExpiredError, BookingError) as exc:
        messages.error(request, str(exc))
        return redirect("payments:failed", booking_id=booking.booking_id)

    booking.refresh_from_db()
    try:
        ensure_ticket_qr(booking, request)
    except Exception as exc:  # pragma: no cover - QR failure should not void a paid booking
        logger.exception("QR generation failed for %s: %s", booking.booking_id, exc)

    messages.success(
        request,
        f"Payment successful (simulated demo gateway). Booking {booking.booking_id} is confirmed. Your e-ticket is ready!",
    )
    return redirect("payments:success", booking_id=booking.booking_id)


@login_required
def success(request, booking_id):
    booking = _booking_for(request, booking_id)
    if booking.status != Booking.Status.CONFIRMED:
        messages.info(request, "This booking is not confirmed yet.")
        return redirect("bookings:my_bookings")
    ensure_ticket_qr(booking, request)
    payment = booking.payments.filter(status=Payment.Status.SUCCESS).order_by("-created_at").first()
    return render(
        request,
        "payments/payment_success.html",
        {"booking": booking, "payment": payment},
    )


@login_required
def failed(request, booking_id):
    booking = _booking_for(request, booking_id)
    payment = booking.payments.order_by("-created_at").first()
    return render(
        request,
        "payments/payment_failed.html",
        {"booking": booking, "payment": payment},
    )


@login_required
def pending(request, booking_id):
    booking = _booking_for(request, booking_id)
    payment = booking.payments.order_by("-created_at").first()
    return render(
        request,
        "payments/payment_pending.html",
        {"booking": booking, "payment": payment},
    )


@login_required
@require_POST
def razorpay_order(request, booking_id):
    """Create (or return) a Razorpay order for the checkout popup."""
    if not (settings.PAYMENT_MODE == "razorpay" and gateway.razorpay_configured()):
        return JsonResponse({"error": "Razorpay is not configured."}, status=400)
    booking = _booking_for(request, booking_id)
    if booking.status != Booking.Status.PENDING or booking.is_expired:
        return JsonResponse({"error": "Reservation expired."}, status=400)
    if not _passengers_ready(booking):
        return JsonResponse({"error": "Passenger details are incomplete."}, status=400)
    payment = booking.payments.filter(status__in=[Payment.Status.INITIATED, Payment.Status.PENDING]).order_by("-created_at").first()
    if not payment:
        return JsonResponse({"error": "Payment session not found."}, status=400)
    try:
        if not payment.gateway_order_id:
            order = gateway.create_order(payment)
            payment.gateway = Payment.Gateway.RAZORPAY
            payment.gateway_order_id = order.get("id", "")
            payment.save(update_fields=["gateway", "gateway_order_id", "updated_at"])
        return JsonResponse(
            {
                "order_id": payment.gateway_order_id,
                "key_id": settings.RAZORPAY_KEY_ID,
                "amount": int(payment.amount * 100),
                "currency": settings.RAZORPAY_CURRENCY,
                "name": settings.RAZORPAY_COMPANY_NAME,
                "description": f"BUSGO booking {booking.booking_id}",
                "prefill": {"name": booking.contact_name, "email": booking.contact_email, "contact": booking.contact_phone},
            }
        )
    except RuntimeError as exc:
        return JsonResponse({"error": str(exc)}, status=502)


@login_required
@require_POST
def razorpay_verify(request, booking_id):
    """Verify Razorpay signature + amount server-side before confirming the booking."""
    if not (settings.PAYMENT_MODE == "razorpay" and gateway.razorpay_configured()):
        return JsonResponse({"error": "Razorpay is not configured."}, status=400)
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid payload."}, status=400)

    booking = _booking_for(request, booking_id)
    order_id = data.get("razorpay_order_id", "")
    gateway_payment_id = data.get("razorpay_payment_id", "")
    signature = data.get("razorpay_signature", "")

    payment = booking.payments.filter(gateway_order_id=order_id).order_by("-created_at").first()
    if not payment:
        return JsonResponse({"error": "Payment order not found."}, status=400)
    if not gateway.verify_signature(order_id, gateway_payment_id, signature):
        payment.mark_failed("Razorpay signature verification failed.")
        return JsonResponse({"error": "Signature verification failed."}, status=400)

    try:
        remote = gateway.fetch_payment(gateway_payment_id)
    except RuntimeError as exc:
        return JsonResponse({"error": str(exc)}, status=502)

    if remote.get("order_id") != order_id or int(remote.get("amount", 0)) != int(payment.amount * 100):
        payment.mark_failed("Razorpay amount/order mismatch.")
        return JsonResponse({"error": "Payment amount verification failed."}, status=400)
    if remote.get("status") not in ("captured", "authorized"):
        payment.mark_failed(f"Razorpay payment status: {remote.get('status')}")
        return JsonResponse({"error": "Payment was not captured."}, status=400)

    payment.gateway = Payment.Gateway.RAZORPAY
    payment.gateway_payment_id = gateway_payment_id
    payment.gateway_signature = signature
    payment.save(update_fields=["gateway", "gateway_payment_id", "gateway_signature", "updated_at"])

    try:
        confirm_booking_payment(booking.booking_id, payment)
    except BookingError as exc:
        return JsonResponse({"error": str(exc)}, status=409)

    booking.refresh_from_db()
    ensure_ticket_qr(booking, request)
    return JsonResponse(
        {
            "ok": True,
            "redirect_url": reverse("payments:success", args=[booking.booking_id]),
        }
    )
