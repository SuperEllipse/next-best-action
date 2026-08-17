"""Scenario trigger service for Flask dashboard."""

from scenarios import run_scenario_a_push, run_scenario_b_pull


def trigger_scenario_a(verbose: bool = False) -> dict:
    return {"scenario": "PUSH_NBA", "results": run_scenario_a_push(verbose=verbose)}


def trigger_scenario_b(verbose: bool = False) -> dict:
    return {"scenario": "PULL_CONCIERGE", "results": run_scenario_b_pull(verbose=verbose)}
