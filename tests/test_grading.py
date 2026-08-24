"""Offline tests for answer comparison and sheet grading — no browser, no Google APIs."""

import pytest

import env as E
import sheets as S


# ── compare_answers ──────────────────────────────────────────────────────────
def test_compare_exact():
    assert E.compare_answers("1991", "1991") == 1.0
    assert E.compare_answers(" Python ", "python", "exact") == 1.0
    assert E.compare_answers("1992", "1991") == 0.0
    assert E.compare_answers(None, "1991") == 0.0


def test_compare_contains():
    assert E.compare_answers("It was released in 1991.", "1991", "contains") == 1.0
    assert E.compare_answers("no year here", "1991", "contains") == 0.0


def test_compare_numeric():
    assert E.compare_answers("about 6,378 km", "6378", "numeric") == 1.0
    assert E.compare_answers("6377", "6378", "numeric") == 0.0


def test_compare_json():
    assert E.compare_answers('{"a": 1}', '{"a":1}', "json") == 1.0
    assert E.compare_answers('{"a": 2}', '{"a":1}', "json") == 0.0
    assert E.compare_answers("not json", '{"a":1}', "json") == 0.0


def test_compare_regex():
    assert E.compare_answers("Guido van Rossum", r"guido.*rossum", "regex") == 1.0
    assert E.compare_answers("someone else", r"guido.*rossum", "regex") == 0.0


# ── cell references ──────────────────────────────────────────────────────────
def test_column_to_index():
    assert S.column_to_index("A") == 0
    assert S.column_to_index("Z") == 25
    assert S.column_to_index("AA") == 26
    assert S.column_to_index("AB") == 27


def test_parse_cell_reference():
    assert S.parse_cell_reference("A1") == ("A", 0, 0)
    assert S.parse_cell_reference("B2") == ("B", 1, 1)
    assert S.parse_cell_reference("AA123") == ("AA", 122, 26)
    assert S.parse_cell_reference("1A") is None
    assert S.parse_cell_reference("A") is None
    assert S.parse_cell_reference("A1:B2") is None


# ── grid grading ─────────────────────────────────────────────────────────────
GRID = "alpha\tbeta\tgamma\n1\t2\t3\n4\t5\t6"


def test_grade_cells_in_grid_all_match():
    assert S.grade_cells_in_grid(GRID, {"A1": "alpha", "B2": "2", "C3": "6"}) == 1.0


def test_grade_cells_in_grid_partial():
    reward = S.grade_cells_in_grid(GRID, {"A1": "alpha", "B2": "wrong"})
    assert reward == pytest.approx(0.5)


def test_grade_cells_in_grid_missing_cells_score_zero():
    assert S.grade_cells_in_grid(GRID, {"Z99": "nope"}) == 0.0


def test_grade_cells_in_grid_strips_whitespace():
    assert S.grade_cells_in_grid("  x  \ty\n", {"A1": "x"}) == 1.0


# ── answer template end-to-end (fake page) ───────────────────────────────────
class _FakePage:
    url = "https://en.wikipedia.org/wiki/Guido_van_Rossum"

    async def goto(self, *a, **k):
        return None

    async def evaluate(self, *a, **k):
        return 3  # window.history.length


@pytest.fixture(autouse=True)
def _fake_browser(monkeypatch):
    async def _page():
        return _FakePage()

    monkeypatch.setattr(E, "_page", _page)


async def test_answer_template_grades_response():
    gen = E.answer.func(url="https://example.com", prompt="What?", expected="42",
                        compare_mode="contains")
    prompt = await gen.asend(None)
    assert "https://example.com" in prompt
    assert await gen.asend("the answer is 42") == 1.0


async def test_answer_template_no_expected_gives_full_credit():
    gen = E.answer.func(url="https://example.com", prompt="Do something.")
    await gen.asend(None)
    assert await gen.asend("done") == 1.0


async def test_wiki_speedrun_reached_target():
    gen = E.wiki_speedrun.func(start_page="Cat", target_page="Guido_van_Rossum", max_clicks=6)
    await gen.asend(None)
    reward = await gen.asend("done")
    assert 0.1 <= reward <= 1.0


async def test_wiki_speedrun_missed_target():
    gen = E.wiki_speedrun.func(start_page="Cat", target_page="Ancient_Egypt", max_clicks=6)
    await gen.asend(None)
    assert await gen.asend("done") == 0.0


# ── task collection ──────────────────────────────────────────────────────────
def test_tasks_collect():
    import tasks

    slugs = [t.slug for t in tasks.tasks]
    assert len(slugs) == len(set(slugs)) == 9 + 50
    assert "wiki-python-year" in slugs
    assert sum(1 for s in slugs if s.startswith("sheetbench-")) == 50
