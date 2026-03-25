"""
Views for the accounts app: authentication, user management, teams.
"""

from django.utils import timezone
from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from .models import Team, User
from .permissions import CanManageTeams, CanManageUsers, IsSelfOrAdmin
from .serializers import (
    ChangePasswordSerializer,
    LoginSerializer,
    RegisterSerializer,
    TeamSerializer,
    TokenResponseSerializer,
    UserAdminUpdateSerializer,
    UserCreateSerializer,
    UserSerializer,
    UserUpdateSerializer,
)


class LoginView(generics.GenericAPIView):
    """
    Authenticate a user and return JWT tokens.

    POST /api/auth/login/
    """

    permission_classes = [permissions.AllowAny]
    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        user.last_activity = timezone.now()
        user.save(update_fields=["last_activity"])

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


class RegisterView(generics.CreateAPIView):
    """
    Register a new user account.

    POST /api/auth/register/
    """

    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


class LogoutView(generics.GenericAPIView):
    """
    Blacklist the refresh token to log out.

    POST /api/auth/logout/
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            refresh_token = request.data.get("refresh")
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            return Response(
                {"message": "Successfully logged out."},
                status=status.HTTP_200_OK,
            )
        except Exception:
            return Response(
                {"message": "Invalid token."},
                status=status.HTTP_400_BAD_REQUEST,
            )


class MeView(generics.RetrieveUpdateAPIView):
    """
    Retrieve or update the current authenticated user's profile.

    GET  /api/auth/me/
    PUT  /api/auth/me/
    PATCH /api/auth/me/
    """

    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return UserUpdateSerializer
        return UserSerializer

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserSerializer(instance).data)


class ChangePasswordView(generics.GenericAPIView):
    """
    Change the current user's password.

    POST /api/auth/change-password/
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ChangePasswordSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password"])

        return Response(
            {"message": "Password changed successfully."},
            status=status.HTTP_200_OK,
        )


class UserViewSet(viewsets.ModelViewSet):
    """
    CRUD operations for user management (admin only for create/update/delete).

    GET    /api/auth/users/         - List users
    POST   /api/auth/users/         - Create user (admin)
    GET    /api/auth/users/{id}/    - Retrieve user
    PUT    /api/auth/users/{id}/    - Update user
    DELETE /api/auth/users/{id}/    - Deactivate user
    """

    permission_classes = [permissions.IsAuthenticated, CanManageUsers]
    filterset_fields = ["role", "team", "is_active"]
    search_fields = ["email", "first_name", "last_name", "job_title"]
    ordering_fields = ["first_name", "last_name", "created_at", "role"]

    def get_queryset(self):
        user = self.request.user
        queryset = User.objects.select_related("team").all()

        if user.role == User.Role.ADMIN:
            return queryset
        elif user.role == User.Role.SALES_MANAGER and user.team:
            return queryset.filter(team=user.team)
        else:
            return queryset.filter(id=user.id)

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        if self.action in ("update", "partial_update"):
            if self.request.user.role == User.Role.ADMIN:
                return UserAdminUpdateSerializer
            return UserUpdateSerializer
        return UserSerializer

    def perform_destroy(self, instance):
        """Soft-delete by deactivating instead of removing."""
        instance.is_active = False
        instance.save(update_fields=["is_active"])

    @action(detail=True, methods=["post"], url_path="activate")
    def activate_user(self, request, pk=None):
        """Re-activate a deactivated user."""
        user = self.get_object()
        user.is_active = True
        user.save(update_fields=["is_active"])
        return Response(
            {"message": f"User {user.get_full_name()} has been activated."},
            status=status.HTTP_200_OK,
        )


class TeamViewSet(viewsets.ModelViewSet):
    """
    CRUD operations for team management.

    GET    /api/auth/teams/         - List teams
    POST   /api/auth/teams/         - Create team (admin)
    GET    /api/auth/teams/{id}/    - Retrieve team
    PUT    /api/auth/teams/{id}/    - Update team (admin)
    DELETE /api/auth/teams/{id}/    - Delete team (admin)
    """

    queryset = Team.objects.all()
    serializer_class = TeamSerializer
    permission_classes = [permissions.IsAuthenticated, CanManageTeams]
    search_fields = ["name"]
    ordering_fields = ["name", "created_at"]

    @action(detail=True, methods=["get"], url_path="members")
    def members(self, request, pk=None):
        """List members of a specific team."""
        team = self.get_object()
        members = User.objects.filter(team=team, is_active=True)
        serializer = UserSerializer(members, many=True)
        return Response(serializer.data)
