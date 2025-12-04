"""Shared Flask-RESTX API configuration for the Shopcart service."""

from flask_restx import Api

# Centralized API instance so namespaces can be registered in one place.
api = Api(
    title="Shopcart REST API Service",
    version="1.0.0",
    description="This service manages customer shopcarts and their items.",
    prefix="/api",
    doc="/apidocs/",
    errors=False,  # Defer to our global error handlers for consistent JSON
)

# Import and register namespaces
# pylint: disable=import-outside-toplevel


def register_namespaces():
    """Register all API namespaces"""
    from service.resources.items import api as items_namespace

    api.add_namespace(items_namespace)


__all__ = ["api", "register_namespaces"]
