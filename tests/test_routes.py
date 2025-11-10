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

# pylint: disable=duplicate-code,too-many-lines
import os
import logging
from unittest import TestCase
from unittest.mock import patch
from decimal import Decimal
from datetime import datetime, timezone
from werkzeug.exceptions import HTTPException
from wsgi import app
from service.common import status
from service.models import db, Shopcart, ShopcartItem, DataValidationError
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

    def _create_shopcart_for_customer(
        self, customer_id: int, status_value: str = "active"
    ) -> dict:
        """Create a shopcart for a specific customer via the API."""
        payload = {"customer_id": customer_id, "status": status_value, "items": []}
        response = self.client.post(BASE_URL, json=payload)
        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            f"Failed to create shopcart for {customer_id}",
        )
        return response.get_json()

    def _create_shopcart_with_created_date(
        self, created_dt: datetime, status_value: str = "active"
    ) -> Shopcart:
        """Persist a shopcart with a specific created_date timestamp."""
        cart = ShopcartFactory(status=status_value)
        cart.created_date = created_dt
        cart.last_modified = created_dt
        cart.create()
        return cart

    def _create_cart_with_items(
        self, customer_id: int, item_specs: list[tuple[int, Decimal, int]]
    ) -> Shopcart:
        """Create a cart with provided (product_id, price, quantity) tuples."""
        cart = self._create_cart(customer_id=customer_id)
        for idx, (product_id, price, quantity) in enumerate(item_specs):
            pid = product_id or 1000 + idx
            self._add_item(
                cart,
                product_id=pid,
                price=Decimal(str(price)),
                quantity=quantity,
            )
        db.session.refresh(cart)
        return cart

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
        response = self.client.get(location)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        new_shopcart = response.get_json()
        self.assertEqual(new_shopcart["customerId"], test_shopcart.customer_id)
        self.assertEqual(new_shopcart["status"], test_shopcart.status)
        self.assertEqual(new_shopcart["totalItems"], 0)
        self.assertEqual(new_shopcart["totalPrice"], 0.0)
        self.assertIsInstance(new_shopcart["items"], list)

    # ----------------------------------------------------------
    # TEST ADMIN UI
    # ----------------------------------------------------------
    def test_admin_ui_served(self):
        """It should serve the admin single-page UI"""
        resp = self.client.get("/ui")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        content_type = resp.headers.get("Content-Type", "")
        self.assertIn("text/html", content_type)
        body = resp.get_data(as_text=True)
        self.assertIn("Admin Console", body)
        self.assertIn("Workflow shortcuts", body)

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

        response = self.client.get(f"{BASE_URL}/{shopcart.customer_id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        self.assertEqual(data["customerId"], shopcart.customer_id)
        self.assertEqual(data["totalItems"], 2)
        self.assertAlmostEqual(data["totalPrice"], 19.0, places=2)
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["items"][0]["productId"], 111)

    def test_get_shopcart_not_found(self):
        """It should not Get a Shopcart thats not found"""
        response = self.client.get(f"{BASE_URL}/0")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        data = response.get_json()
        logging.debug("Response data = %s", data)
        self.assertIn("was not found", data["message"])

    def test_get_shopcart_without_auth_header(self):
        """It should allow reading a shopcart without auth headers"""
        shopcart = ShopcartFactory()
        shopcart.create()
        response = self.client.get(f"{BASE_URL}/{shopcart.customer_id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        self.assertEqual(data["customerId"], shopcart.customer_id)

    def test_get_shopcart_ignores_customer_mismatch(self):
        """It should return data even if X-Customer-ID does not match"""
        shopcart = ShopcartFactory()
        shopcart.create()
        response = self.client.get(
            f"{BASE_URL}/{shopcart.customer_id}",
            headers={"X-Customer-ID": str(shopcart.customer_id + 1)},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        self.assertEqual(data["customerId"], shopcart.customer_id)

    def test_get_shopcart_invalid_header(self):
        """It should ignore non-integer customer headers"""
        shopcart = ShopcartFactory()
        shopcart.create()
        response = self.client.get(
            f"{BASE_URL}/{shopcart.customer_id}",
            headers={"X-Customer-ID": "not-a-number"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

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

    def test_list_shopcarts_filter_by_status(self):
        """It should filter shopcarts by status"""
        self._create_shopcart_for_customer(4001, "active")
        self._create_shopcart_for_customer(4002, "abandoned")
        self._create_shopcart_for_customer(4003, "abandoned")

        response = self.client.get(f"{BASE_URL}?status=abandoned")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.get_json()
        self.assertEqual(len(data), 2)
        for entry in data:
            self.assertEqual(entry["status"], "abandoned")

    def test_list_shopcarts_filter_by_customer_id(self):
        """It should filter shopcarts by customer id"""
        self._create_shopcart_for_customer(12345, "active")
        self._create_shopcart_for_customer(67890, "abandoned")

        response = self.client.get(f"{BASE_URL}?customer_id=12345")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.get_json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["customer_id"], 12345)

    def test_list_shopcarts_filter_by_status_and_customer(self):
        """It should combine status and customer id filters"""
        self._create_shopcart_for_customer(12345, "active")
        self._create_shopcart_for_customer(54321, "active")
        self._create_shopcart_for_customer(67890, "abandoned")

        response = self.client.get(f"{BASE_URL}?customer_id=12345&status=active")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.get_json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["customer_id"], 12345)
        self.assertEqual(data[0]["status"], "active")

    def test_list_shopcarts_filter_created_before(self):
        """It should filter carts created before a timestamp"""
        older = self._create_shopcart_with_created_date(datetime(2024, 1, 1, 12, 0, 0))
        newer = self._create_shopcart_with_created_date(datetime(2024, 1, 3, 12, 0, 0))
        cutoff = datetime(2024, 1, 2, 0, 0, 0, tzinfo=timezone.utc).isoformat()

        response = self.client.get(f"{BASE_URL}?created_before={cutoff}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.get_json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["customer_id"], older.customer_id)

        response = self.client.get(f"{BASE_URL}?created_after={cutoff}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        self.assertTrue(any(entry["customer_id"] == newer.customer_id for entry in data))
        self.assertFalse(
            any(entry["customer_id"] == older.customer_id for entry in data)
        )

    def test_list_shopcarts_filter_created_between(self):
        """It should support filtering carts within a created_date range"""
        early = self._create_shopcart_with_created_date(datetime(2024, 1, 1, 0, 0, 0))
        middle = self._create_shopcart_with_created_date(datetime(2024, 1, 2, 0, 0, 0))
        late = self._create_shopcart_with_created_date(datetime(2024, 1, 3, 0, 0, 0))

        start = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc).isoformat()
        end = datetime(2024, 1, 2, 12, 0, 0, tzinfo=timezone.utc).isoformat()
        response = self.client.get(
            f"{BASE_URL}?created_after={start}&created_before={end}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.get_json()
        customer_ids = {entry["customer_id"] for entry in data}
        self.assertIn(middle.customer_id, customer_ids)
        self.assertNotIn(early.customer_id, customer_ids)
        self.assertNotIn(late.customer_id, customer_ids)

    def test_list_shopcarts_invalid_created_filter(self):
        """It should reject invalid created_before timestamps"""
        response = self.client.get(f"{BASE_URL}?created_before=not-a-date")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.get_json()
        self.assertIn("created_before", data["message"])

    def test_list_shopcarts_filter_returns_empty(self):
        """It should return an empty list when filters match nothing"""
        self._create_shopcart_for_customer(1001, "active")
        self._create_shopcart_for_customer(1002, "active")

        response = self.client.get(f"{BASE_URL}?status=abandoned")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.get_json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 0)

    def test_list_shopcarts_filter_by_locked_status(self):
        """It should return carts when filtering by locked status"""
        active_cart = ShopcartFactory(status="active")
        active_cart.create()
        locked_cart = ShopcartFactory(status="locked")
        locked_cart.create()
        response = self.client.get(f"{BASE_URL}?status=locked")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        self.assertTrue(all(cart["status"] == "locked" for cart in data))
        self.assertTrue(any(cart["customer_id"] == locked_cart.customer_id for cart in data))
        self.assertFalse(any(cart["customer_id"] == active_cart.customer_id for cart in data))

    def test_list_shopcarts_filter_total_price_less_than(self):
        """It should filter carts with totals below a threshold"""
        low = self._create_cart_with_items(
            7001,
            [
                (2001, Decimal("10.00"), 2),
                (2002, Decimal("5.50"), 1),
            ],
        )
        self._create_cart_with_items(
            7002,
            [
                (3001, Decimal("40.00"), 3),
            ],
        )

        response = self.client.get(f"{BASE_URL}?total_price_lt=40")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.get_json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["customer_id"], low.customer_id)

    def test_list_shopcarts_filter_total_price_greater_than(self):
        """It should filter carts with totals above a threshold"""
        self._create_cart_with_items(
            7101,
            [
                (3101, Decimal("9.99"), 1),
            ],
        )
        high = self._create_cart_with_items(
            7102,
            [
                (3201, Decimal("50.00"), 2),
            ],
        )

        response = self.client.get(f"{BASE_URL}?total_price_gt=80")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["customer_id"], high.customer_id)

    def test_list_shopcarts_filter_total_price_range(self):
        """It should filter carts within a total price range"""
        self._create_cart_with_items(
            7201,
            [
                (3301, Decimal("5.00"), 2),
            ],
        )
        mid = self._create_cart_with_items(
            7202,
            [
                (3401, Decimal("20.00"), 3),
            ],
        )
        self._create_cart_with_items(
            7203,
            [
                (3501, Decimal("100.00"), 1),
            ],
        )

        response = self.client.get(
            f"{BASE_URL}?total_price_gt=50&total_price_lt=80"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["customer_id"], mid.customer_id)

    def test_list_shopcarts_invalid_total_price(self):
        """It should reject invalid total price filters"""
        response = self.client.get(f"{BASE_URL}?total_price_lt=not-a-number")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.get_json()
        self.assertIn("total_price_lt", data["message"])

        response = self.client.get(f"{BASE_URL}?total_price_lt=50&total_price_gt=60")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.get_json()
        self.assertIn("total_price_lt must be greater", data["message"])

    def test_list_shopcarts_invalid_status(self):
        """It should reject unsupported status filters"""
        self._create_shopcart_for_customer(2001, "active")

        response = self.client.get(f"{BASE_URL}?status=pending")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        data = response.get_json()
        self.assertIn("Invalid status", data["message"])

    def test_list_shopcarts_invalid_customer_id(self):
        """It should reject non-integer customer id filters"""
        self._create_shopcart_for_customer(2002, "active")

        response = self.client.get(f"{BASE_URL}?customer_id=not-a-number")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        data = response.get_json()
        self.assertIn("customer_id must be an integer", data["message"])

    def test_list_shopcarts_blank_status_rejected(self):
        """It should reject blank status filters"""
        self._create_shopcart_for_customer(2003, "active")
        response = self.client.get(f"{BASE_URL}?status=")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("status must be a non-empty value", response.get_json()["message"])

    def test_list_shopcarts_blank_total_price_lt_rejected(self):
        """It should reject blank total_price_lt filters"""
        self._create_shopcart_for_customer(2004, "active")
        response = self.client.get(f"{BASE_URL}?total_price_lt=")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(
            "total_price_lt must be a non-empty decimal value",
            response.get_json()["message"],
        )

    def test_list_shopcarts_blank_created_before_rejected(self):
        """It should reject blank created_before filters"""
        self._create_shopcart_for_customer(2005, "active")
        response = self.client.get(f"{BASE_URL}?created_before=")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(
            "created_before must be a non-empty ISO8601 timestamp",
            response.get_json()["message"],
        )

    def test_list_shopcarts_created_after_accepts_naive_timestamp(self):
        """It should accept naive timestamps and normalize them to UTC"""
        self._create_shopcart_for_customer(2006, "active")
        response = self.client.get(f"{BASE_URL}?created_after=2024-01-01T12:00:00")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # ----------------------------------------------------------
    # TEST DELETE
    # ----------------------------------------------------------

    def test_delete_shopcart(self):
        """It should Delete a Shopcart"""
        test_shopcart = self._create_shopcarts(1)[0]
        response = self.client.delete(f"{BASE_URL}/{test_shopcart.customer_id}")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(len(response.data), 0)
        # make sure they are deleted
        response = self.client.get(f"{BASE_URL}/{test_shopcart.customer_id}")
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
        customer_id = sc["customer_id"]
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
        response = self.client.put(f"{BASE_URL}/{customer_id}", json=update_body)
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
        customer_id = sc["customer_id"]
        self.assertEqual(sc.get("total_items", 0), 0)

        # Add two products
        body_add = {
            "items": [
                {"product_id": 2001, "quantity": 2, "price": 5.50},
                {"product_id": 2002, "quantity": 3, "price": 1.25},
            ]
        }
        response = self.client.patch(f"{BASE_URL}/{customer_id}", json=body_add)
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
        response = self.client.put(f"{BASE_URL}/{customer_id}", json=body_update_remove)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        after = response.get_json()

        # Now only product_id 2001 with quantity=4 should remain
        self.assertEqual(after["id"], shopcart_id)
        self.assertEqual(after["total_items"], 4)
        self.assertTrue(
            any(i["product_id"] == 2001 and i["quantity"] == 4 for i in after["items"])
        )
        self.assertFalse(any(i["product_id"] == 2002 for i in after["items"]))

    def test_checkout_sets_abandoned_and_updates_last_modified(self):
        """It should set status=abandoned and refresh last_modified on checkout"""
        # Create and bulk add items
        payload = {"customer_id": 515151}
        response = self.client.post(BASE_URL, json=payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        sc = response.get_json()
        shopcart_id = sc["id"]
        customer_id = sc["customer_id"]
        last_modified_before = sc.get("last_modified")

        body = {
            "items": [
                {"product_id": 3001, "quantity": 2, "price": 19.99},
                {"product_id": 3002, "quantity": 3, "price": 29.99},
            ]
        }
        response = self.client.put(f"{BASE_URL}/{customer_id}", json=body)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Checkout
        response = self.client.put(f"{BASE_URL}/{customer_id}/checkout")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        after = response.get_json()

        self.assertEqual(after["id"], shopcart_id)
        self.assertEqual(after["status"], "abandoned")
        self.assertIn("last_modified", after)
        self.assertIsNotNone(after["last_modified"])
        if last_modified_before:
            self.assertNotEqual(after["last_modified"], last_modified_before)

    def test_checkout_nonexistent_shopcart_returns_404(self):
        """Checkout should return 404 when the cart id does not exist"""
        resp = self.client.put(f"{BASE_URL}/999999/checkout")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_cancel_shopcart_sets_status_abandoned(self):
        """Cancelling a cart should mark it abandoned"""
        cart = ShopcartFactory(status="active")
        cart.create()
        resp = self.client.patch(f"{BASE_URL}/{cart.customer_id}/cancel")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        payload = resp.get_json()
        self.assertEqual(payload["status"], "abandoned")
        refreshed = Shopcart.find(cart.id)
        self.assertEqual(refreshed.status, "abandoned")

    def test_cancel_shopcart_not_found(self):
        """Cancelling a missing cart returns 404"""
        resp = self.client.patch(f"{BASE_URL}/404404/cancel")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_lock_shopcart_sets_status_locked(self):
        """Locking a cart should mark it locked and refresh last_modified"""
        cart = ShopcartFactory(status="active")
        cart.create()
        initial_last_modified = cart.last_modified.isoformat()
        resp = self.client.patch(f"{BASE_URL}/{cart.customer_id}/lock")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        payload = resp.get_json()
        self.assertEqual(payload["status"], "locked")
        self.assertNotEqual(payload["last_modified"], initial_last_modified)
        refreshed = Shopcart.find(cart.id)
        self.assertEqual(refreshed.status, "locked")

    def test_lock_shopcart_not_found(self):
        """Lock should return 404 when the cart id does not exist"""
        resp = self.client.patch(f"{BASE_URL}/999999/lock")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_expire_shopcart_sets_status_expired(self):
        """Expiring a cart should mark it expired and refresh last_modified"""
        cart = ShopcartFactory(status="locked")
        cart.create()
        initial_last_modified = cart.last_modified.isoformat()
        resp = self.client.patch(f"{BASE_URL}/{cart.customer_id}/expire")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        payload = resp.get_json()
        self.assertEqual(payload["status"], "expired")
        self.assertNotEqual(payload["last_modified"], initial_last_modified)
        refreshed = Shopcart.find(cart.id)
        self.assertEqual(refreshed.status, "expired")

    def test_expire_shopcart_not_found(self):
        """Expire should return 404 when the cart id does not exist"""
        resp = self.client.patch(f"{BASE_URL}/999999/expire")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_reactivate_shopcart_sets_status_active(self):
        """Reactivating should restore status to active"""
        cart = ShopcartFactory(status="abandoned")
        cart.create()
        resp = self.client.patch(f"{BASE_URL}/{cart.customer_id}/reactivate")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        payload = resp.get_json()
        self.assertEqual(payload["status"], "active")
        refreshed = Shopcart.find(cart.id)
        self.assertEqual(refreshed.status, "active")

    def test_reactivate_shopcart_not_found(self):
        """Reactivating a missing cart returns 404"""
        resp = self.client.patch(f"{BASE_URL}/404404/reactivate")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_shopcart_status_only(self):
        """It should update the cart status when provided"""
        cart = ShopcartFactory(status="active")
        cart.create()
        resp = self.client.patch(
            f"{BASE_URL}/{cart.customer_id}", json={"status": "abandoned"}
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        updated = Shopcart.find(cart.id)
        self.assertEqual(updated.status, "abandoned")

    def test_update_shopcart_not_found(self):
        """It should return 404 when updating a non-existing shopcart"""
        body = {
            "status": "abandoned",
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
        customer_id = sc["customer_id"]

        # No Content-Type header -> 415 via check_content_type
        response = self.client.open(
            f"{BASE_URL}/{customer_id}", method="PUT", data=b"{}"
        )
        self.assertEqual(response.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    # ----------------------------------------------------------
    # UPDATE AN ITEM
    # ----------------------------------------------------------

    def _create_cart(self, customer_id=321):
        """Helper to create a cart."""
        cart = ShopcartFactory(customer_id=customer_id, status="active")
        cart.create()
        return cart

    def _add_item(self, cart, **overrides):
        """Helper to attach an item to the provided cart."""
        payload = {
            "shopcart_id": cart.id,
            "product_id": overrides.pop("product_id", 1234),
            "quantity": overrides.pop("quantity", 1),
            "price": overrides.pop("price", Decimal("2.00")),
        }
        description = overrides.pop("description", None)
        if description is not None:
            payload["description"] = description
        if overrides:
            payload.update(overrides)
        item = ShopcartItemFactory(**payload)
        item.create()
        return item

    def _setup_cart_with_basic_items(self):
        """Create a cart populated with deterministic items for filtering tests."""
        cart = self._create_cart(customer_id=555001)
        self._add_item(
            cart,
            product_id=123,
            quantity=1,
            price=Decimal("5.00"),
            description="Eco-friendly water bottle",
        )
        self._add_item(
            cart,
            product_id=456,
            quantity=2,
            price=Decimal("10.00"),
            description="Durable hiking backpack",
        )
        self._add_item(
            cart,
            product_id=789,
            quantity=5,
            price=Decimal("25.00"),
            description="Compact travel mug",
        )
        return cart

    def _setup_cart_for_combined_filters(self):
        """Create a cart tailored for combined filter scenarios."""
        cart = self._create_cart(customer_id=555002)
        self._add_item(
            cart,
            product_id=123,
            quantity=2,
            price=Decimal("15.00"),
            description="Eco travel essentials kit",
        )
        self._add_item(
            cart,
            product_id=456,
            quantity=4,
            price=Decimal("12.00"),
            description="Durable rope set",
        )
        self._add_item(
            cart,
            product_id=789,
            quantity=1,
            price=Decimal("30.00"),
            description="Luxury gift box",
        )
        return cart

    def test_update_item_not_found_returns_404(self):
        """It should return 404 when product id isn't present in cart"""
        cart = self._create_cart()
        resp = self.client.patch(
            f"{BASE_URL}/{cart.customer_id}/items/999999",
            json={"quantity": 1},
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_item_bad_price_returns_400(self):
        """It should reject item updates when price parsing fails"""
        cart = self._create_cart()
        item = self._add_item(cart)
        resp = self.client.patch(
            f"{BASE_URL}/{cart.customer_id}/items/{item.product_id}",
            json={"price": "not-a-number"},
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_item_blocked_when_cart_abandoned(self):
        """It should block modifications when the cart status is abandoned"""
        cart = self._create_cart()
        item = self._add_item(cart)
        cart.status = "abandoned"
        cart.update()
        resp = self.client.patch(
            f"{BASE_URL}/{cart.customer_id}/items/{item.product_id}",
            json={"quantity": 2},
        )
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)

    def test_update_item_without_header_allowed(self):
        """Item updates should work without any auth headers"""
        cart = ShopcartFactory(status="active")
        cart.create()
        item = ShopcartItemFactory(shopcart_id=cart.id)
        item.create()
        resp = self.client.patch(
            f"{BASE_URL}/{cart.customer_id}/items/{item.product_id}",
            json={"quantity": 2},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        payload = resp.get_json()
        self.assertEqual(payload["total_items"], 2)

    def test_update_item_ignores_non_integer_header(self):
        """Non-integer X-Customer-ID headers should be ignored"""
        cart = ShopcartFactory(status="active")
        cart.create()
        item = ShopcartItemFactory(shopcart_id=cart.id)
        item.create()
        resp = self.client.patch(
            f"{BASE_URL}/{cart.customer_id}/items/{item.product_id}",
            json={"quantity": 1},
            headers={"X-Customer-ID": "abc"},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        payload = resp.get_json()
        self.assertEqual(payload["total_items"], 1)

    def test_update_item_cart_not_found(self):
        """It should return 404 when the cart id does not exist"""
        resp = self.client.patch(
            f"{BASE_URL}/999999/items/111",
            json={"quantity": 1},
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
            f"{BASE_URL}/{cart.customer_id}/items/777",
            json=body,
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        updated = resp.get_json()

        self.assertEqual(updated["total_items"], 5)
        self.assertTrue(
            any(i["product_id"] == 777 and i["quantity"] == 5 for i in updated["items"])
        )

        # verify customer view totals
        resp = self.client.get(f"{BASE_URL}/{cart.customer_id}")
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
            f"{BASE_URL}/{cart.customer_id}/items/888",
            json=body,
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

        resp = self.client.get(f"{BASE_URL}/{cart.customer_id}")
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
            f"{BASE_URL}/{cart.customer_id}/items/999",
            json={"quantity": 0},
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
            f"{BASE_URL}/{cart.customer_id}/items/55555",
            json={"quantity": 1},
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
            f"{BASE_URL}/{cart.customer_id}/items/2468",
            json={"quantity": "NaN"},
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

        # negative
        resp = self.client.patch(
            f"{BASE_URL}/{cart.customer_id}/items/2468",
            json={"quantity": -1},
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

        # too large
        resp = self.client.patch(
            f"{BASE_URL}/{cart.customer_id}/items/2468",
            json={"quantity": 1000},
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_item_allows_different_customer_header(self):
        """Mismatched X-Customer-ID header should not block updates"""
        cart = ShopcartFactory(status="active")
        cart.create()
        item = ShopcartItemFactory(
            shopcart_id=cart.id, product_id=1234, quantity=1, price=Decimal("1.00")
        )
        item.create()

        resp = self.client.patch(
            f"{BASE_URL}/{cart.customer_id}/items/1234",
            json={"quantity": 2},
            headers={"X-Customer-ID": str(cart.customer_id + 1)},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        payload = resp.get_json()
        self.assertEqual(payload["total_items"], 2)

    def test_update_item_requires_active_cart(self):
        """It should block item updates when the cart is not active"""
        cart = ShopcartFactory(status="abandoned")
        cart.create()
        item = ShopcartItemFactory(
            shopcart_id=cart.id, product_id=4321, quantity=1, price=Decimal("1.00")
        )
        item.create()

        resp = self.client.patch(
            f"{BASE_URL}/{cart.customer_id}/items/4321",
            json={"quantity": 2},
        )
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)

    def test_update_item_invalid_price(self):
        """Price must parse as Decimal"""
        cart = ShopcartFactory(status="active")
        cart.create()
        item = ShopcartItemFactory(
            shopcart_id=cart.id, product_id=2469, quantity=1, price=Decimal("2.00")
        )
        item.create()

        resp = self.client.put(
            f"{BASE_URL}/{cart.customer_id}/items/2469",
            json={"price": "not-a-number"},
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

    def test_add_item_returns_internal_error_when_item_missing(self):
        """It should surface an internal error if the item cannot be persisted"""
        cart = ShopcartFactory(status="active")
        cart.create()
        with patch("service.routes.Shopcart.upsert_item", autospec=True):
            resp = self.client.post(
                f"{BASE_URL}/{cart.customer_id}/items",
                json={
                    "product_id": 9999,
                    "quantity": 1,
                    "price": 12.34,
                    "description": "Transient product",
                },
                content_type="application/json",
            )
        self.assertEqual(resp.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("Unable to persist cart item.", resp.get_json()["message"])

    def test_add_item_requires_product_id(self):
        """It should reject item creation without a product_id"""
        self.client.post(
            "/shopcarts",
            json={"customer_id": 1, "status": "active"},
            content_type="application/json",
        )
        resp = self.client.post(
            "/shopcarts/1/items",
            json={"quantity": 1, "price": 9.99},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("product_id", resp.get_json()["message"])

    def test_add_item_product_id_must_be_integer(self):
        """It should reject non-integer product ids"""
        self.client.post(
            "/shopcarts",
            json={"customer_id": 1, "status": "active"},
            content_type="application/json",
        )
        resp = self.client.post(
            "/shopcarts/1/items",
            json={"product_id": "abc", "quantity": 1, "price": 9.99},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_add_item_quantity_must_be_integer(self):
        """It should reject non-integer quantities"""
        self.client.post(
            "/shopcarts",
            json={"customer_id": 1, "status": "active"},
            content_type="application/json",
        )
        resp = self.client.post(
            "/shopcarts/1/items",
            json={"product_id": 100, "quantity": "two", "price": 9.99},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("quantity", resp.get_json()["message"])

    def test_add_item_quantity_must_be_positive(self):
        """It should reject zero or negative quantities"""
        self.client.post(
            "/shopcarts",
            json={"customer_id": 1, "status": "active"},
            content_type="application/json",
        )
        resp = self.client.post(
            "/shopcarts/1/items",
            json={"product_id": 100, "quantity": 0, "price": 9.99},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_add_item_requires_price_for_new_product(self):
        """It should require price when adding a new product"""
        self.client.post(
            "/shopcarts",
            json={"customer_id": 1, "status": "active"},
            content_type="application/json",
        )
        resp = self.client.post(
            "/shopcarts/1/items",
            json={"product_id": 100, "quantity": 1},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("price", resp.get_json()["message"])

    def test_add_item_price_must_parse(self):
        """It should reject prices that cannot be parsed"""
        self.client.post(
            "/shopcarts",
            json={"customer_id": 1, "status": "active"},
            content_type="application/json",
        )
        resp = self.client.post(
            "/shopcarts/1/items",
            json={"product_id": 100, "quantity": 1, "price": "not-a-number"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_add_item_existing_product_increments_quantity(self):
        """It should merge with existing items and reuse stored price when price omitted"""
        self.client.post(
            "/shopcarts",
            json={"customer_id": 1, "status": "active"},
            content_type="application/json",
        )
        first = self.client.post(
            "/shopcarts/1/items",
            json={"product_id": 100, "quantity": 2, "price": 10.00},
            content_type="application/json",
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)

        second = self.client.post(
            "/shopcarts/1/items",
            json={"product_id": 100, "quantity": 1},
            content_type="application/json",
        )
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        item = second.get_json()
        self.assertEqual(item["quantity"], 3)
        self.assertAlmostEqual(float(item["price"]), 10.00, places=2)

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
        product_id = resp.get_json()["product_id"]

        resp = self.client.get(f"/shopcarts/1/items/{product_id}")
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
        product_id = resp.get_json()["product_id"]

        # delete the item by product id
        resp = self.client.delete(f"/shopcarts/1/items/{product_id}")
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

    def test_list_items_filter_by_description(self):
        """It should filter items by description substring"""
        cart = self._setup_cart_with_basic_items()
        resp = self.client.get(
            f"{BASE_URL}/{cart.customer_id}/items?description=eco"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.get_json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["product_id"], 123)
        self.assertIn("eco", data[0]["description"].lower())

    def test_list_items_filter_by_product_id(self):
        """It should filter items by product_id"""
        cart = self._setup_cart_with_basic_items()
        resp = self.client.get(f"{BASE_URL}/{cart.customer_id}/items?product_id=456")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.get_json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["product_id"], 456)

    def test_list_items_filter_by_quantity(self):
        """It should filter items by quantity"""
        cart = self._setup_cart_with_basic_items()
        resp = self.client.get(f"{BASE_URL}/{cart.customer_id}/items?quantity=2")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.get_json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["product_id"], 456)

    def test_list_items_filter_by_price_range(self):
        """It should filter items within a price range"""
        cart = self._setup_cart_with_basic_items()
        resp = self.client.get(
            f"{BASE_URL}/{cart.customer_id}/items?min_price=6&max_price=20"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.get_json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["product_id"], 456)

    def test_list_items_filter_by_min_price_only(self):
        """It should filter items by minimum price only"""
        cart = self._setup_cart_with_basic_items()
        resp = self.client.get(f"{BASE_URL}/{cart.customer_id}/items?min_price=10")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.get_json()
        product_ids = sorted(item["product_id"] for item in data)
        self.assertEqual(product_ids, [456, 789])

    def test_list_items_filter_by_max_price_only(self):
        """It should filter items by maximum price only"""
        cart = self._setup_cart_with_basic_items()
        resp = self.client.get(f"{BASE_URL}/{cart.customer_id}/items?max_price=10")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.get_json()
        product_ids = sorted(item["product_id"] for item in data)
        self.assertEqual(product_ids, [123, 456])

    def test_list_items_filter_combined(self):
        """It should combine multiple filters"""
        cart = self._setup_cart_for_combined_filters()
        resp = self.client.get(
            f"{BASE_URL}/{cart.customer_id}/items"
            "?description=eco&product_id=123&min_price=10&max_price=20"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.get_json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["product_id"], 123)
        self.assertIn("eco", data[0]["description"].lower())
        self.assertGreaterEqual(data[0]["price"], 10.0)
        self.assertLessEqual(data[0]["price"], 20.0)

    def test_list_items_filter_invalid_min_price(self):
        """It should reject invalid min_price values"""
        cart = self._setup_cart_with_basic_items()
        resp = self.client.get(
            f"{BASE_URL}/{cart.customer_id}/items?min_price=abc"
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        data = resp.get_json()
        self.assertIn("min_price must be a number", data["message"])

    def test_list_items_filter_invalid_quantity(self):
        """It should reject invalid quantity values"""
        cart = self._setup_cart_with_basic_items()
        resp = self.client.get(f"{BASE_URL}/{cart.customer_id}/items?quantity=two")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        data = resp.get_json()
        self.assertIn("quantity must be an integer", data["message"])

    def test_list_items_filter_unknown_parameter(self):
        """It should reject unsupported query parameters"""
        cart = self._setup_cart_with_basic_items()
        resp = self.client.get(f"{BASE_URL}/{cart.customer_id}/items?color=red")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        data = resp.get_json()
        self.assertEqual(
            data["message"], "color is not a supported filter parameter"
        )

    def test_list_items_filter_ordering_validation(self):
        """It should validate min_price is not greater than max_price"""
        cart = self._setup_cart_with_basic_items()
        resp = self.client.get(
            f"{BASE_URL}/{cart.customer_id}/items?min_price=20&max_price=10"
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        data = resp.get_json()
        self.assertIn("min_price must be less than or equal to max_price", data["message"])

    def test_list_items_filter_empty_result(self):
        """It should return an empty list when no results match"""
        cart = self._setup_cart_with_basic_items()
        resp = self.client.get(
            f"{BASE_URL}/{cart.customer_id}/items?description=nonexistent"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.get_json()
        self.assertEqual(data, [])

    def test_list_items_filter_blank_description_rejected(self):
        """It should reject blank description filters"""
        cart = self._setup_cart_with_basic_items()
        resp = self.client.get(f"{BASE_URL}/{cart.customer_id}/items?description= ")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("description must be a non-empty string", resp.get_json()["message"])

    def test_list_items_filter_blank_min_price_rejected(self):
        """It should reject blank numeric price filters"""
        cart = self._setup_cart_with_basic_items()
        resp = self.client.get(f"{BASE_URL}/{cart.customer_id}/items?min_price=")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("min_price must be a number", resp.get_json()["message"])

    def test_list_items_filter_multiple_unknown_parameters(self):
        """It should reject multiple unsupported parameters with a combined message"""
        cart = self._setup_cart_with_basic_items()
        resp = self.client.get(f"{BASE_URL}/{cart.customer_id}/items?foo=1&bar=2")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            resp.get_json()["message"], "bar, foo are not supported filter parameters"
        )

    def test_get_shopcart_totals_returns_aggregates(self):
        """It should return aggregated totals for a cart"""
        cart = self._create_cart_with_items(
            8601,
            [
                (4001, Decimal("9.99"), 2),
                (4002, Decimal("5.00"), 1),
            ],
        )
        resp = self.client.get(f"{BASE_URL}/{cart.customer_id}/totals")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.get_json()
        self.assertEqual(data["customer_id"], cart.customer_id)
        self.assertEqual(data["item_count"], 2)
        self.assertEqual(data["total_quantity"], 3)
        self.assertAlmostEqual(data["subtotal"], 24.98, places=2)
        self.assertAlmostEqual(data["discount"], 0.0, places=2)
        self.assertAlmostEqual(data["total"], 24.98, places=2)

    def test_get_shopcart_totals_for_empty_cart(self):
        """It should return zero totals when the cart has no items"""
        cart = self._create_cart(customer_id=8602)
        resp = self.client.get(f"{BASE_URL}/{cart.customer_id}/totals")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.get_json()
        self.assertEqual(data["item_count"], 0)
        self.assertEqual(data["total_quantity"], 0)
        self.assertEqual(data["subtotal"], 0.0)
        self.assertEqual(data["discount"], 0.0)
        self.assertEqual(data["total"], 0.0)

    def test_get_shopcart_totals_not_found(self):
        """It should return 404 when the cart does not exist"""
        resp = self.client.get(f"{BASE_URL}/999999/totals")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

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

        resp, code = error_handlers.request_validation_error(
            DataValidationError("validation failed")
        )
        self.assertEqual(code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.json["message"], "validation failed")

        resp, code = error_handlers.forbidden("denied")
        self.assertEqual(code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.json["message"], "denied")

        resp, code = error_handlers.unauthorized("no auth")
        self.assertEqual(code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(resp.json["message"], "no auth")

        resp, code = error_handlers.resource_conflict("duplicate")
        self.assertEqual(code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.json["message"], "duplicate")
