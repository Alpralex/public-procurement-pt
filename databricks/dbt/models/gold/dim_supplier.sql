-- Awardees (adjudicatarios). Key: the supplier's NIF.
-- Privacy: natural persons are never named. They map to "Individual (name withheld)"; awardees without a
-- Portuguese NIF whose name has a company word map to "No Portuguese NIF (name withheld)".
-- supplier_id is the NIF as an integer for named suppliers and -1, -2, -3 for the three withheld rows.
with per_name as (
    select supplier_key, awardee_class, awardee_name, count(*) as n, max(contract_id) as last_contract
    from {{ source('silver', 'silver_contract_awardees') }}
    where supplier_key not like 'WITHHELD-%'
    group by all
),

named as (
    select
        supplier_key,
        any_value(awardee_class)                                    as supplier_type,
        max_by(awardee_name, struct(n, last_contract))              as supplier_name
    from per_name
    group by supplier_key
),

counts as (
    select supplier_key, count(distinct contract_id) as contracts
    from {{ source('silver', 'silver_contract_awardees') }}
    group by supplier_key
)

select
    cast(n.supplier_key as int)     as supplier_id,
    n.supplier_key,
    n.supplier_name,
    n.supplier_type,
    false                           as is_withheld,
    c.contracts
from named n join counts c on c.supplier_key = n.supplier_key

union all
select -1, 'WITHHELD-IND', 'Individual (name withheld)', 'Individual', true,
       (select contracts from counts where supplier_key = 'WITHHELD-IND')
union all
select -2, 'WITHHELD-NONIF', 'No Portuguese NIF (name withheld)', 'No Portuguese NIF', true,
       (select contracts from counts where supplier_key = 'WITHHELD-NONIF')
union all
select -3, 'NOT-REPORTED', 'Awardee not reported', 'Not reported', true,
       (select count(*) from {{ source('silver', 'silver_contracts') }} where n_awardees = 0)
