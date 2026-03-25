"""
Email service layer: handles template rendering, variable interpolation,
and sending logic.
"""

import logging
import re

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone

from apps.contacts.models import Contact

from .models import EmailLog, EmailTemplate

logger = logging.getLogger(__name__)


class EmailService:
    """
    Service for sending emails with template support and variable interpolation.

    Supported template variables:
        {{contact_name}}    - Contact's full name
        {{contact_first}}   - Contact's first name
        {{contact_last}}    - Contact's last name
        {{contact_email}}   - Contact's email
        {{company_name}}    - Contact's company name
        {{deal_value}}      - Associated deal value
        {{deal_title}}      - Associated deal title
        {{sender_name}}     - Sender's full name
        {{current_date}}    - Today's date
    """

    VARIABLE_PATTERN = re.compile(r"\{\{(\w+)\}\}")

    @classmethod
    def render_template(cls, template, context=None):
        """
        Render a template by replacing {{variable}} placeholders with context values.
        """
        context = context or {}
        subject = cls._interpolate(template.subject, context)
        body_html = cls._interpolate(template.body_html, context)
        body_text = cls._interpolate(template.body_text, context) if template.body_text else ""
        return subject, body_html, body_text

    @classmethod
    def _interpolate(cls, text, context):
        """Replace {{variable}} with values from context dict."""
        def replacer(match):
            key = match.group(1)
            return str(context.get(key, match.group(0)))

        return cls.VARIABLE_PATTERN.sub(replacer, text)

    @classmethod
    def build_context_for_contact(cls, contact, sender=None, deal=None):
        """Build a template variable context from a contact object."""
        context = {
            "contact_name": contact.full_name,
            "contact_first": contact.first_name,
            "contact_last": contact.last_name,
            "contact_email": contact.email,
            "company_name": contact.company.name if contact.company else "",
            "current_date": timezone.now().strftime("%B %d, %Y"),
        }
        if sender:
            context["sender_name"] = sender.get_full_name()
        if deal:
            context["deal_value"] = f"${deal.value:,.2f}"
            context["deal_title"] = deal.title
        return context

    @classmethod
    def send_email(cls, to_email, subject, body_html, body_text="", sender=None,
                   contact=None, campaign=None):
        """
        Send a single email and log it.

        Returns the EmailLog instance.
        """
        log = EmailLog.objects.create(
            campaign=campaign,
            contact=contact,
            to_email=to_email,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
            status=EmailLog.Status.PENDING,
            sent_by=sender,
        )

        try:
            msg = EmailMultiAlternatives(
                subject=subject,
                body=body_text or subject,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[to_email],
            )
            if body_html:
                msg.attach_alternative(body_html, "text/html")

            msg.send(fail_silently=False)

            log.status = EmailLog.Status.SENT
            log.sent_at = timezone.now()
            log.save(update_fields=["status", "sent_at"])

            # Update contact's last_contacted
            if contact:
                contact.last_contacted = timezone.now()
                contact.save(update_fields=["last_contacted"])
                contact.update_lead_score(5)

            logger.info("Email sent to %s: %s", to_email, subject)

        except Exception as exc:
            log.status = EmailLog.Status.FAILED
            log.error_message = str(exc)
            log.save(update_fields=["status", "error_message"])
            logger.error("Failed to send email to %s: %s", to_email, str(exc))

        return log

    @classmethod
    def send_template_email(cls, template_id, to_email, context=None,
                            sender=None, contact=None, campaign=None):
        """
        Send an email using a template with variable interpolation.
        """
        try:
            template = EmailTemplate.objects.get(id=template_id, is_active=True)
        except EmailTemplate.DoesNotExist:
            raise ValueError(f"Email template with id {template_id} not found or inactive.")

        # Build context from contact if available
        if contact and not context:
            context = cls.build_context_for_contact(contact, sender=sender)

        subject, body_html, body_text = cls.render_template(template, context)

        return cls.send_email(
            to_email=to_email,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
            sender=sender,
            contact=contact,
            campaign=campaign,
        )

    @classmethod
    def send_campaign(cls, campaign):
        """
        Execute a campaign: send the template to all recipients.
        Updates campaign statistics.
        """
        from .models import EmailCampaign

        if campaign.status not in (EmailCampaign.Status.DRAFT, EmailCampaign.Status.SCHEDULED):
            raise ValueError("Campaign has already been sent or cancelled.")

        if not campaign.template:
            raise ValueError("Campaign has no template assigned.")

        campaign.status = EmailCampaign.Status.SENDING
        campaign.save(update_fields=["status"])

        recipients = campaign.recipients.all()
        sent_count = 0
        bounce_count = 0

        for contact in recipients:
            context = cls.build_context_for_contact(
                contact, sender=campaign.created_by
            )
            log = cls.send_template_email(
                template_id=campaign.template.id,
                to_email=contact.email,
                context=context,
                sender=campaign.created_by,
                contact=contact,
                campaign=campaign,
            )

            if log.status == EmailLog.Status.SENT:
                sent_count += 1
            elif log.status == EmailLog.Status.FAILED:
                bounce_count += 1

        campaign.status = EmailCampaign.Status.SENT
        campaign.sent_at = timezone.now()
        campaign.total_sent = sent_count
        campaign.total_bounced = bounce_count
        campaign.save(
            update_fields=["status", "sent_at", "total_sent", "total_bounced"]
        )

        logger.info(
            "Campaign '%s' sent: %d delivered, %d bounced",
            campaign.name,
            sent_count,
            bounce_count,
        )
        return campaign
