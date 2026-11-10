# Genie space: "Ask Portugal's public contracts"

Genie answers questions in plain language (Portuguese or English) by writing SQL against the gold tables. The
column descriptions it reads come from dbt (`dbt/models/gold/_gold.yml`, written to Unity Catalog by
`persist_docs`), so no extra documentation is needed in the space itself.

## Create the space with one command

```bash
export BUNDLE_VAR_warehouse_id=$(databricks warehouses list --output json | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")
python3 scripts/create_genie_space.py
```

The script sends the tables, `instructions.md`, the sample questions and the trusted SQL in
`example_queries.sql` to the Genie API, using the CLI login. Run it again after editing those files: it updates
the same space (its id is kept in `.genie_space_id`).

## Or create it by hand (about 5 minutes, in the Databricks UI)

1. Left menu **Genie** → **New**.
2. **Tables**: `workspace.gold.contracts_enriched`, `workspace.gold.mart_top_suppliers`,
   `workspace.gold.dim_supplier`, `workspace.gold.mart_supplier_concentration`,
   `workspace.gold.mart_threshold_summary`, `workspace.gold.dim_cpv`.
   Do not add silver tables: they hold raw awardee names, and gold never names a natural person.
3. **Title**: Ask Portugal's public contracts · **Warehouse**: Serverless Starter Warehouse.
4. **Instructions**: paste the text of `instructions.md`.
5. **SQL queries** (Configure → Instructions → SQL queries): add the queries in `example_queries.sql`, each with
   the question written above it. Genie reuses them as trusted answers.
6. **Sample questions**: add the five questions at the end of `instructions.md`.
7. Ask the sample questions once and mark the good answers with a thumbs-up.

For the portfolio: record a 60-second screen video asking two questions in Portuguese and one in English.
