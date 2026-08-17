"""Iceberg-only CrewAI tools — operational data, uplift, inventory, audit. No passenger profiles."""

import datetime

from crewai.tools import tool

from spark_session import ICEBERG_NAMESPACE, collect_as_dicts, get_spark_session

NS = ICEBERG_NAMESPACE


def _spark():
    return get_spark_session("CrewAITools")


@tool("Fetch Operational Events and Chat Signals")
def fetch_operational_context(customer_id: str) -> str:
    """Retrieves flight disruption events and unstructured chat signals from Iceberg for a passenger."""
    spark = _spark()
    events = collect_as_dicts(
        spark.sql(
            f"SELECT * FROM {NS}.flight_operational_events WHERE customer_id = '{customer_id}'"
        )
    )
    signals = collect_as_dicts(
        spark.sql(
            f"SELECT * FROM {NS}.unstructured_chat_signals WHERE customer_id = '{customer_id}'"
        )
    )
    return f"Operational Events: {events}\nChat Signals: {signals}"


@tool("Query Uplift History and Action Shelf")
def query_uplift_and_actions(customer_id: str) -> str:
    """Retrieves historical uplift experiments and available gesture actions from Iceberg."""
    spark = _spark()
    uplift = collect_as_dicts(
        spark.sql(
            f"SELECT * FROM {NS}.historical_uplift_experiments WHERE customer_id = '{customer_id}'"
        )
    )
    actions = collect_as_dicts(spark.sql(f"SELECT * FROM {NS}.action_gesture_shelf"))
    return f"Uplift History: {uplift}\nAction Shelf: {actions}"


@tool("Query Live Flight and Lounge Inventory")
def query_inventory(pnr: str) -> str:
    """Queries alternate flights, seats, and lounge availability from Iceberg inventory."""
    spark = _spark()
    inventory = collect_as_dicts(
        spark.sql(f"SELECT * FROM {NS}.concierge_inventory_lookup WHERE pnr = '{pnr}'")
    )
    return f"Inventory Options Available: {inventory}"


@tool("Log Final Execution Result")
def log_execution_result(
    pnr: str,
    customer_id: str,
    scenario: str,
    action: str,
    reasoning: str,
    status: str,
) -> str:
    """Writes the agent decision and explanation to the Iceberg irop_execution_results audit table."""
    spark = _spark()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    exec_id = f"EXEC-{now.replace(' ', '-').replace(':', '')}-{customer_id}"
    spark.sql(f"""
        INSERT INTO {NS}.irop_execution_results VALUES
        ('{exec_id}', '{pnr}', '{customer_id}', '{scenario}', '{action}',
         '{reasoning.replace("'", "''")}', '{status}', true, cast('{now}' as timestamp))
    """)
    return f"Logged execution {exec_id} to Iceberg audit table."


def get_execution_results(limit: int = 50) -> list:
    """Read audit results for dashboard (non-tool helper)."""
    spark = _spark()
    df = spark.sql(
        f"SELECT * FROM {NS}.irop_execution_results ORDER BY executed_at DESC LIMIT {limit}"
    )
    return collect_as_dicts(df)


def get_passengers_for_event(event_id: str = "EVT-9001") -> list:
    """Return all passengers affected by a misconnect event."""
    spark = _spark()
    df = spark.sql(f"""
        SELECT DISTINCT customer_id, pnr, event_id, new_connection_mins, misconnect_risk
        FROM {NS}.flight_operational_events
        WHERE misconnect_risk = true
          AND event_id LIKE 'EVT-900%'
    """)
    return collect_as_dicts(df)
