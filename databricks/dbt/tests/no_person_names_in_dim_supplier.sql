-- Privacy: no name of an awardee withheld as an individual may appear as a supplier name, and no supplier key
-- may be an individual, sole-trader or estate NIF.
select s.supplier_key, 'name of a withheld awardee' as problem
from {{ ref('dim_supplier') }} s
join (
    select distinct lower(awardee_name) as nm
    from {{ source('silver', 'silver_contract_awardees') }}
    where supplier_key = 'WITHHELD-IND'
      and (nif is null or nif rlike '^([123]|45)')
) w on lower(s.supplier_name) = w.nm
where not s.is_withheld

union all
select supplier_key, 'individual NIF used as key'
from {{ ref('dim_supplier') }}
where supplier_key rlike '^([123]|45|70|74|75|8)'
