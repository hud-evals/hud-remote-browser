"""Tests for evaluation and setup functions using real browser."""

from evaluate.url_match import url_match
from evaluate.page_contains import page_contains
from evaluate.element_exists import element_exists
from evaluate.cookie_exists import cookie_exists
from evaluate.cookie_match import cookie_match
from evaluate.history_length import history_length
from evaluate.raw_last_action_is import raw_last_action_is
from evaluate.selector_history import selector_history
from evaluate.verify_type_action import verify_type_action
from setup.navigate import navigate_to_url
from setup.cookies import set_cookies, clear_cookies
from setup.interact import click_element, fill_input, select_option
from setup.load_html import load_html_content


class TestEvaluation:
    """Test evaluation and setup functions with real browser."""

    async def test_browser(self, playwright_tool):
        # Test url_match
        await playwright_tool.page.goto("https://example.com/")
        result = await url_match(playwright_tool, "https://example.com/")
        assert result["reward"] == 1.0
        assert result["success"] is True

        result = await url_match(playwright_tool, "other.com")
        assert result["reward"] == 0.0

        # Test page_contains
        result = await page_contains(playwright_tool, "Example Domain")
        assert result["reward"] == 1.0

        result = await page_contains(playwright_tool, "This text does not exist")
        assert result["reward"] == 0.0

        result = await page_contains(playwright_tool, ["Example", "Domain"])
        assert result["reward"] == 1.0

        result = await page_contains(
            playwright_tool, ["Example", "NonexistentText"], partial_rewarding=True
        )
        assert result["reward"] == 0.5

        # Test element_exists with custom HTML
        await playwright_tool.page.set_content(
            '<html><body><h1 id="title">Hello</h1></body></html>'
        )
        result = await element_exists(playwright_tool, "#title")
        assert result["reward"] == 1.0

        result = await element_exists(playwright_tool, "#nonexistent")
        assert result["reward"] == 0.0

        # Test cookies
        await playwright_tool.page.goto("https://example.com/")
        await playwright_tool.page.context.add_cookies(
            [{"name": "session", "value": "abc123", "url": "https://example.com/"}]
        )

        result = await cookie_exists(playwright_tool, "session")
        assert result["reward"] == 1.0
        assert result["cookie_value"] == "abc123"

        result = await cookie_exists(playwright_tool, "nonexistent")
        assert result["reward"] == 0.0

        result = await cookie_match(playwright_tool, "session", "abc123")
        assert result["reward"] == 1.0

        result = await cookie_match(playwright_tool, "session", "wrong")
        assert result["reward"] == 0.0

        # Test history-based evaluations
        playwright_tool.action_history = [{"type": "click"}] * 5
        result = await history_length(playwright_tool, min_length=3, max_length=7)
        assert result["success"] is True

        playwright_tool.action_history = [
            {"type": "navigate", "details": {}, "timestamp": "t1"},
            {"type": "click", "details": {"selector": "#btn"}, "timestamp": "t2"},
        ]
        result = await raw_last_action_is(playwright_tool, "click")
        assert result["reward"] == 1.0

        playwright_tool.selector_history = ["#a", "#b", "#c"]
        result = await selector_history(playwright_tool, 1, "#b")
        assert result["reward"] == 1.0

        playwright_tool.action_history = [
            {"type": "type", "details": {"text": "hello", "selector": "#input"}, "timestamp": "t"},
        ]
        result = await verify_type_action(playwright_tool, "hello")
        assert result["reward"] == 1.0

        # Test setup functions
        result = await navigate_to_url(playwright_tool, "https://example.com/")
        assert result["success"] is True

        result = await set_cookies(
            playwright_tool,
            [{"name": "test", "value": "value", "url": "https://example.com/"}],
        )
        assert result["success"] is True

        result = await clear_cookies(playwright_tool)
        assert result["success"] is True

        # Test click_element
        await playwright_tool.page.set_content(
            """<html><body>
            <button id="btn" onclick="document.body.innerHTML='clicked'">Click</button>
            </body></html>"""
        )
        result = await click_element(playwright_tool, "#btn")
        assert result["success"] is True

        # Test fill_input
        await playwright_tool.page.set_content(
            '<html><body><input id="name" type="text" /></body></html>'
        )
        result = await fill_input(playwright_tool, "#name", "John")
        assert result["success"] is True
        value = await playwright_tool.page.input_value("#name")
        assert value == "John"

        # Test select_option
        await playwright_tool.page.set_content(
            """<html><body>
            <select id="dropdown">
                <option value="a">A</option>
                <option value="b">B</option>
            </select>
            </body></html>"""
        )
        result = await select_option(playwright_tool, "#dropdown", "b")
        assert result["success"] is True

        # Test load_html_content
        result = await load_html_content(
            playwright_tool, "<html><body><h1>Test</h1></body></html>"
        )
        assert result["success"] is True

    async def test_no_tool(self):
        """Test that all functions handle None tool gracefully."""
        assert (await url_match(None, "example.com"))["reward"] == 0.0
        assert (await page_contains(None, "test"))["reward"] == 0.0
        assert (await element_exists(None, "#test"))["reward"] == 0.0
        assert (await cookie_exists(None, "session"))["reward"] == 0.0
        assert (await cookie_match(None, "token", "value"))["reward"] == 0.0
        assert (await history_length(None, min_length=1))["reward"] == 0.0
        assert (await raw_last_action_is(None, "click"))["reward"] == 0.0
        assert (await selector_history(None, 0, "#a"))["reward"] == 0.0
        assert (await verify_type_action(None, "hello"))["reward"] == 0.0
        assert (await navigate_to_url(None, "https://example.com/"))["success"] is False
        assert (await set_cookies(None, []))["success"] is False
        assert (await clear_cookies(None))["success"] is False
        assert (await click_element(None, "#btn"))["success"] is False
        assert (await fill_input(None, "#name", "test"))["success"] is False
        assert (await select_option(None, "#dropdown", "opt"))["success"] is False
        assert (await load_html_content(None, "<p>test</p>"))["success"] is False
