######################################################################
# Copyright 2016, 2024 John J. Rofrano. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
######################################################################

"""
Shopcart Service

This service implements a REST API that allows you to Create, Read, Update
and Delete Shopcarts
"""

import decimal
from decimal import Decimal
from datetime import datetime, timezone
from dataclasses import dataclass
from flask import jsonify, request, url_for, abort
from flask import current_app as app  # Import Flask application
from sqlalchemy import func
from service.models import Shopcart, ShopcartItem
from service.common import status  # HTTP Status Codes


def _require_product_id(payload):
    """Extract and validate product_id from payload."""
    try:
        return int(payload["product_id"])
    except (KeyError, TypeError, ValueError):
        abort(
            status.HTTP_400_BAD_REQUEST,
            "product_id is required and must be an integer.",
        )


def _require_quantity_increment(payload):
    """Ensure quantity is a positive integer increment."""
    try:
        increment = int(payload.get("quantity", 0))
    except (TypeError, ValueError):
        abort(status.HTTP_400_BAD_REQUEST, "quantity must be an integer.")
    if increment <= 0:
        abort(status.HTTP_400_BAD_REQUEST, "quantity must be a positive integer.")
    return increment


def _resolve_price(existing_item, price_raw):
    """Resolve the price for the incoming payload."""
    if existing_item and price_raw is None:
        return Decimal(str(existing_item.price))
    if price_raw is None:
        abort(status.HTTP_400_BAD_REQUEST, "price is required.")
    try:
        return Decimal(str(price_raw))
    except (decimal.InvalidOperation, ValueError, TypeError):
        abort(status.HTTP_400_BAD_REQUEST, "price is invalid.")


def _resolve_description(existing_item, payload):
    """Select description, defaulting to the existing entry."""
    base = existing_item.description if existing_item else ""
    return payload.get("description", base or "")


def _parse_decimal(value: str, field: str) -> Decimal:
    """Parse a decimal value from query parameters."""
    cleaned = (value or "").strip()
    if not cleaned:
        abort(
            status.HTTP_400_BAD_REQUEST,
            f"{field} must be a non-empty decimal value when provided.",
        )
    try:
        return Decimal(cleaned)
    except (decimal.InvalidOperation, ValueError):
        abort(
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


@dataclass
class CartFilters:
    """Container for list endpoint filters."""

    status: str | None = None
    customer_id: int | None = None
    created_before: datetime | None = None
    created_after: datetime | None = None
    total_price_lt: Decimal | None = None
    total_price_gt: Decimal | None = None


def _parse_status_filter(value) -> str | None:
    """Normalize and validate a status filter."""
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if not normalized:
        abort(
            status.HTTP_400_BAD_REQUEST,
            "status must be a non-empty value when provided.",
        )
    allowed_statuses = Shopcart.allowed_statuses()
    if normalized not in allowed_statuses:
        readable_statuses = ", ".join(sorted(allowed_statuses))
        abort(
            status.HTTP_400_BAD_REQUEST,
            f"Invalid status '{value}'. Allowed values: {readable_statuses}.",
        )
    return normalized


def _parse_customer_id_filter(value) -> int | None:
    """Parse a customer_id filter."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        abort(
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
    total_price_lt_raw = args.get("total_price_lt")
    if total_price_lt_raw is not None:
        filters.total_price_lt = _parse_decimal(total_price_lt_raw, "total_price_lt")
    total_price_gt_raw = args.get("total_price_gt")
    if total_price_gt_raw is not None:
        filters.total_price_gt = _parse_decimal(total_price_gt_raw, "total_price_gt")
    if (
        filters.total_price_lt is not None
        and filters.total_price_gt is not None
        and filters.total_price_lt < filters.total_price_gt
    ):
        abort(
            status.HTTP_400_BAD_REQUEST,
            "total_price_lt must be greater than or equal to total_price_gt.",
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


######################################################################
# HEALTH CHECK ENDPOINT
######################################################################
@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint for Kubernetes"""
    return jsonify({"status": "OK"}), status.HTTP_200_OK


######################################################################
# GET INDEX
######################################################################
@app.route("/", methods=["GET"])
def index():
    """Return basic service metadata in JSON format"""
    response = {
        "description": "This service manages customer shopcarts and their items.",
        "name": "Shopcart REST API Service",
        "version": "1.0.0",
        "paths": {
            "shopcarts": "/shopcarts",
        },
    }
    return jsonify(response), 200


######################################################################
#  R E S T   A P I   E N D P O I N T S
######################################################################


######################################################################
# CREATE A NEW SHOPCART
######################################################################
@app.route("/shopcarts", methods=["POST"])
def create_shopcarts():
    """
    Create a Shopcart
    This endpoint will create a Shopcart based the data in the body that is posted
    """
    app.logger.info("Request to Create a Shopcart...")
    check_content_type("application/json")

    shopcart = Shopcart()
    # Get the data from the request and deserialize it
    data = request.get_json()
    app.logger.info("Processing: %s", data)
    shopcart.deserialize(data)

    # Enforce one cart per customer
    existing = Shopcart.find_by_customer_id(shopcart.customer_id).first()
    if existing:
        abort(
            status.HTTP_409_CONFLICT,
            f"Shopcart for customer '{shopcart.customer_id}' already exists.",
        )

    # Save the new Shopcart to the database
    shopcart.create()
    app.logger.info("Shopcart with new id [%s] saved!", shopcart.id)

    # Return the location of the new Shopcart
    location_url = url_for(
        "get_shopcarts", customer_id=shopcart.customer_id, _external=True
    )

    return (
        jsonify(shopcart.serialize()),
        status.HTTP_201_CREATED,
        {"Location": location_url},
    )


######################################################################
# READ A SHOPCART (Customer)
######################################################################
@app.route("/shopcarts/<int:customer_id>", methods=["GET"])
def get_shopcarts(customer_id):
    """
    Retrieve a single Shopcart for the given customer
    """
    app.logger.info("Request to Retrieve shopcart for customer [%s]", customer_id)

    # Attempt to find the Shopcart and abort if not found
    shopcart = Shopcart.find_by_customer_id(customer_id).first()
    if not shopcart:
        abort(
            status.HTTP_404_NOT_FOUND,
            f"Shopcart for customer '{customer_id}' was not found.",
        )

    response = shopcart.to_customer_view()
    app.logger.info("Returning shopcart for customer: %s", customer_id)
    return jsonify(response), status.HTTP_200_OK


######################################################################
# DELETE A SHOPCART
######################################################################
@app.route("/shopcarts/<int:customer_id>", methods=["DELETE"])
def delete_shopcarts(customer_id):
    """
    Delete a Shopcart

    This endpoint will delete a Shopcart based the id specified in the path
    """
    app.logger.info("Request to Delete a shopcart for customer [%s]", customer_id)

    # Delete the Shopcart if it exists
    shopcart = Shopcart.find_by_customer_id(customer_id).first()
    if shopcart:
        app.logger.info("Shopcart with ID: %d found.", shopcart.id)
        shopcart.delete()

    app.logger.info("Shopcart delete complete for customer: %s.", customer_id)
    return {}, status.HTTP_204_NO_CONTENT


######################################################################
# Checks the ContentType of a request
######################################################################
def check_content_type(content_type) -> None:
    """Checks that the media type is correct"""
    if "Content-Type" not in request.headers:
        app.logger.error("No Content-Type specified.")
        abort(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"Content-Type must be {content_type}",
        )

    if request.headers["Content-Type"] == content_type:
        return

    app.logger.error("Invalid Content-Type: %s", request.headers["Content-Type"])
    abort(
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        f"Content-Type must be {content_type}",
    )


######################################################################
# UPDATE A SHOPCART
######################################################################
@app.route("/shopcarts/<int:customer_id>", methods=["PUT", "PATCH"])
def update_shopcart(customer_id: int):
    """
    Update the status of a shopcart
    """
    check_content_type("application/json")
    shopcart = Shopcart.find_by_customer_id(customer_id).first()
    if not shopcart:
        abort(
            status.HTTP_404_NOT_FOUND,
            f"Shopcart for customer '{customer_id}' was not found.",
        )
    data = request.get_json() or {}
    if "status" in data:
        shopcart.status = str(data["status"])
    items = data.get("items")
    if items is not None:
        shopcart.set_items(items)
    shopcart.update()
    return jsonify(shopcart.serialize()), status.HTTP_200_OK


######################################################################
# CHECKOUT A SHOPCART
######################################################################
@app.route("/shopcarts/<int:customer_id>/checkout", methods=["PUT", "PATCH"])
def checkout_shopcart(customer_id: int):
    """
    Change the status to "abandoned" and refresh last_modified.
    """
    shopcart = Shopcart.find_by_customer_id(customer_id).first()
    if not shopcart:
        abort(
            status.HTTP_404_NOT_FOUND,
            f"Shopcart for customer '{customer_id}' was not found.",
        )
    shopcart.status = "abandoned"
    shopcart.last_modified = datetime.utcnow()
    shopcart.update()
    return jsonify(shopcart.serialize()), status.HTTP_200_OK


######################################################################
# CANCEL A SHOPCART
######################################################################
@app.route("/shopcarts/<int:customer_id>/cancel", methods=["PATCH"])
def cancel_shopcart(customer_id: int):
    """
    Mark the specified shopcart as abandoned.
    """
    app.logger.info("Request to cancel shopcart for customer [%s]", customer_id)
    shopcart = Shopcart.find_by_customer_id(customer_id).first()
    if not shopcart:
        abort(
            status.HTTP_404_NOT_FOUND,
            f"Shopcart for customer '{customer_id}' was not found.",
        )
    current_status = (shopcart.status or "").strip().lower()
    if current_status != "abandoned":
        shopcart.status = "abandoned"
        shopcart.last_modified = datetime.utcnow()
        shopcart.update()
    app.logger.info("Shopcart for customer [%s] cancelled.", customer_id)
    return jsonify(shopcart.serialize()), status.HTTP_200_OK


######################################################################
# LOCK A SHOPCART
######################################################################
@app.route("/shopcarts/<int:customer_id>/lock", methods=["PATCH"])
def lock_shopcart(customer_id: int):
    """
    Mark the specified shopcart as locked for downstream processing.
    """
    app.logger.info("Request to lock shopcart for customer [%s]", customer_id)
    shopcart = Shopcart.find_by_customer_id(customer_id).first()
    if not shopcart:
        abort(
            status.HTTP_404_NOT_FOUND,
            f"Shopcart for customer '{customer_id}' was not found.",
        )
    current_status = (shopcart.status or "").strip().lower()
    if current_status != "locked":
        shopcart.status = "locked"
        shopcart.last_modified = datetime.utcnow()
        shopcart.update()
    app.logger.info("Shopcart for customer [%s] locked.", customer_id)
    return jsonify(shopcart.serialize()), status.HTTP_200_OK


######################################################################
# EXPIRE A SHOPCART
######################################################################
@app.route("/shopcarts/<int:customer_id>/expire", methods=["PATCH"])
def expire_shopcart(customer_id: int):
    """
    Mark the specified shopcart as expired and no longer actionable.
    """
    app.logger.info("Request to expire shopcart for customer [%s]", customer_id)
    shopcart = Shopcart.find_by_customer_id(customer_id).first()
    if not shopcart:
        abort(
            status.HTTP_404_NOT_FOUND,
            f"Shopcart for customer '{customer_id}' was not found.",
        )
    current_status = (shopcart.status or "").strip().lower()
    if current_status != "expired":
        shopcart.status = "expired"
        shopcart.last_modified = datetime.utcnow()
        shopcart.update()
    app.logger.info("Shopcart for customer [%s] expired.", customer_id)
    return jsonify(shopcart.serialize()), status.HTTP_200_OK


######################################################################
# REACTIVATE A SHOPCART
######################################################################
@app.route("/shopcarts/<int:customer_id>/reactivate", methods=["PATCH"])
def reactivate_shopcart(customer_id: int):
    """
    Reactivate an abandoned shopcart.
    """
    app.logger.info("Request to reactivate shopcart for customer [%s]", customer_id)
    shopcart = Shopcart.find_by_customer_id(customer_id).first()
    if not shopcart:
        abort(
            status.HTTP_404_NOT_FOUND,
            f"Shopcart for customer '{customer_id}' was not found.",
        )
    current_status = (shopcart.status or "").strip().lower()
    if current_status != "active":
        shopcart.status = "active"
        shopcart.last_modified = datetime.utcnow()
        shopcart.update()
    app.logger.info("Shopcart for customer [%s] reactivated.", customer_id)
    return jsonify(shopcart.serialize()), status.HTTP_200_OK


######################################################################
# UPDATE A SINGLE ITEM IN A SHOPCART
######################################################################
@app.route(
    "/shopcarts/<int:customer_id>/items/<int:product_id>", methods=["PUT", "PATCH"]
)
def update_shopcart_item(customer_id: int, product_id: int):
    """
    Update a single item in a shopcart
    """
    shopcart = Shopcart.find_by_customer_id(customer_id).first()
    if not shopcart:
        abort(
            status.HTTP_404_NOT_FOUND,
            f"Shopcart for customer '{customer_id}' was not found.",
        )

    check_content_type("application/json")
    payload = request.get_json() or {}

    status_norm = (
        shopcart.status.strip().lower()
        if isinstance(shopcart.status, str)
        else "active"
    )
    if status_norm == "abandoned":
        abort(status.HTTP_409_CONFLICT, "Cannot update items on an abandoned shopcart.")

    current = next(
        (it for it in shopcart.items if int(it.product_id) == int(product_id)), None
    )
    if current is None:
        abort(
            status.HTTP_404_NOT_FOUND,
            f"Item with product_id '{product_id}' not found in this shopcart.",
        )

    q_raw = payload.get("quantity", current.quantity)
    try:
        q = int(q_raw)
    except (TypeError, ValueError):
        abort(status.HTTP_400_BAD_REQUEST, "quantity must be an integer.")
    if q < 0 or q > 99:
        abort(status.HTTP_400_BAD_REQUEST, "invalid quantity")

    if q == 0:
        shopcart.remove_item(product_id)
        shopcart.update()
        return jsonify(shopcart.serialize()), status.HTTP_200_OK

    price_raw = payload.get("price", float(current.price))
    try:
        price = Decimal(str(price_raw))
    except (decimal.InvalidOperation, ValueError, TypeError):
        abort(status.HTTP_400_BAD_REQUEST, "price is invalid.")

    desc = payload.get("description", current.description or "")
    shopcart.upsert_item(
        product_id=product_id, quantity=q, price=price, description=desc
    )
    shopcart.update()
    return jsonify(shopcart.serialize()), status.HTTP_200_OK


######################################################################
# LIST ALL SHOPCARTS
######################################################################
@app.route("/shopcarts", methods=["GET"])
def list_shopcarts():
    """
    Retrieve Shopcarts, optionally filtered by status and customer_id.
    """
    filters = _parse_list_filters(request.args)
    app.logger.info(
        (
            "Request to list shopcarts filters="
            "status=%s customer_id=%s created_before=%s created_after=%s "
            "total_price_lt=%s total_price_gt=%s"
        ),
        filters.status,
        filters.customer_id,
        filters.created_before,
        filters.created_after,
        filters.total_price_lt,
        filters.total_price_gt,
    )

    query = Shopcart.query
    if filters.status is not None:
        query = query.filter(func.lower(Shopcart.status) == filters.status)
    if filters.customer_id is not None:
        query = query.filter(Shopcart.customer_id == filters.customer_id)
    if filters.created_before is not None:
        query = query.filter(Shopcart.created_date <= filters.created_before)
    if filters.created_after is not None:
        query = query.filter(Shopcart.created_date >= filters.created_after)

    return (
        jsonify(
            [
                cart.serialize()
                for cart in _filter_by_total_price(
                    query.all(), filters.total_price_gt, filters.total_price_lt
                )
            ]
        ),
        status.HTTP_200_OK,
    )


######################################################################
# CREATE A NEW SHOPCART ITEM
######################################################################
@app.route("/shopcarts/<int:customer_id>/items", methods=["POST"])
def add_item_to_shopcart(customer_id):
    """Add an Item to a Shopcart"""
    app.logger.info("Request to add item to shopcart for customer %s", customer_id)
    check_content_type("application/json")
    shopcart = Shopcart.find_by_customer_id(customer_id).first()
    if not shopcart:
        abort(
            status.HTTP_404_NOT_FOUND, f"Shopcart for customer {customer_id} not found"
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

    return jsonify(updated_item.serialize()), status.HTTP_201_CREATED


######################################################################
# READ AN ITEM FROM SHOPCART
######################################################################
@app.route("/shopcarts/<int:customer_id>/items/<int:product_id>", methods=["GET"])
def read_item_from_shopcart(customer_id, product_id):
    """Read an item from a shopcart"""
    app.logger.info(
        f"Request to read product {product_id} from shopcart of customer {customer_id}"
    )

    # find the shopcart for the customer
    shopcart = Shopcart.find_by_customer_id(customer_id).first()
    if not shopcart:
        abort(
            status.HTTP_404_NOT_FOUND, f"Shopcart for customer {customer_id} not found"
        )

    # find the item in the shopcart by product_id
    item = next(
        (entry for entry in shopcart.items if entry.product_id == product_id),
        None,
    )
    if not item:
        abort(
            status.HTTP_404_NOT_FOUND,
            f"Product with id {product_id} not found in this shopcart",
        )

    return jsonify(item.serialize()), status.HTTP_200_OK


##############################################
# DELETE AN ITEM FROM SHOPCART
##############################################
@app.route("/shopcarts/<int:customer_id>/items/<int:product_id>", methods=["DELETE"])
def delete_item_from_shopcart(customer_id, product_id):
    """Delete an existing item from a shopcart"""
    app.logger.info(
        f"Request to delete product {product_id} from shopcart of customer {customer_id}"
    )

    # find the shopcart for the customer
    shopcart = Shopcart.find_by_customer_id(customer_id).first()
    if not shopcart:
        abort(
            status.HTTP_404_NOT_FOUND, f"Shopcart for customer {customer_id} not found"
        )

    # find the item in the shopcart by product_id
    item = next(
        (entry for entry in shopcart.items if entry.product_id == product_id),
        None,
    )
    if not item:
        abort(
            status.HTTP_404_NOT_FOUND,
            f"Product with id {product_id} not found in this shopcart",
        )

    # remove the item and persist
    shopcart.remove_item(product_id)
    shopcart.last_modified = datetime.utcnow()
    shopcart.update()
    app.logger.info(
        "Product %s deleted successfully from shopcart for customer %s",
        product_id,
        customer_id,
    )

    return "", status.HTTP_204_NO_CONTENT


##############################################
# LIST ALL ITEMS IN A SHOPCART
##############################################
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
        abort(status.HTTP_400_BAD_REQUEST, f"{field} must be a number")
    try:
        return Decimal(cleaned)
    except (decimal.InvalidOperation, ValueError, TypeError):
        abort(status.HTTP_400_BAD_REQUEST, f"{field} must be a number")


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
        abort(
            status.HTTP_400_BAD_REQUEST,
            "min_price must be less than or equal to max_price",
        )

    return filters


@app.route("/shopcarts/<int:customer_id>/items", methods=["GET"])
def list_items_in_shopcart(customer_id):
    """List all items in a customer's shopcart"""
    app.logger.info(f"Request to list all items in shopcart of customer {customer_id}")

    # find the shopcart for the customer
    shopcart = Shopcart.find_by_customer_id(customer_id).first()
    if not shopcart:
        abort(
            status.HTTP_404_NOT_FOUND, f"Shopcart for customer {customer_id} not found"
        )

    filters = _parse_item_filters(request.args)
    query = ShopcartItem.find_by_shopcart_id(shopcart.id)
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

    # convert to list of dicts
    items = query.order_by(ShopcartItem.id).all()
    results = [item.serialize() for item in items]
    return jsonify(results), status.HTTP_200_OK


##############################################
# SHOPCART TOTALS
##############################################
@app.route("/shopcarts/<int:customer_id>/totals", methods=["GET"])
def get_shopcart_totals(customer_id: int):
    """Return aggregated totals for a customer's shopcart."""
    app.logger.info(
        "Request to compute totals for shopcart of customer %s", customer_id
    )

    shopcart = Shopcart.find_by_customer_id(customer_id).first()
    if not shopcart:
        abort(
            status.HTTP_404_NOT_FOUND,
            f"Shopcart for customer {customer_id} not found",
        )

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
    return jsonify(aggregate), status.HTTP_200_OK


def _parse_iso8601_to_utc(value: str, field: str) -> datetime:
    """Parse an ISO8601 string into a UTC naive datetime for database comparison."""
    cleaned = (value or "").strip()
    if not cleaned:
        abort(
            status.HTTP_400_BAD_REQUEST,
            f"{field} must be a non-empty ISO8601 timestamp when provided.",
        )
    normalized = cleaned.replace("Z", "+00:00").replace(" ", "+")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        abort(
            status.HTTP_400_BAD_REQUEST,
            f"{field} must be a valid ISO8601 timestamp: {cleaned}",
        )
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    utc_value = parsed.astimezone(timezone.utc)
    return utc_value.replace(tzinfo=None)
