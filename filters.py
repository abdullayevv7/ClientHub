"""
Campaign service layer for ClientHub CRM.
Handles campaign execution logic, recipient population, and statistics aggregation.
"""

import logging
from collections import Counter

from django.db.models import Count, Q
from django.utils import timezone

from apps.contacts.models import Contact

from .models import Campaign, CampaignRecipient

logger = logging.getLogger(__name__)


class CampaignService:
    """
    Service for campaign execution, recipient management, and analytics.
    """

    @classmethod
    def populate_recipients(cls, campaign):
        """
        Build the recipient list from the campaign's target segment.
        Evaluates segment rules against the contact database and creates
        CampaignRecipient records for each matching contact.

        Returns the number of recipients added.
        """
        if not campaign.segment:
            raise ValueError("Campaign has no segment assigned.")

        from apps.segments.services import SegmentService

        contacts = SegmentService.evaluate_segment(campaign.segment)

        # Exclude contacts that have already unsubscribed or been added
        existing_contact_ids = set(
            campaign.recipients.values_list("contact_id", flat=True)
        )

        recipients_to_create = []
        for contact in contacts:
            if contact.id not in existing_contact_ids:
                recipients_to_create.append(
                    CampaignRecipient(
                        campaign=campaign,
                        contact=contact,
                        status=CampaignRecipient.DeliveryStatus.PENDING,
                    )
                )

        created = CampaignRecipient.objects.bulk_create(
            recipients_to_create, ignore_conflicts=True
        )

        campaign.total_targeted = campaign.recipients.count()
        campaign.save(update_fields=["total_targeted", "updated_at"])

        logger.info(
            "Populated %d recipients for campaign '%s'",
            len(created),
            campaign.name,
        )
        return len(created)

    @classmethod
    def get_campaign_stats(cls, campaign):
        """
        Compute detailed performance statistics for a campaign.
        Returns a dictionary of metrics suitable for dashboard rendering.
        """
        recipient_qs = campaign.recipients.all()
        total = recipient_qs.count()

        status_counts = dict(
            recipient_qs.values_list("status")
            .annotate(count=Count("id"))
            .values_list("status", "count")
        )

        sent = status_counts.get(CampaignRecipient.DeliveryStatus.SENT, 0)
        delivered = status_counts.get(CampaignRecipient.DeliveryStatus.DELIVERED, 0)
        opened = status_counts.get(CampaignRecipient.DeliveryStatus.OPENED, 0)
        clicked = status_counts.get(CampaignRecipient.DeliveryStatus.CLICKED, 0)
        converted = status_counts.get(CampaignRecipient.DeliveryStatus.CONVERTED, 0)
        bounced = status_counts.get(CampaignRecipient.DeliveryStatus.BOUNCED, 0)
        unsubscribed = status_counts.get(CampaignRecipient.DeliveryStatus.UNSUBSCRIBED, 0)
        failed = status_counts.get(CampaignRecipient.DeliveryStatus.FAILED, 0)
        pending = status_counts.get(CampaignRecipient.DeliveryStatus.PENDING, 0)

        # Aggregate opened/clicked include downstream statuses
        effective_opened = opened + clicked + converted
        effective_delivered = delivered + effective_opened + unsubscribed

        delivery_rate = (
            round(effective_delivered / (sent + delivered + effective_opened) * 100, 2)
            if (sent + delivered + effective_opened) > 0
            else 0
        )

        return {
            "campaign_id": str(campaign.id),
            "campaign_name": campaign.name,
            "status": campaign.status,
            "total_targeted": total,
            "pending": pending,
            "sent": sent,
            "delivered": effective_delivered,
            "opened": effective_opened,
            "clicked": clicked + converted,
            "converted": converted,
            "bounced": bounced,
            "unsubscribed": unsubscribed,
            "failed": failed,
            "delivery_rate": delivery_rate,
            "open_rate": (
                round(effective_opened / effective_delivered * 100, 2)
                if effective_delivered > 0
                else 0
            ),
            "click_rate": (
                round((clicked + converted) / effective_delivered * 100, 2)
                if effective_delivered > 0
                else 0
            ),
            "conversion_rate": (
                round(converted / effective_delivered * 100, 2)
                if effective_delivered > 0
                else 0
            ),
            "bounce_rate": (
                round(bounced / total * 100, 2) if total > 0 else 0
            ),
            "unsubscribe_rate": (
                round(unsubscribed / effective_delivered * 100, 2)
                if effective_delivered > 0
                else 0
            ),
            "budget": float(campaign.budget) if campaign.budget else None,
            "total_revenue": float(campaign.total_revenue),
            "roi": campaign.roi,
            "started_at": (
                campaign.actual_start.isoformat() if campaign.actual_start else None
            ),
            "ended_at": (
                campaign.actual_end.isoformat() if campaign.actual_end else None
            ),
        }

    @classmethod
    def update_campaign_counters(cls, campaign):
        """
        Recalculate denormalized counters on the campaign from recipient records.
        Should be called after batch status updates.
        """
        qs = campaign.recipients.all()
        counts = dict(
            qs.values_list("status")
            .annotate(count=Count("id"))
            .values_list("status", "count")
        )

        campaign.total_sent = sum(
            counts.get(s, 0)
            for s in [
                CampaignRecipient.DeliveryStatus.SENT,
                CampaignRecipient.DeliveryStatus.DELIVERED,
                CampaignRecipient.DeliveryStatus.OPENED,
                CampaignRecipient.DeliveryStatus.CLICKED,
                CampaignRecipient.DeliveryStatus.CONVERTED,
                CampaignRecipient.DeliveryStatus.UNSUBSCRIBED,
            ]
        )
        campaign.total_delivered = sum(
            counts.get(s, 0)
            for s in [
                CampaignRecipient.DeliveryStatus.DELIVERED,
                CampaignRecipient.DeliveryStatus.OPENED,
                CampaignRecipient.DeliveryStatus.CLICKED,
                CampaignRecipient.DeliveryStatus.CONVERTED,
                CampaignRecipient.DeliveryStatus.UNSUBSCRIBED,
            ]
        )
        campaign.total_opened = sum(
            counts.get(s, 0)
            for s in [
                CampaignRecipient.DeliveryStatus.OPENED,
                CampaignRecipient.DeliveryStatus.CLICKED,
                CampaignRecipient.DeliveryStatus.CONVERTED,
            ]
        )
        campaign.total_clicked = sum(
            counts.get(s, 0)
            for s in [
                CampaignRecipient.DeliveryStatus.CLICKED,
                CampaignRecipient.DeliveryStatus.CONVERTED,
            ]
        )
        campaign.total_converted = counts.get(
            CampaignRecipient.DeliveryStatus.CONVERTED, 0
        )
        campaign.total_bounced = counts.get(
            CampaignRecipient.DeliveryStatus.BOUNCED, 0
        )
        campaign.total_unsubscribed = counts.get(
            CampaignRecipient.DeliveryStatus.UNSUBSCRIBED, 0
        )
        campaign.save(
            update_fields=[
                "total_sent",
                "total_delivered",
                "total_opened",
                "total_clicked",
                "total_converted",
                "total_bounced",
                "total_unsubscribed",
                "updated_at",
            ]
        )

        logger.info("Updated counters for campaign '%s'", campaign.name)
