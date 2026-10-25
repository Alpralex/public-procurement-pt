-- The supplier bridge splits each contract's value without loss: allocated values add up to the contract value.
select f.contract_id, f.contract_value, sum(b.allocated_value) as allocated
from {{ ref('fct_contracts') }} f
join {{ ref('bridge_contract_supplier') }} b using (contract_id)
group by f.contract_id, f.contract_value
having abs(coalesce(f.contract_value, 0) - coalesce(sum(b.allocated_value), 0)) > 0.01
    or abs(sum(b.allocation_share) - 1) > 1e-9
