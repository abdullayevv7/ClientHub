"""
URL routing for the tasks app.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"", views.TaskViewSet, basename="task")

urlpatterns = [
    path("", include(router.urls)),
]
