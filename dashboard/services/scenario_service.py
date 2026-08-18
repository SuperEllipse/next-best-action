"""Scenario trigger service for Flask dashboard."""

from choice_oriented_passenger import get_rules_contrast as fetch_rules_contrast
from iceberg_tools import compute_execution_stats
from scenarios import run_scenario_a, run_scenario_b


def trigger_scenario_a(verbose: bool = False) -> dict:
    return {"scenario": "PUSH_NBA", "results": run_scenario_a(verbose=verbose)}


def trigger_scenario_b(
    verbose: bool = False,
    chat_message: str | None = None,
    chat_history: list[dict] | None = None,
) -> dict:
    return {
        "scenario": "PULL_CONCIERGE",
        "results": run_scenario_b(
            verbose=verbose,
            chat_message=chat_message,
            chat_history=chat_history,
            ensure_scenario_a=True,
        ),
    }


def get_executive_stats(window: str = "1d") -> dict:
    return compute_execution_stats(window=window)


def get_rules_contrast() -> dict:
    return fetch_rules_contrast()
