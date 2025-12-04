"""Centralized JSON error handling for the service."""

from flask import current_app as app, jsonify
from flask_restx.errors import ValidationError
from werkzeug.exceptions import HTTPException

from service.models import DataValidationError
from . import status


def _format_error_details(errors) -> str | None:
    """Format validation error details into a readable string."""
    if not errors:
        return None
    if isinstance(errors, dict):
        return "; ".join(f"{field}: {msg}" for field, msg in errors.items())
    return str(errors)


def _message_from_validation_error(error) -> str | None:
    """Extract messages from Flask-RESTX ValidationError instances."""
    if not isinstance(error, ValidationError):
        return None
    data = getattr(error, "data", {}) or {}
    formatted = _format_error_details(data.get("errors") if isinstance(data, dict) else None)
    if formatted:
        return formatted
    fallback = (
        data.get("message")
        if isinstance(data, dict)
        else None
    ) or getattr(error, "message", None) or getattr(error, "description", None)
    return str(fallback) if fallback else None


def _message_from_http_data(error) -> str | None:
    """Extract messages from HTTPException-like objects carrying .data."""
    data = getattr(error, "data", None)
    if data is None:
        return None
    formatted = _format_error_details(data.get("errors") if isinstance(data, dict) else None)
    if formatted:
        return formatted
    if isinstance(data, dict) and data.get("message"):
        return str(data["message"])
    return None


def _extract_message(error) -> str:
    """Return a human-friendly message for the given error."""
    resolvers = (
        _message_from_validation_error,
        _message_from_http_data,
        lambda err: getattr(err, "description", None),
        lambda err: getattr(err, "message", None),
    )
    for resolver in resolvers:
        message = resolver(error)
        if message:
            return str(message)
    return str(error)


def _json_error(code: int, error_name: str, message: str, *, log_as_error: bool = False):
    """Build and log a JSON error response."""
    logger = app.logger.error if log_as_error else app.logger.warning
    logger(message)
    return jsonify(status=code, error=error_name, message=message), code


@app.errorhandler(DataValidationError)
@app.errorhandler(ValidationError)
def handle_validation_error(error):
    """Return 400 for validation failures with a JSON body."""
    return _json_error(status.HTTP_400_BAD_REQUEST, "Bad Request", _extract_message(error))


@app.errorhandler(HTTPException)
def handle_http_exception(error):
    """Ensure all HTTPException responses are JSON."""
    code = getattr(error, "code", status.HTTP_500_INTERNAL_SERVER_ERROR)
    name = getattr(error, "name", "HTTPException")
    message = _extract_message(error)
    return _json_error(code, name, message, log_as_error=code >= 500)


@app.errorhandler(Exception)
def handle_unhandled_exception(error):
    """Catch-all handler to guarantee JSON 500 responses."""
    app.logger.exception("Unhandled exception: %s", error)
    return _json_error(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "Internal Server Error",
        "An unexpected error occurred.",
        log_as_error=True,
    )


# Convenience exports for any direct tests/imports
__all__ = [
    "handle_http_exception",
    "handle_unhandled_exception",
    "handle_validation_error",
]
