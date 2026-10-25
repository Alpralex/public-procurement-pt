-- Q4 Largest named suppliers by allocated value 2019-2026: top 25 across all divisions and top 10 within each
-- CPV division. Withheld and not-reported awardees are not ranked but stay in the share denominators.
with alloc as (
    select b.supplier_key, f.cpv_division, b.contract_id, b.allocated_value
    from {{ ref('bridge_contract_supplier') }} b
    join {{ ref('fct_contracts') }} f using (contract_id)
    where b.allocated_value > 0
),

overall as (
    select 'All divisions' as rank_scope, null::varchar as cpv_division, supplier_key,
           sum(allocated_value) as allocated_value, count(distinct contract_id) as contracts,
           sum(sum(allocated_value)) over () as scope_value
    from alloc group by supplier_key
),

per_div as (
    select 'CPV division' as rank_scope, cpv_division, supplier_key,
           sum(allocated_value) as allocated_value, count(distinct contract_id) as contracts,
           sum(sum(allocated_value)) over (partition by cpv_division) as scope_value
    from alloc group by cpv_division, supplier_key
),

both_scopes as (
    select * from overall union all select * from per_div
),

ranked as (
    select *, row_number() over (partition by rank_scope, cpv_division order by allocated_value desc, supplier_key) as supplier_rank
    from both_scopes
    where supplier_key not in ('WITHHELD-IND', 'WITHHELD-NONIF', 'NOT-REPORTED')
)

select rank_scope, cpv_division, supplier_rank, supplier_key, allocated_value, contracts,
       allocated_value / scope_value as share_of_scope
from ranked
where (rank_scope = 'All divisions' and supplier_rank <= 25) or (rank_scope = 'CPV division' and supplier_rank <= 10)
