"""
Serializers for the integrations app.
"""

from rest_framework import serializers

from .models import Integration, SyncLog, WebhookEvent


class IntegrationListSerializer(serializers.ModelSerializer):
    """List serializer -- hides sensitive credential fields."""

    provider_display = serializers.CharField(
        source="get_provider_display", read_only=True
    )
    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )
    is_token_expired = serializers.ReadOnlyField()
    created_by_name = serializers.CharField(
        source="created_by.get_full_name", read_only=True, default=None
    )

    class Meta:
        model = Integration
        fields = [
            "id",
            "name",
            "provider",
            "provider_display",
            "status",
            "status_display",
            "is_enabled",
            "is_token_expired",
            "last_synced",
            "sync_frequency_minutes",
            "error_count",
            "created_by",
            "created_by_name",
            "created_at",
        ]


class IntegrationDetailSerializer(serializers.ModelSerializer):
    """Detail serializer -- includes config but still hides raw credentials."""

    provider_display = serializers.CharField(
        source="get_provider_display", read_only=True
    )
    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )
    is_token_expired = serializers.ReadOnlyField()
    created_by_name = serializers.CharField(
        source="created_by.get_full_name", read_only=True, default=None
    )
    # Mask sensitive fields
    has_api_key = serializers.SerializerMethodField()
    has_access_token = serializers.SerializerMethodField()

    class Meta:
        model = Integration
        fields = [
            "id",
            "name",
            "provider",
            "provider_display",
            "status",
            "status_display",
            "description",
            "has_api_key",
            "has_access_token",
            "is_token_expired",
            "token_expires_at",
            "config",
            "webhook_url",
            "is_enabled",
            "last_synced",
            "sync_frequency_minutes",
            "last_error",
            "error_count",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_by",
            "last_synced",
            "last_error",
            "error_count",
            "created_at",
            "updated_at",
        ]

    def get_has_api_key(self, obj):
        return bool(obj.api_key)

    def get_has_access_token(self, obj):
        return bool(obj.access_token)


class IntegrationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating integrations with credentials."""

    class Meta:
        model = Integration
        fields = [
            "name",
            "provider",
            "description",
            "api_key",
            "api_secret",
            "access_token",
            "refresh_token",
            "token_expires_at",
            "config",
            "webhook_url",
            "webhook_secret",
            "sync_frequency_minutes",
            "is_enabled",
        ]

    def validate(self, attrs):
        provider = attrs.get("provider", "")
        # Validate required fields per provider
        providers_needing_api_key = {
            Integration.Provider.SENDGRID,
            Integration.Provider.MAILCHIMP,
            Integration.Provider.STRIPE,
        }
        if provider in providers_needing_api_key and not attrs.get("api_key"):
            raise serializers.ValidationError(
                f"api_key is required for {provider} integrations."
            )
        return attrs


class WebhookEventListSerializer(serializers.ModelSerializer):
    integration_name = serializers.CharField(
        source="integration.name", read_only=True
    )

    class Meta:
        model = WebhookEvent
        fields = [
            "id",
            "integration",
            "integration_name",
            "direction",
            "event_type",
            "status",
            "response_status_code",
            "retry_count",
            "processed_at",
            "created_at",
        ]


class WebhookEventDetailSerializer(serializers.ModelSerializer):
    integration_name = serializers.CharField(
        source="integration.name", read_only=True
    )
    can_retry = serializers.ReadOnlyField()

    class Meta:
        model = WebhookEvent
        fields = [
            "id",
            "integration",
            "integration_name",
            "direction",
            "event_type",
            "payload",
            "headers",
            "status",
            "response_status_code",
            "response_body",
            "error_message",
            "retry_count",
            "max_retries",
            "can_retry",
            "next_retry_at",
            "processed_at",
            "created_at",
        ]


class SyncLogSerializer(serializers.ModelSerializer):
    integration_name = serializers.CharField(
        source="integration.name", read_only=True
    )

    class Meta:
        model = SyncLog
        fields = [
            "id",
            "integration",
            "integration_name",
            "started_at",
            "completed_at",
            "records_synced",
            "records_created",
            "records_updated",
            "records_failed",
            "error_message",
            "success",
        ]


class IntegrationTestSerializer(serializers.Serializer):
    """Request serializer for testing an integration connection."""

    integration_id = serializers.UUIDField()


class WebhookRetrySerializer(serializers.Serializer):
    """Request serializer for retrying a failed webhook event."""

    event_id = serializers.UUIDField()
