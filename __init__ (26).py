"""
Views for the deals app: deals, pipelines, stages.
"""

from django.db.models import Q, Sum
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import User
from apps.activities.models import ActivityLog
from utils.permissions import IsTeamMemberOrAdmin

from .models import Deal, DealActivity, DealStage, Pipeline
from .serializers import (
    DealActivitySerializer,
    DealCreateUpdateSerializer,
    DealDetailSerializer,
    DealListSerializer,
    DealMoveSerializer,
    DealStageSerializer,
    PipelineCreateSerializer,
    PipelineListSerializer,
)


class PipelineViewSet(viewsets.ModelViewSet):
    """
    CRUD for sales pipelines.

    GET    /api/deals/pipelines/         - List pipelines
    POST   /api/deals/pipelines/         - Create pipeline
    GET    /api/deals/pipelines/{id}/    - Retrieve pipeline
    PUT    /api/deals/pipelines/{id}/    - Update pipeline
    DELETE /api/deals/pipelines/{id}/    - Delete pipeline
    """

    queryset = Pipeline.objects.prefetch_related("stages").all()
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["name"]
    ordering_fields = ["name", "created_at"]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return PipelineCreateSerializer
        return PipelineListSerializer

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            from apps.accounts.permissions import IsAdminUser

            return [permissions.IsAuthenticated(), IsAdminUser()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["get"], url_path="deals")
    def deals(self, request, pk=None):
        """List all deals in a pipeline, grouped by stage."""
        pipeline = self.get_object()
        stages = pipeline.stages.all()
        result = []
        for stage in stages:
            deals = Deal.objects.filter(stage=stage).select_related(
                "contact", "company", "owner"
            )
            result.append(
                {
                    "stage": DealStageSerializer(stage).data,
                    "deals": DealListSerializer(deals, many=True).data,
                }
            )
        return Response(result)

    @action(detail=True, methods=["post"], url_path="stages")
    def add_stage(self, request, pk=None):
        """Add a new stage to a pipeline."""
        pipeline = self.get_object()
        serializer = DealStageSerializer(data={**request.data, "pipeline": pipeline.id})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class DealStageViewSet(viewsets.ModelViewSet):
    """
    CRUD for deal stages.

    GET    /api/deals/stages/         - List all stages
    POST   /api/deals/stages/         - Create a stage
    GET    /api/deals/stages/{id}/    - Retrieve a stage
    PUT    /api/deals/stages/{id}/    - Update a stage
    DELETE /api/deals/stages/{id}/    - Delete a stage
    """

    queryset = DealStage.objects.select_related("pipeline").all()
    serializer_class = DealStageSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["pipeline"]
    ordering_fields = ["order", "name"]

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            from utils.permissions import IsSalesManager

            return [permissions.IsAuthenticated(), IsSalesManager()]
        return [permissions.IsAuthenticated()]


class DealViewSet(viewsets.ModelViewSet):
    """
    CRUD for deals with role-based filtering.

    GET    /api/deals/deals/         - List deals
    POST   /api/deals/deals/         - Create a deal
    GET    /api/deals/deals/{id}/    - Retrieve a deal
    PUT    /api/deals/deals/{id}/    - Update a deal
    DELETE /api/deals/deals/{id}/    - Delete a deal
    """

    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["stage", "owner", "priority", "company", "contact"]
    search_fields = ["title", "description", "contact__first_name", "company__name"]
    ordering_fields = ["title", "value", "created_at", "expected_close_date", "priority"]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        queryset = Deal.objects.select_related(
            "stage", "stage__pipeline", "contact", "company", "owner", "created_by"
        )

        if user.role == User.Role.ADMIN:
            return queryset
        elif user.role == User.Role.SALES_MANAGER and user.team:
            team_members = User.objects.filter(team=user.team)
            return queryset.filter(Q(owner__in=team_members) | Q(owner__isnull=True))
        elif user.role == User.Role.SUPPORT_AGENT:
            return queryset  # Read-only
        else:
            return queryset.filter(Q(owner=user) | Q(owner__isnull=True))

    def get_serializer_class(self):
        if self.action == "list":
            return DealListSerializer
        if self.action in ("create", "update", "partial_update"):
            return DealCreateUpdateSerializer
        return DealDetailSerializer

    def perform_create(self, serializer):
        deal = serializer.save(created_by=self.request.user)
        if not deal.owner:
            deal.owner = self.request.user
            deal.save(update_fields=["owner"])

        # Log activity
        DealActivity.objects.create(
            deal=deal,
            activity_type=DealActivity.ActivityType.STAGE_CHANGE,
            description=f"Deal created in stage '{deal.stage.name}'",
            new_value=deal.stage.name,
            user=self.request.user,
        )

        ActivityLog.objects.create(
            user=self.request.user,
            action=ActivityLog.Action.CREATED,
            entity_type="deal",
            entity_id=str(deal.id),
            description=f"Created deal '{deal.title}' (${deal.value})",
        )

        # Update contact lead score
        if deal.contact:
            deal.contact.update_lead_score(10)

    def perform_update(self, serializer):
        old_deal = self.get_object()
        old_stage = old_deal.stage
        old_value = old_deal.value
        old_owner = old_deal.owner

        deal = serializer.save()

        # Track stage changes
        if deal.stage != old_stage:
            DealActivity.objects.create(
                deal=deal,
                activity_type=DealActivity.ActivityType.STAGE_CHANGE,
                description=f"Moved from '{old_stage.name}' to '{deal.stage.name}'",
                old_value=old_stage.name,
                new_value=deal.stage.name,
                user=self.request.user,
            )

        # Track value changes
        if deal.value != old_value:
            DealActivity.objects.create(
                deal=deal,
                activity_type=DealActivity.ActivityType.VALUE_CHANGE,
                description=f"Value changed from ${old_value} to ${deal.value}",
                old_value=str(old_value),
                new_value=str(deal.value),
                user=self.request.user,
            )

        # Track owner changes
        if deal.owner != old_owner:
            DealActivity.objects.create(
                deal=deal,
                activity_type=DealActivity.ActivityType.OWNER_CHANGE,
                description=f"Owner changed to {deal.owner.get_full_name() if deal.owner else 'unassigned'}",
                old_value=old_owner.get_full_name() if old_owner else "",
                new_value=deal.owner.get_full_name() if deal.owner else "",
                user=self.request.user,
            )

        ActivityLog.objects.create(
            user=self.request.user,
            action=ActivityLog.Action.UPDATED,
            entity_type="deal",
            entity_id=str(deal.id),
            description=f"Updated deal '{deal.title}'",
        )

    @action(detail=True, methods=["patch"], url_path="move")
    def move(self, request, pk=None):
        """Move a deal to a different stage (e.g., from drag-and-drop)."""
        deal = self.get_object()
        serializer = DealMoveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        old_stage = deal.stage
        new_stage = DealStage.objects.get(id=serializer.validated_data["stage_id"])

        deal.stage = new_stage

        # If moving to a lost stage, record the reason
        if new_stage.is_lost:
            deal.lost_reason = serializer.validated_data.get("lost_reason", "")
            deal.actual_close_date = timezone.now().date()
        elif new_stage.is_won:
            deal.actual_close_date = timezone.now().date()

        deal.save()

        # Log activity
        DealActivity.objects.create(
            deal=deal,
            activity_type=DealActivity.ActivityType.STAGE_CHANGE,
            description=f"Moved from '{old_stage.name}' to '{new_stage.name}'",
            old_value=old_stage.name,
            new_value=new_stage.name,
            user=request.user,
        )

        ActivityLog.objects.create(
            user=request.user,
            action=ActivityLog.Action.STAGE_CHANGED,
            entity_type="deal",
            entity_id=str(deal.id),
            description=f"Deal '{deal.title}' moved to '{new_stage.name}'",
        )

        return Response(DealDetailSerializer(deal).data)

    @action(detail=True, methods=["get"], url_path="activities")
    def activities(self, request, pk=None):
        """List all activities for a deal."""
        deal = self.get_object()
        activities = deal.activities.select_related("user").all()
        serializer = DealActivitySerializer(activities, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="add-activity")
    def add_activity(self, request, pk=None):
        """Add a manual activity entry to a deal."""
        deal = self.get_object()
        serializer = DealActivitySerializer(data={**request.data, "deal": deal.id})
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
