"""
Models for Shopcart

All of the models are stored in this module
"""

import logging
from datetime import datetime
import decimal
from decimal import Decimal
from flask_sqlalchemy import SQLAlchemy

logger = logging.getLogger("flask.app")

# Create the SQLAlchemy object to be initialized later in init_db()
db = SQLAlchemy()


class DataValidationError(Exception):
    """Used for an data validation errors when deserializing"""


class Shopcart(db.Model):
    """
    Class that represents a Shopcart
    """

    ##################################################
    # Table Schema
    ##################################################
    __tablename__ = "shopcarts"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, nullable=False)
    created_date = db.Column(db.DateTime(), nullable=False, default=datetime.utcnow)
    last_modified = db.Column(
        db.DateTime(), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    status = db.Column(db.String(20), nullable=False, default="active")
    total_items = db.Column(db.Integer, default=0)

    # Relationship: One Shopcart has many ShopcartItems
    items = db.relationship(
        "ShopcartItem",
        backref="shopcart",
        cascade="all, delete-orphan",
        lazy=True,
    )

    def __repr__(self):
        return f"<Shopcart customer_id={self.customer_id} id=[{self.id}]>"

    def create(self):
        """
        Creates a Shopcart to the database
        """
        logger.info("Creating Shopcart for customer %s", self.customer_id)
        self.id = None  # pylint: disable=invalid-name
        try:
            db.session.add(self)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error("Error creating record: %s", self)
            raise DataValidationError(e) from e

    def update(self):
        """
        Updates a Shopcart to the database
        """
        logger.info("Saving Shopcart with id: %s", self.id)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error("Error updating record: %s", self)
            raise DataValidationError(e) from e

    def delete(self):
        """Removes a Shopcart from the data store"""
        logger.info("Deleting Shopcart with id: %s", self.id)
        try:
            db.session.delete(self)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error("Error deleting record: %s", self)
            raise DataValidationError(e) from e

    def serialize(self):
        """Serializes a Shopcart into a dictionary"""
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "created_date": (
                self.created_date.isoformat() if self.created_date else None
            ),
            "last_modified": (
                self.last_modified.isoformat() if self.last_modified else None
            ),
            "status": self.status,
            "total_items": self.total_items,
            "items": [item.serialize() for item in self.items],
        }

    def deserialize(self, data):
        """
        Deserializes a Shopcart from a dictionary

        Args:
            data (dict): A dictionary containing the resource data
        """
        try:
            self.customer_id = data["customer_id"]
            self.status = data.get("status", "active")
            self.total_items = data.get("total_items", 0)

            # Handle optional date fields
            if "created_date" in data:
                self.created_date = datetime.fromisoformat(data["created_date"])
            if "last_modified" in data:
                self.last_modified = datetime.fromisoformat(data["last_modified"])

            # Handle nested items
            if "items" in data:
                self.items = []
                for item_data in data["items"]:
                    item = ShopcartItem()
                    item.deserialize(item_data)
                    self.items.append(item)

        except AttributeError as error:
            raise DataValidationError("Invalid attribute: " + error.args[0]) from error
        except KeyError as error:
            raise DataValidationError(
                "Invalid Shopcart: missing " + error.args[0]
            ) from error
        except TypeError as error:
            raise DataValidationError(
                "Invalid Shopcart: body of request contained bad or no data "
                + str(error)
            ) from error
        except ValueError as error:
            raise DataValidationError(
                "Invalid Shopcart: bad data format " + str(error)
            ) from error
        return self

    def upsert_item(self, product_id, quantity, price, description=""):
        """Add or update an item by product_id; quantity<=0 deletes it. Does not commit."""
        existing = None
        for it in getattr(self, "items", []):
            if int(getattr(it, "product_id", -1)) == int(product_id):
                existing = it
                break

        if quantity is None or int(quantity) <= 0:
            if existing is not None:
                db.session.delete(existing)
                try:
                    self.items.remove(existing)
                except ValueError:
                    pass
        else:
            if existing is None:
                new_item = ShopcartItem(
                    shopcart_id=self.id,
                    product_id=int(product_id),
                    quantity=int(quantity),
                    price=price,
                    description=description or "",
                )
                db.session.add(new_item)
                if hasattr(self, "items"):
                    self.items.append(new_item)
            else:
                existing.quantity = int(quantity)
                existing.price = price
                if description:
                    existing.description = description

        total = 0
        for it in getattr(self, "items", []):
            try:
                total += int(getattr(it, "quantity", 0) or 0)
            except (TypeError, ValueError):
                continue
        self.total_items = int(total)

    def remove_item(self, product_id: int):
        """Remove an item by product_id. Does not commit."""
        return self.upsert_item(product_id=product_id, quantity=0, price=0)

    def set_items(self, items_payload: list):
        """
        Bulk, idempotent application of item changes:
        - quantity > 0 => add or update
        - quantity <= 0 => remove
        Recomputes total_items at the end.
        """
        items = items_payload or []

        for item in items:
            try:
                product_id = int(item["product_id"])
            except (KeyError, TypeError, ValueError) as e:
                raise DataValidationError(f"Invalid product_id: {item!r}") from e

            try:
                quantity = int(item.get("quantity", 0))
            except (TypeError, ValueError) as e:
                raise DataValidationError(f"Invalid quantity: {item!r}") from e

            price_raw = item.get("price", 0)
            try:
                price = Decimal(str(price_raw))
            except (decimal.InvalidOperation, ValueError, TypeError) as e:
                raise DataValidationError(f"Invalid price: {price_raw!r}") from e

            description = item.get("description", "")

            if quantity <= 0:
                if hasattr(self, "remove_item"):
                    self.remove_item(product_id)
                else:
                    self.upsert_item(
                        product_id=product_id,
                        quantity=0,
                        price=Decimal(0),
                        description=description,
                    )
            else:
                self.upsert_item(
                    product_id=product_id,
                    quantity=quantity,
                    price=price,
                    description=description,
                )

        total = 0
        if hasattr(self, "items"):
            for i in self.items:
                try:
                    total += int(getattr(i, "quantity", 0) or 0)
                except (TypeError, ValueError):
                    continue
        self.total_items = int(total)

    ##################################################
    # CLASS METHODS
    ##################################################

    @classmethod
    def all(cls):
        """Returns all of the Shopcarts in the database"""
        logger.info("Processing all Shopcarts")
        return cls.query.all()

    @classmethod
    def find(cls, by_id):
        """Finds a Shopcart by it's ID"""
        logger.info("Processing lookup for id %s ...", by_id)
        return cls.query.session.get(cls, by_id)

    @classmethod
    def find_by_customer_id(cls, customer_id):
        """Returns all Shopcarts with the given customer_id

        Args:
            customer_id (int): the customer_id of the Shopcarts you want to match
        """
        logger.info("Processing customer_id query for %s ...", customer_id)
        return cls.query.filter(cls.customer_id == customer_id)

    @classmethod
    def find_by_status(cls, status):
        """Returns all Shopcarts with the given status

        Args:
            status (string): the status of the Shopcarts you want to match
        """
        logger.info("Processing status query for %s ...", status)
        return cls.query.filter(cls.status == status)


######################################################################
#  S H O P C A R T   I T E M   M O D E L
######################################################################
class ShopcartItem(db.Model):
    """
    Class that represents a Shopcart Item
    """

    ##################################################
    # Table Schema
    ##################################################
    __tablename__ = "shopcart_items"

    id = db.Column(db.Integer, primary_key=True)
    shopcart_id = db.Column(
        db.Integer,
        db.ForeignKey("shopcarts.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id = db.Column(db.Integer, nullable=False)
    description = db.Column(db.String(256))
    quantity = db.Column(db.Integer, nullable=False, default=1)
    price = db.Column(db.Numeric(10, 2), nullable=False)

    def __repr__(self):
        return f"<ShopcartItem id=[{self.id}] shopcart_id=[{self.shopcart_id}] product_id=[{self.product_id}]>"

    def create(self):
        """
        Creates a ShopcartItem to the database
        """
        logger.info("Creating ShopcartItem for product %s", self.product_id)
        self.id = None  # pylint: disable=invalid-name
        try:
            db.session.add(self)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error("Error creating record: %s", self)
            raise DataValidationError(e) from e

    def update(self):
        """
        Updates a ShopcartItem to the database
        """
        logger.info("Saving ShopcartItem with id: %s", self.id)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error("Error updating record: %s", self)
            raise DataValidationError(e) from e

    def delete(self):
        """Removes a ShopcartItem from the data store"""
        logger.info("Deleting ShopcartItem with id: %s", self.id)
        try:
            db.session.delete(self)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error("Error deleting record: %s", self)
            raise DataValidationError(e) from e

    def serialize(self):
        """Serializes a ShopcartItem into a dictionary"""
        return {
            "id": self.id,
            "shopcart_id": self.shopcart_id,
            "product_id": self.product_id,
            "description": self.description,
            "quantity": self.quantity,
            "price": float(self.price),
        }

    def deserialize(self, data):
        """
        Deserializes a ShopcartItem from a dictionary

        Args:
            data (dict): A dictionary containing the resource data
        """
        try:
            self.product_id = data["product_id"]
            self.quantity = data["quantity"]
            self.price = Decimal(str(data["price"]))

            # Optional fields
            self.description = data.get("description", "")
            if "shopcart_id" in data:
                self.shopcart_id = data["shopcart_id"]

        except AttributeError as error:
            raise DataValidationError("Invalid attribute: " + error.args[0]) from error
        except KeyError as error:
            raise DataValidationError(
                "Invalid ShopcartItem: missing " + error.args[0]
            ) from error
        except TypeError as error:
            raise DataValidationError(
                "Invalid ShopcartItem: body of request contained bad or no data "
                + str(error)
            ) from error
        except ValueError as error:
            raise DataValidationError(
                "Invalid ShopcartItem: bad data format " + str(error)
            ) from error
        return self

    ##################################################
    # CLASS METHODS
    ##################################################

    @classmethod
    def all(cls):
        """Returns all of the ShopcartItems in the database"""
        logger.info("Processing all ShopcartItems")
        return cls.query.all()

    @classmethod
    def find(cls, by_id):
        """Finds a ShopcartItem by it's ID"""
        logger.info("Processing lookup for id %s ...", by_id)
        return cls.query.session.get(cls, by_id)

    @classmethod
    def find_by_shopcart_id(cls, shopcart_id):
        """Returns all ShopcartItems with the given shopcart_id

        Args:
            shopcart_id (int): the shopcart_id of the ShopcartItems you want to match
        """
        logger.info("Processing shopcart_id query for %s ...", shopcart_id)
        return cls.query.filter(cls.shopcart_id == shopcart_id)

    @classmethod
    def find_by_product_id(cls, product_id):
        """Returns all ShopcartItems with the given product_id

        Args:
            product_id (int): the product_id of the ShopcartItems you want to match
        """
        logger.info("Processing product_id query for %s ...", product_id)
        return cls.query.filter(cls.product_id == product_id)
