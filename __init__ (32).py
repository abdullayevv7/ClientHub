"""
Celery tasks for asynchronous email sending.
"""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def send_email_async(self, to_email, subject, body_html, body_text="",
                     sender_id=None, contact_id=None, campaign_id=None):
    """
    Send a single email asynchronously via Celery.
    """
    from apps.accounts.models import User
    from apps.contacts.models import Contact

    from .models import EmailCampaign
    from .services import EmailService

    try:
        sender = User.objects.get(id=sender_id) if sender_id else None
        contact = Contact.objects.get(id=contact_id) if contact_id else None
        campaign = EmailCampaign.objects.get(id=campaign_id) if campaign_id else None

        log = EmailService.send_email(
            to_email=to_email,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
            sender=sender,
            contact=contact,
            campaign=campaign,
        )
        return str(log.id)

    except Exception as exc:
        logger.error("Async email send failed: %s", str(exc))
        self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def send_template_email_async(self, template_id, to_email, context=None,
                               sender_id=None, contact_id=None):
    """
    Send a template-based email asynchronously via Celery.
    """
    from apps.accounts.models import User
    from apps.contacts.models import Contact

    from .services import EmailService

    try:
        sender = User.objects.get(id=sender_id) if sender_id else None
        contact = Contact.objects.get(id=contact_id) if contact_id else None

        log = EmailService.send_template_email(
            template_id=template_id,
            to_email=to_email,
            context=context,
            sender=sender,
            contact=contact,
        )
        return str(log.id)

    except Exception as exc:
        logger.error("Async template email send failed: %s", str(exc))
        self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=300)
def execute_campaign_async(self, campaign_id):
    """
    Execute a full email campaign asynchronously.
    """
    from .models import EmailCampaign
    from .services import EmailService

    try:
        campaign = EmailCampaign.objects.get(id=campaign_id)
        EmailService.send_campaign(campaign)
        logger.info("Campaign '%s' executed successfully", campaign.name)
        return f"Campaign {campaign.name} sent successfully"

    except EmailCampaign.DoesNotExist:
        logger.error("Campaign %s not found", campaign_id)
        return f"Campaign {campaign_id} not found"
    except Exception as exc:
        logger.error("Campaign execution failed: %s", str(exc))
        self.retry(exc=exc)


@shared_task
def send_scheduled_campaigns():
    """
    Check for campaigns scheduled to be sent and execute them.
    Run periodically via Celery Beat.
    """
    from django.utils import timezone

    from .models import EmailCampaign

    now = timezone.now()
    campaigns = EmailCampaign.objects.filter(
        status=EmailCampaign.Status.SCHEDULED,
        scheduled_at__lte=now,
    )

    for campaign in campaigns:
        execute_campaign_async.delay(str(campaign.id))
        logger.info("Triggered scheduled campaign: %s", campaign.name)

    return f"Triggered {campaigns.count()} scheduled campaigns"
