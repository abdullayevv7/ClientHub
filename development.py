"""
URL routing for the segments app.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"segments", views.SegmentViewSet, basename="segment")
router.register(r"rules", views.SegmentRuleViewSet, basename="segment-rule")

urlpatterns = [
    path("", include(router.urls)),
]
