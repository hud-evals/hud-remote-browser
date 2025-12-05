"""FastAPI server for remote browser environment state management.

This replaces the old Unix socket-based context server with HTTP REST API.
Run with: uvicorn environment.server:app --reload
"""

import logging
import os
import sys
from datetime import datetime
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Add parent directory to path so we can import from server/providers
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from environment.context import RemoteBrowserContext

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(asctime)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# Global context instance
context = RemoteBrowserContext()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI app."""
    # Startup
    logger.info("Starting remote browser environment server")
    context.startup()
    yield
    # Shutdown
    logger.info("Shutting down remote browser environment server")
    if context.browser_provider and hasattr(context.browser_provider, "close"):
        try:
            context.browser_provider.close()
            logger.info("Browser provider closed")
        except Exception as e:
            logger.error(f"Error closing browser provider: {e}")


app = FastAPI(title="Remote Browser Environment", lifespan=lifespan)


# Request/Response models
class InitializeRequest(BaseModel):
    """Request model for browser initialization."""

    provider_name: str
    provider_config: Dict[str, Any]
    launch_options: Dict[str, Any] = {}


class InitializeResponse(BaseModel):
    """Response model for browser initialization."""

    cdp_url: str
    telemetry: Dict[str, Any]


class StateResponse(BaseModel):
    """Response model for state queries."""

    is_initialized: bool
    startup_complete: bool
    provider_name: Optional[str]
    has_cdp_url: bool
    has_browser_provider: bool


class TelemetryResponse(BaseModel):
    """Response model for telemetry queries."""

    provider: str
    status: str
    live_url: Optional[str]
    cdp_url: Optional[str]
    instance_id: Optional[str]
    timestamp: str


# Endpoints
@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/state", response_model=StateResponse)
async def get_state():
    """Get current state summary."""
    state = context.get_state_summary()
    return StateResponse(**state)


@app.get("/telemetry", response_model=TelemetryResponse)
async def get_telemetry():
    """Get telemetry data."""
    telemetry = context.get_telemetry()
    return TelemetryResponse(**telemetry)


@app.get("/cdp_url")
async def get_cdp_url():
    """Get CDP URL."""
    cdp_url = context.get_cdp_url()
    if not cdp_url:
        raise HTTPException(status_code=404, detail="CDP URL not available")
    return {"cdp_url": cdp_url}


@app.post("/initialize", response_model=InitializeResponse)
async def initialize(request: InitializeRequest):
    """Initialize browser provider and launch browser."""
    logger.info(f"Initializing browser with provider: {request.provider_name}")

    try:
        # Import provider dynamically (providers are in server/ package)
        from server.providers import get_provider

        # Store configuration
        context.provider_config = request.provider_config
        context.launch_options = request.launch_options

        # Initialize provider
        provider_class = get_provider(request.provider_name)
        browser_provider = provider_class(request.provider_config)
        context.browser_provider = browser_provider

        # Launch browser
        cdp_url = await browser_provider.launch(**request.launch_options)

        # Build and store telemetry
        telemetry_data = {
            "provider": request.provider_name,
            "status": "running",
            "live_url": browser_provider.get_live_view_url()
            if hasattr(browser_provider, "get_live_view_url")
            else None,
            "cdp_url": cdp_url,
            "instance_id": browser_provider._instance_id
            if hasattr(browser_provider, "_instance_id")
            else None,
            "timestamp": datetime.now().isoformat(),
        }
        context._telemetry = telemetry_data
        context.is_initialized = True

        logger.info(f"Browser initialized successfully. CDP URL: {cdp_url}")

        return InitializeResponse(cdp_url=cdp_url, telemetry=telemetry_data)

    except Exception as e:
        logger.error(f"Failed to initialize browser: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/shutdown")
async def shutdown():
    """Shutdown browser provider."""
    logger.info("Shutting down browser provider")

    try:
        if context.browser_provider and hasattr(context.browser_provider, "close"):
            context.browser_provider.close()
            logger.info("Browser provider closed")

        # Reset state
        context.browser_provider = None
        context.is_initialized = False
        context._telemetry = None

        return {"status": "shutdown_complete"}

    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
