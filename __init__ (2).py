"""
Account-specific permission classes.
"""

from rest_framework.permissions import BasePermission

from .models import User


class IsAdminUser(BasePermission):
    """Only admin users can access."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == User.Role.ADMIN


class CanManageUsers(BasePermission):
    """Admin can manage all users. Managers can view team members."""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.user.role == User.Role.ADMIN:
            return True
        if request.user.role == User.Role.SALES_MANAGER and request.method in (
            "GET",
            "HEAD",
            "OPTIONS",
        ):
            return True
        return False

    def has_object_permission(self, request, view, obj):
        if request.user.role == User.Role.ADMIN:
            return True
        # Users can always edit their own profile
        if request.user == obj:
            return True
        # Managers can view team members
        if (
            request.user.role == User.Role.SALES_MANAGER
            and request.method in ("GET", "HEAD", "OPTIONS")
            and obj.team == request.user.team
        ):
            return True
        return False


class CanManageTeams(BasePermission):
    """Only admins can create/update/delete teams. Others can view."""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return request.user.role == User.Role.ADMIN


class IsSelfOrAdmin(BasePermission):
    """Users can access their own data; admins can access any."""

    def has_object_permission(self, request, view, obj):
        return request.user == obj or request.user.role == User.Role.ADMIN
