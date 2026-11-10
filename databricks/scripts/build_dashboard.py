"""Write dashboards/public_procurement.lvdash.json (Databricks AI/BI dashboard) from a short Python spec.

    python scripts/build_dashboard.py [--catalog workspace]

Keeping the dashboard as generated JSON makes it reviewable in Git and deployable with the bundle.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def datasets(cat: str) -> list[dict]:
    g = f"{cat}.gold"
    q = {
        "ds_kpi": f"""SELECT count(*) AS contracts,
       round(sum(contract_value_eur) / 1e9, 2) AS value_bn,
       round(avg(CASE WHEN procedure_group = 'Open tender' AND bidders_count IS NOT NULL
                      THEN CAST(is_single_bid AS INT) END) * 100, 1) AS open_single_bid_pct,
       count(DISTINCT contracting_entity) AS buyers
FROM {g}.contracts_enriched""",
        "ds_year": f"""SELECT contract_year, entity_type, procedure_group,
       CASE WHEN entity_type IN ('Municipality', 'Parish', 'Municipal company or service', 'Intermunicipal body')
            THEN 'Local government'
            WHEN entity_type IN ('Health', 'Central government', 'State-owned company') THEN entity_type
            ELSE 'Other public bodies' END AS buyer_group,
       count(*) AS contracts, sum(contract_value_eur) / 1e9 AS value_bn
FROM {g}.contracts_enriched
GROUP BY ALL""",
        "ds_category": f"""WITH c AS (
  SELECT cpv_category, count(*) AS contracts, sum(contract_value_eur) / 1e9 AS value_bn
  FROM {g}.contracts_enriched GROUP BY ALL),
r AS (SELECT *, row_number() OVER (ORDER BY value_bn DESC) AS rk FROM c)
SELECT cpv_category, contracts, value_bn
FROM r WHERE rk <= 12""",
        "ds_region": f"""SELECT region, region_group, count(*) AS contracts, sum(contract_value_eur) / 1e9 AS value_bn
FROM {g}.contracts_enriched
WHERE region_group NOT IN ('Multiple or national', 'Abroad', 'Not reported')
GROUP BY ALL""",
        "ds_single_bid": f"""SELECT contract_year, procedure_group,
       round(sum(single_bid_contracts) / sum(contracts_with_bidders) * 100, 1) AS single_bid_pct
FROM {g}.mart_competition
WHERE procedure_group IN ('Open tender', 'Prior consultation') AND contract_year <= 2025
GROUP BY ALL""",
        "ds_bunching": f"""SELECT bin_start / 1000 AS value_k_eur,
       CASE WHEN bin_start IN (19000, 74000) THEN 'Just below a legal limit' ELSE 'All other bands' END AS band,
       sum(contracts) AS contracts
FROM {g}.mart_threshold_bunching
WHERE threshold_family = 'Goods and services' AND bin_start BETWEEN 5000 AND 99000
GROUP BY ALL""",
        "ds_thresholds": f"""SELECT procedure_limit || ' (' || threshold_family || ', EUR ' || format_number(threshold_eur, 0) || ')' AS legal_limit,
       contracts_just_below, contracts_just_above,
       round(contracts_just_below / neighbour_bin_avg, 1) AS times_neighbours
FROM {g}.mart_threshold_summary""",
        "ds_concentration": f"""SELECT c.cpv_short_name AS category, round(m.hhi) AS hhi, round(m.top5_share * 100, 1) AS top5_pct,
       m.supplier_value / 1e9 AS value_bn
FROM {g}.mart_supplier_concentration m
JOIN {g}.dim_cpv c USING (cpv_division)
WHERE m.period = '2019-2026' AND m.supplier_value > 5e8""",
        "ds_price": f"""SELECT procedure_group,
       round((1 - try_divide(sum(base_contract_value), sum(base_price_total))) * 100, 1) AS pct_below_base_price
FROM {g}.mart_price_vs_base
GROUP BY ALL
HAVING sum(base_contracts) > 1000""",
        "ds_layers": f"""SELECT * FROM VALUES
  ('1 Bronze', 'bronze_contracts: raw rows, Auto Loader', (SELECT count(*) FROM {cat}.silver.bronze_contracts)),
  ('2 Silver', 'silver_contracts: typed and deduplicated', (SELECT count(*) FROM {cat}.silver.silver_contracts)),
  ('2 Silver', 'silver_contracts_rejected: failed a drop rule', (SELECT count(*) FROM {cat}.silver.silver_contracts_rejected)),
  ('2 Silver', 'silver_contract_awardees: one row per awardee', (SELECT count(*) FROM {cat}.silver.silver_contract_awardees)),
  ('3 Gold', 'fct_contracts: fact table (dbt)', (SELECT count(*) FROM {g}.fct_contracts)),
  ('3 Gold', 'bridge_contract_supplier: value split per supplier', (SELECT count(*) FROM {g}.bridge_contract_supplier))
AS t(layer, table_name, row_count)""",
        "ds_freshness": f"""SELECT max(_ingested_at) AS last_ingested,
       count(DISTINCT _source_file) AS source_files,
       (SELECT max(contract_date) FROM {g}.fct_contracts) AS latest_contract_date
FROM {cat}.silver.bronze_contracts""",
    }
    return [{"name": k, "displayName": k.removeprefix("ds_").replace("_", " "), "queryLines": [v]} for k, v in q.items()]


def text(name, lines, x, y, w, h):
    return {"widget": {"name": name, "multilineTextboxSpec": {"lines": lines}}, "position": pos(x, y, w, h)}


def pos(x, y, w, h):
    return {"x": x, "y": y, "width": w, "height": h}


def field(name, expr=None):
    return {"name": name, "expression": expr or f"`{name}`"}


def counter(name, ds, col, title, x, y, w=2, h=3):
    return {
        "widget": {
            "name": name,
            "queries": [{"name": "main_query", "query": {"datasetName": ds, "fields": [field(col)], "disaggregated": True}}],
            "spec": {
                "version": 2,
                "widgetType": "counter",
                "encodings": {"value": {"fieldName": col, "displayName": title}},
                "frame": {"showTitle": True, "title": title},
            },
        },
        "position": pos(x, y, w, h),
    }


def chart(name, kind, ds, x_col, y_col, title, x, y, w, h, color=None, agg="SUM", horizontal=False, sort_by_value=False,
          x_title="", y_title="", labels=False):
    """Bar / line chart. y is aggregated with `agg`; with horizontal=True the category is on the y axis."""
    value = f"{agg.lower()}({y_col})"
    fields = [field(x_col), field(value, f"{agg}(`{y_col}`)")]
    if color:
        fields.append(field(color))
    cat_scale = {"type": "categorical"} if not x_col.endswith("year") and not x_col.startswith("value_k") else {"type": "quantitative"}
    if sort_by_value:
        cat_scale = {**cat_scale, "sort": {"by": "x-reversed" if horizontal else "y-reversed"}}
    cat = {"fieldName": x_col, "scale": cat_scale, "displayName": x_title or " "}
    val = {"fieldName": value, "scale": {"type": "quantitative"}, "displayName": y_title or y_col.replace("_", " ")}
    enc = {"x": val, "y": cat} if horizontal else {"x": cat, "y": val}
    if color:
        enc["color"] = {"fieldName": color, "scale": {"type": "categorical"}, "displayName": color.replace("_", " ").capitalize()}
    if labels:
        enc["label"] = {"show": True}
    return {
        "widget": {
            "name": name,
            "queries": [{"name": "main_query", "query": {"datasetName": ds, "fields": fields, "disaggregated": False}}],
            "spec": {"version": 3, "widgetType": kind, "encodings": enc, "frame": {"showTitle": True, "title": title}},
        },
        "position": pos(x, y, w, h),
    }


def table(name, ds, cols, title, x, y, w, h, names=None):
    return {
        "widget": {
            "name": name,
            "queries": [{"name": "main_query", "query": {"datasetName": ds, "fields": [field(c) for c in cols], "disaggregated": True}}],
            "spec": {
                "version": 1,
                "widgetType": "table",
                "encodings": {"columns": [{"fieldName": c, "displayName": (names or {}).get(c, c.replace("_", " "))} for c in cols]},
                "frame": {"showTitle": True, "title": title},
            },
        },
        "position": pos(x, y, w, h),
    }


def build(cat: str) -> dict:
    E = "EUR bn"
    overview = [
        text("intro", [
            "## Where does Portugal's public procurement money go?\n",
            "Every contract published on Portal BASE since January 2019 (refreshed weekly; 2026 is the year to date), "
            "EUR without VAT. Click any bar to filter the page.",
        ], 0, 0, 6, 2),
        counter("kpi_contracts", "ds_kpi", "contracts", "Contracts", 0, 2),
        counter("kpi_value", "ds_kpi", "value_bn", "Contract value, EUR bn", 2, 2),
        counter("kpi_single", "ds_kpi", "open_single_bid_pct", "Open tenders with a single bid, %", 4, 2),
        chart("value_by_year", "bar", "ds_year", "contract_year", "value_bn", "Spending by year and buyer, EUR bn",
              0, 5, 3, 6, color="buyer_group", y_title=E),
        chart("value_by_entity", "bar", "ds_year", "entity_type", "value_bn", "Who buys: value by buyer type",
              3, 5, 3, 6, horizontal=True, sort_by_value=True, y_title=E, labels=True),
        chart("value_by_procedure", "bar", "ds_year", "procedure_group", "value_bn", "How it is bought: value by procedure",
              0, 11, 3, 6, horizontal=True, sort_by_value=True, y_title=E, labels=True),
        chart("value_by_category", "bar", "ds_category", "cpv_category", "value_bn",
              "What is bought: top 12 CPV categories by value", 3, 11, 3, 6, horizontal=True, sort_by_value=True,
              y_title=E, labels=True),
        chart("value_by_region", "bar", "ds_region", "region", "value_bn", "Where: value by district of execution, EUR bn",
              0, 17, 6, 6, sort_by_value=True, y_title=E),
    ]
    competition = [
        text("intro2", [
            "## Competition, legal limits and prices\n",
            "Single-bid share where bidders are listed; how contract values pile up just below the direct-award limits; "
            "supplier concentration per category (HHI: under 1,500 unconcentrated, over 2,500 high); "
            "price signed against the base price.",
        ], 0, 0, 6, 2),
        chart("single_bid", "line", "ds_single_bid", "contract_year", "single_bid_pct",
              "Procedures with a single bid, % (2019-2025)", 0, 2, 3, 6, color="procedure_group", y_title="%"),
        chart("price_vs_base", "bar", "ds_price", "procedure_group", "pct_below_base_price",
              "Signed price below the base price, %", 3, 2, 3, 6, horizontal=True, sort_by_value=True,
              y_title="%", labels=True),
        chart("bunching", "bar", "ds_bunching", "value_k_eur", "contracts",
              "Goods and services contracts per EUR 1,000 band: peaks just below the EUR 20k and 75k limits",
              0, 8, 6, 6, color="band", x_title="Contract value, EUR thousand", y_title="Contracts"),
        table("thresholds", "ds_thresholds", ["legal_limit", "contracts_just_below", "contracts_just_above", "times_neighbours"],
              "Contracts just below each legal limit vs the neighbouring bands", 0, 14, 3, 6,
              names={"legal_limit": "Legal limit", "contracts_just_below": "Just below", "contracts_just_above": "Just above",
                     "times_neighbours": "x neighbouring bands"}),
        table("concentration", "ds_concentration", ["category", "hhi", "top5_pct", "value_bn"],
              "Supplier concentration by category, 2019-2026", 3, 14, 3, 6,
              names={"category": "CPV category", "hhi": "HHI", "top5_pct": "Top 5 share, %", "value_bn": "Value, EUR bn"}),
    ]
    pipeline = [
        text("intro3", [
            "## How the data gets here\n",
            "Yearly Portal BASE files land in a Unity Catalog volume. A Lakeflow pipeline ingests only new files with Auto "
            "Loader (bronze), then types, deduplicates and checks every row (silver): rows that break a rule go to a "
            "rejected table with the rule's name. dbt-databricks builds the gold star schema and runs its tests. "
            "One weekly job runs both; the whole project deploys with a Databricks Asset Bundle.",
        ], 0, 0, 6, 3),
        counter("kpi_files", "ds_freshness", "source_files", "Source files ingested", 0, 3),
        counter("kpi_last", "ds_freshness", "last_ingested", "Last ingestion", 2, 3),
        counter("kpi_latest", "ds_freshness", "latest_contract_date", "Latest contract date", 4, 3),
        table("layers", "ds_layers", ["layer", "table_name", "row_count"], "Rows per layer (medallion architecture)",
              0, 6, 6, 6, names={"layer": "Layer", "table_name": "Table", "row_count": "Rows"}),
    ]
    return {
        "datasets": datasets(cat),
        "pages": [
            {"name": "overview", "displayName": "Overview", "pageType": "PAGE_TYPE_CANVAS", "layout": overview},
            {"name": "competition", "displayName": "Competition and prices", "pageType": "PAGE_TYPE_CANVAS", "layout": competition},
            {"name": "pipeline", "displayName": "Data pipeline", "pageType": "PAGE_TYPE_CANVAS", "layout": pipeline},
        ],
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--catalog", default="workspace")
    a = p.parse_args()
    out = ROOT / "dashboards" / "public_procurement.lvdash.json"
    out.write_text(json.dumps(build(a.catalog), indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {out}")
