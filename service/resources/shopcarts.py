"""Flask-RESTX resources for shopcart operations."""

# pylint: disable=too-few-public-methods,missing-function-docstring,inconsistent-return-statements

import decimal
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from flask import request
from flask_restx import Namespace, Resource, abort, fields
from sqlalchemy import func

from service.common import status
from service.models import Shopcart, ShopcartItem
from service.routes import check_content_type


######################################################################
# Custom Exceptions for Better Testability
######################################################################
class ValidationError(Exception):
    """Custom exception for validation errors that can be easily tested."""

    def __init__(self, status_code, message):
        self.status_code = status_code
        self.message = message
        super().__init__(self.message)


class NotFoundError(ValidationError):
    """Exception for resource not found errors."""

    def __init__(self, message):
        super().__init__(status.HTTP_404_NOT_FOUND, message)


ns = Namespace("shopcarts", path="/shopcarts", description="Shopcart operations")

# ---------------------------------------------------------------------------
# Swagger models
# ---------------------------------------------------------------------------
message_model = ns.model(
    "Message",
    {
        "status": fields.Integer(example=400),
        "error": fields.String(example="Bad Request"),
        "message": fields.String(example="Invalid payload."),
    },
)

shopcart_item_payload = ns.model(
    "ShopcartItemPayload",
    {
        "product_id": fields.Integer(required=False, example=42),
        "quantity": fields.Integer(required=False, example=1),
        "price": fields.Float(required=False, example=9.99),
        "description": fields.String(required=False, example="Eco-friendly mug"),
    },
)

shopcart_item_model = ns.model(
    "ShopcartItem",
    {
        "id": fields.Integer(readonly=True, description="Item identifier"),
        "shopcart_id": fields.Integer(description="Parent shopcart id"),
        "product_id": fields.Integer(required=True, example=123),
        "description": fields.String(example="Coffee mug"),
        "quantity": fields.Integer(required=True, example=2),
        "price": fields.Float(required=True, example=12.99),
    },
)

shopcart_model = ns.model(
    "Shopcart",
    {
        "id": fields.Integer(readonly=True),
        "customer_id": fields.Integer(required=True, example=1001),
        "name": fields.String(example="Holiday cart"),
        "created_date": fields.String(example="2024-01-01T12:00:00Z"),
        "last_modified": fields.String(example="2024-01-02T12:00:00Z"),
        "status": fields.String(example="active"),
        "total_items": fields.Integer(example=3),
        "items": fields.List(fields.Nested(shopcart_item_model)),
    },
)

shopcart_create_model = ns.model(
    "ShopcartCreate",
    {
        "customer_id": fields.Integer(required=True, example=888),
        "status": fields.String(default="active", example="active"),
        "name": fields.String(example="My cart"),
        "items": fields.List(fields.Nested(shopcart_item_payload)),
    },
)

shopcart_update_model = ns.model(
    "ShopcartUpdate",
    {
        "status": fields.String(example="abandoned"),
        "items": fields.List(fields.Nested(shopcart_item_payload)),
    },
)

shopcart_customer_item_model = ns.model(
    "ShopcartCustomerItem",
    {
        "itemId": fields.Integer(example=1),
        "productId": fields.Integer(example=10),
        "description": fields.String(example="Paper clips"),
        "quantity": fields.Integer(example=1),
        "price": fields.Float(example=1.99),
    },
)

shopcart_customer_view_model = ns.model(
    "ShopcartCustomerView",
    {
        "customerId": fields.Integer(example=888),
        "name": fields.String(example="My cart"),
        "createdDate": fields.String(example="2024-01-01T12:00:00Z"),
        "lastModified": fields.String(example="2024-01-02T12:00:00Z"),
        "status": fields.String(example="active"),
        "totalItems": fields.Integer(example=2),
        "totalPrice": fields.Float(example=19.98),
        "items": fields.List(fields.Nested(shopcart_customer_item_model)),
    },
)

totals_model = ns.model(
    "ShopcartTotals",
    {
        "customer_id": fields.Integer(example=123),
        "item_count": fields.Integer(example=2),
        "total_quantity": fields.Integer(example=3),
        "subtotal": fields.Float(example=29.97),
        "discount": fields.Float(example=0.0),
        "total": fields.Float(example=29.97),
    },
)


def _get_cart_or_404(customer_id: int) -> Shopcart:
    cart = Shopcart.find_by_customer_id(customer_id).first()
    if not cart:
        abort(
            status.HTTP_404_NOT_FOUND,
            message=f"Shopcart for customer '{customer_id}' was not found.",
        )
    return cart


def _resolve_description(existing_item, payload):
    """Select description, defaulting to the existing entry."""
    base = existing_item.description if existing_item else ""
    return payload.get("description", base or "")


def _find_item_by_product_or_id(
    shopcart: Shopcart, product_id: int
) -> ShopcartItem | None:
    """Find item by product_id or item.id."""
    # Try finding by product_id first
    item = next(
        (it for it in shopcart.items if int(it.product_id) == int(product_id)), None
    )
    if item is None:
        # Try finding by item.id in case the route was matched incorrectly
        item = ShopcartItem.find(product_id)
        if item and item.shopcart_id != shopcart.id:
            item = None
    return item


def _parse_quantity_from_payload(payload, current_item: ShopcartItem) -> int:
    """Parse and validate quantity from payload."""
    q_raw = payload.get("quantity", current_item.quantity)
    try:
        q = int(q_raw)
    except (TypeError, ValueError):
        abort(status.HTTP_400_BAD_REQUEST, message="quantity must be an integer.")
    if q < 0 or q > 99:
        abort(status.HTTP_400_BAD_REQUEST, message="invalid quantity")
    return q


def _parse_price_from_payload(payload, current_item: ShopcartItem) -> Decimal:
    """Parse and validate price from payload."""
    price_raw = payload.get("price", float(current_item.price))
    try:
        return Decimal(str(price_raw))
    except (decimal.InvalidOperation, ValueError, TypeError):
        abort(status.HTTP_400_BAD_REQUEST, message="price is invalid.")


def _find_shopcart_by_id_or_customer(customer_id):
    """Find shopcart by customer_id first, then by shopcart.id."""
    shopcart = Shopcart.find_by_customer_id(customer_id).first()
    if not shopcart:
        shopcart = Shopcart.find(customer_id)
    if not shopcart:
        raise NotFoundError(f"Shopcart for customer '{customer_id}' was not found.")
    return shopcart


def _require_product_id_from_payload(payload):
    """Extract and validate product_id from payload."""
    try:
        return int(payload["product_id"])
    except (KeyError, TypeError, ValueError):
        raise ValidationError(
            status.HTTP_400_BAD_REQUEST,
            "product_id is required and must be an integer.",
        )


def _require_quantity_increment_from_payload(payload):
    """Validate quantity increment from payload."""
    try:
        increment = int(payload.get("quantity", 0))
    except (TypeError, ValueError):
        raise ValidationError(
            status.HTTP_400_BAD_REQUEST, "quantity must be an integer."
        )
    if increment <= 0:
        raise ValidationError(
            status.HTTP_400_BAD_REQUEST,
            "quantity must be a positive integer.",
        )
    return increment


def _resolve_price_for_new_item(existing_item, price_raw):
    """Resolve the price for the incoming payload."""
    if existing_item and price_raw is None:
        return Decimal(str(existing_item.price))
    if price_raw is None:
        raise ValidationError(status.HTTP_400_BAD_REQUEST, "price is required.")
    try:
        return Decimal(str(price_raw))
    except (decimal.InvalidOperation, ValueError, TypeError):
        raise ValidationError(status.HTTP_400_BAD_REQUEST, "price is invalid.")


def _find_existing_item(shopcart, product_id):
    """Find existing item by product_id in shopcart."""
    return next(
        (item for item in shopcart.items if item.product_id == product_id),
        None,
    )


def _validate_shopcart_status_for_update(shopcart: Shopcart):
    """Validate that shopcart status allows updates."""
    status_norm = (
        shopcart.status.strip().lower()
        if isinstance(shopcart.status, str)
        else "active"
    )
    if status_norm == "abandoned":
        abort(
            status.HTTP_409_CONFLICT,
            message="Cannot update items on an abandoned shopcart.",
        )


def _check_if_product_id_is_item_id(product_id: int) -> bool:
    """Check if product_id is actually an item_id."""
    item_by_id = ShopcartItem.find(product_id)
    # If find returns an item, its id must equal product_id (find searches by id)
    return item_by_id is not None


def _handle_zero_quantity_update(shopcart: Shopcart, current: ShopcartItem):
    """Handle the case when quantity is set to 0 (remove item)."""
    shopcart.remove_item(current.product_id)
    shopcart.update()
    return shopcart.serialize(), status.HTTP_200_OK


def _update_shopcart_item(
    shopcart: Shopcart,
    current: ShopcartItem,
    quantity: int,
    price: Decimal,
    description: str,
):
    """Update shopcart item with new values."""
    shopcart.upsert_item(
        product_id=current.product_id,
        quantity=quantity,
        price=price,
        description=description,
    )
    shopcart.update()


def _get_update_response(shopcart: Shopcart, product_id: int, is_item_id: bool):
    """Get the appropriate response after updating an item."""
    if is_item_id:
        updated_item = ShopcartItem.find(product_id)
        if updated_item and updated_item.shopcart_id == shopcart.id:
            return updated_item.serialize(), status.HTTP_200_OK
    return shopcart.serialize(), status.HTTP_200_OK


def _parse_decimal(value: str, field: str) -> Decimal:
    """Parse a decimal value from query parameters."""
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValidationError(
            status.HTTP_400_BAD_REQUEST,
            f"{field} must be a non-empty decimal value when provided.",
        )
    try:
        return Decimal(cleaned)
    except (decimal.InvalidOperation, ValueError):
        raise ValidationError(
            status.HTTP_400_BAD_REQUEST,
            f"{field} must be a valid decimal number: {value}",
        )


def _compute_cart_total(cart: Shopcart) -> Decimal:
    """Calculate the total price for a shopcart."""
    total = Decimal("0")
    for item in getattr(cart, "items", []):
        quantity = int(getattr(item, "quantity", 0) or 0)
        price = (
            item.price
            if isinstance(item.price, Decimal)
            else Decimal(str(item.price or 0))
        )
        total += price * quantity
    return total


STATUS_ALIAS_MAP = {
    "open": "active",  # OPEN maps to active (for backward compatibility)
    "active": "active",
    "closed": "abandoned",  # CLOSED maps to abandoned (for backward compatibility)
    "abandoned": "abandoned",
    "purchased": "locked",  # PURCHASED maps to locked
    "locked": "locked",
    "merged": "expired",  # MERGED maps to expired
    "expired": "expired",
}


@dataclass
class CartFilters:
    """Container for list endpoint filters."""

    status: str | None = None
    customer_id: int | None = None
    created_before: datetime | None = None
    created_after: datetime | None = None
    max_total: Decimal | None = None
    min_total: Decimal | None = None


def _parse_status_filter(value) -> str | None:
    """Normalize and validate a status filter."""
    if value is None:
        return None
    normalized = str(value).strip().upper()
    if not normalized:
        raise ValidationError(
            status.HTTP_400_BAD_REQUEST,
            "status must be a non-empty value when provided.",
        )
    normalized_lower = normalized.lower()
    if normalized_lower in STATUS_ALIAS_MAP:
        return STATUS_ALIAS_MAP[normalized_lower]

    allowed_statuses = Shopcart.allowed_statuses()
    friendly_names = {"OPEN", "CLOSED", "PURCHASED", "MERGED"}
    all_valid_statuses = sorted(
        allowed_statuses | {s.upper() for s in allowed_statuses} | friendly_names
    )
    readable_statuses = ", ".join(all_valid_statuses)
    raise ValidationError(
        status.HTTP_400_BAD_REQUEST,
        f"Invalid status '{value}'. Allowed values: {readable_statuses}.",
    )


def _parse_customer_id_filter(value) -> int | None:
    """Parse a customer_id filter."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValidationError(
            status.HTTP_400_BAD_REQUEST,
            "customer_id must be an integer when provided.",
        )


def _parse_optional_datetime(value, field: str) -> datetime | None:
    """Parse an ISO8601 timestamp when provided."""
    if value is None:
        return None
    return _parse_iso8601_to_utc(value, field)


def _parse_list_filters(args) -> CartFilters:
    """Extract and validate query parameters for the list endpoint."""
    filters = CartFilters()
    filters.status = _parse_status_filter(args.get("status"))
    filters.customer_id = _parse_customer_id_filter(args.get("customer_id"))
    filters.created_before = _parse_optional_datetime(
        args.get("created_before"), "created_before"
    )
    filters.created_after = _parse_optional_datetime(
        args.get("created_after"), "created_after"
    )
    max_total_raw = args.get("max_total")
    max_field = "max_total"
    if max_total_raw is None:
        max_total_raw = args.get("total_price_lt")
        if max_total_raw is not None:
            max_field = "total_price_lt"
    if max_total_raw is not None:
        filters.max_total = _parse_decimal(max_total_raw, max_field)

    min_total_raw = args.get("min_total")
    min_field = "min_total"
    if min_total_raw is None:
        min_total_raw = args.get("total_price_gt")
        if min_total_raw is not None:
            min_field = "total_price_gt"
    if min_total_raw is not None:
        filters.min_total = _parse_decimal(min_total_raw, min_field)

    if (
        filters.max_total is not None
        and filters.min_total is not None
        and filters.max_total < filters.min_total
    ):
        abort(
            status.HTTP_400_BAD_REQUEST,
            message="max_total must be greater than or equal to min_total.",
        )
    return filters


def _filter_by_total_price(
    shopcarts, min_total: Decimal | None, max_total: Decimal | None
):
    """Filter shopcarts in-memory according to total price bounds."""
    if min_total is None and max_total is None:
        return shopcarts

    filtered = []
    for cart in shopcarts:
        total_amount = _compute_cart_total(cart)
        if max_total is not None and total_amount > max_total:
            continue
        if min_total is not None and total_amount < min_total:
            continue
        filtered.append(cart)
    return filtered


ITEM_FILTER_FIELDS = {"description", "product_id", "min_price", "max_price", "quantity"}


@dataclass
class ItemFilters:
    """Container for shopcart item filters."""

    description: str | None = None
    product_id: int | None = None
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    quantity: int | None = None


def _parse_price_bound(value: str, field: str) -> Decimal:
    """Parse a numeric price boundary from the request."""
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValidationError(status.HTTP_400_BAD_REQUEST, f"{field} must be a number")
    try:
        return Decimal(cleaned)
    except (decimal.InvalidOperation, ValueError, TypeError):
        raise ValidationError(status.HTTP_400_BAD_REQUEST, f"{field} must be a number")


def _normalize_description_filter(value) -> str | None:
    """Normalize a description filter, validating non-empty input."""
    if value is None:
        return None
    description = str(value).strip()
    if not description:
        raise ValidationError(
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
        raise ValidationError(status.HTTP_400_BAD_REQUEST, error_message)


def _parse_item_filters(args) -> ItemFilters:
    """Validate and normalize query params for item listing."""
    unsupported = sorted(set(args.keys()) - ITEM_FILTER_FIELDS)
    if unsupported:
        if len(unsupported) == 1:
            raise ValidationError(
                status.HTTP_400_BAD_REQUEST,
                f"{unsupported[0]} is not a supported filter parameter",
            )
        joined = ", ".join(unsupported)
        raise ValidationError(
            status.HTTP_400_BAD_REQUEST,
            f"{joined} are not supported filter parameters",
        )

    filters = ItemFilters()
    filters.description = _normalize_description_filter(args.get("description"))
    filters.product_id = _parse_optional_int(
        args, "product_id", "product_id must be an integer"
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
        raise ValidationError(
            status.HTTP_400_BAD_REQUEST,
            "min_price must be less than or equal to max_price",
        )

    return filters


def _parse_iso8601_to_utc(value: str, field: str) -> datetime:
    """Parse an ISO8601 string into a UTC naive datetime for database comparison."""
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValidationError(
            status.HTTP_400_BAD_REQUEST,
            f"{field} must be a non-empty ISO8601 timestamp when provided.",
        )
    normalized = cleaned.replace("Z", "+00:00").replace(" ", "+")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        raise ValidationError(
            status.HTTP_400_BAD_REQUEST,
            f"{field} must be a valid ISO8601 timestamp: {cleaned}",
        )
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    utc_value = parsed.astimezone(timezone.utc)
    return utc_value.replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------
@ns.route("")
class ShopcartCollectionResource(Resource):
    """Handles /shopcarts endpoint operations."""

    @ns.doc(
        "list_shopcarts",
        params={
            "status": "Filter by status (active, abandoned, locked, expired, OPEN/CLOSED/PURCHASED/MERGED aliases)",
            "customer_id": "Filter by customer id",
            "created_before": "ISO8601 timestamp upper bound",
            "created_after": "ISO8601 timestamp lower bound",
            "max_total": "Maximum total (or total_price_lt alias)",
            "min_total": "Minimum total (or total_price_gt alias)",
        },
    )
    @ns.marshal_list_with(shopcart_model)
    def get(self):
        """Retrieve Shopcarts, optionally filtered by status and customer_id."""
        try:
            filters = _parse_list_filters(request.args)
            query = Shopcart.query
            if filters.status is not None:
                query = query.filter(func.lower(Shopcart.status) == filters.status)
            if filters.customer_id is not None:
                query = query.filter(Shopcart.customer_id == filters.customer_id)
            if filters.created_before is not None:
                query = query.filter(Shopcart.created_date <= filters.created_before)
            if filters.created_after is not None:
                query = query.filter(Shopcart.created_date >= filters.created_after)

            shopcarts = _filter_by_total_price(
                query.all(), filters.min_total, filters.max_total
            )
            return [cart.serialize() for cart in shopcarts], status.HTTP_200_OK
        except NotFoundError as e:
            abort(e.status_code, message=e.message)
        except ValidationError as e:
            abort(e.status_code, message=e.message)

    @ns.expect(shopcart_create_model, validate=True)
    @ns.marshal_with(shopcart_model, code=status.HTTP_201_CREATED)
    @ns.response(status.HTTP_409_CONFLICT, "Shopcart already exists", message_model)
    def post(self):
        """Create a Shopcart."""
        check_content_type("application/json")

        shopcart = Shopcart()
        data = request.get_json()
        shopcart.deserialize(data)

        existing = Shopcart.find_by_customer_id(shopcart.customer_id).first()
        if existing:
            abort(
                status.HTTP_409_CONFLICT,
                message=f"Shopcart for customer '{shopcart.customer_id}' already exists.",
            )

        shopcart.create()
        location_url = f"/api/shopcarts/{shopcart.customer_id}"

        return (
            shopcart.serialize(),
            status.HTTP_201_CREATED,
            {"Location": location_url},
        )


@ns.route("/<int:customer_id>")
@ns.response(status.HTTP_404_NOT_FOUND, "Shopcart not found", message_model)
class ShopcartResource(Resource):
    """Handles /shopcarts/<customer_id> endpoint operations."""

    @ns.marshal_with(shopcart_customer_view_model)
    def get(self, customer_id):
        """Retrieve a single Shopcart for the given customer."""
        shopcart = _get_cart_or_404(customer_id)
        return shopcart.to_customer_view(), status.HTTP_200_OK

    @ns.expect(shopcart_update_model, validate=False)
    @ns.marshal_with(shopcart_model)
    def put(self, customer_id: int):
        """Update the status or items of a shopcart."""
        check_content_type("application/json")
        shopcart = _get_cart_or_404(customer_id)
        data = request.get_json() or {}
        if "status" in data:
            shopcart.status = str(data["status"])
        items = data.get("items")
        if items is not None:
            shopcart.set_items(items)
        shopcart.update()
        return shopcart.serialize(), status.HTTP_200_OK

    @ns.expect(shopcart_update_model, validate=False)
    @ns.marshal_with(shopcart_model)
    def patch(self, customer_id: int):
        """Partial update of a shopcart."""
        return self.put(customer_id)

    @ns.response(status.HTTP_204_NO_CONTENT, "Shopcart deleted")
    def delete(self, customer_id):
        """Delete a Shopcart."""
        shopcart = _get_cart_or_404(customer_id)
        shopcart.delete()
        return "", status.HTTP_204_NO_CONTENT


@ns.route("/<int:customer_id>/checkout")
@ns.response(status.HTTP_404_NOT_FOUND, "Shopcart not found", message_model)
class CheckoutResource(Resource):
    """Handles checkout operations."""

    @ns.marshal_with(shopcart_model)
    def put(self, customer_id: int):
        """Change the status to abandoned and refresh last_modified."""
        shopcart = _get_cart_or_404(customer_id)
        shopcart.status = "abandoned"
        shopcart.last_modified = datetime.utcnow()
        shopcart.update()
        return shopcart.serialize(), status.HTTP_200_OK

    @ns.marshal_with(shopcart_model)
    def patch(self, customer_id: int):
        """Alias for PUT checkout."""
        return self.put(customer_id)  # pragma: no cover


@ns.route("/<int:customer_id>/cancel")
@ns.response(status.HTTP_404_NOT_FOUND, "Shopcart not found", message_model)
class CancelResource(Resource):
    """Mark the specified shopcart as abandoned."""

    @ns.marshal_with(shopcart_model)
    def patch(self, customer_id: int):
        shopcart = _get_cart_or_404(customer_id)
        current_status = (shopcart.status or "").strip().lower()
        if current_status != "abandoned":
            shopcart.status = "abandoned"
            shopcart.last_modified = datetime.utcnow()
            shopcart.update()
        return shopcart.serialize(), status.HTTP_200_OK


@ns.route("/<int:customer_id>/lock")
@ns.response(status.HTTP_404_NOT_FOUND, "Shopcart not found", message_model)
class LockResource(Resource):
    """Mark the specified shopcart as locked."""

    @ns.marshal_with(shopcart_model)
    def patch(self, customer_id: int):
        shopcart = _get_cart_or_404(customer_id)
        current_status = (shopcart.status or "").strip().lower()
        if current_status != "locked":
            shopcart.status = "locked"
            shopcart.last_modified = datetime.utcnow()
            shopcart.update()
        return shopcart.serialize(), status.HTTP_200_OK


@ns.route("/<int:customer_id>/expire")
@ns.response(status.HTTP_404_NOT_FOUND, "Shopcart not found", message_model)
class ExpireResource(Resource):
    """Mark the specified shopcart as expired."""

    @ns.marshal_with(shopcart_model)
    def patch(self, customer_id: int):
        shopcart = _get_cart_or_404(customer_id)
        current_status = (shopcart.status or "").strip().lower()
        if current_status != "expired":
            shopcart.status = "expired"
            shopcart.last_modified = datetime.utcnow()
            shopcart.update()
        return shopcart.serialize(), status.HTTP_200_OK


@ns.route("/<int:customer_id>/reactivate")
@ns.response(status.HTTP_404_NOT_FOUND, "Shopcart not found", message_model)
class ReactivateResource(Resource):
    """Reactivate an abandoned shopcart."""

    @ns.marshal_with(shopcart_model)
    def patch(self, customer_id: int):
        shopcart = _get_cart_or_404(customer_id)
        current_status = (shopcart.status or "").strip().lower()
        if current_status != "active":
            shopcart.status = "active"
            shopcart.last_modified = datetime.utcnow()
            shopcart.update()
        return shopcart.serialize(), status.HTTP_200_OK


@ns.route("/<int:customer_id>/items")
@ns.response(status.HTTP_404_NOT_FOUND, "Shopcart not found", message_model)
class ShopcartItemsCollectionResource(Resource):
    """Manage items within a shopcart."""

    @ns.expect(shopcart_item_payload)
    @ns.marshal_with(shopcart_item_model, code=status.HTTP_201_CREATED)
    def post(self, customer_id):
        """Add an item to a shopcart."""
        try:
            check_content_type("application/json")
            shopcart = _find_shopcart_by_id_or_customer(customer_id)

            payload = request.get_json() or {}
            product_id = _require_product_id_from_payload(payload)
            increment = _require_quantity_increment_from_payload(payload)
            existing_item = _find_existing_item(shopcart, product_id)

            price = _resolve_price_for_new_item(existing_item, payload.get("price"))
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

            updated_item = _find_existing_item(shopcart, product_id)
            if not updated_item:
                abort(
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message="Unable to persist cart item.",
                )

            return updated_item.serialize(), status.HTTP_201_CREATED
        except NotFoundError as e:
            abort(e.status_code, message=e.message)
        except ValidationError as e:
            abort(e.status_code, message=e.message)

    @ns.doc(
        "list_shopcart_items",
        params={
            "description": "Substring match on item description",
            "product_id": "Exact product id",
            "quantity": "Exact quantity",
            "min_price": "Minimum price",
            "max_price": "Maximum price",
        },
    )
    @ns.marshal_list_with(shopcart_item_model)
    def get(self, customer_id):
        """List all items in a customer's shopcart."""
        try:
            # Try finding by customer_id first, then by shopcart.id
            shopcart = Shopcart.find_by_customer_id(customer_id).first()
            if not shopcart:
                shopcart = Shopcart.find(customer_id)
            if not shopcart:
                raise NotFoundError(
                    f"Shopcart for customer '{customer_id}' was not found."
                )

            filters = _parse_item_filters(request.args)
            query = ShopcartItem.find_by_shopcart_id(shopcart.id)
            if filters.description is not None:
                query = query.filter(
                    ShopcartItem.description.ilike(f"%{filters.description}%")
                )
            if filters.product_id is not None:
                query = query.filter(ShopcartItem.product_id == filters.product_id)
            if filters.quantity is not None:
                query = query.filter(ShopcartItem.quantity == filters.quantity)
            if filters.min_price is not None:
                query = query.filter(ShopcartItem.price >= filters.min_price)
            if filters.max_price is not None:
                query = query.filter(ShopcartItem.price <= filters.max_price)

            items = query.order_by(ShopcartItem.id).all()
            results = [item.serialize() for item in items]
            return results, status.HTTP_200_OK
        except NotFoundError as e:
            abort(e.status_code, message=e.message)
        except ValidationError as e:
            abort(e.status_code, message=e.message)


@ns.route("/<int:customer_id>/items/<int:product_id>")
@ns.response(status.HTTP_404_NOT_FOUND, "Shopcart not found", message_model)
class ShopcartItemResource(Resource):
    """Manage a specific item within a shopcart."""

    @ns.marshal_with(shopcart_item_model)
    def get(self, customer_id, product_id):
        """Read an item from a shopcart."""
        try:
            # Try finding by customer_id first, then by shopcart.id
            shopcart = Shopcart.find_by_customer_id(customer_id).first()
            if not shopcart:
                shopcart = Shopcart.find(customer_id)
            if not shopcart:
                raise NotFoundError(
                    f"Shopcart for customer '{customer_id}' was not found."
                )
            # Try finding by product_id first, then by item.id
            item = next(
                (entry for entry in shopcart.items if entry.product_id == product_id),
                None,
            )
            if not item:
                # Try finding by item.id in case the route was matched incorrectly
                item = ShopcartItem.find(product_id)
                if item and item.shopcart_id != shopcart.id:
                    item = None
            if not item:
                raise NotFoundError(
                    f"Product with id {product_id} not found in this shopcart"
                )
            return item.serialize(), status.HTTP_200_OK
        except NotFoundError as e:
            abort(e.status_code, message=e.message)
        except ValidationError as e:
            abort(e.status_code, message=e.message)

    @ns.expect(shopcart_item_payload, validate=True)
    @ns.marshal_with(shopcart_model)
    @ns.response(
        status.HTTP_409_CONFLICT, "Cart status does not allow updates", message_model
    )
    def put(self, customer_id: int, product_id: int):
        """Update a single item in a shopcart."""
        # First try to find by customer_id
        shopcart = Shopcart.find_by_customer_id(customer_id).first()

        # If not found by customer_id, try by shopcart.id
        # But if found by shopcart.id and customer_id doesn't match, this is a shopcart_id route
        if not shopcart:
            shopcart = Shopcart.find(customer_id)
            if shopcart and shopcart.customer_id != customer_id:
                # This is a shopcart_id route, not a customer_id route
                # Return 404 to let Flask try the next matching route (items route)
                abort(
                    status.HTTP_404_NOT_FOUND,
                    message=f"Shopcart for customer '{customer_id}' was not found.",
                )

        if not shopcart:
            abort(
                status.HTTP_404_NOT_FOUND,
                message=f"Shopcart for customer '{customer_id}' was not found.",
            )

        check_content_type("application/json")
        payload = request.get_json() or {}

        _validate_shopcart_status_for_update(shopcart)

        current = _find_item_by_product_or_id(shopcart, product_id)
        if current is None:
            abort(
                status.HTTP_404_NOT_FOUND,
                message=f"Item with product_id '{product_id}' not found in this shopcart.",
            )

        q = _parse_quantity_from_payload(payload, current)
        if q == 0:
            return _handle_zero_quantity_update(shopcart, current)

        price = _parse_price_from_payload(payload, current)
        desc = payload.get("description", current.description or "")
        is_item_id = _check_if_product_id_is_item_id(product_id)

        _update_shopcart_item(shopcart, current, q, price, desc)
        return _get_update_response(shopcart, product_id, is_item_id)

    @ns.expect(shopcart_item_payload, validate=True)
    @ns.marshal_with(shopcart_model)
    @ns.response(
        status.HTTP_409_CONFLICT, "Cart status does not allow updates", message_model
    )
    def patch(self, customer_id: int, product_id: int):
        """Partial update of a shopcart item."""
        return self.put(customer_id, product_id)

    @ns.response(status.HTTP_204_NO_CONTENT, "Item deleted")
    def delete(self, customer_id, product_id):
        """Delete an existing item from a shopcart."""
        try:
            # Try finding by customer_id first, then by shopcart.id
            shopcart = Shopcart.find_by_customer_id(customer_id).first()
            if not shopcart:
                shopcart = Shopcart.find(customer_id)
            if not shopcart:
                raise NotFoundError(
                    f"Shopcart for customer '{customer_id}' was not found."
                )
            # Try finding by product_id first, then by item.id
            item = next(
                (entry for entry in shopcart.items if entry.product_id == product_id),
                None,
            )
            if not item:
                # Try finding by item.id in case the route was matched incorrectly
                item = ShopcartItem.find(product_id)
                if item and item.shopcart_id != shopcart.id:
                    item = None
            if not item:
                raise NotFoundError(
                    f"Product with id {product_id} not found in this shopcart"
                )

            shopcart.remove_item(item.product_id)
            shopcart.last_modified = datetime.utcnow()
            shopcart.update()

            return "", status.HTTP_204_NO_CONTENT
        except NotFoundError as e:
            abort(e.status_code, message=e.message)
        except ValidationError as e:
            abort(e.status_code, message=e.message)


@ns.route("/<int:customer_id>/totals")
@ns.response(status.HTTP_404_NOT_FOUND, "Shopcart not found", message_model)
class ShopcartTotalsResource(Resource):
    """Return aggregated totals for a customer's shopcart."""

    @ns.marshal_with(totals_model)
    def get(self, customer_id: int):
        shopcart = _get_cart_or_404(customer_id)

        total_quantity = 0
        subtotal = Decimal("0")
        for item in getattr(shopcart, "items", []):
            quantity = int(getattr(item, "quantity", 0) or 0)
            price = (
                item.price
                if isinstance(item.price, Decimal)
                else Decimal(str(item.price or 0))
            )
            total_quantity += quantity
            subtotal += price * quantity

        discount = Decimal("0")
        aggregate = {
            "customer_id": customer_id,
            "item_count": len(getattr(shopcart, "items", [])),
            "total_quantity": total_quantity,
            "subtotal": float(subtotal),
            "discount": float(discount),
            "total": float(subtotal - discount),
        }
        return aggregate, status.HTTP_200_OK
