"""
Models for Shopcart

All of the models are stored in this module
"""

import logging
from datetime import datetime
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
            "created_date": self.created_date.isoformat() if self.created_date else None,
            "last_modified": self.last_modified.isoformat() if self.last_modified else None,
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
    
    @classmethod
    def list_shopcarts(cls, 
                       customer_id=None, 
                       status="active", 
                       start_date=None,
                       end_date=None,
                       page=1,
                       limit=10
                       ):
        """
        Returns a paginated list of shopcarts with optional filters.

        Args:
            customer_id (int): filter by customer ID
            status (str): filter by status ("active"/"abandoned"/"completed"), default "active"
            start_date (datetime): filter created_date >= start_date
            end_date (datetime): filter created_date <= end_date
            page (int): pagination page number (1-based)
            limit (int): number of records per page
        """
        logger.info("Listing shopcarts (customer_id=%s, status=%s, page=%d, limit=%d)",
                    customer_id, status, page, limit)

        query = cls.query

        if status:
            query = query.filter(cls.status == status)

        if customer_id:
            query = query.filter(cls.customer_id == customer_id)

        if start_date:
            query = query.filter(cls.created_date >= start_date)

        if end_date:
            query = query.filter(cls.created_date <= end_date)

        total = query.count()

        results = query.order_by(cls.created_date.desc()) \
                       .offset((page - 1) * limit) \
                       .limit(limit) \
                       .all()

        has_next = total > page * limit

        return {
            "shopcarts": [cart.serialize() for cart in results],
            "pagination": {
                "total": total,
                "page": page,
                "limit": limit,
                "hasNext": has_next
            }
        }


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
