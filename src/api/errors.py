"""Standardized error response utilities for the API.

This module provides a consistent error response format across all API endpoints,
enabling the frontend to properly categorize errors and implement appropriate
handling strategies (retry, user notification, etc.).
"""

from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    """Error codes for API responses.

    These codes provide semantic meaning for frontend error handling:
    - Frontend can determine if an error is retryable
    - Frontend can show appropriate user messages
    - Frontend can implement specific handling (e.g., re-auth for AUTH errors)
    """

    # Authentication errors
    AUTH_REQUIRED = "AUTH_REQUIRED"  # Missing authentication
    AUTH_INVALID = "AUTH_INVALID"  # Invalid token/credentials
    AUTH_EXPIRED = "AUTH_EXPIRED"  # Token expired
    AUTH_FORBIDDEN = "AUTH_FORBIDDEN"  # Valid auth but not authorized

    # Validation errors
    VALIDATION_ERROR = "VALIDATION_ERROR"  # Invalid input data
    MISSING_FIELD = "MISSING_FIELD"  # Required field missing
    INVALID_FORMAT = "INVALID_FORMAT"  # Field has wrong format

    # Resource errors
    NOT_FOUND = "NOT_FOUND"  # Resource doesn't exist
    CONFLICT = "CONFLICT"  # Resource state conflict

    # Server errors (potentially retryable)
    SERVER_ERROR = "SERVER_ERROR"  # Generic server error
    TIMEOUT = "TIMEOUT"  # Request/operation timed out
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"  # Backend service down
    RATE_LIMITED = "RATE_LIMITED"  # Too many requests

    # External service errors
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"  # Third-party API failed
    LLM_ERROR = "LLM_ERROR"  # LLM/Gemini API error
    TOOL_ERROR = "TOOL_ERROR"  # Tool execution failed


# Errors that the frontend may safely retry automatically (for idempotent operations)
RETRYABLE_ERRORS = {
    ErrorCode.TIMEOUT,
    ErrorCode.SERVICE_UNAVAILABLE,
    ErrorCode.RATE_LIMITED,
    ErrorCode.SERVER_ERROR,  # May be transient
}


def is_retryable(code: ErrorCode) -> bool:
    """Check if an error code indicates a retryable error."""
    return code in RETRYABLE_ERRORS


def create_error_response(
    code: ErrorCode,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a standardized error response.

    Args:
        code: Error code enum value
        message: Human-readable error message (safe to show to users)
        details: Optional additional details (e.g., field name for validation errors)

    Returns:
        Dict with standardized error structure:
        {
            "error": {
                "code": "ERROR_CODE",
                "message": "Human-readable message",
                "retryable": true/false,
                "details": {...}  # optional
            }
        }
    """
    error_data: dict[str, Any] = {
        "code": code.value,
        "message": message,
        "retryable": is_retryable(code),
    }

    if details:
        error_data["details"] = details

    return {"error": error_data}


# Convenience functions for common error types


def validation_error(message: str, field: str | None = None) -> tuple[dict[str, Any], int]:
    """Create a validation error response (400)."""
    details = {"field": field} if field else None
    return create_error_response(ErrorCode.VALIDATION_ERROR, message, details), 400


def missing_field_error(field: str) -> tuple[dict[str, Any], int]:
    """Create a missing field error response (400)."""
    return create_error_response(
        ErrorCode.MISSING_FIELD,
        f"Missing required field: {field}",
        {"field": field},
    ), 400


def not_found_error(resource: str = "Resource") -> tuple[dict[str, Any], int]:
    """Create a not found error response (404)."""
    return create_error_response(
        ErrorCode.NOT_FOUND,
        f"{resource} not found",
    ), 404


def auth_required_error() -> tuple[dict[str, Any], int]:
    """Create an authentication required error response (401)."""
    return create_error_response(
        ErrorCode.AUTH_REQUIRED,
        "Authentication required",
    ), 401


def auth_invalid_error(message: str = "Invalid credentials") -> tuple[dict[str, Any], int]:
    """Create an invalid authentication error response (401)."""
    return create_error_response(
        ErrorCode.AUTH_INVALID,
        message,
    ), 401


def auth_forbidden_error(message: str = "Access denied") -> tuple[dict[str, Any], int]:
    """Create a forbidden error response (403)."""
    return create_error_response(
        ErrorCode.AUTH_FORBIDDEN,
        message,
    ), 403


def timeout_error(
    message: str = "Request timed out. Please try again.",
    timeout_seconds: int | None = None,
) -> tuple[dict[str, Any], int]:
    """Create a timeout error response (504)."""
    details = {"timeout_seconds": timeout_seconds} if timeout_seconds else None
    return create_error_response(ErrorCode.TIMEOUT, message, details), 504


def server_error(
    message: str = "An unexpected error occurred. Please try again.",
) -> tuple[dict[str, Any], int]:
    """Create a generic server error response (500).

    Note: Never expose internal error details to users. Log them server-side instead.
    """
    return create_error_response(ErrorCode.SERVER_ERROR, message), 500


def service_unavailable_error(
    message: str = "Service temporarily unavailable. Please try again later.",
) -> tuple[dict[str, Any], int]:
    """Create a service unavailable error response (503)."""
    return create_error_response(ErrorCode.SERVICE_UNAVAILABLE, message), 503


def rate_limited_error(
    message: str = "Too many requests. Please slow down.",
    retry_after: int | None = None,
) -> tuple[dict[str, Any], int]:
    """Create a rate limited error response (429)."""
    details = {"retry_after": retry_after} if retry_after else None
    return create_error_response(ErrorCode.RATE_LIMITED, message, details), 429


def llm_error(message: str = "AI service error. Please try again.") -> tuple[dict[str, Any], int]:
    """Create an LLM/Gemini error response (502)."""
    return create_error_response(ErrorCode.LLM_ERROR, message), 502


def tool_error(
    message: str = "Tool execution failed.",
    tool_name: str | None = None,
) -> tuple[dict[str, Any], int]:
    """Create a tool execution error response (500)."""
    details = {"tool": tool_name} if tool_name else None
    return create_error_response(ErrorCode.TOOL_ERROR, message, details), 500


def external_service_error(
    message: str = "External service error. Please try again.",
    service: str | None = None,
) -> tuple[dict[str, Any], int]:
    """Create an external service error response (502)."""
    details = {"service": service} if service else None
    return create_error_response(ErrorCode.EXTERNAL_SERVICE_ERROR, message, details), 502


def invalid_json_error() -> tuple[dict[str, Any], int]:
    """Create an invalid JSON error response (400)."""
    return create_error_response(
        ErrorCode.INVALID_FORMAT,
        "Invalid JSON in request body",
    ), 400
