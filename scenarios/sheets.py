"""Google Sheets scenarios - complete tasks in spreadsheets."""
import logging
from typing import Any, Dict, List, Optional, Union

from setup.navigate import navigate_to_url
from setup.sheets import sheets_from_xlsx, sheets_from_bytes, navigate_to_google_sheet
from evaluate.sheets_cell_values import sheets_cell_values
from evaluate.sheet_contains import sheet_contains

logger = logging.getLogger(__name__)


def register_sheets_scenarios(env: Any) -> None:
    """Register Google Sheets scenarios with the environment."""

    @env.scenario("complete-sheet-task")
    async def complete_sheet_task(
        prompt: str,
        sheet_url: str,
        expected_cells: Dict[str, Any],
        partial_rewarding: bool = True,
    ) -> Any:
        """Complete a task in a Google Sheet and verify cell values.
        
        Args:
            prompt: The task instruction for the agent
            sheet_url: URL of the Google Sheet to work on
            expected_cells: Dict mapping cell references to expected values, e.g. {"A1": "100", "B2": "Total"}
            partial_rewarding: Whether to give partial credit for some correct cells
        """
        from env import persistent_ctx
        playwright_tool = persistent_ctx.playwright_tool if persistent_ctx else None

        if not playwright_tool:
            logger.error("No playwright tool available")
            yield 0.0
            return

        # Setup: Navigate to the sheet
        logger.info("Navigating to sheet: %s", sheet_url)
        if playwright_tool.page:
            await navigate_to_google_sheet(playwright_tool.page, sheet_url)
        else:
            await navigate_to_url(playwright_tool, sheet_url)

        # Yield the task prompt
        _ = yield prompt

        # Evaluate: Check if cells have expected values
        result = await sheets_cell_values(
            playwright_tool, 
            expected_cells, 
            partial_rewarding=partial_rewarding
        )
        
        logger.info("Sheet task result: %d/%d cells correct, reward=%.2f", 
                   result.get("matching_cells", 0), 
                   result.get("total_cells", 0),
                   result["reward"])
        
        yield result["reward"]

    @env.scenario("sheet-from-file")
    async def sheet_from_file(
        prompt: str,
        file_url: Optional[str] = None,
        file_bytes: Optional[str] = None,
        sheet_name: str = "Worksheet",
        expected_cells: Optional[Dict[str, Any]] = None,
        expected_text: Optional[Union[str, List[str]]] = None,
    ) -> Any:
        """Create a sheet from an Excel file and complete a task.
        
        Args:
            prompt: The task instruction for the agent
            file_url: URL of Excel file to convert (use this OR file_bytes)
            file_bytes: Base64-encoded Excel file bytes (use this OR file_url)
            sheet_name: Name for the created sheet
            expected_cells: Optional dict of cell references to expected values
            expected_text: Optional text that should appear in the sheet
        """
        from env import persistent_ctx
        playwright_tool = persistent_ctx.playwright_tool if persistent_ctx else None

        if not playwright_tool:
            yield 0.0
            return

        # Setup: Create sheet from file
        if file_url:
            result = await sheets_from_xlsx(playwright_tool, file_url, sheet_name)
        elif file_bytes:
            result = await sheets_from_bytes(playwright_tool, file_bytes, sheet_name)
        else:
            logger.error("No file_url or file_bytes provided")
            yield 0.0
            return

        if not result.get("success"):
            logger.error("Failed to create sheet: %s", result.get("error"))
            yield 0.0
            return

        _ = yield prompt

        # Evaluate
        reward = 1.0

        if expected_cells:
            cell_result = await sheets_cell_values(playwright_tool, expected_cells)
            reward = min(reward, cell_result["reward"])

        if expected_text:
            text_list = [expected_text] if isinstance(expected_text, str) else expected_text
            text_result = await sheet_contains(playwright_tool, text_list)
            reward = min(reward, text_result["reward"])

        yield reward
