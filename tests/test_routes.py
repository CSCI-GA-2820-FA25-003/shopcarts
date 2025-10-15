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
TestShopcart API Service Test Suite
"""

# pylint: disable=duplicate-code
import os
import logging
from unittest import TestCase
from decimal import Decimal
from werkzeug.exceptions import HTTPException
from wsgi import app
from service.common import status
from service.models import db, Shopcart, ShopcartItem
from service.common import error_handlers
from service import routes
from .factories import ShopcartFactory, ShopcartItemFactory

DATABASE_URI = os.getenv(
    "DATABASE_URI", "postgresql+psycopg://postgres:postgres@localhost:5432/testdb"
)
BASE_URL = "/shopcarts"


######################################################################
#  T E S T   C A S E S
######################################################################
# pylint: disable=too-many-public-methods
class TestYourResourceService(TestCase):
    """REST API Server Tests"""

    @classmethod
    def setUpClass(cls):
        """Run once before all tests"""
        app.config["TESTING"] = True
        app.config["DEBUG"] = False
        # Set up the test database
        app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URI
        app.logger.setLevel(logging.CRITICAL)
        app.app_context().push()

    @classmethod
    def tearDownClass(cls):
        """Run once after all tests"""
        db.session.close()

    def setUp(self):
        """Runs before each test"""
        self.client = app.test_client()
        db.session.query(ShopcartItem).delete()  # clean up items first
        db.session.query(Shopcart).delete()  # clean up the last tests
        db.session.commit()

    def tearDown(self):
        """This runs after each test"""
        db.session.remove()

    ############################################################
    # Utility function to bulk create shopcarts
    ############################################################
    def _create_shopcarts(self, count: int = 1) -> list:
        """Factory method to create shopcarts in bulk"""
        shopcarts = []
        for _ in range(count):
            test_shopcart = ShopcartFactory()
            response = self.client.post(BASE_URL, json=test_shopcart.serialize())
            self.assertEqual(
                response.status_code,
                status.HTTP_201_CREATED,
                "Could not create test shopcart",
            )
            new_shopcart = response.get_json()
            test_shopcart.id = new_shopcart["id"]
            shopcarts.append(test_shopcart)
        return shopcarts

    ######################################################################
    #  P L A C E   T E S T   C A S E S   H E R E
    ######################################################################

    def test_index(self):
        """It should return service metadata at the root URL"""
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # Verify JSON structure
        data = resp.get_json()
        self.assertIsNotNone(data)
        self.assertIn("name", data)
        self.assertIn("version", data)
        self.assertIn("description", data)
        self.assertIn("paths", data)

        # Check key values
        self.assertEqual(data["name"], "Shopcart REST API Service")
        self.assertEqual(data["version"], "1.0.0")
        self.assertTrue(data["description"].startswith("This service manages"))

        # Verify paths section
        paths = data["paths"]
        self.assertIn("shopcarts", paths)
        self.assertEqual(paths["shopcarts"], "/shopcarts")

    # ----------------------------------------------------------
    # TEST CREATE
    # ----------------------------------------------------------
    def test_create_shopcart(self):
        """It should Create a new Shopcart"""
        test_shopcart = ShopcartFactory()
        logging.debug("Test Shopcart: %s", test_shopcart.serialize())
        response = self.client.post(BASE_URL, json=test_shopcart.serialize())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Make sure location header is set
        location = response.headers.get("Location", None)
        self.assertIsNotNone(location)

        # Check the data is correct
        new_shopcart = response.get_json()
        self.assertEqual(new_shopcart["customer_id"], test_shopcart.customer_id)
        self.assertEqual(new_shopcart["status"], test_shopcart.status)
        self.assertEqual(new_shopcart["total_items"], test_shopcart.total_items)
        self.assertIn("items", new_shopcart)
        # Check that the location header works for customer view
        response = self.client.get(
            location, headers={"X-Customer-ID": str(test_shopcart.customer_id)}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        new_shopcart = response.get_json()
        self.assertEqual(new_shopcart["customerId"], test_shopcart.customer_id)
        self.assertEqual(new_shopcart["status"], test_shopcart.status)
        self.assertEqual(new_shopcart["totalItems"], 0)
        self.assertEqual(new_shopcart["totalPrice"], 0.0)
        self.assertIsInstance(new_shopcart["items"], list)

    def test_create_shopcart_conflict(self):
        """It should return 409 when creating a cart for the same customer twice"""
        payload = {"customer_id": 9999, "status": "active"}
        first = self.client.post(BASE_URL, json=payload)
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        second = self.client.post(BASE_URL, json=payload)
        self.assertEqual(second.status_code, status.HTTP_409_CONFLICT)
        data = second.get_json()
        self.assertIn("already exists", data["message"])

    # ----------------------------------------------------------
    # TEST READ
    # ----------------------------------------------------------
    def test_get_shopcart(self):
        """It should Get a single Shopcart"""
        # Create a shopcart and items directly
        shopcart = ShopcartFactory()
        shopcart.create()
        item = ShopcartItemFactory(
            shopcart_id=shopcart.id,
            product_id=111,
            description="First item",
            quantity=2,
            price=Decimal("9.50"),
        )
        item.create()

        response = self.client.get(
            f"{BASE_URL}/{shopcart.customer_id}",
            headers={"X-Customer-ID": str(shopcart.customer_id)},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        self.assertEqual(data["customerId"], shopcart.customer_id)
        self.assertEqual(data["totalItems"], 2)
        self.assertAlmostEqual(data["totalPrice"], 19.0, places=2)
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["items"][0]["productId"], 111)

    def test_get_shopcart_not_found(self):
        """It should not Get a Shopcart thats not found"""
        response = self.client.get(f"{BASE_URL}/0", headers={"X-Customer-ID": "0"})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        data = response.get_json()
        logging.debug("Response data = %s", data)
        self.assertIn("was not found", data["message"])

    def test_get_shopcart_requires_auth(self):
        """It should require authentication header for customer read"""
        shopcart = ShopcartFactory()
        shopcart.create()
        response = self.client.get(f"{BASE_URL}/{shopcart.customer_id}")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_shopcart_forbidden(self):
        """It should forbid customers from reading other carts"""
        shopcart = ShopcartFactory()
        shopcart.create()
        response = self.client.get(
            f"{BASE_URL}/{shopcart.customer_id}",
            headers={"X-Customer-ID": str(shopcart.customer_id + 1)},
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_shopcart_invalid_header(self):
        """It should reject non-integer customer headers"""
        shopcart = ShopcartFactory()
        shopcart.create()
        response = self.client.get(
            f"{BASE_URL}/{shopcart.customer_id}",
            headers={"X-Customer-ID": "not-a-number"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_get_shopcart(self):
        """Admin should be able to view any cart"""
        shopcart = ShopcartFactory()
        shopcart.create()
        response = self.client.get(
            f"/admin{BASE_URL}/{shopcart.customer_id}", headers={"X-Role": "admin"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        self.assertEqual(data["customerId"], shopcart.customer_id)

    def test_admin_get_shopcart_forbidden(self):
        """Non-admins should not access admin endpoint"""
        response = self.client.get(f"/admin{BASE_URL}/1")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_get_shopcart_not_found(self):
        """Admins should receive 404 when cart missing"""
        response = self.client.get(
            f"/admin{BASE_URL}/9999", headers={"X-Role": "admin"}
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_shopcarts(self):
        """It should list all shopcarts"""
        shopcarts = self._create_shopcarts(3)
        self.assertEqual(len(shopcarts), 3)

        response = self.client.get(BASE_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.get_json()
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 3)

        first = data[0]
        self.assertIn("id", first)
        self.assertIn("customer_id", first)
        self.assertIn("status", first)
        self.assertIn("items", first)

    # ----------------------------------------------------------
    # TEST DELETE
    # ----------------------------------------------------------

    def test_delete_shopcart(self):
        """It should Delete a Shopcart"""
        test_shopcart = self._create_shopcarts(1)[0]
        response = self.client.delete(f"{BASE_URL}/{test_shopcart.id}")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(len(response.data), 0)
        # make sure they are deleted
        response = self.client.get(
            f"{BASE_URL}/{test_shopcart.customer_id}",
            headers={"X-Customer-ID": str(test_shopcart.customer_id)},
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_non_existing_shopcart(self):
        """It should Delete a Shopcart even if it doesn't exist"""
        response = self.client.delete(f"{BASE_URL}/0")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(len(response.data), 0)

    # ----------------------------------------------------------
    # TEST UPDATE
    # ----------------------------------------------------------

    def test_update_shopcart_add_one_item_to_empty(self):
        """It should bulk-update an empty cart to contain one item with quantity=1"""
        # Create an empty shopcart
        payload = {"customer_id": 424242}
        response = self.client.post(BASE_URL, json=payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        sc = response.get_json()
        shopcart_id = sc["id"]
        self.assertEqual(sc.get("total_items", 0), 0)

        # Bulk update with one item (quantity=1)
        update_body = {
            "items": [
                {
                    "product_id": 1001,
                    "quantity": 1,
                    "price": 9.99,
                    "description": "First item",
                }
            ]
        }
        response = self.client.put(f"{BASE_URL}/{shopcart_id}", json=update_body)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        after = response.get_json()

        self.assertEqual(after["id"], shopcart_id)
        self.assertEqual(after["total_items"], 1)
        self.assertTrue(
            any(i["product_id"] == 1001 and i["quantity"] == 1 for i in after["items"])
        )

    def test_update_shopcart_bulk_add_update_remove_items(self):
        """It should support bulk add, update, and remove in one or multiple updates"""
        # Create an empty shopcart
        payload = {"customer_id": 737373}
        response = self.client.post(BASE_URL, json=payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        sc = response.get_json()
        shopcart_id = sc["id"]
        self.assertEqual(sc.get("total_items", 0), 0)

        # Add two products
        body_add = {
            "items": [
                {"product_id": 2001, "quantity": 2, "price": 5.50},
                {"product_id": 2002, "quantity": 3, "price": 1.25},
            ]
        }
        response = self.client.patch(f"{BASE_URL}/{shopcart_id}", json=body_add)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        after_add = response.get_json()
        self.assertEqual(after_add["total_items"], 5)

        # Update one product and remove the other (quantity<=0 => remove)
        body_update_remove = {
            "items": [
                {"product_id": 2001, "quantity": 4, "price": 5.50},  # 2 -> 4
                {"product_id": 2002, "quantity": 0},  # remove
            ]
        }
        response = self.client.put(f"{BASE_URL}/{shopcart_id}", json=body_update_remove)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        after = response.get_json()

        # Now only product_id 2001 with quantity=4 should remain
        self.assertEqual(after["total_items"], 4)
        self.assertTrue(
            any(i["product_id"] == 2001 and i["quantity"] == 4 for i in after["items"])
        )
        self.assertFalse(any(i["product_id"] == 2002 for i in after["items"]))

    def test_checkout_sets_completed_and_updates_last_modified(self):
        """It should set status=completed and refresh last_modified on checkout"""
        # Create and bulk add items
        payload = {"customer_id": 515151}
        response = self.client.post(BASE_URL, json=payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        sc = response.get_json()
        shopcart_id = sc["id"]
        last_modified_before = sc.get("last_modified")

        body = {
            "items": [
                {"product_id": 3001, "quantity": 2, "price": 19.99},
                {"product_id": 3002, "quantity": 3, "price": 29.99},
            ]
        }
        response = self.client.put(f"{BASE_URL}/{shopcart_id}", json=body)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Checkout
        response = self.client.put(f"{BASE_URL}/{shopcart_id}/checkout")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        after = response.get_json()

        self.assertEqual(after["status"], "completed")
        self.assertIn("last_modified", after)
        self.assertIsNotNone(after["last_modified"])
        if last_modified_before:
            self.assertNotEqual(after["last_modified"], last_modified_before)

    def test_checkout_nonexistent_shopcart_returns_404(self):
        """Checkout should return 404 when the cart id does not exist"""
        resp = self.client.put(f"{BASE_URL}/999999/checkout")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_shopcart_status_only(self):
        """It should update the cart status when provided"""
        cart = ShopcartFactory(status="active")
        cart.create()
        resp = self.client.patch(
            f"{BASE_URL}/{cart.id}", json={"status": "abandoned"}
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        updated = Shopcart.find(cart.id)
        self.assertEqual(updated.status, "abandoned")

    def test_update_shopcart_not_found(self):
        """It should return 404 when updating a non-existing shopcart"""
        body = {
            "status": "completed",
            "items": [{"product_id": 1, "quantity": 1, "price": 1.0}],
        }
        response = self.client.put(f"{BASE_URL}/999999", json=body)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_shopcart_bad_content_type(self):
        """It should reject updates with missing/incorrect Content-Type"""
        # Create a cart to have a valid id
        payload = {"customer_id": 1111}
        response = self.client.post(BASE_URL, json=payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        sc = response.get_json()
        shopcart_id = sc["id"]

        # No Content-Type header -> 415 via check_content_type
        response = self.client.open(
            f"{BASE_URL}/{shopcart_id}", method="PUT", data=b"{}"
        )
        self.assertEqual(response.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    # ----------------------------------------------------------
    # UPDATE AN ITEM
    # ----------------------------------------------------------

    def _create_cart_with_headers(self, customer_id=321):
        """Helper to create a cart and return (cart, headers)."""
        cart = ShopcartFactory(customer_id=customer_id, status="active")
        cart.create()
        headers = {"X-Customer-ID": str(cart.customer_id)}
        return cart, headers

    def _add_item(self, cart, product_id=1234, quantity=1, price=Decimal("2.00")):
        """Helper to attach an item to the provided cart."""
        item = ShopcartItemFactory(
            shopcart_id=cart.id,
            product_id=product_id,
            quantity=quantity,
            price=price,
        )
        item.create()
        return item

    def test_update_item_not_found_returns_404(self):
        """It should return 404 when product id isn't present in cart"""
        cart, headers = self._create_cart_with_headers()
        resp = self.client.patch(
            f"{BASE_URL}/{cart.id}/items/999999",
            json={"quantity": 1},
            headers=headers,
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_item_bad_price_returns_400(self):
        """It should reject item updates when price parsing fails"""
        cart, headers = self._create_cart_with_headers()
        item = self._add_item(cart)
        resp = self.client.patch(
            f"{BASE_URL}/{cart.id}/items/{item.product_id}",
            json={"price": "not-a-number"},
            headers=headers,
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_item_blocked_when_cart_completed(self):
        """It should block modifications when the cart status is completed"""
        cart, headers = self._create_cart_with_headers()
        item = self._add_item(cart)
        cart.status = "completed"
        cart.update()
        resp = self.client.patch(
            f"{BASE_URL}/{cart.id}/items/{item.product_id}",
            json={"quantity": 2},
            headers=headers,
        )
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)

    def test_update_item_missing_header_unauthorized(self):
        """It should require X-Customer-ID header for item updates"""
        cart = ShopcartFactory(status="active")
        cart.create()
        item = ShopcartItemFactory(shopcart_id=cart.id)
        item.create()
        resp = self.client.patch(
            f"{BASE_URL}/{cart.id}/items/{item.product_id}",
            json={"quantity": 2},
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_update_item_header_must_be_integer(self):
        """It should reject requests where X-Customer-ID is not an integer"""
        cart = ShopcartFactory(status="active")
        cart.create()
        item = ShopcartItemFactory(shopcart_id=cart.id)
        item.create()
        resp = self.client.patch(
            f"{BASE_URL}/{cart.id}/items/{item.product_id}",
            json={"quantity": 1},
            headers={"X-Customer-ID": "abc"},
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_item_cart_not_found(self):
        """It should return 404 when the cart id does not exist"""
        resp = self.client.patch(
            f"{BASE_URL}/999999/items/111",
            json={"quantity": 1},
            headers={"X-Customer-ID": "999999"},
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_add_item_shopcart_not_found(self):
        """It should return 404 when adding an item to a missing cart"""
        resp = self.client.post(
            "/shopcarts/999/items",
            json={"product_id": 1, "quantity": 1, "price": 1.0},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_read_item_missing_in_cart(self):
        """It should return 404 when the item id is not in the cart"""
        cart = ShopcartFactory(status="active")
        cart.create()
        resp = self.client.get(f"/shopcarts/{cart.customer_id}/items/123456")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_item_missing_in_cart(self):
        """It should return 404 when deleting an item not present in the cart"""
        cart = ShopcartFactory(status="active")
        cart.create()
        resp = self.client.delete(f"/shopcarts/{cart.customer_id}/items/999")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_item_quantity_valid(self):
        """Given a cart with an item, when quantity is changed to a valid number,
        then the item and totals should update."""
        cart = ShopcartFactory(status="active")
        cart.create()
        item = ShopcartItemFactory(
            shopcart_id=cart.id,
            product_id=777,
            quantity=2,
            price=Decimal("5.00"),
            description="size=S,color=red",
        )
        item.create()

        body = {"quantity": 5}
        resp = self.client.patch(
            f"{BASE_URL}/{cart.id}/items/777",
            json=body,
            headers={"X-Customer-ID": str(cart.customer_id)},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        updated = resp.get_json()

        self.assertEqual(updated["total_items"], 5)
        self.assertTrue(
            any(i["product_id"] == 777 and i["quantity"] == 5 for i in updated["items"])
        )

        # verify customer view totals
        resp = self.client.get(
            f"{BASE_URL}/{cart.customer_id}",
            headers={"X-Customer-ID": str(cart.customer_id)},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        view = resp.get_json()
        self.assertEqual(view["totalItems"], 5)
        self.assertAlmostEqual(view["totalPrice"], 25.00, places=2)

    def test_update_item_options_and_price(self):
        """Given a cart with an item, when options (description) and price change,
        then the item persists the option and totals reflect price delta."""
        cart = ShopcartFactory(status="active")
        cart.create()
        item = ShopcartItemFactory(
            shopcart_id=cart.id,
            product_id=888,
            quantity=1,
            price=Decimal("10.00"),
            description="size=M,color=black",
        )
        item.create()

        body = {"description": "size=L,color=blue", "price": 12.50}
        resp = self.client.put(
            f"{BASE_URL}/{cart.id}/items/888",
            json=body,
            headers={"X-Customer-ID": str(cart.customer_id)},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        updated = resp.get_json()

        self.assertTrue(
            any(
                i["product_id"] == 888 and i["description"] == "size=L,color=blue"
                for i in updated["items"]
            )
        )
        self.assertTrue(
            any(
                i["product_id"] == 888 and float(i["price"]) == 12.50
                for i in updated["items"]
            )
        )

        resp = self.client.get(
            f"{BASE_URL}/{cart.customer_id}",
            headers={"X-Customer-ID": str(cart.customer_id)},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        view = resp.get_json()
        self.assertEqual(view["totalItems"], 1)
        self.assertAlmostEqual(view["totalPrice"], 12.50, places=2)

    def test_update_item_quantity_zero_removes(self):
        """Given a cart with an item, when quantity is set to zero,
        then the item is removed and totals are zero."""
        cart = ShopcartFactory(status="active")
        cart.create()
        item = ShopcartItemFactory(
            shopcart_id=cart.id, product_id=999, quantity=3, price=Decimal("2.00")
        )
        item.create()

        resp = self.client.patch(
            f"{BASE_URL}/{cart.id}/items/999",
            json={"quantity": 0},
            headers={"X-Customer-ID": str(cart.customer_id)},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        updated = resp.get_json()

        self.assertEqual(updated["total_items"], 0)
        self.assertFalse(any(i["product_id"] == 999 for i in updated["items"]))

    def test_update_item_not_found_in_cart(self):
        """It should return 404 if the product does not exist in the cart"""
        cart = ShopcartFactory(status="active")
        cart.create()
        resp = self.client.patch(
            f"{BASE_URL}/{cart.id}/items/55555",
            json={"quantity": 1},
            headers={"X-Customer-ID": str(cart.customer_id)},
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_item_quantity_rule_violations(self):
        """It should enforce quantity rules (type, negative, too large)"""
        cart = ShopcartFactory(status="active")
        cart.create()
        item = ShopcartItemFactory(
            shopcart_id=cart.id, product_id=2468, quantity=1, price=Decimal("1.00")
        )
        item.create()

        # non-integer
        resp = self.client.patch(
            f"{BASE_URL}/{cart.id}/items/2468",
            json={"quantity": "NaN"},
            headers={"X-Customer-ID": str(cart.customer_id)},
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

        # negative
        resp = self.client.patch(
            f"{BASE_URL}/{cart.id}/items/2468",
            json={"quantity": -1},
            headers={"X-Customer-ID": str(cart.customer_id)},
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

        # too large
        resp = self.client.patch(
            f"{BASE_URL}/{cart.id}/items/2468",
            json={"quantity": 1000},
            headers={"X-Customer-ID": str(cart.customer_id)},
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_item_forbidden_wrong_customer(self):
        """It should forbid updating an item in someone else's cart"""
        cart = ShopcartFactory(status="active")
        cart.create()
        item = ShopcartItemFactory(
            shopcart_id=cart.id, product_id=1234, quantity=1, price=Decimal("1.00")
        )
        item.create()

        resp = self.client.patch(
            f"{BASE_URL}/{cart.id}/items/1234",
            json={"quantity": 2},
            headers={"X-Customer-ID": str(cart.customer_id + 1)},
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_item_requires_active_cart(self):
        """It should block item updates when the cart is not active"""
        cart = ShopcartFactory(status="completed")
        cart.create()
        item = ShopcartItemFactory(
            shopcart_id=cart.id, product_id=4321, quantity=1, price=Decimal("1.00")
        )
        item.create()

        resp = self.client.patch(
            f"{BASE_URL}/{cart.id}/items/4321",
            json={"quantity": 2},
            headers={"X-Customer-ID": str(cart.customer_id)},
        )
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)

    def test_update_item_missing_customer_header(self):
        """Update item should require X-Customer-ID header"""
        cart = ShopcartFactory(status="active")
        cart.create()
        item = ShopcartItemFactory(
            shopcart_id=cart.id, product_id=1357, quantity=1, price=Decimal("1.00")
        )
        item.create()

        resp = self.client.patch(
            f"{BASE_URL}/{cart.id}/items/1357", json={"quantity": 2}
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_update_item_invalid_price(self):
        """Price must parse as Decimal"""
        cart = ShopcartFactory(status="active")
        cart.create()
        item = ShopcartItemFactory(
            shopcart_id=cart.id, product_id=2469, quantity=1, price=Decimal("2.00")
        )
        item.create()

        resp = self.client.put(
            f"{BASE_URL}/{cart.id}/items/2469",
            json={"price": "not-a-number"},
            headers={"X-Customer-ID": str(cart.customer_id)},
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_add_item_to_existing_shopcart(self):
        """It should successfully add an item to an existing shopcart"""
        resp = self.client.post(
            "/shopcarts",
            json={"customer_id": 1, "status": "active"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        resp = self.client.post(
            "/shopcarts/1/items",
            json={
                "product_id": 100,
                "quantity": 2,
                "price": 19.99,
                "description": "Coffee Mug",
            },
            content_type="application/json",
        )

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        data = resp.get_json()
        self.assertEqual(data["product_id"], 100)
        self.assertEqual(data["quantity"], 2)

    def test_read_item_from_shopcart(self):
        """It should read an existing item from a shopcart"""
        resp = self.client.post(
            "/shopcarts",
            json={"customer_id": 1, "status": "active"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        resp = self.client.post(
            "/shopcarts/1/items",
            json={"product_id": 100, "quantity": 2, "price": 9.99},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        item_id = resp.get_json()["id"]

        resp = self.client.get(f"/shopcarts/1/items/{item_id}")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_read_item_from_nonexistent_shopcart(self):
        """It should return 404 if the shopcart does not exist"""
        resp = self.client.get("/shopcarts/999/items/1")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_read_item_not_in_this_shopcart(self):
        """It should return 404 if the item is not in the customer's shopcart"""
        # create a shopcart and add an item
        self.client.post(
            "/shopcarts",
            json={"customer_id": 1, "status": "active"},
            content_type="application/json",
        )
        self.client.post(
            "/shopcarts/1/items",
            json={"product_id": 101, "quantity": 2, "price": 9.99},
            content_type="application/json",
        )

        # read item from a different (non-existent) cart
        resp = self.client.get("/shopcarts/2/items/1")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_item_from_shopcart(self):
        """It should delete an item from the shopcart"""
        # create a shopcart and add an item
        resp = self.client.post(
            "/shopcarts", json={"customer_id": 1, "status": "active"}
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        resp = self.client.post(
            "/shopcarts/1/items",
            json={"product_id": 123, "quantity": 2, "price": 10.5},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        item_id = resp.get_json()["id"]

        # delete the item
        resp = self.client.delete(f"/shopcarts/1/items/{item_id}")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

    def test_delete_nonexistent_item(self):
        """It should return 404 when deleting a non-existing item"""
        resp = self.client.delete("/shopcarts/1/items/999")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_items_in_shopcart(self):
        """It should list all items in a shopcart"""
        # create a shopcart
        resp = self.client.post(
            "/shopcarts", json={"customer_id": 1, "status": "active"}
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        # add multiple items
        self.client.post(
            "/shopcarts/1/items",
            json={"product_id": 101, "quantity": 1, "price": 9.99},
            content_type="application/json",
        )
        self.client.post(
            "/shopcarts/1/items",
            json={"product_id": 102, "quantity": 2, "price": 19.99},
            content_type="application/json",
        )

        # add an item to a different cart to ensure isolation
        resp = self.client.get("/shopcarts/1/items")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.get_json()
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["product_id"], 101)
        self.assertEqual(data[1]["product_id"], 102)

    def test_list_items_in_nonexistent_shopcart(self):
        """It should return 404 if the shopcart does not exist"""
        resp = self.client.get("/shopcarts/999/items")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    # ----------------------------------------------------------
    # SUPPORT FUNCTIONS AND ERROR HANDLERS
    # ----------------------------------------------------------

    def test_check_content_type_missing_header(self):
        """It should abort when Content-Type header is missing"""
        with app.test_request_context("/shopcarts", method="POST"):
            with self.assertRaises(HTTPException) as raised:
                routes.check_content_type("application/json")
        self.assertEqual(raised.exception.code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    def test_check_content_type_invalid(self):
        """It should abort when Content-Type is incorrect"""
        with app.test_request_context(
            "/shopcarts",
            method="POST",
            headers={"Content-Type": "text/plain"},
        ):
            with self.assertRaises(HTTPException) as raised:
                routes.check_content_type("application/json")
        self.assertEqual(raised.exception.code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    def test_error_handlers(self):
        """It should format error responses correctly"""
        resp, code = error_handlers.bad_request("bad request")
        self.assertEqual(code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.json["error"], "Bad Request")

        resp, code = error_handlers.not_found("missing")
        self.assertEqual(code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(resp.json["error"], "Not Found")

        resp, code = error_handlers.method_not_supported("wrong method")
        self.assertEqual(code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(resp.json["error"], "Method not Allowed")

        resp, code = error_handlers.mediatype_not_supported("bad media")
        self.assertEqual(code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)
        self.assertEqual(resp.json["error"], "Unsupported media type")

        resp, code = error_handlers.internal_server_error("boom")
        self.assertEqual(code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(resp.json["error"], "Internal Server Error")
