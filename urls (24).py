"""
Serializers for the deals app.
"""

from rest_framework import serializers

from .models import Deal, DealActivity, DealStage, Pipeline


class DealStageSerializer(serializers.ModelSerializer):
    deal_count = serializers.ReadOnlyField()

    class Meta:
        model = DealStage
        fields = [
            "id",
            "pipeline",
            "name",
            "order",
            "probability",
            "color",
            "is_won",
            "is_lost",
            "deal_count",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class DealActivitySerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.get_full_name", read_only=True, default=None)

    class Meta:
        model = DealActivity
        fields = [
            "id",
            "deal",
            "activity_type",
            "description",
            "old_value",
            "new_value",
            "user",
            "user_name",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class PipelineListSerializer(serializers.ModelSerializer):
    deal_count = serializers.ReadOnlyField()
    total_value = serializers.ReadOnlyField()
    stages = DealStageSerializer(many=True, read_only=True)

    class Meta:
        model = Pipeline
        fields = [
            "id",
            "name",
            "description",
            "is_active",
            "is_default",
            "deal_count",
            "total_value",
            "stages",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class PipelineCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pipeline
        fields = ["name", "description", "is_active", "is_default"]


class DealListSerializer(serializers.ModelSerializer):
    stage_name = serializers.CharField(source="stage.name", read_only=True)
    stage_color = serializers.CharField(source="stage.color", read_only=True)
    pipeline_name = serializers.CharField(source="stage.pipeline.name", read_only=True)
    contact_name = serializers.SerializerMethodField()
    company_name = serializers.CharField(source="company.name", read_only=True, default=None)
    owner_name = serializers.CharField(source="owner.get_full_name", read_only=True, default=None)
    weighted_value = serializers.ReadOnlyField()

    class Meta:
        model = Deal
        fields = [
            "id",
            "title",
            "value",
            "currency",
            "stage",
            "stage_name",
            "stage_color",
            "pipeline_name",
            "contact",
            "contact_name",
            "company",
            "company_name",
            "owner",
            "owner_name",
            "priority",
            "expected_close_date",
            "weighted_value",
            "created_at",
        ]

    def get_contact_name(self, obj):
        if obj.contact:
            return obj.contact.full_name
        return None


class DealDetailSerializer(serializers.ModelSerializer):
    stage_name = serializers.CharField(source="stage.name", read_only=True)
    stage_color = serializers.CharField(source="stage.color", read_only=True)
    pipeline_name = serializers.CharField(source="stage.pipeline.name", read_only=True)
    pipeline_id = serializers.CharField(source="stage.pipeline.id", read_only=True)
    contact_name = serializers.SerializerMethodField()
    company_name = serializers.CharField(source="company.name", read_only=True, default=None)
    owner_name = serializers.CharField(source="owner.get_full_name", read_only=True, default=None)
    created_by_name = serializers.CharField(
        source="created_by.get_full_name", read_only=True, default=None
    )
    weighted_value = serializers.ReadOnlyField()
    is_closed = serializers.ReadOnlyField()
    activities = DealActivitySerializer(many=True, read_only=True)

    class Meta:
        model = Deal
        fields = [
            "id",
            "title",
            "description",
            "value",
            "currency",
            "stage",
            "stage_name",
            "stage_color",
            "pipeline_name",
            "pipeline_id",
            "contact",
            "contact_name",
            "company",
            "company_name",
            "owner",
            "owner_name",
            "priority",
            "expected_close_date",
            "actual_close_date",
            "probability",
            "weighted_value",
            "is_closed",
            "lost_reason",
            "created_by",
            "created_by_name",
            "activities",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]

    def get_contact_name(self, obj):
        if obj.contact:
            return obj.contact.full_name
        return None


class DealCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Deal
        fields = [
            "title",
            "description",
            "value",
            "currency",
            "stage",
            "contact",
            "company",
            "owner",
            "priority",
            "expected_close_date",
            "probability",
            "lost_reason",
        ]

    def validate_stage(self, value):
        if not value.pipeline.is_active:
            raise serializers.ValidationError(
                "Cannot assign a deal to a stage in an inactive pipeline."
            )
        return value


class DealMoveSerializer(serializers.Serializer):
    """Serializer for moving a deal to a different stage."""

    stage_id = serializers.UUIDField()
    lost_reason = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_stage_id(self, value):
        try:
            stage = DealStage.objects.get(id=value)
        except DealStage.DoesNotExist:
            raise serializers.ValidationError("Stage not found.")
        return value
