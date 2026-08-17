#!/usr/bin/env python3
"""
Minimal Iceberg INSERT test for airline_irop — mirrors Quickstart notebook flow.

Usage:
  python test_iceberg_insert.py

Optional:
  export ICEBERG_JAR=/opt/spark/optional-lib/your-runtime.jar
"""

import sys
import time

sys.path.insert(0, ".")

from spark_session import ICEBERG_DATABASE, ICEBERG_NAMESPACE, get_spark_session, verify_iceberg_runtime

TABLE = "flight_operational_events_smoke"
FULL_TABLE = f"{ICEBERG_NAMESPACE}.{TABLE}"


def main():
    print("=== Step 1: Spark session (Quickstart config) ===")
    spark = get_spark_session("IROP-Insert-Test")
    verify_iceberg_runtime(spark)

    print(f"\n=== Step 2: CREATE DATABASE + USE {ICEBERG_NAMESPACE} ===")
    spark.sql(f"CREATE DATABASE IF NOT EXISTS {ICEBERG_DATABASE}")
    spark.sql(f"USE {ICEBERG_NAMESPACE}")
    spark.sql("SHOW CURRENT NAMESPACE").show()

    print(f"\n=== Step 3: CREATE TABLE {TABLE} (short name after USE) ===")
    spark.sql(f"DROP TABLE IF EXISTS {TABLE}")
    spark.sql(f"""
        CREATE TABLE {TABLE} (
            event_id STRING,
            pnr STRING,
            customer_id STRING,
            flight_number STRING,
            itinerary STRING,
            orig_connection_mins INT,
            new_connection_mins INT,
            misconnect_risk BOOLEAN,
            event_timestamp TIMESTAMP
        ) USING iceberg
    """)
    print(f"Created {FULL_TABLE}")

    print(f"\n=== Step 4: INSERT (three-part name like Quickstart) ===")
    t0 = time.time()
    spark.sql(f"""
        INSERT INTO {FULL_TABLE} VALUES (
            'EVT-SMOKE-1', 'PNR-TEST', 'CUST-000', 'EK002', 'LHR-DXB-SIN',
            90, 35, TRUE, timestamp('2026-08-12 11:30:00')
        )
    """)
    elapsed = time.time() - t0
    print(f"INSERT completed in {elapsed:.1f}s")

    print("\n=== Step 5: Verify ===")
    spark.sql(f"SELECT COUNT(*) AS row_count FROM {FULL_TABLE}").show()
    spark.sql(f"SELECT * FROM {FULL_TABLE}").show(truncate=False)

    print("\n=== SUCCESS: Iceberg INSERT test passed ===")


if __name__ == "__main__":
    main()
