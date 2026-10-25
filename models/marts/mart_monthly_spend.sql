-- Q5 Monthly pattern: contracts and value by month of the contract date, entity type and contract type.
select
    date_trunc('month', f.contract_date)::date     as month_start,
    e.entity_type,
    f.contract_type,
    p.procedure_group,
    count(*)                                        as contracts,
    coalesce(sum(f.contract_value), 0)              as contract_value
from {{ ref('fct_contracts') }} f
join {{ ref('dim_entity') }} e using (entity_key)
join {{ ref('dim_procedure') }} p using (procedure_key)
group by all
