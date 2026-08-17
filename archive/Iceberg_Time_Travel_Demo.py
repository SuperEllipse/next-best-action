"""
Apache Iceberg Table Creation & Time Travel Demo

Creates an Iceberg table on ADLS Gen2 using the shared Hive Metastore in the
go01demoazure environment, then demonstrates time travel queries.

Prerequisites: Enable the Spark Add-on on this CML session before running.

ADLS warehouse locations (from Hive Metastore):
  - Managed:  abfs://data@go01demoazure.dfs.core.windows.net/warehouse/tablespace/managed/hive
  - External: abfs://data@go01demoazure.dfs.core.windows.net/warehouse/tablespace/external/hive

Important: Do NOT add spark.jars.packages for Iceberg. The runtime ships
iceberg-spark-runtime-3.5_2.12 (v1.5.2) under /opt/spark/optional-lib/.
"""

import time
from datetime import datetime, timezone

import cml.data_v1 as cmldata
from pyspark.sql import SparkSession

# ---------------------------------------------------------------------------
# 1. Create Spark Session (via CML connection)
# ---------------------------------------------------------------------------

CONNECTION_NAME = "go01-az-dl"
conn = cmldata.get_connection(CONNECTION_NAME)
spark = conn.get_spark_session()

print(f"Spark version : {spark.version}")
print(f"Application ID: {spark.sparkContext.applicationId}")

# ---------------------------------------------------------------------------
# Alternative: Manual SparkSession (uncomment if not using CML connection)
# ---------------------------------------------------------------------------
#
# ADLS_ACCOUNT = "go01demoazure"
# ADLS_CONTAINER = "data"
# ADLS_BASE = f"abfs://{ADLS_CONTAINER}@{ADLS_ACCOUNT}.dfs.core.windows.net"
# MANAGED_WAREHOUSE = f"{ADLS_BASE}/warehouse/tablespace/managed/hive"
# EXTERNAL_WAREHOUSE = f"{ADLS_BASE}/warehouse/tablespace/external/hive"
#
# iceberg_jars = ",".join([
#     "/opt/spark/optional-lib/iceberg-spark-runtime.jar",
#     "/opt/spark/optional-lib/iceberg-hive-runtime.jar",
#     "/opt/spark/optional-lib/hive-warehouse-connector-assembly.jar",
# ])
#
# spark = (
#     SparkSession.builder
#     .appName("Iceberg Time Travel Demo")
#     .config("spark.jars", iceberg_jars)
#     .config("spark.yarn.access.hadoopFileSystems", EXTERNAL_WAREHOUSE)
#     .config("spark.sql.extensions",
#             "com.qubole.spark.hiveacid.HiveAcidAutoConvertExtension,"
#             "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
#     .config("spark.sql.catalog.spark_catalog", "org.apache.iceberg.spark.SparkSessionCatalog")
#     .config("spark.sql.catalog.spark_catalog.type", "hive")
#     .config("spark.sql.catalog.spark_catalog.warehouse", MANAGED_WAREHOUSE)
#     .config("spark.hadoop.hive.metastore.warehouse.dir", MANAGED_WAREHOUSE)
#     .config("spark.hadoop.hive.metastore.warehouse.external.dir", EXTERNAL_WAREHOUSE)
#     .config("spark.hadoop.iceberg.engine.hive.enabled", "true")
#     .getOrCreate()
# )

# ---------------------------------------------------------------------------
# 2. Configuration Constants
# ---------------------------------------------------------------------------

ADLS_ACCOUNT = "go01demoazure"
ADLS_CONTAINER = "data"
ADLS_BASE = f"abfs://{ADLS_CONTAINER}@{ADLS_ACCOUNT}.dfs.core.windows.net"

MANAGED_WAREHOUSE = f"{ADLS_BASE}/warehouse/tablespace/managed/hive"
EXTERNAL_WAREHOUSE = f"{ADLS_BASE}/warehouse/tablespace/external/hive"

DB_NAME = "iceberg_demo"
TABLE_NAME = "orders"
FULL_TABLE = f"spark_catalog.{DB_NAME}.{TABLE_NAME}"

print(f"Managed warehouse : {MANAGED_WAREHOUSE}")
print(f"External warehouse: {EXTERNAL_WAREHOUSE}")
print(f"Target table      : {FULL_TABLE}")

# ---------------------------------------------------------------------------
# 3. Verify Hive Metastore Connectivity
# ---------------------------------------------------------------------------

spark.sql("SHOW DATABASES").show(20, truncate=False)

# ---------------------------------------------------------------------------
# 4. Create Database and Iceberg Table
# ---------------------------------------------------------------------------

spark.sql(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
spark.sql(f"USE {DB_NAME}")
spark.sql(f"DROP TABLE IF EXISTS {FULL_TABLE}")

spark.sql(f"""
    CREATE TABLE {TABLE_NAME} (
        order_id   BIGINT,
        customer   STRING,
        amount     DOUBLE,
        order_date STRING
    )
    USING iceberg
    TBLPROPERTIES ('format-version'='2')
""")

print("Iceberg table created.")

spark.sql(f"DESCRIBE EXTENDED {TABLE_NAME}").filter(
    "col_name IN ('Location', 'Provider', 'Table Properties')"
).show(truncate=False)

# Optional: external Iceberg table under the external warehouse
# EXTERNAL_TABLE = f"{EXTERNAL_WAREHOUSE}/{DB_NAME}.db/orders_external"
# spark.sql("DROP TABLE IF EXISTS orders_external")
# spark.sql(f"""
#     CREATE TABLE orders_external (
#         order_id BIGINT, customer STRING, amount DOUBLE
#     )
#     USING iceberg
#     LOCATION '{EXTERNAL_TABLE}'
# """)

# ---------------------------------------------------------------------------
# 5. Insert Data — Create Multiple Snapshots
# ---------------------------------------------------------------------------

spark.sql(f"""
    INSERT INTO {TABLE_NAME} VALUES
        (1, 'Alice',  99.50,  '2026-01-15'),
        (2, 'Bob',   150.00,  '2026-01-16'),
        (3, 'Carol',  75.25,  '2026-01-17')
""")
print("Snapshot 1 committed (3 rows)")

time.sleep(3)
travel_timestamp = int(time.time())
time.sleep(2)

spark.sql(f"""
    INSERT INTO {TABLE_NAME} VALUES
        (4, 'Dave', 200.00, '2026-01-18'),
        (5, 'Eve',  125.75, '2026-01-19')
""")
print("Snapshot 2 committed (5 rows total)")

spark.sql(f"DELETE FROM {TABLE_NAME} WHERE order_id = 2")
spark.sql(f"INSERT INTO {TABLE_NAME} VALUES (2, 'Bob (updated)', 175.00, '2026-01-20')")
print("Snapshot 3 committed (Bob updated)")

# ---------------------------------------------------------------------------
# 6. Query Current Data
# ---------------------------------------------------------------------------

print("=== Current table (latest snapshot) ===")
spark.sql(f"SELECT * FROM {TABLE_NAME} ORDER BY order_id").show()

# ---------------------------------------------------------------------------
# 7. Inspect Snapshots (Table History)
# ---------------------------------------------------------------------------

print("=== Snapshot history ===")
spark.sql(f"""
    SELECT snapshot_id, committed_at, operation, summary
    FROM {TABLE_NAME}.snapshots
    ORDER BY committed_at
""").show(truncate=False)

spark.read.format("iceberg").load(f"{FULL_TABLE}.history").show(truncate=False)

# ---------------------------------------------------------------------------
# 8. Time Travel
# ---------------------------------------------------------------------------

# 8a. as-of-timestamp
print(f"Traveling back to timestamp: {travel_timestamp} ({travel_timestamp * 1000} ms)")
print("Expected: 3 rows (Alice, Bob, Carol) — before Dave and Eve were added\n")

df_past = (
    spark.read
    .option("as-of-timestamp", travel_timestamp * 1000)
    .format("iceberg")
    .load(FULL_TABLE)
)
df_past.orderBy("order_id").show()

# 8b. snapshot-id
first_snapshot = (
    spark.sql(f"SELECT snapshot_id FROM {TABLE_NAME}.snapshots ORDER BY committed_at LIMIT 1")
    .collect()[0].snapshot_id
)
print(f"First snapshot ID: {first_snapshot}")
print("Expected: 3 rows from the initial INSERT\n")

(
    spark.read
    .option("snapshot-id", first_snapshot)
    .format("iceberg")
    .load(FULL_TABLE)
    .orderBy("order_id")
    .show()
)

# 8c. SQL TIMESTAMP AS OF
ts_str = datetime.fromtimestamp(travel_timestamp, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
print(f"SQL time travel as of: {ts_str}\n")

spark.sql(f"""
    SELECT * FROM {TABLE_NAME}
    TIMESTAMP AS OF '{ts_str}'
    ORDER BY order_id
""").show()

# ---------------------------------------------------------------------------
# 9. Compare Snapshots Side by Side
# ---------------------------------------------------------------------------

current_count = spark.sql(f"SELECT COUNT(*) AS cnt FROM {TABLE_NAME}").collect()[0].cnt
past_count = df_past.count()

print(f"Current snapshot row count : {current_count}")
print(f"Historical snapshot count  : {past_count}")
print(f"Rows added since time-travel point: {current_count - past_count}")

# ---------------------------------------------------------------------------
# 10. Cleanup (optional — uncomment to run)
# ---------------------------------------------------------------------------

# spark.sql(f"DROP TABLE IF EXISTS {FULL_TABLE}")
# spark.sql(f"DROP DATABASE IF EXISTS {DB_NAME} CASCADE")
# spark.stop()
# print("Cleaned up.")
