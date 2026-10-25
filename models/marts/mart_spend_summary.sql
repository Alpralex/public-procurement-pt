-- Q1 Where does the money go: contracts and value by year, contract type, contracting-entity type,
-- CPV division, procedure group and place of execution.
select
    f.contract_year,
    f.contract_type,
    e.entity_type,
    f.cpv_division,
    p.procedure_group,
    f.region_key,
    count(*)                                   as contracts,
    coalesce(sum(f.contract_value), 0)         as contract_value
from {{ ref('fct_contracts') }} f
join {{ ref('dim_entity') }} e using (entity_key)
join {{ ref('dim_procedure') }} p using (procedure_key)
group by all
