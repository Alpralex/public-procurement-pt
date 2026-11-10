# Portugal's public contracts on a Databricks lakehouse

The same 1.55 million Portal BASE contracts as the rest of this repository, moved from a DuckDB project to a
Databricks lakehouse the way a data team would run it in production: incremental ingestion, layered Delta tables,
data-quality rules that are measured on every run, dbt for the business logic, tests that prove the migration
is right, and a dashboard plus a natural-language "ask the data" space on top.

**Stack:** Databricks (Unity Catalog, Lakeflow declarative pipelines, Auto Loader, Delta Lake, serverless SQL,
AI/BI dashboards, Genie, Asset Bundles), PySpark, dbt-databricks, pytest, GitHub Actions, Power BI.

```
Portal BASE yearly files (contratos_YYYY.parquet, 39 text columns)
        │  databricks fs cp → UC volume  /Volumes/workspace/raw/landing
        ▼
┌──────────────────────── Lakeflow pipeline (src/pipeline) ────────────────────────┐
│ bronze_contracts           Auto Loader, streaming: only new files are read       │
│ silver_contracts           dedup + typing (PySpark, src/procurement/transforms)  │
│   ├ expect_or_drop         id is a number · has a date · year = file year        │
│   └ expect (monitor)       price ≥ 0 · CPV present · entity NIF · base price ok  │
│ silver_contracts_rejected  rows a rule kept out, with the rule's name            │
│ silver_contract_awardees   one row per awardee; natural persons masked           │
│ silver_location_lines      place of execution lines                              │
└──────────────────────────────────────────────────────────────────────────────────┘
        ▼
┌──────────────────────── dbt-databricks (dbt/) ───────────────────────────────────┐
│ dim_entity · dim_supplier · dim_cpv · dim_procedure · dim_region · dim_date      │
│ fct_contracts (liquid clustering) · bridge_contract_supplier                     │
│ mart_spend_summary · mart_competition · mart_threshold_* · mart_price_vs_base    │
│ mart_supplier_concentration · mart_top_suppliers · contracts_enriched            │
│ 17 tests: keys, privacy, bridge sums, marts = fact, totals = DuckDB build        │
└──────────────────────────────────────────────────────────────────────────────────┘
        ▼
AI/BI dashboard (dashboards/) · Genie space (genie/) · Power BI on the SQL warehouse (powerbi/)

One bundle (databricks.yml) deploys schemas, volume, pipeline, weekly job and dashboard.
```

## Results

The lakehouse reproduces the DuckDB build exactly. Run on the files of 24 October 2026 (local Spark 4.0 with the
same code, `scripts/run_local.py`):

| Check | DuckDB build | Lakehouse |
|---|---:|---:|
| Source rows (bronze) | 1,555,252 | 1,555,252 |
| Contracts after dedup (silver, fact) | 1,550,674 | 1,550,674 |
| Contract value, EUR bn without VAT | 120.54 | 120.54 |
| Health / municipalities, EUR bn | 31.31 / 30.08 | 31.31 / 30.08 |
| Open tenders: share of value / single-bid share | 50.7% / 10.2% | 50.7% / 10.2% |
| Goods and services just below EUR 20,000 vs just above | 50,519 vs 12,290 | 50,519 vs 12,290 |
| HHI construction / energy / telecoms | 59 / 1,072 / 1,634 | 59 / 1,072 / 1,634 |
| Open tenders signed below the base price | 10.9% | 10.9% |
| Supplier bridge rows | 1,576,333 | 1,576,333 |

`dbt build`: 6 seeds, 18 models, 17 tests, all passing. The PySpark unit tests (9) cover parsing, the date rule,
deduplication, ANSI-mode safety and the privacy rules for natural persons.

Two things the migration caught, both now guarded by code:

* **Seed regexes losing their backslashes.** The entity-type rules are regular expressions (`\bipo\b`,
  `^(municipio|camara municipal)\b`). Loaded as SQL literals by one seed loader, `\b` became a backspace
  character, every municipality fell into "Other public-law body", and the totals still matched. A test
  (`seed_regex_patterns_intact`) now fails on it.
* **Decimal precision in the HHI.** Spark keeps six decimals when dividing decimals, which rounded small market
  shares and gave an HHI of 58.3 instead of 59.0 for construction. Shares are now computed in double.

## Design notes

* **Bronze keeps everything as text.** Auto Loader reads the files with type inference off, so a malformed
  amount or date never breaks ingestion; parsing happens once, in silver, where it is tested.
* **Silver logic is plain PySpark functions** (`src/procurement/transforms.py`) imported by the pipeline, so the
  same code is unit-tested locally and in CI without a workspace.
* **Quality rules are measured, not just enforced.** Rules that must hold drop the row (and the rejected
  table shows which rule); rules that describe the data's limits only count failures. The pipeline event log
  gives the pass/fail numbers per run (see `src/notebooks/lakehouse_tour.py`).
* **Gold stays in dbt** because the business rules (entity types, legal value limits, supplier allocation) are
  SQL with reference data and tests, and because dbt-databricks keeps the project portable: the same models run
  on local Spark (`--target local`) and on a Databricks SQL warehouse.
* **Privacy carries over.** Natural persons are never keyed by NIF or named in gold; Genie only sees gold tables.
* **Free Edition limits respected:** serverless only, one SQL warehouse, one pipeline; 1.55 million rows fit
  the daily quota.

## Run it

### On Databricks (Free Edition is enough)

```bash
# 1. CLI and login (once)
brew tap databricks/tap && brew install databricks
databricks auth login --host https://<your-workspace>.cloud.databricks.com

# 2. Source files: data/raw/contratos_YYYY.parquet (see ../scripts/get_data.py)
cd databricks
WAREHOUSE_ID=$(databricks warehouses list --output json | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")

# 3. Deploy schemas, volume, pipeline, job and dashboard
databricks bundle deploy --var="warehouse_id=$WAREHOUSE_ID"

# 4. Upload the files to the landing volume
databricks fs cp ../data/raw/ dbfs:/Volumes/workspace/raw/landing/ --recursive --overwrite

# 5. Pipeline (bronze, silver) then dbt (gold + tests)
databricks bundle run procurement_refresh --var="warehouse_id=$WAREHOUSE_ID"
```

Then open the dashboard (Dashboards → *Portugal public procurement 2019-2026* → Publish), create the Genie space
([`genie/README.md`](genie/README.md)) and, if you like, connect Power BI ([`powerbi/README.md`](powerbi/README.md)).
Adding a new yearly file to the volume and running the job again processes only that file in bronze.

### Locally, without Databricks

```bash
cd databricks
pip install -r requirements-dev.txt     # needs Java 17+
pytest -q tests                         # 9 unit tests
python scripts/run_local.py --raw ../data/raw   # silver with PySpark, gold with dbt on local Spark, all tests
```

## Files

| Path | What it is |
|---|---|
| `databricks.yml`, `resources/` | Asset Bundle: schemas, volume, pipeline, weekly job, dashboard |
| `src/pipeline/procurement_pipeline.py` | Lakeflow pipeline: bronze (Auto Loader), silver, expectations, rejected rows |
| `src/procurement/transforms.py` | Silver transformations in PySpark (port of `../models/staging`) |
| `src/notebooks/lakehouse_tour.py` | Notebook: row counts per layer, quality metrics, migration check, Delta history, one PySpark analysis |
| `dbt/` | Gold layer in dbt-databricks: dimensions, fact, marts, tests, column docs for Unity Catalog |
| `dashboards/public_procurement.lvdash.json` | AI/BI dashboard, generated by `scripts/build_dashboard.py` |
| `genie/` | Genie space instructions, example SQL and sample questions (Portuguese and English) |
| `powerbi/README.md` | Power BI Desktop on the Databricks SQL warehouse |
| `tests/` | PySpark unit tests |
| `scripts/run_local.py` | Full local run and migration check |
