"""Run the whole lakehouse locally on Spark, without Databricks, and check it against the DuckDB build.

    python scripts/run_local.py --raw ../data/raw            # silver with PySpark, then dbt (target local)

1. Reads the yearly Parquet files (the same files the pipeline's Auto Loader ingests).
2. Applies the silver transformations from src/procurement/transforms.py (the code the Lakeflow pipeline runs).
3. Saves silver as tables in a local Hive metastore (./.local_spark) and runs `dbt build --target local`, which
   builds the gold layer with the same SQL models as on Databricks and runs every dbt test, including the
   migration check against the DuckDB totals.

Local Spark has no Delta, Auto Loader or expectations; the pipeline file itself only runs on Databricks.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
WAREHOUSE = ROOT / ".local_spark"


def spark_session():
    from pyspark.sql import SparkSession

    return (
        SparkSession.builder.master("local[*]")
        .appName("procurement-local")
        .config("spark.driver.memory", os.environ.get("SPARK_DRIVER_MEMORY", "8g"))
        .config("spark.sql.shuffle.partitions", "16")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.ansi.enabled", "true")
        .enableHiveSupport()
        .getOrCreate()
    )


def build_silver(raw: Path) -> None:
    from pyspark.sql import functions as F

    from procurement import transforms as T

    os.chdir(WAREHOUSE)  # metastore_db/ and spark-warehouse/ live here, where dbt finds them too
    spark = spark_session()
    spark.sql("create database if not exists silver")
    bronze = spark.read.parquet(str(raw / "contratos_*.parquet")).withColumn("_source_file", F.input_file_name())
    bronze = T.with_source_year(bronze)
    print(f"bronze rows: {bronze.count():,}")

    contracts = T.parse_contracts(bronze).cache()
    contracts.write.mode("overwrite").saveAsTable("silver.silver_contracts")
    contracts = spark.read.table("silver.silver_contracts")
    T.parse_awardees(contracts).write.mode("overwrite").saveAsTable("silver.silver_contract_awardees")
    T.parse_location_lines(contracts).write.mode("overwrite").saveAsTable("silver.silver_location_lines")

    for t in ("silver_contracts", "silver_contract_awardees", "silver_location_lines"):
        print(f"silver.{t}: {spark.read.table('silver.' + t).count():,} rows")
    spark.stop()


def run_dbt(args: list[str]) -> int:
    env = {**os.environ, "DBT_PROFILES_DIR": str(ROOT / "dbt")}
    # dbt-spark's session method reuses the Hive metastore above when started from this folder.
    cmd = ["dbt", *args, "--target", "local", "--project-dir", str(ROOT / "dbt")]
    print("$", " ".join(cmd))
    return subprocess.call(cmd, cwd=WAREHOUSE, env=env)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--raw", type=Path, default=ROOT.parent / "data" / "raw")
    p.add_argument("--skip-silver", action="store_true")
    p.add_argument("--silver-only", action="store_true", help=argparse.SUPPRESS)
    a = p.parse_args()
    WAREHOUSE.mkdir(exist_ok=True)
    if a.silver_only:
        build_silver(a.raw.resolve())
        return
    if not a.skip_silver:
        # separate process: the local metastore (Derby) allows one JVM at a time, and dbt starts its own
        rc = subprocess.call([sys.executable, __file__, "--silver-only", "--raw", str(a.raw.resolve())])
        if rc:
            sys.exit(rc)
    sys.exit(run_dbt(["build"]))


if __name__ == "__main__":
    main()
