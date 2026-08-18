#!/usr/bin/env python3
"""Orchestrate IROP demo: create tables, seed data, run scenarios, launch Flask dashboard."""

import argparse
import os
import sys

# Ensure project root is on path and load .env before other imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from env_config import load_project_env, print_env_status

load_project_env()


def _print_scenario_result(customer_id: str, data: dict) -> None:
    scenario = data.get("scenario", "")
    header = f"\n--- {customer_id}" + (f" [{scenario}]" if scenario else "") + " ---"
    print(header)
    if data.get("push_prompt"):
        print(f"Push: {data['push_prompt']}")
    if data.get("concierge_reply"):
        print(f"Concierge: {data['concierge_reply']}")
    if data.get("chosen_flight"):
        print(f"Flight: {data['chosen_flight']}")
    if data.get("result"):
        print(data["result"])
    if data.get("brain_log"):
        print("\nAgent Brain Log:")
        for step in data["brain_log"]:
            print(f"  [{step.get('phase')}] {step.get('detail', '')[:200]}")


def setup_data():
    from spark_session import verify_iceberg_runtime
    from table_creation import create_tables
    from seed_data import seed_data

    print("=== Verifying Iceberg runtime ===")
    verify_iceberg_runtime()
    print("=== Creating Iceberg tables ===")
    create_tables()
    print("=== Seeding operational data (first ADLS write may take 1-3 min) ===")
    seed_data()
    print("Done. Passenger profiles remain in Snowflake only.")


def run_scenarios(verbose: bool = True):
    from scenarios import run_scenario_a, run_scenario_b

    print_env_status()
    print("\n=== Scenario A: Push / NBA ===")
    results_a = run_scenario_a(verbose=verbose)
    for cid, data in results_a.items():
        _print_scenario_result(cid, data)

    print("\n=== Scenario B: Pull / Concierge (David) ===")
    results_b = run_scenario_b(verbose=verbose)
    for cid, data in results_b.items():
        _print_scenario_result(cid, data)


def launch_dashboard():
    from dashboard.app import get_app_server_config, run_server

    print_env_status()
    host, port = get_app_server_config()
    print(f"=== Launching Flask dashboard on {host}:{port} (CDSW_APP_PORT) ===")
    print("Access via the grid icon in the Cloudera AI session toolbar.")
    run_server(debug=False)


def main():
    parser = argparse.ArgumentParser(description="IROP Agentic Demo")
    parser.add_argument(
        "command",
        choices=["setup", "seed", "test-insert", "scenario-a", "scenario-b", "scenarios", "dashboard", "all"],
        help="setup=create tables+seed, seed=seed only, test-insert=smoke test, scenario-a/b, dashboard, all",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress verbose CrewAI agent output (summary still printed)",
    )
    args = parser.parse_args()
    verbose = not args.quiet

    if args.command == "setup":
        setup_data()
    elif args.command == "seed":
        from seed_data import seed_data
        seed_data()
    elif args.command == "test-insert":
        from test_iceberg_insert import main as test_insert
        test_insert()
    elif args.command == "scenario-a":
        from scenarios import run_scenario_a
        print_env_status()
        print("\n=== Scenario A: Push / NBA ===")
        results_a = run_scenario_a(verbose=verbose)
        for cid, data in results_a.items():
            _print_scenario_result(cid, data)
    elif args.command == "scenario-b":
        from scenarios import run_scenario_b
        print_env_status()
        print("\n=== Scenario B: Pull / Concierge (David) ===")
        results_b = run_scenario_b(verbose=verbose)
        for cid, data in results_b.items():
            _print_scenario_result(cid, data)
    elif args.command == "scenarios":
        run_scenarios(verbose=verbose)
    elif args.command == "dashboard":
        launch_dashboard()
    elif args.command == "all":
        setup_data()
        run_scenarios(verbose=verbose)
        launch_dashboard()


if __name__ == "__main__":
    main()
