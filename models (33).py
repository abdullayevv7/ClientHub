"""
URL routing for the emails app.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"templates", views.EmailTemplateViewSet, basename="email-template")
router.register(r"campaigns", views.EmailCampaignViewSet, basename="email-campaign")
router.register(r"logs", views.EmailLogViewSet, basename="email-log")

urlpatterns = [
    path("send/", views.SendEmailView.as_view(), name="send-email"),
    path("", include(router.urls)),
]
