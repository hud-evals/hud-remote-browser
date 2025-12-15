"""Cookie match evaluation helper for remote browser environment."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def cookie_match(
    playwright_tool: Any,
    cookie_name: str,
    expected_value: str
) -> dict:
    """Check if a cookie value matches expected value.

    Args:
        playwright_tool: The PlaywrightToolWithMemory instance
        cookie_name: Name of the cookie to check
        expected_value: Expected value of the cookie

    Returns:
        Evaluation result with reward between 0.0 and 1.0
    """
    logger.info("Checking cookie %s for value: %s", cookie_name, expected_value)

    if not playwright_tool or not hasattr(playwright_tool, "page") or not playwright_tool.page:
        logger.error("No browser page available")
        return {"reward": 0.0, "success": False, "error": "No browser page available"}

    try:
        cookies = await playwright_tool.page.context.cookies()
        cookie = next((c for c in cookies if c.get("name") == cookie_name), None)

        if not cookie:
            logger.info("Cookie not found: %s", cookie_name)
            return {
                "reward": 0.0,
                "success": False,
                "cookie_name": cookie_name,
                "error": "Cookie not found",
            }

        actual_value = cookie.get("value", "")
        if actual_value == expected_value:
            logger.info("Cookie value matches: %s=%s", cookie_name, expected_value)
            return {
                "reward": 1.0,
                "success": True,
                "cookie_name": cookie_name,
                "value": actual_value,
            }
        else:
            logger.info("Cookie value mismatch: expected '%s', got '%s'", expected_value, actual_value)
            return {
                "reward": 0.0,
                "success": False,
                "cookie_name": cookie_name,
                "expected": expected_value,
                "actual": actual_value,
            }

    except Exception as e:
        logger.error("Error checking cookie: %s", e)
        return {"reward": 0.0, "success": False, "error": str(e)}
