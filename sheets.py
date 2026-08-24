"""Google Sheets helpers: create a sheet from an Excel file, and grade it from the live page.

Grading reads the sheet through the browser clipboard (select-all, copy, read) rather than the
Sheets API, so it sees exactly the state the agent left behind.
"""

import asyncio
import base64
import io
import json
import logging
import os
from typing import Any

import httpx
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

logger = logging.getLogger(__name__)

_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def get_gcp_credentials() -> dict:
    """Load GCP service-account credentials from the environment.

    Accepts GCP_CREDENTIALS_JSON (raw or base64), GCP_CREDENTIALS_BASE64, GCP_CREDENTIALS_FILE,
    or the individual GCP_* field variables.
    """
    creds_json = os.getenv("GCP_CREDENTIALS_JSON")
    if creds_json:
        if not creds_json.startswith("{") and " " not in creds_json[:100]:
            try:
                creds_json = base64.b64decode(creds_json).decode("utf-8")
            except Exception:
                pass
        try:
            return json.loads(creds_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid GCP_CREDENTIALS_JSON: {e}") from e

    creds_base64 = os.getenv("GCP_CREDENTIALS_BASE64")
    if creds_base64:
        try:
            return json.loads(base64.b64decode(creds_base64).decode("utf-8"))
        except Exception as e:
            raise ValueError(f"Invalid GCP_CREDENTIALS_BASE64: {e}") from e

    creds_file = os.getenv("GCP_CREDENTIALS_FILE")
    if creds_file:
        with open(creds_file) as f:
            return json.load(f)

    required_fields = [
        "type", "project_id", "private_key_id", "private_key", "client_email",
        "client_id", "auth_uri", "token_uri", "auth_provider_x509_cert_url",
        "client_x509_cert_url",
    ]
    credentials = {}
    for field in required_fields:
        env_key = f"GCP_{field.upper()}"
        value = os.getenv(env_key)
        if not value:
            raise ValueError(f"Missing required GCP credential field: {env_key}")
        credentials[field] = value
    credentials["universe_domain"] = os.getenv("GCP_UNIVERSE_DOMAIN", "googleapis.com")
    return credentials


async def create_sheet(
    file_url: str = "", file_bytes: str = "", name: str = "Worksheet"
) -> dict:
    """Create a world-writable Google Sheet from an xlsx URL or base64 bytes.

    Returns {"sheet_id", "sheet_url", "sheet_name"}.
    """
    if file_url:
        async with httpx.AsyncClient() as client:
            response = await client.get(file_url, follow_redirects=True, timeout=30.0)
            response.raise_for_status()
            raw = response.content
        logger.info("Downloaded %d bytes from %s", len(raw), file_url)
    elif file_bytes:
        raw = base64.b64decode(file_bytes)
        logger.info("Decoded %d bytes", len(raw))
    else:
        raise ValueError("Provide file_url or file_bytes")

    credentials = Credentials.from_service_account_info(
        get_gcp_credentials(), scopes=["https://www.googleapis.com/auth/drive"]
    )
    drive_service = build("drive", "v3", credentials=credentials)

    file_metadata = {"name": name, "mimeType": "application/vnd.google-apps.spreadsheet"}
    media = MediaIoBaseUpload(io.BytesIO(raw), mimetype=_XLSX_MIME, resumable=True)
    drive_file = (
        drive_service.files()
        .create(body=file_metadata, media_body=media, fields="id,webViewLink")
        .execute()
    )
    sheet_id = drive_file["id"]
    sheet_url = drive_file["webViewLink"]
    logger.info("Created Google Sheet %s", sheet_id)

    permission = {"type": "anyone", "role": "writer", "allowFileDiscovery": False}
    drive_service.permissions().create(fileId=sheet_id, body=permission, fields="id").execute()

    return {"sheet_id": sheet_id, "sheet_url": sheet_url, "sheet_name": name}


async def navigate_to_sheet(page: Any, sheet_url: str, max_attempts: int = 3) -> bool:
    """Navigate to a Google Sheet, retrying through slow loads and the 'Loading issue' popup."""
    for attempt in range(max_attempts):
        try:
            await page.goto(sheet_url, wait_until="load", timeout=45000)
            try:
                await page.wait_for_selector(".grid-container", timeout=20000)
                await page.wait_for_timeout(2000)
                if await page.locator('text="Loading issue"').is_visible(timeout=1000):
                    logger.warning("Loading issue popup detected, reloading page")
                    await page.reload(wait_until="networkidle", timeout=30000)
                    await page.wait_for_selector(".grid-container", timeout=20000)
                return True
            except Exception:
                if attempt < max_attempts - 1:
                    logger.warning("Timeout waiting for sheet to load, retrying with refresh")
                    await page.reload(timeout=30000)
                else:
                    logger.warning("Sheet never fully loaded after %d attempts", max_attempts)
                    return False
        except Exception as e:
            if attempt < max_attempts - 1:
                logger.warning("Navigation failed: %s, retrying", e)
                await page.wait_for_timeout(2000)
            else:
                logger.error("Navigation failed after all attempts: %s", e)
                raise
    return False


# ── cell references ──────────────────────────────────────────────────────────
def column_to_index(col_str: str) -> int:
    """Column letters to 0-indexed column number: A -> 0, Z -> 25, AA -> 26."""
    result = 0
    for char in col_str.upper():
        result = result * 26 + (ord(char) - ord("A") + 1)
    return result - 1


def parse_cell_reference(cell_ref: str) -> tuple | None:
    """Parse 'A1' / 'AA123' into (col_letters, row_0indexed, col_0indexed); None if invalid."""
    col_letters = ""
    row_digits = ""
    for i, char in enumerate(cell_ref):
        if char.isalpha():
            col_letters += char.upper()
        elif char.isdigit():
            row_digits = cell_ref[i:]
            break
        else:
            return None
    if not col_letters or not row_digits or not row_digits.isdigit():
        return None
    return (col_letters, int(row_digits) - 1, column_to_index(col_letters))


# ── grading from the live page ───────────────────────────────────────────────
async def _read_grid(page: Any) -> str:
    """Select-all + copy the current sheet tab and return the clipboard TSV text."""
    try:
        await page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    except Exception as e:
        logger.warning("Failed to grant clipboard permissions: %s", e)

    await page.keyboard.press("Escape")
    await page.locator("body").click(force=True)
    try:
        await page.click(".fixed4-inner-container")
    except Exception:
        pass
    await page.keyboard.press("Control+A")
    await asyncio.sleep(1)
    await page.keyboard.press("Control+C")
    await asyncio.sleep(1)
    content = await page.evaluate("() => navigator.clipboard.readText()")
    logger.info("Extracted %d characters from sheet", len(content))
    return content


async def _switch_to_answer_tab(page: Any, max_attempts: int = 3) -> bool:
    """Click the ANSWER sheet tab if present; grading falls back to the current tab if not."""
    selector = 'span.docs-sheet-tab-name:has-text("ANSWER")'
    for attempt in range(1, max_attempts + 1):
        try:
            if await page.locator(selector).count() > 0:
                await page.locator(selector).click()
                await page.wait_for_timeout(1000)
                logger.info("Switched to ANSWER tab")
                return True
            await page.wait_for_timeout(500)
        except Exception as e:
            logger.warning("ANSWER tab navigation attempt %d failed: %s", attempt, e)
            await page.wait_for_timeout(2500)
    logger.warning("ANSWER tab not found after %d attempts, grading current tab", max_attempts)
    return False


def grade_cells_in_grid(grid: str, expected_cells: dict) -> float:
    """Score expected cell values against TSV grid text — partial credit per matching cell."""
    if not expected_cells:
        return 1.0
    rows = grid.rstrip("\n").split("\n")
    matching = 0
    for cell_ref, expected_value in expected_cells.items():
        parsed = parse_cell_reference(cell_ref)
        if parsed is None:
            logger.error("Invalid cell reference: %s", cell_ref)
            continue
        _, row_num, col_num = parsed
        actual = ""
        if row_num < len(rows):
            cells = rows[row_num].split("\t")
            if col_num < len(cells):
                actual = cells[col_num]
        if str(actual).strip() == str(expected_value).strip():
            matching += 1
        else:
            logger.info(
                "Cell %s mismatch: expected '%s', got '%s'", cell_ref, expected_value, actual
            )
    logger.info("Cells matched: %d/%d", matching, len(expected_cells))
    return matching / len(expected_cells)


async def _graded_grid(page: Any) -> str | None:
    """Wait for the sheet grid, then read it; None if the page can't be read."""
    if "docs.google.com/spreadsheets" not in page.url:
        logger.error("Not on a Google Sheets page: %s", page.url)
        return None
    try:
        await page.wait_for_selector(".grid-container", timeout=20000)
        await page.wait_for_timeout(2000)
    except Exception as e:
        logger.warning("Timeout waiting for sheet to load: %s", e)
        await asyncio.sleep(5)
    try:
        return await _read_grid(page)
    except Exception as e:
        logger.error("Failed to read sheet content: %s", e)
        return None


async def grade_cells(page: Any, expected_cells: dict) -> float:
    """Check cell values on the sheet's ANSWER tab (or current tab) — partial credit."""
    if "docs.google.com/spreadsheets" not in page.url:
        logger.error("Not on a Google Sheets page: %s", page.url)
        return 0.0
    await _switch_to_answer_tab(page)
    grid = await _graded_grid(page)
    return grade_cells_in_grid(grid, expected_cells) if grid is not None else 0.0


async def grade_contains(page: Any, search_terms: list) -> float:
    """Check the sheet contains each term (case-insensitive) — partial credit per term."""
    if not search_terms:
        return 1.0
    grid = await _graded_grid(page)
    if not grid:
        logger.warning("Sheet content is empty or unreadable")
        return 0.0
    found = sum(1 for term in search_terms if str(term).lower() in grid.lower())
    logger.info("Terms found: %d/%d", found, len(search_terms))
    return found / len(search_terms)
