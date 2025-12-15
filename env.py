"""Remote Browser Environment - Cloud browser automation with multiple providers.

This demonstrates:
- Multiple cloud browser providers (Browserbase, Steel, Hyperbrowser, etc.)
- Persistent context for browser session management
- @env.scenario() for web automation evaluation flows
"""
import asyncio
import logging
import os
import sys
from datetime import datetime
from typing import Any, Optional, TypedDict

from hud import Environment
from hud.server.context import attach_context

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="[%(levelname)s] %(asctime)s | %(name)s | %(message)s",
    force=True,
)
logger = logging.getLogger(__name__)

# Global state
persistent_ctx = None
playwright_tool = None
browser_executor = None

# Create Environment instance
env = Environment(name="remote-browser")


class Telemetry(TypedDict):
    """Standard telemetry format."""
    provider: str
    status: str
    live_url: str | None
    timestamp: str
    cdp_url: str | None
    instance_id: str | None


@env.resource("telemetry://live")
async def get_telemetry_resource() -> Telemetry:
    """MCP resource containing telemetry data including provider's live view URL."""
    global persistent_ctx

    if persistent_ctx:
        try:
            telemetry = persistent_ctx.get_telemetry()
            return Telemetry(
                provider=telemetry["provider"],
                status=telemetry["status"],
                live_url=telemetry["live_url"],
                timestamp=datetime.now().isoformat(),
                cdp_url=None,
                instance_id=telemetry["instance_id"],
            )
        except Exception as e:
            logger.error("Error getting telemetry data: %s", e)

    return Telemetry(
        provider=os.getenv("BROWSER_PROVIDER", "unknown"),
        status="not_initialized",
        live_url=None,
        timestamp=datetime.now().isoformat(),
        cdp_url=None,
        instance_id=None,
    )


@env.initialize
async def initialize_environment(ctx: Any) -> None:
    """Initialize the remote browser environment."""
    global persistent_ctx, playwright_tool, browser_executor

    from tools.browser import PlaywrightToolWithMemory, BrowserExecutor
    from tools.computer import register_computer_tools
    from providers import get_provider

    try:
        logger.info("Connecting to persistent context...")

        # Connect to persistent context server
        max_retries = 10
        retry_delay = 1.0

        for attempt in range(max_retries):
            try:
                persistent_ctx = attach_context("/tmp/hud_remote_browser_ctx.sock")
                if persistent_ctx is None:
                    raise ConnectionError("Failed to attach to context server")
                logger.info("Connected to persistent remote browser context")
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning("Context server not ready (attempt %d/%d): %s", attempt + 1, max_retries, e)
                    await asyncio.sleep(retry_delay)
                else:
                    raise

        # Check if we need to initialize a new browser session
        if not persistent_ctx.get_is_initialized():
            logger.info("Initializing new browser session...")

            # Detect provider from API keys or explicit setting
            provider_name = _detect_provider()
            logger.info("Using browser provider: %s", provider_name)

            # Initialize provider
            provider_class = get_provider(provider_name)
            provider_config = _get_provider_config(provider_name)
            
            persistent_ctx.set_provider_config(provider_config)
            browser_provider = provider_class(provider_config)
            persistent_ctx.set_browser_provider(browser_provider)

            # Launch browser
            launch_options = {}
            if os.getenv("BROWSER_MAX_DURATION"):
                launch_options["max_duration"] = int(os.getenv("BROWSER_MAX_DURATION"))
            if os.getenv("BROWSER_IDLE_TIMEOUT"):
                launch_options["idle_timeout"] = int(os.getenv("BROWSER_IDLE_TIMEOUT"))

            persistent_ctx.set_launch_options(launch_options)
            cdp_url = await browser_provider.launch(**launch_options)

            # Store telemetry
            telemetry_data = {
                "provider": provider_name,
                "status": "running",
                "live_url": browser_provider.get_live_view_url() if hasattr(browser_provider, "get_live_view_url") else None,
                "cdp_url": cdp_url,
                "instance_id": browser_provider._instance_id if hasattr(browser_provider, "_instance_id") else None,
                "timestamp": datetime.now().isoformat(),
            }
            persistent_ctx.set_telemetry(telemetry_data)
            logger.info("Browser launched")
        else:
            logger.info("Reusing existing browser session...")
            cdp_url = persistent_ctx.get_cdp_url()
            if not cdp_url:
                raise ValueError("No CDP URL in persistent context")

        # Initialize playwright tool
        playwright_tool = PlaywrightToolWithMemory(context=None, cdp_url=cdp_url)
        await playwright_tool._ensure_browser()
        logger.info("Playwright connected")

        # Register tools
        env.add_tool(playwright_tool)
        
        browser_executor = BrowserExecutor(playwright_tool)
        register_computer_tools(env, browser_executor)
        logger.info("Tools registered")

        # Store playwright tool on context for scenarios
        persistent_ctx.playwright_tool = playwright_tool

        # Navigate to initial URL if specified
        if not persistent_ctx.get_is_initialized():
            initial_url = os.getenv("BROWSER_URL")
            if initial_url:
                await playwright_tool.navigate(initial_url)
            persistent_ctx.set_initialized(True)

        logger.info("Remote browser environment ready!")

    except Exception as e:
        logger.error("Initialization failed: %s", e)
        import traceback
        logger.error("Traceback: %s", traceback.format_exc())
        raise


# Mapping of API key env vars to provider names
PROVIDER_API_KEYS = {
    "ANCHOR_API_KEY": "anchorbrowser",
    "STEEL_API_KEY": "steel",
    "BROWSERBASE_API_KEY": "browserbase",
    "HYPERBROWSER_API_KEY": "hyperbrowser",
    "KERNEL_API_KEY": "kernel",
}


def _detect_provider() -> str:
    """Detect provider from BROWSER_PROVIDER or auto-detect from API keys."""
    explicit = os.getenv("BROWSER_PROVIDER", "").lower()
    if explicit:
        return explicit
    
    available = [p for k, p in PROVIDER_API_KEYS.items() if os.getenv(k)]
    
    if len(available) == 1:
        logger.info("Auto-detected provider: %s", available[0])
        return available[0]
    elif len(available) > 1:
        raise ValueError(f"Multiple API keys set ({', '.join(available)}). Set BROWSER_PROVIDER.")
    else:
        raise ValueError(f"No API key set. Provide one of: {', '.join(PROVIDER_API_KEYS.keys())}")


def _get_provider_config(provider_name: str) -> dict:
    """Get provider-specific configuration from environment."""
    config = {}
    
    if provider_name == "anchorbrowser":
        config["api_key"] = os.getenv("ANCHOR_API_KEY")
        config["base_url"] = os.getenv("ANCHOR_BASE_URL", "https://api.anchorbrowser.io")
    elif provider_name == "steel":
        config["api_key"] = os.getenv("STEEL_API_KEY")
        config["base_url"] = os.getenv("STEEL_BASE_URL", "https://api.steel.dev")
    elif provider_name == "browserbase":
        config["api_key"] = os.getenv("BROWSERBASE_API_KEY")
        config["project_id"] = os.getenv("BROWSERBASE_PROJECT_ID")
    elif provider_name == "hyperbrowser":
        config["api_key"] = os.getenv("HYPERBROWSER_API_KEY")
    elif provider_name == "kernel":
        config["api_key"] = os.getenv("KERNEL_API_KEY")
    
    return config


@env.shutdown
async def shutdown_environment() -> None:
    """Shutdown the remote browser environment."""
    global persistent_ctx, playwright_tool, browser_executor

    logger.info("Shutting down browser provider...")
    try:
        if persistent_ctx:
            provider = persistent_ctx.get_browser_provider()
            if provider and hasattr(provider, "close"):
                provider.close()
                logger.info("Browser provider closed")
    except Exception as e:
        logger.error("Error during shutdown: %s", e)
    finally:
        playwright_tool = None
        browser_executor = None


# Include tool routers
from tools.browser import router as browser_router
env.include_router(browser_router)

# Register scenarios
from scenarios import register_scenarios
register_scenarios(env)


if __name__ == "__main__":
    env.run(transport="stdio")
