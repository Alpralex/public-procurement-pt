"""Export the marts: Parquet files for Power BI and Qlik (powerbi/data/) and compact JSON for the web page (web/data/).

Run after `dbt build --profiles-dir .` from the repository root. Privacy: only dim_supplier carries supplier names,
and it has already collapsed natural persons into "Individual (name withheld)". The script checks at the end that no
name of a withheld individual appears in any exported file.
"""
import json
import os

import duckdb

DB = os.environ.get("PROC_DB_PATH", "data/procurement.duckdb")
con = duckdb.connect(DB, read_only=True)
os.makedirs("powerbi/data", exist_ok=True)
os.makedirs("web/data", exist_ok=True)

PQ = "(format parquet, compression zstd, compression_level 19)"

tables = {
    "dim_date": "select * from dim_date order by date_day",
    "dim_entity": "select entity_id, entity_nif, entity_name, entity_type, contracts, first_year, last_year from dim_entity order by entity_id",
    "dim_supplier": """select supplier_id, case when not is_withheld then supplier_key end as supplier_nif, supplier_name,
                              supplier_type, is_withheld, contracts from dim_supplier order by supplier_id""",
    "dim_cpv": "select * from dim_cpv order by cpv_division",
    "dim_procedure": "select * from dim_procedure order by procedure_key",
    "dim_region": "select * from dim_region order by sort_order",
    "dim_contract_type": "select * from dim_contract_type order by contract_type",
    # one row per contract; base and effective prices only where they can be compared (see mart_price_vs_base)
    "fct_contracts": """
        select contract_id::integer as contract_id, contract_date, entity_id, cpv_division,
               procedure_key::tinyint as procedure_key, contract_type, region_key, contract_value,
               case when contracts_in_procedure = 1 and base_price > 0 and contract_value > 0
                         and contract_value / base_price between 0.2 and 5 then base_price end as base_price_comparable,
               case when has_effective_price and contract_value > 0
                         and effective_price / contract_value between 0.2 and 5 then effective_price end as effective_price_closed,
               bidders_count::smallint as bidders_count
        from fct_contracts
        order by entity_id, contract_date, contract_id""",
    # contract x supplier; value of a supplier = allocation_share x contract_value
    "bridge_contract_supplier": """
        select contract_id::integer as contract_id, supplier_id, allocation_share::double as allocation_share
        from bridge_contract_supplier
        order by supplier_id, contract_id""",
    "mart_supplier_concentration": "select * from mart_supplier_concentration order by period, cpv_division",
    "mart_top_suppliers": """select t.rank_scope, t.cpv_division, t.supplier_rank, s.supplier_id, t.allocated_value, t.contracts, t.share_of_scope
                             from mart_top_suppliers t join dim_supplier s using (supplier_key) order by 1, 2, 3""",
    "mart_threshold_summary": "select * from mart_threshold_summary order by threshold_family, threshold_eur",
}
total = 0
for name, sql in tables.items():
    path = f"powerbi/data/{name}.parquet"
    con.execute(f"copy ({sql}) to '{path}' {PQ}")
    n = con.execute(f"select count(*) from '{path}'").fetchone()[0]
    size = os.path.getsize(path)
    total += size
    print(f"{path}: {n:,} rows, {size / 1e6:.2f} MB")
print(f"powerbi/data total: {total / 1e6:.2f} MB")


def rows(sql):
    return [[float(v) if hasattr(v, "as_tuple") else v for v in r] for r in con.execute(sql).fetchall()]


# lookups: the web JSON stores category indexes, meta.json holds the labels
CTYPES = [r[0] for r in con.execute("select contract_type from dim_contract_type order by contract_type").fetchall()]
ETYPES = [r[0] for r in con.execute("select entity_type from dim_entity group by 1 order by sum(contracts) desc").fetchall()]
CPVS = rows("select cpv_division, cpv_short_name, cpv_division_name from dim_cpv order by cpv_division")
PGROUPS = rows("select procedure_group, min(group_order) from dim_procedure group by 1 order by 2, 1")
REGIONS = rows("select region_key, region, region_group from dim_region order by sort_order")

lk = {
    "ct": {v: i for i, v in enumerate(CTYPES)},
    "et": {v: i for i, v in enumerate(ETYPES)},
    "cpv": {r[0]: i for i, r in enumerate(CPVS)},
    "pg": {r[0]: i for i, r in enumerate(PGROUPS)},
    "rg": {r[0]: i for i, r in enumerate(REGIONS)},
}
con.execute("create temp table lk_ct as select * from (values " + ",".join(f"('{k}',{v})" for k, v in lk["ct"].items()) + ") t(k, i)")
con.execute("create temp table lk_et as select * from (values " + ",".join(f"('{k}',{v})" for k, v in lk["et"].items()) + ") t(k, i)")
con.execute("create temp table lk_cpv as select * from (values " + ",".join(f"('{k}',{v})" for k, v in lk["cpv"].items()) + ") t(k, i)")
con.execute("create temp table lk_pg as select * from (values " + ",".join(f"('{k}',{v})" for k, v in lk["pg"].items()) + ") t(k, i)")
con.execute("create temp table lk_rg as select * from (values " + ",".join(f"('{k.replace(chr(39), chr(39) * 2)}',{v})" for k, v in lk["rg"].items()) + ") t(k, i)")

J = "join lk_ct ct on ct.k = m.contract_type join lk_et et on et.k = m.entity_type"
web = {
    # year, contract type, entity type, CPV division, contracts, value (EUR)
    "cpv": f"""select m.contract_year, ct.i, et.i, cpv.i, sum(contracts), round(sum(contract_value))
               from mart_spend_summary m {J} join lk_cpv cpv on cpv.k = m.cpv_division group by all order by 1, 2, 3, 4""",
    # year, contract type, entity type, region, contracts, value
    "region": f"""select m.contract_year, ct.i, et.i, rg.i, sum(contracts), round(sum(contract_value))
                  from mart_spend_summary m {J} join lk_rg rg on rg.k = m.region_key group by all order by 1, 2, 3, 4""",
    # year, contract type, entity type, procedure group, contracts, value, contracts with bidders, bidders,
    # single-bid contracts, value with bidders, single-bid value
    "competition": f"""select m.contract_year, ct.i, et.i, pg.i, contracts, round(contract_value), contracts_with_bidders, bidders_total,
                              single_bid_contracts, round(value_with_bidders), round(single_bid_value)
                       from mart_competition m {J} join lk_pg pg on pg.k = m.procedure_group order by 1, 2, 3, 4""",
    # month (YYYY-MM), contract type, entity type, contracts, value
    "monthly": f"""select strftime(month_start, '%Y-%m'), ct.i, et.i, sum(contracts), round(sum(contract_value))
                   from mart_monthly_spend m {J} group by all order by 1, 2, 3""",
    # family (0 goods and services, 1 public works), year, entity type, bin start (EUR thousands), contracts
    "bunching": """select case when m.threshold_family = 'Public works' then 1 else 0 end, m.contract_year, et.i, m.bin_start // 1000, sum(contracts)
                   from mart_threshold_bunching m join lk_et et on et.k = m.entity_type
                   where m.threshold_family = 'Public works' or m.bin_start < 100000
                   group by all order by 1, 2, 3, 4""",
    # year, contract type, entity type, procedure group, base contracts, base contract value, base price total,
    # below base, at base, closed contracts, closed contract value, closed effective value, closed above contract
    "price": f"""select m.contract_year, ct.i, et.i, pg.i, base_contracts, round(base_contract_value), round(base_price_total),
                        below_base_contracts, at_base_contracts, closed_contracts, round(closed_contract_value),
                        round(closed_effective_value), closed_above_contract
                 from mart_price_vs_base m {J} join lk_pg pg on pg.k = m.procedure_group
                 where base_contracts > 0 or closed_contracts > 0 order by 1, 2, 3, 4""",
    # CPV division, value, suppliers, top-1 share, top-5 share, top-10 share, HHI, withheld share, SME-flag share 2024+
    "concentration": """select cpv.i, round(supplier_value), suppliers, round(top1_share, 4), round(top5_share, 4), round(top10_share, 4),
                               round(hhi), round(withheld_share, 4), round(sme_flag_share_2024_on, 4)
                        from mart_supplier_concentration m join lk_cpv cpv on cpv.k = m.cpv_division
                        where period = '2019-2026' order by 1""",
    # scope (-1 all divisions, else CPV index), rank, supplier name, value, contracts, share of scope
    "suppliers": """select coalesce(cpv.i, -1), t.supplier_rank, s.supplier_name, round(t.allocated_value), t.contracts, round(t.share_of_scope, 4)
                    from mart_top_suppliers t join dim_supplier s using (supplier_key)
                    left join lk_cpv cpv on cpv.k = t.cpv_division
                    where t.rank_scope = 'All divisions' or t.supplier_rank <= 5 order by 1, 2""",
}
for name, sql in web.items():
    data = rows(sql)
    with open(f"web/data/{name}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"), ensure_ascii=False)
    print(f"web/data/{name}.json: {len(data):,} rows")

meta = {
    "contract_types": CTYPES,
    "entity_types": ETYPES,
    "cpv": CPVS,
    "procedure_groups": [r[0] for r in PGROUPS],
    "regions": REGIONS,
    "thresholds": rows("""select threshold_id, threshold_family, procedure_limit, threshold_eur, limit_rule, contracts_just_below,
                                 contracts_just_above, round(neighbour_bin_avg, 1), contracts_within_1_euro_below
                          from mart_threshold_summary order by threshold_family, threshold_eur"""),
    "totals": rows("select count(*), round(sum(contract_value)), min(contract_date)::varchar, max(contract_date)::varchar from fct_contracts")[0],
    "entities": con.execute("select count(*) from dim_entity").fetchone()[0],
    "suppliers": con.execute("select count(*) from dim_supplier where not is_withheld").fetchone()[0],
    "downloaded": "2026-10-25",
}
with open("web/data/meta.json", "w", encoding="utf-8") as f:
    json.dump(meta, f, separators=(",", ":"), ensure_ascii=False)
web_total = sum(os.path.getsize(f"web/data/{n}") for n in os.listdir("web/data") if n.endswith(".json"))
print(f"web/data total: {web_total / 1e6:.2f} MB")

# ---- privacy check: no name of a withheld individual in any exported file ----
withheld = {r[0] for r in con.execute(
    """select distinct lower(awardee_name) from stg_contract_awardees
       where supplier_key = 'WITHHELD-IND' and (nif is null or regexp_matches(nif, '^([123]|45)'))
         and regexp_matches(awardee_name, '[A-Za-z]{2}')   -- skip lines whose "name" is only a number""").fetchall()}
withheld -= {"individual"}  # the supplier_type label itself


def strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, (list, tuple)):
        for x in obj:
            yield from strings(x)
    elif isinstance(obj, dict):
        for x in obj.values():
            yield from strings(x)


leaks = []
for n in os.listdir("web/data"):
    with open(f"web/data/{n}", encoding="utf-8") as f:
        leaks += [(n, s) for s in strings(json.load(f)) if s.lower() in withheld]
for name in tables:
    cols = [r[0] for r in con.execute(f"describe select * from 'powerbi/data/{name}.parquet'").fetchall()
            if r[1] == "VARCHAR"]
    for col in cols:
        for (v,) in con.execute(f"select distinct {col} from 'powerbi/data/{name}.parquet' where {col} is not null").fetchall():
            if v.lower() in withheld:
                leaks.append((f"{name}.{col}", v))
print(f"privacy check: {len(leaks)} withheld names found in exports")
for leak in leaks[:20]:
    print("  ", leak)
if leaks:
    raise SystemExit("privacy check failed")
