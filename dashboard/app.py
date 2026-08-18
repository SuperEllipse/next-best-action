"""Flask dashboard for IROP agentic demo."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from env_config import get_env_status, load_project_env

load_project_env()

from flask import Flask, jsonify, render_template, request

from choice_oriented_passenger import DEFAULT_PUSH_PROMPT, DEFAULT_SCRIPTED_CHAT
from dashboard.services.iceberg_service import (
    fetch_affected_passengers,
    fetch_execution_results,
    fetch_operational_events,
    fetch_uplift_by_customer,
)
from dashboard.services.mcp_service import DEMO_PASSENGERS, check_mcp_health, get_passenger_profile
from dashboard.services.scenario_service import (
    get_executive_stats,
    get_rules_contrast,
    trigger_scenario_a,
    trigger_scenario_b,
)


def _static_version() -> str:
    static_dir = os.path.join(os.path.dirname(__file__), "static", "js")
    app_js = os.path.join(static_dir, "app.js")
    try:
        return str(int(os.path.getmtime(app_js)))
    except OSError:
        return "1"


def create_app() -> Flask:
    app = Flask(__name__)

    @app.context_processor
    def inject_static_version():
        return {"static_version": _static_version()}

    @app.route("/")
    @app.route("/executive")
    def executive():
        return render_template(
            "executive.html",
            passengers=DEMO_PASSENGERS,
            customer_id="CUST-404",
            push_prompt=DEFAULT_PUSH_PROMPT,
            scripted_chat=DEFAULT_SCRIPTED_CHAT,
        )

    @app.route("/concierge")
    def concierge():
        return render_template(
            "concierge.html",
            customer_id="CUST-404",
            pnr="PNR-404D",
            push_prompt=DEFAULT_PUSH_PROMPT,
            scripted_chat=DEFAULT_SCRIPTED_CHAT,
        )

    @app.route("/api/health")
    def health():
        env_status = get_env_status()
        mcp = check_mcp_health()
        return jsonify({
            "flask": "ok",
            "mcp": mcp,
            "env": env_status,
            "ready_for_scenarios": env_status["openai_api_key_set"] and env_status["snowflake_pat_set"],
        })

    @app.route("/api/execution-results")
    def api_execution_results():
        limit = request.args.get("limit", 100, type=int)
        window = request.args.get("window", "1d")
        scenario = request.args.get("scenario")
        category = request.args.get("filter", request.args.get("category", "all"))
        since = request.args.get("since")
        return jsonify(
            fetch_execution_results(
                limit=limit,
                window=window,
                scenario=scenario or None,
                category=category,
                since=since,
            )
        )

    @app.route("/api/execution-stats")
    def api_execution_stats():
        window = request.args.get("window", "1d")
        return jsonify(get_executive_stats(window=window))

    @app.route("/api/rules-contrast")
    def api_rules_contrast():
        return jsonify(get_rules_contrast())

    @app.route("/api/operational-events")
    def api_operational_events():
        return jsonify(fetch_operational_events())

    @app.route("/api/passenger/<customer_id>")
    def api_passenger(customer_id):
        try:
            profile = get_passenger_profile(customer_id)
            uplift = fetch_uplift_by_customer(customer_id)
            return jsonify({"customer_id": customer_id, "profile": profile, "uplift": uplift})
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.route("/api/affected-passengers")
    def api_affected_passengers():
        return jsonify(fetch_affected_passengers())

    @app.route("/api/scenario-a", methods=["POST"])
    def api_scenario_a():
        try:
            verbose = request.json.get("verbose", False) if request.is_json else False
            return jsonify(trigger_scenario_a(verbose=verbose))
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.route("/api/scenario-b", methods=["POST"])
    def api_scenario_b():
        try:
            body = request.get_json(silent=True) or {}
            return jsonify(
                trigger_scenario_b(
                    verbose=body.get("verbose", False),
                    chat_message=body.get("chat_message"),
                    chat_history=body.get("chat_history"),
                )
            )
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    return app


def get_app_server_config() -> tuple[str, int]:
    port = int(os.environ["CDSW_APP_PORT"])
    return "127.0.0.1", port


def run_server(debug: bool = False) -> None:
    host, port = get_app_server_config()
    create_app().run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    run_server(debug=True)
