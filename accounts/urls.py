from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.register, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("profile/", views.profile, name="profile"),
    path("password-reset/", views.BusgoPasswordResetView.as_view(), name="password_reset"),
    path("password-reset/done/", views.BusgoPasswordResetDoneView.as_view(), name="password_reset_done"),
    path(
        "password-reset/<uidb64>/<token>/",
        views.BusgoPasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "password-reset/complete/",
        views.BusgoPasswordResetCompleteView.as_view(),
        name="password_reset_complete",
    ),
]
