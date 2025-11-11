"""Step definitions for shopcart UI BDD scenarios."""

from __future__ import annotations

from behave import given, when, then
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from features.environment import (
    create_cart_via_api,
    delete_cart_via_api,
    delete_cart_via_ui,
)

WAIT_TIMEOUT = 10


def wait_for_alert_text(context, expected_text: str):
    WebDriverWait(context.browser, WAIT_TIMEOUT).until(
        EC.text_to_be_present_in_element((By.CSS_SELECTOR, "#alerts .alert"), expected_text)
    )


def get_table_html(context):
    table = context.browser.find_element(By.ID, "shopcart-table")
    return table.get_attribute("outerHTML")


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


@given("a shopcart exists with customer id {customer_id:d}")
def step_impl_cart_exists(context, customer_id):
    create_cart_via_api(context, customer_id, name=f"BDD Cart {customer_id}")
    context.created_customer_ids.add(customer_id)


@given("the shopcart with customer id {customer_id:d} is removed outside the UI")
def step_impl_cart_removed_elsewhere(context, customer_id):
    delete_cart_via_api(context, customer_id)


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


@then('I should see an error message "{message}"')
def step_impl_error_message(context, message):
    wait_for_alert_text(context, message)


@then("the cart should not be created")
def step_impl_not_created(context):
    latest_html = get_table_html(context)
    if context.table_snapshot is None:
        # If no snapshot is available, ensure the placeholder text is still present.
        assert "No data yet" in latest_html or "No results match" in latest_html
    else:
        assert latest_html == context.table_snapshot


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

    # Set the status - map "OPEN" to "active", "CLOSED" to "abandoned"
    if status.upper() == "OPEN":
        status_value = "active"
    elif status.upper() == "CLOSED":
        status_value = "abandoned"
    else:
        status_value = status.lower()
    from selenium.webdriver.support.ui import Select
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

    # Map status values - "OPEN" to "active", "LOCKED" to "locked", etc.
    status_value = "active" if status.upper() == "OPEN" else status.lower()
    from selenium.webdriver.support.ui import Select
    select = Select(status_select)
    select.select_by_value(status_value)

    submit_button.click()

    # Store the expected status for verification
    context.expected_status = status
    context.expected_customer_id = customer_id


@then("I should receive a 200 OK response")
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


@then("I should receive a 404 Not Found response")
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

    # Map status for display - "LOCKED" might show as "LOCKED" or "locked"
    status_display = status.upper() if status.upper() == "LOCKED" else status
    result_text = result_card.text
    assert status_display in result_text or status.lower() in result_text.lower(), \
        f"Expected status '{status}' in result card, got: {result_text}"


@then("the shopcart data should match the updated status")
def step_impl_data_matches_status(context):
    """Verify the shopcart data in the UI matches the updated status."""
    # Check both the result card and the table
    if hasattr(context, "expected_status") and hasattr(context, "expected_customer_id"):
        # Verify in result card
        result_card = context.browser.find_element(By.ID, "result-card")
        if not result_card.get_attribute("hidden"):
            result_text = result_card.text
            status_display = context.expected_status.upper() if context.expected_status.upper() == "LOCKED" else context.expected_status
            assert status_display in result_text or context.expected_status.lower() in result_text.lower(), \
                f"Status '{context.expected_status}' not found in result card"

        # Verify in table
        table = context.browser.find_element(By.ID, "shopcart-table")
        table_text = table.text
        assert str(context.expected_customer_id) in table_text, \
            f"Customer {context.expected_customer_id} not found in table"


@when('I open the "My Shopcarts" page')
def step_impl_open_my_shopcarts(context):
    """Navigate to the My Shopcarts page and load all shopcarts."""
    context.browser.get(context.ui_url)
    # Wait for the page to load and trigger the list all action
    list_all_btn = WebDriverWait(context.browser, WAIT_TIMEOUT).until(
        EC.element_to_be_clickable((By.ID, "list-all"))
    )
    list_all_btn.click()
    # Wait for the table to update
    WebDriverWait(context.browser, WAIT_TIMEOUT).until(
        EC.presence_of_element_located((By.ID, "shopcart-table"))
    )


@then("I should see a list of all my shopcarts")
def step_impl_see_list(context):
    """Verify that the shopcart list is displayed."""
    table = context.browser.find_element(By.ID, "shopcart-table")
    # Check that the table exists and is not showing empty state
    table_text = table.text
    assert "No shopcarts found" not in table_text or len(table.find_elements(By.TAG_NAME, "tr")) > 1, \
        "Shopcart list should be displayed"


@then("each shopcart should show its ID, name, and status")
def step_impl_shopcart_shows_details(context):
    """Verify that each shopcart in the list shows ID, name, and status."""
    table = context.browser.find_element(By.ID, "shopcart-table")
    rows = table.find_elements(By.CSS_SELECTOR, "tbody tr")
    # Filter out empty state row
    data_rows = [row for row in rows if "No shopcarts found" not in row.text]
    
    if not data_rows:
        # If no data rows, that's okay if we're testing empty state
        return
    
    for row in data_rows:
        cells = row.find_elements(By.TAG_NAME, "td")
        assert len(cells) >= 3, "Each shopcart row should have at least Cart ID, Name, and Status columns"
        # First cell should be Cart ID (customer_id)
        cart_id = cells[0].text.strip()
        assert cart_id and cart_id.isdigit(), f"Cart ID should be a number, got: {cart_id}"
        # Second cell should be Name
        name = cells[1].text.strip()
        # Name can be empty, so we just check it exists
        # Third cell should be Status
        status_cell = cells[2]
        status_badge = status_cell.find_elements(By.CSS_SELECTOR, ".badge")
        assert len(status_badge) > 0, "Status should be displayed with a badge"


@when('I filter by "{status}"')
def step_impl_filter_by_status(context, status):
    """Apply a status filter to the shopcart list."""
    # Ensure we're on the page first
    if not context.browser.current_url.startswith(context.base_url):
        context.browser.get(context.ui_url)
    # Wait for the query form to be available
    query_form = WebDriverWait(context.browser, WAIT_TIMEOUT).until(
        EC.presence_of_element_located((By.ID, "query-form"))
    )
    status_select = query_form.find_element(By.ID, "status-filter")
    from selenium.webdriver.support.ui import Select
    select = Select(status_select)
    select.select_by_value(status)
    # Submit the form
    query_form.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    # Wait for the table to update or error message
    WebDriverWait(context.browser, WAIT_TIMEOUT).until(
        EC.any_of(
            EC.presence_of_element_located((By.ID, "shopcart-table")),
            EC.presence_of_element_located((By.CSS_SELECTOR, "#alerts .alert"))
        )
    )


@then('I should see only the shopcarts with status "{status}"')
def step_impl_see_filtered_status(context, status):
    """Verify that only shopcarts with the specified status are displayed."""
    table = context.browser.find_element(By.ID, "shopcart-table")
    rows = table.find_elements(By.CSS_SELECTOR, "tbody tr")
    data_rows = [row for row in rows if "No shopcarts found" not in row.text]
    
    if not data_rows:
        # If no rows, that's okay if the filter resulted in no matches
        return
    
    # Map status for comparison
    expected_display = "OPEN" if status.upper() == "OPEN" else status.upper()
    
    for row in data_rows:
        cells = row.find_elements(By.TAG_NAME, "td")
        if len(cells) >= 3:
            status_cell = cells[2]
            status_text = status_cell.text.strip()
            # Status should match the expected display
            assert expected_display in status_text.upper(), \
                f"Expected status '{expected_display}' but found '{status_text}' in row"


@when("I try to apply a filter that doesn't exist")
def step_impl_invalid_filter(context):
    """Try to apply an invalid filter option."""
    # We'll simulate this by trying to set an invalid status value via JavaScript
    # or by checking the UI behavior when an invalid option is selected
    # For now, we'll check that the UI handles invalid status gracefully
    query_form = context.browser.find_element(By.ID, "query-form")
    status_select = query_form.find_element(By.ID, "status-filter")
    # Try to select a value that doesn't exist in the dropdown
    # Since the dropdown only has valid options, we'll trigger an API error
    # by sending an invalid status via the form
    from selenium.webdriver.support.ui import Select
    select = Select(status_select)
    # Select a valid option first, then we'll modify it to be invalid
    # Actually, we can't easily set an invalid option through the UI
    # So we'll test by making a direct API call with invalid status
    # But for UI testing, we should test what happens when the API returns an error
    # Let's just submit the form with an invalid status by manipulating the select
    context.browser.execute_script(
        "arguments[0].value = 'INVALID_STATUS';",
        status_select
    )
    query_form.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    # Wait for error message
    WebDriverWait(context.browser, WAIT_TIMEOUT).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "#alerts .alert"))
    )


@then('I should see a message "No shopcarts found"')
def step_impl_see_empty_message(context):
    """Verify that the empty state message is displayed."""
    table = context.browser.find_element(By.ID, "shopcart-table")
    table_text = table.text
    assert "No shopcarts found" in table_text, \
        f"Expected 'No shopcarts found' message, but got: {table_text}"