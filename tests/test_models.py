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
Test cases for Shopcart Model
"""

# pylint: disable=duplicate-code
import os
import logging
from datetime import datetime
from decimal import Decimal
from unittest import TestCase
from unittest.mock import patch
from wsgi import app
from service.models import Shopcart, ShopcartItem, DataValidationError, db
from .factories import ShopcartFactory, ShopcartItemFactory

DATABASE_URI = os.getenv(
    "DATABASE_URI", "postgresql+psycopg://postgres:postgres@localhost:5432/testdb"
)


######################################################################
#  S H O P C A R T   M O D E L   T E S T   C A S E S
######################################################################
# pylint: disable=too-many-public-methods
class TestShopcartModel(TestCase):
    """Test Cases for Shopcart Model"""

    @classmethod
    def setUpClass(cls):
        """This runs once before the entire test suite"""
        app.config["TESTING"] = True
        app.config["DEBUG"] = False
        app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URI
        app.logger.setLevel(logging.CRITICAL)
        app.app_context().push()

    @classmethod
    def tearDownClass(cls):
        """This runs once after the entire test suite"""
        db.session.close()

    def setUp(self):
        """This runs before each test"""
        db.session.query(ShopcartItem).delete()  # clean up items first (FK constraint)
        db.session.query(Shopcart).delete()  # then clean up shopcarts
        db.session.commit()

    def tearDown(self):
        """This runs after each test"""
        db.session.remove()

    ######################################################################
    #  T E S T   C A S E S
    ######################################################################

    def test_create_a_shopcart(self):
        """It should Create a Shopcart and assert that it exists"""
        shopcart = ShopcartFactory()
        shopcart.create()
        self.assertIsNotNone(shopcart.id)
        found = Shopcart.all()
        self.assertEqual(len(found), 1)
        data = Shopcart.find(shopcart.id)
        self.assertEqual(data.customer_id, shopcart.customer_id)

    def test_read_a_shopcart(self):
        """It should Read a Shopcart"""
        shopcart = ShopcartFactory()
        shopcart.create()
        self.assertIsNotNone(shopcart.id)
        # Fetch it back
        found_shopcart = Shopcart.find(shopcart.id)
        self.assertEqual(found_shopcart.id, shopcart.id)
        self.assertEqual(found_shopcart.customer_id, shopcart.customer_id)
        self.assertEqual(found_shopcart.status, shopcart.status)

    def test_update_a_shopcart(self):
        """It should Update a Shopcart"""
        shopcart = ShopcartFactory()
        shopcart.create()
        self.assertIsNotNone(shopcart.id)
        # Change it and save it
        shopcart.status = "abandoned"
        original_id = shopcart.id
        shopcart.update()
        self.assertEqual(shopcart.id, original_id)
        self.assertEqual(shopcart.status, "abandoned")
        # Fetch it back and make sure the id hasn't changed
        shopcarts = Shopcart.all()
        self.assertEqual(len(shopcarts), 1)
        self.assertEqual(shopcarts[0].id, original_id)
        self.assertEqual(shopcarts[0].status, "abandoned")

    def test_delete_a_shopcart(self):
        """It should Delete a Shopcart"""
        shopcart = ShopcartFactory()
        shopcart.create()
        self.assertEqual(len(Shopcart.all()), 1)
        # Delete the shopcart and make sure it isn't in the database
        shopcart.delete()
        self.assertEqual(len(Shopcart.all()), 0)

    def test_list_all_shopcarts(self):
        """It should List all Shopcarts in the database"""
        shopcarts = Shopcart.all()
        self.assertEqual(shopcarts, [])
        # Create 5 Shopcarts
        for _ in range(5):
            shopcart = ShopcartFactory()
            shopcart.create()
        # See if we get back 5 shopcarts
        shopcarts = Shopcart.all()
        self.assertEqual(len(shopcarts), 5)

    def test_find_by_customer_id(self):
        """It should Find Shopcarts by customer_id"""
        # Create 5 shopcarts with different customer_ids
        shopcarts = ShopcartFactory.create_batch(5)
        for shopcart in shopcarts:
            shopcart.create()
        customer_id = shopcarts[0].customer_id
        # Find shopcarts with that customer_id
        found = Shopcart.find_by_customer_id(customer_id)
        count = found.count()
        # Make sure we get at least one
        self.assertGreater(count, 0)
        # Check that all found shopcarts have the correct customer_id
        for shopcart in found:
            self.assertEqual(shopcart.customer_id, customer_id)

    def test_find_by_status(self):
        """It should Find Shopcarts by Status"""
        # Create 10 shopcarts
        shopcarts = ShopcartFactory.create_batch(10)
        for shopcart in shopcarts:
            shopcart.create()
        status = shopcarts[0].status
        # Find shopcarts with that status
        found = Shopcart.find_by_status(status)
        count = found.count()
        self.assertGreater(count, 0)
        # Check that all found shopcarts have the correct status
        for shopcart in found:
            self.assertEqual(shopcart.status, status)

    def test_serialize_a_shopcart(self):
        """It should serialize a Shopcart"""
        shopcart = ShopcartFactory()
        item = ShopcartItemFactory()
        shopcart.items.append(item)
        data = shopcart.serialize()
        self.assertNotEqual(data, None)
        self.assertIn("id", data)
        self.assertEqual(data["id"], shopcart.id)
        self.assertIn("customer_id", data)
        self.assertEqual(data["customer_id"], shopcart.customer_id)
        self.assertIn("name", data)
        self.assertEqual(data["name"], shopcart.name)
        self.assertIn("status", data)
        self.assertEqual(data["status"], shopcart.status)
        self.assertIn("total_items", data)
        self.assertEqual(data["total_items"], shopcart.total_items)
        self.assertIn("items", data)
        self.assertEqual(len(data["items"]), 1)

    def test_to_eastern_iso_handles_none_and_naive(self):
        """It should convert naive datetimes to Eastern ISO or return None for empty values"""
        self.assertIsNone(Shopcart._to_eastern_iso(None))
        naive = datetime(2024, 1, 1, 12, 0, 0)
        converted = Shopcart._to_eastern_iso(naive)
        self.assertTrue(converted.startswith("2024-01-01T07:00:00"))
        self.assertTrue(converted.endswith("-05:00"))

    def test_deserialize_a_shopcart(self):
        """It should de-serialize a Shopcart"""
        data = {
            "customer_id": 123,
            "status": "active",
            "total_items": 0,
            "name": "Sample cart",
        }
        shopcart = Shopcart()
        shopcart.deserialize(data)
        self.assertNotEqual(shopcart, None)
        self.assertEqual(shopcart.customer_id, 123)
        self.assertEqual(shopcart.status, "active")
        self.assertEqual(shopcart.total_items, 0)
        self.assertEqual(shopcart.name, "Sample cart")

    def test_deserialize_missing_data(self):
        """It should not deserialize a Shopcart with missing data"""
        data = {"status": "active"}
        shopcart = Shopcart()
        self.assertRaises(DataValidationError, shopcart.deserialize, data)

    def test_deserialize_bad_data(self):
        """It should not deserialize bad data"""
        data = "this is not a dictionary"
        shopcart = Shopcart()
        self.assertRaises(DataValidationError, shopcart.deserialize, data)

    def test_deserialize_with_items(self):
        """It should deserialize a Shopcart with items"""
        data = {
            "customer_id": 123,
            "status": "active",
            "items": [
                {
                    "product_id": 456,
                    "quantity": 2,
                    "price": 99.99,
                    "description": "Test Product",
                }
            ],
        }
        shopcart = Shopcart()
        shopcart.deserialize(data)
        self.assertEqual(len(shopcart.items), 1)
        self.assertEqual(shopcart.items[0].product_id, 456)
        self.assertEqual(shopcart.items[0].quantity, 2)

    def test_shopcart_repr(self):
        """It should have a helpful representation"""
        shopcart = ShopcartFactory()
        representation = repr(shopcart)
        self.assertIn(str(shopcart.customer_id), representation)

    def test_shopcart_create_failure(self):
        """It should raise DataValidationError when create fails"""
        shopcart = ShopcartFactory()
        with patch(
            "service.models.db.session.commit", side_effect=Exception("DB error")
        ):
            with self.assertRaises(DataValidationError):
                shopcart.create()
        db.session.rollback()

    def test_shopcart_update_failure(self):
        """It should raise DataValidationError when update fails"""
        shopcart = ShopcartFactory()
        shopcart.create()
        with patch(
            "service.models.db.session.commit", side_effect=Exception("DB error")
        ):
            with self.assertRaises(DataValidationError):
                shopcart.update()
        db.session.rollback()

    def test_shopcart_delete_failure(self):
        """It should raise DataValidationError when delete fails"""
        shopcart = ShopcartFactory()
        shopcart.create()
        with patch(
            "service.models.db.session.commit", side_effect=Exception("DB error")
        ):
            with self.assertRaises(DataValidationError):
                shopcart.delete()
        db.session.rollback()

    def test_shopcart_deserialize_bad_dates(self):
        """It should raise DataValidationError for bad date formats"""
        data = {
            "customer_id": 1,
            "created_date": "not-a-date",
        }
        shopcart = Shopcart()
        self.assertRaises(DataValidationError, shopcart.deserialize, data)

    def test_shopcart_deserialize_attribute_error(self):
        """It should raise DataValidationError when payload lacks dict methods"""

        class MissingGet(dict):
            """Dict-like helper that raises AttributeError on .get(...) to simulate bad payloads."""

            def get(self, *_args, **_kwargs):
                raise AttributeError("get")

        payload = MissingGet({"customer_id": 1, "status": "active"})
        shopcart = Shopcart()
        self.assertRaises(DataValidationError, shopcart.deserialize, payload)

    def test_set_items_bulk_updates_and_total(self):
        """It should bulk apply item adds/updates/removals and keep total_items accurate"""
        sc = Shopcart(customer_id=987654321, status="active", total_items=0)
        sc.create()
        self.assertEqual(sc.total_items, 0)
        self.assertEqual(len(sc.items), 0)

        sc.set_items(
            [
                {"product_id": 9001, "quantity": 2, "price": Decimal("3.5")},
                {"product_id": 9002, "quantity": 3, "price": Decimal("1.0")},
            ]
        )
        sc.update()
        fresh = Shopcart.find(sc.id)
        self.assertEqual(fresh.total_items, 5)
        self.assertTrue(
            any(i.product_id == 9001 and i.quantity == 2 for i in fresh.items)
        )
        self.assertTrue(
            any(i.product_id == 9002 and i.quantity == 3 for i in fresh.items)
        )

        sc.set_items(
            [
                {"product_id": 9001, "quantity": 4, "price": Decimal("3.5")},
                {"product_id": 9002, "quantity": 0},
            ]
        )
        sc.update()
        fresh = Shopcart.find(sc.id)
        self.assertEqual(fresh.total_items, 4)
        self.assertTrue(
            any(i.product_id == 9001 and i.quantity == 4 for i in fresh.items)
        )
        self.assertFalse(any(i.product_id == 9002 for i in fresh.items))

    def test_set_items_rejects_bad_payloads(self):
        """It should raise DataValidationError when payload entries are invalid"""
        sc = Shopcart(customer_id=123, status="active")
        sc.create()

        with self.assertRaises(DataValidationError):
            sc.set_items([{"product_id": "NaN", "quantity": 1, "price": Decimal("1.0")}])

        with self.assertRaises(DataValidationError):
            sc.set_items([{"product_id": 1, "quantity": "foo", "price": Decimal("1.0")}])

        with self.assertRaises(DataValidationError):
            sc.set_items([{"product_id": 1, "quantity": 1, "price": "oops"}])

    def test_upsert_item_handles_missing_reference_on_delete(self):
        """It should swallow missing list entries when removing an item"""
        cart = ShopcartFactory()
        cart.create()
        item = ShopcartItemFactory(shopcart_id=cart.id, product_id=999, quantity=1)
        item.create()
        db.session.refresh(cart)
        self.assertTrue(cart.items)

        with patch.object(cart.items, "remove", side_effect=ValueError("not present")), patch(
            "service.models.shopcart.db.session.delete"
        ) as delete_mock:
            cart.upsert_item(product_id=item.product_id, quantity=0, price=item.price)

        delete_mock.assert_called_once_with(item)
        self.assertEqual(cart.total_items, 1)


######################################################################
#  S H O P C A R T   I T E M   M O D E L   T E S T   C A S E S
######################################################################
class TestShopcartItemModel(TestCase):
    """Test Cases for ShopcartItem Model"""

    @classmethod
    def setUpClass(cls):
        """This runs once before the entire test suite"""
        app.config["TESTING"] = True
        app.config["DEBUG"] = False
        app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URI
        app.logger.setLevel(logging.CRITICAL)
        app.app_context().push()

    @classmethod
    def tearDownClass(cls):
        """This runs once after the entire test suite"""
        db.session.close()

    def setUp(self):
        """This runs before each test"""
        db.session.query(ShopcartItem).delete()
        db.session.query(Shopcart).delete()
        db.session.commit()

    def tearDown(self):
        """This runs after each test"""
        db.session.remove()

    ######################################################################
    #  T E S T   C A S E S
    ######################################################################

    def test_create_a_shopcart_item(self):
        """It should Create a ShopcartItem and assert that it exists"""
        # First create a shopcart
        shopcart = ShopcartFactory()
        shopcart.create()
        # Now create an item
        item = ShopcartItemFactory(shopcart_id=shopcart.id)
        item.create()
        self.assertIsNotNone(item.id)
        found = ShopcartItem.all()
        self.assertEqual(len(found), 1)
        data = ShopcartItem.find(item.id)
        self.assertEqual(data.product_id, item.product_id)
        self.assertEqual(data.shopcart_id, shopcart.id)

    def test_read_a_shopcart_item(self):
        """It should Read a ShopcartItem"""
        shopcart = ShopcartFactory()
        shopcart.create()
        item = ShopcartItemFactory(shopcart_id=shopcart.id)
        item.create()
        # Fetch it back
        found_item = ShopcartItem.find(item.id)
        self.assertEqual(found_item.id, item.id)
        self.assertEqual(found_item.shopcart_id, item.shopcart_id)
        self.assertEqual(found_item.product_id, item.product_id)
        self.assertEqual(found_item.quantity, item.quantity)

    def test_update_a_shopcart_item(self):
        """It should Update a ShopcartItem"""
        shopcart = ShopcartFactory()
        shopcart.create()
        item = ShopcartItemFactory(shopcart_id=shopcart.id)
        item.create()
        # Change it and save it
        item.quantity = 10
        original_id = item.id
        item.update()
        self.assertEqual(item.id, original_id)
        self.assertEqual(item.quantity, 10)
        # Fetch it back
        items = ShopcartItem.all()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].quantity, 10)

    def test_delete_a_shopcart_item(self):
        """It should Delete a ShopcartItem"""
        shopcart = ShopcartFactory()
        shopcart.create()
        item = ShopcartItemFactory(shopcart_id=shopcart.id)
        item.create()
        self.assertEqual(len(ShopcartItem.all()), 1)
        # Delete the item
        item.delete()
        self.assertEqual(len(ShopcartItem.all()), 0)

    def test_list_all_shopcart_items(self):
        """It should List all ShopcartItems in the database"""
        items = ShopcartItem.all()
        self.assertEqual(items, [])
        # Create a shopcart and 5 items
        shopcart = ShopcartFactory()
        shopcart.create()
        for _ in range(5):
            item = ShopcartItemFactory(shopcart_id=shopcart.id)
            item.create()
        # See if we get back 5 items
        items = ShopcartItem.all()
        self.assertEqual(len(items), 5)

    def test_find_by_shopcart_id(self):
        """It should Find ShopcartItems by shopcart_id"""
        # Create 2 shopcarts
        shopcart1 = ShopcartFactory()
        shopcart1.create()
        shopcart2 = ShopcartFactory()
        shopcart2.create()
        # Create items for each shopcart
        for _ in range(3):
            item = ShopcartItemFactory(shopcart_id=shopcart1.id)
            item.create()
        for _ in range(2):
            item = ShopcartItemFactory(shopcart_id=shopcart2.id)
            item.create()
        # Find items for shopcart1
        found = ShopcartItem.find_by_shopcart_id(shopcart1.id)
        self.assertEqual(found.count(), 3)

    def test_find_by_product_id(self):
        """It should Find ShopcartItems by product_id"""
        shopcart = ShopcartFactory()
        shopcart.create()
        # Create items with same product_id
        product_id = 999
        for _ in range(3):
            item = ShopcartItemFactory(shopcart_id=shopcart.id, product_id=product_id)
            item.create()
        # Find items with that product_id
        found = ShopcartItem.find_by_product_id(product_id)
        self.assertEqual(found.count(), 3)

    def test_serialize_a_shopcart_item(self):
        """It should serialize a ShopcartItem"""
        item = ShopcartItemFactory()
        data = item.serialize()
        self.assertNotEqual(data, None)
        self.assertIn("id", data)
        self.assertEqual(data["id"], item.id)
        self.assertIn("shopcart_id", data)
        self.assertEqual(data["shopcart_id"], item.shopcart_id)
        self.assertIn("product_id", data)
        self.assertEqual(data["product_id"], item.product_id)
        self.assertIn("quantity", data)
        self.assertEqual(data["quantity"], item.quantity)
        self.assertIn("price", data)
        self.assertEqual(data["price"], float(item.price))
        self.assertIn("description", data)
        self.assertEqual(data["description"], item.description)

    def test_deserialize_a_shopcart_item(self):
        """It should de-serialize a ShopcartItem"""
        data = {
            "product_id": 456,
            "quantity": 2,
            "price": 99.99,
            "description": "Test Product",
        }
        item = ShopcartItem()
        item.deserialize(data)
        self.assertNotEqual(item, None)
        self.assertEqual(item.product_id, 456)
        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.price, Decimal("99.99"))
        self.assertEqual(item.description, "Test Product")

    def test_deserialize_item_with_shopcart_id(self):
        """It should map optional shopcart_id when present"""
        data = {
            "product_id": 555,
            "quantity": 3,
            "price": 10.50,
            "shopcart_id": 42,
        }
        item = ShopcartItem()
        item.deserialize(data)
        self.assertEqual(item.shopcart_id, 42)

    def test_deserialize_item_missing_data(self):
        """It should not deserialize a ShopcartItem with missing data"""
        data = {"quantity": 2}
        item = ShopcartItem()
        self.assertRaises(DataValidationError, item.deserialize, data)

    def test_deserialize_item_bad_data(self):
        """It should not deserialize bad data"""
        data = "this is not a dictionary"
        item = ShopcartItem()
        self.assertRaises(DataValidationError, item.deserialize, data)

    def test_shopcart_item_repr(self):
        """It should have a helpful representation"""
        item = ShopcartItemFactory()
        self.assertIn(str(item.product_id), repr(item))

    def test_shopcart_item_create_failure(self):
        """It should raise DataValidationError when item create fails"""
        shopcart = ShopcartFactory()
        shopcart.create()
        item = ShopcartItemFactory(shopcart_id=shopcart.id)
        with patch(
            "service.models.db.session.commit", side_effect=Exception("DB item error")
        ):
            with self.assertRaises(DataValidationError):
                item.create()
        db.session.rollback()

    def test_shopcart_item_update_failure(self):
        """It should raise DataValidationError when item update fails"""
        shopcart = ShopcartFactory()
        shopcart.create()
        item = ShopcartItemFactory(shopcart_id=shopcart.id)
        item.create()
        with patch(
            "service.models.db.session.commit", side_effect=Exception("DB item error")
        ):
            with self.assertRaises(DataValidationError):
                item.update()
        db.session.rollback()

    def test_shopcart_item_delete_failure(self):
        """It should raise DataValidationError when item delete fails"""
        shopcart = ShopcartFactory()
        shopcart.create()
        item = ShopcartItemFactory(shopcart_id=shopcart.id)
        item.create()
        with patch(
            "service.models.db.session.commit", side_effect=Exception("DB item error")
        ):
            with self.assertRaises(DataValidationError):
                item.delete()
        db.session.rollback()

    def test_shopcart_item_deserialize_attribute_error(self):
        """It should raise DataValidationError when payload lacks dict methods"""

        class MissingGet(dict):
            """Dict-like helper that raises AttributeError on .get(...) to simulate bad payloads."""

            def get(self, *_args, **_kwargs):
                raise AttributeError("get")

        payload = MissingGet(
            {"product_id": 1, "quantity": 1, "price": Decimal("10.00")}
        )
        item = ShopcartItem()
        self.assertRaises(DataValidationError, item.deserialize, payload)

    def test_shopcart_item_deserialize_value_error(self):
        """It should raise DataValidationError when price conversion fails"""
        item = ShopcartItem()
        with patch("service.models.Decimal", side_effect=ValueError("bad decimal")):
            self.assertRaises(
                DataValidationError,
                item.deserialize,
                {"product_id": 1, "quantity": 1, "price": "oops"},
            )

    def test_cascade_delete(self):
        """It should cascade delete items when shopcart is deleted"""
        # Create a shopcart with items
        shopcart = ShopcartFactory()
        shopcart.create()
        for _ in range(3):
            item = ShopcartItemFactory(shopcart_id=shopcart.id)
            item.create()
        # Verify items exist
        self.assertEqual(len(ShopcartItem.all()), 3)
        # Delete the shopcart
        shopcart.delete()
        # Verify items are also deleted
        self.assertEqual(len(ShopcartItem.all()), 0)
