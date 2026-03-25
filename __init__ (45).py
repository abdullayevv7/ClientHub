"""
Segment models for ClientHub CRM.
Segments define dynamic or static groups of contacts based on
composable filter rules. Used for campaign targeting, reporting, and analytics.
"""

import uuid

from django.conf import settings
from django.db import models


class Segment(models.Model):
    """
    A named segment of contacts, defined by a set of filter rules.
    Segments can be dynamic (evaluated at query time) or static (snapshot).
    """

    class SegmentType(models.TextChoices):
        DYNAMIC = "dynamic", "Dynamic"
        STATIC = "static", "Static"

    class MatchMode(models.TextChoices):
        ALL = "all", "Match All Rules (AND)"
        ANY = "any", "Match Any Rule (OR)"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, db_index=True)
    description = models.TextField(blank=True, default="")
    segment_type = models.CharField(
        max_length=10,
        choices=SegmentType.choices,
        default=SegmentType.DYNAMIC,
    )
    match_mode = models.CharField(
        max_length=5,
        choices=MatchMode.choices,
        default=MatchMode.ALL,
        help_text="Whether contacts must match ALL rules or ANY rule",
    )
    is_active = models.BooleanField(default=True)
    contact_count = models.PositiveIntegerField(
        default=0,
        help_text="Cached count of matching contacts (updated on evaluation)",
    )
    # Static segment members
    static_contacts = models.ManyToManyField(
        "contacts.Contact",
        blank=True,
        related_name="static_segments",
        help_text="Manually assigned contacts for static segments",
    )
    last_evaluated = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_segments",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        db_table = "crm_segments"

    def __str__(self):
        return f"{self.name} ({self.get_segment_type_display()})"

    @property
    def rule_count(self):
        return self.rules.count()


class SegmentRule(models.Model):
    """
    A single filter rule within a segment.
    Rules specify a field, operator, and value to match contacts against.

    Examples:
        field=status,    operator=equals,         value=customer
        field=lead_score, operator=greater_than,  value=50
        field=city,       operator=contains,      value=New York
        field=tags,       operator=includes,      value=<tag_id>
        field=created_at, operator=after,         value=2024-01-01
    """

    class Operator(models.TextChoices):
        EQUALS = "equals", "Equals"
        NOT_EQUALS = "not_equals", "Does Not Equal"
        CONTAINS = "contains", "Contains"
        NOT_CONTAINS = "not_contains", "Does Not Contain"
        STARTS_WITH = "starts_with", "Starts With"
        ENDS_WITH = "ends_with", "Ends With"
        GREATER_THAN = "greater_than", "Greater Than"
        LESS_THAN = "less_than", "Less Than"
        GREATER_OR_EQUAL = "gte", "Greater Than or Equal"
        LESS_OR_EQUAL = "lte", "Less Than or Equal"
        IS_EMPTY = "is_empty", "Is Empty"
        IS_NOT_EMPTY = "is_not_empty", "Is Not Empty"
        IN_LIST = "in", "In List"
        NOT_IN_LIST = "not_in", "Not In List"
        BEFORE = "before", "Before (date)"
        AFTER = "after", "After (date)"
        BETWEEN = "between", "Between"
        INCLUDES = "includes", "Includes (M2M)"
        EXCLUDES = "excludes", "Excludes (M2M)"

    # Allowed contact fields that rules can target
    class Field(models.TextChoices):
        STATUS = "status", "Status"
        SOURCE = "source", "Source"
        LEAD_SCORE = "lead_score", "Lead Score"
        FIRST_NAME = "first_name", "First Name"
        LAST_NAME = "last_name", "Last Name"
        EMAIL = "email", "Email"
        PHONE = "phone", "Phone"
        JOB_TITLE = "job_title", "Job Title"
        DEPARTMENT = "department", "Department"
        CITY = "city", "City"
        STATE = "state", "State"
        COUNTRY = "country", "Country"
        COMPANY_NAME = "company__name", "Company Name"
        COMPANY_INDUSTRY = "company__industry", "Company Industry"
        COMPANY_SIZE = "company__size", "Company Size"
        TAGS = "tags", "Tags"
        OWNER = "owner", "Owner"
        CREATED_AT = "created_at", "Created Date"
        UPDATED_AT = "updated_at", "Updated Date"
        LAST_CONTACTED = "last_contacted", "Last Contacted Date"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    segment = models.ForeignKey(
        Segment, on_delete=models.CASCADE, related_name="rules"
    )
    field = models.CharField(
        max_length=50,
        choices=Field.choices,
        help_text="The contact field to filter on",
    )
    operator = models.CharField(
        max_length=20,
        choices=Operator.choices,
        help_text="The comparison operator",
    )
    value = models.CharField(
        max_length=500,
        blank=True,
        default="",
        help_text="The value to compare against. For IN/NOT_IN, comma-separated. For BETWEEN, pipe-separated.",
    )
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["segment", "order"]
        db_table = "crm_segment_rules"

    def __str__(self):
        return f"{self.get_field_display()} {self.get_operator_display()} '{self.value}'"
