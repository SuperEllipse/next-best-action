#!/usr/bin/env python3
"""Orchestrate IROP demo: create tables, seed data, run scenarios, launch Flask dashboard."""

import argparse
import os
import sys

# Ensure project root is on path and load .env before other imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from env_config import load_project_env, print_env_status

load_project_env()


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
    from scenarios import run_scenario_a_push, run_scenario_b_pull

    print_env_status()
    print("\n=== Scenario A: Push / NBA ===")
    results_a = run_scenario_a_push(verbose=verbose)
    for cid, data in results_a.items():
        print(f"\n--- {cid} ---\n{data['result']}")

    print("\n=== Scenario B: Pull / Concierge (David) ===")
    results_b = run_scenario_b_pull(verbose=verbose)
    for cid, data in results_b.items():
        print(f"\n--- {cid} ---\n{data['result']}")


def launch_dashboard():
    from dashboard.app import get_app_server_config, run_server

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
        from scenarios import run_scenario_a_push
        print_env_status()
        print("\n=== Scenario A: Push / NBA ===")
        results_a = run_scenario_a_push(verbose=verbose)
        for cid, data in results_a.items():
            print(f"\n--- {cid} ---\n{data['result']}")
    elif args.command == "scenario-b":
        from scenarios import run_scenario_b_pull
        print_env_status()
        print("\n=== Scenario B: Pull / Concierge (David) ===")
        results_b = run_scenario_b_pull(verbose=verbose)
        for cid, data in results_b.items():
            print(f"\n--- {cid} ---\n{data['result']}")
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
