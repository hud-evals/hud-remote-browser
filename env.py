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

        # Get actual viewport from the browser and update DISPLAY_WIDTH/HEIGHT
        # This is critical because some providers (like BrowserBase) may adjust
        # the viewport to a supported size different from what was requested
        actual_viewport = await _get_actual_viewport(playwright_tool)
        if actual_viewport:
            actual_width, actual_height = actual_viewport
            requested_width = int(os.getenv("DISPLAY_WIDTH", "1280"))
            requested_height = int(os.getenv("DISPLAY_HEIGHT", "720"))
            
            if (actual_width, actual_height) != (requested_width, requested_height):
                logger.warning(
                    "Viewport mismatch! Requested %sx%s, actual %sx%s. Updating DISPLAY_* env vars.",
                    requested_width, requested_height, actual_width, actual_height
                )
                os.environ["DISPLAY_WIDTH"] = str(actual_width)
                os.environ["DISPLAY_HEIGHT"] = str(actual_height)
            else:
                logger.info("Viewport matches: %sx%s", actual_width, actual_height)

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


async def _get_actual_viewport(playwright_tool: Any) -> tuple[int, int] | None:
    """Get actual viewport size from the browser.
    
    This queries the browser's actual viewport dimensions, which may differ
    from what was requested if the provider adjusted it (e.g., BrowserBase
    only supports specific sizes without advancedStealth).
    
    Returns:
        (width, height) tuple or None if unable to determine
    """
    try:
        # After _ensure_browser() is called, playwright_tool.page should be available
        page = playwright_tool.page
        if not page:
            logger.warning("No page available to get viewport")
            return None
        
        # Try viewport_size first (Playwright's configured viewport)
        viewport = page.viewport_size
        if viewport:
            return (viewport["width"], viewport["height"])
        
        # Fallback: evaluate in browser to get actual window dimensions
        result = await page.evaluate("""
            () => ({
                width: window.innerWidth,
                height: window.innerHeight
            })
        """)
        return (result["width"], result["height"])
    except Exception as e:
        logger.warning("Failed to get actual viewport: %s", e)
        return None


# Provider detection priority (first available wins)
PROVIDER_PRIORITY = [
    ("ANCHOR_API_KEY", "anchorbrowser"),
    ("STEEL_API_KEY", "steel"),
    ("BROWSERBASE_API_KEY", "browserbase"),
    ("HYPERBROWSER_API_KEY", "hyperbrowser"),
    ("KERNEL_API_KEY", "kernel"),
]


def _detect_provider() -> str:
    """Detect provider from BROWSER_PROVIDER or auto-detect from API keys with priority."""
    explicit = os.getenv("BROWSER_PROVIDER", "").lower()
    if explicit:
        return explicit
    
    # Use priority order: first API key found wins
    for api_key_var, provider_name in PROVIDER_PRIORITY:
        if os.getenv(api_key_var):
            logger.info("Auto-detected provider: %s (from %s)", provider_name, api_key_var)
            return provider_name
    
    api_keys = [k for k, _ in PROVIDER_PRIORITY]
    raise ValueError(f"No API key set. Provide one of: {', '.join(api_keys)}")


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

    logger.info("Shutting down remote browser environment...")
    
    # Close playwright tool first (disconnects from browser)
    try:
        if playwright_tool and hasattr(playwright_tool, "close"):
            await playwright_tool.close()
            logger.info("Playwright tool closed")
    except Exception as e:
        logger.warning("Error closing playwright tool: %s", e)
    
    # Then close the browser provider (terminates session)
    try:
        if persistent_ctx:
            provider = persistent_ctx.get_browser_provider()
            if provider and hasattr(provider, "close"):
                provider.close()
                logger.info("Browser provider closed")
            persistent_ctx.set_initialized(False)
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
