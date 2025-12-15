"""Verify type action evaluation helper for remote browser environment."""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


async def verify_type_action(
    playwright_tool: Any,
    expected_text: str,
    selector: Optional[str] = None,
    partial_rewarding: bool = True,
) -> dict:
    """Check for a sequence: first click on element, then type text into it.

    Args:
        playwright_tool: The PlaywrightToolWithMemory instance
        expected_text: The expected text that should have been typed
        selector: Optional selector to check (if not provided, checks last type action)
        partial_rewarding: Whether to give partial rewards

    Returns:
        Evaluation result with reward between 0.0 and 1.0
    """
    logger.info("Starting verify_type_action evaluation")

    if not expected_text:
        logger.error("No expected text provided")
        return {"reward": 0.0, "success": False, "error": "No expected text provided"}

    logger.info("Looking for type action with text: %s", expected_text)
    if selector:
        logger.info("Checking for specific selector: %s", selector)

    if (
        not playwright_tool
        or not hasattr(playwright_tool, "action_history")
        or not playwright_tool.action_history
    ):
        logger.error("No playwright tool available")
        return {"reward": 0.0, "success": False, "error": "No playwright tool available"}

    action_history = playwright_tool.action_history
    logger.info("Total actions in history: %d", len(action_history))

    if len(action_history) == 0:
        logger.info("No actions in history")
        return {"reward": 0.0, "success": False, "action_count": 0, "error": "No actions in history"}

    # Look for the most recent type action
    for i in range(len(action_history) - 1, -1, -1):
        action = action_history[i]

        if action.get("type") == "type":
            action_details = action.get("details", {})
            typed_text = action_details.get("text", "")
            action_selector = action_details.get("selector", "")

            # Check if selector matches (if specified)
            if selector and action_selector != selector:
                continue

            # Check if typed text matches
            if str(typed_text) == str(expected_text):
                logger.info("Found matching type action at index %d", i)
                logger.info("  Selector: %s", action_selector)
                logger.info("  Text: '%s'", typed_text)

                return {
                    "reward": 1.0,
                    "success": True,
                    "typed_text": typed_text,
                    "selector": action_selector,
                    "action_index": i,
                }
            elif not selector:
                # If no specific selector required, any mismatch is a failure
                logger.info("Found type action but text mismatch")
                logger.info("  Expected: '%s'", expected_text)
                logger.info("  Got: '%s'", typed_text)

                if partial_rewarding:
                    return {
                        "reward": 0.5,
                        "success": False,
                        "expected": expected_text,
                        "actual": typed_text,
                        "selector": action_selector,
                    }

    logger.info("No matching type action found")
    return {
        "reward": 0.0,
        "success": False,
        "expected_text": expected_text,
        "required_selector": selector,
        "error": "No matching type action found",
    }
