"""
Django admin configuration for the accounts app.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Team, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = [
        "email",
        "first_name",
        "last_name",
        "role",
        "team",
        "is_active",
        "created_at",
    ]
    list_filter = ["role", "team", "is_active", "is_staff"]
    search_fields = ["email", "first_name", "last_name"]
    ordering = ["email"]
    readonly_fields = ["created_at", "updated_at", "last_activity"]

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Personal Info",
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "phone",
                    "avatar",
                    "job_title",
                    "bio",
                    "timezone",
                )
            },
        ),
        (
            "Organization",
            {"fields": ("role", "team")},
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (
            "Preferences",
            {"fields": ("email_notifications",)},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at", "last_activity", "last_login")},
        ),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "first_name",
                    "last_name",
                    "password1",
                    "password2",
                    "role",
                    "team",
                ),
            },
        ),
    )


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ["name", "is_active", "member_count", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["name"]
    readonly_fields = ["created_at", "updated_at"]
