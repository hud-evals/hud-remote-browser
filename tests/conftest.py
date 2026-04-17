"""Shared fixtures for hud-remote-browser tests."""

import sys
from pathlib import Path

import pytest_asyncio
from dotenv import load_dotenv

# Add project root to sys.path so test files can import top-level modules
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load .env file from project root
load_dotenv(project_root / ".env")


@pytest_asyncio.fixture
async def playwright_tool():
    """
    Create a real PlaywrightToolWithMemory connected to a remote browser provider.

    Uses auto-detection from environment variables (ANCHOR_API_KEY, STEEL_API_KEY,
    BROWSERBASE_API_KEY, etc.) to select the provider.
    """
    from env import _detect_provider, _get_provider_config
    from providers import get_provider
    from tools.browser import PlaywrightToolWithMemory

    # Detect provider from environment
    provider_name = _detect_provider()

    # Get provider config and launch
    provider_config = _get_provider_config(provider_name)
    provider_class = get_provider(provider_name)
    provider = provider_class(provider_config)

    cdp_url = await provider.launch()

    # Create tool with real CDP connection
    tool = PlaywrightToolWithMemory(cdp_url=cdp_url)
    await tool._ensure_browser()

    yield tool

    # Cleanup
    await tool.close()
    provider.close()
