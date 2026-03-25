"""
Report and Dashboard models for ClientHub CRM.
"""

import uuid

from django.conf import settings
from django.db import models


class Report(models.Model):
    """
    Saved report configuration. Users can save custom report parameters
    and re-run them later.
    """

    class ReportType(models.TextChoices):
        REVENUE = "revenue", "Revenue Report"
        PIPELINE = "pipeline", "Pipeline Report"
        SALES_PERFORMANCE = "sales_performance", "Sales Performance"
        CONVERSION = "conversion", "Conversion Report"
        ACTIVITY = "activity", "Activity Report"
        CONTACT_GROWTH = "contact_growth", "Contact Growth"
        CUSTOM = "custom", "Custom Report"

    class DateRange(models.TextChoices):
        TODAY = "today", "Today"
        THIS_WEEK = "this_week", "This Week"
        THIS_MONTH = "this_month", "This Month"
        THIS_QUARTER = "this_quarter", "This Quarter"
        THIS_YEAR = "this_year", "This Year"
        LAST_7_DAYS = "last_7_days", "Last 7 Days"
        LAST_30_DAYS = "last_30_days", "Last 30 Days"
        LAST_90_DAYS = "last_90_days", "Last 90 Days"
        CUSTOM = "custom", "Custom Range"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    report_type = models.CharField(
        max_length=20,
        choices=ReportType.choices,
        default=ReportType.REVENUE,
    )
    date_range = models.CharField(
        max_length=20,
        choices=DateRange.choices,
        default=DateRange.THIS_MONTH,
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    filters = models.JSONField(
        default=dict,
        blank=True,
        help_text="JSON object of additional filter parameters",
    )
    is_favorite = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reports",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_favorite", "-created_at"]
        db_table = "crm_reports"

    def __str__(self):
        return f"{self.name} ({self.get_report_type_display()})"


class Dashboard(models.Model):
    """
    User-customizable dashboard with widget layout configuration.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, default="My Dashboard")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="dashboards",
    )
    layout = models.JSONField(
        default=list,
        blank=True,
        help_text="JSON array of widget configurations",
    )
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_default", "name"]
        db_table = "crm_dashboards"

    def __str__(self):
        return f"{self.name} - {self.user.get_full_name()}"

    def save(self, *args, **kwargs):
        if self.is_default:
            Dashboard.objects.filter(
                user=self.user, is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)
