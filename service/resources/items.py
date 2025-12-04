"""
Item Resource for Flask-RESTX
"""
import decimal
from decimal import Decimal
from datetime import datetime
from dataclasses import dataclass
from flask import current_app as app, request
from flask_restx import Resource, Namespace, fields, abort

from service.models import Shopcart, ShopcartItem
from service.common import status

# Create a namespace for items
api = Namespace("items", description="Item operations", path="/shopcarts/<int:shopcart_id>/items")

######################################################################
# Swagger Models
######################################################################

# Item model for responses
item_model = api.model(
    "Item",
    {
        "id": fields.Integer(required=True, description="The item ID"),
        "shopcart_id": fields.Integer(required=True, description="The shopcart ID"),
        "product_id": fields.Integer(required=True, description="The product ID"),
        "description": fields.String(description="Item description"),
        "quantity": fields.Integer(required=True, description="Item quantity"),
        "price": fields.Float(required=True, description="Item price"),
    },
)

# ItemCreate model for POST requests
item_create_model = api.model(
    "ItemCreate",
    {
        "product_id": fields.Integer(required=True, description="The product ID"),
        "quantity": fields.Integer(required=True, description="Item quantity (must be positive)"),
        "price": fields.Float(required=False, description="Item price (required if item doesn't exist)"),
        "description": fields.String(required=False, description="Item description"),
    },
)

# ItemUpdate model for PUT requests
item_update_model = api.model(
    "ItemUpdate",
    {
        "quantity": fields.Integer(required=False, description="Item quantity (0-99, 0 deletes item)"),
        "price": fields.Float(required=False, description="Item price"),
        "description": fields.String(required=False, description="Item description"),
    },
)

# Message model for error responses
message_model = api.model(
    "Message",
    {
        "status": fields.Integer(required=True, description="HTTP status code"),
        "error": fields.String(required=True, description="Error type"),
        "message": fields.String(required=True, description="Error message"),
    },
)

# Item list model
item_list_model = api.model(
    "ItemList",
    {
        "items": fields.List(fields.Nested(item_model), description="List of items"),
    },
)


######################################################################
# Helper Functions
######################################################################

def _require_product_id(payload):
    """Extract and validate product_id from payload."""
    try:
        return int(payload["product_id"])
    except (KeyError, TypeError, ValueError):
        abort(
            status.HTTP_400_BAD_REQUEST,
            "product_id is required and must be an integer.",
        )
        return None  # Never reached, but satisfies pylint


def _require_quantity_increment(payload):
    """Ensure quantity is a positive integer increment."""
    try:
        increment = int(payload.get("quantity", 0))
    except (TypeError, ValueError):
        abort(status.HTTP_400_BAD_REQUEST, "quantity must be an integer.")
        return None  # Never reached, but satisfies pylint
    if increment <= 0:
        abort(status.HTTP_400_BAD_REQUEST, "quantity must be a positive integer.")
        return None  # Never reached, but satisfies pylint
    return increment


def _resolve_price(existing_item, price_raw):
    """Resolve the price for the incoming payload."""
    if existing_item and price_raw is None:
        return Decimal(str(existing_item.price))
    if price_raw is None:
        abort(status.HTTP_400_BAD_REQUEST, "price is required.")
        return None  # Never reached, but satisfies pylint
    try:
        return Decimal(str(price_raw))
    except (decimal.InvalidOperation, ValueError, TypeError):
        abort(status.HTTP_400_BAD_REQUEST, "price is invalid.")
        return None  # Never reached, but satisfies pylint


def _resolve_description(existing_item, payload):
    """Select description, defaulting to the existing entry."""
    base = existing_item.description if existing_item else ""
    return payload.get("description", base or "")


def _parse_price_bound(value: str, field: str) -> Decimal | None:
    """Parse a numeric price boundary from the request."""
    cleaned = (value or "").strip()
    if not cleaned:
        abort(status.HTTP_400_BAD_REQUEST, f"{field} must be a number")
        return None  # Never reached, but satisfies pylint
    try:
        return Decimal(cleaned)
    except (decimal.InvalidOperation, ValueError, TypeError):
        abort(status.HTTP_400_BAD_REQUEST, f"{field} must be a number")
        return None  # Never reached, but satisfies pylint


def _normalize_description_filter(value) -> str | None:
    """Normalize a description filter, validating non-empty input."""
    if value is None:
        return None
    description = str(value).strip()
    if not description:
        abort(
            status.HTTP_400_BAD_REQUEST,
            "description must be a non-empty string when provided",
        )
    return description


def _parse_optional_int(args, field: str, error_message: str) -> int | None:
    """Parse an optional integer query parameter."""
    if field not in args:
        return None
    try:
        return int(args.get(field))
    except (TypeError, ValueError):
        abort(status.HTTP_400_BAD_REQUEST, error_message)
        return None  # Never reached, but satisfies pylint


def _validate_shopcart_and_item(shopcart_id, item_id):
    """Validate shopcart and item exist and item belongs to shopcart."""
    shopcart = Shopcart.find(shopcart_id)
    if not shopcart:
        abort(
            status.HTTP_404_NOT_FOUND,
            f"Shopcart with id '{shopcart_id}' was not found.",
        )

    item = ShopcartItem.find(item_id)
    if not item:
        abort(
            status.HTTP_404_NOT_FOUND,
            f"Item with id '{item_id}' was not found.",
        )

    if item.shopcart_id != shopcart.id:
        abort(
            status.HTTP_404_NOT_FOUND,
            f"Item with id '{item_id}' not found in shopcart '{shopcart_id}'.",
        )

    return shopcart, item


def _check_shopcart_status(shopcart):
    """Check if shopcart status allows updates."""
    status_norm = (
        shopcart.status.strip().lower()
        if isinstance(shopcart.status, str)
        else "active"
    )
    if status_norm == "abandoned":
        abort(
            status.HTTP_409_CONFLICT,
            "Cannot update items on an abandoned shopcart.",
        )


def _parse_quantity_for_update(payload, item):
    """Parse and validate quantity from update payload."""
    q_raw = payload.get("quantity", item.quantity)
    try:
        q = int(q_raw)
    except (TypeError, ValueError):
        abort(status.HTTP_400_BAD_REQUEST, "quantity must be an integer.")
    if q < 0 or q > 99:
        abort(status.HTTP_400_BAD_REQUEST, "invalid quantity")
    return q


def _parse_price_for_update(payload, item):
    """Parse and validate price from update payload."""
    price_raw = payload.get("price", float(item.price))
    try:
        return Decimal(str(price_raw))
    except (decimal.InvalidOperation, ValueError, TypeError):
        abort(status.HTTP_400_BAD_REQUEST, "price is invalid.")
        return None  # Never reached, but satisfies pylint


@dataclass
class ItemFilters:
    """Container for shopcart item filters."""

    description: str | None = None
    product_id: int | None = None
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    quantity: int | None = None
    status: str | None = None  # Filter by shopcart status (not item status)


ITEM_FILTER_FIELDS = {"description", "product_id", "min_price", "max_price", "quantity", "sku", "status"}


def _parse_item_filters(args) -> ItemFilters:
    """Validate and normalize query params for item listing."""
    unsupported = sorted(set(args.keys()) - ITEM_FILTER_FIELDS)
    if unsupported:
        if len(unsupported) == 1:
            abort(
                status.HTTP_400_BAD_REQUEST,
                f"{unsupported[0]} is not a supported filter parameter",
            )
        joined = ", ".join(unsupported)
        abort(
            status.HTTP_400_BAD_REQUEST,
            f"{joined} are not supported filter parameters",
        )

    filters = ItemFilters()
    filters.description = _normalize_description_filter(args.get("description"))

    # Handle sku as alias for product_id (both should be integers)
    product_id_raw = args.get("product_id") or args.get("sku")
    if product_id_raw:
        filters.product_id = _parse_optional_int(
            {"product_id": product_id_raw},
            "product_id",
            "product_id (or sku) must be an integer",
        )

    filters.quantity = _parse_optional_int(
        args, "quantity", "quantity must be an integer"
    )
    if "min_price" in args:
        filters.min_price = _parse_price_bound(args.get("min_price"), "min_price")
    if "max_price" in args:
        filters.max_price = _parse_price_bound(args.get("max_price"), "max_price")

    if (
        filters.min_price is not None
        and filters.max_price is not None
        and filters.min_price > filters.max_price
    ):
        abort(
            status.HTTP_400_BAD_REQUEST,
            "min_price must be less than or equal to max_price",
        )

    # Status filter applies to shopcart, not item
    filters.status = args.get("status")

    return filters


######################################################################
# Resource Classes
######################################################################


@api.route("")
@api.param("shopcart_id", "The Shopcart identifier")
class ItemCollection(Resource):
    """Handles all operations for a collection of Items"""

    @api.doc("list_items")
    @api.param("description", "Filter by description (partial match)", type="string")
    @api.param("product_id", "Filter by product ID", type="integer")
    @api.param("sku", "Filter by SKU (alias for product_id, must be integer)", type="integer")
    @api.param("status", "Filter by shopcart status", type="string")
    @api.param("quantity", "Filter by quantity", type="integer")
    @api.param("min_price", "Filter by minimum price", type="number")
    @api.param("max_price", "Filter by maximum price", type="number")
    @api.marshal_list_with(item_model, code=status.HTTP_200_OK)
    @api.response(404, "Shopcart not found", message_model)
    @api.response(400, "Bad Request", message_model)
    def get(self, shopcart_id):
        """List all items in a shopcart with optional filters"""
        app.logger.info(f"Request to list all items in shopcart {shopcart_id}")

        # Find the shopcart by ID
        shopcart = Shopcart.find(shopcart_id)
        if not shopcart:
            abort(
                status.HTTP_404_NOT_FOUND,
                f"Shopcart with id '{shopcart_id}' was not found.",
            )

        filters = _parse_item_filters(request.args)
        query = ShopcartItem.find_by_shopcart_id(shopcart.id)

        # Apply shopcart status filter if provided
        if filters.status is not None:
            status_norm = str(filters.status).strip().lower()
            if status_norm != shopcart.status.lower():
                # Return empty list if shopcart status doesn't match
                return [], status.HTTP_200_OK

        if filters.description is not None:
            query = query.filter(ShopcartItem.description.ilike(f"%{filters.description}%"))
        if filters.product_id is not None:
            query = query.filter(ShopcartItem.product_id == filters.product_id)
        if filters.quantity is not None:
            query = query.filter(ShopcartItem.quantity == filters.quantity)
        if filters.min_price is not None:
            query = query.filter(ShopcartItem.price >= filters.min_price)
        if filters.max_price is not None:
            query = query.filter(ShopcartItem.price <= filters.max_price)

        # Convert to list of dicts
        items = query.order_by(ShopcartItem.id).all()
        results = [item.serialize() for item in items]
        return results, status.HTTP_200_OK

    @api.doc("create_item")
    @api.expect(item_create_model)
    @api.marshal_with(item_model, code=status.HTTP_201_CREATED)
    @api.response(400, "Bad Request", message_model)
    @api.response(404, "Shopcart not found", message_model)
    @api.response(500, "Internal Server Error", message_model)
    def post(self, shopcart_id):
        """Add an Item to a Shopcart"""
        app.logger.info("Request to add item to shopcart %s", shopcart_id)

        # Find the shopcart by ID
        shopcart = Shopcart.find(shopcart_id)
        if not shopcart:
            abort(
                status.HTTP_404_NOT_FOUND,
                f"Shopcart with id '{shopcart_id}' was not found.",
            )

        payload = request.get_json() or {}
        product_id = _require_product_id(payload)
        increment = _require_quantity_increment(payload)

        existing_item = next(
            (item for item in shopcart.items if item.product_id == product_id),
            None,
        )

        price = _resolve_price(existing_item, payload.get("price"))
        quantity = increment + (existing_item.quantity if existing_item else 0)
        description = _resolve_description(existing_item, payload)

        shopcart.upsert_item(
            product_id=product_id,
            quantity=quantity,
            price=price,
            description=description,
        )
        shopcart.last_modified = datetime.utcnow()
        shopcart.update()

        updated_item = next(
            (item for item in shopcart.items if item.product_id == product_id), None
        )
        if not updated_item:
            abort(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "Unable to persist cart item.",
            )

        return updated_item.serialize(), status.HTTP_201_CREATED


@api.route("/<int:item_id>")
@api.param("shopcart_id", "The Shopcart identifier")
@api.param("item_id", "The Item identifier")
class ItemResource(Resource):
    """Handles all operations for a single Item"""

    @api.doc("get_item")
    @api.marshal_with(item_model, code=status.HTTP_200_OK)
    @api.response(404, "Shopcart or Item not found", message_model)
    def get(self, shopcart_id, item_id):
        """Read an item from a shopcart"""
        app.logger.info(
            f"Request to read item {item_id} from shopcart {shopcart_id}"
        )

        # Find the shopcart by ID
        shopcart = Shopcart.find(shopcart_id)
        if not shopcart:
            abort(
                status.HTTP_404_NOT_FOUND,
                f"Shopcart with id '{shopcart_id}' was not found.",
            )

        # Find the item by ID
        item = ShopcartItem.find(item_id)
        if not item:
            abort(
                status.HTTP_404_NOT_FOUND,
                f"Item with id '{item_id}' was not found.",
            )

        # Verify the item belongs to this shopcart
        if item.shopcart_id != shopcart.id:
            abort(
                status.HTTP_404_NOT_FOUND,
                f"Item with id '{item_id}' not found in shopcart '{shopcart_id}'.",
            )

        return item.serialize(), status.HTTP_200_OK

    @api.doc("update_item")
    @api.expect(item_update_model)
    @api.marshal_with(item_model, code=status.HTTP_200_OK)
    @api.response(400, "Bad Request", message_model)
    @api.response(404, "Shopcart or Item not found", message_model)
    @api.response(409, "Conflict", message_model)
    def put(self, shopcart_id, item_id):
        """Update an item in a shopcart"""
        app.logger.info(
            f"Request to update item {item_id} in shopcart {shopcart_id}"
        )

        shopcart, item = _validate_shopcart_and_item(shopcart_id, item_id)
        _check_shopcart_status(shopcart)

        payload = request.get_json() or {}
        q = _parse_quantity_for_update(payload, item)

        if q == 0:
            shopcart.remove_item(item.product_id)
            shopcart.update()
            return "", status.HTTP_204_NO_CONTENT

        price = _parse_price_for_update(payload, item)
        desc = payload.get("description", item.description or "")
        shopcart.upsert_item(
            product_id=item.product_id, quantity=q, price=price, description=desc
        )
        shopcart.update()

        updated_item = ShopcartItem.find(item_id)
        if not updated_item:
            abort(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "Unable to retrieve updated item.",
            )

        return updated_item.serialize(), status.HTTP_200_OK

    @api.doc("delete_item")
    @api.response(204, "Item deleted successfully")
    @api.response(404, "Shopcart or Item not found", message_model)
    def delete(self, shopcart_id, item_id):
        """Delete an existing item from a shopcart"""
        app.logger.info(
            f"Request to delete item {item_id} from shopcart {shopcart_id}"
        )

        # Find the shopcart by ID
        shopcart = Shopcart.find(shopcart_id)
        if not shopcart:
            abort(
                status.HTTP_404_NOT_FOUND,
                f"Shopcart with id '{shopcart_id}' was not found.",
            )

        # Find the item by ID
        item = ShopcartItem.find(item_id)
        if not item:
            abort(
                status.HTTP_404_NOT_FOUND,
                f"Item with id '{item_id}' was not found.",
            )

        # Verify the item belongs to this shopcart
        if item.shopcart_id != shopcart.id:
            abort(
                status.HTTP_404_NOT_FOUND,
                f"Item with id '{item_id}' not found in shopcart '{shopcart_id}'.",
            )

        # Remove the item and persist
        shopcart.remove_item(item.product_id)
        shopcart.last_modified = datetime.utcnow()
        shopcart.update()
        app.logger.info(
            "Item %s deleted successfully from shopcart %s",
            item_id,
            shopcart_id,
        )

        return "", status.HTTP_204_NO_CONTENT
