"""Lakeflow declarative pipeline: Portal BASE contracts, bronze -> silver.

bronze_contracts           streaming table. Auto Loader picks up every new contratos_YYYY.parquet dropped in the
                           landing volume, keeps all 39 source columns as text, and adds the file path and load time.
silver_contracts           materialized view, one typed row per contract (dedup + parsing in procurement.transforms).
silver_contract_awardees   materialized view, one row per awardee line, privacy-safe supplier key.
silver_location_lines      materialized view, one row per place-of-execution line.
silver_contracts_rejected  materialized view, the rows the quality rules keep out of silver, with the reason.

Data-quality rules are pipeline expectations, so the pipeline's event log and UI show how many rows passed and
failed each rule on every run. The gold layer (dimensions, fact, marts) is built by dbt in ../../dbt.

Configuration (set in resources/pipeline.yml):
    landing_path   UC volume path with the yearly Parquet files, e.g. /Volumes/workspace/raw/landing
    src_path       workspace folder that holds the procurement package (the bundle's src/)
"""

import sys

from pyspark import pipelines as dp
from pyspark.sql import functions as F

# The bundle syncs ../src to the workspace; put it on the path so the shared transforms import here.
sys.path.append(spark.conf.get("src_path"))  # noqa: F821  (spark is provided by the pipeline runtime)
from procurement import transforms as T  # noqa: E402

LANDING = spark.conf.get("landing_path")  # noqa: F821

# Rules a contract must pass to reach silver. expect_all_or_drop drops the row and counts it in the event log.
CONTRACT_RULES = {
    "contract_id_is_number": "contract_id IS NOT NULL",
    "has_a_date": "contract_date IS NOT NULL",
    "year_matches_file": "year(contract_date) = source_file_year",
}
# Rules that are only monitored: the row is kept and the share that fails shows in the pipeline metrics.
CONTRACT_WARNINGS = {
    "price_not_negative": "contract_price IS NULL OR contract_price >= 0",
    "cpv_code_present": "cpv_code IS NOT NULL",
    "entity_has_nif": "entity_key RLIKE '^[0-9]{9}$'",
    "base_price_plausible": "base_price IS NULL OR contract_value IS NULL OR base_price = 0 "
    "OR contract_value / base_price BETWEEN 0.2 AND 5",
}


@dp.table(
    name="bronze_contracts",
    comment="Raw Portal BASE contract rows, all columns as text, loaded incrementally by Auto Loader.",
    table_properties={"quality": "bronze"},
)
def bronze_contracts():
    return (
        spark.readStream.format("cloudFiles")  # noqa: F821
        .option("cloudFiles.format", "parquet")
        .option("cloudFiles.inferColumnTypes", "false")
        .option("pathGlobFilter", "contratos_*.parquet")
        .load(LANDING)
        .select(
            "*",
            F.col("_metadata.file_path").alias("_source_file"),
            F.current_timestamp().alias("_ingested_at"),
        )
    )


def _parsed_contracts():
    bronze = T.with_source_year(spark.read.table("bronze_contracts"))  # noqa: F821
    return T.parse_contracts(bronze)


@dp.materialized_view(
    name="silver_contracts",
    comment="One row per contract: deduplicated, typed and cleaned. Amounts in EUR without VAT.",
    table_properties={"quality": "silver"},
    cluster_by=["contract_date"],
)
@dp.expect_all_or_drop(CONTRACT_RULES)
@dp.expect_all(CONTRACT_WARNINGS)
def silver_contracts():
    return _parsed_contracts()


@dp.materialized_view(
    name="silver_contracts_rejected",
    comment="Contracts kept out of silver by a quality rule, with the rule that failed.",
    table_properties={"quality": "quarantine"},
)
def silver_contracts_rejected():
    df = _parsed_contracts()
    reason = F.coalesce(
        *[F.when(~F.expr(f"coalesce({rule}, false)"), F.lit(name)) for name, rule in CONTRACT_RULES.items()]
    )
    return df.withColumn("failed_rule", reason).where(F.col("failed_rule").isNotNull())


@dp.materialized_view(
    name="silver_contract_awardees",
    comment="One row per awardee line. supplier_key is the NIF for companies and WITHHELD-* for natural persons.",
    table_properties={"quality": "silver"},
)
@dp.expect_or_fail("awardee_has_key", "supplier_key IS NOT NULL")
def silver_contract_awardees():
    return T.parse_awardees(spark.read.table("silver_contracts"))  # noqa: F821


@dp.materialized_view(
    name="silver_location_lines",
    comment="One row per place-of-execution line of a contract: country and district as published.",
    table_properties={"quality": "silver"},
)
def silver_location_lines():
    return T.parse_location_lines(spark.read.table("silver_contracts"))  # noqa: F821
