"""Remote browser scenarios.

Scenarios are registered via @env.scenario() and their handles are exposed
as module-level attributes after register_scenarios() is called from env.py.

Usage in tasks.py:
    from scenarios import answer, fill_record, wiki_speedrun
"""
from scenarios.sheets import register_sheets_scenarios
from scenarios.general import register_general_scenarios

# ScenarioHandle instances — populated by register_scenarios()
answer = None
fill_record = None
wiki_speedrun = None
sheet_from_file = None


def register_scenarios(env):
    """Register all scenarios with the environment and expose their handles."""
    global answer, fill_record, wiki_speedrun, sheet_from_file

    general = register_general_scenarios(env)
    sheets = register_sheets_scenarios(env)

    answer = general["answer"]
    fill_record = general["fill_record"]
    wiki_speedrun = general["wiki_speedrun"]

    sheet_from_file = sheets["sheet_from_file"]
