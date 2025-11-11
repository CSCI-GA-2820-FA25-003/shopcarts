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
