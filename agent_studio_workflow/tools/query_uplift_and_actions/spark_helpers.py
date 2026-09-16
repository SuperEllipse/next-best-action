"""Spark / Iceberg helpers for Agent Studio custom tools."""

import glob
import os
from pathlib import Path

from pyspark.sql import SparkSession

ICEBERG_JAR_DEFAULT = (
    "/opt/spark/optional-lib/iceberg-spark-runtime-3.5_2.12-1.5.2.1.25.731.0-41.jar"
)
ICEBERG_DATABASE = "airline_irop"


def get_iceberg_warehouse_uri() -> str:
    uri = os.environ.get("ICEBERG_WAREHOUSE_URI", "").strip()
    if not uri:
        raise ValueError(
            "ICEBERG_WAREHOUSE_URI is not set. See project .env.example."
        )
    return uri
ICEBERG_NAMESPACE = f"spark_catalog.{ICEBERG_DATABASE}"

_spark = None


def resolve_iceberg_jar(jar_override: str = "") -> str:
    env_jar = (jar_override or os.environ.get("ICEBERG_JAR", "")).strip()
    if env_jar and Path(env_jar).exists():
        return env_jar
    if Path(ICEBERG_JAR_DEFAULT).exists():
        return ICEBERG_JAR_DEFAULT
    matches = sorted(glob.glob("/opt/spark/optional-lib/iceberg-spark-runtime*.jar"))
    if matches:
        return matches[-1]
    raise FileNotFoundError(
        "Iceberg jar not found. Set ICEBERG_JAR or install under /opt/spark/optional-lib/"
    )


def _iceberg_session_active(spark: SparkSession) -> bool:
    return "IcebergSparkSessionExtensions" in spark.conf.get("spark.sql.extensions", "")


def get_spark_session(app_name: str = "AgentStudioTool", jar_override: str = "") -> SparkSession:
    global _spark

    active = SparkSession.getActiveSession()
    if active is not None and _iceberg_session_active(active):
        _spark = active
        return _spark

    if _spark is not None and _iceberg_session_active(_spark):
        return _spark

    jar = resolve_iceberg_jar(jar_override)
    _spark = (
        SparkSession.builder.appName(app_name)
        .config("spark.hadoop.fs.s3a.s3guard.ddb.region", "us-east-2")
        .config("spark.yarn.access.hadoopFileSystems", get_iceberg_warehouse_uri())
        .config("spark.jars", jar)
        .config(
            "spark.sql.extensions",
            "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
        )
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.iceberg.spark.SparkSessionCatalog",
        )
        .config("spark.sql.catalog.local", "org.apache.iceberg.spark.SparkCatalog")
        .config("spark.sql.catalog.local.type", "hadoop")
        .config("spark.sql.catalog.spark_catalog.type", "hive")
        .getOrCreate()
    )
    return _spark


def collect_as_dicts(df) -> list:
    return [row.asDict(recursive=True) for row in df.collect()]


def sql_escape(value: str) -> str:
    return value.replace("'", "''")
