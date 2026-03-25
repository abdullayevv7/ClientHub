"""
Shared permission classes for ClientHub CRM.
"""

from rest_framework.permissions import BasePermission

from apps.accounts.models import User


class IsAdmin(BasePermission):
    """Allows access only to admin users."""

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == User.Role.ADMIN
        )


class IsSalesManager(BasePermission):
    """Allows access to sales managers and above."""

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in (User.Role.ADMIN, User.Role.SALES_MANAGER)
        )


class IsSalesRep(BasePermission):
    """Allows access to sales reps and above."""

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role
            in (User.Role.ADMIN, User.Role.SALES_MANAGER, User.Role.SALES_REP)
        )


class IsSupportAgent(BasePermission):
    """Allows access to support agents."""

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == User.Role.SUPPORT_AGENT
        )


class IsOwnerOrAdmin(BasePermission):
    """
    Object-level permission: allows access if user owns the object or is admin.
    Expects the object to have an 'owner' or 'assigned_to' or 'created_by' attribute.
    """

    def has_object_permission(self, request, view, obj):
        if request.user.role == User.Role.ADMIN:
            return True

        owner_field = getattr(obj, "owner", None)
        assigned_to = getattr(obj, "assigned_to", None)
        created_by = getattr(obj, "created_by", None)

        user = request.user
        return user in (owner_field, assigned_to, created_by)


class IsTeamMemberOrAdmin(BasePermission):
    """
    Allows access if the user is in the same team as the object owner,
    or if the user is an admin.
    """

    def has_object_permission(self, request, view, obj):
        if request.user.role == User.Role.ADMIN:
            return True

        owner = getattr(obj, "owner", None) or getattr(obj, "assigned_to", None)
        if owner is None:
            return False

        if request.user == owner:
            return True

        # Sales managers can access team members' objects
        if request.user.role == User.Role.SALES_MANAGER:
            return request.user.team == owner.team if owner.team else False

        return False
