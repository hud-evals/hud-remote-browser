"""BrowserBase provider implementation."""

import os
import logging
from typing import Optional, Dict, Any
import httpx

from .base import BrowserProvider

logger = logging.getLogger(__name__)


class BrowserBaseProvider(BrowserProvider):
    """BrowserBase provider for remote browser control.

    BrowserBase provides cloud browser instances with features like:
    - Multiple regions support
    - Context persistence
    - Live view URLs
    - Session recordings
    - Proxy support

    API Documentation: https://docs.browserbase.com/reference/api/create-a-session
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        super().__init__(config)
        self.api_key = config.get("api_key") if config else os.getenv("BROWSERBASE_API_KEY")
        self.base_url = (
            config.get("base_url", "https://api.browserbase.com")
            if config
            else "https://api.browserbase.com"
        )
        self.project_id = (
            config.get("project_id") if config else os.getenv("BROWSERBASE_PROJECT_ID")
        )
        self._session_data: Dict[str, Any] | None = None

        if not self.api_key:
            raise ValueError("BrowserBase API key not provided")

    async def launch(self, **kwargs: Any) -> str:
        """Launch a BrowserBase instance.

        Args:
            **kwargs: Launch options including:
                - projectId: Project ID (required if not set in config)
                - region: Browser region (e.g., "us-west-2")
                - keepAlive: Keep session alive after disconnect
                - contextId: Reuse browser context
                - browserSettings: Additional browser settings
                - proxies: Enable proxy support
                - advancedStealth: Enable advanced stealth (Scale plan, allows custom viewports)
                - os: OS for advanced stealth ("windows", "mac", "linux")

        Returns:
            CDP URL for connecting to the browser
        """
        # Build request payload
        # See: https://docs.browserbase.com/fundamentals/create-browser-session
        request_data: Dict[str, Any] = {"projectId": kwargs.get("projectId", self.project_id)}

        # Start with browserSettings from kwargs if provided, or empty dict
        browser_settings = dict(kwargs.get("browserSettings", {}))

        # Advanced stealth mode (Scale plan) - enables custom viewports
        if kwargs.get("advancedStealth"):
            browser_settings["advancedStealth"] = True
            if "os" in kwargs:
                browser_settings["os"] = kwargs["os"]

        # Viewport configuration - sync with DISPLAY_WIDTH/HEIGHT to prevent coordinate drift
        # NOTE: Without advancedStealth, only specific viewport sizes are allowed:
        # Desktop: 1920x1080, 1366x768, 1536x864, 1280x720, 1024x768
        # With advancedStealth (Scale plan): Custom sizes allowed per OS
        # See: https://docs.browserbase.com/features/viewports
        if "viewport" in kwargs:
            browser_settings["viewport"] = kwargs["viewport"]
        elif "viewport" not in browser_settings:
            width = int(os.getenv("DISPLAY_WIDTH", "1280"))
            height = int(os.getenv("DISPLAY_HEIGHT", "720"))
            
            # If advancedStealth is enabled, use exact dimensions
            if browser_settings.get("advancedStealth"):
                browser_settings["viewport"] = {"width": width, "height": height}
                logger.info("Setting viewport to %sx%s (advancedStealth)", width, height)
            else:
                # Map to closest supported viewport for basic mode
                supported_viewports = [
                    (1920, 1080), (1536, 864), (1366, 768), (1280, 720), (1024, 768)
                ]
                closest = min(supported_viewports, key=lambda v: abs(v[0] - width) + abs(v[1] - height))
                browser_settings["viewport"] = {"width": closest[0], "height": closest[1]}
                if (closest[0], closest[1]) != (width, height):
                    logger.warning(
                        "BrowserBase: Requested %sx%s not supported without advancedStealth, using closest: %sx%s",
                        width, height, closest[0], closest[1]
                    )
                else:
                    logger.info("Setting viewport to %sx%s", closest[0], closest[1])

        if browser_settings:
            request_data["browserSettings"] = browser_settings

        # Add optional parameters
        if "region" in kwargs:
            request_data["region"] = kwargs["region"]

        if "keepAlive" in kwargs:
            request_data["keepAlive"] = kwargs["keepAlive"]

        if "contextId" in kwargs:
            request_data["contextId"] = kwargs["contextId"]

        if "proxies" in kwargs:
            request_data["proxies"] = kwargs["proxies"]

        # Ensure we have a project ID
        if not request_data.get("projectId"):
            raise ValueError("BrowserBase project ID not provided")

        # Make API request
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/v1/sessions",
                json=request_data,
                headers={"X-BB-API-Key": str(self.api_key), "Content-Type": "application/json"},
                timeout=30.0,
            )
            response.raise_for_status()

        # Extract session data
        data = response.json()
        self._session_data = data
        self._instance_id = data.get("id")

        if not self._instance_id:
            raise Exception("Failed to get session ID from BrowserBase response")

        # Get CDP URL - BrowserBase returns connectUrl directly
        self._cdp_url = data.get("connectUrl")
        if not self._cdp_url:
            raise Exception("Failed to get connect URL from BrowserBase response")

        self._is_running = True

        logger.info("Launched BrowserBase session: %s", self._instance_id)

        # Store selenium URL from create response
        self._selenium_remote_url = data.get("seleniumRemoteUrl")

        # Fetch live view URLs from debug endpoint
        # See: https://docs.browserbase.com/reference/api/session-live-urls
        try:
            async with httpx.AsyncClient() as debug_client:
                debug_response = await debug_client.get(
                    f"{self.base_url}/v1/sessions/{self._instance_id}/debug",
                    headers={"X-BB-API-Key": str(self.api_key)},
                    timeout=10.0,
                )
                if debug_response.status_code == 200:
                    debug_data = debug_response.json()
                    self._debugger_fullscreen_url = debug_data.get("debuggerFullscreenUrl")
                    self._debugger_url = debug_data.get("debuggerUrl")
                    self._live_view_url = self._debugger_fullscreen_url  # Use fullscreen as primary
                    self._ws_url = debug_data.get("wsUrl")
                    logger.info("Got BrowserBase live view URL")
                else:
                    logger.warning("Failed to get debug URLs: %s", debug_response.status_code)
                    self._live_view_url = None
                    self._debugger_fullscreen_url = None
                    self._debugger_url = None
        except Exception as e:
            logger.warning("Error fetching debug URLs: %s", e)
            self._live_view_url = None
            self._debugger_fullscreen_url = None
            self._debugger_url = None

        return self._cdp_url

    def close(self) -> None:
        """Terminate the BrowserBase session."""
        if not self._instance_id:
            return

        try:
            # BrowserBase sessions automatically close after disconnect unless keepAlive is true
            # Use PATCH to update session status (POST is not supported)
            with httpx.Client() as client:
                response = client.patch(
                    f"{self.base_url}/v1/sessions/{self._instance_id}",
                    json={"status": "REQUEST_RELEASE"},
                    headers={"X-BB-API-Key": str(self.api_key), "Content-Type": "application/json"},
                    timeout=30.0,
                )
                # BrowserBase may return 404 if session already ended, or other codes
                if response.status_code in (200, 201, 204, 404):
                    logger.info(f"Terminated BrowserBase session: {self._instance_id}")
                else:
                    # Log but don't raise - session will close automatically
                    logger.warning(f"BrowserBase close returned {response.status_code}")
        except Exception as e:
            # Sessions close automatically on disconnect, so this is not critical
            logger.debug(f"Note: BrowserBase session cleanup: {e}")
        finally:
            self._is_running = False
            self._cdp_url = None
            self._instance_id = None

    async def get_status(self) -> Dict[str, Any]:
        """Get status including BrowserBase-specific info."""
        status = await super().get_status()

        # Add BrowserBase-specific status
        if self._instance_id and self._is_running:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{self.base_url}/v1/sessions/{self._instance_id}",
                        headers={
                            "X-BB-API-Key": str(self.api_key),
                            "Content-Type": "application/json",
                        },
                        timeout=10.0,
                    )
                    if response.status_code == 200:
                        session_data = response.json()
                        status["session_data"] = session_data
                        status["status"] = session_data.get("status", "UNKNOWN")
                        status["region"] = session_data.get("region")
                        status["proxy_bytes"] = session_data.get("proxyBytes")
                        status["cpu_usage"] = session_data.get("avgCpuUsage")
                        status["memory_usage"] = session_data.get("memoryUsage")
            except Exception as e:
                logger.warning(f"Failed to get session status: {e}")

        return status

    def get_live_view_url(self) -> Optional[str]:
        """Get the fullscreen live view URL for the BrowserBase instance.
        
        This URL can be opened directly in a browser to view the session.
        Fetched from GET /v1/sessions/{id}/debug endpoint.
        """
        return self._debugger_fullscreen_url if hasattr(self, "_debugger_fullscreen_url") else None

    def get_debugger_url(self) -> Optional[str]:
        """Get the standard debugger URL (non-fullscreen)."""
        return self._debugger_url if hasattr(self, "_debugger_url") else None

    def get_selenium_remote_url(self) -> Optional[str]:
        """Get the Selenium remote URL for the BrowserBase instance."""
        return self._selenium_remote_url if hasattr(self, "_selenium_remote_url") else None
