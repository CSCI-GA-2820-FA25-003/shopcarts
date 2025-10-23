# Shopcart REST API Service

This project implements a Flask-based REST API for managing customer shopcarts and their items. It is the reference implementation used in the NYU DevOps course and extends the original project template with a working service, database models, and automated tests.

## Prerequisites
- Python 3.11
- `pipenv` (or another preferred environment manager)
- PostgreSQL (local or containerised) reachable by the Flask app

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

## Running the Service
Choose one of the following:
- `pipenv run flask run` (default Flask dev server on `http://127.0.0.1:5000`)
- `make run` (uses Honcho to launch Gunicorn via the `Procfile`)

When the service starts you should see log output confirming the database tables were created and the server is accepting requests.

## Running Tests and Quality Checks
- Unit tests with coverage: `make test` (or `pytest --pspec --cov=service --disable-warnings`)
- Linting: `make lint`

All tests require the service dependencies to be installed and a database connection available (the test suite uses the configured Flask database).

## API Overview
All request and response bodies are JSON. Unless otherwise noted, endpoints that accept a body require the header `Content-Type: application/json`. Numeric identifiers (`customer_id`, `product_id`, `item_id`, etc.) must be sent as integers.

### Service Metadata
| Method | Path | Description | Notes |
| ------ | ---- | ----------- | ----- |
| GET | `/` | Returns service name, version, description, and available paths | No authentication required |

### Shopcart Collection
| Method | Path | Description | Required Input |
| ------ | ---- | ----------- | -------------- |
| POST | `/shopcarts` | Create a new shopcart | Body: `{ "customer_id": 1, "status": "active", "total_items": 0, "items": [] }`<br>`customer_id` (int) is required and must be unique. Optional fields: `status` (default `active`), `total_items`, `items` (see item schema below). |
| GET | `/shopcarts` | List all shopcarts | No body. Optional query params: `status` (`active`, `abandoned`), `customer_id` (integer), `created_after`, `created_before` (ISO8601 timestamps), `total_price_gt`, and `total_price_lt` (decimal). |

Filtering rules:
- Filters can be combined; only carts matching every provided parameter are returned.
- `created_after` / `created_before` accept ISO8601 timestamps (e.g. `2024-01-02T00:00:00+00:00`); omit the timezone to assume UTC.
- `total_price_gt` / `total_price_lt` accept decimal values and filter on the computed cart total (sum of `price * quantity` for each item). Provide both to search within a range.
- Omitting a filter leaves that dimension unrestricted.
- Supplying a status other than `active` or `abandoned`, or a non-integer `customer_id`, produces a `400 Bad Request`.
- Non-ISO8601 timestamps for `created_after` / `created_before`, invalid decimal totals, or contradictory ranges produce a `400 Bad Request`.

### Shopcart Detail
| Method | Path | Description | Required Input |
| ------ | ---- | ----------- | -------------- |
| GET | `/shopcarts/<customer_id>` | Retrieve the shopcart belonging to a specific customer | Header: `X-Customer-ID` with the same integer value as the path parameter. |
| GET | `/admin/shopcarts/<customer_id>` | Admin view of any customer shopcart | Header: `X-Role: admin`. |
| DELETE | `/shopcarts/<customer_id>` | Delete a shopcart by its customer id | No body |
| PUT / PATCH | `/shopcarts/<customer_id>` | Update shopcart status and optionally replace items | Body supports any of:<br>`status` (string),<br>`items` (array of Shopcart Items defined below). If `items` is provided it overwrites the existing collection. |
| PUT / PATCH | `/shopcarts/<customer_id>/checkout` | Close the cart by marking it `abandoned` and refresh `last_modified` | No body |
| PATCH | `/shopcarts/<customer_id>/cancel` | Cancel the cart (sets status to `abandoned`) | No body |
| PATCH | `/shopcarts/<customer_id>/reactivate` | Reactivate a previously abandoned cart (sets status to `active`) | No body |

### Shopcart Items
| Method | Path | Description | Required Input |
| ------ | ---- | ----------- | -------------- |
| POST | `/shopcarts/<customer_id>/items` | Add a new item to the customer's active shopcart | Body: `{ "product_id": 10, "quantity": 2, "price": 19.99, "description": "T-shirt" }`.<br>`quantity` must be a positive integer and `price` is coerced to Decimal with 2 places. |
| GET | `/shopcarts/<customer_id>/items` | List all items in the customer's shopcart | No body |
| GET | `/shopcarts/<customer_id>/items/<item_id>` | Retrieve a single item by id | No additional headers |
| DELETE | `/shopcarts/<customer_id>/items/<item_id>` | Remove an item from the shopcart | No body |
| PUT / PATCH | `/shopcarts/<customer_id>/items/<product_id>` | Update or remove (when quantity is 0) an item by `product_id` | Headers: `X-Customer-ID` must match the owning customer.<br>Body supports `quantity`, `price`, and `description`. Quantity is clamped to 0–99. Setting `quantity` to 0 deletes the item. |

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
curl http://127.0.0.1:5000/shopcarts/1 -H "X-Customer-ID: 1"

# Checkout
curl -X PATCH http://127.0.0.1:5000/shopcarts/1/checkout
```

## Additional Commands
- Generate a random secret key: `make secret`
- Build and run the production image: `make build` then `docker run`
- Kubernetes helpers (`make cluster`, `make deploy`) are available for local cluster experimentation.

With these instructions you can install, run, exercise each API endpoint, and test the service locally.
