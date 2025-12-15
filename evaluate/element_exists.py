"""Element exists evaluation helper for remote browser environment."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def element_exists(playwright_tool: Any, selector: str) -> dict:
    """Check if an element exists on the page.

    Args:
        playwright_tool: The PlaywrightToolWithMemory instance
        selector: CSS selector for the element

    Returns:
        Evaluation result with reward between 0.0 and 1.0
    """
    logger.info("Checking if element exists: %s", selector)

    if not playwright_tool or not hasattr(playwright_tool, "page") or not playwright_tool.page:
        logger.error("No browser page available")
        return {"reward": 0.0, "success": False, "error": "No browser page available"}

    try:
        element = await playwright_tool.page.query_selector(selector)

        if element:
            logger.info("Element found: %s", selector)
            return {
                "reward": 1.0,
                "success": True,
                "selector": selector,
            }
        else:
            logger.info("Element not found: %s", selector)
            return {
                "reward": 0.0,
                "success": False,
                "selector": selector,
            }

    except Exception as e:
        logger.error("Error checking element: %s", e)
        return {"reward": 0.0, "success": False, "error": str(e)}
