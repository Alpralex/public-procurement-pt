-- Q5 Monthly pattern: contracts and value by month, entity type, contract type and procedure group.
select
    cast(trunc(f.contract_date, 'MM') as date)      as month_start,
    e.entity_type,
    f.contract_type,
    p.procedure_group,
    count(*)                                        as contracts,
    coalesce(sum(f.contract_value), 0)              as contract_value
from {{ ref('fct_contracts') }} f
join {{ ref('dim_entity') }} e on e.entity_key = f.entity_key
join {{ ref('dim_procedure') }} p on p.procedure_key = f.procedure_key
group by all
