"""
Email models: templates, campaigns, and send logs for ClientHub CRM.
"""

import uuid

from django.conf import settings
from django.db import models


class EmailTemplate(models.Model):
    """
    Reusable email templates with variable placeholders.
    Supports placeholders like {{contact_name}}, {{company_name}}, {{deal_value}}.
    """

    class Category(models.TextChoices):
        OUTREACH = "outreach", "Outreach"
        FOLLOW_UP = "follow_up", "Follow Up"
        PROPOSAL = "proposal", "Proposal"
        ONBOARDING = "onboarding", "Onboarding"
        NEWSLETTER = "newsletter", "Newsletter"
        NOTIFICATION = "notification", "Notification"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, unique=True)
    subject = models.CharField(max_length=300)
    body_html = models.TextField(help_text="HTML body with {{variable}} placeholders")
    body_text = models.TextField(
        blank=True, default="", help_text="Plain text fallback"
    )
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.OTHER,
    )
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="email_templates",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        db_table = "crm_email_templates"

    def __str__(self):
        return self.name


class EmailCampaign(models.Model):
    """
    An email campaign that sends a template to a set of contacts.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SCHEDULED = "scheduled", "Scheduled"
        SENDING = "sending", "Sending"
        SENT = "sent", "Sent"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    template = models.ForeignKey(
        EmailTemplate,
        on_delete=models.SET_NULL,
        null=True,
        related_name="campaigns",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    recipients = models.ManyToManyField(
        "contacts.Contact",
        blank=True,
        related_name="email_campaigns",
    )
    scheduled_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    total_sent = models.PositiveIntegerField(default=0)
    total_opened = models.PositiveIntegerField(default=0)
    total_clicked = models.PositiveIntegerField(default=0)
    total_bounced = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="email_campaigns",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        db_table = "crm_email_campaigns"

    def __str__(self):
        return self.name

    @property
    def open_rate(self):
        if self.total_sent == 0:
            return 0
        return round((self.total_opened / self.total_sent) * 100, 2)

    @property
    def click_rate(self):
        if self.total_sent == 0:
            return 0
        return round((self.total_clicked / self.total_sent) * 100, 2)

    @property
    def bounce_rate(self):
        if self.total_sent == 0:
            return 0
        return round((self.total_bounced / self.total_sent) * 100, 2)


class EmailLog(models.Model):
    """
    Log of individual emails sent, both campaign and direct.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        DELIVERED = "delivered", "Delivered"
        OPENED = "opened", "Opened"
        CLICKED = "clicked", "Clicked"
        BOUNCED = "bounced", "Bounced"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(
        EmailCampaign,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="logs",
    )
    contact = models.ForeignKey(
        "contacts.Contact",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="email_logs",
    )
    to_email = models.EmailField()
    subject = models.CharField(max_length=300)
    body_html = models.TextField(blank=True, default="")
    body_text = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    error_message = models.TextField(blank=True, default="")
    opened_at = models.DateTimeField(null=True, blank=True)
    clicked_at = models.DateTimeField(null=True, blank=True)
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sent_emails",
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        db_table = "crm_email_logs"

    def __str__(self):
        return f"Email to {self.to_email}: {self.subject}"
