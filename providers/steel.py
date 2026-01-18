"""Steel provider implementation."""

import os
import logging
from typing import Optional, Dict, Any
import httpx

from .base import BrowserProvider

logger = logging.getLogger(__name__)


class SteelProvider(BrowserProvider):
    """Steel provider for remote browser control.

    Steel is an open-source browser API that provides cloud browser instances with features like:
    - CAPTCHA solving
    - Proxy support
    - Session management
    - Context persistence (cookies, local storage)
    - Live view and recordings
    - Anti-detection measures
    - Up to 24-hour sessions

    API Documentation: https://docs.steel.dev/api-reference
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        super().__init__(config)
        self.api_key = config.get("api_key") if config else os.getenv("STEEL_API_KEY")
        self.base_url = (
            config.get("base_url", "https://api.steel.dev") if config else "https://api.steel.dev"
        )
        self._session_data: Dict[str, Any] | None = None

        if not self.api_key:
            raise ValueError("Steel API key not provided")

    async def launch(self, **kwargs: Any) -> str:
        """Launch a Steel browser instance.

        Args:
            **kwargs: Launch options including:
                - timeout: Session timeout in milliseconds (max 24 hours, default 30 min)
                - useProxy: Enable Steel's built-in proxy
                - proxyUrl: Custom proxy URL (user:pass@host:port)
                - blockAds: Block ads
                - solveCaptcha: Enable CAPTCHA solving
                - sessionContext: Saved context (cookies, localStorage)

        Returns:
            CDP WebSocket URL for connecting to the browser
        """
        # Build request payload - Steel API is minimal, only include what's needed
        # See: https://docs.steel.dev/overview/sessions-api/overview
        request_data: Dict[str, Any] = {}

        # Timeout (optional, in ms)
        if "timeout" in kwargs:
            request_data["timeout"] = kwargs["timeout"]

        # Proxy configuration
        if kwargs.get("useProxy"):
            request_data["useProxy"] = True
        if "proxyUrl" in kwargs and kwargs["proxyUrl"]:
            request_data["proxyUrl"] = kwargs["proxyUrl"]

        # Optional features
        if kwargs.get("blockAds"):
            request_data["blockAds"] = True
        if kwargs.get("solveCaptcha"):
            request_data["solveCaptcha"] = True

        # Dimensions - sync with DISPLAY_WIDTH/HEIGHT to prevent coordinate drift
        if "dimensions" in kwargs:
            request_data["dimensions"] = kwargs["dimensions"]
        else:
            width = int(os.getenv("DISPLAY_WIDTH", "1448"))
            height = int(os.getenv("DISPLAY_HEIGHT", "944"))
            request_data["dimensions"] = {"width": width, "height": height}
            logger.info("Setting dimensions to %sx%s", width, height)

        # Session context if provided
        if "sessionContext" in kwargs:
            request_data["sessionContext"] = kwargs["sessionContext"]

        # Make API request
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/v1/sessions",
                json=request_data,
                headers={"Content-Type": "application/json", "Steel-Api-Key": str(self.api_key)},
                timeout=30.0,
            )
            response.raise_for_status()

        # Extract session data
        data = response.json()
        self._session_data = data
        self._instance_id = data.get("id")

        if not self._instance_id:
            raise Exception("Failed to get session ID from Steel response")

        # Construct WebSocket URL - Steel does NOT return wsUrl in API response
        # Must construct it: wss://connect.steel.dev?apiKey=API_KEY&sessionId=SESSION_ID
        # See: https://docs.steel.dev/overview/guides
        self._cdp_url = f"wss://connect.steel.dev?apiKey={self.api_key}&sessionId={self._instance_id}"

        self._is_running = True

        logger.info("Launched Steel session: %s", self._instance_id)

        # Store additional URLs for reference
        # Steel may return sessionViewerUrl and/or debugUrl for live viewing
        # If not returned, construct from session ID
        # Format: https://app.steel.dev/sessions/{sessionId}/viewer
        self._debug_url = data.get("debugUrl")
        self._session_viewer_url = data.get("sessionViewerUrl") or data.get("session_viewer_url")
        
        # Construct live view URL if not provided
        # The viewer URL should work without authentication
        if self._debug_url:
            self._live_view_url = self._debug_url
        elif self._session_viewer_url:
            self._live_view_url = self._session_viewer_url
        else:
            # Construct the viewer URL from session ID
            self._live_view_url = f"https://app.steel.dev/sessions/{self._instance_id}/viewer"
            logger.info("Constructed live view URL from session ID")

        return self._cdp_url

    def close(self) -> None:
        """Terminate the Steel session."""
        if not self._instance_id:
            return

        try:
            with httpx.Client() as client:
                response = client.delete(
                    f"{self.base_url}/v1/sessions/{self._instance_id}",
                    headers={
                        "Content-Type": "application/json",
                        "Steel-Api-Key": str(self.api_key),
                    },
                    timeout=30.0,
                )
                # Steel may return 404 if session already ended
                if response.status_code != 404:
                    response.raise_for_status()

            logger.info(f"Terminated Steel session: {self._instance_id}")
        except Exception as e:
            logger.error(f"Error terminating session {self._instance_id}: {e}")
        finally:
            self._is_running = False
            self._cdp_url = None
            self._instance_id = None

    async def get_status(self) -> Dict[str, Any]:
        """Get status including Steel-specific info."""
        status = await super().get_status()

        # Add Steel-specific status
        if self._instance_id and self._is_running:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{self.base_url}/v1/sessions/{self._instance_id}",
                        headers={
                            "Steel-Api-Key": str(self.api_key),
                            "Content-Type": "application/json",
                        },
                        timeout=10.0,
                    )
                    if response.status_code == 200:
                        session_data = response.json()
                        status["session_data"] = session_data
                        status["status"] = session_data.get("status", "UNKNOWN")
                        status["context"] = session_data.get("context")
            except Exception as e:
                logger.warning(f"Failed to get session status: {e}")

        return status

    def get_debug_url(self) -> Optional[str]:
        """Get the debug URL for the Steel instance."""
        return self._debug_url if hasattr(self, "_debug_url") else None

    def get_live_view_url(self) -> Optional[str]:
        """Get the live view URL for the Steel instance."""
        return self._live_view_url if hasattr(self, "_live_view_url") else None

    async def save_context(self) -> Optional[Dict[str, Any]]:
        """Save the current browser context (cookies, localStorage).

        Returns:
            Context data that can be passed to launch() to restore state
        """
        if not self._instance_id:
            return None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/v1/sessions/{self._instance_id}/context",
                    headers={
                        "Content-Type": "application/json",
                        "Steel-Api-Key": str(self.api_key),
                    },
                    timeout=10.0,
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to save context: {e}")
            return None
