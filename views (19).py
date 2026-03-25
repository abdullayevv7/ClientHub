"""
URL routing for the contacts app.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"contacts", views.ContactViewSet, basename="contact")
router.register(r"companies", views.CompanyViewSet, basename="company")
router.register(r"tags", views.ContactTagViewSet, basename="contact-tag")

urlpatterns = [
    path("", include(router.urls)),
]
