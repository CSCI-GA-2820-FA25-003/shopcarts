"""Step definitions for shopcart UI BDD scenarios."""

from __future__ import annotations

from behave import given, when, then
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from features.environment import delete_cart_via_ui

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
    status_value = "active" if status.upper() == "OPEN" else status.lower()
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
