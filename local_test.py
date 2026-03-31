"""Local test script for the remote browser environment.

Development workflow (Docker with hot-reload):
1. Build: hud build
2. Start: hud dev -w scenarios -w evaluate -w setup --port 8765
3. Test: python local_test.py --list
         python local_test.py --task wiki-python-year
         python local_test.py --task wiki-easy-hop --model gpt-4o-mini

The container runs the environment with tools/scenarios.
This script connects to it and runs agent evaluations.
"""

import argparse
import asyncio
import os

import hud
from hud import Environment
from hud.agents import OpenAIChatAgent

from tasks import ALL_TASKS

# Connect to running container (scenarios/tools are defined there)
DEV_URL = os.getenv("HUD_DEV_URL", "http://localhost:8765/mcp")

dev_env = Environment("remote-browser")
dev_env.connect_url(DEV_URL)


def list_tasks():
    """Print all available tasks with their scenarios."""
    print(f"Available tasks ({len(ALL_TASKS)}):")
    print("-" * 60)
    for slug, task in ALL_TASKS.items():
        print(f"  {slug:<28} [{task.scenario}]")


async def run_task(slug: str, model: str, max_steps: int):
    """Run a single task against the dev container."""
    task = ALL_TASKS[slug]
    # Rebind to dev container environment
    local_task = dev_env(task.scenario, **(task.args or {}))

    print(f"\n=== {slug} (scenario: {task.scenario}, model: {model}) ===")

    async with hud.eval(local_task, name=slug) as ctx:
        agent = OpenAIChatAgent.create(model=model)
        await agent.run(ctx, max_steps=max_steps)
        print(f"  Reward: {ctx.reward}")


async def main():
    parser = argparse.ArgumentParser(description="Local test for remote browser tasks")
    parser.add_argument("--task", type=str, help="Run a specific task by slug")
    parser.add_argument(
        "--list", action="store_true", help="List available tasks and exit"
    )
    parser.add_argument(
        "--model", type=str, default="gpt-4o", help="Model to use (default: gpt-4o)"
    )
    parser.add_argument(
        "--max-steps", type=int, default=10, help="Max agent steps (default: 10)"
    )
    args = parser.parse_args()

    if args.list:
        list_tasks()
        return

    if args.task:
        if args.task not in ALL_TASKS:
            print(f"Unknown task: {args.task}")
            list_tasks()
            return
        await run_task(args.task, args.model, args.max_steps)
    else:
        print(f"Container URL: {DEV_URL}")
        print("Make sure the container is running:")
        print("  hud dev -w scenarios -w evaluate -w setup --port 8765")
        print()
        # Default: run all tasks
        for slug in ALL_TASKS:
            try:
                await run_task(slug, args.model, args.max_steps)
            except Exception as e:
                print(f"  ERROR: {e}")


if __name__ == "__main__":
    asyncio.run(main())
