"""
Shared database utilities for models.
"""
import logging
from decimal import Decimal as _Decimal

from flask_sqlalchemy import SQLAlchemy

logger = logging.getLogger("flask.app")

# Global SQLAlchemy handle initialized in the app factory
db = SQLAlchemy()

# Expose Decimal so callers can patch service.models.Decimal in tests
Decimal = _Decimal  # pylint: disable=invalid-name


class DataValidationError(Exception):
    """Used for data validation errors when deserializing"""


class CRUDMixin:
    """Common create/update/delete helpers with consistent error handling."""

    def _perform_db_action(self, action: str, work):
        """Execute a DB action and handle rollback/logging on failure."""
        try:
            work()
            db.session.commit()
        except Exception as error:  # pylint: disable=broad-except
            db.session.rollback()
            logger.error("Error %s record: %s", action, self)
            raise DataValidationError(error) from error

    def create(self):
        """Add the record to the session and commit."""
        self.id = None  # pylint: disable=invalid-name
        self._perform_db_action("creating", lambda: db.session.add(self))

    def update(self):
        """Commit pending changes for this record."""
        self._perform_db_action("updating", lambda: None)

    def delete(self):
        """Delete the record from the session and commit."""
        self._perform_db_action("deleting", lambda: db.session.delete(self))
