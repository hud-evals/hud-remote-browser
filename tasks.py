"""Task definitions for hud-remote-browser.

Each task is created via scenario.task() and registered in ALL_TASKS for
discovery by local_test.py and remote_test.py.

Usage:
    python local_test.py --list
    python local_test.py --task wiki-python-year
    python local_test.py --task wiki-easy-hop --model gpt-4o-mini
"""

from env import env  # noqa: F401 — triggers scenario registration

from scenarios import answer, fill_record, wiki_speedrun

# =============================================================================
# ANSWER — navigate and extract information (binary/fuzzy scoring)
# =============================================================================

# Easy: single fact extraction, "contains" match
wiki_python_year = answer.task(
    url="https://en.wikipedia.org/wiki/Python_(programming_language)",
    prompt="What year was Python first released? Return just the year as a number.",
    expected="1991",
    compare_mode="contains",
)
wiki_python_year.slug = "wiki-python-year"

# Easy: exact JSON field extraction
json_extract_title = answer.task(
    url="https://httpbin.org/json",
    prompt="Extract the 'title' field from the slideshow object. Return just the title text.",
    expected="Sample Slideshow",
    compare_mode="exact",
)
json_extract_title.slug = "json-extract-title"

# Hard: multi-hop — navigate to a linked page, then extract
wiki_multi_hop = answer.task(
    url="https://en.wikipedia.org/wiki/Python_(programming_language)",
    prompt=(
        "Find the name of the person who created Python by reading this page, "
        "then navigate to their Wikipedia article and find what year they were born. "
        "Return just the birth year as a number."
    ),
    expected="1956",
    compare_mode="contains",
)
wiki_multi_hop.slug = "wiki-multi-hop"

# Medium: numeric comparison mode
numeric_extraction = answer.task(
    url="https://en.wikipedia.org/wiki/Earth",
    prompt=(
        "What is the approximate equatorial radius of Earth in kilometers? "
        "Return just the number (e.g. 6371)."
    ),
    expected="6371",
    compare_mode="numeric",
)
numeric_extraction.slug = "numeric-extraction"

# =============================================================================
# FILL-RECORD — form filling with partial-credit scoring
# =============================================================================

# Medium: fill a simple order form
httpbin_order_form = fill_record.task(
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
    },
)
httpbin_order_form.slug = "httpbin-order-form"

# Hard: more fields, more detailed instructions
httpbin_complex_form = fill_record.task(
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
        "input[name='delivery']": "19:30",
        "textarea[name='comments']": "Ring the bell twice.",
    },
)
httpbin_complex_form.slug = "httpbin-complex-form"

# =============================================================================
# WIKI-SPEEDRUN — navigate Wikipedia by clicking links (efficiency scoring)
# =============================================================================

# Easy: one direct link away
wiki_easy_hop = wiki_speedrun.task(
    start_page="Python_(programming_language)",
    target_page="Guido_van_Rossum",
    max_clicks=3,
)
wiki_easy_hop.slug = "wiki-easy-hop"

# Medium: requires a chain of related articles
wiki_medium_hop = wiki_speedrun.task(
    start_page="Cat",
    target_page="Ancient_Egypt",
    max_clicks=6,
)
wiki_medium_hop.slug = "wiki-medium-hop"

# Hard: distant topics, longer chain needed
wiki_hard_hop = wiki_speedrun.task(
    start_page="JavaScript",
    target_page="Tim_Berners-Lee",
    max_clicks=8,
)
wiki_hard_hop.slug = "wiki-hard-hop"

# =============================================================================
# ALL_TASKS — master registry for discovery
# =============================================================================

ALL_TASKS = {
    # answer
    "wiki-python-year": wiki_python_year,
    "json-extract-title": json_extract_title,
    "wiki-multi-hop": wiki_multi_hop,
    "numeric-extraction": numeric_extraction,
    # fill-record
    "httpbin-order-form": httpbin_order_form,
    "httpbin-complex-form": httpbin_complex_form,
    # wiki-speedrun
    "wiki-easy-hop": wiki_easy_hop,
    "wiki-medium-hop": wiki_medium_hop,
    "wiki-hard-hop": wiki_hard_hop,
}
