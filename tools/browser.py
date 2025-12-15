"""Browser tools - PlaywrightToolWithMemory and BrowserExecutor."""
import base64
import logging
from datetime import datetime
from typing import Any, Dict, List, Literal

from pydantic import Field

from hud.server import MCPRouter
from hud.tools.playwright import PlaywrightTool
from hud.tools.executors.base import BaseExecutor
from hud.tools.types import ContentResult

logger = logging.getLogger(__name__)

router = MCPRouter()


# =============================================================================
# PlaywrightToolWithMemory
# =============================================================================


class PlaywrightToolWithMemory(PlaywrightTool):
    """Extended PlaywrightTool that tracks navigation and action history."""

    def __init__(self, context: Any = None, cdp_url: str | None = None) -> None:
        super().__init__(cdp_url=cdp_url)
        self.navigation_history: List[Dict[str, Any]] = []
        self.action_history: List[Dict[str, Any]] = []
        self.selector_history: List[str] = []

    async def _ensure_browser(self) -> None:
        await super()._ensure_browser()
        if self.page:
            self._setup_event_listeners()

    def _setup_event_listeners(self) -> None:
        if not self.page:
            return
        try:
            self.page.on("dialog", self._handle_dialog)
        except Exception as e:
            logger.warning("Failed to setup event listeners: %s", e)

    async def _handle_dialog(self, dialog: Any) -> None:
        try:
            dialog_info = {
                "type": dialog.type,
                "message": dialog.message,
                "timestamp": datetime.now().isoformat(),
            }
            self._record_action("dialog", dialog_info)
            await dialog.dismiss()
        except Exception as e:
            logger.error("Error handling dialog: %s", e)

    def _record_action(self, action_type: str, details: Dict[str, Any], result: Any = None) -> None:
        self.action_history.append({
            "type": action_type,
            "timestamp": datetime.now().isoformat(),
            "details": details,
            "result": result,
        })

    async def navigate(
        self,
        url: str = Field(..., description="URL to navigate to"),
        wait_for_load_state: Literal["load", "domcontentloaded", "networkidle"] = Field(
            "networkidle", description="Wait condition after navigation"
        ),
    ) -> dict:
        self._record_action("navigate", {"url": url, "wait_for_load_state": wait_for_load_state})
        result = await super().navigate(url, wait_for_load_state)
        
        if self.action_history:
            self.action_history[-1]["result"] = result
        
        if result.get("success") and self.page:
            self.navigation_history.append({
                "url": self.page.url,
                "timestamp": datetime.now().isoformat()
            })
        
        return result

    async def click(
        self,
        selector: str = Field(..., description="CSS selector to click"),
        button: Literal["left", "right", "middle"] = Field("left", description="Mouse button"),
        count: int = Field(1, description="Number of clicks"),
        wait_for_navigation: bool = Field(False, description="Wait for navigation after click"),
    ) -> dict:
        self.selector_history.append(selector)
        self._record_action("click", {
            "selector": selector,
            "button": button,
            "count": count,
            "wait_for_navigation": wait_for_navigation,
        })
        result = await super().click(selector, button, count, wait_for_navigation)
        
        if self.action_history:
            self.action_history[-1]["result"] = result
        
        return result

    def get_history_summary(self) -> Dict[str, Any]:
        return {
            "navigation_count": len(self.navigation_history),
            "action_count": len(self.action_history),
            "unique_selectors": len(set(self.selector_history)),
            "last_navigation": self.navigation_history[-1] if self.navigation_history else None,
            "last_action": self.action_history[-1] if self.action_history else None,
        }


# =============================================================================
# BrowserExecutor
# =============================================================================


PLAYWRIGHT_KEY_MAP = {
    "ctrl": "Control", "control": "Control", "alt": "Alt", "shift": "Shift",
    "meta": "Meta", "cmd": "Meta", "command": "Meta", "win": "Meta",
    "enter": "Enter", "return": "Enter", "tab": "Tab", "backspace": "Backspace",
    "delete": "Delete", "escape": "Escape", "esc": "Escape", "space": "Space",
    "up": "ArrowUp", "down": "ArrowDown", "left": "ArrowLeft", "right": "ArrowRight",
    "pageup": "PageUp", "pagedown": "PageDown", "home": "Home", "end": "End",
    "f1": "F1", "f2": "F2", "f3": "F3", "f4": "F4", "f5": "F5", "f6": "F6",
    "f7": "F7", "f8": "F8", "f9": "F9", "f10": "F10", "f11": "F11", "f12": "F12",
}


class BrowserExecutor(BaseExecutor):
    """Executor that performs actions within a browser viewport using Playwright."""

    def __init__(self, playwright_tool: PlaywrightToolWithMemory, display_num: int | None = None):
        super().__init__(display_num)
        self.playwright_tool = playwright_tool

    def _map_key(self, key: str) -> str:
        return PLAYWRIGHT_KEY_MAP.get(key.lower().strip(), key)

    async def _ensure_page(self):
        await self.playwright_tool._ensure_browser()
        if not self.playwright_tool.page:
            raise RuntimeError("No browser page available")
        return self.playwright_tool.page

    async def screenshot(self) -> str | None:
        try:
            page = await self._ensure_page()
            screenshot_bytes = await page.screenshot(full_page=False)
            return base64.b64encode(screenshot_bytes).decode()
        except Exception as e:
            logger.error("Screenshot failed: %s", e)
            return None

    async def click(
        self,
        x: int | None = None,
        y: int | None = None,
        button: Literal["left", "right", "middle", "back", "forward"] = "left",
        pattern: list[int] | None = None,
        hold_keys: list[str] | None = None,
        take_screenshot: bool = True,
    ) -> ContentResult:
        try:
            page = await self._ensure_page()
            if x is None or y is None:
                return ContentResult(error="Coordinates required for click")

            if hold_keys:
                for key in hold_keys:
                    await page.keyboard.down(self._map_key(key))

            button_map = {"left": "left", "right": "right", "middle": "middle", "back": "left", "forward": "left"}
            if pattern:
                for delay in pattern:
                    await page.mouse.click(x, y, button=button_map[button])
                    if delay > 0:
                        await page.wait_for_timeout(delay)
            else:
                await page.mouse.click(x, y, button=button_map[button])

            if hold_keys:
                for key in hold_keys:
                    await page.keyboard.up(self._map_key(key))

            result = ContentResult(output=f"Clicked at ({x}, {y})")
            if take_screenshot:
                result = result + ContentResult(base64_image=await self.screenshot())
            return result
        except Exception as e:
            return ContentResult(error=str(e))

    async def write(
        self,
        text: str,
        enter_after: bool = False,
        hold_keys: list[str] | None = None,
        take_screenshot: bool = True,
    ) -> ContentResult:
        try:
            page = await self._ensure_page()

            if hold_keys:
                for key in hold_keys:
                    await page.keyboard.down(self._map_key(key))

            await page.keyboard.type(text)
            if enter_after:
                await page.keyboard.press("Enter")

            if hold_keys:
                for key in hold_keys:
                    await page.keyboard.up(self._map_key(key))

            result = ContentResult(output=f"Typed: {text}")
            if take_screenshot:
                result = result + ContentResult(base64_image=await self.screenshot())
            return result
        except Exception as e:
            return ContentResult(error=str(e))

    async def press(
        self,
        keys: list[str],
        take_screenshot: bool = True,
    ) -> ContentResult:
        try:
            page = await self._ensure_page()
            mapped_keys = [self._map_key(key) for key in keys]
            processed_keys = [k.upper() if len(k) == 1 and k.isalpha() and k.islower() else k for k in mapped_keys]
            key_combination = "+".join(processed_keys)
            await page.keyboard.press(key_combination)

            result = ContentResult(output=f"Pressed: {key_combination}")
            if take_screenshot:
                result = result + ContentResult(base64_image=await self.screenshot())
            return result
        except Exception as e:
            return ContentResult(error=str(e))

    async def scroll(
        self,
        x: int | None = None,
        y: int | None = None,
        scroll_x: int | None = None,
        scroll_y: int | None = None,
        hold_keys: list[str] | None = None,
        take_screenshot: bool = True,
    ) -> ContentResult:
        try:
            page = await self._ensure_page()

            if x is None or y is None:
                viewport = page.viewport_size
                x = viewport["width"] // 2 if viewport else 400
                y = viewport["height"] // 2 if viewport else 300

            await page.mouse.move(x, y)
            await page.mouse.wheel(scroll_x or 0, scroll_y or 0)

            result = ContentResult(output=f"Scrolled by ({scroll_x}, {scroll_y})")
            if take_screenshot:
                result = result + ContentResult(base64_image=await self.screenshot())
            return result
        except Exception as e:
            return ContentResult(error=str(e))

    async def move(
        self,
        x: int | None = None,
        y: int | None = None,
        take_screenshot: bool = True,
    ) -> ContentResult:
        try:
            page = await self._ensure_page()
            if x is None or y is None:
                return ContentResult(error="Coordinates required for move")

            await page.mouse.move(x, y)

            result = ContentResult(output=f"Moved to ({x}, {y})")
            if take_screenshot:
                result = result + ContentResult(base64_image=await self.screenshot())
            return result
        except Exception as e:
            return ContentResult(error=str(e))

    async def drag(
        self,
        path: list[tuple[int, int]],
        button: Literal["left", "right", "middle"] = "left",
        hold_keys: list[str] | None = None,
        take_screenshot: bool = True,
    ) -> ContentResult:
        try:
            page = await self._ensure_page()
            if not path or len(path) < 2:
                return ContentResult(error="Path must have at least 2 points")

            if hold_keys:
                for key in hold_keys:
                    await page.keyboard.down(self._map_key(key))

            start_x, start_y = path[0]
            await page.mouse.move(start_x, start_y)
            await page.mouse.down(button=button)

            for x, y in path[1:]:
                await page.mouse.move(x, y)

            await page.mouse.up(button=button)

            if hold_keys:
                for key in hold_keys:
                    await page.keyboard.up(self._map_key(key))

            result = ContentResult(output=f"Dragged through {len(path)} points")
            if take_screenshot:
                result = result + ContentResult(base64_image=await self.screenshot())
            return result
        except Exception as e:
            return ContentResult(error=str(e))


__all__ = ["router", "PlaywrightToolWithMemory", "BrowserExecutor"]
