"""Interaction setup helpers for remote browser environment."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def click_element(
    playwright_tool: Any,
    selector: str,
    timeout: int = 30000
) -> dict:
    """Click on an element by selector.

    Args:
        playwright_tool: The PlaywrightToolWithMemory instance
        selector: CSS selector for the element
        timeout: Maximum time to wait for element (ms)

    Returns:
        Result dict with success status
    """
    logger.info("Clicking element with selector: %s", selector)

    if not playwright_tool or not hasattr(playwright_tool, "page") or not playwright_tool.page:
        logger.error("No browser page available")
        return {"success": False, "error": "No browser page available"}

    try:
        element = await playwright_tool.page.wait_for_selector(selector, timeout=timeout)
        await element.click()
        logger.info("Successfully clicked element: %s", selector)
        return {"success": True, "selector": selector}
    except Exception as e:
        logger.error("Failed to click element: %s", e)
        return {"success": False, "error": str(e)}


async def fill_input(
    playwright_tool: Any,
    selector: str,
    text: str,
    timeout: int = 30000
) -> dict:
    """Fill an input field with text.

    Args:
        playwright_tool: The PlaywrightToolWithMemory instance
        selector: CSS selector for the input element
        text: Text to fill in the input
        timeout: Maximum time to wait for element (ms)

    Returns:
        Result dict with success status
    """
    logger.info("Filling input %s with text", selector)

    if not playwright_tool or not hasattr(playwright_tool, "page") or not playwright_tool.page:
        logger.error("No browser page available")
        return {"success": False, "error": "No browser page available"}

    try:
        element = await playwright_tool.page.wait_for_selector(selector, timeout=timeout)
        await element.fill(text)
        logger.info("Successfully filled input: %s", selector)
        return {"success": True, "selector": selector, "length": len(text)}
    except Exception as e:
        logger.error("Failed to fill input: %s", e)
        return {"success": False, "error": str(e)}


async def select_option(
    playwright_tool: Any,
    selector: str,
    value: str,
    timeout: int = 30000
) -> dict:
    """Select an option in a dropdown.

    Args:
        playwright_tool: The PlaywrightToolWithMemory instance
        selector: CSS selector for the select element
        value: Value of the option to select
        timeout: Maximum time to wait for element (ms)

    Returns:
        Result dict with success status
    """
    logger.info("Selecting option %s in %s", value, selector)

    if not playwright_tool or not hasattr(playwright_tool, "page") or not playwright_tool.page:
        logger.error("No browser page available")
        return {"success": False, "error": "No browser page available"}

    try:
        await playwright_tool.page.select_option(selector, value, timeout=timeout)
        logger.info("Successfully selected option: %s", value)
        return {"success": True, "selector": selector, "value": value}
    except Exception as e:
        logger.error("Failed to select option: %s", e)
        return {"success": False, "error": str(e)}
