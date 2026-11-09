from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from buses import views as bus_views

admin.site.site_header = "BUSGO Administration"
admin.site.site_title = "BUSGO Admin"
admin.site.index_title = "Operations Control Centre"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("buses.urls")),
    path("accounts/", include("accounts.urls")),
    path("bookings/", include("bookings.urls")),
    path("payments/", include("payments.urls")),
    path("dashboard/", include("dashboard.urls")),
    path("about/", bus_views.about, name="about"),
    path("contact/", bus_views.contact, name="contact"),
    path("policies/", bus_views.policies, name="policies"),
]

handler404 = "buses.views.error_404"
handler500 = "buses.views.error_500"

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / "static")
