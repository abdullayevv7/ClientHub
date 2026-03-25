"""
Django filter classes for contacts and companies.
"""

import django_filters

from .models import Company, Contact


class ContactFilter(django_filters.FilterSet):
    """Advanced filtering for contacts."""

    name = django_filters.CharFilter(method="filter_name", label="Search by name")
    email = django_filters.CharFilter(lookup_expr="icontains")
    company = django_filters.UUIDFilter(field_name="company__id")
    company_name = django_filters.CharFilter(
        field_name="company__name", lookup_expr="icontains"
    )
    status = django_filters.ChoiceFilter(choices=Contact.Status.choices)
    source = django_filters.ChoiceFilter(choices=Contact.Source.choices)
    owner = django_filters.UUIDFilter(field_name="owner__id")
    tag = django_filters.UUIDFilter(field_name="tags__id")
    tag_name = django_filters.CharFilter(
        field_name="tags__name", lookup_expr="icontains"
    )
    lead_score_min = django_filters.NumberFilter(
        field_name="lead_score", lookup_expr="gte"
    )
    lead_score_max = django_filters.NumberFilter(
        field_name="lead_score", lookup_expr="lte"
    )
    city = django_filters.CharFilter(lookup_expr="icontains")
    country = django_filters.CharFilter(lookup_expr="icontains")
    created_after = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="gte"
    )
    created_before = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="lte"
    )
    last_contacted_after = django_filters.DateTimeFilter(
        field_name="last_contacted", lookup_expr="gte"
    )
    last_contacted_before = django_filters.DateTimeFilter(
        field_name="last_contacted", lookup_expr="lte"
    )

    class Meta:
        model = Contact
        fields = [
            "status",
            "source",
            "owner",
            "company",
        ]

    def filter_name(self, queryset, name, value):
        """Search by first name, last name, or full name."""
        return queryset.filter(
            models.Q(first_name__icontains=value)
            | models.Q(last_name__icontains=value)
        )


class CompanyFilter(django_filters.FilterSet):
    """Advanced filtering for companies."""

    name = django_filters.CharFilter(lookup_expr="icontains")
    industry = django_filters.ChoiceFilter(choices=Company.Industry.choices)
    size = django_filters.ChoiceFilter(choices=Company.Size.choices)
    owner = django_filters.UUIDFilter(field_name="owner__id")
    city = django_filters.CharFilter(lookup_expr="icontains")
    country = django_filters.CharFilter(lookup_expr="icontains")
    revenue_min = django_filters.NumberFilter(
        field_name="annual_revenue", lookup_expr="gte"
    )
    revenue_max = django_filters.NumberFilter(
        field_name="annual_revenue", lookup_expr="lte"
    )
    created_after = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="gte"
    )
    created_before = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="lte"
    )

    class Meta:
        model = Company
        fields = ["industry", "size", "owner"]
