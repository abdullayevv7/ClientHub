"""
Account models: User, Team, and Role management for ClientHub CRM.
"""

import uuid

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    """Custom user manager that uses email as the unique identifier."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.ADMIN)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class Team(models.Model):
    """
    Represents a sales team. Users belong to teams for data scoping
    and collaboration.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        db_table = "crm_teams"

    def __str__(self):
        return self.name

    @property
    def member_count(self):
        return self.members.filter(is_active=True).count()


class User(AbstractUser):
    """
    Custom user model for ClientHub CRM.
    Uses email as the primary identifier instead of username.
    """

    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        SALES_MANAGER = "sales_manager", "Sales Manager"
        SALES_REP = "sales_rep", "Sales Rep"
        SUPPORT_AGENT = "support_agent", "Support Agent"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = None  # Remove username field
    email = models.EmailField("email address", unique=True, db_index=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.SALES_REP,
        db_index=True,
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="members",
    )
    phone = models.CharField(max_length=20, blank=True, default="")
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    job_title = models.CharField(max_length=100, blank=True, default="")
    bio = models.TextField(blank=True, default="")
    timezone = models.CharField(max_length=50, default="UTC")
    is_active = models.BooleanField(default=True)
    email_notifications = models.BooleanField(default=True)
    last_activity = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        ordering = ["first_name", "last_name"]
        db_table = "crm_users"

    def __str__(self):
        return f"{self.get_full_name()} ({self.email})"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN

    @property
    def is_sales_manager(self):
        return self.role == self.Role.SALES_MANAGER

    @property
    def is_sales_rep(self):
        return self.role == self.Role.SALES_REP

    @property
    def is_support_agent(self):
        return self.role == self.Role.SUPPORT_AGENT

    @property
    def can_manage_deals(self):
        return self.role in (self.Role.ADMIN, self.Role.SALES_MANAGER, self.Role.SALES_REP)

    @property
    def can_manage_pipeline(self):
        return self.role in (self.Role.ADMIN, self.Role.SALES_MANAGER)
