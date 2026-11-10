-- Migration check: the lakehouse gives the same totals as the DuckDB version of the project
-- (1,550,674 contracts, EUR 120.54bn without VAT, files downloaded on 25 October 2026).
-- Severity warn: a newer download of Portal BASE has more contracts, which is expected and must not stop the
-- weekly job. On the same files the counts must match exactly; check the warning after a fresh download.
{{ config(severity='warn') }}
with f as (select count(*) as n, sum(contract_value) as v from {{ ref('fct_contracts') }})
select n, v from f
where n <> {{ var('expected_contracts') }}
   or abs(v - {{ var('expected_value_eur') }}) > {{ var('expected_value_tolerance_eur') }}
