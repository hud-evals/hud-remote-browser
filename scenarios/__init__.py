"""Remote browser scenarios.

Scenarios must be registered with @env.scenario() since they're Environment-specific.
"""
from scenarios.sheets import register_sheets_scenarios
from scenarios.general import register_general_scenarios


def register_scenarios(env):
    """Register all scenarios with the environment."""
    register_sheets_scenarios(env)
    register_general_scenarios(env)
