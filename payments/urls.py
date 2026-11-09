from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("checkout/<str:booking_id>/", views.checkout, name="checkout"),
    path("process/<str:booking_id>/", views.process_payment, name="process"),
    path("success/<str:booking_id>/", views.success, name="success"),
    path("failed/<str:booking_id>/", views.failed, name="failed"),
    path("pending/<str:booking_id>/", views.pending, name="pending"),
    path("razorpay/order/<str:booking_id>/", views.razorpay_order, name="razorpay_order"),
    path("razorpay/verify/<str:booking_id>/", views.razorpay_verify, name="razorpay_verify"),
]
