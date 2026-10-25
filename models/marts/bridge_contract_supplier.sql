-- Contract-to-supplier bridge. A contract with several awardees (framework agreements, consortia, lots
-- awarded together) has one row per awardee, and the contract value is split equally among them
-- (allocation_share = 1 / n_awardees): the source gives no split. Contracts without an awardee get one row
-- for NOT-REPORTED, so allocated_value sums back to fct_contracts.contract_value for every contract.
with aw as (
    select a.contract_id, a.awardee_seq, a.supplier_key, a.nif, a.n_awardees, c.sme_awardees_raw
    from {{ ref('stg_contract_awardees') }} a
    join {{ ref('stg_contracts') }} c using (contract_id)
)

select
    aw.contract_id,
    aw.awardee_seq,
    aw.supplier_key,
    s.supplier_id,
    1.0 / aw.n_awardees                                            as allocation_share,
    f.contract_value / aw.n_awardees                               as allocated_value,
    coalesce(aw.nif is not null and list_contains(string_split(replace(aw.sme_awardees_raw, ' ', chr(10)), chr(10)), aw.nif), false) as is_sme_flagged
from aw
join {{ ref('fct_contracts') }} f using (contract_id)
join {{ ref('dim_supplier') }} s on s.supplier_key = aw.supplier_key

union all
select contract_id, 1, 'NOT-REPORTED', -3, 1.0, contract_value, false
from {{ ref('fct_contracts') }}
where n_awardees = 0
