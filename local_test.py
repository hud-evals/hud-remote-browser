"""Local test script for the remote browser environment.

Development workflow (Docker with hot-reload):
1. Build: hud build
2. Start: hud dev -w scenarios -w evaluate -w setup --port 8765
3. Test: python local_test.py

The container runs the environment with tools/scenarios.
This script connects to it and runs agent evaluations.
"""
import asyncio
import os

import hud
from hud import Environment
from hud.agents import OpenAIChatAgent
from hud.settings import settings
from openai import AsyncOpenAI

# Use HUD inference gateway - see all models at https://hud.ai/models
client = AsyncOpenAI(base_url="https://inference.hud.ai", api_key=settings.api_key)

# Connect to running container (scenarios/tools are defined there)
DEV_URL = os.getenv("HUD_DEV_URL", "http://localhost:8765/mcp")

env = Environment("remote-browser")
env.connect_url(DEV_URL)


async def test_tools_standalone():
    """Test environment tools directly."""
    print("=== Test 1: Standalone Tools ===")

    async with env:
        print(f"Tools: {[t.name for t in env.as_tools()]}")


async def test_answer_scenario():
    """Test answer scenario with manual OpenAI calls."""
    print("\n=== Test 2: Answer Scenario (Manual Agent Loop) ===")

    task = env("answer",
        url="https://en.wikipedia.org/wiki/Python_(programming_language)",
        prompt="What year was Python first released? Return just the year.",
        expected="1991",
        compare_mode="contains"
    )

    async with hud.eval(task) as ctx:
        messages = [{"role": "user", "content": ctx.prompt}]

        while True:
            response = await client.chat.completions.create(
                model="gpt-4o",  # https://hud.ai/models
                messages=messages,
                tools=ctx.as_openai_chat_tools(),
            )
            msg = response.choices[0].message

            if not msg.tool_calls:
                break

            messages.append(msg)
            for tc in msg.tool_calls:
                result = await ctx.call_tool(tc)
                messages.append(result)


async def test_wiki_speedrun():
    """Test wiki speedrun scenario with OpenAIChatAgent."""
    print("\n=== Test 3: Wiki Speedrun Scenario ===")

    task = env("wiki-speedrun",
        start_page="Python_(programming_language)",
        target_page="Guido_van_Rossum",
        max_clicks=3
    )

    async with hud.eval(task) as ctx:
        agent = OpenAIChatAgent.create(model="gpt-4o")  # https://hud.ai/models
        await agent.run(ctx)


async def main():
    print("Remote Browser Environment - Local Test")
    print("=" * 50)
    print(f"Container URL: {DEV_URL}")
    print("Make sure the container is running:")
    print("  hud dev -w scenarios -w evaluate -w setup --port 8765")
    print("=" * 50)
    print()

    await test_tools_standalone()
    # Uncomment to run scenarios:
    # await test_answer_scenario()
    # await test_wiki_speedrun()


if __name__ == "__main__":
    asyncio.run(main())
