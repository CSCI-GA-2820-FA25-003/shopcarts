"""
Swagger data models for Shopcart Service API documentation.

This module defines the data models used for Swagger/OpenAPI documentation
using flask-restx api.model() decorators.
"""
try:
    from flask_restx import fields  # pylint: disable=import-error
except ImportError:
    fields = None  # type: ignore


def create_swagger_models(api_instance):
    """Create and register all Swagger models with the API instance."""
    if fields is None or api_instance is None:
        return {}

    # Define Item model
    item_model = api_instance.model(
        "Item",
        {
            "id": fields.Integer(
                required=False,
                readonly=True,
                description="The unique identifier for the item",
                example=1,
            ),
            "shopcart_id": fields.Integer(
                required=False,
                readonly=True,
                description="The ID of the shopcart this item belongs to",
                example=1,
            ),
            "product_id": fields.Integer(
                required=True,
                description="The unique identifier for the product",
                example=12345,
            ),
            "description": fields.String(
                required=False,
                description="Description of the item",
                example="Widget Pro 5000",
                max_length=256,
            ),
            "quantity": fields.Integer(
                required=True,
                description="Quantity of this item in the cart",
                example=2,
                min=1,
                max=99,
            ),
            "price": fields.Float(
                required=True,
                description="Price per unit of the item",
                example=29.99,
                min=0.0,
            ),
        },
    )

    # Define Item creation model (without id and shopcart_id)
    item_create_model = api_instance.model(
        "ItemCreate",
        {
            "product_id": fields.Integer(
                required=True,
                description="The unique identifier for the product",
                example=12345,
            ),
            "description": fields.String(
                required=False,
                description="Description of the item",
                example="Widget Pro 5000",
                max_length=256,
            ),
            "quantity": fields.Integer(
                required=True,
                description="Quantity of this item to add to the cart",
                example=2,
                min=1,
                max=99,
            ),
            "price": fields.Float(
                required=True,
                description="Price per unit of the item",
                example=29.99,
                min=0.0,
            ),
        },
    )

    # Define Item update model
    item_update_model = api_instance.model(
        "ItemUpdate",
        {
            "quantity": fields.Integer(
                required=False,
                description="New quantity for the item (0 to remove)",
                example=3,
                min=0,
                max=99,
            ),
            "price": fields.Float(
                required=False,
                description="New price per unit",
                example=24.99,
                min=0.0,
            ),
            "description": fields.String(
                required=False,
                description="New description for the item",
                example="Updated Widget Pro 5000",
                max_length=256,
            ),
        },
    )

    # Define Shopcart model
    shopcart_model = api_instance.model(
        "Shopcart",
        {
            "id": fields.Integer(
                required=False,
                readonly=True,
                description="The unique identifier for the shopcart",
                example=1,
            ),
            "customer_id": fields.Integer(
                required=True,
                description="The unique identifier for the customer",
                example=101,
            ),
            "name": fields.String(
                required=False,
                description="Name of the shopcart",
                example="My Summer Cart",
                max_length=120,
            ),
            "created_date": fields.String(
                required=False,
                readonly=True,
                description="ISO8601 timestamp when the shopcart was created",
                example="2024-01-15T10:30:00-05:00",
            ),
            "last_modified": fields.String(
                required=False,
                readonly=True,
                description="ISO8601 timestamp when the shopcart was last modified",
                example="2024-01-15T14:45:00-05:00",
            ),
            "status": fields.String(
                required=False,
                description="Status of the shopcart",
                example="active",
                enum=["active", "abandoned", "locked", "expired"],
            ),
            "total_items": fields.Integer(
                required=False,
                readonly=True,
                description="Total number of items in the cart",
                example=5,
            ),
            "items": fields.List(
                fields.Nested(item_model),
                required=False,
                description="List of items in the shopcart",
            ),
        },
    )

    # Define Shopcart creation model
    shopcart_create_model = api_instance.model(
        "ShopcartCreate",
        {
            "customer_id": fields.Integer(
                required=True,
                description="The unique identifier for the customer",
                example=101,
            ),
            "name": fields.String(
                required=False,
                description="Name of the shopcart",
                example="My Summer Cart",
                max_length=120,
            ),
            "status": fields.String(
                required=False,
                description="Initial status of the shopcart",
                example="active",
                enum=["active", "abandoned", "locked", "expired"],
                default="active",
            ),
            "items": fields.List(
                fields.Nested(item_create_model),
                required=False,
                description="Initial items to add to the shopcart",
            ),
        },
    )

    # Define Shopcart update model
    shopcart_update_model = api_instance.model(
        "ShopcartUpdate",
        {
            "status": fields.String(
                required=False,
                description="New status for the shopcart",
                example="locked",
                enum=["active", "abandoned", "locked", "expired"],
            ),
            "items": fields.List(
                fields.Nested(item_create_model),
                required=False,
                description="Updated list of items (replaces existing items)",
            ),
        },
    )

    # Define Shopcart totals model
    shopcart_totals_model = api_instance.model(
        "ShopcartTotals",
        {
            "customer_id": fields.Integer(
                required=True,
                description="The customer ID",
                example=101,
            ),
            "item_count": fields.Integer(
                required=True,
                description="Number of distinct items in the cart",
                example=3,
            ),
            "total_quantity": fields.Integer(
                required=True,
                description="Total quantity of all items",
                example=7,
            ),
            "subtotal": fields.Float(
                required=True,
                description="Subtotal before discounts",
                example=199.93,
            ),
            "discount": fields.Float(
                required=True,
                description="Discount amount (currently always 0.0)",
                example=0.0,
            ),
            "total": fields.Float(
                required=True,
                description="Final total after discounts",
                example=199.93,
            ),
        },
    )

    # Define error model
    error_model = api_instance.model(
        "Error",
        {
            "error": fields.String(
                required=True,
                description="Error message",
                example="Shopcart for customer '101' was not found.",
            ),
            "status": fields.Integer(
                required=False,
                description="HTTP status code",
                example=404,
            ),
        },
    )

    return {
        "item": item_model,
        "item_create": item_create_model,
        "item_update": item_update_model,
        "shopcart": shopcart_model,
        "shopcart_create": shopcart_create_model,
        "shopcart_update": shopcart_update_model,
        "shopcart_totals": shopcart_totals_model,
        "error": error_model,
    }
