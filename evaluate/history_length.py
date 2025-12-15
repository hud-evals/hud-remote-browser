"""History length evaluation helper for remote browser environment."""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


async def history_length(
    playwright_tool: Any,
    min_length: Optional[int] = None,
    max_length: Optional[int] = None
) -> dict:
    """Check if action history has specific length.

    Args:
        playwright_tool: The PlaywrightToolWithMemory instance
        min_length: Minimum required length
        max_length: Maximum allowed length

    Returns:
        Evaluation result with reward between 0.0 and 1.0
    """
    logger.info("Evaluating history length - min: %s, max: %s", min_length, max_length)

    if not playwright_tool:
        logger.error("No playwright tool available")
        return {"reward": 0.0, "success": False, "error": "No playwright tool available"}

    # Get action history from PlaywrightToolWithMemory
    hist_len = len(playwright_tool.action_history) if hasattr(playwright_tool, "action_history") else 0
    logger.info("Current history length: %d", hist_len)

    in_range = True
    if min_length is not None and hist_len < min_length:
        in_range = False
        logger.info("History too short: %d < %d", hist_len, min_length)
    if max_length is not None and hist_len > max_length:
        in_range = False
        logger.info("History too long: %d > %d", hist_len, max_length)

    if in_range:
        logger.info("History length in range: %d", hist_len)

    # Calculate reward based on how close we are to the target
    if min_length is not None and max_length is not None:
        target = (min_length + max_length) / 2
        reward = max(0, 1 - abs(hist_len - target) / target) if target > 0 else (1.0 if in_range else 0.0)
    else:
        reward = 1.0 if in_range else 0.0

    return {
        "reward": float(reward),
        "success": in_range,
        "history_length": hist_len,
        "min_length": min_length,
        "max_length": max_length,
        "in_range": in_range,
    }
