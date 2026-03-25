"""
Serializers for the emails app.
"""

from rest_framework import serializers

from .models import EmailCampaign, EmailLog, EmailTemplate


class EmailTemplateSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(
        source="created_by.get_full_name", read_only=True, default=None
    )

    class Meta:
        model = EmailTemplate
        fields = [
            "id",
            "name",
            "subject",
            "body_html",
            "body_text",
            "category",
            "is_active",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]


class EmailCampaignListSerializer(serializers.ModelSerializer):
    template_name = serializers.CharField(source="template.name", read_only=True, default=None)
    created_by_name = serializers.CharField(
        source="created_by.get_full_name", read_only=True, default=None
    )
    open_rate = serializers.ReadOnlyField()
    click_rate = serializers.ReadOnlyField()
    recipient_count = serializers.SerializerMethodField()

    class Meta:
        model = EmailCampaign
        fields = [
            "id",
            "name",
            "template",
            "template_name",
            "status",
            "scheduled_at",
            "sent_at",
            "total_sent",
            "total_opened",
            "total_clicked",
            "total_bounced",
            "open_rate",
            "click_rate",
            "recipient_count",
            "created_by",
            "created_by_name",
            "created_at",
        ]

    def get_recipient_count(self, obj):
        return obj.recipients.count()


class EmailCampaignDetailSerializer(serializers.ModelSerializer):
    template_name = serializers.CharField(source="template.name", read_only=True, default=None)
    created_by_name = serializers.CharField(
        source="created_by.get_full_name", read_only=True, default=None
    )
    open_rate = serializers.ReadOnlyField()
    click_rate = serializers.ReadOnlyField()
    bounce_rate = serializers.ReadOnlyField()
    recipient_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=None,
        source="recipients",
        write_only=True,
        required=False,
    )

    class Meta:
        model = EmailCampaign
        fields = [
            "id",
            "name",
            "template",
            "template_name",
            "status",
            "scheduled_at",
            "sent_at",
            "total_sent",
            "total_opened",
            "total_clicked",
            "total_bounced",
            "open_rate",
            "click_rate",
            "bounce_rate",
            "recipient_ids",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_by",
            "total_sent",
            "total_opened",
            "total_clicked",
            "total_bounced",
            "sent_at",
            "created_at",
            "updated_at",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.contacts.models import Contact

        if "recipient_ids" in self.fields:
            self.fields["recipient_ids"].child_relation.queryset = Contact.objects.all()


class EmailCampaignCreateSerializer(serializers.ModelSerializer):
    recipient_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=None,
        source="recipients",
        required=False,
    )

    class Meta:
        model = EmailCampaign
        fields = [
            "name",
            "template",
            "scheduled_at",
            "recipient_ids",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.contacts.models import Contact

        self.fields["recipient_ids"].child_relation.queryset = Contact.objects.all()

    def create(self, validated_data):
        recipients = validated_data.pop("recipients", [])
        campaign = EmailCampaign.objects.create(**validated_data)
        if recipients:
            campaign.recipients.set(recipients)
        return campaign


class EmailLogSerializer(serializers.ModelSerializer):
    contact_name = serializers.SerializerMethodField()
    sent_by_name = serializers.CharField(
        source="sent_by.get_full_name", read_only=True, default=None
    )

    class Meta:
        model = EmailLog
        fields = [
            "id",
            "campaign",
            "contact",
            "contact_name",
            "to_email",
            "subject",
            "status",
            "error_message",
            "opened_at",
            "clicked_at",
            "sent_by",
            "sent_by_name",
            "sent_at",
            "created_at",
        ]

    def get_contact_name(self, obj):
        if obj.contact:
            return obj.contact.full_name
        return None


class SendEmailSerializer(serializers.Serializer):
    """Serializer for sending a single email."""

    to_email = serializers.EmailField()
    contact_id = serializers.UUIDField(required=False, allow_null=True)
    template_id = serializers.UUIDField(required=False, allow_null=True)
    subject = serializers.CharField(max_length=300, required=False)
    body_html = serializers.CharField(required=False)
    body_text = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        template_id = attrs.get("template_id")
        subject = attrs.get("subject")
        body_html = attrs.get("body_html")

        if not template_id and (not subject or not body_html):
            raise serializers.ValidationError(
                "Either provide a template_id or both subject and body_html."
            )
        return attrs
