"""Iceberg data access for Flask dashboard."""

from iceberg_tools import (
    get_execution_results_filtered,
    get_passengers_for_event,
)
from spark_session import ICEBERG_NAMESPACE, collect_as_dicts, get_spark_session

NS = ICEBERG_NAMESPACE


def fetch_execution_results(
    limit: int = 100,
    window: str = "1d",
    scenario: str | None = None,
    category: str = "all",
    since: str | None = None,
) -> list:
    return get_execution_results_filtered(
        window=window,
        scenario=scenario,
        category=category,
        since=since,
        limit=limit,
    )


def fetch_operational_events() -> list:
    spark = get_spark_session("Dashboard")
    df = spark.sql(f"SELECT * FROM {NS}.flight_operational_events ORDER BY event_timestamp DESC")
    return collect_as_dicts(df)


def fetch_chat_signals() -> list:
    spark = get_spark_session("Dashboard")
    df = spark.sql(f"SELECT * FROM {NS}.unstructured_chat_signals ORDER BY signal_timestamp DESC")
    return collect_as_dicts(df)


def fetch_uplift_by_customer(customer_id: str) -> list:
    spark = get_spark_session("Dashboard")
    df = spark.sql(
        f"SELECT * FROM {NS}.historical_uplift_experiments WHERE customer_id = '{customer_id}'"
    )
    return collect_as_dicts(df)


def fetch_affected_passengers() -> list:
    return get_passengers_for_event()
