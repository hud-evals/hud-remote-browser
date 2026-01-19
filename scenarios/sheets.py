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
            logger.error("No playwright tool available")
            # Must yield prompt first, then reward (scenario protocol)
            _ = yield "[ERROR] Environment setup failed: No playwright tool available. Please check environment configuration."
            yield 0.0
            return

        # Setup: Create sheet from file
        if file_url:
            result = await sheets_from_xlsx(playwright_tool, file_url, sheet_name)
        elif file_bytes:
            result = await sheets_from_bytes(playwright_tool, file_bytes, sheet_name)
        else:
            logger.error("No file_url or file_bytes provided")
            _ = yield "[ERROR] Environment setup failed: No file_url or file_bytes provided."
            yield 0.0
            return

        if not result.get("success"):
            error_msg = result.get("error", "Unknown error")
            logger.error("Failed to create sheet: %s", error_msg)
            _ = yield f"[ERROR] Environment setup failed: {error_msg}. Please check GCP credentials configuration."
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
