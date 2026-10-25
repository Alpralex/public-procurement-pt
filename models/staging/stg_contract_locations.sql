-- Place of execution per contract. LocalExecucao holds one line per place, "Country, District, Municipality".
-- A contract gets its district when all Portuguese lines name the same district, "Multiple" when they name
-- several, "Unspecified" when they give Portugal without a district, "Abroad" when every line is another country.
with lines as (
    select contract_id, unnest(string_split(location_raw, chr(10))) as line
    from {{ ref('stg_contracts') }}
    where location_raw is not null
),

parts as (
    select
        contract_id,
        trim(split_part(line, ',', 1)) as country,
        trim(split_part(line, ',', 2)) as district
    from lines
    where trim(line) <> ''
),

per_contract as (
    select
        p.contract_id,
        count(distinct d.district_pt)                        as n_districts,
        min(d.district_pt)                                   as one_district,
        bool_or(p.country = 'Portugal')                      as has_portugal
    from parts p
    left join {{ ref('districts') }} d
        on d.district_pt = p.district and d.sort_order <= 20
    group by p.contract_id
)

select
    c.contract_id,
    case when c.location_raw is null       then 'Not reported'
         when pc.n_districts = 1           then pc.one_district
         when pc.n_districts > 1           then 'Multiple'
         when pc.has_portugal              then 'Unspecified'
         else 'Abroad' end                  as district_pt
from {{ ref('stg_contracts') }} c
left join per_contract pc using (contract_id)
