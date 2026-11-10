# Databricks notebook source
# MAGIC %md
# MAGIC # Portugal public procurement on a lakehouse: a guided tour
# MAGIC
# MAGIC 1.55 million contracts from Portal BASE (IMPIC), 2019 to October 2026, moved from a DuckDB project to
# MAGIC Databricks. This notebook walks through each layer and checks the numbers.
# MAGIC
# MAGIC | Layer | Built by | Tables |
# MAGIC |---|---|---|
# MAGIC | Bronze | Lakeflow pipeline, Auto Loader | `silver.bronze_contracts` (raw text, one row per source row) |
# MAGIC | Silver | Lakeflow pipeline, PySpark (`src/procurement/transforms.py`) + expectations | `silver_contracts`, `silver_contract_awardees`, `silver_location_lines`, `silver_contracts_rejected` |
# MAGIC | Gold | dbt-databricks (`dbt/`) + tests | `gold.fct_contracts`, dimensions, marts, `contracts_enriched` |

# COMMAND ----------

CATALOG = "workspace"
spark.sql(f"USE CATALOG {CATALOG}")

# COMMAND ----------

# MAGIC %md ## 1. Row counts through the layers

# COMMAND ----------

counts = spark.sql("""
SELECT 'bronze: source rows'                AS step, count(*) AS rows FROM silver.bronze_contracts
UNION ALL SELECT 'silver: contracts (deduplicated)', count(*) FROM silver.silver_contracts
UNION ALL SELECT 'silver: rejected by quality rules', count(*) FROM silver.silver_contracts_rejected
UNION ALL SELECT 'gold: fct_contracts',              count(*) FROM gold.fct_contracts
UNION ALL SELECT 'silver: awardee lines',           count(*) FROM silver.silver_contract_awardees
UNION ALL SELECT 'gold: supplier bridge rows',      count(*) FROM gold.bridge_contract_supplier
""")
display(counts)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Data quality: what the pipeline expectations saw
# MAGIC Every pipeline update logs, per rule, how many rows passed and failed. Dropping rules keep bad rows out of
# MAGIC silver (they land in `silver_contracts_rejected` with the rule name); warning rules only count them.

# COMMAND ----------

quality = spark.sql("""
WITH latest AS (
  SELECT origin.update_id
  FROM event_log(TABLE(silver.silver_contracts))
  WHERE event_type = 'create_update'
  ORDER BY timestamp DESC LIMIT 1
),
exp AS (
  SELECT explode(from_json(details:flow_progress:data_quality:expectations,
                 'array<struct<name:string, dataset:string, passed_records:bigint, failed_records:bigint>>')) AS e
  FROM event_log(TABLE(silver.silver_contracts))
  WHERE event_type = 'flow_progress' AND origin.update_id IN (SELECT update_id FROM latest)
)
SELECT e.dataset, e.name AS rule, sum(e.passed_records) AS passed, sum(e.failed_records) AS failed,
       round(sum(e.failed_records) / (sum(e.passed_records) + sum(e.failed_records)) * 100, 3) AS failed_pct
FROM exp GROUP BY ALL ORDER BY dataset, rule
""")
display(quality)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. The migration is right: same totals as the DuckDB build
# MAGIC The DuckDB version reported 1,550,674 contracts and EUR 120.54bn. dbt runs the same check as a test
# MAGIC (`dbt/tests/lakehouse_matches_duckdb_build.sql`); here it is in one query.

# COMMAND ----------

display(spark.sql("""
SELECT count(*) AS contracts, round(sum(contract_value) / 1e9, 2) AS value_bn_eur,
       count(*) = 1550674 AS contracts_match
FROM gold.fct_contracts
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Delta Lake: history and time travel
# MAGIC Each pipeline update writes a new table version. Older versions stay queryable, so a weekly refresh can be
# MAGIC compared with the previous one.

# COMMAND ----------

display(spark.sql("DESCRIBE HISTORY gold.fct_contracts").select("version", "timestamp", "operation").limit(5))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. One analysis in PySpark: does one more bidder lower the price?
# MAGIC Open tenders and prior consultations with a single contract and a plausible base price. The ratio
# MAGIC contract value / base price falls as the number of bidders grows.

# COMMAND ----------

from pyspark.sql import functions as F

f = spark.table("gold.fct_contracts").alias("f")
p = spark.table("gold.dim_procedure").alias("p")
competitive = (
    f.join(p, "procedure_key")
    .where(F.col("procedure_group").isin("Open tender", "Prior consultation"))
    .where((F.col("contracts_in_procedure") == 1) & (F.col("base_price") > 0) & (F.col("contract_value") > 0))
    .withColumn("ratio", F.col("contract_value") / F.col("base_price"))
    .where(F.col("ratio").between(0.2, 5) & F.col("bidders_count").isNotNull())
    .withColumn("bidders", F.when(F.col("bidders_count") >= 10, F.lit("10+")).otherwise(F.lpad(F.col("bidders_count").cast("string"), 2, "0")))
)
display(
    competitive.groupBy("procedure_group", "bidders")
    .agg(F.count("*").alias("contracts"), F.round(F.percentile_approx("ratio", 0.5) * 100, 1).alias("median_price_pct_of_base"))
    .orderBy("procedure_group", "bidders")
)
