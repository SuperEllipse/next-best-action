"""Flask dashboard for IROP agentic demo."""

import os
import sys

# Project root on path + load .env for Snowflake/OpenAI keys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from env_config import load_project_env

load_project_env()

from flask import Flask, jsonify, render_template, request

from dashboard.services.iceberg_service import (
    fetch_affected_passengers,
    fetch_execution_results,
    fetch_operational_events,
    fetch_uplift_by_customer,
)
from dashboard.services.mcp_service import DEMO_PASSENGERS, check_mcp_health, get_passenger_profile
from dashboard.services.scenario_service import trigger_scenario_a, trigger_scenario_b


def create_app() -> Flask:
    app = Flask(__name__)

    @app.route("/")
    @app.route("/executive")
    def executive():
        return render_template(
            "executive.html",
            passengers=DEMO_PASSENGERS,
        )

    @app.route("/concierge")
    def concierge():
        return render_template("concierge.html", customer_id="CUST-404", pnr="PNR-404D")

    @app.route("/api/health")
    def health():
        return jsonify({"flask": "ok", "mcp": check_mcp_health()})

    @app.route("/api/execution-results")
    def api_execution_results():
        limit = request.args.get("limit", 50, type=int)
        return jsonify(fetch_execution_results(limit))

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
            return jsonify(trigger_scenario_a())
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.route("/api/scenario-b", methods=["POST"])
    def api_scenario_b():
        try:
            return jsonify(trigger_scenario_b())
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    return app


def get_app_server_config() -> tuple[str, int]:
    """Cloudera AI embedded web apps must bind to CDSW_APP_PORT on 127.0.0.1."""
    port = int(os.environ["CDSW_APP_PORT"])
    return "127.0.0.1", port


def run_server(debug: bool = False) -> None:
    host, port = get_app_server_config()
    create_app().run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    run_server(debug=True)
