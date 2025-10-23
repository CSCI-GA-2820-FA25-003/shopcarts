"""
Shopcart model definition.
"""
import decimal
import logging
from datetime import datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from .base import CRUDMixin, DataValidationError, db

logger = logging.getLogger("flask.app")
EASTERN_ZONE = ZoneInfo("America/New_York")


class Shopcart(CRUDMixin, db.Model):
    """Represents a customer's shopcart."""

    VALID_STATUSES = frozenset({"active", "abandoned"})

    @staticmethod
    def _to_eastern_iso(value):
        """Return an ISO8601 string converted to US Eastern time."""
        if not value:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(EASTERN_ZONE).isoformat()

    @staticmethod
    def _decimal():
        """Fetch Decimal lazily so tests can patch service.models.Decimal."""
        from importlib import import_module  # pylint: disable=import-outside-toplevel

        return import_module("service.models").Decimal

    ##################################################
    # Table Schema
    ##################################################
    __tablename__ = "shopcarts"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, nullable=False, unique=True)
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

    ##################################################
    __tablename__ = "shopcarts"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, nullable=False, unique=True)
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

    # ------------------------------------------------------------------
    # CRUD OPERATIONS (logging + shared mixin behaviour)
    # ------------------------------------------------------------------
    def create(self):
        logger.info("Creating Shopcart for customer %s", self.customer_id)
        super().create()

    def update(self):
        logger.info("Saving Shopcart with id: %s", self.id)
        super().update()

    def delete(self):
        logger.info("Deleting Shopcart with id: %s", self.id)
        super().delete()

    # ------------------------------------------------------------------
    # SERIALIZATION
    # ------------------------------------------------------------------
    def serialize(self):
        """Serializes a Shopcart into a dictionary"""
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "created_date": self._to_eastern_iso(self.created_date),
            "last_modified": self._to_eastern_iso(self.last_modified),
            "status": self.status,
            "total_items": self.total_items,
            "items": [item.serialize() for item in self.items],
        }

    def to_customer_view(self):
        """Return an API-facing representation with computed totals and camelCase keys."""
        items = []
        total_quantity = 0
        total_price = Decimal("0")

        for item in getattr(self, "items", []):
            quantity = int(item.quantity or 0)
            price = item.price or Decimal("0")
            total_quantity += quantity
            total_price += price * quantity
            items.append(
                {
                    "itemId": item.id,
                    "productId": item.product_id,
                    "description": item.description,
                    "quantity": quantity,
                    "price": float(price),
                }
            )

        return {
            "customerId": self.customer_id,
            "createdDate": self._to_eastern_iso(self.created_date),
            "lastModified": self._to_eastern_iso(self.last_modified),
            "status": self.status,
            "totalItems": total_quantity,
            "totalPrice": float(total_price),
            "items": items,
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

            if "created_date" in data:
                self.created_date = datetime.fromisoformat(data["created_date"])
            if "last_modified" in data:
                self.last_modified = datetime.fromisoformat(data["last_modified"])

            if "items" in data:
                from .shopcart_item import ShopcartItem  # pylint: disable=import-outside-toplevel

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

    # ------------------------------------------------------------------
    # ITEM HELPERS
    # ------------------------------------------------------------------
    def upsert_item(self, product_id, quantity, price, description=""):
        """Add or update an item by product_id; quantity<=0 deletes it. Does not commit."""
        existing = next(
            (
                item
                for item in getattr(self, "items", [])
                if int(getattr(item, "product_id", -1)) == int(product_id)
            ),
            None,
        )
        if quantity is None or int(quantity) <= 0:
            if existing is not None:
                db.session.delete(existing)
                try:
                    self.items.remove(existing)
                except ValueError:
                    pass
        else:
            from .shopcart_item import ShopcartItem  # pylint: disable=import-outside-toplevel

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
        self.total_items = int(
            sum(
                int(getattr(item, "quantity", 0) or 0)
                for item in getattr(self, "items", [])
            )
        )

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
        for item in items_payload or []:
            try:
                product_id = int(item["product_id"])
            except (KeyError, TypeError, ValueError) as error:
                raise DataValidationError(f"Invalid product_id: {item!r}") from error
            try:
                quantity = int(item.get("quantity", 0))
            except (TypeError, ValueError) as error:
                raise DataValidationError(f"Invalid quantity: {item!r}") from error
            price_raw = item.get("price", 0)
            try:
                price = self._decimal()(str(price_raw))
            except (decimal.InvalidOperation, ValueError, TypeError) as error:
                raise DataValidationError(f"Invalid price: {price_raw!r}") from error
            description = item.get("description", "")
            if quantity <= 0:
                self.remove_item(product_id)
            else:
                self.upsert_item(
                    product_id=product_id,
                    quantity=quantity,
                    price=price,
                    description=description,
                )
        self.total_items = int(
            sum(
                int(getattr(item, "quantity", 0) or 0)
                for item in getattr(self, "items", [])
            )
        )

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
        """Returns all Shopcarts with the given customer_id"""
        logger.info("Processing customer_id query for %s ...", customer_id)
        return cls.query.filter(cls.customer_id == customer_id)

    @classmethod
    def find_by_status(cls, status):
        """Returns all Shopcarts with the given status"""
        logger.info("Processing status query for %s ...", status)
        return cls.query.filter(cls.status == status)

    @classmethod
    def allowed_statuses(cls):
        """Return the set of valid status values."""
        return cls.VALID_STATUSES
