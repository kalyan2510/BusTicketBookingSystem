from django.core.management.base import BaseCommand

from bookings.services import release_expired_bookings


class Command(BaseCommand):
    help = "Release seats held by unpaid bookings whose reservation window has expired."

    def handle(self, *args, **options):
        count = release_expired_bookings()
        self.stdout.write(self.style.SUCCESS(f"Released {count} expired reservation(s)."))
