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

"""Tests for application factory and logging utilities."""
# pylint: disable=missing-function-docstring, too-few-public-methods

import logging
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from flask import Flask
from sqlalchemy.exc import SQLAlchemyError

from service import create_app
from service.__init__ import _ensure_optional_columns
from service.common import log_handlers


class TestLoggingUtilities(TestCase):
    """Validate logging helper behaviour."""

    def test_init_logging_applies_formatter(self):
        """It should copy handlers and apply the standard formatter."""
        app = Flask(__name__)
        logger = logging.getLogger("test_logger")
        original_handlers = list(logger.handlers)

        handler = logging.StreamHandler()
        logger.handlers = [handler]
        logger.setLevel(logging.INFO)

        try:
            log_handlers.init_logging(app, "test_logger")
            self.assertEqual(app.logger.handlers, logger.handlers)
            self.assertIsNotNone(handler.formatter)
            self.assertIn("%(levelname)s", handler.formatter._fmt)
        finally:
            logger.handlers = original_handlers
            app.logger.handlers = []


class TestAppFactory(TestCase):
    """Ensure the application factory handles failures gracefully."""

    def test_create_app_exits_when_database_setup_fails(self):
        """It should exit with code 4 if database initialization fails."""
        with patch(
            "service.models.db.create_all", side_effect=RuntimeError("db boom")
        ), patch("service.common.log_handlers.init_logging"), self.assertRaises(
            SystemExit
        ) as raised:
            create_app()

        self.assertEqual(raised.exception.code, 4)


class TestOptionalColumnBackfill(TestCase):
    """Unit tests for the optional column backfill helper."""

    def _make_fake_db(self, connection, rollback_flag):
        """Build a minimal fake db object for backfill testing."""
        def _fake_begin():
            return _BeginContext(connection)

        def _fake_rollback():
            rollback_flag["called"] = True

        return SimpleNamespace(
            engine=SimpleNamespace(begin=_fake_begin),
            session=SimpleNamespace(rollback=_fake_rollback),
        )

    def test_adds_missing_name_column(self):
        """It should issue the ALTER TABLE when the name column is missing."""
        captures = {"sql": None, "called": False}

        fake_db = self._make_fake_db(_RecordingConnection(captures), captures)
        app = Flask(__name__)
        with app.app_context(), patch(
            "service.__init__.inspect", return_value=_MissingNameInspector()
        ):
            _ensure_optional_columns(fake_db)

        self.assertIsNotNone(captures["sql"])
        self.assertIn("alter table shopcarts add column name", captures["sql"].lower())
        self.assertFalse(captures["called"])

    def test_handles_sqlalchemy_errors(self):
        """It should roll back when ALTER TABLE fails."""
        captures = {"called": False}

        fake_db = self._make_fake_db(_FailingConnection(), captures)
        app = Flask(__name__)
        with app.app_context(), patch(
            "service.__init__.inspect", return_value=_MissingNameInspector()
        ):
            _ensure_optional_columns(fake_db)

        self.assertTrue(captures["called"])


class _BeginContext:
    """Simple context manager for fake database connections."""

    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self.connection

    def __exit__(self, exc_type, exc, tb):
        return False


class _RecordingConnection:
    """Fake connection that records executed SQL."""

    def __init__(self, captures):
        self.captures = captures

    def execute(self, statement):
        self.captures["sql"] = str(statement)


class _MissingNameInspector:
    """Inspector whose table misses the name column."""

    def get_columns(self, _):
        return [{"name": "customer_id"}]


class _FailingConnection:
    """Fake connection that raises SQLAlchemy errors."""

    def execute(self, statement):
        raise SQLAlchemyError(f"cannot run {statement}")
