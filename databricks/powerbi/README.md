# Power BI on the lakehouse

The gold tables are read straight from the Databricks SQL warehouse, so the Power BI model, the AI/BI dashboard
and Genie all use the same numbers.

## Connect (Power BI Desktop, Windows VM)

1. In Databricks: **SQL Warehouses** → *Serverless Starter Warehouse* → **Connection details**. Copy
   *Server hostname* and *HTTP path*.
2. Power BI Desktop → **Get data** → **Azure Databricks** (the same connector works for Databricks on AWS/GCP).
3. Paste the hostname and HTTP path. Data connectivity mode: **DirectQuery** for the fact table,
   **Import** for the dimensions (a composite model), or Import for everything on Free Edition (the warehouse
   stops when idle and the daily quota is small).
4. Authentication: **Personal Access Token** (Databricks → Settings → Developer → Access tokens).
5. Pick `workspace.gold`: `fct_contracts`, `dim_entity`, `dim_cpv`, `dim_procedure`, `dim_region`,
   `dim_contract_type`, `dim_date`. Relationships and measures are the same as in the DuckDB-based model in
   [`../../powerbi`](../../powerbi) (TMDL), only the source changes.

Free Edition is for non-commercial use and has no SLA, so the public "publish to web" report of the project
stays on the Parquet-based model; this connection is the demonstration that the model runs on a lakehouse.
