"""Tasks for the remote-browser environment.

`hud eval tasks.py` and `hud sync tasks` collect the public `tasks` list below: the general
browsing tasks plus the 50 SheetBench tasks minted from the vendored `sheetbench.json`
(the hud-evals/SheetBench-50 dataset re-cut against the v6 `sheet-from-file` template).
"""

import json
from pathlib import Path

from env import (  # noqa: F401  (re-export env for `hud eval tasks.py`)
    answer,
    env,
    fill_record,
    sheet_from_file,
    wiki_speedrun,
)

# =============================================================================
# ANSWER — navigate and extract information (binary scoring)
# =============================================================================

_wiki_python_year = answer(
    url="https://en.wikipedia.org/wiki/Python_(programming_language)",
    prompt="What year was Python first released? Return just the year as a number.",
    expected="1991",
    compare_mode="contains",
)
_wiki_python_year.slug = "wiki-python-year"

_json_extract_title = answer(
    url="https://httpbin.org/json",
    prompt="Extract the 'title' field from the slideshow object. Return just the title text.",
    expected="Sample Slide Show",
    compare_mode="exact",
)
_json_extract_title.slug = "json-extract-title"

_wiki_multi_hop = answer(
    url="https://en.wikipedia.org/wiki/Python_(programming_language)",
    prompt=(
        "Find the name of the person who created Python by reading this page, "
        "then navigate to their Wikipedia article and find what year they were born. "
        "Return just the birth year as a number."
    ),
    expected="1956",
    compare_mode="contains",
)
_wiki_multi_hop.slug = "wiki-multi-hop"

_numeric_extraction = answer(
    url="https://en.wikipedia.org/wiki/Earth",
    prompt=(
        "What is the approximate equatorial radius of Earth in kilometers? "
        "Return just the number rounded to the nearest integer (e.g. 1234)."
    ),
    expected="6378",
    compare_mode="numeric",
)
_numeric_extraction.slug = "numeric-extraction"

# =============================================================================
# FILL-RECORD — form filling with partial-credit scoring
# =============================================================================

_httpbin_order_form = fill_record(
    url="https://httpbin.org/forms/post",
    prompt="Fill out the order form with the customer information provided.",
    fields={
        "Customer name": "Jane Smith",
        "Telephone": "555-9876",
        "Email": "jane@example.com",
        "Size": "Medium",
        "Topping": "Bacon",
    },
    verify={
        "input[name='custname']": "Jane Smith",
        "input[name='custtel']": "555-9876",
        "input[name='custemail']": "jane@example.com",
        "input[type='radio'][name='size'][value='medium']": "checked",
        "input[type='checkbox'][name='topping'][value='bacon']": "checked",
    },
)
_httpbin_order_form.slug = "httpbin-order-form"

_httpbin_complex_form = fill_record(
    url="https://httpbin.org/forms/post",
    prompt=(
        "Fill out the pizza order form completely: "
        "Customer: John Doe, Phone: 212-555-0100, Email: john@company.com, "
        "Size: Large, Toppings: Mushrooms and Onion, "
        "Delivery time: 19:30, Delivery instructions: Ring the bell twice."
    ),
    fields={
        "Customer name": "John Doe",
        "Telephone": "212-555-0100",
        "Email": "john@company.com",
        "Size": "Large",
        "Delivery time": "19:30",
        "Delivery instructions": "Ring the bell twice.",
    },
    verify={
        "input[name='custname']": "John Doe",
        "input[name='custtel']": "212-555-0100",
        "input[name='custemail']": "john@company.com",
        "input[type='radio'][name='size'][value='large']": "checked",
        "input[type='checkbox'][name='topping'][value='mushroom']": "checked",
        "input[type='checkbox'][name='topping'][value='onion']": "checked",
        "input[name='delivery']": "19:30",
        "textarea[name='comments']": "Ring the bell twice.",
    },
)
_httpbin_complex_form.slug = "httpbin-complex-form"

# =============================================================================
# WIKI-SPEEDRUN — navigate Wikipedia by clicking links (efficiency scoring)
# =============================================================================

_wiki_easy_hop = wiki_speedrun(
    start_page="Python_(programming_language)",
    target_page="Guido_van_Rossum",
    max_clicks=3,
)
_wiki_easy_hop.slug = "wiki-easy-hop"

_wiki_medium_hop = wiki_speedrun(
    start_page="Cat",
    target_page="Ancient_Egypt",
    max_clicks=6,
)
_wiki_medium_hop.slug = "wiki-medium-hop"

_wiki_hard_hop = wiki_speedrun(
    start_page="JavaScript",
    target_page="Tim_Berners-Lee",
    max_clicks=8,
)
_wiki_hard_hop.slug = "wiki-hard-hop"

# =============================================================================
# SHEETBENCH-50 — spreadsheet tasks minted from the vendored dataset
# =============================================================================

# Formatting rules that were the dataset's per-task system prompt; in v6 they travel
# with the task prompt.
_SHEETBENCH_RULES = (
    'All solutions should be put in the sheet called "ANSWER". In the answer sheet, all dates '
    "should use the American standard format MM/DD/YYYY with no leading zero. All numbers "
    "should use the format and decimal place precision given in the input sheets (e.g., with "
    "or without a thousands separator should depend on the inputs), unless specified otherwise."
)


def _sheetbench_tasks() -> list:
    rows = json.loads((Path(__file__).parent / "sheetbench.json").read_text())
    minted = []
    for row in rows:
        task = sheet_from_file(
            prompt=f"{row['prompt']}\n\n{_SHEETBENCH_RULES}",
            file_url=row["file_url"],
            sheet_name="Worksheet",
            expected_cells=row["expected_cells"],
        )
        task.slug = f"sheetbench-{row['id'][:8]}"
        minted.append(task)
    return minted


_sheetbench = _sheetbench_tasks()


tasks = [
    _wiki_python_year,
    _json_extract_title,
    _wiki_multi_hop,
    _numeric_extraction,
    _httpbin_order_form,
    _httpbin_complex_form,
    _wiki_easy_hop,
    _wiki_medium_hop,
    _wiki_hard_hop,
    *_sheetbench,
]
