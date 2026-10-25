-- Awardees (adjudicatarios). Key: the supplier's NIF.
-- Privacy: natural persons are never named. Every awardee without a NIF and without a company word in its
-- name, and every NIF of an individual, sole trader or estate (prefixes 1, 2, 3, 45, 70, 74, 75, 8), maps to one
-- row "Individual (name withheld)". Awardees without a Portuguese NIF whose name has a company word
-- (mostly foreign companies) map to "No Portuguese NIF (name withheld)": the two cannot be told apart reliably.
-- supplier_id is the NIF as an integer for named suppliers and -1, -2, -3 for the three withheld rows.
with named as (
    select
        supplier_key,
        any_value(awardee_class)                                         as supplier_type,
        arg_max(awardee_name, (n, last_contract))                        as supplier_name
    from (
        select supplier_key, awardee_class, awardee_name, count(*) as n, max(contract_id) as last_contract
        from {{ ref('stg_contract_awardees') }}
        where supplier_key not like 'WITHHELD-%'
        group by all
    )
    group by supplier_key
),

counts as (
    select supplier_key, count(distinct contract_id) as contracts
    from {{ ref('stg_contract_awardees') }}
    group by supplier_key
)

select
    n.supplier_key::integer                                              as supplier_id,
    n.supplier_key,
    n.supplier_name,
    n.supplier_type,
    false                                                                as is_withheld,
    c.contracts
from named n join counts c using (supplier_key)

union all
select -1, 'WITHHELD-IND', 'Individual (name withheld)', 'Individual', true,
       (select contracts from counts where supplier_key = 'WITHHELD-IND')
union all
select -2, 'WITHHELD-NONIF', 'No Portuguese NIF (name withheld)', 'No Portuguese NIF', true,
       (select contracts from counts where supplier_key = 'WITHHELD-NONIF')
union all
select -3, 'NOT-REPORTED', 'Awardee not reported', 'Not reported', true,
       (select count(*) from {{ ref('stg_contracts') }} where n_awardees = 0)
