"""
Integration models for ClientHub CRM.
Manages third-party service connections (Slack, Salesforce, Mailchimp, etc.),
webhook endpoints, and synchronization state.
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Integration(models.Model):
    """
    Represents a configured third-party integration.
    Each integration stores its connection credentials (encrypted),
    configuration, and sync status.
    """

    class Provider(models.TextChoices):
        SLACK = "slack", "Slack"
        SALESFORCE = "salesforce", "Salesforce"
        HUBSPOT = "hubspot", "HubSpot"
        MAILCHIMP = "mailchimp", "Mailchimp"
        STRIPE = "stripe", "Stripe"
        ZAPIER = "zapier", "Zapier"
        GOOGLE_CALENDAR = "google_calendar", "Google Calendar"
        MICROSOFT_TEAMS = "ms_teams", "Microsoft Teams"
        TWILIO = "twilio", "Twilio"
        SENDGRID = "sendgrid", "SendGrid"
        CUSTOM_WEBHOOK = "webhook", "Custom Webhook"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        ERROR = "error", "Error"
        PENDING = "pending", "Pending Setup"
        EXPIRED = "expired", "Token Expired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, help_text="User-friendly label for this integration")
    provider = models.CharField(max_length=20, choices=Provider.choices, db_index=True)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    description = models.TextField(blank=True, default="")

    # Credentials (in production these should be encrypted at rest)
    api_key = models.CharField(max_length=500, blank=True, default="")
    api_secret = models.CharField(max_length=500, blank=True, default="")
    access_token = models.TextField(blank=True, default="")
    refresh_token = models.TextField(blank=True, default="")
    token_expires_at = models.DateTimeField(null=True, blank=True)

    # Configuration
    config = models.JSONField(
        default=dict, blank=True,
        help_text="Provider-specific configuration (channel IDs, sync options, etc.)",
    )
    webhook_url = models.URLField(blank=True, default="", help_text="Outgoing webhook URL")
    webhook_secret = models.CharField(
        max_length=200, blank=True, default="",
        help_text="Secret for validating incoming webhook payloads",
    )

    # Sync tracking
    last_synced = models.DateTimeField(null=True, blank=True)
    sync_frequency_minutes = models.PositiveIntegerField(
        default=60, help_text="How often to sync data (in minutes)"
    )
    last_error = models.TextField(blank=True, default="")
    error_count = models.PositiveIntegerField(default=0)

    is_enabled = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="integrations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["provider", "name"]
        db_table = "crm_integrations"

    def __str__(self):
        return f"{self.name} ({self.get_provider_display()})"

    @property
    def is_token_expired(self):
        if not self.token_expires_at:
            return False
        return timezone.now() >= self.token_expires_at

    def mark_error(self, error_message):
        """Record an error and increment the error count."""
        self.status = self.Status.ERROR
        self.last_error = error_message
        self.error_count += 1
        self.save(update_fields=["status", "last_error", "error_count", "updated_at"])

    def mark_synced(self):
        """Mark a successful sync."""
        self.last_synced = timezone.now()
        self.error_count = 0
        self.last_error = ""
        if self.status == self.Status.ERROR:
            self.status = self.Status.ACTIVE
        self.save(
            update_fields=["last_synced", "error_count", "last_error", "status", "updated_at"]
        )


class WebhookEvent(models.Model):
    """
    Log of incoming and outgoing webhook events.
    Provides an audit trail and retry mechanism for failed deliveries.
    """

    class Direction(models.TextChoices):
        INCOMING = "incoming", "Incoming"
        OUTGOING = "outgoing", "Outgoing"

    class EventStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        RETRYING = "retrying", "Retrying"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    integration = models.ForeignKey(
        Integration, on_delete=models.CASCADE, related_name="webhook_events"
    )
    direction = models.CharField(
        max_length=10, choices=Direction.choices, db_index=True
    )
    event_type = models.CharField(
        max_length=100, db_index=True,
        help_text="Event type identifier (e.g., 'contact.created', 'deal.won')",
    )
    payload = models.JSONField(default=dict, help_text="Full event payload")
    headers = models.JSONField(default=dict, blank=True, help_text="HTTP headers")
    status = models.CharField(
        max_length=12, choices=EventStatus.choices, default=EventStatus.PENDING
    )
    response_status_code = models.PositiveIntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    retry_count = models.PositiveIntegerField(default=0)
    max_retries = models.PositiveIntegerField(default=3)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        db_table = "crm_webhook_events"
        indexes = [
            models.Index(fields=["integration", "direction", "event_type"]),
            models.Index(fields=["status", "next_retry_at"]),
        ]

    def __str__(self):
        return f"{self.direction} {self.event_type} ({self.status})"

    @property
    def can_retry(self):
        return self.retry_count < self.max_retries and self.status == self.EventStatus.FAILED


class SyncLog(models.Model):
    """Records each sync execution for an integration."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    integration = models.ForeignKey(
        Integration, on_delete=models.CASCADE, related_name="sync_logs"
    )
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    records_synced = models.PositiveIntegerField(default=0)
    records_created = models.PositiveIntegerField(default=0)
    records_updated = models.PositiveIntegerField(default=0)
    records_failed = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True, default="")
    success = models.BooleanField(default=False)

    class Meta:
        ordering = ["-started_at"]
        db_table = "crm_sync_logs"

    def __str__(self):
        status_label = "OK" if self.success else "FAILED"
        return f"Sync {self.integration.name} at {self.started_at} [{status_label}]"
