"""
Deal, Pipeline, and DealStage models for ClientHub CRM.
"""

import uuid

from django.conf import settings
from django.db import models


class Pipeline(models.Model):
    """
    A sales pipeline containing ordered stages.
    Organizations can have multiple pipelines (e.g., Inbound, Outbound, Enterprise).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(
        default=False,
        help_text="Default pipeline for new deals",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_pipelines",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        db_table = "crm_pipelines"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Ensure only one default pipeline
        if self.is_default:
            Pipeline.objects.filter(is_default=True).exclude(pk=self.pk).update(
                is_default=False
            )
        super().save(*args, **kwargs)

    @property
    def deal_count(self):
        return Deal.objects.filter(stage__pipeline=self).count()

    @property
    def total_value(self):
        return (
            Deal.objects.filter(stage__pipeline=self)
            .aggregate(total=models.Sum("value"))
            .get("total")
            or 0
        )


class DealStage(models.Model):
    """
    A stage within a pipeline (e.g., Lead, Qualified, Proposal, Negotiation, Won, Lost).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pipeline = models.ForeignKey(
        Pipeline, on_delete=models.CASCADE, related_name="stages"
    )
    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField(
        default=0,
        help_text="Position of this stage in the pipeline (ascending order)",
    )
    probability = models.PositiveIntegerField(
        default=0,
        help_text="Win probability percentage (0-100)",
    )
    color = models.CharField(max_length=7, default="#6B7280", help_text="Hex color code")
    is_won = models.BooleanField(default=False, help_text="Marks this as a 'won' stage")
    is_lost = models.BooleanField(default=False, help_text="Marks this as a 'lost' stage")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["pipeline", "order"]
        db_table = "crm_deal_stages"
        unique_together = [("pipeline", "name"), ("pipeline", "order")]

    def __str__(self):
        return f"{self.pipeline.name} - {self.name}"

    @property
    def deal_count(self):
        return self.deals.count()


class Deal(models.Model):
    """
    Represents a sales opportunity / deal in the pipeline.
    """

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200, db_index=True)
    description = models.TextField(blank=True, default="")
    value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text="Monetary value of the deal",
    )
    currency = models.CharField(max_length=3, default="USD")
    stage = models.ForeignKey(
        DealStage, on_delete=models.PROTECT, related_name="deals"
    )
    contact = models.ForeignKey(
        "contacts.Contact",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deals",
    )
    company = models.ForeignKey(
        "contacts.Company",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deals",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="owned_deals",
    )
    priority = models.CharField(
        max_length=10,
        choices=Priority.choices,
        default=Priority.MEDIUM,
    )
    expected_close_date = models.DateField(null=True, blank=True)
    actual_close_date = models.DateField(null=True, blank=True)
    probability = models.PositiveIntegerField(
        default=0,
        help_text="Override probability (0-100). Uses stage probability if 0.",
    )
    lost_reason = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_deals",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        db_table = "crm_deals"

    def __str__(self):
        return self.title

    @property
    def weighted_value(self):
        """Calculate weighted value based on probability."""
        prob = self.probability if self.probability > 0 else self.stage.probability
        return float(self.value) * (prob / 100.0)

    @property
    def is_closed(self):
        return self.stage.is_won or self.stage.is_lost

    @property
    def pipeline(self):
        return self.stage.pipeline


class DealActivity(models.Model):
    """
    Tracks stage changes and key events on a deal.
    """

    class ActivityType(models.TextChoices):
        STAGE_CHANGE = "stage_change", "Stage Change"
        VALUE_CHANGE = "value_change", "Value Change"
        OWNER_CHANGE = "owner_change", "Owner Change"
        NOTE = "note", "Note"
        EMAIL_SENT = "email_sent", "Email Sent"
        MEETING = "meeting", "Meeting"
        CALL = "call", "Call"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    deal = models.ForeignKey(
        Deal, on_delete=models.CASCADE, related_name="activities"
    )
    activity_type = models.CharField(
        max_length=20, choices=ActivityType.choices, db_index=True
    )
    description = models.TextField()
    old_value = models.CharField(max_length=255, blank=True, default="")
    new_value = models.CharField(max_length=255, blank=True, default="")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="deal_activities",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        db_table = "crm_deal_activities"
        verbose_name_plural = "deal activities"

    def __str__(self):
        return f"{self.deal.title} - {self.activity_type}"
