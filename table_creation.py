"""Create Iceberg operational tables — Quickstart pattern (USE db + CREATE TABLE ... USING iceberg)."""

from spark_session import ICEBERG_NAMESPACE, ensure_database, get_spark_session

TABLES = {
    "flight_operational_events": """
        event_id STRING,
        pnr STRING,
        customer_id STRING,
        flight_number STRING,
        itinerary STRING,
        orig_connection_mins INT,
        new_connection_mins INT,
        misconnect_risk BOOLEAN,
        event_timestamp TIMESTAMP
    """,
    "unstructured_chat_signals": """
        signal_id STRING,
        pnr STRING,
        customer_id STRING,
        signal_timestamp TIMESTAMP,
        sentiment STRING,
        message_text STRING
    """,
    "action_gesture_shelf": """
        action_id STRING,
        action_code STRING,
        action_description STRING,
        cost_usd DOUBLE,
        requires_human BOOLEAN,
        policy_notes STRING
    """,
    "historical_uplift_experiments": """
        experiment_id STRING,
        customer_id STRING,
        archetype STRING,
        action_id STRING,
        gesture_applied BOOLEAN,
        uplift_score DOUBLE
    """,
    "concierge_inventory_lookup": """
        lookup_id STRING,
        pnr STRING,
        alternate_flight STRING,
        departure_time TIMESTAMP,
        arrival_time TIMESTAMP,
        seats_available INT,
        lounge_available BOOLEAN,
        inventory_status STRING,
        overnight_required BOOLEAN,
        destination STRING,
        hold_status STRING,
        hold_expires_at TIMESTAMP,
        amenity_type STRING,
        amenity_id STRING,
        amenity_status STRING
    """,
    "irop_execution_results": """
        exec_id STRING,
        case_id STRING,
        pnr STRING,
        customer_id STRING,
        scenario STRING,
        action_taken STRING,
        reasoning STRING,
        status STRING,
        success_flag BOOLEAN,
        executed_at TIMESTAMP
    """,
}


def create_tables():
    spark = get_spark_session("IROP-TableCreation")
    ensure_database(spark)

    for table, schema in TABLES.items():
        spark.sql(f"DROP TABLE IF EXISTS {table}")
        spark.sql(f"CREATE TABLE {table} ({schema}) USING iceberg")
        print(f"Created {ICEBERG_NAMESPACE}.{table}")


if __name__ == "__main__":
    create_tables()
