-- Question marts add up to the contract fact (contracts and value).
with f as (select count(*) as n, sum(contract_value) as v from {{ ref('fct_contracts') }}),
m as (
    select 'mart_spend_summary' as mart, sum(contracts) as n, sum(contract_value) as v from {{ ref('mart_spend_summary') }}
    union all select 'mart_competition', sum(contracts), sum(contract_value) from {{ ref('mart_competition') }}
    union all select 'mart_monthly_spend', sum(contracts), sum(contract_value) from {{ ref('mart_monthly_spend') }}
)
select m.* from m, f
where m.n <> f.n or abs(m.v - f.v) > 1
