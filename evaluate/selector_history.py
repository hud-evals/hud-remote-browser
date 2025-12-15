"""Selector history evaluation helper for remote browser environment."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def selector_history(
    playwright_tool: Any,
    index: int,
    expected_selector: str
) -> dict:
    """Check if selector at index matches expected.

    Args:
        playwright_tool: The PlaywrightToolWithMemory instance
        index: Index in selector history (0-based)
        expected_selector: Expected selector string

    Returns:
        Evaluation result with reward between 0.0 and 1.0
    """
    logger.info("Evaluating selector_history: index=%d, expected=%s", index, expected_selector)

    if not playwright_tool:
        logger.error("No playwright tool available")
        return {"reward": 0.0, "success": False, "error": "No playwright tool available"}

    sel_history = (
        playwright_tool.selector_history if hasattr(playwright_tool, "selector_history") else []
    )

    if index < 0 or index >= len(sel_history):
        logger.info("No selector found at index %d", index)
        return {
            "reward": 0.0,
            "success": False,
            "expected_selector": expected_selector,
            "selector_history_length": len(sel_history),
            "error": f"No selector found at index {index}",
        }

    actual_selector = sel_history[index]
    success = actual_selector == expected_selector

    if success:
        logger.info("Selector at index %d matches: %s", index, expected_selector)
    else:
        logger.info("Selector at index %d '%s' does not match expected '%s'", index, actual_selector, expected_selector)

    return {
        "reward": 1.0 if success else 0.0,
        "success": success,
        "actual_selector": actual_selector,
        "expected_selector": expected_selector,
        "index": index,
        "selector_history_length": len(sel_history),
    }
