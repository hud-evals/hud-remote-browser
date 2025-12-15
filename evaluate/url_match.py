"""URL match evaluation helper for remote browser environment."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def url_match(playwright_tool: Any, target_url: str) -> dict:
    """Check if the current URL contains a target string.

    Args:
        playwright_tool: The PlaywrightToolWithMemory instance
        target_url: The target URL string to look for

    Returns:
        Evaluation result with reward between 0.0 and 1.0
    """
    logger.info("Evaluating URL match for target: '%s'", target_url)

    if not playwright_tool or not hasattr(playwright_tool, "page") or not playwright_tool.page:
        logger.error("No browser page available")
        return {"reward": 0.0, "success": False, "error": "No browser page available"}

    current_url = playwright_tool.page.url
    logger.info("Current page URL: '%s'", current_url)

    if target_url in current_url:
        logger.info("URL match successful: '%s' found in '%s'", target_url, current_url)
        return {
            "reward": 1.0,
            "success": True,
            "current_url": current_url,
            "target_url": target_url,
        }
    else:
        logger.info("URL match failed: '%s' not found in '%s'", target_url, current_url)

        info = {
            "reward": 0.0,
            "success": False,
            "current_url": current_url,
            "target_url": target_url,
        }

        # Check for partial matches
        if target_url.lower() in current_url.lower():
            info["note"] = "Case-insensitive match found"

        # Check for protocol differences
        if current_url.startswith("https://") and not target_url.startswith("https://"):
            alt_target = "https://" + target_url
            if alt_target in current_url:
                info["note"] = "Match found with https:// prefix"

        return info
