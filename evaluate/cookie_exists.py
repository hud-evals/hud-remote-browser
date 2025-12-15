"""Cookie exists evaluation helper for remote browser environment."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def cookie_exists(playwright_tool: Any, cookie_name: str) -> dict:
    """Check if a cookie exists in the browser.

    Args:
        playwright_tool: The PlaywrightToolWithMemory instance
        cookie_name: Name of the cookie to check for

    Returns:
        Evaluation result with reward between 0.0 and 1.0
    """
    logger.info("Checking if cookie exists: %s", cookie_name)

    if not playwright_tool or not hasattr(playwright_tool, "page") or not playwright_tool.page:
        logger.error("No browser page available")
        return {"reward": 0.0, "success": False, "error": "No browser page available"}

    try:
        cookies = await playwright_tool.page.context.cookies()
        cookie = next((c for c in cookies if c.get("name") == cookie_name), None)

        if cookie:
            logger.info("Cookie found: %s", cookie_name)
            return {
                "reward": 1.0,
                "success": True,
                "cookie_name": cookie_name,
                "cookie_value": cookie.get("value", ""),
                "domain": cookie.get("domain", ""),
            }
        else:
            logger.info("Cookie not found: %s", cookie_name)
            return {
                "reward": 0.0,
                "success": False,
                "cookie_name": cookie_name,
                "total_cookies": len(cookies),
            }

    except Exception as e:
        logger.error("Error checking cookie: %s", e)
        return {"reward": 0.0, "success": False, "error": str(e)}
