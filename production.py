"""
Views for the segments app: segment CRUD, rule management, and evaluation.
"""

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.activities.models import ActivityLog
from utils.permissions import IsSalesManager

from .models import Segment, SegmentRule
from .serializers import (
    SegmentCreateSerializer,
    SegmentDetailSerializer,
    SegmentListSerializer,
    SegmentRuleCreateSerializer,
    SegmentRuleSerializer,
)
from .services import SegmentService


class SegmentViewSet(viewsets.ModelViewSet):
    """
    CRUD for contact segments with rule evaluation.

    GET    /api/segments/segments/                  - List segments
    POST   /api/segments/segments/                  - Create segment (with inline rules)
    GET    /api/segments/segments/{id}/             - Retrieve segment
    PUT    /api/segments/segments/{id}/             - Update segment
    DELETE /api/segments/segments/{id}/             - Delete segment
    POST   /api/segments/segments/{id}/evaluate/   - Evaluate segment (refresh contacts)
    POST   /api/segments/segments/{id}/preview/    - Preview segment match count
    POST   /api/segments/segments/{id}/rules/      - Add a rule
    GET    /api/segments/segments/{id}/contacts/   - List matching contacts
    """

    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["segment_type", "is_active", "created_by"]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "contact_count", "created_at", "last_evaluated"]
    ordering = ["name"]

    def get_queryset(self):
        return Segment.objects.select_related("created_by").prefetch_related("rules").all()

    def get_serializer_class(self):
        if self.action == "list":
            return SegmentListSerializer
        if self.action in ("create", "update", "partial_update"):
            return SegmentCreateSerializer
        return SegmentDetailSerializer

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [permissions.IsAuthenticated(), IsSalesManager()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        segment = serializer.save(created_by=self.request.user)
        ActivityLog.objects.create(
            user=self.request.user,
            action=ActivityLog.Action.CREATED,
            entity_type="segment",
            entity_id=str(segment.id),
            description=f"Created segment '{segment.name}'",
        )

    @action(detail=True, methods=["post"], url_path="evaluate")
    def evaluate(self, request, pk=None):
        """
        Evaluate a segment: run its rules against the contact database
        and update the cached contact count.
        """
        segment = self.get_object()
        contacts = SegmentService.evaluate_segment(segment)
        contact_ids = list(contacts.values_list("id", flat=True)[:100])

        return Response(
            {
                "segment_id": str(segment.id),
                "segment_name": segment.name,
                "contact_count": segment.contact_count,
                "sample_contact_ids": [str(cid) for cid in contact_ids],
                "evaluated_at": segment.last_evaluated.isoformat(),
            }
        )

    @action(detail=False, methods=["post"], url_path="preview")
    def preview(self, request):
        """
        Preview a segment without saving. Accepts raw rule data
        and returns the match count and sample IDs.
        """
        rules = request.data.get("rules", [])
        match_mode = request.data.get("match_mode", "all")

        if not rules:
            return Response(
                {"contact_count": 0, "sample_ids": []},
                status=status.HTTP_200_OK,
            )

        result = SegmentService.preview_segment(rules, match_mode)
        return Response(result)

    @action(detail=True, methods=["post"], url_path="rules")
    def add_rule(self, request, pk=None):
        """Add a single rule to an existing segment."""
        segment = self.get_object()
        serializer = SegmentRuleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        rule = SegmentRule.objects.create(
            segment=segment, **serializer.validated_data
        )
        return Response(
            SegmentRuleSerializer(rule).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get"], url_path="contacts")
    def contacts(self, request, pk=None):
        """Return the list of contacts matching this segment."""
        segment = self.get_object()
        contacts = SegmentService.evaluate_segment(segment)

        from apps.contacts.serializers import ContactListSerializer

        # Apply pagination
        page = self.paginate_queryset(contacts)
        if page is not None:
            serializer = ContactListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = ContactListSerializer(contacts, many=True)
        return Response(serializer.data)


class SegmentRuleViewSet(viewsets.ModelViewSet):
    """
    Standalone CRUD for segment rules.

    GET    /api/segments/rules/         - List all rules
    POST   /api/segments/rules/         - Create rule
    GET    /api/segments/rules/{id}/    - Retrieve rule
    PUT    /api/segments/rules/{id}/    - Update rule
    DELETE /api/segments/rules/{id}/    - Delete rule
    """

    queryset = SegmentRule.objects.select_related("segment").all()
    serializer_class = SegmentRuleSerializer
    permission_classes = [permissions.IsAuthenticated, IsSalesManager]
    filterset_fields = ["segment", "field", "operator"]
    ordering_fields = ["order", "created_at"]
