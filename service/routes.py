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
Core service routes that are not part of the RESTX API namespace.
"""
# pylint: disable=unused-import

from flask import abort, jsonify, redirect, request
from flask import current_app as app  # Import Flask application

from service.common import status
from service.models import Shopcart  # noqa: F401


######################################################################
# Checks the ContentType of a request
######################################################################
def check_content_type(content_type) -> None:
    """Checks that the media type is correct."""
    if "Content-Type" not in request.headers:
        app.logger.error("No Content-Type specified.")
        abort(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"Content-Type must be {content_type}",
        )

    if request.headers["Content-Type"] == content_type:
        return

    app.logger.error("Invalid Content-Type: %s", request.headers["Content-Type"])
    abort(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, f"Content-Type must be {content_type}")


######################################################################
# HEALTH CHECK ENDPOINT
######################################################################
@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint for Kubernetes."""
    return jsonify({"status": "OK"}), status.HTTP_200_OK


######################################################################
# GET INDEX
######################################################################
@app.route("/", methods=["GET"])
def index():
    """Return service metadata, or redirect browsers to the UI."""
    accept = request.headers.get("Accept", "")
    # If a browser hits "/" (Accept usually includes text/html), send it to the UI.
    if "text/html" in accept.lower():  # pragma: no cover (convenience path for browsers)
        return redirect("/ui", code=302)

    response = {
        "description": "This service manages customer shopcarts and their items.",
        "name": "Shopcart REST API Service",
        "version": "1.0.0",
        "paths": {
            "shopcarts": "/api/shopcarts",
            "docs": "/apidocs/",
            "ui": "/ui",
        },
    }
    return jsonify(response), status.HTTP_200_OK


######################################################################
# ADMIN UI
######################################################################
@app.route("/ui", methods=["GET"])
@app.route("/admin", methods=["GET"])
def admin_ui():
    """Serve the single-page admin console."""
    return app.send_static_file("index.html")
