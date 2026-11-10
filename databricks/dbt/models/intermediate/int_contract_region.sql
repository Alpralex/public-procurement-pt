-- Place of execution per contract. A contract gets its district when all Portuguese lines name the same
-- district, "Multiple" when they name several, "Unspecified" when they give Portugal without a district,
-- "Abroad" when every line is another country, "Not reported" when the field is empty.
with per_contract as (
    select
        l.contract_id,
        count(distinct d.district_pt)          as n_districts,
        min(d.district_pt)                     as one_district,
        bool_or(l.country = 'Portugal')        as has_portugal
    from {{ source('silver', 'silver_location_lines') }} l
    left join {{ ref('districts') }} d
        on d.district_pt = l.district and d.sort_order <= 20
    group by l.contract_id
)

select
    c.contract_id,
    case when c.location_raw is null     then 'Not reported'
         when pc.n_districts = 1         then pc.one_district
         when pc.n_districts > 1         then 'Multiple'
         when pc.has_portugal            then 'Unspecified'
         else 'Abroad' end                as district_pt
from {{ source('silver', 'silver_contracts') }} c
left join per_contract pc on pc.contract_id = c.contract_id
