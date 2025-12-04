"""
Flask-RESTX API initialization
"""

from flask_restx import Api

# Create the Flask-RESTX API instance
api = Api(
    version="1.0.0",
    title="Shopcart REST API Service",
    description="This service manages customer shopcarts and their items.",
    doc="/api/",
)

# Import and register namespaces
# pylint: disable=import-outside-toplevel


def register_namespaces():
    """Register all API namespaces"""
    from service.resources.items import api as items_namespace

    api.add_namespace(items_namespace)
