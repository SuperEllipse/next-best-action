"""Iceberg-only CrewAI tools — operational data, uplift, inventory, audit. No passenger profiles."""

import datetime
import json
from typing import Optional

from crewai.tools import tool

from spark_session import ICEBERG_NAMESPACE, collect_as_dicts, get_spark_session

NS = ICEBERG_NAMESPACE


def _spark():
    return get_spark_session("CrewAITools")


def _sql_escape(value: str) -> str:
    return value.replace("'", "''")


WINDOW_HOURS = {"1h": 1, "4h": 4, "1d": 24, "1w": 168}


def _parse_executed_at(value) -> Optional[datetime.datetime]:
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%a, %d %b %Y %H:%M:%S GMT", "%a, %d %b %Y %H:%M:%S %Z"):
        try:
            return datetime.datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        return datetime.datetime.fromisoformat(text.replace("Z", "+00:00").split("+")[0])
    except ValueError:
        return None


def _all_execution_rows() -> list:
    spark = _spark()
    return collect_as_dicts(
        spark.sql(f"SELECT * FROM {NS}.irop_execution_results ORDER BY executed_at DESC")
    )


def filter_rows_by_window(rows: list, window: str = "1d") -> list:
    hours = WINDOW_HOURS.get(window, 24)
    cutoff = datetime.datetime.now() - datetime.timedelta(hours=hours)
    filtered = []
    for row in rows:
        ts = _parse_executed_at(row.get("executed_at"))
        if ts is None or ts >= cutoff:
            filtered.append(row)
    return filtered


def filter_rows_by_since(rows: list, since: Optional[str]) -> list:
    if not since:
        return rows
    cutoff = _parse_executed_at(since)
    if cutoff is None:
        return rows
    filtered = []
    for row in rows:
        ts = _parse_executed_at(row.get("executed_at"))
        if ts is None or ts >= cutoff:
            filtered.append(row)
    return filtered


def _is_autorebook(action: str) -> bool:
    return "PROACTIVE_REBOOK" in (action or "")


def _is_hold_prompt(action: str) -> bool:
    return (action or "") == "HOLD_AND_PROMPT"


def _is_successful(row: dict) -> bool:
    status = (row.get("status") or "").upper()
    if "FAIL" in status:
        return False
    if status in {"SUCCESS", "CONFIRMED", "COMPLETED"}:
        return True
    return bool(row.get("success_flag"))


def filter_rows_by_category(rows: list, category: str = "all") -> list:
    cat = (category or "all").lower()
    if cat == "all":
        return rows
    if cat == "successful":
        return [r for r in rows if _is_successful(r)]
    if cat == "autorebook":
        return [r for r in rows if _is_autorebook(r.get("action_taken", ""))]
    if cat in {"hold_prompt", "hold-and-prompt", "hold"}:
        return [r for r in rows if _is_hold_prompt(r.get("action_taken", ""))]
    if cat == "staged":
        return [r for r in rows if r.get("status") == "STAGED_FOR_CONCIERGE"]
    if cat == "failed":
        return [
            r
            for r in rows
            if "FAIL" in (r.get("status") or "").upper() or not r.get("success_flag", True)
        ]
    return rows


def get_execution_results_filtered(
    window: str = "1d",
    scenario: Optional[str] = None,
    category: str = "all",
    since: Optional[str] = None,
    limit: int = 100,
) -> list:
    rows = _all_execution_rows()
    rows = filter_rows_by_window(rows, window)
    rows = filter_rows_by_since(rows, since)
    if scenario:
        rows = [r for r in rows if r.get("scenario") == scenario]
    rows = filter_rows_by_category(rows, category)
    return rows[:limit]


def make_case_id(customer_id: str) -> str:
    stamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    return f"CASE-{customer_id}-{stamp}"


def insert_execution_result(
    pnr: str,
    customer_id: str,
    scenario: str,
    action: str,
    reasoning: str,
    status: str,
    case_id: Optional[str] = None,
    success_flag: bool = True,
) -> dict:
    """Insert audit row (non-tool helper). Returns exec metadata."""
    spark = _spark()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    exec_id = f"EXEC-{now.replace(' ', '-').replace(':', '')}-{customer_id}"
    cid = case_id or make_case_id(customer_id)
    spark.sql(f"""
        INSERT INTO {NS}.irop_execution_results VALUES
        ('{exec_id}', '{cid}', '{pnr}', '{customer_id}', '{scenario}', '{_sql_escape(action)}',
         '{_sql_escape(reasoning)}', '{_sql_escape(status)}', {str(success_flag).lower()},
         cast('{now}' as timestamp))
    """)
    return {
        "exec_id": exec_id,
        "case_id": cid,
        "scenario": scenario,
        "action_taken": action,
        "status": status,
        "executed_at": now,
    }


def get_staging_for_customer(customer_id: str) -> Optional[dict]:
    """Latest Scenario A staging row awaiting concierge handoff."""
    spark = _spark()
    rows = collect_as_dicts(
        spark.sql(f"""
            SELECT * FROM {NS}.irop_execution_results
            WHERE customer_id = '{customer_id}'
              AND status = 'STAGED_FOR_CONCIERGE'
            ORDER BY executed_at DESC
            LIMIT 1
        """)
    )
    return rows[0] if rows else None


def has_open_staging(customer_id: str) -> bool:
    staging = get_staging_for_customer(customer_id)
    if not staging:
        return False
    case_id = staging.get("case_id")
    spark = _spark()
    completed = collect_as_dicts(
        spark.sql(f"""
            SELECT COUNT(*) AS c FROM {NS}.irop_execution_results
            WHERE case_id = '{case_id}'
              AND scenario = 'PULL_CONCIERGE'
              AND status = 'SUCCESS'
        """)
    )
    return completed[0]["c"] == 0


def place_inventory_holds(pnr: str, flights: tuple[str, ...] = ("EK372", "EK380")) -> list:
    """Mark alternate flights as HELD in Iceberg inventory."""
    spark = _spark()
    flight_list = ", ".join(f"'{f}'" for f in flights)
    spark.sql(f"""
        UPDATE {NS}.concierge_inventory_lookup
        SET hold_status = 'HELD', inventory_status = 'AVAILABLE'
        WHERE pnr = '{pnr}' AND alternate_flight IN ({flight_list})
    """)
    return collect_as_dicts(
        spark.sql(f"""
            SELECT * FROM {NS}.concierge_inventory_lookup
            WHERE pnr = '{pnr}' AND alternate_flight IN ({flight_list})
        """)
    )


def confirm_inventory_choice(
    pnr: str,
    chosen_flight: str,
    release_flights: tuple[str, ...] = ("EK380",),
) -> list:
    """Confirm chosen flight hold and release others."""
    spark = _spark()
    spark.sql(f"""
        UPDATE {NS}.concierge_inventory_lookup
        SET hold_status = 'CONFIRMED', inventory_status = 'CONFIRMED'
        WHERE pnr = '{pnr}' AND alternate_flight = '{chosen_flight}'
    """)
    if release_flights:
        release_list = ", ".join(f"'{f}'" for f in release_flights)
        spark.sql(f"""
            UPDATE {NS}.concierge_inventory_lookup
            SET hold_status = 'RELEASED'
            WHERE pnr = '{pnr}' AND alternate_flight IN ({release_list})
        """)
    return collect_as_dicts(
        spark.sql(f"SELECT * FROM {NS}.concierge_inventory_lookup WHERE pnr = '{pnr}'")
    )


def get_inventory_for_pnr(pnr: str) -> list:
    spark = _spark()
    return collect_as_dicts(
        spark.sql(f"SELECT * FROM {NS}.concierge_inventory_lookup WHERE pnr = '{pnr}' ORDER BY departure_time")
    )


def compute_execution_stats(window: str = "1d") -> dict:
    """Executive summary statistics from audit log for the selected time window."""
    rows = filter_rows_by_window(_all_execution_rows(), window)
    total = len(rows)
    staged = [r for r in rows if r.get("status") == "STAGED_FOR_CONCIERGE"]
    success = [r for r in rows if _is_successful(r)]
    hold_prompt = [r for r in rows if _is_hold_prompt(r.get("action_taken", ""))]
    auto_rebook = [r for r in rows if _is_autorebook(r.get("action_taken", ""))]
    failed = [r for r in rows if "FAIL" in (r.get("status") or "").upper() or not r.get("success_flag", True)]

    case_ids_staged = {r.get("case_id") for r in staged if r.get("case_id")}
    case_ids_completed = {
        r.get("case_id")
        for r in success
        if r.get("scenario") == "PULL_CONCIERGE" and r.get("case_id")
    }
    converted = len(case_ids_staged & case_ids_completed)
    staged_count = len(case_ids_staged)

    return {
        "total_audit_rows": total,
        "staged_for_concierge": len(staged),
        "successful_resolutions": len(success),
        "hold_and_prompt_actions": len(hold_prompt),
        "proactive_rebook_actions": len(auto_rebook),
        "failed_actions": len(failed),
        "staged_to_completed_conversion_rate": round(converted / staged_count, 2) if staged_count else 0.0,
        "by_scenario": _count_field(rows, "scenario"),
        "by_status": _count_field(rows, "status"),
        "by_action": _count_field(rows, "action_taken"),
        "window": window,
    }


def _count_field(rows: list, field: str) -> dict:
    counts: dict = {}
    for row in rows:
        key = row.get(field) or "UNKNOWN"
        counts[key] = counts.get(key, 0) + 1
    return counts


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
    """Queries alternate flights, seats, lounge and quiet-pod availability from Iceberg inventory."""
    inventory = get_inventory_for_pnr(pnr)
    return f"Inventory Options Available: {inventory}"


@tool("Place Inventory Holds on Alternate Flights")
def place_flight_holds(pnr: str) -> str:
    """Places HELD status on pre-identified alternate flights for a passenger PNR in Iceberg inventory."""
    held = place_inventory_holds(pnr)
    return f"Inventory holds placed: {held}"


@tool("Read Scenario A Staging Record")
def read_push_staging(customer_id: str) -> str:
    """Reads the latest STAGED_FOR_CONCIERGE audit record for handoff from Push to Concierge."""
    staging = get_staging_for_customer(customer_id)
    if not staging:
        return "No staging record found — Scenario A push may not have run yet."
    return f"Push staging record: {staging}"


def append_chat_signal(
    customer_id: str,
    pnr: str,
    message_text: str,
    sentiment: str = "CALM",
) -> dict:
    """Persist a concierge chat turn to unstructured_chat_signals."""
    spark = _spark()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    signal_id = f"SIG-{now.replace(' ', '-').replace(':', '')}-{customer_id}"
    spark.sql(f"""
        INSERT INTO {NS}.unstructured_chat_signals VALUES
        ('{signal_id}', '{pnr}', '{customer_id}', cast('{now}' as timestamp),
         '{_sql_escape(sentiment)}', '{_sql_escape(message_text)}')
    """)
    return {"signal_id": signal_id, "message_text": message_text, "signal_timestamp": now}


@tool("Append Passenger Chat Signal")
def append_chat_signal_tool(
    customer_id: str,
    pnr: str,
    message_text: str,
    sentiment: str = "CALM",
) -> str:
    """Writes the latest passenger chat message to Iceberg unstructured_chat_signals."""
    meta = append_chat_signal(customer_id, pnr, message_text, sentiment)
    return f"Chat signal appended: {meta}"


def get_prior_concierge_audit(customer_id: str, case_id: str = "") -> list:
    spark = _spark()
    where = f"customer_id = '{customer_id}' AND scenario = 'PULL_CONCIERGE'"
    if case_id:
        where += f" AND case_id = '{_sql_escape(case_id)}'"
    return collect_as_dicts(
        spark.sql(f"""
            SELECT * FROM {NS}.irop_execution_results
            WHERE {where}
            ORDER BY executed_at DESC
            LIMIT 5
        """)
    )


@tool("Read Prior Concierge Audit Decisions")
def read_prior_concierge_audit(customer_id: str, case_id: str = "") -> str:
    """Returns prior Scenario B fulfillment rows for this passenger (multi-turn context)."""
    rows = get_prior_concierge_audit(customer_id, case_id)
    if not rows:
        return "No prior concierge audit rows for this passenger."
    return f"Prior concierge decisions: {rows}"


@tool("Confirm Passenger Flight and Amenity Choice")
def confirm_passenger_choice(pnr: str, chosen_flight: str, release_flights: str = "") -> str:
    """
    Confirms the chosen alternate flight in Iceberg inventory and releases other holds.
    release_flights: comma-separated flight codes to release (e.g. 'EK380' or 'EK372').
    """
    release = tuple(f.strip() for f in release_flights.split(",") if f.strip()) if release_flights else ()
    if not release:
        all_flights = [r.get("alternate_flight") for r in get_inventory_for_pnr(pnr)]
        release = tuple(f for f in all_flights if f and f != chosen_flight)
    updated = confirm_inventory_choice(pnr, chosen_flight, release_flights=release)
    return f"Confirmed {chosen_flight}; inventory now: {updated}"


@tool("Re-hold Alternate Flights")
def re_hold_alternate_flights(pnr: str, flights: str = "EK372,EK380") -> str:
    """Re-applies HELD status on named alternate flights (e.g. after a change of mind)."""
    flight_tuple = tuple(f.strip() for f in flights.split(",") if f.strip())
    held = place_inventory_holds(pnr, flights=flight_tuple)
    return f"Re-held flights {flight_tuple}: {held}"


@tool("Log Final Execution Result")
def log_execution_result(
    pnr: str,
    customer_id: str,
    scenario: str,
    action: str,
    reasoning: str,
    status: str,
    case_id: str = "",
) -> str:
    """Writes the agent decision and explanation to the Iceberg irop_execution_results audit table."""
    meta = insert_execution_result(
        pnr=pnr,
        customer_id=customer_id,
        scenario=scenario,
        action=action,
        reasoning=reasoning,
        status=status,
        case_id=case_id or None,
    )
    return f"Logged execution {meta['exec_id']} (case {meta['case_id']}) to Iceberg audit table."


def get_execution_results(limit: int = 50) -> list:
    """Read audit results for dashboard (non-tool helper)."""
    return get_execution_results_filtered(window="1w", category="all", limit=limit)


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
