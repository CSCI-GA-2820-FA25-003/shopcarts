# Shopcart REST API Service

This project implements a Flask-based REST API for managing customer shopcarts and their items. It is the reference implementation used in the NYU DevOps course and extends the original project template with a working service, database models, and automated tests.

## Prerequisites
- Python 3.11
- `pipenv` (or another preferred environment manager)
- PostgreSQL (local or containerised) reachable by the Flask app

The service automatically creates the database tables on startup.

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
- `pipenv run flask run` (default Flask dev server on `http://127.0.0.1:8080`)
- `make run` or `honcho start` (uses Honcho to launch Gunicorn via the `Procfile`)

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
| GET | `/shopcarts` | List all shopcarts | No body |

### Shopcart Detail
| Method | Path | Description | Required Input |
| ------ | ---- | ----------- | -------------- |
| GET | `/shopcarts/<customer_id>` | Retrieve the shopcart belonging to a specific customer | Header: `X-Customer-ID` with the same integer value as the path parameter. |
| GET | `/admin/shopcarts/<customer_id>` | Admin view of any customer shopcart | Header: `X-Role: admin`. |
| DELETE | `/shopcarts/<shopcart_id>` | Delete a shopcart by its database id | No body, id is the internal shopcart identifier. |
| PUT / PATCH | `/shopcarts/<shopcart_id>` | Update shopcart status and optionally replace items | Body supports any of:<br>`status` (string),<br>`items` (array of Shopcart Items defined below). If `items` is provided it overwrites the existing collection. |
| PUT / PATCH | `/shopcarts/<shopcart_id>/checkout` | Mark the shopcart as `completed` and refresh `last_modified` | No body |

### Shopcart Items
| Method | Path | Description | Required Input |
| ------ | ---- | ----------- | -------------- |
| POST | `/shopcarts/<customer_id>/items` | Add a new item to the customer's active shopcart | Body: `{ "product_id": 10, "quantity": 2, "price": 19.99, "description": "T-shirt" }`.<br>`quantity` must be a positive integer and `price` is coerced to Decimal with 2 places. |
| GET | `/shopcarts/<customer_id>/items` | List all items in the customer's shopcart | No body |
| GET | `/shopcarts/<customer_id>/items/<item_id>` | Retrieve a single item by id | No additional headers |
| DELETE | `/shopcarts/<customer_id>/items/<item_id>` | Remove an item from the shopcart | No body |
| PUT / PATCH | `/shopcarts/<shopcart_id>/items/<product_id>` | Update or remove (when quantity is 0) an item by `product_id` | Headers: `X-Customer-ID` must match the owning customer.<br>Body supports `quantity`, `price`, and `description`. Quantity is clamped to 0–99. Setting `quantity` to 0 deletes the item. |

### Item Schema
The item objects appearing in `POST /shopcarts`, `PUT/PATCH /shopcarts/<shopcart_id>`, and the item-specific endpoints use the following fields:
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
