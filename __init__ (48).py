"""
Serializers for the tasks app.
"""

from rest_framework import serializers

from .models import Reminder, Task, TaskComment


class TaskCommentSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.get_full_name", read_only=True, default=None)

    class Meta:
        model = TaskComment
        fields = [
            "id",
            "task",
            "content",
            "author",
            "author_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "author", "created_at", "updated_at"]


class ReminderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reminder
        fields = [
            "id",
            "task",
            "reminder_type",
            "remind_at",
            "is_sent",
            "sent_at",
            "user",
            "created_at",
        ]
        read_only_fields = ["id", "is_sent", "sent_at", "created_at"]


class TaskListSerializer(serializers.ModelSerializer):
    assigned_to_name = serializers.CharField(
        source="assigned_to.get_full_name", read_only=True, default=None
    )
    contact_name = serializers.SerializerMethodField()
    deal_title = serializers.CharField(source="deal.title", read_only=True, default=None)
    is_overdue = serializers.ReadOnlyField()
    comment_count = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            "id",
            "title",
            "status",
            "priority",
            "task_type",
            "assigned_to",
            "assigned_to_name",
            "contact",
            "contact_name",
            "deal",
            "deal_title",
            "due_date",
            "is_overdue",
            "comment_count",
            "created_at",
        ]

    def get_contact_name(self, obj):
        if obj.contact:
            return obj.contact.full_name
        return None

    def get_comment_count(self, obj):
        return obj.comments.count()


class TaskDetailSerializer(serializers.ModelSerializer):
    assigned_to_name = serializers.CharField(
        source="assigned_to.get_full_name", read_only=True, default=None
    )
    created_by_name = serializers.CharField(
        source="created_by.get_full_name", read_only=True, default=None
    )
    contact_name = serializers.SerializerMethodField()
    deal_title = serializers.CharField(source="deal.title", read_only=True, default=None)
    is_overdue = serializers.ReadOnlyField()
    comments = TaskCommentSerializer(many=True, read_only=True)
    reminders = ReminderSerializer(many=True, read_only=True)

    class Meta:
        model = Task
        fields = [
            "id",
            "title",
            "description",
            "status",
            "priority",
            "task_type",
            "assigned_to",
            "assigned_to_name",
            "contact",
            "contact_name",
            "deal",
            "deal_title",
            "due_date",
            "completed_at",
            "is_overdue",
            "created_by",
            "created_by_name",
            "comments",
            "reminders",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by", "completed_at", "created_at", "updated_at"]

    def get_contact_name(self, obj):
        if obj.contact:
            return obj.contact.full_name
        return None


class TaskCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = [
            "title",
            "description",
            "status",
            "priority",
            "task_type",
            "assigned_to",
            "contact",
            "deal",
            "due_date",
        ]
