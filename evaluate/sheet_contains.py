"""Google Sheet contains evaluation helper for remote browser environment."""

import logging
from typing import Any, List, Union

logger = logging.getLogger(__name__)


async def sheet_contains(
    playwright_tool: Any,
    search_terms: Union[str, List[str]],
    partial_rewarding: bool = True
) -> dict:
    """Check if a Google Sheet contains specific text by copying content to clipboard.

    Args:
        playwright_tool: The PlaywrightToolWithMemory instance
        search_terms: Search terms as string or list of strings
        partial_rewarding: Whether to give partial rewards

    Returns:
        Evaluation result with reward between 0.0 and 1.0
    """
    logger.info("Starting sheet_contains evaluation")

    if not playwright_tool or not hasattr(playwright_tool, "page") or not playwright_tool.page:
        logger.error("No browser page available")
        return {"reward": 0.0, "success": False, "error": "No browser page available"}

    page = playwright_tool.page
    current_url = page.url
    logger.info("Current page URL: %s", current_url)

    if "docs.google.com/spreadsheets" not in current_url:
        logger.error("Not on a Google Sheets page! URL: %s", current_url)
        return {
            "reward": 0.0,
            "success": False,
            "error": f"Not on a Google Sheets page! URL: {current_url}",
        }

    logger.info("Confirmed on Google Sheets page")

    # Process search terms
    if isinstance(search_terms, str):
        terms = [search_terms]
    elif isinstance(search_terms, list):
        terms = search_terms
    else:
        logger.error("Invalid search_terms format: %s", search_terms)
        return {
            "reward": 0.0,
            "success": False,
            "error": f"Invalid search_terms format. Expected string or list, got {type(search_terms)}",
        }

    if not terms:
        logger.error("No search terms provided")
        return {"reward": 0.0, "success": False, "error": "No search terms provided"}

    logger.info("Search terms to find: %s", terms)

    try:
        # Wait for sheet to fully load
        logger.info("Waiting for sheet to fully load...")
        try:
            await page.wait_for_selector(".grid-container", timeout=20000)
            logger.info("Sheet grid container loaded")
            await page.wait_for_timeout(2000)
        except Exception as e:
            logger.warning("Timeout waiting for sheet to load: %s", str(e))
            await page.wait_for_timeout(5000)

        # Select all cells using Ctrl+A
        logger.info("Selecting all cells with Ctrl+A")
        await page.keyboard.press("Control+A")
        await page.wait_for_timeout(500)

        # Copy to clipboard with Ctrl+C
        logger.info("Copying content to clipboard with Ctrl+C")
        await page.keyboard.press("Control+C")
        await page.wait_for_timeout(1000)

        # Get clipboard content
        logger.info("Getting clipboard content")
        clipboard_content = await page.evaluate("() => navigator.clipboard.readText()")

        if not clipboard_content:
            logger.warning("Clipboard content is empty")
            return {"reward": 0.0, "success": False, "error": "Clipboard content is empty"}

        logger.info("Clipboard content length: %d characters", len(clipboard_content))

        # Check for search terms
        found_terms = []
        missing_terms = []

        for term in terms:
            if term.lower() in clipboard_content.lower():
                found_terms.append(term)
                logger.info("Found term: '%s'", term)
            else:
                missing_terms.append(term)
                logger.info("Missing term: '%s'", term)

        # Calculate reward
        if partial_rewarding and len(terms) > 0:
            reward = float(len(found_terms)) / len(terms)
            logger.info("Partial rewarding: %d/%d = %f", len(found_terms), len(terms), reward)
        elif not missing_terms:
            reward = 1.0
            logger.info("All terms found!")
        else:
            reward = 0.0
            logger.info("Missing terms: %s", missing_terms)

        success = not missing_terms

        return {
            "reward": float(reward),
            "success": success,
            "found_terms": found_terms,
            "missing_terms": missing_terms,
            "total_terms": len(terms),
            "clipboard_length": len(clipboard_content),
        }

    except Exception as e:
        logger.error("Exception during sheet_contains evaluation: %s", str(e))
        return {"reward": 0.0, "success": False, "error": f"Failed to evaluate: {str(e)}"}
