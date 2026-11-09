"""End-to-end integration tests for the BUSGO booking platform."""
from datetime import time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.models import Booking, Cancellation
from buses.models import Bus, BusOperator, BusSchedule, Route
from payments.models import Payment


class BusgoFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.operator = BusOperator.objects.create(
            name="Test Coach Lines",
            description="Integration-test operator",
            logo_static="images/bus-1.jpg",
            rating="4.5",
            contact_email="ops@testcoach.example",
            contact_phone="9876543210",
        )
        cls.bus = Bus.objects.create(
            operator=cls.operator,
            name="Test Cruiser",
            registration_number="KA01TEST01",
            bus_type=Bus.BusType.AC_SEATER,
            layout=Bus.Layout.SEATER_2X2,
            total_seats=40,
            amenities="WiFi,Charging Point,Water Bottle",
            image_static="images/bus-1.jpg",
            rating="4.5",
        )
        cls.route = Route.objects.create(
            source="Bengaluru",
            destination="Mysuru",
            distance_km=145,
            duration_minutes=210,
            base_fare=Decimal("499.00"),
            image="images/route-mountain.jpg",
            is_popular=True,
        )
        cls.schedule = BusSchedule.objects.create(
            bus=cls.bus,
            route=cls.route,
            travel_date=timezone.localdate() + timedelta(days=5),
            departure_time=time(9, 0),
            arrival_time=time(13, 0),
            fare=Decimal("599.00"),
        )
        cls.schedule.ensure_seats()
        cls.user = User.objects.create_user(
            username="traveller@example.com",
            email="traveller@example.com",
            password="Traveller@123",
            first_name="Test",
            last_name="Traveller",
        )
        cls.other_user = User.objects.create_user(
            username="other@example.com",
            email="other@example.com",
            password="Other@1234",
        )
        cls.staff = User.objects.create_user(
            username="staff@example.com",
            email="staff@example.com",
            password="Staff@1234",
            is_staff=True,
        )

    # -- helpers ---------------------------------------------------------
    def _free_seat_ids(self, count=2):
        booked = self.schedule.booked_seat_ids
        return [
            str(seat.pk)
            for seat in self.schedule.seats.filter(is_active=True)
            if seat.pk not in booked
        ][:count]

    def _hold(self, seats=None, user=None):
        self.client.force_login(user or self.user)
        seats = seats or self._free_seat_ids(2)
        response = self.client.post(
            reverse("bookings:create_booking", args=[self.schedule.pk]),
            {"seat_ids": seats},
        )
        self.assertRedirects(
            response, reverse("bookings:passenger_details", args=[Booking.objects.latest("id").booking_id])
        )
        return Booking.objects.latest("id")

    def _fill_passengers(self, booking):
        data = {
            "contact_name": "Test Traveller",
            "contact_email": "traveller@example.com",
            "contact_phone": "9876543210",
        }
        for booking_seat in booking.booking_seats.select_related("seat"):
            prefix = f"seat{booking_seat.pk}"
            data[f"{prefix}-name"] = f"Passenger {booking_seat.seat.seat_number}"
            data[f"{prefix}-age"] = "28"
            data[f"{prefix}-gender"] = "Male"
            data[f"{prefix}-phone"] = "9876543210"
            data[f"{prefix}-email"] = "traveller@example.com"
        response = self.client.post(
            reverse("bookings:passenger_details", args=[booking.booking_id]), data
        )
        self.assertRedirects(response, reverse("payments:checkout", args=[booking.booking_id]))

    def _pay(self, booking, action="success"):
        response = self.client.get(reverse("payments:checkout", args=[booking.booking_id]))
        self.assertEqual(response.status_code, 200)
        token = response.context["signed_token"]
        return self.client.post(
            reverse("payments:process", args=[booking.booking_id]),
            {"token": token, "method": "UPI", "action": action},
        )

    def _confirm_booking(self):
        booking = self._hold()
        self._fill_passengers(booking)
        self._pay(booking)
        booking.refresh_from_db()
        return booking

    # -- public pages ----------------------------------------------------
    def test_public_pages_render(self):
        pages = [
            reverse("buses:home"),
            reverse("buses:search"),
            reverse("buses:search") + "?from=Bengaluru&to=Mysuru",
            reverse("buses:bus_details", args=[self.schedule.pk]),
            reverse("about"),
            reverse("contact"),
            reverse("policies"),
            reverse("accounts:login"),
            reverse("accounts:register"),
            reverse("accounts:password_reset"),
        ]
        for url in pages:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_search_finds_schedule(self):
        response = self.client.get(
            reverse("buses:search"),
            {"from": "Bengaluru", "to": "Mysuru", "date": self.schedule.travel_date.isoformat()},
        )
        self.assertContains(response, "Test Cruiser")
        self.assertEqual(response.context["result_count"], 1)

    # -- accounts --------------------------------------------------------
    def test_register_login_logout(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "full_name": "New Traveller",
                "email": "new@example.com",
                "phone": "9876543210",
                "password1": "NewTraveller@123",
                "password2": "NewTraveller@123",
                "terms": "on",
            },
        )
        self.assertRedirects(response, reverse("buses:home"))
        self.assertTrue(User.objects.filter(email="new@example.com").exists())

        self.client.post(reverse("accounts:logout"))
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "new@example.com", "password": "NewTraveller@123", "remember_me": "on"},
        )
        self.assertRedirects(response, reverse("buses:home"))
        self.assertEqual(self.client.get(reverse("accounts:profile")).status_code, 200)

    def test_protected_pages_require_login(self):
        self.assertRedirects(
            self.client.get(reverse("bookings:my_bookings")),
            f"{reverse('accounts:login')}?next={reverse('bookings:my_bookings')}",
        )

    # -- booking flow ----------------------------------------------------
    def test_full_booking_payment_ticket_flow(self):
        booking = self._hold()
        self.assertEqual(booking.status, Booking.Status.PENDING)
        self.assertEqual(booking.booking_seats.count(), 2)
        self.assertIsNotNone(booking.expires_at)

        self._fill_passengers(booking)
        booking.refresh_from_db()
        self.assertEqual(booking.passengers.count(), 2)

        self._pay(booking)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.CONFIRMED)
        self.assertTrue(booking.ticket_number)
        self.assertEqual(booking.payments.filter(status=Payment.Status.SUCCESS).count(), 1)

        self.assertEqual(self.client.get(reverse("bookings:ticket", args=[booking.booking_id])).status_code, 200)
        pdf = self.client.get(reverse("bookings:ticket_pdf", args=[booking.booking_id]))
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf["Content-Type"], "application/pdf")
        self.assertGreater(len(b"".join(pdf.streaming_content)), 1000)
        verify = self.client.get(reverse("bookings:verify_ticket", args=[booking.ticket_number]))
        self.assertContains(verify, booking.ticket_number)

    def test_double_booking_is_prevented(self):
        seats = self._free_seat_ids(1)
        self._hold(seats=seats)
        before = Booking.objects.count()

        other = self.client_class()
        other.force_login(self.other_user)
        other.post(reverse("bookings:create_booking", args=[self.schedule.pk]), {"seat_ids": seats})
        self.assertEqual(Booking.objects.count(), before)

    def test_ticket_is_private(self):
        booking = self._confirm_booking()
        other = self.client_class()
        other.force_login(self.other_user)
        self.assertEqual(other.get(reverse("bookings:ticket", args=[booking.booking_id])).status_code, 404)
        self.assertEqual(other.get(reverse("bookings:ticket_pdf", args=[booking.booking_id])).status_code, 404)

    def test_seat_map_renders_every_seat(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("bookings:seat_selection", args=[self.schedule.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode().count("data-seat-id"), 40)
        self.assertContains(response, "Choose your seats")
        self.assertContains(response, "Continue to passengers")

    def test_back_to_seats_releases_hold_and_preselects(self):
        booking = self._hold()
        held_seat_ids = [str(bs.seat_id) for bs in booking.booking_seats.all()]
        response = self.client.post(reverse("bookings:release_hold", args=[booking.booking_id]))
        self.assertEqual(response.status_code, 302)
        self.assertIn("preselect=", response["Location"])
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.EXPIRED)
        self.assertFalse(self.schedule.booked_seat_ids.intersection({int(pk) for pk in held_seat_ids}))

        seat_page = self.client.get(response["Location"])
        self.assertEqual(seat_page.status_code, 200)
        self.assertContains(seat_page, f'data-preselect="{",".join(held_seat_ids)}"')

    def test_payment_is_blocked_until_passengers_are_saved(self):
        booking = self._hold()
        response = self.client.get(reverse("payments:checkout", args=[booking.booking_id]))
        self.assertRedirects(
            response, reverse("bookings:passenger_details", args=[booking.booking_id])
        )

    def test_checkout_displays_upi_qr_and_passenger_review(self):
        booking = self._hold()
        self._fill_passengers(booking)
        response = self.client.get(reverse("payments:checkout", args=[booking.booking_id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data:image/png;base64")
        self.assertContains(response, "pay-passenger-table")
        self.assertContains(response, "DEMO UPI QR")

    def test_payment_failure_and_pending_do_not_confirm(self):
        booking = self._hold()
        self._fill_passengers(booking)
        self._pay(booking, action="failure")
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.PENDING)
        self.assertEqual(booking.payments.filter(status=Payment.Status.FAILED).count(), 1)

        self._pay(booking, action="pending")
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.PENDING)
        self.assertEqual(booking.payments.filter(status=Payment.Status.PENDING).count(), 1)

    def test_cancellation_refund_policy(self):
        booking = self._confirm_booking()
        response = self.client.post(
            reverse("bookings:cancel", args=[booking.booking_id]),
            {"reason": "Change of plans"},
        )
        self.assertRedirects(response, reverse("bookings:my_bookings"))
        booking.refresh_from_db()
        cancellation = Cancellation.objects.get(booking=booking)
        self.assertEqual(booking.status, Booking.Status.CANCELLED)
        self.assertEqual(cancellation.refund_percent, 90)
        self.assertEqual(cancellation.refund_amount, (booking.total_amount * Decimal("0.9")).quantize(Decimal("0.01")))
        self.assertEqual(booking.payments.filter(status=Payment.Status.REFUNDED).count(), 1)

    # -- dashboard -------------------------------------------------------
    def test_dashboard_requires_staff(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("dashboard:home")).status_code, 302)

        self.client.force_login(self.staff)
        for name in [
            "home",
            "operator_list",
            "bus_list",
            "route_list",
            "schedule_list",
            "booking_list",
            "passenger_list",
            "payment_list",
            "cancellation_list",
        ]:
            with self.subTest(view=name):
                self.assertEqual(self.client.get(reverse(f"dashboard:{name}")).status_code, 200)

    def test_dashboard_operator_crud(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("dashboard:operator_add"),
            {
                "name": "Dashboard Test Operator",
                "description": "Created by a test.",
                "rating": "4.0",
                "contact_email": "ops@dashboardtest.example",
                "contact_phone": "9876543210",
                "logo_static": "images/bus-1.jpg",
                "is_active": "on",
            },
        )
        self.assertRedirects(response, reverse("dashboard:operator_list"))
        operator = BusOperator.objects.get(name="Dashboard Test Operator")

        response = self.client.post(reverse("dashboard:operator_delete", args=[operator.pk]))
        self.assertRedirects(response, reverse("dashboard:operator_list"))
        self.assertFalse(BusOperator.objects.filter(pk=operator.pk).exists())
