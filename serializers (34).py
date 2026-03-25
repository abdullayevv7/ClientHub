"""
Views for the emails app: templates, campaigns, sending, and logs.
"""

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.activities.models import ActivityLog
from utils.permissions import IsSalesManager

from .models import EmailCampaign, EmailLog, EmailTemplate
from .serializers import (
    EmailCampaignCreateSerializer,
    EmailCampaignDetailSerializer,
    EmailCampaignListSerializer,
    EmailLogSerializer,
    EmailTemplateSerializer,
    SendEmailSerializer,
)
from .services import EmailService
from .tasks import execute_campaign_async, send_email_async


class EmailTemplateViewSet(viewsets.ModelViewSet):
    """
    CRUD for email templates.

    GET    /api/emails/templates/         - List templates
    POST   /api/emails/templates/         - Create template
    GET    /api/emails/templates/{id}/    - Retrieve template
    PUT    /api/emails/templates/{id}/    - Update template
    DELETE /api/emails/templates/{id}/    - Delete template
    """

    queryset = EmailTemplate.objects.all()
    serializer_class = EmailTemplateSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["category", "is_active"]
    search_fields = ["name", "subject"]
    ordering_fields = ["name", "category", "created_at"]

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [permissions.IsAuthenticated(), IsSalesManager()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["post"], url_path="preview")
    def preview(self, request, pk=None):
        """Preview a template with sample data."""
        template = self.get_object()
        sample_context = {
            "contact_name": "John Doe",
            "contact_first": "John",
            "contact_last": "Doe",
            "contact_email": "john@example.com",
            "company_name": "Acme Corp",
            "deal_value": "$50,000.00",
            "deal_title": "Enterprise License",
            "sender_name": request.user.get_full_name(),
            "current_date": "January 15, 2025",
        }
        context = {**sample_context, **request.data.get("context", {})}
        subject, body_html, body_text = EmailService.render_template(template, context)
        return Response(
            {
                "subject": subject,
                "body_html": body_html,
                "body_text": body_text,
            }
        )


class SendEmailView(APIView):
    """
    Send a single email (direct or template-based).

    POST /api/emails/send/
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = SendEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        to_email = data["to_email"]
        contact_id = data.get("contact_id")
        template_id = data.get("template_id")

        contact = None
        if contact_id:
            from apps.contacts.models import Contact

            try:
                contact = Contact.objects.get(id=contact_id)
            except Contact.DoesNotExist:
                return Response(
                    {"error": "Contact not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        if template_id:
            # Send via template
            context = EmailService.build_context_for_contact(
                contact, sender=request.user
            ) if contact else {}
            log = EmailService.send_template_email(
                template_id=template_id,
                to_email=to_email,
                context=context,
                sender=request.user,
                contact=contact,
            )
        else:
            # Send direct email
            log = EmailService.send_email(
                to_email=to_email,
                subject=data["subject"],
                body_html=data["body_html"],
                body_text=data.get("body_text", ""),
                sender=request.user,
                contact=contact,
            )

        ActivityLog.objects.create(
            user=request.user,
            action=ActivityLog.Action.EMAIL_SENT,
            entity_type="email",
            entity_id=str(log.id),
            description=f"Sent email to {to_email}",
        )

        return Response(
            EmailLogSerializer(log).data,
            status=status.HTTP_201_CREATED,
        )


class EmailCampaignViewSet(viewsets.ModelViewSet):
    """
    CRUD and execution for email campaigns.

    GET    /api/emails/campaigns/              - List campaigns
    POST   /api/emails/campaigns/              - Create campaign
    GET    /api/emails/campaigns/{id}/         - Retrieve campaign
    PUT    /api/emails/campaigns/{id}/         - Update campaign
    DELETE /api/emails/campaigns/{id}/         - Delete campaign
    POST   /api/emails/campaigns/{id}/send/    - Execute campaign
    """

    permission_classes = [permissions.IsAuthenticated, IsSalesManager]
    filterset_fields = ["status"]
    search_fields = ["name"]
    ordering_fields = ["name", "status", "created_at", "sent_at"]

    def get_queryset(self):
        return EmailCampaign.objects.select_related("template", "created_by").all()

    def get_serializer_class(self):
        if self.action == "list":
            return EmailCampaignListSerializer
        if self.action == "create":
            return EmailCampaignCreateSerializer
        return EmailCampaignDetailSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["post"], url_path="send")
    def send_campaign(self, request, pk=None):
        """Execute a campaign (send emails to all recipients)."""
        campaign = self.get_object()

        if campaign.status not in (
            EmailCampaign.Status.DRAFT,
            EmailCampaign.Status.SCHEDULED,
        ):
            return Response(
                {"error": "Campaign has already been sent or cancelled."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not campaign.template:
            return Response(
                {"error": "Campaign has no template assigned."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if campaign.recipients.count() == 0:
            return Response(
                {"error": "Campaign has no recipients."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Execute asynchronously via Celery
        execute_campaign_async.delay(str(campaign.id))

        ActivityLog.objects.create(
            user=request.user,
            action=ActivityLog.Action.CAMPAIGN_SENT,
            entity_type="campaign",
            entity_id=str(campaign.id),
            description=f"Launched campaign '{campaign.name}'",
        )

        return Response(
            {
                "message": f"Campaign '{campaign.name}' is being sent to {campaign.recipients.count()} recipients.",
                "campaign_id": str(campaign.id),
            },
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=True, methods=["get"], url_path="logs")
    def logs(self, request, pk=None):
        """View send logs for a campaign."""
        campaign = self.get_object()
        logs = EmailLog.objects.filter(campaign=campaign).select_related("contact")
        serializer = EmailLogSerializer(logs, many=True)
        return Response(serializer.data)


class EmailLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only access to email send logs.

    GET /api/emails/logs/         - List all email logs
    GET /api/emails/logs/{id}/    - Retrieve a specific log
    """

    serializer_class = EmailLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["status", "campaign", "contact"]
    search_fields = ["to_email", "subject"]
    ordering_fields = ["created_at", "sent_at", "status"]

    def get_queryset(self):
        user = self.request.user
        queryset = EmailLog.objects.select_related("contact", "sent_by", "campaign")

        if user.role == User.Role.ADMIN:
            return queryset
        return queryset.filter(sent_by=user)
