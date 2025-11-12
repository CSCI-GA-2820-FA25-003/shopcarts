"""Step definitions for shopcart UI and API BDD scenarios."""

from __future__ import annotations

from decimal import Decimal
from urllib.parse import urljoin

import requests
from behave import given, when, then
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from features.environment import (
    create_cart_via_api,
    delete_cart_via_api,
    delete_cart_via_ui,
)

WAIT_TIMEOUT = 10

STATUS_ALIAS_MAP = {
    "open": "active",
    "active": "active",
    "abandoned": "abandoned",
    "purchased": "locked",
    "locked": "locked",
    "merged": "expired",
    "expired": "expired",
}


def canonical_status(label: str) -> str:
    normalized = (label or "").strip().lower()
    return STATUS_ALIAS_MAP.get(normalized, normalized or "active")


def status_display_label(label: str) -> str:
    canonical = canonical_status(label)
    return canonical.upper()


def add_item_via_api(context, customer_id: int, price: Decimal, product_id: int) -> None:
    payload = {
        "product_id": product_id,
        "quantity": 1,
        "price": float(price),
    }
    response = requests.post(
        api_url(context, f"shopcarts/{customer_id}/items"), json=payload, timeout=10
    )
    response.raise_for_status()


def api_url(context, path: str) -> str:
    return urljoin(context.base_url + "/", path.lstrip("/"))


def query_form(context):
    return context.browser.find_element(By.ID, "query-form")


def get_table_rows(context):
    """Return parsed table rows, skipping placeholders. Returns [] on stale DOM."""
    try:
        rows = context.browser.find_elements(By.CSS_SELECTOR, "#shopcart-table tbody tr")
    except StaleElementReferenceException:
        return []
    parsed = []
    for row in rows:
        try:
            cells = row.find_elements(By.TAG_NAME, "td")
        except StaleElementReferenceException:
            return []
        if len(cells) < 6:
            continue
        try:
            customer_text = cells[0].text.strip()
            status_text = cells[2].text.strip()
            total_text = cells[4].text.strip()
        except StaleElementReferenceException:
            return []
        if "No data yet" in customer_text or "No results" in customer_text:
            continue
        parsed.append(
            {
                "customer_id": int(customer_text),
                "status_label": status_text,
                "total_price": total_text,
            }
        )
    return parsed


def wait_for_table_rows(context):
    WebDriverWait(context.browser, WAIT_TIMEOUT).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "#shopcart-table tbody tr"))
    )
    return get_table_rows(context)


def wait_for_alert_text(context, expected_text: str):
    WebDriverWait(context.browser, WAIT_TIMEOUT).until(
        EC.text_to_be_present_in_element((By.CSS_SELECTOR, "#alerts .alert"), expected_text)
    )


def get_table_html(context):
    table = context.browser.find_element(By.ID, "shopcart-table")
    return table.get_attribute("outerHTML")


def set_input_value(element, value: str):
    element.clear()
    element.send_keys(value)


def submit_query_form(context):
    query_form(context).find_element(By.CSS_SELECTOR, "button[type='submit']").click()


def capture_latest_rows(context):
    rows = get_table_rows(context)
    context.latest_rows = rows
    return rows


@given("the shopcart admin UI is available")
def step_impl_ui_available(context):
    context.browser.get(context.ui_url)


@given("I am a logged-in customer on the Shopcart page")
def step_impl_visit_shopcart_page(context):
    context.browser.get(context.ui_url)


@given("I am on the Create Shopcart form")
def step_impl_on_create_form(context):
    context.browser.get(context.ui_url)
    context.table_snapshot = get_table_html(context)


@given("the service is running")
def step_impl_service_running(context):
    response = requests.get(api_url(context, "health"), timeout=10)
    response.raise_for_status()


@given("shopcarts exist for customer_id={customer_id:d}")
def step_impl_shopcarts_for_customer(context, customer_id):
    create_cart_via_api(context, customer_id, status="active")
    context.created_customer_ids.add(customer_id)


@given('shopcarts exist with status="{status_label}"')
def step_impl_shopcarts_with_status(context, status_label):
    for suffix in (1, 2):
        cid = 100 * suffix + len(context.created_customer_ids) + 1
        create_cart_via_api(
            context,
            cid,
            status=canonical_status(status_label),
        )
        context.created_customer_ids.add(cid)


@given("shopcarts exist with various total prices")
def step_impl_shopcarts_various_totals(context):
    specs = [
        (201, Decimal("25.00"), "active"),
        (202, Decimal("120.00"), "abandoned"),
        (203, Decimal("250.00"), "active"),
    ]
    for cid, total_value, status_label in specs:
        create_cart_via_api(context, cid, status=status_label)
        if total_value > 0:
            add_item_via_api(context, cid, total_value, product_id=cid * 10)
        context.created_customer_ids.add(cid)


@given("the following shopcarts exist:")
def step_impl_shopcarts_from_table(context):
    expected_total = len(context.table.rows)
    for row in context.table:
        customer_id = int(row["customer_id"])
        status_label = row.get("status", "OPEN")
        total_value = Decimal(str(row.get("total", "0") or "0"))
        create_cart_via_api(
            context,
            customer_id,
            status=canonical_status(status_label),
        )
        if total_value > 0:
            add_item_via_api(context, customer_id, total_value, product_id=customer_id * 10)
        context.created_customer_ids.add(customer_id)
    context.expected_shopcart_count = expected_total


@given("a shopcart exists with customer id {customer_id:d}")
def step_impl_cart_exists(context, customer_id):
    create_cart_via_api(context, customer_id, name=f"BDD Cart {customer_id}")
    context.created_customer_ids.add(customer_id)


@given("the shopcart with customer id {customer_id:d} is removed outside the UI")
def step_impl_cart_removed_elsewhere(context, customer_id):
    delete_cart_via_api(context, customer_id)


@when('I send a GET request to "{path}"')
def step_impl_send_get_request(context, path):
    context.api_response = requests.get(api_url(context, path), timeout=10)


@when(
    'I submit a valid "Create Cart" form with customer_id={customer_id:d} and name="{cart_name}"'
)
def step_impl_submit_valid_form(context, customer_id, cart_name):
    context.browser.get(context.ui_url)
    customer_input = context.browser.find_element(By.ID, "create-customer-id")
    name_input = context.browser.find_element(By.ID, "create-name")
    submit_button = context.browser.find_element(By.ID, "create-submit")

    customer_input.clear()
    customer_input.send_keys(str(customer_id))
    name_input.clear()
    name_input.send_keys(cart_name)
    submit_button.click()

    context.cleanup_customer_id = customer_id


@when("I submit the form without entering a customer ID")
def step_impl_submit_invalid_form(context):
    context.browser.get(context.ui_url)
    customer_input = context.browser.find_element(By.ID, "create-customer-id")
    customer_input.clear()
    name_input = context.browser.find_element(By.ID, "create-name")
    name_input.clear()
    name_input.send_keys("Unnamed cart")
    submit_button = context.browser.find_element(By.ID, "create-submit")
    submit_button.click()


@then('I should receive a confirmation message "{message}"')
def step_impl_receive_confirmation(context, message):
    wait_for_alert_text(context, message)


@then('I should see the new cart listed with status "{status_text}"')
def step_impl_cart_listed(context, status_text):
    table_locator = (By.ID, "shopcart-table")
    WebDriverWait(context.browser, WAIT_TIMEOUT).until(
        EC.text_to_be_present_in_element(table_locator, status_text)
    )
    assert status_text in context.browser.find_element(*table_locator).text
    if context.cleanup_customer_id:
        delete_cart_via_ui(context, context.cleanup_customer_id)
        context.cleanup_customer_id = None


@then("I should receive a {status_code:d} {status_text} response")
def step_impl_http_response(context, status_code, status_text):
    assert hasattr(context, "api_response"), "API response is missing"
    assert (
        context.api_response.status_code == status_code
    ), f"Expected {status_code} got {context.api_response.status_code}"


@then("all returned shopcarts should have customer_id={customer_id:d}")
def step_impl_api_filter_customer(context, customer_id):
    data = context.api_response.json()
    assert data, "Expected at least one shopcart"
    assert all(entry["customer_id"] == customer_id for entry in data)


@then('all returned shopcarts should have status="{status_label}"')
def step_impl_api_filter_status(context, status_label):
    expected = canonical_status(status_label)
    data = context.api_response.json()
    assert data, "Expected at least one shopcart"
    assert all(entry["status"] == expected for entry in data)


@then(
    "all returned shopcarts should have total_price between {min_total:f} and {max_total:f}"
)
def step_impl_api_filter_totals(context, min_total, max_total):
    lower = Decimal(str(min_total))
    upper = Decimal(str(max_total))
    data = context.api_response.json()
    assert data, "Expected at least one shopcart"
    for entry in data:
        total_value = entry.get("total_price") or entry.get("totalPrice")
        if total_value is None or Decimal(str(total_value)) == 0:
            items = entry.get("items", [])
            total = sum(
                Decimal(str(item.get("price", 0))) * Decimal(str(item.get("quantity", 0)))
                for item in items
            )
        else:
            total = Decimal(str(total_value))
        assert lower <= total <= upper, f"{total} not within {lower}-{upper}"


@then('I should see an error message "{message}"')
def step_impl_error_message(context, message):
    wait_for_alert_text(context, message)


@then('I should see a warning message "{message}"')
def step_impl_warning_message(context, message):
    wait_for_alert_text(context, message)


@then("the cart should not be created")
def step_impl_not_created(context):
    latest_html = get_table_html(context)
    if context.table_snapshot is None:
        # If no snapshot is available, ensure the placeholder text is still present.
        assert "No data yet" in latest_html or "No results match" in latest_html
    else:
        assert latest_html == context.table_snapshot


@when("I filter shopcarts by customer id {customer_id:d}")
def step_impl_filter_by_customer(context, customer_id):
    form = query_form(context)
    set_input_value(form.find_element(By.NAME, "customerId"), str(customer_id))
    submit_query_form(context)
    wait_for_alert_text(context, "Query completed")
    capture_latest_rows(context)


@then("the UI should only list shopcarts with customer id {customer_id:d}")
def step_impl_ui_customer_results(context, customer_id):
    rows = getattr(context, "latest_rows", None) or get_table_rows(context)
    assert rows, "No rows returned in UI"
    assert all(row["customer_id"] == customer_id for row in rows)


@when('I filter shopcarts by status "{status_label}" in the UI')
def step_impl_filter_by_status_ui(context, status_label):
    form = query_form(context)
    dropdown = Select(form.find_element(By.NAME, "status"))
    dropdown.select_by_value(canonical_status(status_label))
    submit_query_form(context)
    wait_for_alert_text(context, "Query completed")
    capture_latest_rows(context)


@then('the UI should only list shopcarts with status "{status_label}"')
def step_impl_ui_status_results(context, status_label):
    expected = status_display_label(status_label)
    rows = getattr(context, "latest_rows", None) or get_table_rows(context)
    assert rows, "No rows returned in UI"
    assert all(row["status_label"] == expected for row in rows)


@when("I submit an invalid price range in the UI")
def step_impl_invalid_price_range_ui(context):
    form = query_form(context)
    set_input_value(form.find_element(By.NAME, "minTotal"), "500")
    set_input_value(form.find_element(By.NAME, "maxTotal"), "100")
    submit_query_form(context)


@when("I clear the UI filters")
def step_impl_clear_filters(context):
    clear_button = context.browser.find_element(By.ID, "clear-filters")
    clear_button.click()
    wait_for_alert_text(context, "Filters cleared. Showing all shopcarts.")
    capture_latest_rows(context)


@then("the filter form should be reset")
def step_impl_form_reset(context):
    form = query_form(context)
    assert form.find_element(By.NAME, "customerId").get_attribute("value") == ""
    assert form.find_element(By.NAME, "minTotal").get_attribute("value") == ""
    assert form.find_element(By.NAME, "maxTotal").get_attribute("value") == ""
    select = Select(form.find_element(By.NAME, "status"))
    assert select.first_selected_option.get_attribute("value") == ""


@then("the UI should show at least {count:d} shopcarts")
def step_impl_ui_minimum_rows(context, count):
    rows = getattr(context, "latest_rows", None) or get_table_rows(context)
    assert len(rows) >= count, f"Expected at least {count} rows, saw {len(rows)}"


@given("I load the shopcart details for customer {customer_id:d}")
@when("I load the shopcart details for customer {customer_id:d}")
def step_impl_load_details(context, customer_id):
    read_form = context.browser.find_element(By.ID, "read-form")
    customer_input = read_form.find_element(By.NAME, "customerId")
    customer_input.clear()
    customer_input.send_keys(str(customer_id))
    read_form.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    WebDriverWait(context.browser, WAIT_TIMEOUT).until(
        EC.text_to_be_present_in_element(
            (By.ID, "result-card"), f"Customer {customer_id}"
        )
    )
    context.active_customer_id = customer_id


@when("I delete the shopcart from the details panel")
def step_impl_delete_from_card(context):
    customer_id = getattr(context, "active_customer_id", None)
    assert (
        customer_id is not None
    ), "A shopcart must be loaded before invoking the delete button."
    delete_button = context.browser.find_element(By.CSS_SELECTOR, "[data-delete-cart]")
    delete_button.click()
    alert = WebDriverWait(context.browser, WAIT_TIMEOUT).until(EC.alert_is_present())
    alert.accept()


@then("the cart details panel should be cleared")
def step_impl_card_cleared(context):
    def card_is_hidden(driver):
        element = driver.find_element(By.ID, "result-card")
        return element.get_attribute("hidden") is not None

    WebDriverWait(context.browser, WAIT_TIMEOUT).until(card_is_hidden)
    result_card = context.browser.find_element(By.ID, "result-card")
    assert result_card.get_attribute("hidden") is not None
    assert not result_card.text.strip()

@given('there is an existing shopcart with customer_id={customer_id:d} and status "{status}"')
def step_impl_existing_shopcart(context, customer_id, status):
    """Create a shopcart via the UI for testing update operations."""
    context.browser.get(context.ui_url)
    # First, try to delete if it exists to ensure clean state
    try:
        delete_cart_via_ui(context, customer_id)
        WebDriverWait(context.browser, 3).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#alerts .alert"))
        )
    except Exception:
        pass  # Cart might not exist, which is fine

    # Create the shopcart with the specified status
    customer_input = context.browser.find_element(By.ID, "create-customer-id")
    name_input = context.browser.find_element(By.ID, "create-name")
    status_select = context.browser.find_element(By.CSS_SELECTOR, "#create-form select[name='status']")
    submit_button = context.browser.find_element(By.ID, "create-submit")

    customer_input.clear()
    customer_input.send_keys(str(customer_id))
    name_input.clear()
    name_input.send_keys(f"Test Cart {customer_id}")

    # Set the status - map "OPEN" to "active"
    status_value = canonical_status(status)
    select = Select(status_select)
    select.select_by_value(status_value)

    submit_button.click()

    # Wait for success message
    WebDriverWait(context.browser, WAIT_TIMEOUT).until(
        EC.text_to_be_present_in_element((By.CSS_SELECTOR, "#alerts .alert"), "created")
    )

    # Store for cleanup
    if not hasattr(context, "cleanup_customer_ids"):
        context.cleanup_customer_ids = []
    context.cleanup_customer_ids.append(customer_id)


@given('there is no shopcart with customer_id={customer_id:d}')
def step_impl_no_shopcart(context, customer_id):
    """Ensure no shopcart exists for the given customer_id."""
    context.browser.get(context.ui_url)
    # Try to delete if it exists
    try:
        delete_cart_via_ui(context, customer_id)
        WebDriverWait(context.browser, 3).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#alerts .alert"))
        )
    except Exception:
        pass  # Cart doesn't exist, which is what we want


@when('I send a PUT request to update shopcart for customer {customer_id:d} with status "{status}"')
def step_impl_update_shopcart(context, customer_id, status):
    """Update a shopcart via the UI update form."""
    context.browser.get(context.ui_url)
    update_form = context.browser.find_element(By.ID, "update-form")
    customer_input = update_form.find_element(By.CSS_SELECTOR, "input[name='customerId']")
    status_select = update_form.find_element(By.CSS_SELECTOR, "select[name='status']")
    submit_button = update_form.find_element(By.CSS_SELECTOR, "button[type='submit']")

    customer_input.clear()
    customer_input.send_keys(str(customer_id))

    # Map aliases (e.g., "OPEN") into canonical values expected by the dropdown.
    select = Select(status_select)
    select.select_by_value(canonical_status(status))

    submit_button.click()

    # Store the expected status for verification
    context.expected_status = status
    context.expected_customer_id = customer_id


@then("I should receive a 200 OK response in the UI")
def step_impl_200_ok(context):
    """Verify a successful update (200 OK equivalent in UI)."""
    # In UI testing, we check for success message instead of HTTP status
    WebDriverWait(context.browser, WAIT_TIMEOUT).until(
        EC.any_of(
            EC.text_to_be_present_in_element((By.CSS_SELECTOR, "#alerts .alert"), "updated"),
            EC.text_to_be_present_in_element((By.CSS_SELECTOR, "#alerts .alert"), "success")
        )
    )
    alert_text = context.browser.find_element(By.CSS_SELECTOR, "#alerts .alert").text.lower()
    assert "updated" in alert_text or "success" in alert_text, f"Expected success message, got: {alert_text}"


@then("I should receive a 404 Not Found response in the UI")
def step_impl_404_not_found(context):
    """Verify a 404 Not Found response (cart doesn't exist)."""
    # In UI testing, we check for error message indicating cart not found
    WebDriverWait(context.browser, WAIT_TIMEOUT).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "#alerts .alert"))
    )
    alert_text = context.browser.find_element(By.CSS_SELECTOR, "#alerts .alert").text.lower()
    assert "not found" in alert_text or "404" in alert_text, f"Expected 'not found' error, got: {alert_text}"


@then('the response body should include the updated status "{status}"')
def step_impl_response_has_status(context, status):
    """Verify the response includes the updated status."""
    # Check the result card for the updated status
    WebDriverWait(context.browser, WAIT_TIMEOUT).until(
        EC.presence_of_element_located((By.ID, "result-card"))
    )
    result_card = context.browser.find_element(By.ID, "result-card")
    assert not result_card.get_attribute("hidden"), "Result card should be visible"

    expected_display = status_display_label(status)
    result_text = result_card.text
    assert expected_display in result_text, \
        f"Expected status '{expected_display}' in result card, got: {result_text}"


@then("the shopcart data should match the updated status")
def step_impl_data_matches_status(context):
    """Verify the shopcart data in the UI matches the updated status."""
    # Check both the result card and the table
    if hasattr(context, "expected_status") and hasattr(context, "expected_customer_id"):
        # Verify in result card
        result_card = context.browser.find_element(By.ID, "result-card")
        if not result_card.get_attribute("hidden"):
            result_text = result_card.text
            expected_display = status_display_label(context.expected_status)
            assert expected_display in result_text, \
                f"Status '{expected_display}' not found in result card"

        # Verify in table
        table = context.browser.find_element(By.ID, "shopcart-table")
        table_text = table.text
        assert str(context.expected_customer_id) in table_text, \
            f"Customer {context.expected_customer_id} not found in table"
        expected_display = status_display_label(context.expected_status)
        assert expected_display in table_text, \
            f"Status '{expected_display}' not found in table output"
