"""
URL routing for the campaigns app.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"tags", views.CampaignTagViewSet, basename="campaign-tag")
router.register(r"campaigns", views.CampaignViewSet, basename="campaign")

urlpatterns = [
    path("", include(router.urls)),
]
