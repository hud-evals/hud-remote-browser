"""Computer tools registration for remote browser."""
from typing import Any

from hud.tools.computer import (
    AnthropicComputerTool,
    OpenAIComputerTool,
    HudComputerTool,
    GeminiComputerTool,
    QwenComputerTool,
)

from tools.browser import BrowserExecutor


def register_computer_tools(env: Any, browser_executor: BrowserExecutor) -> None:
    """Register computer tools with the environment."""
    env.add_tool(HudComputerTool(executor=browser_executor))
    env.add_tool(AnthropicComputerTool(executor=browser_executor))
    env.add_tool(OpenAIComputerTool(executor=browser_executor))
    env.add_tool(GeminiComputerTool(executor=browser_executor))
    env.add_tool(QwenComputerTool(executor=browser_executor))
