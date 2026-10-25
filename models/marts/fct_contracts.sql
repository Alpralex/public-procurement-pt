-- One row per contract. Amounts in EUR as published (contract prices exclude VAT).
-- contract_value is the contract price (precoContratual); the 72 negative prices are set to NULL.
-- contract_date: signature date, else closing date (simplified direct awards), else publication date.
select
    c.contract_id,
    c.contract_date,
    year(c.contract_date)                                          as contract_year,
    c.contract_date_basis,
    c.source_file_year,
    c.entity_key,
    e.entity_id,
    c.cpv_division,
    c.cpv_code,
    p.procedure_key,
    ct.contract_type,
    ct.threshold_family,
    l.district_pt                                                  as region_key,
    c.contract_value,
    c.base_price,
    c.effective_price,
    c.closing_date is not null and c.effective_price > 0           as has_effective_price,
    c.n_awardees,
    c.bidders_count,
    c.bidders_count = 1                                            as is_single_bid,
    c.is_centralised,
    c.is_ecological,
    c.sme_awardees_raw is not null                                 as has_sme_flag,
    c.execution_days,
    case when c.contract_value < 200000 then (floor(c.contract_value / 1000) * 1000)::integer end as value_bin_start,
    c.procedure_id,
    case when c.procedure_id is not null then count(*) over (partition by c.procedure_id) end as contracts_in_procedure
from {{ ref('stg_contracts') }} c
join {{ ref('procedure_types') }} p on p.procedure_name_pt = c.procedure_name_pt
join {{ ref('contract_types') }} ct on ct.contract_type_pt = c.contract_type_pt
join {{ ref('stg_contract_locations') }} l on l.contract_id = c.contract_id
join {{ ref('dim_entity') }} e on e.entity_key = c.entity_key
