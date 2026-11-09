from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Bus,
    BusOperator,
    BusSchedule,
    ContactMessage,
    NewsletterSubscriber,
    Review,
    Route,
    Seat,
)


@admin.register(BusOperator)
class BusOperatorAdmin(admin.ModelAdmin):
    list_display = ("name", "rating", "contact_phone", "contact_email", "is_active", "bus_count")
    list_filter = ("is_active", "rating")
    search_fields = ("name", "contact_email", "contact_phone")
    prepopulated_fields = {"slug": ("name",)}
    fieldsets = (
        ("Operator", {"fields": ("name", "slug", "description", "rating", "is_active")}),
        ("Branding", {"fields": ("logo", "logo_static")}),
        ("Contact", {"fields": ("contact_email", "contact_phone")}),
    )

    @admin.display(description="Buses")
    def bus_count(self, obj):
        return obj.buses.count()


class SeatInline(admin.TabularInline):
    model = Seat
    extra = 0
    fields = ("seat_number", "deck", "seat_type", "row", "col", "is_window", "is_active", "price_multiplier")
    ordering = ("deck", "row", "col")
    max_num = 0


@admin.register(Bus)
class BusAdmin(admin.ModelAdmin):
    list_display = ("name", "operator", "registration_number", "bus_type", "layout", "total_seats", "rating", "is_active")
    list_filter = ("bus_type", "layout", "is_active", "operator")
    search_fields = ("name", "registration_number", "operator__name")
    list_select_related = ("operator",)
    fieldsets = (
        ("Bus", {"fields": ("operator", "name", "registration_number", "bus_type", "layout", "total_seats")}),
        ("Presentation", {"fields": ("image", "image_static", "amenities", "rating")}),
        ("Availability", {"fields": ("is_active",)}),
    )

    @admin.display(description="Photo")
    def photo(self, obj):
        return format_html('<img src="{}" style="height:38px;border-radius:6px" />', obj.image_url)


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ("source", "destination", "distance_km", "duration_display", "base_fare", "is_popular", "is_active")
    list_filter = ("is_popular", "is_active")
    search_fields = ("source", "destination")
    list_editable = ("is_popular", "is_active")


@admin.register(BusSchedule)
class BusScheduleAdmin(admin.ModelAdmin):
    list_display = (
        "route",
        "bus",
        "travel_date",
        "departure_time",
        "arrival_time",
        "fare",
        "is_active",
        "seat_summary",
    )
    list_filter = ("travel_date", "is_active", "bus__operator", "route")
    search_fields = ("bus__name", "bus__registration_number", "route__source", "route__destination")
    date_hierarchy = "travel_date"
    list_select_related = ("bus__operator", "route")
    autocomplete_fields = ("bus", "route")
    inlines = [SeatInline]

    @admin.display(description="Seats")
    def seat_summary(self, obj):
        total = obj.seats.count()
        booked = obj.seats.filter(booking_seats__booking__status__in=["CONFIRMED", "PENDING"]).distinct().count()
        return f"{booked}/{total} booked"


@admin.register(Seat)
class SeatAdmin(admin.ModelAdmin):
    list_display = ("seat_number", "schedule", "deck", "seat_type", "row", "col", "is_window", "is_active")
    list_filter = ("deck", "seat_type", "is_active", "is_window")
    search_fields = ("seat_number", "schedule__bus__name", "schedule__route__source", "schedule__route__destination")
    list_select_related = ("schedule__bus", "schedule__route")


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("user", "bus", "rating", "title", "is_approved", "created_at")
    list_filter = ("is_approved", "rating", "created_at")
    search_fields = ("user__email", "user__first_name", "comment", "title")
    list_editable = ("is_approved",)
    actions = ("approve_reviews", "unapprove_reviews")
    list_select_related = ("user", "bus")

    @admin.action(description="Approve selected reviews")
    def approve_reviews(self, request, queryset):
        queryset.update(is_approved=True)

    @admin.action(description="Unapprove selected reviews")
    def unapprove_reviews(self, request, queryset):
        queryset.update(is_approved=False)


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ("email", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("email",)


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "subject", "is_resolved", "created_at")
    list_filter = ("is_resolved", "created_at")
    search_fields = ("name", "email", "subject", "message")
    list_editable = ("is_resolved",)
    readonly_fields = ("created_at",)
