{{ config(liquid_clustered_by=['contract_year']) }}
-- One wide, readable row per contract for Genie (natural-language questions) and the AI/BI dashboard.
-- Every column has a description in _gold.yml, which Genie reads to understand the data.
-- No supplier names here: questions about suppliers go through mart_top_suppliers (companies only).
select
    f.contract_id,
    f.contract_date,
    f.contract_year,
    month(f.contract_date)                  as contract_month,
    e.entity_name                           as contracting_entity,
    e.entity_type,
    f.contract_type,
    f.threshold_family,
    p.procedure_name_en                     as procedure_name,
    p.procedure_group,
    p.is_competitive,
    f.cpv_division,
    c.cpv_short_name                        as cpv_category,
    r.region                                as region,
    r.region_group,
    f.contract_value                        as contract_value_eur,
    f.base_price                            as base_price_eur,
    f.effective_price                       as effective_price_eur,
    f.bidders_count,
    f.is_single_bid,
    f.n_awardees,
    f.is_centralised,
    f.is_ecological,
    f.execution_days
from {{ ref('fct_contracts') }} f
join {{ ref('dim_entity') }} e on e.entity_key = f.entity_key
join {{ ref('dim_procedure') }} p on p.procedure_key = f.procedure_key
left join {{ ref('dim_cpv') }} c on c.cpv_division = f.cpv_division
left join {{ ref('dim_region') }} r on r.region_key = f.region_key
