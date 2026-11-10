-- Contract-to-supplier bridge. A contract with several awardees has one row per awardee, and the contract value
-- is split equally among them (the source gives no split). Contracts without an awardee get one NOT-REPORTED
-- row, so allocated_value sums back to fct_contracts.contract_value for every contract.
with aw as (
    select a.contract_id, a.awardee_seq, a.supplier_key, a.nif, a.n_awardees, c.sme_awardees_raw
    from {{ source('silver', 'silver_contract_awardees') }} a
    join {{ source('silver', 'silver_contracts') }} c on c.contract_id = a.contract_id
)

select
    aw.contract_id,
    aw.awardee_seq,
    aw.supplier_key,
    s.supplier_id,
    1.0 / aw.n_awardees                                     as allocation_share,
    f.contract_value / aw.n_awardees                        as allocated_value,
    coalesce(aw.nif is not null
             and array_contains(split(replace(aw.sme_awardees_raw, ' ', chr(10)), chr(10)), aw.nif), false) as is_sme_flagged
from aw
join {{ ref('fct_contracts') }} f on f.contract_id = aw.contract_id
join {{ ref('dim_supplier') }} s on s.supplier_key = aw.supplier_key

union all
select contract_id, 1, 'NOT-REPORTED', -3, 1.0, contract_value, false
from {{ ref('fct_contracts') }}
where n_awardees = 0
