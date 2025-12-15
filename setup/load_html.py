"""HTML content loading helper for remote browser environment."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def load_html_content(playwright_tool: Any, html: str) -> dict:
    """Load custom HTML content directly into the browser.

    Args:
        playwright_tool: The PlaywrightToolWithMemory instance
        html: HTML content to load

    Returns:
        Result dict with success status
    """
    logger.info("Loading custom HTML content into browser")

    if not playwright_tool or not hasattr(playwright_tool, "page") or not playwright_tool.page:
        logger.error("No browser page available")
        return {"success": False, "error": "No browser page available"}

    try:
        data_url = f"data:text/html,{html}"
        await playwright_tool.page.goto(data_url)
        logger.info("Successfully loaded custom HTML content")
        return {
            "success": True,
            "length": len(html),
            "url": playwright_tool.page.url,
        }
    except Exception as e:
        logger.error("Failed to load HTML content: %s", e)
        return {"success": False, "error": str(e)}
