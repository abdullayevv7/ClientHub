"""
Django admin configuration for the contacts app.
"""

from django.contrib import admin

from .models import Company, Contact, ContactNote, ContactTag


class ContactNoteInline(admin.TabularInline):
    model = ContactNote
    extra = 0
    readonly_fields = ["author", "created_at"]


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = [
        "first_name",
        "last_name",
        "email",
        "company",
        "status",
        "lead_score",
        "owner",
        "created_at",
    ]
    list_filter = ["status", "source", "company", "owner"]
    search_fields = ["first_name", "last_name", "email", "company__name"]
    readonly_fields = ["created_at", "updated_at", "created_by"]
    inlines = [ContactNoteInline]
    list_per_page = 50

    fieldsets = (
        (
            "Basic Info",
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "email",
                    "phone",
                    "mobile",
                    "avatar",
                )
            },
        ),
        (
            "Professional",
            {"fields": ("job_title", "department", "company")},
        ),
        (
            "Status",
            {"fields": ("status", "source", "lead_score")},
        ),
        (
            "Address",
            {
                "fields": (
                    "address_line1",
                    "address_line2",
                    "city",
                    "state",
                    "postal_code",
                    "country",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Social",
            {
                "fields": ("linkedin_url", "twitter_handle"),
                "classes": ("collapse",),
            },
        ),
        (
            "Assignment",
            {"fields": ("owner", "created_by", "tags")},
        ),
        (
            "Other",
            {"fields": ("description", "last_contacted", "created_at", "updated_at")},
        ),
    )


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "industry",
        "size",
        "city",
        "country",
        "owner",
        "contact_count",
        "created_at",
    ]
    list_filter = ["industry", "size"]
    search_fields = ["name", "email"]
    readonly_fields = ["created_at", "updated_at", "created_by"]
    list_per_page = 50


@admin.register(ContactTag)
class ContactTagAdmin(admin.ModelAdmin):
    list_display = ["name", "color", "created_at"]
    search_fields = ["name"]


@admin.register(ContactNote)
class ContactNoteAdmin(admin.ModelAdmin):
    list_display = ["contact", "author", "is_pinned", "created_at"]
    list_filter = ["is_pinned"]
    search_fields = ["content", "contact__first_name", "contact__last_name"]
    readonly_fields = ["created_at", "updated_at"]
