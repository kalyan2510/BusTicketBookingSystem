from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import (
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.db.models import Count, Q, Sum
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme

from bookings.models import Booking

from .forms import BusgoPasswordResetForm, BusgoSetPasswordForm, LoginForm, ProfileForm, RegisterForm


def _safe_next(request, fallback):
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt and url_has_allowed_host_and_scheme(
        nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return nxt
    return fallback


def register(request):
    if request.user.is_authenticated:
        messages.info(request, "You are already signed in.")
        return redirect("buses:home")

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user, backend="accounts.backends.EmailOrUsernameBackend")
            messages.success(
                request,
                f"Welcome aboard, {user.first_name}! Your BUSGO account is ready. Start by searching for a bus.",
            )
            return redirect(_safe_next(request, "buses:home"))
        messages.error(request, "Please correct the highlighted fields and try again.")
    else:
        form = RegisterForm()

    return render(request, "accounts/register.html", {"form": form, "next": request.GET.get("next", "")})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("buses:home")

    if request.method == "POST":
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)
            if not form.cleaned_data.get("remember_me"):
                request.session.set_expiry(0)
            messages.success(request, f"Welcome back, {user.first_name or user.username.split('@')[0].title()}!")
            return redirect(_safe_next(request, "buses:home"))
        messages.error(request, "Sign in failed. Please check your credentials.")
    else:
        form = LoginForm(request)

    return render(
        request,
        "accounts/login.html",
        {"form": form, "next": request.GET.get("next", "")},
    )


def logout_view(request):
    if request.method != "POST":
        return redirect("buses:home")
    if request.user.is_authenticated:
        name = request.user.first_name or "traveller"
        auth_logout(request)
        messages.success(request, f"You have been signed out safely. See you soon, {name}!")
    return redirect("buses:home")


@login_required
def profile(request):
    profile_obj = request.user.profile
    form = ProfileForm(request.POST or None, request.FILES or None, instance=profile_obj)

    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect("accounts:profile")
        messages.error(request, "Could not update your profile. Please check the form.")

    bookings = (
        Booking.objects.filter(user=request.user)
        .select_related("schedule__bus__operator", "schedule__route")
        .order_by("-created_at")
    )
    stats = bookings.aggregate(
        total=Count("id"),
        confirmed=Count("id", filter=Q(status=Booking.Status.CONFIRMED)),
        cancelled=Count("id", filter=Q(status=Booking.Status.CANCELLED)),
        spent=Sum("total_amount", filter=Q(status=Booking.Status.CONFIRMED)),
    )
    recent = bookings[:5]

    return render(
        request,
        "accounts/profile.html",
        {
            "form": form,
            "profile": profile_obj,
            "stats": stats,
            "recent_bookings": recent,
            "site": settings,
        },
    )


class BusgoPasswordResetView(PasswordResetView):
    template_name = "accounts/password_reset.html"
    form_class = BusgoPasswordResetForm
    email_template_name = "accounts/password_reset_email.html"
    subject_template_name = "accounts/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password_reset_done")


class BusgoPasswordResetDoneView(PasswordResetDoneView):
    template_name = "accounts/password_reset_done.html"


class BusgoPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = "accounts/password_reset_confirm.html"
    form_class = BusgoSetPasswordForm
    success_url = reverse_lazy("accounts:password_reset_complete")


class BusgoPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = "accounts/password_reset_complete.html"
