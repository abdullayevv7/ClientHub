"""
Views for the tasks app.
"""

from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import User
from apps.activities.models import ActivityLog

from .models import Reminder, Task, TaskComment
from .serializers import (
    ReminderSerializer,
    TaskCommentSerializer,
    TaskCreateUpdateSerializer,
    TaskDetailSerializer,
    TaskListSerializer,
)


class TaskViewSet(viewsets.ModelViewSet):
    """
    CRUD for tasks with role-based filtering.

    GET    /api/tasks/              - List tasks
    POST   /api/tasks/              - Create a task
    GET    /api/tasks/{id}/         - Retrieve a task
    PUT    /api/tasks/{id}/         - Update a task
    DELETE /api/tasks/{id}/         - Delete a task
    """

    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["status", "priority", "task_type", "assigned_to", "contact", "deal"]
    search_fields = ["title", "description"]
    ordering_fields = ["title", "priority", "status", "due_date", "created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        queryset = Task.objects.select_related(
            "assigned_to", "contact", "deal", "created_by"
        ).prefetch_related("comments")

        if user.role == User.Role.ADMIN:
            return queryset
        elif user.role == User.Role.SALES_MANAGER and user.team:
            team_members = User.objects.filter(team=user.team)
            return queryset.filter(
                Q(assigned_to__in=team_members)
                | Q(created_by__in=team_members)
                | Q(assigned_to__isnull=True)
            )
        else:
            return queryset.filter(
                Q(assigned_to=user) | Q(created_by=user) | Q(assigned_to__isnull=True)
            )

    def get_serializer_class(self):
        if self.action == "list":
            return TaskListSerializer
        if self.action in ("create", "update", "partial_update"):
            return TaskCreateUpdateSerializer
        return TaskDetailSerializer

    def perform_create(self, serializer):
        task = serializer.save(created_by=self.request.user)
        if not task.assigned_to:
            task.assigned_to = self.request.user
            task.save(update_fields=["assigned_to"])

        ActivityLog.objects.create(
            user=self.request.user,
            action=ActivityLog.Action.CREATED,
            entity_type="task",
            entity_id=str(task.id),
            description=f"Created task '{task.title}'",
        )

    def perform_update(self, serializer):
        task = serializer.save()
        ActivityLog.objects.create(
            user=self.request.user,
            action=ActivityLog.Action.UPDATED,
            entity_type="task",
            entity_id=str(task.id),
            description=f"Updated task '{task.title}'",
        )

    @action(detail=True, methods=["patch"], url_path="complete")
    def complete(self, request, pk=None):
        """Mark a task as completed."""
        task = self.get_object()
        task.status = Task.Status.COMPLETED
        task.completed_at = timezone.now()
        task.save(update_fields=["status", "completed_at", "updated_at"])

        ActivityLog.objects.create(
            user=request.user,
            action=ActivityLog.Action.COMPLETED,
            entity_type="task",
            entity_id=str(task.id),
            description=f"Completed task '{task.title}'",
        )

        # If task is linked to a deal, log on the deal too
        if task.deal:
            from apps.deals.models import DealActivity

            DealActivity.objects.create(
                deal=task.deal,
                activity_type=DealActivity.ActivityType.NOTE,
                description=f"Task '{task.title}' completed",
                user=request.user,
            )

        return Response(TaskDetailSerializer(task).data)

    @action(detail=True, methods=["get", "post"], url_path="comments")
    def comments(self, request, pk=None):
        """List or add comments on a task."""
        task = self.get_object()

        if request.method == "GET":
            comments = task.comments.select_related("author").all()
            serializer = TaskCommentSerializer(comments, many=True)
            return Response(serializer.data)

        serializer = TaskCommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(task=task, author=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="reminders")
    def add_reminder(self, request, pk=None):
        """Add a reminder to a task."""
        task = self.get_object()
        serializer = ReminderSerializer(data={**request.data, "task": task.id})
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], url_path="my-tasks")
    def my_tasks(self, request):
        """Get tasks assigned to the current user."""
        tasks = Task.objects.filter(
            assigned_to=request.user,
            status__in=[Task.Status.TODO, Task.Status.IN_PROGRESS],
        ).select_related("contact", "deal")
        serializer = TaskListSerializer(tasks, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="overdue")
    def overdue(self, request):
        """Get all overdue tasks."""
        tasks = self.get_queryset().filter(
            due_date__lt=timezone.now(),
            status__in=[Task.Status.TODO, Task.Status.IN_PROGRESS],
        )
        serializer = TaskListSerializer(tasks, many=True)
        return Response(serializer.data)
