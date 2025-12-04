"""Shared Flask-RESTX API configuration for the Shopcart service."""

from flask_restx import Api

# Centralized API instance so namespaces can be registered in one place.
api = Api(
    title="Shopcart REST API Service",
    version="1.0.0",
    description="Shopcart service API documentation",
    prefix="/api",
    doc="/apidocs/",
    errors=False,  # Defer to our global error handlers for consistent JSON
)

__all__ = ["api"]
