"""Scenario configuration accessors."""

from twin.simulator import SCENARIOS


def scenario_names() -> list[str]:
    """Return configured scenario keys without inventing a regional map."""
    return sorted(SCENARIOS)
