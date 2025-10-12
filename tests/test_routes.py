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
from wsgi import app
from service.common import status
from service.models import db, Shopcart, ShopcartItem
from .factories import ShopcartFactory, ShopcartItemFactory
from service.common import error_handlers
from service import routes
from werkzeug.exceptions import HTTPException

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
        """It should call the home page"""
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    # Todo: Add your test cases here...

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
        response = self.client.get(
            f"{BASE_URL}/0", headers={"X-Customer-ID": "0"}
        )
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
