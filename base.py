"""
Tests for the segments app.
"""

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import Team, User
from apps.contacts.models import Company, Contact, ContactTag

from .models import Segment, SegmentRule
from .services import SegmentService


class SegmentModelTests(TestCase):
    """Unit tests for Segment and SegmentRule models."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="tester@test.com",
            password="testpass123",
            first_name="Test",
            last_name="User",
            role=User.Role.ADMIN,
        )

    def test_create_dynamic_segment(self):
        segment = Segment.objects.create(
            name="High Value Leads",
            segment_type=Segment.SegmentType.DYNAMIC,
            match_mode=Segment.MatchMode.ALL,
            created_by=self.user,
        )
        self.assertEqual(segment.segment_type, "dynamic")
        self.assertEqual(segment.rule_count, 0)

    def test_create_segment_with_rules(self):
        segment = Segment.objects.create(
            name="Enterprise Customers",
            created_by=self.user,
        )
        SegmentRule.objects.create(
            segment=segment,
            field=SegmentRule.Field.STATUS,
            operator=SegmentRule.Operator.EQUALS,
            value="customer",
            order=0,
        )
        SegmentRule.objects.create(
            segment=segment,
            field=SegmentRule.Field.COMPANY_SIZE,
            operator=SegmentRule.Operator.EQUALS,
            value="enterprise",
            order=1,
        )
        self.assertEqual(segment.rule_count, 2)

    def test_segment_str(self):
        segment = Segment.objects.create(
            name="Test Segment",
            segment_type=Segment.SegmentType.STATIC,
            created_by=self.user,
        )
        self.assertIn("Static", str(segment))

    def test_rule_str(self):
        segment = Segment.objects.create(name="Test", created_by=self.user)
        rule = SegmentRule.objects.create(
            segment=segment,
            field=SegmentRule.Field.LEAD_SCORE,
            operator=SegmentRule.Operator.GREATER_THAN,
            value="50",
        )
        self.assertIn("Lead Score", str(rule))
        self.assertIn("Greater Than", str(rule))


class SegmentServiceTests(TestCase):
    """Tests for SegmentService evaluation logic."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="service@test.com",
            password="testpass123",
            first_name="Service",
            last_name="User",
            role=User.Role.ADMIN,
        )
        self.company = Company.objects.create(
            name="Acme Corp",
            industry=Company.Industry.TECHNOLOGY,
            size=Company.Size.ENTERPRISE,
            created_by=self.user,
        )
        self.contact_a = Contact.objects.create(
            first_name="Alice",
            last_name="Smith",
            email="alice@acme.com",
            status=Contact.Status.CUSTOMER,
            lead_score=80,
            company=self.company,
            city="New York",
            created_by=self.user,
        )
        self.contact_b = Contact.objects.create(
            first_name="Bob",
            last_name="Jones",
            email="bob@example.com",
            status=Contact.Status.LEAD,
            lead_score=20,
            city="London",
            created_by=self.user,
        )
        self.contact_c = Contact.objects.create(
            first_name="Charlie",
            last_name="Brown",
            email="charlie@acme.com",
            status=Contact.Status.CUSTOMER,
            lead_score=60,
            company=self.company,
            city="New York",
            created_by=self.user,
        )

    def test_evaluate_equals_rule(self):
        segment = Segment.objects.create(name="Customers", created_by=self.user)
        SegmentRule.objects.create(
            segment=segment,
            field="status",
            operator="equals",
            value="customer",
        )
        contacts = SegmentService.evaluate_segment(segment)
        self.assertEqual(contacts.count(), 2)
        self.assertIn(self.contact_a, contacts)
        self.assertIn(self.contact_c, contacts)

    def test_evaluate_greater_than_rule(self):
        segment = Segment.objects.create(name="High Score", created_by=self.user)
        SegmentRule.objects.create(
            segment=segment,
            field="lead_score",
            operator="greater_than",
            value="50",
        )
        contacts = SegmentService.evaluate_segment(segment)
        self.assertEqual(contacts.count(), 2)

    def test_evaluate_contains_rule(self):
        segment = Segment.objects.create(name="NYC", created_by=self.user)
        SegmentRule.objects.create(
            segment=segment,
            field="city",
            operator="contains",
            value="New York",
        )
        contacts = SegmentService.evaluate_segment(segment)
        self.assertEqual(contacts.count(), 2)

    def test_evaluate_and_mode(self):
        segment = Segment.objects.create(
            name="NYC Customers",
            match_mode=Segment.MatchMode.ALL,
            created_by=self.user,
        )
        SegmentRule.objects.create(
            segment=segment, field="status", operator="equals", value="customer"
        )
        SegmentRule.objects.create(
            segment=segment,
            field="lead_score",
            operator="greater_than",
            value="70",
        )
        contacts = SegmentService.evaluate_segment(segment)
        self.assertEqual(contacts.count(), 1)
        self.assertIn(self.contact_a, contacts)

    def test_evaluate_or_mode(self):
        segment = Segment.objects.create(
            name="Leads or High Score",
            match_mode=Segment.MatchMode.ANY,
            created_by=self.user,
        )
        SegmentRule.objects.create(
            segment=segment, field="status", operator="equals", value="lead"
        )
        SegmentRule.objects.create(
            segment=segment,
            field="lead_score",
            operator="greater_than",
            value="70",
        )
        contacts = SegmentService.evaluate_segment(segment)
        self.assertEqual(contacts.count(), 2)

    def test_evaluate_static_segment(self):
        segment = Segment.objects.create(
            name="Static Group",
            segment_type=Segment.SegmentType.STATIC,
            created_by=self.user,
        )
        segment.static_contacts.add(self.contact_a, self.contact_b)
        contacts = SegmentService.evaluate_segment(segment)
        self.assertEqual(contacts.count(), 2)

    def test_evaluate_empty_rules(self):
        segment = Segment.objects.create(name="Empty", created_by=self.user)
        contacts = SegmentService.evaluate_segment(segment)
        self.assertEqual(contacts.count(), 0)

    def test_preview_segment(self):
        result = SegmentService.preview_segment(
            [{"field": "status", "operator": "equals", "value": "customer"}],
            match_mode="all",
        )
        self.assertEqual(result["contact_count"], 2)
        self.assertTrue(len(result["sample_ids"]) <= 10)


class SegmentAPITests(APITestCase):
    """Integration tests for the Segment API."""

    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@test.com",
            password="testpass123",
            first_name="Admin",
            last_name="User",
            role=User.Role.ADMIN,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def test_create_segment_with_rules(self):
        data = {
            "name": "Active Leads",
            "segment_type": "dynamic",
            "match_mode": "all",
            "rules": [
                {"field": "status", "operator": "equals", "value": "lead"},
                {"field": "lead_score", "operator": "greater_than", "value": "30"},
            ],
        }
        response = self.client.post(
            "/api/segments/segments/", data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        segment = Segment.objects.get(name="Active Leads")
        self.assertEqual(segment.rules.count(), 2)

    def test_list_segments(self):
        Segment.objects.create(name="Segment A", created_by=self.admin)
        Segment.objects.create(name="Segment B", created_by=self.admin)
        response = self.client.get("/api/segments/segments/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
