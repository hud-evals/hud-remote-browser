"""Remote browser context that holds browser provider state."""

import logging
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class RemoteBrowserContext:
    """Context that holds remote browser state."""

    def __init__(self):
        """Initialize the remote browser context."""
        self.browser_provider = None
        self.is_initialized = False
        self.provider_config: Optional[Dict[str, Any]] = None
        self.launch_options: Optional[Dict[str, Any]] = None
        self._startup_complete = False
        self._telemetry: Optional[Dict[str, Any]] = None

        logger.info("[RemoteBrowserContext] Created new remote browser context")

    def startup(self):
        """One-time startup when context server starts."""
        if self._startup_complete:
            logger.info("[RemoteBrowserContext] Startup already complete, skipping")
            return

        logger.info("[RemoteBrowserContext] Performing one-time startup")
        self._startup_complete = True

    def get_cdp_url(self) -> Optional[str]:
        """Get the CDP URL from telemetry."""
        return self._telemetry.get("cdp_url") if self._telemetry else None

    def get_state_summary(self) -> Dict[str, Any]:
        """Get a summary of the current state."""
        return {
            "is_initialized": self.is_initialized,
            "startup_complete": self._startup_complete,
            "provider_name": self._telemetry.get("provider") if self._telemetry else None,
            "has_cdp_url": self.get_cdp_url() is not None,
            "has_browser_provider": self.browser_provider is not None,
        }

    def get_telemetry(self) -> Dict[str, Any]:
        """Get telemetry data from the browser provider."""
        # If we have stored telemetry, return it
        if self._telemetry:
            return self._telemetry

        # Otherwise return basic telemetry data
        return {
            "provider": "unknown",
            "status": "not_initialized",
            "live_url": None,
            "cdp_url": None,
            "instance_id": None,
            "timestamp": datetime.now().isoformat(),
        }
