import secrets

from django.db import models
from django.utils import timezone

from bookings.models import Booking


def generate_payment_id():
    return "PAY" + timezone.localtime().strftime("%y%m%d") + secrets.token_hex(4).upper()


class Payment(models.Model):
    class Method(models.TextChoices):
        UPI = "UPI", "UPI"
        GOOGLEPAY = "GOOGLEPAY", "Google Pay"
        PHONEPE = "PHONEPE", "PhonePe"
        PAYTM = "PAYTM", "Paytm"
        QR = "QR", "QR Code"
        DEBIT_CARD = "DEBIT_CARD", "Debit Card"
        CREDIT_CARD = "CREDIT_CARD", "Credit Card"
        NETBANKING = "NETBANKING", "Net Banking"

    class Status(models.TextChoices):
        INITIATED = "INITIATED", "Initiated"
        PENDING = "PENDING", "Pending"
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"
        REFUNDED = "REFUNDED", "Refunded"

    class Gateway(models.TextChoices):
        SIMULATED = "SIMULATED", "Simulated gateway (demo)"
        RAZORPAY = "RAZORPAY", "Razorpay"

    payment_id = models.CharField(max_length=30, unique=True, default=generate_payment_id, editable=False)
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="payments")
    method = models.CharField(max_length=20, choices=Method.choices, default=Method.UPI)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.INITIATED, db_index=True)
    gateway = models.CharField(max_length=12, choices=Gateway.choices, default=Gateway.SIMULATED)

    gateway_order_id = models.CharField(max_length=120, blank=True)
    gateway_payment_id = models.CharField(max_length=120, blank=True)
    gateway_signature = models.CharField(max_length=255, blank=True)

    failure_reason = models.CharField(max_length=255, blank=True)
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    refunded_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["booking", "status"])]

    def __str__(self):
        return f"{self.payment_id} · {self.booking.booking_id} · {self.status}"

    @property
    def is_successful(self):
        return self.status == self.Status.SUCCESS

    @property
    def status_badge(self):
        return {
            self.Status.INITIATED: "secondary",
            self.Status.PENDING: "warning",
            self.Status.SUCCESS: "success",
            self.Status.FAILED: "danger",
            self.Status.REFUNDED: "info",
        }.get(self.status, "secondary")

    def mark_failed(self, reason=""):
        self.status = self.Status.FAILED
        self.failure_reason = (reason or "Payment could not be completed.")[:255]
        self.save(update_fields=["status", "failure_reason", "updated_at"])
