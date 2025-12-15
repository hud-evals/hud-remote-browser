"""Page contains evaluation helper for remote browser environment."""

import logging
from typing import Any, List, Union

logger = logging.getLogger(__name__)


async def page_contains(
    playwright_tool: Any,
    search_terms: Union[str, List[str]],
    partial_rewarding: bool = True
) -> dict:
    """Check if the page contains specific text.

    Args:
        playwright_tool: The PlaywrightToolWithMemory instance
        search_terms: Text to search for (string or list of strings)
        partial_rewarding: If True, give partial credit for finding some terms

    Returns:
        Evaluation result with reward between 0.0 and 1.0
    """
    logger.info("Evaluating page_contains for terms: %s", search_terms)

    if not playwright_tool or not hasattr(playwright_tool, "page") or not playwright_tool.page:
        logger.error("No browser page available")
        return {"reward": 0.0, "success": False, "error": "No browser page available"}

    try:
        content = await playwright_tool.page.content()
        logger.info("Page content retrieved, length: %d", len(content))
    except Exception as e:
        logger.error("Failed to get page content: %s", e)
        return {"reward": 0.0, "success": False, "error": f"Failed to get page content: {str(e)}"}

    # Normalize search terms to list
    if isinstance(search_terms, str):
        terms = [search_terms]
    else:
        terms = search_terms

    # Search for terms
    found_terms = []
    not_found_terms = []

    for term in terms:
        if term in content:
            found_terms.append(term)
            logger.info("Found term: '%s'", term)
        else:
            not_found_terms.append(term)
            logger.info("Term not found: '%s'", term)

    # Calculate reward
    if partial_rewarding and terms:
        reward = len(found_terms) / len(terms)
    else:
        reward = 1.0 if len(not_found_terms) == 0 else 0.0

    logger.info("Page contains evaluation complete. Reward: %f", reward)

    return {
        "reward": float(reward),
        "success": reward > 0,
        "found_terms": found_terms,
        "not_found_terms": not_found_terms,
        "total_terms": len(terms),
        "partial_rewarding": partial_rewarding,
    }
