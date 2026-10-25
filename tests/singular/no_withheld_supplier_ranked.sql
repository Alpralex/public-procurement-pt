-- Withheld and not-reported awardees never appear in the supplier rankings.
select * from {{ ref('mart_top_suppliers') }}
where supplier_key in ('WITHHELD-IND', 'WITHHELD-NONIF', 'NOT-REPORTED')
