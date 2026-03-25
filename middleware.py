"""
Celery tasks for task reminders and overdue notifications.
"""

import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_task_reminders(self):
    """
    Check for pending reminders that should be sent now.
    Runs every 30 minutes via Celery Beat.
    """
    from .models import Reminder

    now = timezone.now()
    pending_reminders = Reminder.objects.filter(
        is_sent=False,
        remind_at__lte=now,
        task__status__in=["todo", "in_progress"],
    ).select_related("task", "user")

    sent_count = 0
    for reminder in pending_reminders:
        try:
            if reminder.reminder_type == "email" and reminder.user.email_notifications:
                subject = f"Reminder: {reminder.task.title}"
                message = (
                    f"Hi {reminder.user.get_full_name()},\n\n"
                    f"This is a reminder for your task:\n\n"
                    f"Title: {reminder.task.title}\n"
                    f"Priority: {reminder.task.get_priority_display()}\n"
                    f"Due: {reminder.task.due_date.strftime('%Y-%m-%d %H:%M') if reminder.task.due_date else 'No due date'}\n\n"
                    f"Description: {reminder.task.description[:200]}\n\n"
                    f"Please log in to ClientHub to view the full details.\n\n"
                    f"-- ClientHub CRM"
                )
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[reminder.user.email],
                    fail_silently=False,
                )

            reminder.is_sent = True
            reminder.sent_at = now
            reminder.save(update_fields=["is_sent", "sent_at"])
            sent_count += 1

        except Exception as exc:
            logger.error(
                "Failed to send reminder %s: %s", reminder.id, str(exc)
            )
            self.retry(exc=exc)

    logger.info("Sent %d task reminders", sent_count)
    return f"Sent {sent_count} reminders"


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def check_overdue_tasks(self):
    """
    Check for overdue tasks and send email notifications to assignees.
    Runs every hour via Celery Beat.
    """
    from .models import Task

    now = timezone.now()
    overdue_tasks = Task.objects.filter(
        due_date__lt=now,
        status__in=[Task.Status.TODO, Task.Status.IN_PROGRESS],
        assigned_to__isnull=False,
        assigned_to__email_notifications=True,
    ).select_related("assigned_to", "contact", "deal")

    notified_count = 0
    # Group by user to avoid sending multiple emails
    user_tasks = {}
    for task in overdue_tasks:
        user_id = str(task.assigned_to.id)
        if user_id not in user_tasks:
            user_tasks[user_id] = {
                "user": task.assigned_to,
                "tasks": [],
            }
        user_tasks[user_id]["tasks"].append(task)

    for user_id, data in user_tasks.items():
        user = data["user"]
        tasks = data["tasks"]

        try:
            task_list = "\n".join(
                [
                    f"  - {t.title} (Due: {t.due_date.strftime('%Y-%m-%d %H:%M')})"
                    for t in tasks
                ]
            )
            subject = f"You have {len(tasks)} overdue task(s) in ClientHub"
            message = (
                f"Hi {user.get_full_name()},\n\n"
                f"The following tasks are overdue:\n\n"
                f"{task_list}\n\n"
                f"Please log in to ClientHub to update these tasks.\n\n"
                f"-- ClientHub CRM"
            )
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )
            notified_count += 1

        except Exception as exc:
            logger.error(
                "Failed to send overdue notification to %s: %s",
                user.email,
                str(exc),
            )

    logger.info("Sent overdue notifications to %d users", notified_count)
    return f"Notified {notified_count} users about overdue tasks"


@shared_task
def send_task_assignment_notification(task_id):
    """Send a notification when a task is assigned to someone."""
    from .models import Task

    try:
        task = Task.objects.select_related("assigned_to", "created_by").get(id=task_id)
    except Task.DoesNotExist:
        logger.warning("Task %s not found for assignment notification", task_id)
        return

    if not task.assigned_to or not task.assigned_to.email_notifications:
        return

    # Don't notify if self-assigned
    if task.assigned_to == task.created_by:
        return

    subject = f"New task assigned: {task.title}"
    message = (
        f"Hi {task.assigned_to.get_full_name()},\n\n"
        f"{task.created_by.get_full_name() if task.created_by else 'Someone'} "
        f"has assigned you a new task:\n\n"
        f"Title: {task.title}\n"
        f"Priority: {task.get_priority_display()}\n"
        f"Due: {task.due_date.strftime('%Y-%m-%d %H:%M') if task.due_date else 'No due date'}\n\n"
        f"Description: {task.description[:300]}\n\n"
        f"Log in to ClientHub to view details.\n\n"
        f"-- ClientHub CRM"
    )

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[task.assigned_to.email],
        fail_silently=True,
    )
    logger.info("Sent assignment notification for task %s to %s", task_id, task.assigned_to.email)
