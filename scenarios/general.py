"""General browser scenarios - navigation, forms, and page interaction."""
import json
import logging
import re
from typing import Any, Dict, Optional

from setup.navigate import navigate_to_url

logger = logging.getLogger(__name__)


def compare_answers(actual: Any, expected: Any, mode: str = "exact") -> float:
    """Compare agent answer to expected answer.
    
    Args:
        actual: The agent's answer
        expected: The expected answer
        mode: Comparison mode - "exact", "contains", "json", "numeric", "regex"
    
    Returns:
        Score between 0.0 and 1.0
    """
    if actual is None:
        return 0.0
    
    actual_str = str(actual).strip()
    expected_str = str(expected).strip()
    
    if mode == "exact":
        return 1.0 if actual_str.lower() == expected_str.lower() else 0.0
    
    elif mode == "contains":
        return 1.0 if expected_str.lower() in actual_str.lower() else 0.0
    
    elif mode == "json":
        try:
            actual_json = json.loads(actual_str) if isinstance(actual, str) else actual
            expected_json = json.loads(expected_str) if isinstance(expected, str) else expected
            return 1.0 if actual_json == expected_json else 0.0
        except (json.JSONDecodeError, TypeError):
            return 0.0
    
    elif mode == "numeric":
        try:
            # Extract numbers from strings
            actual_nums = re.findall(r'-?\d+\.?\d*', actual_str)
            expected_nums = re.findall(r'-?\d+\.?\d*', expected_str)
            if actual_nums and expected_nums:
                return 1.0 if float(actual_nums[0]) == float(expected_nums[0]) else 0.0
            return 0.0
        except (ValueError, IndexError):
            return 0.0
    
    elif mode == "regex":
        try:
            return 1.0 if re.search(expected_str, actual_str, re.IGNORECASE) else 0.0
        except re.error:
            return 0.0
    
    return 0.0


def register_general_scenarios(env: Any) -> None:
    """Register general browser scenarios with the environment."""

    @env.scenario("answer")
    async def answer(
        url: str,
        prompt: str,
        expected: Optional[Any] = None,
        compare_mode: str = "exact",
    ) -> Any:
        """Generic task where agent browses and returns an answer.
        
        The agent explores the page(s), then yields a final answer which
        is compared against the expected value (if provided).
        
        Args:
            url: Starting URL
            prompt: Task instruction (should ask agent to return an answer)
            expected: Optional expected answer to compare against. If None, reward is 1.0 on completion.
            compare_mode: How to compare - "exact", "contains", "json", "numeric", "regex"
        
        Example task:
            {
                "scenario": "answer",
                "args": {
                    "url": "https://en.wikipedia.org/wiki/Python_(programming_language)",
                    "prompt": "What year was Python first released? Return just the year.",
                    "expected": "1991",
                    "compare_mode": "contains"
                }
            }
        """
        from env import persistent_ctx
        playwright_tool = persistent_ctx.playwright_tool if persistent_ctx else None

        if not playwright_tool:
            yield 0.0
            return

        # Setup
        await navigate_to_url(playwright_tool, url)

        full_prompt = f"""Starting at: {url}

{prompt}

When you have found the answer, respond with your final answer clearly."""

        # Get the agent's response
        agent_response = yield full_prompt

        # Evaluate by comparing answers (if expected is provided)
        if expected is not None:
            reward = compare_answers(agent_response, expected, compare_mode)
            logger.info("Answer task: expected='%s', got='%s', mode=%s, reward=%.2f",
                       expected, agent_response, compare_mode, reward)
        else:
            reward = 1.0
            logger.info("Answer task: no expected value, agent response='%s', reward=%.2f",
                       agent_response, reward)

        yield reward

    @env.scenario("fill-record")
    async def fill_record(
        url: str,
        prompt: str,
        fields: Optional[Dict[str, Any]] = None,
        verify: Optional[Dict[str, str]] = None,
    ) -> Any:
        """Fill form fields and verify values via selectors.
        
        The agent fills in form fields. Evaluation checks that the
        specified selectors contain the expected values.
        
        Args:
            url: Page with the form/inputs
            prompt: Instructions for filling
            fields: Optional dict describing what to fill {description: value}
            verify: Dict mapping CSS selectors to expected values
                    e.g. {"#name-input": "John", "input[name='email']": "john@example.com"}
        
        Example task:
            {
                "scenario": "fill-record",
                "args": {
                    "url": "https://example.com/form",
                    "prompt": "Fill out the contact form with the given information.",
                    "fields": {"Name": "John Doe", "Email": "john@example.com"},
                    "verify": {"#name": "John Doe", "#email": "john@example.com"}
                }
            }
        """
        from env import persistent_ctx
        playwright_tool = persistent_ctx.playwright_tool if persistent_ctx else None

        if not playwright_tool:
            yield 0.0
            return

        # Setup
        await navigate_to_url(playwright_tool, url)

        # Build prompt with optional field instructions
        if fields:
            fields_desc = "\n".join([f"- {k}: {v}" for k, v in fields.items()])
            full_prompt = f"""You are on a page with form inputs.

{prompt}

Fill in the following:
{fields_desc}

Use the browser tools to locate and fill each field."""
        else:
            full_prompt = f"""You are on a page with form inputs.

{prompt}

Use the browser tools to locate and fill the required fields."""

        _ = yield full_prompt

        # Evaluate by checking selector values
        if not verify:
            logger.warning("No verify selectors provided, giving full credit")
            yield 1.0
            return

        page = playwright_tool.page
        total = len(verify)
        matches = 0

        for selector, expected_value in verify.items():
            try:
                element = page.locator(selector).first
                actual_value = await element.input_value()
                
                # Fallback to text content if input_value is empty
                if not actual_value:
                    actual_value = await element.text_content() or ""
                
                if str(actual_value).strip() == str(expected_value).strip():
                    matches += 1
                    logger.info("Field %s: MATCH '%s'", selector, expected_value)
                else:
                    logger.info("Field %s: MISMATCH expected='%s' got='%s'",
                               selector, expected_value, actual_value)
            except Exception as e:
                logger.warning("Could not check selector %s: %s", selector, e)

        reward = matches / total if total > 0 else 0.0
        logger.info("Fill-record: %d/%d fields correct, reward=%.2f", matches, total, reward)
        
        yield reward

    @env.scenario("wiki-speedrun")
    async def wiki_speedrun(
        start_page: str,
        target_page: str,
        max_clicks: int = 10,
        prompt: Optional[str] = None,
    ) -> Any:
        """Navigate Wikipedia from start to target using only link clicks.
        
        The agent must navigate from one Wikipedia article to another
        by clicking links. Fewer clicks = higher reward.
        
        Args:
            start_page: Starting Wikipedia article title (e.g. "Python_(programming_language)")
            target_page: Target Wikipedia article title (e.g. "Guido_van_Rossum")  
            max_clicks: Maximum allowed clicks (reward scales with efficiency)
            prompt: Optional custom prompt (default explains the game)
        
        Example task:
            {
                "scenario": "wiki-speedrun",
                "args": {
                    "start_page": "Cat",
                    "target_page": "Ancient_Egypt",
                    "max_clicks": 6
                }
            }
        
        Scoring:
            - Reached target in N clicks where N <= max_clicks: reward = 1.0 - (N-1)/(max_clicks)
            - Did not reach target: reward = 0.0
        """
        from env import persistent_ctx
        playwright_tool = persistent_ctx.playwright_tool if persistent_ctx else None

        if not playwright_tool:
            yield 0.0
            return

        start_url = f"https://en.wikipedia.org/wiki/{start_page}"
        target_url_pattern = f"/wiki/{target_page}"

        # Setup
        await navigate_to_url(playwright_tool, start_url)

        if prompt:
            full_prompt = prompt
        else:
            full_prompt = f"""Wikipedia Speedrun Challenge!

Starting article: {start_page.replace('_', ' ')}
Target article: {target_page.replace('_', ' ')}

Navigate from the starting article to the target article by clicking links.
You can ONLY click on links within the article content - no search, no back button.

Try to reach the target in as few clicks as possible!
Maximum clicks allowed: {max_clicks}

Click on article links to navigate. The goal is to reach: {target_page.replace('_', ' ')}"""

        _ = yield full_prompt

        # Evaluate
        page = playwright_tool.page
        current_url = page.url

        # Check if we reached the target
        if target_url_pattern.lower() in current_url.lower():
            # Count clicks from history if available
            try:
                history_length = await page.evaluate("() => window.history.length")
                clicks = max(1, history_length - 1)  # Subtract initial page load
            except Exception:
                clicks = max_clicks  # Assume max if can't determine

            # Score: reaching in 1 click = 1.0, reaching in max_clicks = small positive
            if clicks <= max_clicks:
                reward = max(0.1, 1.0 - (clicks - 1) / max_clicks)
            else:
                reward = 0.1  # Reached but exceeded max
            
            logger.info("Wiki speedrun: Reached target in ~%d clicks, reward=%.2f", clicks, reward)
        else:
            reward = 0.0
            logger.info("Wiki speedrun: Did not reach target. Current URL: %s", current_url)

        yield reward
