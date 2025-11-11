[![Build Status](https://github.com/CSCI-GA-2820-FA25-003/shopcarts/actions/workflows/workflow.yml/badge.svg)](https://github.com/CSCI-GA-2820-FA25-003/shopcarts/actions)
[![codecov](https://codecov.io/gh/CSCI-GA-2820-FA25-003/shopcarts/graph/badge.svg?token=9AM1PN2UYK)](https://codecov.io/gh/CSCI-GA-2820-FA25-003/shopcarts)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Language-Python-blue.svg)](https://python.org/)

# Shopcart REST API Service

This project implements a Flask-based REST API for managing customer shopcarts and their items. It is the reference implementation used in the NYU DevOps course and extends the original project template with a working service, database models, and automated tests.

## Prerequisites
- Python 3.11
- `pipenv` (or another preferred environment manager)
- PostgreSQL (local or containerised) reachable by the Flask app
- Docker (required for building or running the provided container workflows)

The service automatically creates the database tables on startup.

## Contents
The project contains the following key files and directories:

```text
LICENSE             - Apache 2.0 license notice
Makefile            - Common automation targets (install, test, lint, run, etc.)
Pipfile             - Python dependency definitions (Pipenv)
Pipfile.lock        - Locked dependency versions
Procfile            - Honcho/Gunicorn process specification
dot-env-example     - Sample environment variable configuration
wsgi.py             - WSGI entry point exposing the Flask app
service/            - Flask service package
├── __init__.py     - Application factory and initialization
├── config.py       - Service configuration settings
├── routes.py       - REST API route handlers
├── models/         - SQLAlchemy models for shopcarts and items
│   ├── __init__.py - Model package initializer
│   ├── base.py     - Shared DB mixins and utilities
│   ├── shopcart.py - Shopcart model definition
│   └── shopcart_item.py - Shopcart item model
└── common/         - Shared helpers and CLI commands
    ├── cli_commands.py  - Flask CLI to recreate tables
    ├── error_handlers.py - Custom JSON error responses
    ├── log_handlers.py  - Logging configuration
    └── status.py        - HTTP status constants
tests/              - Automated test suites
├── __init__.py     - Test package initializer
├── factories.py    - Factory helpers for generating test data
├── test_cli_commands.py - Tests for CLI utilities
├── test_models.py  - Tests for model behaviour
└── test_routes.py  - Tests for REST API endpoints
```

## Local Setup
1. Clone the repository and move into the project directory.
2. Install dependencies  
   - Recommended: `pipenv install --dev`  
   - Alternative: `make install` (requires `sudo` and `pipenv` on your `PATH`)
3. Copy environment defaults and set the Flask app entry point:
   ```bash
   cp dot-env-example .env        # optional but keeps variables together
   export FLASK_APP=wsgi:app
   ```

## Configuration
- `DATABASE_URI` (default: `postgresql+psycopg://postgres:postgres@localhost:5432/shopcarts`)  
  Override to point at a different PostgreSQL instance. Use the `postgresql+psycopg` dialect so SQLAlchemy loads the correct driver.
- `SECRET_KEY` (default: `sup3r-s3cr3t`)  
  Flask secret used for session management.
- `LOGGING_LEVEL` (default: `INFO`)  
  Adjust via standard Python logging configuration if you need more verbose output.

Quick local database via Docker:
```bash
docker run --name shopcarts-db -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=shopcarts -p 5432:5432 -d postgres:16
```

## Running the Service
Choose one of the following:
- `pipenv run flask run` (default Flask dev server on `http://127.0.0.1:5000`)
- `make run` (uses Honcho to launch Gunicorn via the `Procfile`, binding to `http://127.0.0.1:8080`)

When the service starts you should see log output confirming the database tables were created and the server is accepting requests. A lightweight health probe is available at `GET /health`.

## Admin UI
Requirement #80 adds a lightweight administrator console backed by the same REST API. Once the Flask app is running, open [`http://localhost:5000/ui`](http://localhost:5000/ui) (alias `/admin`) or, if you started the service via `make run`, [`http://localhost:8080/ui`](http://localhost:8080/ui). All buttons submit requests to the live endpoints, so you can drive the service exactly the way Selenium/Behave tests will.

The UI currently supports:
- **Create**: enter a `customer_id`, optional cart `name`, and optional status to POST `/shopcarts`. Successful submissions surface the `"Shopcart created successfully"` toast and immediately refresh the grid.
- **Read**: fetch a single cart by customer id and inspect its metadata/items.
- **Update**: change the cart status with PUT `/shopcarts/<customer_id>`.
- **Delete**: remove a cart in one click—either via the delete form or the new Delete Cart button on the detail panel.
- **List/Query**: filter `/shopcarts` by customer id, friendly statuses (`OPEN`, `ABANDONED`, `PURCHASED`, `MERGED`), or min/max totals. Invalid ranges are rejected client-side with a warning toast, and a **Clear Filters** button resets the form/table in one click.
- **Action**: run helper endpoints (`checkout`, `cancel`, `lock`, `expire`, `reactivate`) to demonstrate the extra workflow action.

The results section shows both the focused cart (for scenario-by-scenario verification) and a live table of all carts returned by the latest query so that CRUD workflows remain visible while you test. Status pills are automatically uppercased (`OPEN`, `LOCKED`, etc.) to match the stakeholder wording used in the BDD scenarios.

## BDD UI Scenarios
Requirement #82 adds automated UI coverage using Behave + Selenium:
1. Start the Flask service locally (e.g., `make run`).  
2. Ensure a Chromium/Chrome browser _and_ matching chromedriver are available (for Debian-based systems: `sudo apt-get install -y chromium chromium-driver`).  
3. In another terminal execute `make bdd` (defaults to `BASE_URL=http://127.0.0.1:8080`; override with `BASE_URL=<url>` if needed).

The feature file `features/shopcarts.feature` exercises the full flow:
- Successful cart creation (Customer ID + optional name) displays the confirmation toast and lists the new cart with status `OPEN`.
- Submitting the Create Cart form without a Customer ID produces the validation error “Customer ID is required” and leaves the list untouched.
- Deleting a cart from the detail panel via the **Delete Cart** button requests confirmation, removes the cart, and surfaces the success toast (with error coverage when the cart is already gone).
- Querying the REST API by customer id, friendly statuses, and min/max totals—plus negative cases for invalid parameters.
- UI-specific scenarios that drive the new filters, ensure the grid updates dynamically, validate bad ranges, and verify the **Clear Filters** reset behavior.

Selenium downloads a headless Chrome driver via `webdriver-manager`. Ensure the UI remains accessible during the run; Behave only interacts with the service through the `/ui` page.

## Running Tests and Quality Checks
- Unit tests with coverage: `make test` (or `pytest --pspec --cov=service --disable-warnings`)
- Linting: `make lint`

All tests require the service dependencies to be installed and a database connection available (the test suite uses the configured Flask database).

## API Overview
All request and response bodies are JSON. Unless otherwise noted, endpoints that accept a body require the header `Content-Type: application/json`. Numeric identifiers (`customer_id`, `product_id`, `item_id`, etc.) must be sent as integers.

### Shopcart Statuses
Valid persisted values are `active`, `abandoned`, `locked`, and `expired`. The UI surfaces these as `OPEN`, `ABANDONED`, `PURCHASED`, and `MERGED` respectively, and the list endpoint accepts either flavor (e.g., `status=OPEN` or `status=active`).

### Service Metadata
| Method | Path | Description | Notes |
| ------ | ---- | ----------- | ----- |
| GET | `/` | Returns service name, version, description, and available paths | No authentication required |
| GET | `/health` | Lightweight health probe | Useful for container orchestrators |

### Shopcart Collection
| Method | Path | Description | Required Input |
| ------ | ---- | ----------- | -------------- |
| POST | `/shopcarts` | Create a new shopcart | Body: `{ "customer_id": 1, "status": "active", "items": [] }`<br>`customer_id` (int) is required and must be unique. Optional fields: `status` (from the valid status list or its friendly alias), `total_items`, `items` (see schema below). |
| GET | `/shopcarts` | List shopcarts with optional filters | Query parameters listed below. |

Supported query parameters:
- `status`: accepts `active`, `abandoned`, `locked`, `expired` as well as their friendly aliases `OPEN`, `ABANDONED`, `PURCHASED`, `MERGED` (case-insensitive).
- `customer_id`: integer equality match.
- `created_after` / `created_before`: ISO8601 timestamps (e.g. `2024-01-02T00:00:00+00:00`). Missing timezones default to UTC.
- `min_total` / `max_total`: decimal totals computed as `sum(quantity * price)`. Provide both to filter within a range; the upper bound must be ≥ the lower bound. Legacy parameters `total_price_gt` / `total_price_lt` remain supported for backwards compatibility.

Filtering rules:
- Filters can be combined; all constraints must match for a cart to be returned.
- Invalid values (bad timestamps, non-integer IDs, empty totals, contradictory ranges) produce `400 Bad Request`.

### Shopcart Detail
| Method | Path | Description | Notes |
| ------ | ---- | ----------- | ----- |
| GET | `/shopcarts/<customer_id>` | Retrieve a customer-facing view with computed totals | Returns camelCase keys, totals, and item list. |
| DELETE | `/shopcarts/<customer_id>` | Delete a shopcart by customer id | No body. |
| PUT / PATCH | `/shopcarts/<customer_id>` | Update cart status and optionally replace items | Body supports `status` and/or `items`; supplying `items` overwrites the collection. |
| PUT / PATCH | `/shopcarts/<customer_id>/checkout` | Mark the cart `abandoned` and refresh `last_modified` | No body. |
| PATCH | `/shopcarts/<customer_id>/cancel` | Ensure the cart is in the `abandoned` state | No body. |
| PATCH | `/shopcarts/<customer_id>/lock` | Transition the cart to `locked` | No body. |
| PATCH | `/shopcarts/<customer_id>/expire` | Transition the cart to `expired` | No body. |
| PATCH | `/shopcarts/<customer_id>/reactivate` | Transition the cart back to `active` | No body. |
| GET | `/shopcarts/<customer_id>/totals` | Return aggregated counts and monetary totals | Always recomputes totals server-side. |

### Shopcart Items
| Method | Path | Description | Notes |
| ------ | ---- | ----------- | ----- |
| POST | `/shopcarts/<customer_id>/items` | Add a new item or increment an existing product | `product_id`, `quantity` (>0), and `price` required. Existing quantities are incremented. |
| GET | `/shopcarts/<customer_id>/items` | List items in the cart with optional filters | See filter list below. |
| GET | `/shopcarts/<customer_id>/items/<product_id>` | Retrieve a single item by product id | Returns the raw item serialization. |
| DELETE | `/shopcarts/<customer_id>/items/<product_id>` | Remove an item from the cart | No body. |
| PUT / PATCH | `/shopcarts/<customer_id>/items/<product_id>` | Update an item by `product_id` | Supports `quantity` (0–99), `price`, `description`. Setting `quantity` to 0 deletes the item. Abandoned carts reject updates with `409 Conflict`. |

Item list filters (`GET /shopcarts/<customer_id>/items`):
- `description`: case-insensitive substring match.
- `product_id`: integer equality.
- `quantity`: integer equality.
- `min_price` / `max_price`: decimal range filters (`min_price` ≤ `max_price`).

### Item Schema
The item objects appearing in `POST /shopcarts`, `PUT/PATCH /shopcarts/<customer_id>`, and the item-specific endpoints use the following fields:
- `product_id` (int, required)
- `quantity` (int, required for create)
- `price` (decimal value, required for create)
- `description` (string, optional)

### Example Workflow
```bash
# Create a new shopcart for customer 1
curl -X POST http://127.0.0.1:5000/shopcarts \
  -H "Content-Type: application/json" \
  -d '{"customer_id": 1}'

# Add an item
curl -X POST http://127.0.0.1:5000/shopcarts/1/items \
  -H "Content-Type: application/json" \
  -d '{"product_id": 1001, "quantity": 2, "price": 19.99, "description": "T-shirt"}'

# View the cart as the customer
curl http://127.0.0.1:5000/shopcarts/1

# Checkout
curl -X PATCH http://127.0.0.1:5000/shopcarts/1/checkout

# Lock the cart for downstream processing
curl -X PATCH http://127.0.0.1:5000/shopcarts/1/lock
```

## Additional Commands
- Generate a random secret key: `make secret`
- Build and run the production image: `make build` then `docker run`
- Kubernetes helpers (`make cluster`, `make deploy`) are available for local cluster experimentation.

## Docker Registry Workflow

### Building and Pushing Images

The Makefile supports building and pushing images to Docker registries (DockerHub, GHCR, etc.):

```bash
# Set your registry credentials (replace with your values)
export REGISTRY=docker.io
export ORG=your-username
export IMAGE_NAME=shopcarts
export IMAGE_TAG=1.0

# Login to your registry
docker login $(REGISTRY)

# Build the image
make build

# Push to registry
make push

# Deploy to Kubernetes (uses local cluster)
make deploy

# Get the service URL
make url

# Clean up when done
make undeploy
```

### Environment Variables

You can override the default image configuration:

- `REGISTRY`: Container registry (default: `docker.io`)
- `ORG`: Organization/username (default: `your-username`)
- `IMAGE_NAME`: Image name (default: `shopcarts`)
- `IMAGE_TAG`: Image tag (default: `1.0`)

Example for GitHub Container Registry:
```bash
export REGISTRY=ghcr.io
export ORG=your-github-username
make build
make push
```

With these instructions you can install, run, exercise each API endpoint, and test the service locally.

## License

Copyright (c) 2016, 2025 [John Rofrano](https://www.linkedin.com/in/JohnRofrano/). All rights reserved.

Licensed under the Apache License. See [LICENSE](LICENSE)

This repository is part of the New York University (NYU) masters class: **CSCI-GA.2820-001 DevOps and Agile Methodologies** created and taught by [John Rofrano](https://cs.nyu.edu/~rofrano/), Adjunct Instructor, NYU Courant Institute, Graduate Division, Computer Science, and NYU Stern School of Business.
