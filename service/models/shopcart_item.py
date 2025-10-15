"""
Shopcart item model definition.
"""
import logging

from .base import CRUDMixin, DataValidationError, db

logger = logging.getLogger("flask.app")


class ShopcartItem(CRUDMixin, db.Model):
    """Represents an item stored inside a shopcart."""

    @staticmethod
    def _decimal():
        """Fetch Decimal lazily so tests can patch service.models.Decimal."""
        from importlib import import_module  # pylint: disable=import-outside-toplevel

        return import_module("service.models").Decimal

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
        return (
            f"<ShopcartItem id=[{self.id}] "
            f"shopcart_id=[{self.shopcart_id}] product_id=[{self.product_id}]>"
        )

    # ------------------------------------------------------------------
    # CRUD OPERATIONS (logging + shared mixin behaviour)
    # ------------------------------------------------------------------
    def create(self):
        logger.info("Creating ShopcartItem for product %s", self.product_id)
        super().create()

    def update(self):
        logger.info("Saving ShopcartItem with id: %s", self.id)
        super().update()

    def delete(self):
        logger.info("Deleting ShopcartItem with id: %s", self.id)
        super().delete()

    # ------------------------------------------------------------------
    # SERIALIZATION
    # ------------------------------------------------------------------
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
            self.price = self._decimal()(str(data["price"]))

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

    # ------------------------------------------------------------------
    # CLASS METHODS
    # ------------------------------------------------------------------
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
        """Returns all ShopcartItems with the given shopcart_id"""
        logger.info("Processing shopcart_id query for %s ...", shopcart_id)
        return cls.query.filter(cls.shopcart_id == shopcart_id)

    @classmethod
    def find_by_product_id(cls, product_id):
        """Returns all ShopcartItems with the given product_id"""
        logger.info("Processing product_id query for %s ...", product_id)
        return cls.query.filter(cls.product_id == product_id)
