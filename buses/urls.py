from django.urls import path

from . import views

app_name = "buses"

urlpatterns = [
    path("", views.home, name="home"),
    path("search/", views.search, name="search"),
    path("buses/<int:schedule_id>/", views.bus_details, name="bus_details"),
    path("newsletter/subscribe/", views.newsletter_subscribe, name="newsletter_subscribe"),
]
