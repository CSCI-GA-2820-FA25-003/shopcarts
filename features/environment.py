"""Behave environment configuration for Selenium UI tests."""

from __future__ import annotations

import os
import time
from urllib.parse import urljoin

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager


def before_all(context):
    """Initialise the Selenium browser before running any scenarios."""
    base_url = os.getenv("BASE_URL", "http://127.0.0.1:8080")
    context.base_url = base_url.rstrip("/")
    context.ui_url = urljoin(context.base_url + "/", "ui")

    chrome_options = Options()
    # Always try to find and use system Chromium first (important for ARM64)
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
        print(f"Using Chrome binary: {chrome_binary}")

    # Headless mode options for Docker/CI environments
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1440,900")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-software-rasterizer")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-background-networking")
    chrome_options.add_argument("--disable-background-timer-throttling")
    chrome_options.add_argument("--disable-renderer-backgrounding")
    chrome_options.add_argument("--disable-backgrounding-occluded-windows")
    chrome_options.add_argument("--disable-ipc-flooding-protection")
    chrome_options.add_argument("--remote-debugging-port=9222")
    
    # Try to find or install chromedriver
    # For ARM64, we MUST use system chromedriver, not webdriver-manager
    driver_path = os.getenv("CHROMEDRIVER")
    if not driver_path:
        # Prefer system chromedriver (works on ARM64)
        driver_path = _first_existing("/usr/bin/chromedriver", "/usr/lib/chromium/chromedriver")
        if driver_path:
            print(f"Using system ChromeDriver: {driver_path}")
    
    # Only use webdriver-manager as last resort (doesn't work well on ARM64)
    if not driver_path:
        try:
            driver_path = ChromeDriverManager().install()
            if driver_path and os.path.exists(driver_path):
                os.chmod(driver_path, 0o755)
        except Exception as e:
            print(f"Warning: Could not install ChromeDriver via webdriver-manager: {e}")
            driver_path = None
    
    # Create service with explicit driver path (required for ARM64)
    # On ARM64, Selenium's auto-detection doesn't work, so we must be explicit
    if not driver_path or not os.path.exists(driver_path):
        raise RuntimeError(
            f"ChromeDriver not found. Please ensure chromedriver is installed. "
            f"Tried: {driver_path}"
        )
    
    try:
        # Use explicit service with system chromedriver (required for ARM64)
        service = Service(driver_path)
        context.browser = webdriver.Chrome(service=service, options=chrome_options)
        print(f"Successfully created Chrome WebDriver with driver: {driver_path}")
    except Exception as e:
        error_msg = (
            f"Failed to create Chrome WebDriver. "
            f"Driver: {driver_path}, Binary: {chrome_binary}, Error: {e}"
        )
        print(f"Error: {error_msg}")
        raise RuntimeError(error_msg) from e
    
    context.browser.implicitly_wait(5)


def before_scenario(context, _scenario):
    context.cleanup_customer_id = None
    context.cleanup_customer_ids = []
    context.table_snapshot = None


def after_scenario(context, _scenario):
    # Clean up any test data created during the scenario
    if hasattr(context, "cleanup_customer_ids") and context.cleanup_customer_ids:
        for customer_id in context.cleanup_customer_ids:
            try:
                delete_cart_via_ui(context, customer_id)
                time.sleep(0.5)  # Small delay between deletions
            except Exception:
                pass  # Ignore cleanup errors
        context.cleanup_customer_ids = []
    
    # Also handle single cleanup_customer_id for backward compatibility
    if hasattr(context, "cleanup_customer_id") and context.cleanup_customer_id is not None:
        try:
            delete_cart_via_ui(context, context.cleanup_customer_id)
            time.sleep(1)
        except Exception:
            pass
        context.cleanup_customer_id = None


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


def _first_existing(*paths: str) -> str | None:
    for path in paths:
        if path and os.path.exists(path):
            return path
    return None
