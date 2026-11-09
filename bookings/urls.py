from django.urls import path

from . import views

app_name = "bookings"

urlpatterns = [
    path("seats/<int:schedule_id>/", views.seat_selection, name="seat_selection"),
    path("create/<int:schedule_id>/", views.create_booking_view, name="create_booking"),
    path("passengers/<str:booking_id>/", views.passenger_details, name="passenger_details"),
    path("hold/<str:booking_id>/release/", views.release_hold, name="release_hold"),
    path("my/", views.my_bookings, name="my_bookings"),
    path("ticket/<str:booking_id>/", views.ticket, name="ticket"),
    path("ticket/<str:booking_id>/pdf/", views.ticket_pdf, name="ticket_pdf"),
    path("verify/<str:ticket_number>/", views.verify_ticket, name="verify_ticket"),
    path("<str:booking_id>/cancel/", views.cancel_booking_view, name="cancel"),
    path("<str:booking_id>/review/", views.review_create, name="review"),
    path("<str:booking_id>/", views.booking_detail, name="detail"),
]
