"""
Campaign management models for ClientHub CRM.
Supports multi-channel marketing campaigns with audience targeting,
scheduling, and performance tracking.
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class CampaignTag(models.Model):
    """Tags for organizing and filtering campaigns."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, unique=True, db_index=True)
    color = models.CharField(max_length=7, default="#8B5CF6", help_text="Hex color code")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        db_table = "crm_campaign_tags"

    def __str__(self):
        return self.name


class Campaign(models.Model):
    """
    Multi-channel marketing campaign.
    Campaigns target a segment of contacts and deliver content through
    one or more channels (email, SMS, push notifications).
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SCHEDULED = "scheduled", "Scheduled"
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    class Channel(models.TextChoices):
        EMAIL = "email", "Email"
        SMS = "sms", "SMS"
        PUSH = "push", "Push Notification"
        MULTI = "multi", "Multi-Channel"

    class CampaignType(models.TextChoices):
        ONE_TIME = "one_time", "One-Time Blast"
        DRIP = "drip", "Drip Sequence"
        TRIGGERED = "triggered", "Event-Triggered"
        AB_TEST = "ab_test", "A/B Test"
        RECURRING = "recurring", "Recurring"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, db_index=True)
    description = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True
    )
    channel = models.CharField(
        max_length=10, choices=Channel.choices, default=Channel.EMAIL
    )
    campaign_type = models.CharField(
        max_length=20, choices=CampaignType.choices, default=CampaignType.ONE_TIME
    )
    segment = models.ForeignKey(
        "segments.Segment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="campaigns",
        help_text="Target audience segment",
    )
    email_template = models.ForeignKey(
        "emails.EmailTemplate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="marketing_campaigns",
    )
    subject_line = models.CharField(max_length=300, blank=True, default="")
    content_html = models.TextField(blank=True, default="", help_text="HTML content body")
    content_text = models.TextField(blank=True, default="", help_text="Plain text fallback")
    tags = models.ManyToManyField(CampaignTag, blank=True, related_name="campaigns")

    # Scheduling
    scheduled_start = models.DateTimeField(null=True, blank=True)
    scheduled_end = models.DateTimeField(null=True, blank=True)
    actual_start = models.DateTimeField(null=True, blank=True)
    actual_end = models.DateTimeField(null=True, blank=True)

    # A/B Test configuration
    ab_variant_name = models.CharField(max_length=50, blank=True, default="")
    ab_parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="ab_variants",
    )
    ab_split_percentage = models.PositiveIntegerField(
        default=50, help_text="Percentage of audience for this variant (0-100)"
    )

    # Budget
    budget = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    cost_per_send = models.DecimalField(
        max_digits=8, decimal_places=4, null=True, blank=True
    )

    # Performance metrics (denormalized for fast dashboard queries)
    total_targeted = models.PositiveIntegerField(default=0)
    total_sent = models.PositiveIntegerField(default=0)
    total_delivered = models.PositiveIntegerField(default=0)
    total_opened = models.PositiveIntegerField(default=0)
    total_clicked = models.PositiveIntegerField(default=0)
    total_converted = models.PositiveIntegerField(default=0)
    total_unsubscribed = models.PositiveIntegerField(default=0)
    total_bounced = models.PositiveIntegerField(default=0)
    total_revenue = models.DecimalField(
        max_digits=15, decimal_places=2, default=0
    )

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_campaigns",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_campaigns",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        db_table = "crm_campaigns"

    def __str__(self):
        return self.name

    @property
    def open_rate(self):
        if self.total_delivered == 0:
            return 0
        return round((self.total_opened / self.total_delivered) * 100, 2)

    @property
    def click_rate(self):
        if self.total_delivered == 0:
            return 0
        return round((self.total_clicked / self.total_delivered) * 100, 2)

    @property
    def conversion_rate(self):
        if self.total_delivered == 0:
            return 0
        return round((self.total_converted / self.total_delivered) * 100, 2)

    @property
    def bounce_rate(self):
        if self.total_sent == 0:
            return 0
        return round((self.total_bounced / self.total_sent) * 100, 2)

    @property
    def roi(self):
        """Return on investment as a percentage."""
        if not self.budget or self.budget == 0:
            return None
        return round(
            (float(self.total_revenue) - float(self.budget)) / float(self.budget) * 100, 2
        )

    def activate(self):
        """Transition campaign to active status."""
        if self.status not in (self.Status.DRAFT, self.Status.SCHEDULED):
            raise ValueError(f"Cannot activate campaign in '{self.status}' status.")
        self.status = self.Status.ACTIVE
        self.actual_start = timezone.now()
        self.save(update_fields=["status", "actual_start", "updated_at"])

    def pause(self):
        if self.status != self.Status.ACTIVE:
            raise ValueError("Only active campaigns can be paused.")
        self.status = self.Status.PAUSED
        self.save(update_fields=["status", "updated_at"])

    def complete(self):
        if self.status not in (self.Status.ACTIVE, self.Status.PAUSED):
            raise ValueError("Only active or paused campaigns can be completed.")
        self.status = self.Status.COMPLETED
        self.actual_end = timezone.now()
        self.save(update_fields=["status", "actual_end", "updated_at"])


class CampaignRecipient(models.Model):
    """
    Tracks individual recipient status within a campaign.
    Created when a campaign is executed against its target segment.
    """

    class DeliveryStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        DELIVERED = "delivered", "Delivered"
        OPENED = "opened", "Opened"
        CLICKED = "clicked", "Clicked"
        CONVERTED = "converted", "Converted"
        BOUNCED = "bounced", "Bounced"
        UNSUBSCRIBED = "unsubscribed", "Unsubscribed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="recipients"
    )
    contact = models.ForeignKey(
        "contacts.Contact",
        on_delete=models.CASCADE,
        related_name="campaign_deliveries",
    )
    status = models.CharField(
        max_length=20,
        choices=DeliveryStatus.choices,
        default=DeliveryStatus.PENDING,
        db_index=True,
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    clicked_at = models.DateTimeField(null=True, blank=True)
    converted_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        db_table = "crm_campaign_recipients"
        unique_together = [("campaign", "contact")]

    def __str__(self):
        return f"{self.campaign.name} -> {self.contact.full_name} ({self.status})"
