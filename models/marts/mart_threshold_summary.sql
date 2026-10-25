-- Q3 summary: for each limit in force 2019 - Sep 2026, the contracts in the EUR 1,000 just below the limit,
-- the EUR 1,000 just above, and the average EUR 1,000 bin in the EUR 4,000 on either side
-- (t-5,000 to t-1,000 and t+1,000 to t+5,000). ratio_below_to_neighbours > 1 means more contracts sit just
-- below the limit than the surrounding values would suggest. Limits written "not above" (art. 128) count the
-- limit itself as below. Exact amounts are also counted: exactly the limit minus one euro and round values.
with t as (
    select * from {{ ref('thresholds') }} where in_analysis
),

f as (
    select threshold_family, contract_value, contract_year
    from {{ ref('fct_contracts') }}
    where contract_value > 0 and contract_date <= date '2026-09-30'
)

select
    t.threshold_id,
    t.threshold_family,
    t.procedure_limit,
    t.threshold_eur,
    t.limit_rule,
    t.legal_source,
    count(*) filter (where (t.limit_rule = 'below' and f.contract_value >= t.threshold_eur - 1000 and f.contract_value < t.threshold_eur)
                        or (t.limit_rule = 'not above' and f.contract_value > t.threshold_eur - 1000 and f.contract_value <= t.threshold_eur))
                                                                            as contracts_just_below,
    count(*) filter (where (t.limit_rule = 'below' and f.contract_value >= t.threshold_eur and f.contract_value < t.threshold_eur + 1000)
                        or (t.limit_rule = 'not above' and f.contract_value > t.threshold_eur and f.contract_value <= t.threshold_eur + 1000))
                                                                            as contracts_just_above,
    count(*) filter (where (f.contract_value >= t.threshold_eur - 5000 and f.contract_value < t.threshold_eur - 1000)
                        or (f.contract_value >= t.threshold_eur + 1000 and f.contract_value < t.threshold_eur + 5000)) / 8.0
                                                                            as neighbour_bin_avg,
    count(*) filter (where f.contract_value >= t.threshold_eur - 1 and f.contract_value < t.threshold_eur)
                                                                            as contracts_within_1_euro_below
from t
join f on f.threshold_family = t.threshold_family
group by all
