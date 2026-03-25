"""
Celery configuration for ClientHub CRM.
"""

import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("clienthub")

# Load config from Django settings, using CELERY_ namespace
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()

# Periodic tasks schedule
app.conf.beat_schedule = {
    "check-overdue-tasks-every-hour": {
        "task": "apps.tasks.tasks.check_overdue_tasks",
        "schedule": crontab(minute=0),  # Every hour at :00
    },
    "send-task-reminders-every-30-min": {
        "task": "apps.tasks.tasks.send_task_reminders",
        "schedule": crontab(minute="*/30"),  # Every 30 minutes
    },
    "generate-daily-report": {
        "task": "apps.reports.tasks.generate_daily_summary",
        "schedule": crontab(hour=8, minute=0),  # Daily at 8:00 AM UTC
    },
    "cleanup-old-activity-logs": {
        "task": "apps.activities.tasks.cleanup_old_logs",
        "schedule": crontab(hour=2, minute=0, day_of_week=0),  # Weekly, Sunday 2 AM
    },
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing Celery connectivity."""
    print(f"Request: {self.request!r}")
