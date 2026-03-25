"""
Views for the campaigns app: campaign CRUD, lifecycle actions, and recipient tracking.
"""

from django.db.models import Q
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import User
from apps.activities.models import ActivityLog
from utils.permissions import IsSalesManager

from .models import Campaign, CampaignRecipient, CampaignTag
from .serializers import (
    CampaignActionSerializer,
    CampaignCreateSerializer,
    CampaignDetailSerializer,
    CampaignListSerializer,
    CampaignRecipientSerializer,
    CampaignTagSerializer,
)
from .services import CampaignService


class CampaignTagViewSet(viewsets.ModelViewSet):
    """
    CRUD for campaign tags.

    GET    /api/campaigns/tags/         - List tags
    POST   /api/campaigns/tags/         - Create tag
    GET    /api/campaigns/tags/{id}/    - Retrieve tag
    PUT    /api/campaigns/tags/{id}/    - Update tag
    DELETE /api/campaigns/tags/{id}/    - Delete tag
    """

    queryset = CampaignTag.objects.all()
    serializer_class = CampaignTagSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["name"]
    ordering_fields = ["name", "created_at"]


class CampaignViewSet(viewsets.ModelViewSet):
    """
    CRUD and lifecycle management for campaigns.

    GET    /api/campaigns/campaigns/              - List campaigns
    POST   /api/campaigns/campaigns/              - Create campaign
    GET    /api/campaigns/campaigns/{id}/         - Retrieve campaign
    PUT    /api/campaigns/campaigns/{id}/         - Update campaign
    DELETE /api/campaigns/campaigns/{id}/         - Delete campaign
    PATCH  /api/campaigns/campaigns/{id}/action/  - Lifecycle action
    GET    /api/campaigns/campaigns/{id}/recipients/ - List recipients
    POST   /api/campaigns/campaigns/{id}/launch/  - Launch campaign
    GET    /api/campaigns/campaigns/{id}/stats/   - Performance stats
    """

    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["status", "channel", "campaign_type", "owner", "segment"]
    search_fields = ["name", "description", "subject_line"]
    ordering_fields = ["name", "status", "created_at", "scheduled_start", "total_sent"]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        queryset = Campaign.objects.select_related(
            "segment", "email_template", "owner", "created_by", "ab_parent"
        ).prefetch_related("tags")

        if user.role == User.Role.ADMIN:
            return queryset
        elif user.role == User.Role.SALES_MANAGER and user.team:
            team_members = User.objects.filter(team=user.team)
            return queryset.filter(
                Q(owner__in=team_members) | Q(owner__isnull=True)
            )
        return queryset.filter(Q(owner=user) | Q(created_by=user))

    def get_serializer_class(self):
        if self.action == "list":
            return CampaignListSerializer
        if self.action in ("create", "update", "partial_update"):
            return CampaignCreateSerializer
        return CampaignDetailSerializer

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [permissions.IsAuthenticated(), IsSalesManager()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        campaign = serializer.save(created_by=self.request.user)
        if not campaign.owner:
            campaign.owner = self.request.user
            campaign.save(update_fields=["owner"])

        ActivityLog.objects.create(
            user=self.request.user,
            action=ActivityLog.Action.CREATED,
            entity_type="campaign",
            entity_id=str(campaign.id),
            description=f"Created campaign '{campaign.name}'",
        )

    @action(detail=True, methods=["patch"], url_path="action")
    def lifecycle_action(self, request, pk=None):
        """Perform a lifecycle action on a campaign (activate, pause, complete, cancel)."""
        campaign = self.get_object()
        serializer = CampaignActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        action_name = serializer.validated_data["action"]
        try:
            if action_name == "activate":
                campaign.activate()
            elif action_name == "pause":
                campaign.pause()
            elif action_name == "complete":
                campaign.complete()
            elif action_name == "cancel":
                campaign.status = Campaign.Status.CANCELLED
                campaign.save(update_fields=["status", "updated_at"])
        except ValueError as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_400_BAD_REQUEST
            )

        ActivityLog.objects.create(
            user=request.user,
            action=ActivityLog.Action.UPDATED,
            entity_type="campaign",
            entity_id=str(campaign.id),
            description=f"Campaign '{campaign.name}' {action_name}d",
        )

        return Response(CampaignDetailSerializer(campaign).data)

    @action(detail=True, methods=["post"], url_path="launch")
    def launch(self, request, pk=None):
        """Launch a campaign: populate recipients from segment and begin sending."""
        campaign = self.get_object()

        if campaign.status not in (Campaign.Status.DRAFT, Campaign.Status.SCHEDULED):
            return Response(
                {"error": "Campaign must be in draft or scheduled status to launch."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not campaign.segment:
            return Response(
                {"error": "Campaign has no target segment assigned."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        recipient_count = CampaignService.populate_recipients(campaign)
        campaign.activate()

        ActivityLog.objects.create(
            user=request.user,
            action=ActivityLog.Action.UPDATED,
            entity_type="campaign",
            entity_id=str(campaign.id),
            description=f"Launched campaign '{campaign.name}' to {recipient_count} recipients",
        )

        return Response(
            {
                "message": f"Campaign launched with {recipient_count} recipients.",
                "campaign_id": str(campaign.id),
                "recipient_count": recipient_count,
            },
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=True, methods=["get"], url_path="recipients")
    def recipients(self, request, pk=None):
        """List all recipients and their delivery status for a campaign."""
        campaign = self.get_object()
        recipients = campaign.recipients.select_related("contact").all()

        status_filter = request.query_params.get("status")
        if status_filter:
            recipients = recipients.filter(status=status_filter)

        serializer = CampaignRecipientSerializer(recipients, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="stats")
    def stats(self, request, pk=None):
        """Get detailed performance statistics for a campaign."""
        campaign = self.get_object()
        return Response(CampaignService.get_campaign_stats(campaign))
