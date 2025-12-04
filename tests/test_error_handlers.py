"""Unit tests for JSON error handlers."""
# pylint: disable=missing-function-docstring,missing-class-docstring,too-few-public-methods

from unittest import TestCase

from flask_restx.errors import ValidationError
from werkzeug.exceptions import InternalServerError, NotFound

from service.common import error_handlers, status
from wsgi import app


class TestErrorHandlers(TestCase):
    """Validate JSON error responses and message extraction."""

    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.ctx = app.app_context()
        cls.ctx.push()

    @classmethod
    def tearDownClass(cls):
        cls.ctx.pop()

    def test_validation_error_includes_field_details(self):
        err = ValidationError("Input payload validation failed")
        err.data = {"errors": {"quantity": "not int"}}
        response, code = error_handlers.handle_validation_error(err)
        payload = response.get_json()
        self.assertEqual(code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("quantity", payload["message"])

    def test_http_exception_returns_json(self):
        err = NotFound("missing resource")
        response, code = error_handlers.handle_http_exception(err)
        payload = response.get_json()
        self.assertEqual(code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(payload["status"], status.HTTP_404_NOT_FOUND)
        self.assertIn("Not Found", payload["error"])
        self.assertIn("missing resource", payload["message"])

    def test_unhandled_exception_returns_json_500(self):
        err = RuntimeError("boom")
        response, code = error_handlers.handle_unhandled_exception(err)
        payload = response.get_json()
        self.assertEqual(code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(payload["status"], status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(payload["message"], "An unexpected error occurred.")

    def test_extract_message_prefers_validation_errors_dict(self):
        err = ValidationError("fail")
        err.data = {"errors": {"price": "invalid"}}
        message = error_handlers._extract_message(err)  # pylint: disable=protected-access
        self.assertIn("price", message)

    def test_extract_message_falls_back_to_http_data_message(self):
        class FakeHTTPException(InternalServerError):
            def __init__(self):
                super().__init__("server exploded")
                self.data = {"message": "custom failure message"}

        err = FakeHTTPException()
        message = error_handlers._extract_message(err)  # pylint: disable=protected-access
        self.assertIn("custom failure message", message)

    def test_extract_message_uses_http_error_dict(self):
        class FakeHTTPException(InternalServerError):
            def __init__(self):
                super().__init__("server exploded")
                self.data = {"errors": {"field": "oops"}}

        err = FakeHTTPException()
        message = error_handlers._extract_message(err)  # pylint: disable=protected-access
        self.assertIn("field", message)

    def test_extract_message_uses_http_error_list(self):
        class FakeHTTPException(InternalServerError):
            def __init__(self):
                super().__init__("server exploded")
                self.data = {"errors": ["oops"]}

        err = FakeHTTPException()
        message = error_handlers._extract_message(err)  # pylint: disable=protected-access
        self.assertIn("oops", message)

    def test_extract_message_handles_non_dict_error_collection(self):
        err = ValidationError("fail")
        err.data = {"errors": ["bad", "worse"]}
        message = error_handlers._extract_message(err)  # pylint: disable=protected-access
        self.assertIn("bad", message)

    def test_extract_message_prefers_description_when_present(self):
        err = ValidationError("fail")
        err.description = "use this description"
        message = error_handlers._extract_message(err)  # pylint: disable=protected-access
        self.assertEqual(message, "use this description")

    def test_extract_message_prefers_message_attribute(self):
        class FakeError:
            def __init__(self):
                self.message = "use-message-attr"

        err = FakeError()
        message = error_handlers._extract_message(err)  # pylint: disable=protected-access
        self.assertEqual(message, "use-message-attr")

    def test_extract_message_defaults_to_str_error(self):
        class BareError(Exception):
            pass

        err = BareError("fallback string")
        message = error_handlers._extract_message(err)  # pylint: disable=protected-access
        self.assertEqual(message, "fallback string")
