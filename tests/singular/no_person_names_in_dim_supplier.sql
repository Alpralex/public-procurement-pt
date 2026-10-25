-- Privacy: no name of an awardee withheld as an individual (natural person) may appear
-- as a supplier name, and no supplier key may be an individual, sole-trader or estate NIF.
select s.supplier_key, 'name of a withheld awardee' as problem
from {{ ref('dim_supplier') }} s
join (
    select distinct lower(awardee_name) as nm
    from {{ ref('stg_contract_awardees') }}
    where supplier_key = 'WITHHELD-IND'
      -- sole-trader and estate NIFs (8, 70, 74, 75) are masked as a precaution, but their trade names can be
      -- the same as a registered company's (one case: an 8xx NIF trading under a pharmacy company's name)
      and (nif is null or regexp_matches(nif, '^([123]|45)'))
) w on lower(s.supplier_name) = w.nm
where not s.is_withheld

union all
select supplier_key, 'individual NIF used as key'
from {{ ref('dim_supplier') }}
where regexp_matches(supplier_key, '^([123]|45|70|74|75|8)')

union all
select supplier_key, 'withheld row without the fixed label'
from {{ ref('dim_supplier') }}
where supplier_key like 'WITHHELD-%'
  and supplier_name not in ('Individual (name withheld)', 'No Portuguese NIF (name withheld)')
