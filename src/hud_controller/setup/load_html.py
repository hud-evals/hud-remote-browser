"""Setup function to load custom HTML content."""

import logging
from fastmcp import Context
from mcp.types import TextContent
from . import setup

logger = logging.getLogger(__name__)


@setup.tool("load_html_content")
async def load_html_content(ctx: Context, html: str):
    """Load custom HTML content directly into the browser.

    Args:
        html: HTML content to load

    Returns:
        Setup result with status
    """
    logger.info("Loading custom HTML content into browser")

    # Get the playwright tool from the environment context
    persistent_ctx = setup.env
    playwright_tool = getattr(persistent_ctx, "playwright_tool", None)
    if not playwright_tool or not hasattr(playwright_tool, "page") or not playwright_tool.page:
        logger.error("No browser page available")
        return TextContent(text="No browser page available", type="text")

    try:
        # Create a data URL with the HTML content
        data_url = f"data:text/html,{html}"

        # Navigate to the data URL
        await playwright_tool.page.goto(data_url)
        logger.info("Successfully loaded custom HTML content")

        return TextContent(
            text=f"Custom HTML content loaded ({len(html)} chars) - URL: {playwright_tool.page.url}",
            type="text",
        )
    except Exception as e:
        logger.error(f"Failed to load HTML content: {e}")
        return TextContent(text=f"Failed to load HTML content: {str(e)}", type="text")
