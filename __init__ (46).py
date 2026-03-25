"""
Segment evaluation service for ClientHub CRM.
Translates segment rules into Django ORM queries to filter contacts.
"""

import logging
from datetime import datetime

from django.db.models import Q
from django.utils import timezone

from apps.contacts.models import Contact

from .models import Segment, SegmentRule

logger = logging.getLogger(__name__)


class SegmentService:
    """
    Service for evaluating segment rules against the contact database.
    Converts declarative rules into dynamic Django ORM queries.
    """

    # Maps operators to Django ORM lookups
    OPERATOR_MAP = {
        SegmentRule.Operator.EQUALS: "exact",
        SegmentRule.Operator.NOT_EQUALS: "exact",  # negated via ~Q
        SegmentRule.Operator.CONTAINS: "icontains",
        SegmentRule.Operator.NOT_CONTAINS: "icontains",  # negated
        SegmentRule.Operator.STARTS_WITH: "istartswith",
        SegmentRule.Operator.ENDS_WITH: "iendswith",
        SegmentRule.Operator.GREATER_THAN: "gt",
        SegmentRule.Operator.LESS_THAN: "lt",
        SegmentRule.Operator.GREATER_OR_EQUAL: "gte",
        SegmentRule.Operator.LESS_OR_EQUAL: "lte",
        SegmentRule.Operator.BEFORE: "lt",
        SegmentRule.Operator.AFTER: "gt",
        SegmentRule.Operator.IN_LIST: "in",
        SegmentRule.Operator.NOT_IN_LIST: "in",  # negated
    }

    # Operators that should negate the Q object
    NEGATED_OPERATORS = {
        SegmentRule.Operator.NOT_EQUALS,
        SegmentRule.Operator.NOT_CONTAINS,
        SegmentRule.Operator.NOT_IN_LIST,
        SegmentRule.Operator.EXCLUDES,
        SegmentRule.Operator.IS_EMPTY,
    }

    @classmethod
    def evaluate_segment(cls, segment):
        """
        Evaluate a segment and return the matching queryset of contacts.

        For static segments, returns the manually-assigned contacts.
        For dynamic segments, evaluates rules against the database.
        """
        if segment.segment_type == Segment.SegmentType.STATIC:
            qs = segment.static_contacts.all()
        else:
            qs = cls._evaluate_dynamic_rules(segment)

        # Update cached count
        count = qs.count()
        segment.contact_count = count
        segment.last_evaluated = timezone.now()
        segment.save(update_fields=["contact_count", "last_evaluated"])

        logger.info(
            "Evaluated segment '%s': %d contacts matched", segment.name, count
        )
        return qs

    @classmethod
    def _evaluate_dynamic_rules(cls, segment):
        """Build and execute a dynamic query from segment rules."""
        rules = segment.rules.all().order_by("order")

        if not rules.exists():
            return Contact.objects.none()

        q_objects = []
        for rule in rules:
            q = cls._rule_to_q(rule)
            if q is not None:
                q_objects.append(q)

        if not q_objects:
            return Contact.objects.none()

        # Combine Q objects based on match mode
        if segment.match_mode == Segment.MatchMode.ALL:
            combined_q = q_objects[0]
            for q in q_objects[1:]:
                combined_q &= q
        else:
            combined_q = q_objects[0]
            for q in q_objects[1:]:
                combined_q |= q

        return Contact.objects.filter(combined_q).distinct()

    @classmethod
    def _rule_to_q(cls, rule):
        """Convert a single SegmentRule into a Django Q object."""
        field = rule.field
        operator = rule.operator
        value = rule.value

        # Handle empty/not-empty operators
        if operator == SegmentRule.Operator.IS_EMPTY:
            return Q(**{f"{field}__exact": ""}) | Q(**{f"{field}__isnull": True})

        if operator == SegmentRule.Operator.IS_NOT_EMPTY:
            return ~(Q(**{f"{field}__exact": ""}) | Q(**{f"{field}__isnull": True}))

        # Handle M2M includes/excludes (e.g., tags)
        if operator == SegmentRule.Operator.INCLUDES:
            return Q(**{f"{field}__id": value})

        if operator == SegmentRule.Operator.EXCLUDES:
            return ~Q(**{f"{field}__id": value})

        # Handle BETWEEN operator
        if operator == SegmentRule.Operator.BETWEEN:
            parts = value.split("|")
            if len(parts) != 2:
                logger.warning(
                    "Invalid BETWEEN value for rule %s: '%s'", rule.id, value
                )
                return None
            low, high = parts[0].strip(), parts[1].strip()
            low = cls._coerce_value(field, low)
            high = cls._coerce_value(field, high)
            return Q(**{f"{field}__gte": low, f"{field}__lte": high})

        # Handle IN/NOT_IN operators
        if operator in (SegmentRule.Operator.IN_LIST, SegmentRule.Operator.NOT_IN_LIST):
            values = [v.strip() for v in value.split(",") if v.strip()]
            values = [cls._coerce_value(field, v) for v in values]
            q = Q(**{f"{field}__in": values})
            if operator in cls.NEGATED_OPERATORS:
                return ~q
            return q

        # Standard operators
        lookup = cls.OPERATOR_MAP.get(operator)
        if not lookup:
            logger.warning("Unsupported operator '%s' in rule %s", operator, rule.id)
            return None

        coerced_value = cls._coerce_value(field, value)
        q = Q(**{f"{field}__{lookup}": coerced_value})

        if operator in cls.NEGATED_OPERATORS:
            return ~q
        return q

    @classmethod
    def _coerce_value(cls, field, value):
        """
        Coerce a string value to the appropriate Python type based on the field.
        """
        numeric_fields = {"lead_score"}
        date_fields = {"created_at", "updated_at", "last_contacted"}

        if field in numeric_fields:
            try:
                return int(value)
            except (ValueError, TypeError):
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return value

        if field in date_fields:
            try:
                dt = datetime.fromisoformat(value)
                if dt.tzinfo is None:
                    dt = timezone.make_aware(dt)
                return dt
            except (ValueError, TypeError):
                return value

        return value

    @classmethod
    def preview_segment(cls, rules_data, match_mode="all"):
        """
        Preview a segment without saving -- takes raw rule data and returns
        the count of matching contacts and a sample of IDs.
        Used by the SegmentBuilder UI for live preview.
        """
        q_objects = []
        for rule_data in rules_data:
            rule = SegmentRule(
                field=rule_data.get("field", ""),
                operator=rule_data.get("operator", ""),
                value=rule_data.get("value", ""),
            )
            q = cls._rule_to_q(rule)
            if q is not None:
                q_objects.append(q)

        if not q_objects:
            return {"contact_count": 0, "sample_ids": []}

        if match_mode == "all":
            combined_q = q_objects[0]
            for q in q_objects[1:]:
                combined_q &= q
        else:
            combined_q = q_objects[0]
            for q in q_objects[1:]:
                combined_q |= q

        qs = Contact.objects.filter(combined_q).distinct()
        count = qs.count()
        sample_ids = list(qs.values_list("id", flat=True)[:10])

        return {
            "contact_count": count,
            "sample_ids": [str(uid) for uid in sample_ids],
        }
