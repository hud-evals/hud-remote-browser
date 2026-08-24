"""Remote browser environment (HUD v6) — a cloud browser the agent drives over ``cdp``.

``@env.initialize`` launches a browser at a cloud provider (Anchor, Steel, Browserbase, or
Hyperbrowser — auto-detected from API keys) and publishes its DevTools endpoint as the ``cdp``
capability. The environment connects to the SAME browser with its own Playwright client, so task
templates can seed state (navigate, create a Google Sheet) before the prompt and grade from the
live page after — never from the agent's self-report.
"""

# NOTE: do NOT add `from __future__ import annotations` — under it a typed @env.template param
# crashes the sync/deploy manifest path (TypeAdapter on a string forward-ref).
import asyncio
import json
import logging
import os
import re
import sys
from typing import Any

from fastmcp import FastMCP
from fastmcp.utilities.types import Image
from hud import Environment
from hud.capabilities import Capability

import sheets
from providers import get_provider

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="[%(levelname)s] %(asctime)s | %(name)s | %(message)s",
    force=True,
)
logger = logging.getLogger(__name__)

env = Environment(name="remote-browser")

# ── provider detection ───────────────────────────────────────────────────────
PROVIDER_PRIORITY = [
    ("ANCHOR_API_KEY", "anchorbrowser"),
    ("STEEL_API_KEY", "steel"),
    ("BROWSERBASE_API_KEY", "browserbase"),
    ("HYPERBROWSER_API_KEY", "hyperbrowser"),
]


def _detect_provider() -> str | None:
    """Detect provider from BROWSER_PROVIDER or auto-detect from API keys with priority."""
    explicit = os.getenv("BROWSER_PROVIDER", "").lower()
    if explicit:
        return explicit
    for api_key_var, provider_name in PROVIDER_PRIORITY:
        if os.getenv(api_key_var):
            logger.info("Auto-detected provider: %s (from %s)", provider_name, api_key_var)
            return provider_name
    return None


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

    if not config.get("api_key"):
        key_var = next((k for k, v in PROVIDER_PRIORITY if v == provider_name), None)
        raise ValueError(
            f"Provider '{provider_name}' selected but no API key found. "
            f"Set the {key_var} environment variable."
        )
    return config


# ── browser lifecycle ────────────────────────────────────────────────────────
_MCP_PORT = 8040
_provider = None
_playwright = None
_browser = None
_server_task: "asyncio.Task | None" = None


async def _page() -> Any:
    """The environment's own page in the shared browser (for setup and grading)."""
    if _browser is None:
        raise RuntimeError("Browser not initialized")
    ctx = _browser.contexts[0] if _browser.contexts else await _browser.new_context()
    return ctx.pages[0] if ctx.pages else await ctx.new_page()


# ── browser tools (mcp capability) ───────────────────────────────────────────
# The cdp capability serves browser-native agents (browser-use). The stock tool
# agents (claude/openai/gemini) consume mcp capabilities, so the same browser is
# also published as computer-style tools driven by the env's Playwright client.
server = FastMCP(name="browser")


@server.tool
async def screenshot() -> Image:
    """Take a screenshot of the current page."""
    page = await _page()
    return Image(data=await page.screenshot(type="png"), format="png")


@server.tool
async def navigate(url: str) -> str:
    """Navigate the browser to a URL."""
    page = await _page()
    await page.goto(url, wait_until="load", timeout=45000)
    return f"Navigated to {page.url} (title: {await page.title()})"


@server.tool
async def click(x: int, y: int) -> str:
    """Click at pixel coordinates (x, y) on the page, as seen in the screenshot."""
    page = await _page()
    await page.mouse.click(x, y)
    return f"Clicked at ({x}, {y})"


@server.tool
async def type_text(text: str) -> str:
    """Type text at the current focus (click an input first)."""
    page = await _page()
    await page.keyboard.type(text)
    return f"Typed {len(text)} characters"


@server.tool
async def press(key: str) -> str:
    """Press a key or combination, e.g. 'Enter', 'Tab', 'Control+A'."""
    page = await _page()
    await page.keyboard.press(key)
    return f"Pressed {key}"


@server.tool
async def scroll(delta_y: int = 500) -> str:
    """Scroll the page vertically by delta_y pixels (negative scrolls up)."""
    page = await _page()
    await page.mouse.wheel(0, delta_y)
    return f"Scrolled by {delta_y}"


@env.initialize
async def _up() -> None:
    """Launch the provider browser, attach Playwright, and publish both capabilities."""
    global _provider, _playwright, _browser, _server_task
    from playwright.async_api import async_playwright

    provider_name = _detect_provider()
    if not provider_name:
        api_keys = [k for k, _ in PROVIDER_PRIORITY]
        raise ValueError(f"No API key set. Provide one of: {', '.join(api_keys)}")
    logger.info("Using browser provider: %s", provider_name)

    provider_class = get_provider(provider_name)
    _provider = provider_class(_get_provider_config(provider_name))

    launch_options = {}
    if os.getenv("BROWSER_MAX_DURATION"):
        launch_options["max_duration"] = int(os.environ["BROWSER_MAX_DURATION"])
    if os.getenv("BROWSER_IDLE_TIMEOUT"):
        launch_options["idle_timeout"] = int(os.environ["BROWSER_IDLE_TIMEOUT"])
    cdp_url = await _provider.launch(**launch_options)
    logger.info("Browser launched (cdp: %s)", cdp_url)

    _playwright = await async_playwright().start()
    _browser = await _playwright.chromium.connect_over_cdp(cdp_url)
    logger.info("Environment Playwright attached")

    if _server_task is None:
        _server_task = asyncio.create_task(
            server.run_async(transport="http", host="127.0.0.1", port=_MCP_PORT)
        )
        await asyncio.sleep(1.0)

    env.add_capability(Capability.cdp(name="browser", url=cdp_url))
    env.add_capability(Capability.mcp(name="tools", url=f"http://127.0.0.1:{_MCP_PORT}/mcp"))


@env.shutdown
async def _down() -> None:
    global _provider, _playwright, _browser, _server_task
    logger.info("Shutting down remote browser environment")
    if _server_task is not None:
        _server_task.cancel()
        _server_task = None
    if _browser is not None:
        try:
            await _browser.close()
        except Exception as e:
            logger.warning("Error closing Playwright browser: %s", e)
        _browser = None
    if _playwright is not None:
        try:
            await _playwright.stop()
        except Exception as e:
            logger.warning("Error stopping Playwright: %s", e)
        _playwright = None
    if _provider is not None:
        try:
            _provider.close()
        except Exception as e:
            logger.warning("Error closing browser provider: %s", e)
        _provider = None


async def _navigate(page: Any, url: str) -> None:
    """Point the shared browser at ``url`` so the agent starts on the right page. Best-effort:
    the prompt also names the URL, so if this fails the agent navigates there itself."""
    try:
        await page.goto(url, wait_until="load", timeout=45000)
    except Exception as e:
        logger.warning("pre-navigation to %s failed (agent will navigate): %s", url, e)


# ── answer comparison ────────────────────────────────────────────────────────
def compare_answers(actual: Any, expected: Any, mode: str = "exact") -> float:
    """Compare the agent's answer to the expected one; returns 0.0 or 1.0."""
    if actual is None:
        return 0.0

    actual_str = str(actual).strip()
    expected_str = str(expected).strip()

    if mode == "exact":
        return 1.0 if actual_str.lower() == expected_str.lower() else 0.0
    if mode == "contains":
        return 1.0 if expected_str.lower() in actual_str.lower() else 0.0
    if mode == "json":
        try:
            actual_json = json.loads(actual_str) if isinstance(actual, str) else actual
            expected_json = json.loads(expected_str) if isinstance(expected, str) else expected
            return 1.0 if actual_json == expected_json else 0.0
        except (json.JSONDecodeError, TypeError):
            return 0.0
    if mode == "numeric":
        try:
            clean_actual = re.sub(r"(?<=\d)[, ](?=\d)", "", actual_str)
            clean_expected = re.sub(r"(?<=\d)[, ](?=\d)", "", expected_str)
            actual_nums = re.findall(r"-?\d+\.?\d*", clean_actual)
            expected_nums = re.findall(r"-?\d+\.?\d*", clean_expected)
            if actual_nums and expected_nums:
                return 1.0 if float(actual_nums[-1]) == float(expected_nums[0]) else 0.0
            return 0.0
        except (ValueError, IndexError):
            return 0.0
    if mode == "regex":
        try:
            return 1.0 if re.search(expected_str, actual_str, re.IGNORECASE) else 0.0
        except re.error:
            return 0.0
    return 0.0


# ── general browsing tasks ───────────────────────────────────────────────────
@env.template(id="answer")
async def answer(url: str, prompt: str, expected: str = "", compare_mode: str = "exact"):
    """Browse from a URL and return an answer — compared against `expected` (binary)."""
    page = await _page()
    await _navigate(page, url)
    full_prompt = (
        f"Starting at: {url}\n\n{prompt}\n\n"
        f"When you have found the answer, respond with your final answer clearly."
    )
    agent_response = yield full_prompt
    if expected:
        reward = compare_answers(agent_response, expected, compare_mode)
        logger.info(
            "answer: expected='%s' got='%s' mode=%s reward=%.2f",
            expected, agent_response, compare_mode, reward,
        )
    else:
        reward = 1.0
    yield reward


@env.template(id="fill-record")
async def fill_record(
    url: str, prompt: str, fields: dict | None = None, verify: dict | None = None
):
    """Fill form fields; each selector in `verify` is checked — count-based partial credit."""
    page = await _page()
    await _navigate(page, url)
    if fields:
        fields_desc = "\n".join(f"- {k}: {v}" for k, v in fields.items())
        full_prompt = (
            f"You are on a page with form inputs.\n\n{prompt}\n\n"
            f"Fill in the following:\n{fields_desc}\n\n"
            f"Use the browser to locate and fill each field."
        )
    else:
        full_prompt = (
            f"You are on a page with form inputs.\n\n{prompt}\n\n"
            f"Use the browser to locate and fill the required fields."
        )
    _ = yield full_prompt

    if not verify:
        logger.warning("fill-record: no verify selectors provided, giving full credit")
        yield 1.0
        return

    matches = 0
    for selector, expected_value in verify.items():
        try:
            element = page.locator(selector).first
            if str(expected_value).strip().lower() == "checked":
                if await element.is_checked():
                    matches += 1
            else:
                actual_value = await element.input_value()
                if not actual_value:
                    actual_value = await element.text_content() or ""
                if str(actual_value).strip() == str(expected_value).strip():
                    matches += 1
        except Exception as e:
            logger.warning("fill-record: could not check selector %s: %s", selector, e)
    reward = matches / len(verify)
    logger.info("fill-record: %d/%d fields correct, reward=%.2f", matches, len(verify), reward)
    yield reward


@env.template(id="wiki-speedrun")
async def wiki_speedrun(start_page: str, target_page: str, max_clicks: int = 10):
    """Navigate Wikipedia from start to target by clicking links — fewer clicks, higher reward."""
    page = await _page()
    start_url = f"https://en.wikipedia.org/wiki/{start_page}"
    await _navigate(page, start_url)
    full_prompt = (
        f"Wikipedia Speedrun Challenge!\n\n"
        f"Starting article: {start_page.replace('_', ' ')}\n"
        f"Target article: {target_page.replace('_', ' ')}\n\n"
        f"Navigate from the starting article to the target article by clicking links.\n"
        f"You can ONLY click on links within the article content - no search, no back button.\n\n"
        f"Try to reach the target in as few clicks as possible!\n"
        f"Maximum clicks allowed: {max_clicks}"
    )
    _ = yield full_prompt

    current_url = page.url
    if f"/wiki/{target_page}".lower() in current_url.lower():
        try:
            history_length = await page.evaluate("() => window.history.length")
            clicks = max(1, history_length - 1)
        except Exception:
            clicks = max_clicks
        reward = max(0.1, 1.0 - (clicks - 1) / max_clicks) if clicks <= max_clicks else 0.1
        logger.info("wiki-speedrun: reached target in ~%d clicks, reward=%.2f", clicks, reward)
    else:
        reward = 0.0
        logger.info("wiki-speedrun: did not reach target, url=%s", current_url)
    yield reward


# ── Google Sheets tasks (SheetBench) ─────────────────────────────────────────
@env.template(id="sheet-from-file")
async def sheet_from_file(
    prompt: str,
    file_url: str = "",
    file_bytes: str = "",
    sheet_name: str = "Worksheet",
    expected_cells: dict | None = None,
    expected_text: list | None = None,
):
    """Create a Google Sheet from an Excel file and complete a task in it.

    Grades from the live sheet: `expected_cells` maps cell refs to expected values (checked on
    the ANSWER tab, partial credit per cell) and `expected_text` lists strings the sheet must
    contain; both present take the minimum.
    """
    page = await _page()
    sheet = await sheets.create_sheet(file_url=file_url, file_bytes=file_bytes, name=sheet_name)
    await sheets.navigate_to_sheet(page, sheet["sheet_url"])
    full_prompt = f"{prompt}\n\nThe spreadsheet is open at {sheet['sheet_url']}."
    _ = yield full_prompt

    reward = 1.0
    if expected_cells:
        cell_reward = await sheets.grade_cells(page, expected_cells)
        reward = min(reward, cell_reward)
    if expected_text:
        text_reward = await sheets.grade_contains(page, list(expected_text))
        reward = min(reward, text_reward)
    yield reward
