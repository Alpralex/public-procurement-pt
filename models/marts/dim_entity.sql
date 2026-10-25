-- Contracting authorities (adjudicante). Key: the entity's NIF. Names change over time (hospital centres
-- merged into local health units in 2024, for example), so the name is the one on the latest contract.
-- entity_type comes from the first matching rule in seeds/entity_type_rules.csv (accent-free, lower-case name).
with named as (
    select
        entity_key,
        arg_max(entity_name, (contract_date, contract_id))          as entity_name,
        case when regexp_full_match(entity_key, '\d{9}') then entity_key end as entity_nif,
        count(*)                                                    as contracts,
        min(year(contract_date))                                    as first_year,
        max(year(contract_date))                                    as last_year
    from {{ ref('stg_contracts') }}
    group by entity_key
),

matched as (
    select
        n.entity_key,
        min(r.rule_order) as rule_order
    from named n
    join {{ ref('entity_type_rules') }} r
        on regexp_matches(
            case when r.match_field = 'nif' then coalesce(n.entity_nif, '') else strip_accents(lower(coalesce(n.entity_name, ''))) end,
            r.pattern)
    group by n.entity_key
)

select
    row_number() over (order by n.entity_key)::integer             as entity_id,
    n.entity_key,
    n.entity_nif,
    coalesce(n.entity_name, 'Not reported')                         as entity_name,
    coalesce(r.entity_type, 'Other public-law body')                as entity_type,
    m.rule_order                                                    as entity_type_rule,
    n.contracts,
    n.first_year,
    n.last_year
from named n
left join matched m using (entity_key)
left join {{ ref('entity_type_rules') }} r on r.rule_order = m.rule_order
