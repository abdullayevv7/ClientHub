"""
Custom exception handling for ClientHub CRM API.
"""

import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler that provides consistent error response format.

    Response format:
    {
        "error": true,
        "message": "Human-readable error message",
        "errors": { ... },  // field-level errors for validation
        "status_code": 400
    }
    """
    # Convert Django ValidationError to DRF ValidationError
    if isinstance(exc, DjangoValidationError):
        if hasattr(exc, "message_dict"):
            exc = ValidationError(detail=exc.message_dict)
        else:
            exc = ValidationError(detail=exc.messages)

    # Call DRF's default exception handler first
    response = exception_handler(exc, context)

    if response is not None:
        error_payload = {
            "error": True,
            "status_code": response.status_code,
        }

        if isinstance(response.data, dict):
            # Extract 'detail' as the main message if present
            if "detail" in response.data:
                error_payload["message"] = str(response.data["detail"])
            else:
                error_payload["message"] = "Validation error"
                error_payload["errors"] = response.data
        elif isinstance(response.data, list):
            error_payload["message"] = response.data[0] if response.data else "An error occurred"
            error_payload["errors"] = response.data
        else:
            error_payload["message"] = str(response.data)

        response.data = error_payload
    else:
        # Unhandled exceptions -- log and return a generic 500
        logger.exception(
            "Unhandled exception in %s",
            context.get("view", "unknown"),
            exc_info=exc,
        )
        response = Response(
            {
                "error": True,
                "message": "An unexpected error occurred. Please try again later.",
                "status_code": 500,
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return response


class BusinessLogicError(APIException):
    """Exception for business rule violations."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "A business rule was violated."
    default_code = "business_logic_error"


class ResourceConflictError(APIException):
    """Exception when a resource conflict is detected."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = "A resource conflict was detected."
    default_code = "conflict"


class ExternalServiceError(APIException):
    """Exception when an external service call fails."""

    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = "An external service is currently unavailable."
    default_code = "external_service_error"
