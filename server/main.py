"""MCP server for remote browser environment.

This version uses HTTP to communicate with the environment server.
"""

import sys
import logging
import os
import asyncio
from datetime import datetime
from typing import Optional, TypedDict, Any

import httpx

# Configure stderr logging
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="[%(levelname)s] %(asctime)s | %(name)s | %(message)s",
    force=True,
)
logger = logging.getLogger(__name__)

from hud.server import MCPServer

# Import tools
from .tools import PlaywrightToolWithMemory, BrowserExecutor
from hud.tools.computer import (
    AnthropicComputerTool,
    OpenAIComputerTool,
    HudComputerTool,
)

# Import setup and evaluate hubs
from .setup import setup as setup_hub
from .evaluate import evaluate as evaluate_hub

# Import providers (for initialization)
from .providers import get_provider

# Global HTTP client for communicating with environment server
http_client: Optional[httpx.AsyncClient] = None
playwright_tool: Optional[PlaywrightToolWithMemory] = None
browser_executor: Optional[BrowserExecutor] = None

# Environment server URL
ENV_SERVER_URL = os.getenv("ENV_SERVER_URL", "http://localhost:8000")

# Create Hud FastMCP instance
mcp = MCPServer(
    name="HUD Remote Browser Environment",
    instructions="""
    This is a remote browser automation environment that connects to cloud browser providers.
    The browser provider is configured via the BROWSER_PROVIDER environment variable.

    Available tools:
    - setup: Initialize browser environment with various setup functions
    - evaluate: Evaluate browser state with various evaluator functions
    - playwright tools: Browser automation (navigate, click, type, etc.)
    - computer tools: Control browser as if it were a desktop application
    """,
)


class Telemetry(TypedDict):
    """Standard evaluation result format."""

    provider: str
    status: str
    live_url: str | None
    timestamp: str
    cdp_url: str | None
    instance_id: str | None


@mcp.resource("telemetry://live")
async def get_telemetry_resource() -> Telemetry:
    """MCP resource containing telemetry data including provider's live view URL."""
    global http_client

    if http_client:
        try:
            response = await http_client.get("/telemetry")
            response.raise_for_status()
            telemetry = response.json()
            return Telemetry(
                provider=telemetry["provider"],
                status=telemetry["status"],
                live_url=telemetry["live_url"],
                timestamp=datetime.now().isoformat(),
                cdp_url=telemetry.get("cdp_url"),
                instance_id=telemetry.get("instance_id"),
            )
        except Exception as e:
            logger.error(f"Error getting telemetry data: {e}")
            return Telemetry(
                provider=os.getenv("BROWSER_PROVIDER", "unknown"),
                status="error",
                live_url=None,
                timestamp=datetime.now().isoformat(),
                cdp_url=None,
                instance_id=None,
            )

    return Telemetry(
        provider=os.getenv("BROWSER_PROVIDER", "unknown"),
        status="not_initialized",
        live_url=None,
        timestamp=datetime.now().isoformat(),
        cdp_url=None,
        instance_id=None,
    )


@mcp.initialize
async def initialize_environment(ctx):
    """Initialize the remote browser environment with progress reporting."""
    global http_client, playwright_tool, browser_executor

    # Extract progress token from context if available
    progress_token = None
    if ctx.meta and hasattr(ctx.meta, "progressToken"):
        progress_token = ctx.meta.progressToken

    async def send_progress(progress: int, message: str):
        if progress_token and hasattr(ctx, "session"):
            try:
                await ctx.session.send_progress_notification(
                    progress_token=progress_token,
                    progress=progress,
                    total=100,
                    message=message,
                )
            except Exception as e:
                logger.warning(f"Failed to send progress notification: {e}")
        logger.info(f"[{progress}%] {message}")

    try:
        await send_progress(5, "Connecting to environment server...")

        # Connect to environment server via HTTP
        http_client = httpx.AsyncClient(base_url=ENV_SERVER_URL, timeout=30.0)

        # Wait for environment server to be ready
        max_retries = 10
        retry_delay = 1.0

        for attempt in range(max_retries):
            try:
                response = await http_client.get("/health")
                response.raise_for_status()
                logger.info("Connected to environment server")
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Environment server not ready yet (attempt {attempt + 1}/{max_retries}): {e}"
                    )
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error(
                        f"Failed to connect to environment server after {max_retries} attempts: {e}"
                    )
                    raise

        await send_progress(10, "Connected to environment server")

        # Check if environment is already initialized
        response = await http_client.get("/state")
        response.raise_for_status()
        state = response.json()

        if not state["is_initialized"]:
            await send_progress(15, "Initializing new browser session...")

            # Get provider configuration from environment
            provider_name = os.getenv("BROWSER_PROVIDER")
            if not provider_name:
                error_msg = (
                    "BROWSER_PROVIDER environment variable is required. "
                    "Supported providers: anchorbrowser, steel, browserbase, hyperbrowser, kernel"
                )
                logger.error(error_msg)
                raise ValueError(error_msg)

            provider_name = provider_name.lower()
            await send_progress(20, f"Using browser provider: {provider_name}")

            # Build provider config
            provider_config = {}

            if provider_name == "anchorbrowser":
                provider_config["api_key"] = os.getenv("ANCHOR_API_KEY")
                provider_config["base_url"] = os.getenv(
                    "ANCHOR_BASE_URL", "https://api.anchorbrowser.io"
                )
            elif provider_name == "steel":
                provider_config["api_key"] = os.getenv("STEEL_API_KEY")
                provider_config["base_url"] = os.getenv("STEEL_BASE_URL", "https://api.steel.dev")
            elif provider_name == "browserbase":
                provider_config["api_key"] = os.getenv("BROWSERBASE_API_KEY")
                provider_config["project_id"] = os.getenv("BROWSERBASE_PROJECT_ID")
            elif provider_name == "hyperbrowser":
                provider_config["api_key"] = os.getenv("HYPERBROWSER_API_KEY")
            elif provider_name == "kernel":
                provider_config["api_key"] = os.getenv("KERNEL_API_KEY")

            # Build launch options
            launch_options = {}
            max_duration = os.getenv("BROWSER_MAX_DURATION")
            if max_duration:
                launch_options["max_duration"] = int(max_duration)
            idle_timeout = os.getenv("BROWSER_IDLE_TIMEOUT")
            if idle_timeout:
                launch_options["idle_timeout"] = int(idle_timeout)

            # Initialize browser via HTTP
            await send_progress(40, "Launching remote browser...")
            init_response = await http_client.post(
                "/initialize",
                json={
                    "provider_name": provider_name,
                    "provider_config": provider_config,
                    "launch_options": launch_options,
                },
            )
            init_response.raise_for_status()
            init_data = init_response.json()
            cdp_url = init_data["cdp_url"]

            await send_progress(60, "Browser launched")
        else:
            # Reuse existing browser session
            await send_progress(20, "Reusing existing browser session...")

            # Get existing CDP URL from environment
            response = await http_client.get("/cdp_url")
            response.raise_for_status()
            cdp_url = response.json()["cdp_url"]

            await send_progress(60, "Using existing CDP URL")

        # Initialize PlaywrightToolWithMemory with CDP URL
        playwright_tool = PlaywrightToolWithMemory(context=None, cdp_url=cdp_url)

        # Ensure browser is connected before registering tools
        await playwright_tool._ensure_browser()
        await send_progress(65, "Browser connection established")

        # Add playwright tool to MCP
        mcp.add_tool(playwright_tool)
        await send_progress(70, "Playwright tool registered")

        # Initialize browser executor
        browser_executor = BrowserExecutor(playwright_tool)
        await send_progress(75, "Browser executor initialized")

        # Create and register computer tools
        mcp.add_tool(HudComputerTool(executor=browser_executor))
        mcp.add_tool(AnthropicComputerTool(executor=browser_executor))
        mcp.add_tool(OpenAIComputerTool(executor=browser_executor))

        await send_progress(80, "Registered hud computer tools")

        # Set the HTTP client as environment for setup and evaluate hubs
        setup_hub.env = http_client
        evaluate_hub.env = http_client

        # Also store playwright tool for direct access (for setup/evaluate)
        setup_hub.playwright_tool = playwright_tool
        evaluate_hub.playwright_tool = playwright_tool

        # Mount the hubs
        mcp.mount(setup_hub)
        mcp.mount(evaluate_hub)
        await send_progress(90, "Setup and evaluate tools registered")

        # Navigate to initial URL if specified (only for new sessions)
        if not state["is_initialized"]:
            initial_url = os.getenv("BROWSER_URL")
            if initial_url:
                await send_progress(95, f"Navigating to {initial_url}")
                await playwright_tool.navigate(initial_url)

        await send_progress(100, "Remote browser environment ready!")

    except Exception as e:
        logger.error(f"Initialization failed: {e}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")
        raise


@mcp.shutdown
async def shutdown_environment():
    """Shutdown the remote browser environment (only called on SIGTERM)."""
    global http_client, playwright_tool, browser_executor

    logger.info("🔧 SIGTERM received - shutting down browser environment")
    try:
        # Close the browser provider via HTTP
        if http_client:
            logger.info("Requesting browser shutdown...")
            try:
                response = await http_client.post("/shutdown")
                response.raise_for_status()
                logger.info("Browser provider closed")
            except Exception as e:
                logger.error(f"Error closing provider: {e}")
            finally:
                await http_client.aclose()

        logger.info("✅ Browser shutdown completed")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
    finally:
        # Clear local references
        playwright_tool = None
        browser_executor = None
        http_client = None


if __name__ == "__main__":
    mcp.run()
