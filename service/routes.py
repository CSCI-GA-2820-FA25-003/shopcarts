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
from flask import jsonify, request, url_for, abort
from flask import current_app as app  # Import Flask application
from service.models import Shopcart, ShopcartItem
from service.common import status  # HTTP Status Codes


def serialize_shopcart_response(shopcart):
    """Serializes a shopcart with calculated totals and camelCase keys"""
    items = []
    total_quantity = 0
    total_price = Decimal("0")

    for item in shopcart.items:
        quantity = item.quantity or 0
        price = item.price or Decimal("0")
        total_quantity += quantity
        total_price += price * quantity
        items.append(
            {
                "productId": item.product_id,
                "description": item.description,
                "quantity": quantity,
                "price": float(price),
            }
        )

    return {
        "customerId": shopcart.customer_id,
        "createdDate": (
            shopcart.created_date.isoformat() if shopcart.created_date else None
        ),
        "lastModified": (
            shopcart.last_modified.isoformat() if shopcart.last_modified else None
        ),
        "status": shopcart.status,
        "totalItems": total_quantity,
        "totalPrice": float(total_price),
        "items": items,
    }


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

    header_customer = request.headers.get("X-Customer-ID")
    if header_customer is None:
        abort(status.HTTP_401_UNAUTHORIZED, "Authentication required")

    try:
        requesting_customer = int(header_customer)
    except ValueError as error:
        abort(status.HTTP_400_BAD_REQUEST, f"Invalid customer id header: {error}")

    if requesting_customer != customer_id:
        abort(
            status.HTTP_403_FORBIDDEN,
            "You are not allowed to view another customer's shopcart.",
        )

    # Attempt to find the Shopcart and abort if not found
    shopcart = Shopcart.find_by_customer_id(customer_id).first()
    if not shopcart:
        abort(
            status.HTTP_404_NOT_FOUND,
            f"Shopcart for customer '{customer_id}' was not found.",
        )

    response = serialize_shopcart_response(shopcart)
    app.logger.info("Returning shopcart for customer: %s", customer_id)
    return jsonify(response), status.HTTP_200_OK


######################################################################
# READ A SHOPCART (Admin)
######################################################################
@app.route("/admin/shopcarts/<int:customer_id>", methods=["GET"])
def admin_get_shopcart(customer_id):
    """
    Retrieve any customer's shopcart for admin users
    """
    app.logger.info("Admin request to Retrieve shopcart for customer [%s]", customer_id)

    role = request.headers.get("X-Role")
    if role != "admin":
        abort(status.HTTP_403_FORBIDDEN, "Admin privileges required.")

    shopcart = Shopcart.find_by_customer_id(customer_id).first()
    if not shopcart:
        abort(
            status.HTTP_404_NOT_FOUND,
            f"Shopcart for customer '{customer_id}' was not found.",
        )

    response = serialize_shopcart_response(shopcart)
    return jsonify(response), status.HTTP_200_OK


######################################################################
# DELETE A SHOPCART
######################################################################
@app.route("/shopcarts/<int:shopcart_id>", methods=["DELETE"])
def delete_shopcarts(shopcart_id):
    """
    Delete a Shopcart

    This endpoint will delete a Shopcart based the id specified in the path
    """
    app.logger.info("Request to Delete a shopcart with id [%s]", shopcart_id)

    # Delete the Shopcart if it exists
    shopcart = Shopcart.find(shopcart_id)
    if shopcart:
        app.logger.info("Shopcart with ID: %d found.", shopcart.id)
        shopcart.delete()

    app.logger.info("Shopcart with ID: %d delete complete.", shopcart_id)
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
@app.route("/shopcarts/<int:shopcart_id>", methods=["PUT", "PATCH"])
def update_shopcart(shopcart_id: int):
    """
    Update the status of a shopcart
    """
    check_content_type("application/json")
    shopcart = Shopcart.find(shopcart_id)
    if not shopcart:
        abort(
            status.HTTP_404_NOT_FOUND,
            f"Shopcart with id '{shopcart_id}' was not found.",
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
@app.route("/shopcarts/<int:shopcart_id>/checkout", methods=["PUT", "PATCH"])
def checkout_shopcart(shopcart_id: int):
    """
    Change the status to "completes" and refresh last_modified
    """
    shopcart = Shopcart.find(shopcart_id)
    if not shopcart:
        abort(
            status.HTTP_404_NOT_FOUND,
            f"Shopcart with id '{shopcart_id}' was not found.",
        )
    shopcart.status = "completed"
    shopcart.update()
    return jsonify(shopcart.serialize()), status.HTTP_200_OK


######################################################################
# UPDATE A SINGLE ITEM IN A SHOPCART
######################################################################
@app.route(
    "/shopcarts/<int:shopcart_id>/items/<int:product_id>", methods=["PUT", "PATCH"]
)
def update_shopcart_item(shopcart_id: int, product_id: int):
    """
    Update a single item in a shopcart
    """
    header_val = request.headers.get("X-Customer-ID")
    if header_val is None:
        abort(status.HTTP_401_UNAUTHORIZED, "Missing X-Customer-ID header.")
    try:
        requester_id = int(header_val)
    except (TypeError, ValueError):
        abort(status.HTTP_400_BAD_REQUEST, "X-Customer-ID must be an integer.")

    shopcart = Shopcart.find(shopcart_id)
    if not shopcart:
        abort(
            status.HTTP_404_NOT_FOUND,
            f"Shopcart with id '{shopcart_id}' was not found.",
        )
    if requester_id != int(shopcart.customer_id):
        abort(status.HTTP_403_FORBIDDEN, "You can only update your own shopcart.")

    check_content_type("application/json")
    payload = request.get_json() or {}

    status_norm = (
        shopcart.status.strip().lower()
        if isinstance(shopcart.status, str)
        else "active"
    )
    if status_norm in ("completed", "cancelled"):
        abort(status.HTTP_409_CONFLICT, "Cannot update items on a non-active shopcart.")

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
    Retrieve all Shopcarts
    """
    app.logger.info("Request to list all shopcarts")
    shopcarts = Shopcart.all()
    results = [shopcart.serialize() for shopcart in shopcarts]
    return jsonify(results), status.HTTP_200_OK


######################################################################
# CREATE A NEW SHOPCART ITEM
######################################################################
@app.route("/shopcarts/<int:customer_id>/items", methods=["POST"])
def add_item_to_shopcart(customer_id):
    """Add an Item to a Shopcart"""
    app.logger.info("Request to add item to shopcart for customer %s", customer_id)
    shopcart = Shopcart.find_by_customer_id(customer_id).first()
    if not shopcart:
        abort(
            status.HTTP_404_NOT_FOUND, f"Shopcart for customer {customer_id} not found"
        )

    data = request.get_json()
    item = ShopcartItem()
    item.deserialize(data)
    item.shopcart_id = shopcart.id
    item.create()

    return jsonify(item.serialize()), status.HTTP_201_CREATED


######################################################################
# READ AN ITEM FROM SHOPCART
######################################################################
@app.route("/shopcarts/<int:customer_id>/items/<int:item_id>", methods=["GET"])
def read_item_from_shopcart(customer_id, item_id):
    """Read an item from a shopcart"""
    app.logger.info(
        f"Request to read item {item_id} from shopcart of customer {customer_id}"
    )

    # find the shopcart for the customer
    shopcart = Shopcart.find_by_customer_id(customer_id).first()
    if not shopcart:
        abort(
            status.HTTP_404_NOT_FOUND, f"Shopcart for customer {customer_id} not found"
        )

    # find the item in the shopcart
    item = ShopcartItem.find(item_id)
    if not item or item.shopcart_id != shopcart.id:
        abort(
            status.HTTP_404_NOT_FOUND,
            f"Item with id {item_id} not found in this shopcart",
        )

    return jsonify(item.serialize()), status.HTTP_200_OK


##############################################
# DELETE AN ITEM FROM SHOPCART
##############################################
@app.route("/shopcarts/<int:customer_id>/items/<int:item_id>", methods=["DELETE"])
def delete_item_from_shopcart(customer_id, item_id):
    """Delete an existing item from a shopcart"""
    app.logger.info(
        f"Request to delete item {item_id} from shopcart of customer {customer_id}"
    )

    # find the shopcart for the customer
    shopcart = Shopcart.find_by_customer_id(customer_id).first()
    if not shopcart:
        abort(
            status.HTTP_404_NOT_FOUND, f"Shopcart for customer {customer_id} not found"
        )

    # find the item in the shopcart
    item = ShopcartItem.find(item_id)
    if not item or item.shopcart_id != shopcart.id:
        abort(
            status.HTTP_404_NOT_FOUND,
            f"Item with id {item_id} not found in this shopcart",
        )

    # delete the item
    item.delete()
    app.logger.info(f"Item {item_id} deleted successfully from shopcart {customer_id}")

    return "", status.HTTP_204_NO_CONTENT


##############################################
# LIST ALL ITEMS IN A SHOPCART
##############################################
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

    # all items in the shopcart
    items = ShopcartItem.find_by_shopcart_id(shopcart.id)

    # convert to list of dicts
    results = [item.serialize() for item in items]
    return jsonify(results), status.HTTP_200_OK
