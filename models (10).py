"""
Tests for the campaigns app.
"""

from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import Team, User
from apps.contacts.models import Contact
from apps.segments.models import Segment

from .models import Campaign, CampaignRecipient, CampaignTag
from .services import CampaignService


class CampaignModelTests(TestCase):
    """Unit tests for Campaign model."""

    def setUp(self):
        self.team = Team.objects.create(name="Sales Team")
        self.user = User.objects.create_user(
            email="manager@test.com",
            password="testpass123",
            first_name="Test",
            last_name="Manager",
            role=User.Role.SALES_MANAGER,
            team=self.team,
        )

    def test_create_campaign(self):
        campaign = Campaign.objects.create(
            name="Spring Launch",
            description="Spring product launch email campaign",
            channel=Campaign.Channel.EMAIL,
            campaign_type=Campaign.CampaignType.ONE_TIME,
            owner=self.user,
            created_by=self.user,
        )
        self.assertEqual(campaign.status, Campaign.Status.DRAFT)
        self.assertEqual(campaign.channel, Campaign.Channel.EMAIL)
        self.assertEqual(str(campaign), "Spring Launch")

    def test_open_rate_calculation(self):
        campaign = Campaign.objects.create(
            name="Test Rates",
            total_delivered=200,
            total_opened=50,
            total_clicked=20,
            total_sent=210,
            total_bounced=10,
            created_by=self.user,
        )
        self.assertEqual(campaign.open_rate, 25.0)
        self.assertEqual(campaign.click_rate, 10.0)

    def test_open_rate_zero_delivered(self):
        campaign = Campaign.objects.create(
            name="No Delivery",
            total_delivered=0,
            created_by=self.user,
        )
        self.assertEqual(campaign.open_rate, 0)
        self.assertEqual(campaign.click_rate, 0)
        self.assertEqual(campaign.conversion_rate, 0)

    def test_roi_calculation(self):
        campaign = Campaign.objects.create(
            name="ROI Test",
            budget=Decimal("1000.00"),
            total_revenue=Decimal("3000.00"),
            created_by=self.user,
        )
        self.assertEqual(campaign.roi, 200.0)

    def test_roi_no_budget(self):
        campaign = Campaign.objects.create(
            name="No Budget",
            total_revenue=Decimal("500.00"),
            created_by=self.user,
        )
        self.assertIsNone(campaign.roi)

    def test_activate_from_draft(self):
        campaign = Campaign.objects.create(
            name="Draft Campaign",
            status=Campaign.Status.DRAFT,
            created_by=self.user,
        )
        campaign.activate()
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, Campaign.Status.ACTIVE)
        self.assertIsNotNone(campaign.actual_start)

    def test_activate_from_invalid_status(self):
        campaign = Campaign.objects.create(
            name="Completed Campaign",
            status=Campaign.Status.COMPLETED,
            created_by=self.user,
        )
        with self.assertRaises(ValueError):
            campaign.activate()

    def test_pause_active_campaign(self):
        campaign = Campaign.objects.create(
            name="Active Campaign",
            status=Campaign.Status.ACTIVE,
            created_by=self.user,
        )
        campaign.pause()
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, Campaign.Status.PAUSED)

    def test_complete_campaign(self):
        campaign = Campaign.objects.create(
            name="Active Campaign",
            status=Campaign.Status.ACTIVE,
            created_by=self.user,
        )
        campaign.complete()
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, Campaign.Status.COMPLETED)
        self.assertIsNotNone(campaign.actual_end)


class CampaignRecipientModelTests(TestCase):
    """Unit tests for CampaignRecipient model."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="user@test.com",
            password="testpass123",
            first_name="Test",
            last_name="User",
        )
        self.contact = Contact.objects.create(
            first_name="Jane",
            last_name="Doe",
            email="jane@example.com",
            created_by=self.user,
        )
        self.campaign = Campaign.objects.create(
            name="Test Campaign",
            created_by=self.user,
        )

    def test_create_recipient(self):
        recipient = CampaignRecipient.objects.create(
            campaign=self.campaign,
            contact=self.contact,
        )
        self.assertEqual(
            recipient.status, CampaignRecipient.DeliveryStatus.PENDING
        )

    def test_unique_together_constraint(self):
        CampaignRecipient.objects.create(
            campaign=self.campaign,
            contact=self.contact,
        )
        with self.assertRaises(Exception):
            CampaignRecipient.objects.create(
                campaign=self.campaign,
                contact=self.contact,
            )


class CampaignAPITests(APITestCase):
    """Integration tests for the Campaign API endpoints."""

    def setUp(self):
        self.team = Team.objects.create(name="Marketing")
        self.admin = User.objects.create_user(
            email="admin@test.com",
            password="testpass123",
            first_name="Admin",
            last_name="User",
            role=User.Role.ADMIN,
        )
        self.manager = User.objects.create_user(
            email="manager@test.com",
            password="testpass123",
            first_name="Sales",
            last_name="Manager",
            role=User.Role.SALES_MANAGER,
            team=self.team,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def test_list_campaigns(self):
        Campaign.objects.create(name="Campaign A", created_by=self.admin)
        Campaign.objects.create(name="Campaign B", created_by=self.admin)

        response = self.client.get("/api/campaigns/campaigns/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_campaign(self):
        data = {
            "name": "New Campaign",
            "description": "Test campaign",
            "channel": "email",
            "campaign_type": "one_time",
            "content_html": "<h1>Hello</h1>",
        }
        response = self.client.post("/api/campaigns/campaigns/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Campaign.objects.count(), 1)
        self.assertEqual(Campaign.objects.first().created_by, self.admin)

    def test_retrieve_campaign(self):
        campaign = Campaign.objects.create(
            name="Detail Campaign",
            created_by=self.admin,
            content_html="<p>Content</p>",
        )
        response = self.client.get(f"/api/campaigns/campaigns/{campaign.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Detail Campaign")

    def test_lifecycle_action_activate(self):
        campaign = Campaign.objects.create(
            name="Draft Campaign",
            status=Campaign.Status.DRAFT,
            created_by=self.admin,
        )
        response = self.client.patch(
            f"/api/campaigns/campaigns/{campaign.id}/action/",
            {"action": "activate"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, Campaign.Status.ACTIVE)

    def test_sales_rep_cannot_create(self):
        rep = User.objects.create_user(
            email="rep@test.com",
            password="testpass123",
            first_name="Sales",
            last_name="Rep",
            role=User.Role.SALES_REP,
        )
        self.client.force_authenticate(user=rep)
        response = self.client.post(
            "/api/campaigns/campaigns/",
            {"name": "Unauthorized", "content_html": "<p>X</p>"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_tag_crud(self):
        response = self.client.post(
            "/api/campaigns/tags/",
            {"name": "Product Launch", "color": "#FF5733"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        tag_id = response.data["id"]

        response = self.client.get(f"/api/campaigns/tags/{tag_id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Product Launch")
