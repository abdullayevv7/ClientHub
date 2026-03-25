"""
Django admin configuration for the deals app.
"""

from django.contrib import admin

from .models import Deal, DealActivity, DealStage, Pipeline


class DealStageInline(admin.TabularInline):
    model = DealStage
    extra = 0
    ordering = ["order"]


class DealActivityInline(admin.TabularInline):
    model = DealActivity
    extra = 0
    readonly_fields = ["activity_type", "description", "old_value", "new_value", "user", "created_at"]


@admin.register(Pipeline)
class PipelineAdmin(admin.ModelAdmin):
    list_display = ["name", "is_active", "is_default", "deal_count", "total_value", "created_at"]
    list_filter = ["is_active", "is_default"]
    search_fields = ["name"]
    inlines = [DealStageInline]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(DealStage)
class DealStageAdmin(admin.ModelAdmin):
    list_display = ["name", "pipeline", "order", "probability", "is_won", "is_lost", "deal_count"]
    list_filter = ["pipeline", "is_won", "is_lost"]
    ordering = ["pipeline", "order"]


@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "value",
        "currency",
        "stage",
        "owner",
        "priority",
        "expected_close_date",
        "created_at",
    ]
    list_filter = ["stage__pipeline", "stage", "priority", "owner"]
    search_fields = ["title", "description", "contact__first_name", "company__name"]
    readonly_fields = ["created_at", "updated_at", "created_by"]
    inlines = [DealActivityInline]
    list_per_page = 50

    fieldsets = (
        (
            "Deal Info",
            {"fields": ("title", "description", "value", "currency", "priority")},
        ),
        (
            "Pipeline",
            {"fields": ("stage", "probability")},
        ),
        (
            "Relationships",
            {"fields": ("contact", "company", "owner", "created_by")},
        ),
        (
            "Dates",
            {
                "fields": (
                    "expected_close_date",
                    "actual_close_date",
                    "created_at",
                    "updated_at",
                )
            },
        ),
        (
            "Outcome",
            {"fields": ("lost_reason",), "classes": ("collapse",)},
        ),
    )


@admin.register(DealActivity)
class DealActivityAdmin(admin.ModelAdmin):
    list_display = ["deal", "activity_type", "user", "created_at"]
    list_filter = ["activity_type"]
    search_fields = ["deal__title", "description"]
    readonly_fields = ["created_at"]
