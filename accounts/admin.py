from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import Profile


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = "Traveller profile"
    fk_name = "user"
    fields = ("phone", "city", "avatar", "email_verified")


class UserAdmin(BaseUserAdmin):
    inlines = [ProfileInline]
    list_display = ("username", "email", "first_name", "last_name", "is_staff", "is_active", "date_joined")
    list_filter = ("is_staff", "is_superuser", "is_active", "date_joined")
    search_fields = ("username", "email", "first_name", "last_name", "profile__phone")

    def get_inline_instances(self, request, obj=None):
        if not obj:
            return []
        return super().get_inline_instances(request, obj)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("display_name", "user", "phone", "city", "email_verified", "created_at")
    search_fields = ("user__username", "user__email", "user__first_name", "user__last_name", "phone")
    list_filter = ("email_verified", "city")
    list_select_related = ("user",)


admin.site.unregister(User)
admin.site.register(User, UserAdmin)
