"""Google Sheets setup helpers for remote browser environment."""

import base64
import io
import json
import logging
import os
from typing import Any, Dict, Optional

import httpx
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

logger = logging.getLogger(__name__)


async def navigate_to_google_sheet(page: Any, sheet_url: str, max_attempts: int = 3) -> bool:
    """Navigate to a Google Sheet with retry logic and loading issue handling.

    Args:
        page: Playwright page object
        sheet_url: URL of the Google Sheet
        max_attempts: Maximum number of navigation attempts

    Returns:
        True if navigation was successful, False otherwise
    """
    for attempt in range(max_attempts):
        try:
            if attempt > 0:
                logger.info("Retrying navigation (attempt %d/%d)", attempt + 1, max_attempts)

            await page.goto(sheet_url, wait_until="load", timeout=45000)

            try:
                await page.wait_for_selector(".grid-container", timeout=20000)
                logger.info("Sheet loaded successfully")

                await page.wait_for_timeout(2000)

                if await page.locator('text="Loading issue"').is_visible(timeout=1000):
                    logger.warning("Loading issue popup detected, reloading page")
                    await page.reload(wait_until="networkidle", timeout=30000)
                    await page.wait_for_selector(".grid-container", timeout=20000)
                    logger.info("Sheet reloaded successfully")

                return True

            except Exception:
                if attempt < max_attempts - 1:
                    logger.warning("Timeout waiting for sheet to load, will retry with refresh")
                    await page.reload(timeout=30000)
                else:
                    logger.warning("Timeout waiting for sheet to fully load after all attempts")
                    return False

        except Exception as e:
            if attempt < max_attempts - 1:
                logger.warning("Navigation failed: %s, retrying...", str(e))
                await page.wait_for_timeout(2000)
            else:
                logger.error("Navigation failed after all attempts: %s", str(e))
                raise

    return False


def get_gcp_credentials() -> Dict[str, str]:
    """Get GCP credentials from environment variable.

    Expects one of:
    1. GCP_CREDENTIALS_JSON - A JSON string or base64-encoded JSON
    2. GCP_CREDENTIALS_BASE64 - Base64 encoded JSON
    3. GCP_CREDENTIALS_FILE - Path to a JSON file
    4. Individual environment variables for each field (GCP_PROJECT_ID, etc.)

    Returns:
        Dict containing GCP service account credentials
    """
    creds_json = os.getenv("GCP_CREDENTIALS_JSON")
    if creds_json:
        if not creds_json.startswith("{") and " " not in creds_json[:100]:
            try:
                creds_json = base64.b64decode(creds_json).decode("utf-8")
                logger.info("Detected and decoded base64-encoded GCP credentials")
            except Exception as e:
                logger.debug("Not base64 encoded: %s", e)

        try:
            return json.loads(creds_json)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse GCP_CREDENTIALS_JSON: %s", e)
            raise ValueError(
                "Invalid GCP_CREDENTIALS_JSON format. "
                "Use either: 1) Valid JSON, 2) Base64-encoded JSON, "
                "3) GCP_CREDENTIALS_BASE64 env var, or 4) Individual env vars"
            )

    creds_base64 = os.getenv("GCP_CREDENTIALS_BASE64")
    if creds_base64:
        try:
            decoded = base64.b64decode(creds_base64).decode("utf-8")
            return json.loads(decoded)
        except Exception as e:
            logger.error("Failed to decode GCP_CREDENTIALS_BASE64: %s", e)
            raise ValueError(f"Invalid GCP_CREDENTIALS_BASE64: {e}")

    creds_file = os.getenv("GCP_CREDENTIALS_FILE")
    if creds_file:
        try:
            with open(creds_file, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error("Failed to load GCP_CREDENTIALS_FILE from %s: %s", creds_file, e)
            raise ValueError(f"Could not load credentials from file {creds_file}: {e}")

    required_fields = [
        "type",
        "project_id",
        "private_key_id",
        "private_key",
        "client_email",
        "client_id",
        "auth_uri",
        "token_uri",
        "auth_provider_x509_cert_url",
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


async def sheets_from_xlsx(
    playwright_tool: Any,
    file_url: Optional[str] = None,
    sheet_name: str = "Worksheet"
) -> dict:
    """Create a Google Sheet from an Excel file URL.

    Args:
        playwright_tool: The PlaywrightToolWithMemory instance
        file_url: URL of the Excel file to convert
        sheet_name: Name for the new Google Sheet (default: "Worksheet")

    Returns:
        Result dict with sheet information
    """
    logger.info("Starting sheets_from_xlsx setup")

    if not file_url:
        logger.error("Missing required file_url parameter")
        return {"success": False, "error": "Missing required parameter: file_url"}

    logger.info("Downloading Excel file from: %s", file_url)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(file_url, follow_redirects=True, timeout=30.0)
            response.raise_for_status()
            file_bytes = response.content

            logger.info("Downloaded %d bytes", len(file_bytes))

            scopes = ["https://www.googleapis.com/auth/drive"]
            gcp_creds = get_gcp_credentials()
            credentials = Credentials.from_service_account_info(gcp_creds, scopes=scopes)
            drive_service = build("drive", "v3", credentials=credentials)

            file_metadata = {
                "name": sheet_name,
                "mimeType": "application/vnd.google-apps.spreadsheet",
            }

            media = MediaIoBaseUpload(
                io.BytesIO(file_bytes),
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                resumable=True,
            )

            logger.info("Uploading to Google Drive with conversion to Sheets")
            drive_file = (
                drive_service.files()
                .create(body=file_metadata, media_body=media, fields="id,webViewLink")
                .execute()
            )

            sheet_id = drive_file.get("id")
            sheet_url = drive_file.get("webViewLink")

            logger.info("Created Google Sheet: %s", sheet_id)

            permission = {"type": "anyone", "role": "writer", "allowFileDiscovery": False}
            drive_service.permissions().create(
                fileId=sheet_id, body=permission, fields="id"
            ).execute()

        logger.info("Set sharing permissions")

        if playwright_tool and hasattr(playwright_tool, "page") and playwright_tool.page:
            page = playwright_tool.page
            logger.info("Navigating to sheet: %s", sheet_url)
            await navigate_to_google_sheet(page, sheet_url, max_attempts=3)
        else:
            logger.warning("No playwright tool available for navigation")

        return {
            "success": True,
            "sheet_id": sheet_id,
            "sheet_url": sheet_url,
            "sheet_name": sheet_name,
        }

    except httpx.HTTPError as e:
        logger.error("HTTP error downloading file: %s", str(e))
        return {"success": False, "error": f"Failed to download Excel file: {str(e)}"}
    except Exception as e:
        logger.error("Error in sheets_from_xlsx: %s", str(e))
        return {"success": False, "error": f"Failed to create sheet: {str(e)}"}


async def sheets_from_bytes(
    playwright_tool: Any,
    base64_bytes: Optional[str] = None,
    sheet_name: str = "Worksheet"
) -> dict:
    """Create a Google Sheet from base64 encoded Excel bytes.

    Args:
        playwright_tool: The PlaywrightToolWithMemory instance
        base64_bytes: Base64 encoded Excel file bytes
        sheet_name: Name for the new Google Sheet (default: "Worksheet")

    Returns:
        Result dict with sheet information
    """
    logger.info("Starting sheets_from_bytes setup")

    if not base64_bytes:
        logger.error("Missing required base64_bytes parameter")
        return {"success": False, "error": "Missing required parameter: base64_bytes"}

    logger.info("Creating sheet from bytes, name: %s", sheet_name)

    try:
        file_bytes = base64.b64decode(base64_bytes)
        logger.info("Decoded %d bytes", len(file_bytes))

        scopes = ["https://www.googleapis.com/auth/drive"]
        gcp_creds = get_gcp_credentials()
        credentials = Credentials.from_service_account_info(gcp_creds, scopes=scopes)
        drive_service = build("drive", "v3", credentials=credentials)

        file_metadata = {
            "name": sheet_name,
            "mimeType": "application/vnd.google-apps.spreadsheet",
        }

        media = MediaIoBaseUpload(
            io.BytesIO(file_bytes),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            resumable=True,
        )

        logger.info("Uploading to Google Drive with conversion to Sheets")
        drive_file = (
            drive_service.files()
            .create(body=file_metadata, media_body=media, fields="id,webViewLink")
            .execute()
        )

        sheet_id = drive_file.get("id")
        sheet_url = drive_file.get("webViewLink")

        logger.info("Created Google Sheet: %s", sheet_id)

        permission = {"type": "anyone", "role": "writer", "allowFileDiscovery": False}
        drive_service.permissions().create(fileId=sheet_id, body=permission, fields="id").execute()

        logger.info("Set sharing permissions")

        if playwright_tool and hasattr(playwright_tool, "page") and playwright_tool.page:
            page = playwright_tool.page
            logger.info("Navigating to sheet: %s", sheet_url)
            await navigate_to_google_sheet(page, sheet_url, max_attempts=2)
        else:
            logger.warning("No playwright tool available for navigation")

        return {
            "success": True,
            "sheet_id": sheet_id,
            "sheet_url": sheet_url,
            "sheet_name": sheet_name,
        }

    except Exception as e:
        logger.error("Error in sheets_from_bytes: %s", str(e))
        return {"success": False, "error": f"Failed to create sheet: {str(e)}"}
