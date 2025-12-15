"""Raw last action evaluation helper for remote browser environment."""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


async def raw_last_action_is(
    playwright_tool: Any,
    expected_action: str,
    expected_details: Optional[Dict[str, Any]] = None
) -> dict:
    """Check if the last action matches expected.

    Args:
        playwright_tool: The PlaywrightToolWithMemory instance
        expected_action: Expected action type (e.g., "click", "type", "navigate")
        expected_details: Optional expected details of the action

    Returns:
        Evaluation result with reward between 0.0 and 1.0
    """
    logger.info("Evaluating raw_last_action_is: expected=%s", expected_action)

    if not playwright_tool:
        logger.error("No playwright tool available")
        return {"reward": 0.0, "success": False, "error": "No playwright tool available"}

    action_history = (
        playwright_tool.action_history if hasattr(playwright_tool, "action_history") else []
    )

    if not action_history:
        logger.info("No actions have been performed yet")
        return {
            "reward": 0.0,
            "success": False,
            "expected_action": expected_action,
            "error": "No actions have been performed",
        }

    last_action = action_history[-1]

    action_matches = last_action["type"] == expected_action
    details_match = True

    if expected_details and action_matches:
        actual_details = last_action.get("details", {})
        for key, expected_value in expected_details.items():
            if actual_details.get(key) != expected_value:
                details_match = False
                break

    success = action_matches and details_match

    if success:
        logger.info("Last action matches: %s", expected_action)
    else:
        if not action_matches:
            logger.info("Last action '%s' does not match expected '%s'", last_action["type"], expected_action)
        else:
            logger.info("Action matches but details do not match")

    return {
        "reward": 1.0 if success else 0.0,
        "success": success,
        "last_action": last_action,
        "expected_action": expected_action,
        "expected_details": expected_details,
    }
