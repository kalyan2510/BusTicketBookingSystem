from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "payment_id",
        "booking",
        "method",
        "amount",
        "status",
        "gateway",
        "created_at",
        "paid_at",
    )
    list_filter = ("status", "method", "gateway", "created_at")
    search_fields = ("payment_id", "booking__booking_id", "gateway_payment_id", "booking__contact_email")
    readonly_fields = (
        "payment_id",
        "gateway_order_id",
        "gateway_payment_id",
        "gateway_signature",
        "created_at",
        "updated_at",
        "paid_at",
        "refunded_at",
    )
    list_select_related = ("booking",)
    date_hierarchy = "created_at"
