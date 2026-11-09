from django.contrib import admin
from django.utils.html import format_html

from .models import Booking, BookingSeat, Cancellation, Passenger


class BookingSeatInline(admin.TabularInline):
    model = BookingSeat
    extra = 0
    readonly_fields = ("seat", "fare")
    can_delete = False


class PassengerInline(admin.StackedInline):
    model = Passenger
    extra = 0
    fields = ("booking_seat", "name", "age", "gender", "phone", "email")
    autocomplete_fields = ()


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "booking_id",
        "user",
        "route",
        "journey_date",
        "status_badge",
        "total_amount",
        "ticket_number",
        "created_at",
    )
    list_filter = ("status", "journey_date", "schedule__bus__operator", "created_at")
    search_fields = (
        "booking_id",
        "ticket_number",
        "contact_name",
        "contact_email",
        "contact_phone",
        "user__email",
        "schedule__route__source",
        "schedule__route__destination",
    )
    readonly_fields = (
        "booking_id",
        "ticket_number",
        "qr_code",
        "seat_subtotal",
        "convenience_fee",
        "gst_amount",
        "total_amount",
        "created_at",
        "updated_at",
        "confirmed_at",
        "cancelled_at",
    )
    inlines = [BookingSeatInline, PassengerInline]
    date_hierarchy = "created_at"
    list_select_related = ("user", "schedule__route", "schedule__bus__operator")

    @admin.display(description="Route")
    def route(self, obj):
        return obj.route_text

    @admin.display(description="Status")
    def status_badge(self, obj):
        colors = {
            "PENDING": "#b7791f",
            "CONFIRMED": "#1f9d6b",
            "CANCELLED": "#e63946",
            "EXPIRED": "#6b7a90",
            "FAILED": "#343a40",
        }
        color = colors.get(obj.status, "#6b7a90")
        return format_html(
            '<span style="background:{};color:#fff;padding:3px 9px;border-radius:20px;font-size:11px;font-weight:700">{}</span>',
            color,
            obj.get_status_display(),
        )


@admin.register(Passenger)
class PassengerAdmin(admin.ModelAdmin):
    list_display = ("name", "age", "gender", "seat_number", "booking", "phone")
    search_fields = ("name", "booking__booking_id", "phone", "email")
    list_filter = ("gender",)
    list_select_related = ("booking", "booking_seat__seat")

    @admin.display(description="Seat")
    def seat_number(self, obj):
        return obj.seat_number


@admin.register(BookingSeat)
class BookingSeatAdmin(admin.ModelAdmin):
    list_display = ("booking", "seat", "fare")
    search_fields = ("booking__booking_id", "seat__seat_number")
    list_select_related = ("booking", "seat__schedule__route")


@admin.register(Cancellation)
class CancellationAdmin(admin.ModelAdmin):
    list_display = (
        "booking",
        "refund_percent",
        "refund_amount",
        "cancellation_fee",
        "status",
        "requested_at",
        "processed_at",
    )
    list_filter = ("status", "requested_at")
    search_fields = ("booking__booking_id", "reason")
    readonly_fields = ("requested_at", "processed_at")
    list_select_related = ("booking",)
