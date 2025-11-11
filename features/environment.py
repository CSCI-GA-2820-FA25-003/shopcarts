"""Behave environment configuration for Selenium UI tests."""

from __future__ import annotations

import os
import time
from urllib.parse import urljoin

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager


def before_all(context):
    """Initialise the Selenium browser before running any scenarios."""
    base_url = os.getenv("BASE_URL", "http://127.0.0.1:5000")
    context.base_url = base_url.rstrip("/")
    context.ui_url = urljoin(context.base_url + "/", "ui")

    chrome_options = Options()
    chrome_binary = (
        os.getenv("CHROME_BINARY")
        or _first_existing(
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
        )
    )
    if chrome_binary:
        chrome_options.binary_location = chrome_binary

    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1440,900")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    driver_path = (
        os.getenv("CHROMEDRIVER")
        or _first_existing("/usr/bin/chromedriver", "/usr/lib/chromium/chromedriver")
        or ChromeDriverManager().install()
    )
    service = Service(driver_path)
    context.browser = webdriver.Chrome(service=service, options=chrome_options)
    context.browser.implicitly_wait(5)


def before_scenario(context, _scenario):
    context.cleanup_customer_id = None
    context.table_snapshot = None
    context.created_customer_ids = set()


def after_scenario(context, _scenario):
    if context.cleanup_customer_id is not None:
        delete_cart_via_ui(context, context.cleanup_customer_id)
        # Give the UI time to refresh the list before the next scenario.
        time.sleep(1)
        context.cleanup_customer_id = None

    if getattr(context, "created_customer_ids", None):
        for customer_id in context.created_customer_ids:
            delete_cart_via_api(context, customer_id)
        context.created_customer_ids.clear()


def after_all(context):
    """Tear down the Selenium browser."""
    if hasattr(context, "browser") and context.browser:
        context.browser.quit()


def delete_cart_via_ui(context, customer_id: int | str):
    """Delete a cart via the UI delete form."""
    if not customer_id:
        return
    browser = context.browser
    if not browser.current_url.startswith(context.base_url):
        browser.get(context.ui_url)
    delete_input = browser.find_element(By.ID, "delete-customer-id")
    delete_button = browser.find_element(By.ID, "delete-submit")
    delete_input.clear()
    delete_input.send_keys(str(customer_id))
    delete_button.click()


def create_cart_via_api(context, customer_id: int, **fields):
    """Create a cart quickly via the REST API for test setup."""
    payload = {"customer_id": customer_id}
    payload.update(fields)
    delete_cart_via_api(context, customer_id)
    response = requests.post(_api_url(context, "shopcarts"), json=payload, timeout=10)
    response.raise_for_status()
    return response.json()


def delete_cart_via_api(context, customer_id: int | str):
    """Remove a cart using the REST API; ignore 404s."""
    if not customer_id:
        return
    try:
        requests.delete(
            _api_url(context, f"shopcarts/{customer_id}"),
            timeout=10,
        )
    except requests.RequestException:
        pass


def _first_existing(*paths: str) -> str | None:
    for path in paths:
        if path and os.path.exists(path):
            return path
    return None


def _api_url(context, path: str) -> str:
    """Build a URL rooted at the running service base URL."""
    return urljoin(context.base_url + "/", path.lstrip("/"))
