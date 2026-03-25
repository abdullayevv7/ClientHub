"""
Serializers for the campaigns app.
"""

from rest_framework import serializers

from .models import Campaign, CampaignRecipient, CampaignTag


class CampaignTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = CampaignTag
        fields = ["id", "name", "color", "created_at"]
        read_only_fields = ["id", "created_at"]


class CampaignListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for campaign list views."""

    segment_name = serializers.CharField(
        source="segment.name", read_only=True, default=None
    )
    owner_name = serializers.CharField(
        source="owner.get_full_name", read_only=True, default=None
    )
    tags = CampaignTagSerializer(many=True, read_only=True)
    open_rate = serializers.ReadOnlyField()
    click_rate = serializers.ReadOnlyField()
    conversion_rate = serializers.ReadOnlyField()

    class Meta:
        model = Campaign
        fields = [
            "id",
            "name",
            "status",
            "channel",
            "campaign_type",
            "segment",
            "segment_name",
            "subject_line",
            "tags",
            "scheduled_start",
            "actual_start",
            "total_targeted",
            "total_sent",
            "total_delivered",
            "total_opened",
            "total_clicked",
            "total_converted",
            "open_rate",
            "click_rate",
            "conversion_rate",
            "owner",
            "owner_name",
            "created_at",
        ]


class CampaignDetailSerializer(serializers.ModelSerializer):
    """Full serializer with all fields and computed properties."""

    segment_name = serializers.CharField(
        source="segment.name", read_only=True, default=None
    )
    template_name = serializers.CharField(
        source="email_template.name", read_only=True, default=None
    )
    owner_name = serializers.CharField(
        source="owner.get_full_name", read_only=True, default=None
    )
    created_by_name = serializers.CharField(
        source="created_by.get_full_name", read_only=True, default=None
    )
    tags = CampaignTagSerializer(many=True, read_only=True)
    open_rate = serializers.ReadOnlyField()
    click_rate = serializers.ReadOnlyField()
    conversion_rate = serializers.ReadOnlyField()
    bounce_rate = serializers.ReadOnlyField()
    roi = serializers.ReadOnlyField()
    ab_variants = CampaignListSerializer(many=True, read_only=True)

    class Meta:
        model = Campaign
        fields = [
            "id",
            "name",
            "description",
            "status",
            "channel",
            "campaign_type",
            "segment",
            "segment_name",
            "email_template",
            "template_name",
            "subject_line",
            "content_html",
            "content_text",
            "tags",
            "scheduled_start",
            "scheduled_end",
            "actual_start",
            "actual_end",
            "ab_variant_name",
            "ab_parent",
            "ab_split_percentage",
            "budget",
            "cost_per_send",
            "total_targeted",
            "total_sent",
            "total_delivered",
            "total_opened",
            "total_clicked",
            "total_converted",
            "total_unsubscribed",
            "total_bounced",
            "total_revenue",
            "open_rate",
            "click_rate",
            "conversion_rate",
            "bounce_rate",
            "roi",
            "ab_variants",
            "owner",
            "owner_name",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_by",
            "total_targeted",
            "total_sent",
            "total_delivered",
            "total_opened",
            "total_clicked",
            "total_converted",
            "total_unsubscribed",
            "total_bounced",
            "total_revenue",
            "actual_start",
            "actual_end",
            "created_at",
            "updated_at",
        ]


class CampaignCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating campaigns."""

    tag_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=CampaignTag.objects.all(),
        source="tags",
        required=False,
    )

    class Meta:
        model = Campaign
        fields = [
            "name",
            "description",
            "channel",
            "campaign_type",
            "segment",
            "email_template",
            "subject_line",
            "content_html",
            "content_text",
            "tag_ids",
            "scheduled_start",
            "scheduled_end",
            "ab_variant_name",
            "ab_parent",
            "ab_split_percentage",
            "budget",
            "cost_per_send",
            "owner",
        ]

    def validate(self, attrs):
        channel = attrs.get("channel", Campaign.Channel.EMAIL)
        if channel == Campaign.Channel.EMAIL:
            if not attrs.get("email_template") and not attrs.get("content_html"):
                raise serializers.ValidationError(
                    "Email campaigns require either an email_template or content_html."
                )
        scheduled_start = attrs.get("scheduled_start")
        scheduled_end = attrs.get("scheduled_end")
        if scheduled_start and scheduled_end and scheduled_end <= scheduled_start:
            raise serializers.ValidationError(
                "scheduled_end must be after scheduled_start."
            )
        return attrs

    def create(self, validated_data):
        tags = validated_data.pop("tags", [])
        campaign = Campaign.objects.create(**validated_data)
        if tags:
            campaign.tags.set(tags)
        return campaign

    def update(self, instance, validated_data):
        tags = validated_data.pop("tags", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if tags is not None:
            instance.tags.set(tags)
        return instance


class CampaignRecipientSerializer(serializers.ModelSerializer):
    contact_name = serializers.SerializerMethodField()
    contact_email = serializers.CharField(
        source="contact.email", read_only=True
    )

    class Meta:
        model = CampaignRecipient
        fields = [
            "id",
            "campaign",
            "contact",
            "contact_name",
            "contact_email",
            "status",
            "sent_at",
            "delivered_at",
            "opened_at",
            "clicked_at",
            "converted_at",
            "error_message",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_contact_name(self, obj):
        if obj.contact:
            return obj.contact.full_name
        return None


class CampaignActionSerializer(serializers.Serializer):
    """Serializer for campaign lifecycle actions (activate, pause, complete)."""

    action = serializers.ChoiceField(
        choices=["activate", "pause", "complete", "cancel"]
    )
    reason = serializers.CharField(required=False, allow_blank=True, default="")
