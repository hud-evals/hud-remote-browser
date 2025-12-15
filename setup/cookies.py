"""Cookie setup helpers for remote browser environment."""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


async def set_cookies(playwright_tool: Any, cookies: List[Dict[str, Any]]) -> dict:
    """Set cookies in the browser.

    Args:
        playwright_tool: The PlaywrightToolWithMemory instance
        cookies: List of cookie dictionaries with name, value, and optional properties

    Returns:
        Result dict with success status
    """
    logger.info("Setting %d cookies", len(cookies))

    if not playwright_tool or not hasattr(playwright_tool, "page") or not playwright_tool.page:
        logger.error("No browser page available")
        return {"success": False, "error": "No browser page available"}

    try:
        await playwright_tool.page.context.add_cookies(cookies)
        cookie_names = [c.get("name", "unnamed") for c in cookies]
        logger.info("Successfully set %d cookies", len(cookies))
        return {
            "success": True,
            "count": len(cookies),
            "names": cookie_names,
        }
    except Exception as e:
        logger.error("Failed to set cookies: %s", e)
        return {"success": False, "error": str(e)}


async def clear_cookies(playwright_tool: Any) -> dict:
    """Clear all cookies from the browser.

    Args:
        playwright_tool: The PlaywrightToolWithMemory instance

    Returns:
        Result dict with success status
    """
    logger.info("Clearing all cookies")

    if not playwright_tool or not hasattr(playwright_tool, "page") or not playwright_tool.page:
        logger.error("No browser page available")
        return {"success": False, "error": "No browser page available"}

    try:
        await playwright_tool.page.context.clear_cookies()
        logger.info("Successfully cleared all cookies")
        return {"success": True}
    except Exception as e:
        logger.error("Failed to clear cookies: %s", e)
        return {"success": False, "error": str(e)}
