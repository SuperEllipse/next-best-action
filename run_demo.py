#!/usr/bin/env python3
"""Orchestrate IROP demo: create tables, seed data, run scenarios, launch Flask dashboard."""

import argparse
import os
import sys


def _bootstrap_project_root() -> str:
    """Resolve project root when run as a script or a Cloudera AI kernel cell."""
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except NameError:
        for key in ("CDSW_PROJECT", "PROJECT_ROOT"):
            root = os.environ.get(key, "").strip()
            if root and os.path.isfile(os.path.join(root, "run_demo.py")):
                return os.path.abspath(root)
        cwd = os.getcwd()
        if os.path.isfile(os.path.join(cwd, "run_demo.py")):
            return cwd
        return cwd


# Ensure project root is on path and load .env before other imports
_ROOT = _bootstrap_project_root()
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from env_config import get_env_status, load_project_env, print_env_status

load_project_env()

_VALID_COMMANDS = frozenset(
    {"setup", "seed", "test-insert", "scenario-a", "scenario-b", "scenarios", "dashboard", "all"}
)


def _running_in_jupyter_kernel() -> bool:
    """True when Cloudera AI runs a .py file via ipykernel (not a shell command)."""
    argv0 = os.path.basename(sys.argv[0]) if sys.argv else ""
    if "ipykernel" in argv0:
        return True
    if any("/jupyter/runtime/kernel-" in arg for arg in sys.argv[1:]):
        return True
    try:
        get_ipython  # type: ignore[name-defined]  # noqa: F821
        return True
    except NameError:
        return False


def _cli_argv() -> list[str]:
    """Build argv for argparse; Jupyter injects kernel connection paths into sys.argv."""
    if _running_in_jupyter_kernel():
        env_cmd = os.environ.get("IROP_DEMO_COMMAND", "").strip()
        if env_cmd:
            if env_cmd not in _VALID_COMMANDS:
                raise SystemExit(
                    f"Invalid IROP_DEMO_COMMAND='{env_cmd}'. "
                    f"Choose from: {', '.join(sorted(_VALID_COMMANDS))}"
                )
            return [env_cmd]
        return []

    cli_args = []
    for arg in sys.argv[1:]:
        if arg in _VALID_COMMANDS or arg in ("-q", "--quiet"):
            cli_args.append(arg)
    return cli_args


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
    status = get_env_status()
    if not status["iceberg_warehouse_uri_set"]:
        print(
            "\nERROR: ICEBERG_WAREHOUSE_URI is not set. "
            "Add your lakehouse path to .env or Application environment variables "
            "(see .env.example)."
        )
        sys.exit(1)
    host, port = get_app_server_config()
    print(f"=== Launching Flask dashboard on {host}:{port} (CDSW_APP_PORT) ===")
    print("Access via the grid icon in the Cloudera AI session toolbar.")
    run_server(debug=False)


def main():
    parser = argparse.ArgumentParser(description="IROP Agentic Demo")
    parser.add_argument(
        "command",
        nargs="?",
        default="dashboard",
        choices=["setup", "seed", "test-insert", "scenario-a", "scenario-b", "scenarios", "dashboard", "all"],
        help="default: dashboard. setup=create tables+seed, seed=seed only, test-insert=smoke test, scenario-a/b, all",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress verbose CrewAI agent output (summary still printed)",
    )
    args = parser.parse_args(_cli_argv())
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
