"""PySpark / Iceberg session — matches code_sample/Iceberg_PySpark_Quickstart_ADLS.ipynb."""

import glob
import os
from pathlib import Path

from pyspark.sql import SparkSession

# Default from Quickstart; override with ICEBERG_JAR env if you use a different runtime jar
ICEBERG_JAR_DEFAULT = (
    "/opt/spark/optional-lib/iceberg-spark-runtime-3.5_2.12-1.5.2.1.25.731.0-41.jar"
)
ADLS_FILESYSTEM = "abfs://data@go01demoazure.dfs.core.windows.net/go01-az-dl"
ICEBERG_DATABASE = "airline_irop"
ICEBERG_NAMESPACE = f"spark_catalog.{ICEBERG_DATABASE}"

_spark = None


def resolve_iceberg_jar() -> str:
    """Use ICEBERG_JAR env, else Quickstart default, else newest runtime jar on disk."""
    env_jar = os.environ.get("ICEBERG_JAR", "").strip()
    if env_jar and Path(env_jar).exists():
        return env_jar
    if Path(ICEBERG_JAR_DEFAULT).exists():
        return ICEBERG_JAR_DEFAULT
    matches = sorted(glob.glob("/opt/spark/optional-lib/iceberg-spark-runtime*.jar"))
    if matches:
        return matches[-1]
    raise FileNotFoundError(
        f"Iceberg jar not found. Set ICEBERG_JAR or install under /opt/spark/optional-lib/"
    )


def _iceberg_session_active(spark: SparkSession) -> bool:
    return "IcebergSparkSessionExtensions" in spark.conf.get("spark.sql.extensions", "")


def get_spark_session(app_name: str = "IROP Demo") -> SparkSession:
    """Build or reuse SparkSession with Quickstart Iceberg configuration."""
    global _spark

    active = SparkSession.getActiveSession()
    if active is not None and _iceberg_session_active(active):
        _spark = active
        return _spark

    if _spark is not None and _iceberg_session_active(_spark):
        return _spark

    jar = resolve_iceberg_jar()
    print(f"Using Iceberg jar: {jar}")

    _spark = (
        SparkSession.builder.appName(app_name)
        .config("spark.hadoop.fs.s3a.s3guard.ddb.region", "us-east-2")
        .config("spark.yarn.access.hadoopFileSystems", ADLS_FILESYSTEM)
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


def ensure_database(spark: SparkSession) -> None:
    spark.sql(f"CREATE DATABASE IF NOT EXISTS {ICEBERG_DATABASE}")
    spark.sql(f"USE {ICEBERG_NAMESPACE}")


def verify_iceberg_runtime(spark: SparkSession | None = None) -> None:
    spark = spark or get_spark_session()
    sc = spark.sparkContext
    jar = resolve_iceberg_jar()
    print("--- Iceberg runtime check ---")
    print(f"  Spark version:        {spark.version}")
    print(f"  master:               {sc.master}")
    print(f"  applicationId:        {sc.applicationId}")
    print(f"  Jar:                  {jar}")
    print(f"  spark.jars:           {spark.conf.get('spark.jars', '')}")
    print(f"  spark.sql.extensions: {spark.conf.get('spark.sql.extensions', '')}")
    print(f"  ADLS filesystems:     {spark.conf.get('spark.yarn.access.hadoopFileSystems', '')}")
    if not _iceberg_session_active(spark):
        raise RuntimeError("Iceberg extensions not loaded.")
    spark.sql(f"USE {ICEBERG_NAMESPACE}")
    spark.sql("SHOW CURRENT NAMESPACE").show()
    print("-----------------------------")


def collect_as_dicts(df) -> list:
    """Collect Spark DataFrame rows as dicts (avoids toPandas/numpy compatibility issues)."""
    return [row.asDict(recursive=True) for row in df.collect()]


def stop_spark_session() -> None:
    global _spark
    active = SparkSession.getActiveSession()
    if active is not None:
        active.stop()
    _spark = None
