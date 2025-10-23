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
from datetime import datetime
from flask import jsonify, request, url_for, abort
from flask import current_app as app  # Import Flask application
from service.models import Shopcart, ShopcartItem
from service.common import status  # HTTP Status Codes


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
    Change the status to "completes" and refresh last_modified
    """
    shopcart = Shopcart.find_by_customer_id(customer_id).first()
    if not shopcart:
        abort(
            status.HTTP_404_NOT_FOUND,
            f"Shopcart for customer '{customer_id}' was not found.",
        )
    shopcart.status = "completed"
    shopcart.update()
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
    check_content_type("application/json")
    shopcart = Shopcart.find_by_customer_id(customer_id).first()
    if not shopcart:
        abort(
            status.HTTP_404_NOT_FOUND, f"Shopcart for customer {customer_id} not found"
        )

    data = request.get_json() or {}
    try:
        product_id = int(data["product_id"])
    except (KeyError, TypeError, ValueError):
        abort(status.HTTP_400_BAD_REQUEST, "product_id is required and must be an integer.")

    try:
        increment = int(data.get("quantity", 0))
    except (TypeError, ValueError):
        abort(status.HTTP_400_BAD_REQUEST, "quantity must be an integer.")

    if increment <= 0:
        abort(status.HTTP_400_BAD_REQUEST, "quantity must be a positive integer.")

    existing = next(
        (item for item in shopcart.items if item.product_id == product_id),
        None,
    )

    price_raw = data.get("price")
    if existing and price_raw is None:
        price = Decimal(str(existing.price))
    else:
        if price_raw is None:
            abort(status.HTTP_400_BAD_REQUEST, "price is required.")
        try:
            price = Decimal(str(price_raw))
        except (decimal.InvalidOperation, ValueError, TypeError):
            abort(status.HTTP_400_BAD_REQUEST, "price is invalid.")

    if existing:
        quantity = existing.quantity + increment
        description = data.get("description", existing.description or "")
    else:
        quantity = increment
        description = data.get("description", "")

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
