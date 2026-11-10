-- Migration check: the lakehouse gives the same totals as the DuckDB version of the project
-- (1,550,674 contracts, EUR 120.54bn without VAT, data of 24 October 2026).
with f as (select count(*) as n, sum(contract_value) as v from {{ ref('fct_contracts') }})
select n, v from f
where n <> {{ var('expected_contracts') }}
   or abs(v - {{ var('expected_value_eur') }}) > {{ var('expected_value_tolerance_eur') }}
