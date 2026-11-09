from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.dashboard_home, name="home"),
    path("operators/", views.operator_list, name="operator_list"),
    path("operators/add/", views.operator_form, name="operator_add"),
    path("operators/<int:pk>/edit/", views.operator_form, name="operator_edit"),
    path("operators/<int:pk>/delete/", views.operator_delete, name="operator_delete"),
    path("buses/", views.bus_list, name="bus_list"),
    path("buses/add/", views.bus_form, name="bus_add"),
    path("buses/<int:pk>/edit/", views.bus_form, name="bus_edit"),
    path("buses/<int:pk>/delete/", views.bus_delete, name="bus_delete"),
    path("routes/", views.route_list, name="route_list"),
    path("routes/add/", views.route_form, name="route_add"),
    path("routes/<int:pk>/edit/", views.route_form, name="route_edit"),
    path("routes/<int:pk>/delete/", views.route_delete, name="route_delete"),
    path("schedules/", views.schedule_list, name="schedule_list"),
    path("schedules/add/", views.schedule_form, name="schedule_add"),
    path("schedules/<int:pk>/edit/", views.schedule_form, name="schedule_edit"),
    path("schedules/<int:pk>/delete/", views.schedule_delete, name="schedule_delete"),
    path("schedules/<int:pk>/seats/", views.seat_layout, name="seat_layout"),
    path("schedules/<int:pk>/seats/action/", views.seat_layout_action, name="seat_layout_action"),
    path("bookings/", views.booking_list, name="booking_list"),
    path("bookings/<str:booking_id>/", views.booking_detail, name="booking_detail"),
    path("passengers/", views.passenger_list, name="passenger_list"),
    path("payments/", views.payment_list, name="payment_list"),
    path("cancellations/", views.cancellation_list, name="cancellation_list"),
    path("cancellations/<int:pk>/", views.cancellation_process, name="cancellation_process"),
]
