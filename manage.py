"""
Task, TaskComment, and Reminder models for ClientHub CRM.
"""

import uuid

from django.conf import settings
from django.db import models


class Task(models.Model):
    """
    A task that can be assigned to users, linked to contacts/deals.
    """

    class Status(models.TextChoices):
        TODO = "todo", "To Do"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    class TaskType(models.TextChoices):
        CALL = "call", "Call"
        EMAIL = "email", "Email"
        MEETING = "meeting", "Meeting"
        FOLLOW_UP = "follow_up", "Follow Up"
        DEMO = "demo", "Demo"
        PROPOSAL = "proposal", "Proposal"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200, db_index=True)
    description = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.TODO,
        db_index=True,
    )
    priority = models.CharField(
        max_length=10,
        choices=Priority.choices,
        default=Priority.MEDIUM,
        db_index=True,
    )
    task_type = models.CharField(
        max_length=20,
        choices=TaskType.choices,
        default=TaskType.OTHER,
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tasks",
    )
    contact = models.ForeignKey(
        "contacts.Contact",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tasks",
    )
    deal = models.ForeignKey(
        "deals.Deal",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tasks",
    )
    due_date = models.DateTimeField(null=True, blank=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_tasks",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-priority", "due_date", "-created_at"]
        db_table = "crm_tasks"

    def __str__(self):
        return self.title

    @property
    def is_overdue(self):
        from django.utils import timezone

        if self.due_date and self.status not in (
            self.Status.COMPLETED,
            self.Status.CANCELLED,
        ):
            return self.due_date < timezone.now()
        return False


class TaskComment(models.Model):
    """Comments on a task for collaboration."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="comments")
    content = models.TextField()
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="task_comments",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        db_table = "crm_task_comments"

    def __str__(self):
        return f"Comment on '{self.task.title}' by {self.author}"


class Reminder(models.Model):
    """
    Reminders linked to tasks, triggered by Celery.
    """

    class ReminderType(models.TextChoices):
        EMAIL = "email", "Email"
        IN_APP = "in_app", "In-App Notification"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="reminders")
    reminder_type = models.CharField(
        max_length=10,
        choices=ReminderType.choices,
        default=ReminderType.EMAIL,
    )
    remind_at = models.DateTimeField(db_index=True)
    is_sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reminders",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["remind_at"]
        db_table = "crm_reminders"

    def __str__(self):
        return f"Reminder for '{self.task.title}' at {self.remind_at}"
