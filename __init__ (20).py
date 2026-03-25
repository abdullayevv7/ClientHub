"""
Views for the contacts app: contacts, companies, tags, and notes.
"""

from django.db.models import Q
from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import User
from apps.activities.models import ActivityLog
from utils.permissions import IsOwnerOrAdmin, IsTeamMemberOrAdmin

from .filters import CompanyFilter, ContactFilter
from .models import Company, Contact, ContactNote, ContactTag
from .serializers import (
    CompanyDetailSerializer,
    CompanyListSerializer,
    ContactCreateUpdateSerializer,
    ContactDetailSerializer,
    ContactListSerializer,
    ContactNoteSerializer,
    ContactTagSerializer,
)


class ContactViewSet(viewsets.ModelViewSet):
    """
    CRUD for contacts with role-based filtering.

    GET    /api/contacts/              - List contacts
    POST   /api/contacts/              - Create a contact
    GET    /api/contacts/{id}/         - Retrieve a contact
    PUT    /api/contacts/{id}/         - Update a contact
    DELETE /api/contacts/{id}/         - Delete a contact
    """

    permission_classes = [permissions.IsAuthenticated]
    filterset_class = ContactFilter
    search_fields = ["first_name", "last_name", "email", "company__name", "job_title"]
    ordering_fields = [
        "first_name",
        "last_name",
        "email",
        "lead_score",
        "created_at",
        "last_contacted",
    ]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        queryset = Contact.objects.select_related("company", "owner", "created_by").prefetch_related(
            "tags"
        )

        if user.role == User.Role.ADMIN:
            return queryset
        elif user.role == User.Role.SALES_MANAGER and user.team:
            team_members = User.objects.filter(team=user.team)
            return queryset.filter(Q(owner__in=team_members) | Q(owner__isnull=True))
        elif user.role == User.Role.SUPPORT_AGENT:
            return queryset  # Read-only access to all contacts
        else:
            return queryset.filter(Q(owner=user) | Q(owner__isnull=True))

    def get_serializer_class(self):
        if self.action == "list":
            return ContactListSerializer
        if self.action in ("create", "update", "partial_update"):
            return ContactCreateUpdateSerializer
        return ContactDetailSerializer

    def perform_create(self, serializer):
        contact = serializer.save(created_by=self.request.user)
        if not contact.owner:
            contact.owner = self.request.user
            contact.save(update_fields=["owner"])

        ActivityLog.objects.create(
            user=self.request.user,
            action=ActivityLog.Action.CREATED,
            entity_type="contact",
            entity_id=str(contact.id),
            description=f"Created contact {contact.full_name}",
        )

    def perform_update(self, serializer):
        contact = serializer.save()
        ActivityLog.objects.create(
            user=self.request.user,
            action=ActivityLog.Action.UPDATED,
            entity_type="contact",
            entity_id=str(contact.id),
            description=f"Updated contact {contact.full_name}",
        )

    def perform_destroy(self, instance):
        ActivityLog.objects.create(
            user=self.request.user,
            action=ActivityLog.Action.DELETED,
            entity_type="contact",
            entity_id=str(instance.id),
            description=f"Deleted contact {instance.full_name}",
        )
        instance.delete()

    @action(detail=True, methods=["get", "post"], url_path="notes")
    def notes(self, request, pk=None):
        """List or create notes for a contact."""
        contact = self.get_object()

        if request.method == "GET":
            notes = ContactNote.objects.filter(contact=contact).select_related("author")
            serializer = ContactNoteSerializer(notes, many=True)
            return Response(serializer.data)

        serializer = ContactNoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(contact=contact, author=request.user)

        # Update lead score for interaction
        contact.update_lead_score(2)

        ActivityLog.objects.create(
            user=request.user,
            action=ActivityLog.Action.NOTE_ADDED,
            entity_type="contact",
            entity_id=str(contact.id),
            description=f"Added note to contact {contact.full_name}",
        )

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="update-score")
    def update_score(self, request, pk=None):
        """Manually adjust a contact's lead score."""
        contact = self.get_object()
        points = request.data.get("points", 0)
        try:
            points = int(points)
        except (TypeError, ValueError):
            return Response(
                {"error": "Points must be an integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        contact.update_lead_score(points)
        return Response(
            {"lead_score": contact.lead_score},
            status=status.HTTP_200_OK,
        )


class CompanyViewSet(viewsets.ModelViewSet):
    """
    CRUD for companies.

    GET    /api/contacts/companies/            - List companies
    POST   /api/contacts/companies/            - Create a company
    GET    /api/contacts/companies/{id}/       - Retrieve a company
    PUT    /api/contacts/companies/{id}/       - Update a company
    DELETE /api/contacts/companies/{id}/       - Delete a company
    """

    permission_classes = [permissions.IsAuthenticated]
    filterset_class = CompanyFilter
    search_fields = ["name", "email", "city", "country"]
    ordering_fields = ["name", "industry", "created_at", "annual_revenue"]
    ordering = ["name"]

    def get_queryset(self):
        user = self.request.user
        queryset = Company.objects.select_related("owner", "created_by")

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
            return CompanyListSerializer
        return CompanyDetailSerializer

    def perform_create(self, serializer):
        company = serializer.save(created_by=self.request.user)
        if not company.owner:
            company.owner = self.request.user
            company.save(update_fields=["owner"])

        ActivityLog.objects.create(
            user=self.request.user,
            action=ActivityLog.Action.CREATED,
            entity_type="company",
            entity_id=str(company.id),
            description=f"Created company {company.name}",
        )

    @action(detail=True, methods=["get"], url_path="contacts")
    def contacts(self, request, pk=None):
        """List contacts belonging to a company."""
        company = self.get_object()
        contacts = Contact.objects.filter(company=company).select_related("owner")
        serializer = ContactListSerializer(contacts, many=True)
        return Response(serializer.data)


class ContactTagViewSet(viewsets.ModelViewSet):
    """
    CRUD for contact tags.

    GET    /api/contacts/tags/     - List tags
    POST   /api/contacts/tags/     - Create a tag
    DELETE /api/contacts/tags/{id}/ - Delete a tag
    """

    queryset = ContactTag.objects.all()
    serializer_class = ContactTagSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["name"]
    pagination_class = None  # Tags are typically a small list
