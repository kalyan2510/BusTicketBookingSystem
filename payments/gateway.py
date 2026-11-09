"""Razorpay test-mode helpers. The simulated gateway is handled in views."""
import base64
import hashlib
import hmac
import json
import logging
import urllib.error
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)

RAZORPAY_API = "https://api.razorpay.com/v1"


def razorpay_configured():
    return bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET)


def _auth_header():
    token = base64.b64encode(
        f"{settings.RAZORPAY_KEY_ID}:{settings.RAZORPAY_KEY_SECRET}".encode()
    ).decode()
    return f"Basic {token}"


def _request(path, method="GET", payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        f"{RAZORPAY_API}{path}",
        data=data,
        method=method,
        headers={
            "Authorization": _auth_header(),
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        logger.error("Razorpay API error %s: %s", exc.code, body)
        raise RuntimeError("Payment gateway rejected the request. Please try again.") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        logger.error("Razorpay network error: %s", exc)
        raise RuntimeError("Could not reach the payment gateway. Please try again.") from exc


def create_order(payment):
    """Create a Razorpay order for a BUSGO payment. Returns the API response."""
    payload = {
        "amount": int(payment.amount * 100),
        "currency": settings.RAZORPAY_CURRENCY,
        "receipt": payment.payment_id,
        "notes": {
            "booking_id": payment.booking.booking_id,
            "payment_id": payment.payment_id,
            "customer_email": payment.booking.contact_email,
        },
    }
    return _request("/orders", method="POST", payload=payload)


def fetch_payment(gateway_payment_id):
    return _request(f"/payments/{gateway_payment_id}")


def verify_signature(order_id, gateway_payment_id, signature):
    expected = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        f"{order_id}|{gateway_payment_id}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature or "")
