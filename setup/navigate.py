"""Navigation setup helpers for remote browser environment."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def navigate_to_url(
    playwright_tool: Any,
    url: str,
    wait_for_load_state: str = "networkidle"
) -> dict:
    """Navigate browser to a specific URL.

    Args:
        playwright_tool: The PlaywrightToolWithMemory instance
        url: The URL to navigate to
        wait_for_load_state: State to wait for after navigation

    Returns:
        Result dict with success status
    """
    logger.info("Navigating to URL: %s", url)

    if not playwright_tool or not hasattr(playwright_tool, "page") or not playwright_tool.page:
        logger.error("No playwright tool available")
        return {"success": False, "error": "No browser available for navigation"}

    result = await playwright_tool.navigate(url, wait_for_load_state)

    if result.get("success"):
        logger.info("Successfully navigated to %s", url)
        return {
            "success": True,
            "url": url,
            "title": result.get("title", "Unknown"),
        }
    else:
        logger.error("Failed to navigate: %s", result.get("error"))
        return {"success": False, "error": result.get("error")}
