"""Google Sheets cell values evaluation helper for remote browser environment."""

import asyncio
import logging
from typing import Any, Dict, List, Union

logger = logging.getLogger(__name__)


def column_to_index(col_str: str) -> int:
    """Convert column letters to 0-indexed column number.
    
    Examples:
        A -> 0, B -> 1, Z -> 25, AA -> 26, AB -> 27, AZ -> 51, BA -> 52
    """
    result = 0
    for char in col_str.upper():
        result = result * 26 + (ord(char) - ord("A") + 1)
    return result - 1  # Convert to 0-indexed


def parse_cell_reference(cell_ref: str) -> tuple[str, int, int] | None:
    """Parse a cell reference like 'A1', 'AA123', 'B2' into (col_letters, row_num, col_num).
    
    Returns:
        Tuple of (column_letters, row_number_0indexed, column_number_0indexed) or None if invalid
    """
    # Find where the letters end and digits begin
    col_letters = ""
    row_digits = ""
    
    for i, char in enumerate(cell_ref):
        if char.isalpha():
            col_letters += char.upper()
        elif char.isdigit():
            row_digits = cell_ref[i:]
            break
        else:
            return None  # Invalid character
    
    # Validate we have both column and row
    if not col_letters or not row_digits or not row_digits.isdigit():
        return None
    
    row_num = int(row_digits) - 1  # Convert to 0-indexed
    col_num = column_to_index(col_letters)
    
    return (col_letters, row_num, col_num)


async def sheets_cell_values(
    playwright_tool: Any,
    cell_values: Union[Dict[str, Any], List[Dict[str, Any]]],
    partial_rewarding: bool = True
) -> dict:
    """Check if specific cells in a Google Sheet have expected values.

    Args:
        playwright_tool: The PlaywrightToolWithMemory instance
        cell_values: Either a dict of cell mappings {"A1": "value", "B2": "value"}
                     or a list with a dict [{"A1": "value", "B2": "value"}]
        partial_rewarding: Whether to give partial rewards

    Returns:
        Evaluation result with reward between 0.0 and 1.0
    """
    logger.info("Starting sheets_cell_values evaluation")
    logger.info("Received cell_values: %s", cell_values)

    # Extract cell values from args
    if isinstance(cell_values, list) and len(cell_values) > 0:
        values = cell_values[0] if isinstance(cell_values[0], dict) else {}
    elif isinstance(cell_values, dict):
        values = cell_values
    else:
        values = {}

    logger.info("Cell values to check: %s", values)

    if not playwright_tool or not hasattr(playwright_tool, "page") or not playwright_tool.page:
        logger.error("No browser page available")
        return {"reward": 0.0, "success": False, "error": "No browser page available"}

    page = playwright_tool.page
    context = page.context

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

    if not isinstance(values, dict):
        logger.error("Invalid cell values format: %s", values)
        return {
            "reward": 0.0,
            "success": False,
            "error": f"Invalid cell values format. Expected dict, got {type(values)}",
        }

    if not values:
        logger.warning("No cell values to check")
        return {"reward": 1.0, "success": True, "message": "No cell values to check"}

    # Try to navigate to the ANSWER sheet tab with retries
    logger.info("=== ANSWER Sheet Navigation ===")
    max_attempts = 3
    answer_navigation_successful = False

    for attempt in range(1, max_attempts + 1):
        try:
            logger.info("Attempt %d/%d: Attempting to find and navigate to ANSWER sheet tab...", attempt, max_attempts)

            answer_tab_selector = 'span.docs-sheet-tab-name:has-text("ANSWER")'
            logger.info("Searching for ANSWER tab with selector: %s", answer_tab_selector)

            answer_tab_exists = await page.locator(answer_tab_selector).count() > 0
            logger.info("ANSWER tab search result (attempt %d): %s", attempt, "Found" if answer_tab_exists else "Not found")

            if answer_tab_exists:
                logger.info("Found ANSWER sheet tab on attempt %d, clicking on it...", attempt)
                await page.locator(answer_tab_selector).click()
                logger.info("Clicked on ANSWER tab, waiting for sheet to switch...")

                try:
                    await page.wait_for_timeout(1000)
                except Exception:
                    await asyncio.sleep(1)
                logger.info("Successfully navigated to ANSWER sheet on attempt %d", attempt)
                answer_navigation_successful = True
                break
            else:
                logger.warning("ANSWER sheet tab not found on attempt %d", attempt)
                if attempt < max_attempts:
                    logger.info("Waiting 500ms before retry %d...", attempt + 1)
                    try:
                        await page.wait_for_timeout(500)
                    except Exception:
                        await asyncio.sleep(0.5)

        except Exception as nav_error:
            logger.error("Error navigating to ANSWER sheet on attempt %d: %s", attempt, str(nav_error))
            if attempt < max_attempts:
                logger.info("Waiting 2500ms before retry %d...", attempt + 1)
                try:
                    await page.wait_for_timeout(2500)
                except Exception:
                    await asyncio.sleep(2.5)

    if not answer_navigation_successful:
        logger.warning("Failed to navigate to ANSWER sheet after %d attempts, proceeding with current sheet", max_attempts)

    # Wait for sheet to fully load
    logger.info("Waiting for sheet to fully load...")
    try:
        await page.wait_for_selector(".grid-container", timeout=20000)
        logger.info("Sheet grid container loaded")
        try:
            await page.wait_for_timeout(2000)
        except Exception:
            await asyncio.sleep(2)
    except Exception as e:
        logger.warning("Timeout waiting for sheet to load: %s", str(e))
        await asyncio.sleep(5)

    # Extract sheet content using clipboard method
    try:
        logger.info("=== File Content Extraction ===")

        try:
            await context.grant_permissions(["clipboard-read", "clipboard-write"])
            logger.info("Granted clipboard read-write permissions")
        except Exception as perm_error:
            logger.warning("Failed to grant permissions: %s", str(perm_error))

        logger.info("Extracting page contents")

        await page.keyboard.press("Escape")
        await page.locator("body").click(force=True)
        await page.click(".fixed4-inner-container")

        logger.info("Selecting all content with Ctrl+A")
        await page.keyboard.press("Control+A")
        await asyncio.sleep(1)

        await page.keyboard.press("Control+C")
        await asyncio.sleep(1)

        clipboard_content = await page.evaluate("() => navigator.clipboard.readText()")
        logger.info("Successfully extracted %d characters from file", len(clipboard_content))

        rows = clipboard_content.rstrip("\n").split("\n")
        logger.info("Split file content into %d rows", len(rows))

        if len(rows) > 0:
            logger.info("First few rows of content:")
            for i, row in enumerate(rows[:3]):
                row_preview = row.replace("\t", " | ")[:100]
                logger.info("  Row %d: '%s%s'", i + 1, row_preview, "..." if len(row) > 100 else "")
            if len(rows) > 3:
                logger.info("  ... and %d more rows", len(rows) - 3)

        logger.info("=== Cell Reference Parsing ===")

        actual_values = {}
        for cell_ref, expected_value in values.items():
            logger.info("Processing cell reference: '%s' -> expected: '%s'", cell_ref, expected_value)

            # Parse cell reference (supports multi-letter columns like AA, AB, etc.)
            parsed = parse_cell_reference(cell_ref)
            if parsed is None:
                logger.error("Invalid cell reference format: '%s' (expected format: A1, B2, AA1, etc.)", cell_ref)
                actual_values[cell_ref] = None
                continue

            col_letters, row_num, col_num = parsed

            logger.info("  Parsed '%s' -> row=%d (0-indexed: %d), col=%s (0-indexed: %d)",
                       cell_ref, row_num + 1, row_num, col_letters, col_num)

            if row_num < len(rows):
                logger.info("  Row %d exists in content", row_num + 1)
                cells = rows[row_num].split("\t")
                logger.info("  Row %d has %d columns", row_num + 1, len(cells))

                if col_num < len(cells):
                    actual_values[cell_ref] = cells[col_num]
                    logger.info("  Found value for %s: '%s'", cell_ref, actual_values[cell_ref])
                else:
                    logger.warning("  Column %s (index %d) not found in row %d (has %d columns)",
                                  col_letters, col_num, row_num + 1, len(cells))
                    actual_values[cell_ref] = ""
            else:
                logger.warning("  Row %d not found in content (has %d rows)", row_num + 1, len(rows))
                actual_values[cell_ref] = ""

        logger.info("=== Cell Value Comparison ===")

        total_cells = len(values)
        matching_cells = 0
        mismatches = []

        for cell_ref, expected_value in values.items():
            actual_value = actual_values.get(cell_ref, "")
            logger.info("Comparing cell %s:", cell_ref)
            logger.info("  Expected: '%s' (type: %s)", expected_value, type(expected_value))
            logger.info("  Actual:   '%s' (type: %s)", actual_value, type(actual_value))

            if actual_value is None:
                mismatches.append({"cell": cell_ref, "expected": expected_value, "actual": ""})
                logger.info("  Cell %s not found", cell_ref)
            elif str(actual_value).strip() == str(expected_value).strip():
                matching_cells += 1
                logger.info("  MATCH: '%s' == '%s'", str(actual_value).strip(), str(expected_value).strip())
            else:
                mismatches.append({
                    "cell": cell_ref,
                    "expected": expected_value,
                    "actual": actual_value,
                })
                logger.info("  VALUE MISMATCH: '%s' != '%s'", str(actual_value).strip(), str(expected_value).strip())

        # Calculate reward
        if partial_rewarding and total_cells > 0:
            reward = matching_cells / total_cells
            logger.info("Partial rewarding: %d/%d = %f", matching_cells, total_cells, reward)
        elif matching_cells == total_cells:
            reward = 1.0
            logger.info("ALL cells match expected values!")
        else:
            reward = 0.0
            logger.info("NOT all cells match expected values")
            logger.info("Mismatches: %s", mismatches)

        success = matching_cells == total_cells
        logger.info("Final reward: %f", reward)

        return {
            "reward": float(reward),
            "success": success,
            "matching_cells": matching_cells,
            "total_cells": total_cells,
            "mismatches": mismatches,
        }

    except Exception as e:
        logger.error("Error evaluating sheet cells: %s", str(e), exc_info=True)
        return {"reward": 0.0, "success": False, "error": f"Failed to evaluate: {str(e)}"}
