"""
Serializers for the segments app.
"""

from rest_framework import serializers

from .models import Segment, SegmentRule


class SegmentRuleSerializer(serializers.ModelSerializer):
    field_display = serializers.CharField(
        source="get_field_display", read_only=True
    )
    operator_display = serializers.CharField(
        source="get_operator_display", read_only=True
    )

    class Meta:
        model = SegmentRule
        fields = [
            "id",
            "segment",
            "field",
            "field_display",
            "operator",
            "operator_display",
            "value",
            "order",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class SegmentListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for segment list views."""

    rule_count = serializers.ReadOnlyField()
    created_by_name = serializers.CharField(
        source="created_by.get_full_name", read_only=True, default=None
    )

    class Meta:
        model = Segment
        fields = [
            "id",
            "name",
            "description",
            "segment_type",
            "match_mode",
            "is_active",
            "contact_count",
            "rule_count",
            "last_evaluated",
            "created_by",
            "created_by_name",
            "created_at",
        ]


class SegmentDetailSerializer(serializers.ModelSerializer):
    """Full serializer including nested rules."""

    rules = SegmentRuleSerializer(many=True, read_only=True)
    rule_count = serializers.ReadOnlyField()
    created_by_name = serializers.CharField(
        source="created_by.get_full_name", read_only=True, default=None
    )

    class Meta:
        model = Segment
        fields = [
            "id",
            "name",
            "description",
            "segment_type",
            "match_mode",
            "is_active",
            "contact_count",
            "rule_count",
            "rules",
            "last_evaluated",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_by",
            "contact_count",
            "last_evaluated",
            "created_at",
            "updated_at",
        ]


class SegmentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating segments with inline rules."""

    rules = SegmentRuleSerializer(many=True, required=False)

    class Meta:
        model = Segment
        fields = [
            "name",
            "description",
            "segment_type",
            "match_mode",
            "is_active",
            "rules",
        ]

    def create(self, validated_data):
        rules_data = validated_data.pop("rules", [])
        segment = Segment.objects.create(**validated_data)
        for idx, rule_data in enumerate(rules_data):
            rule_data.pop("segment", None)
            SegmentRule.objects.create(
                segment=segment, order=idx, **rule_data
            )
        return segment

    def update(self, instance, validated_data):
        rules_data = validated_data.pop("rules", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if rules_data is not None:
            # Replace all rules with the new set
            instance.rules.all().delete()
            for idx, rule_data in enumerate(rules_data):
                rule_data.pop("segment", None)
                SegmentRule.objects.create(
                    segment=instance, order=idx, **rule_data
                )

        return instance


class SegmentRuleCreateSerializer(serializers.ModelSerializer):
    """Serializer for adding individual rules to an existing segment."""

    class Meta:
        model = SegmentRule
        fields = ["field", "operator", "value", "order"]


class SegmentEvaluateSerializer(serializers.Serializer):
    """Response serializer for segment evaluation results."""

    contact_count = serializers.IntegerField()
    contact_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False
    )
    evaluated_at = serializers.DateTimeField()
