-- Q3 Contract values near the legal limits for direct award and prior consultation: EUR 1,000 bins from 0 to
-- 200,000, goods and services and public works, contracts dated up to 30 September 2026 (the limits rose on
-- 1 October 2026). Bin b holds values in [b, b + 1000).
select
    f.threshold_family,
    f.contract_year,
    p.procedure_group,
    e.entity_type,
    cast(floor(f.contract_value / 1000) * 1000 as int)             as bin_start,
    count(*)                                                        as contracts,
    sum(f.contract_value)                                           as contract_value
from {{ ref('fct_contracts') }} f
join {{ ref('dim_entity') }} e on e.entity_key = f.entity_key
join {{ ref('dim_procedure') }} p on p.procedure_key = f.procedure_key
where f.threshold_family in ('Goods and services', 'Public works')
  and f.contract_value > 0 and f.contract_value < 200000
  and f.contract_date <= date '2026-09-30'
group by all
