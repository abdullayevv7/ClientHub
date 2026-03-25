"""
URL routing for the deals app.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"pipelines", views.PipelineViewSet, basename="pipeline")
router.register(r"stages", views.DealStageViewSet, basename="deal-stage")
router.register(r"deals", views.DealViewSet, basename="deal")

urlpatterns = [
    path("", include(router.urls)),
]
