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

import logging
from unittest import TestCase
from unittest.mock import patch
from flask import Flask
from service import create_app
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
