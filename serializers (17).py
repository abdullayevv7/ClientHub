"""
Contact and Company models for ClientHub CRM.
"""

import uuid

from django.conf import settings
from django.db import models


class ContactTag(models.Model):
    """Tags for categorizing contacts."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, unique=True, db_index=True)
    color = models.CharField(max_length=7, default="#3B82F6", help_text="Hex color code")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        db_table = "crm_contact_tags"

    def __str__(self):
        return self.name


class Company(models.Model):
    """
    Represents a company / organization that contacts belong to.
    """

    class Size(models.TextChoices):
        STARTUP = "startup", "Startup (1-10)"
        SMALL = "small", "Small (11-50)"
        MEDIUM = "medium", "Medium (51-200)"
        LARGE = "large", "Large (201-1000)"
        ENTERPRISE = "enterprise", "Enterprise (1000+)"

    class Industry(models.TextChoices):
        TECHNOLOGY = "technology", "Technology"
        HEALTHCARE = "healthcare", "Healthcare"
        FINANCE = "finance", "Finance"
        EDUCATION = "education", "Education"
        MANUFACTURING = "manufacturing", "Manufacturing"
        RETAIL = "retail", "Retail"
        REAL_ESTATE = "real_estate", "Real Estate"
        CONSULTING = "consulting", "Consulting"
        MEDIA = "media", "Media"
        NONPROFIT = "nonprofit", "Non-profit"
        GOVERNMENT = "government", "Government"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, db_index=True)
    website = models.URLField(blank=True, default="")
    industry = models.CharField(
        max_length=20, choices=Industry.choices, default=Industry.OTHER
    )
    size = models.CharField(
        max_length=20, choices=Size.choices, blank=True, default=""
    )
    annual_revenue = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True
    )
    phone = models.CharField(max_length=20, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    address_line1 = models.CharField(max_length=255, blank=True, default="")
    address_line2 = models.CharField(max_length=255, blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="")
    state = models.CharField(max_length=100, blank=True, default="")
    postal_code = models.CharField(max_length=20, blank=True, default="")
    country = models.CharField(max_length=100, blank=True, default="")
    description = models.TextField(blank=True, default="")
    logo = models.ImageField(upload_to="company_logos/", blank=True, null=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_companies",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_companies",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        db_table = "crm_companies"
        verbose_name_plural = "companies"

    def __str__(self):
        return self.name

    @property
    def contact_count(self):
        return self.contacts.count()

    @property
    def deal_count(self):
        return self.deals.count()

    @property
    def total_deal_value(self):
        from apps.deals.models import Deal

        return (
            self.deals.filter(stage__is_won=True)
            .aggregate(total=models.Sum("value"))
            .get("total")
            or 0
        )


class Contact(models.Model):
    """
    Represents an individual contact / lead in the CRM.
    """

    class Status(models.TextChoices):
        LEAD = "lead", "Lead"
        PROSPECT = "prospect", "Prospect"
        CUSTOMER = "customer", "Customer"
        CHURNED = "churned", "Churned"
        INACTIVE = "inactive", "Inactive"

    class Source(models.TextChoices):
        WEBSITE = "website", "Website"
        REFERRAL = "referral", "Referral"
        SOCIAL_MEDIA = "social_media", "Social Media"
        COLD_CALL = "cold_call", "Cold Call"
        EMAIL_CAMPAIGN = "email_campaign", "Email Campaign"
        TRADE_SHOW = "trade_show", "Trade Show"
        PARTNER = "partner", "Partner"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_name = models.CharField(max_length=150, db_index=True)
    last_name = models.CharField(max_length=150, db_index=True)
    email = models.EmailField(unique=True, db_index=True)
    phone = models.CharField(max_length=20, blank=True, default="")
    mobile = models.CharField(max_length=20, blank=True, default="")
    job_title = models.CharField(max_length=100, blank=True, default="")
    department = models.CharField(max_length=100, blank=True, default="")
    company = models.ForeignKey(
        Company,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contacts",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.LEAD,
        db_index=True,
    )
    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.OTHER,
    )
    lead_score = models.IntegerField(default=0, db_index=True)
    address_line1 = models.CharField(max_length=255, blank=True, default="")
    address_line2 = models.CharField(max_length=255, blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="")
    state = models.CharField(max_length=100, blank=True, default="")
    postal_code = models.CharField(max_length=20, blank=True, default="")
    country = models.CharField(max_length=100, blank=True, default="")
    description = models.TextField(blank=True, default="")
    avatar = models.ImageField(upload_to="contact_avatars/", blank=True, null=True)
    linkedin_url = models.URLField(blank=True, default="")
    twitter_handle = models.CharField(max_length=50, blank=True, default="")
    tags = models.ManyToManyField(ContactTag, blank=True, related_name="contacts")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_contacts",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_contacts",
    )
    last_contacted = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        db_table = "crm_contacts"

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def update_lead_score(self, points):
        """Add points to the lead score."""
        self.lead_score = max(0, self.lead_score + points)
        self.save(update_fields=["lead_score"])


class ContactNote(models.Model):
    """Notes attached to a contact."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contact = models.ForeignKey(
        Contact, on_delete=models.CASCADE, related_name="notes"
    )
    content = models.TextField()
    is_pinned = models.BooleanField(default=False)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="contact_notes",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_pinned", "-created_at"]
        db_table = "crm_contact_notes"

    def __str__(self):
        return f"Note on {self.contact} by {self.author}"
