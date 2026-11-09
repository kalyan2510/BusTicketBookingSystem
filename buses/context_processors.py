from django.conf import settings
from django.utils import timezone


def site_context(request):
    return {
        "SITE_NAME": settings.SITE_NAME,
        "SITE_TAGLINE": settings.SITE_TAGLINE,
        "SITE_EMAIL": settings.SITE_EMAIL,
        "SITE_PHONE": settings.SITE_PHONE,
        "SITE_ADDRESS": settings.SITE_ADDRESS,
        "CURRENT_YEAR": timezone.localdate().year,
        "MAX_SEATS": settings.MAX_SEATS_PER_BOOKING,
        "RESERVATION_MINUTES": settings.SEAT_RESERVATION_MINUTES,
    }
