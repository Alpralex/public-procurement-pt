-- Q5 Contract price against the procedure's base price, and effective (final) price against contract price.
-- Base price: procedures with a single contract only (a multi-lot procedure publishes one base price for all
-- lots), base price > 0 and contract value > 0. Effective price: contracts reported as closed (closing date and
-- PrecoTotalEfetivo > 0). Ratios outside 0.2-5 are treated as data-entry outliers: counted in *_outliers and
-- left out of the sums and medians, so a handful of mistyped base prices cannot move a whole group.
with f as (
    select
        f.*,
        p.procedure_group,
        e.entity_type,
        case when f.contracts_in_procedure = 1 and f.base_price > 0 and f.contract_value > 0
             then f.contract_value / f.base_price end                          as base_ratio,
        case when f.has_effective_price and f.contract_value > 0
             then f.effective_price / f.contract_value end                     as effective_ratio
    from {{ ref('fct_contracts') }} f
    join {{ ref('dim_procedure') }} p using (procedure_key)
    join {{ ref('dim_entity') }} e using (entity_key)
)

select
    contract_year,
    procedure_group,
    contract_type,
    entity_type,
    count(*) filter (where base_ratio between 0.2 and 5)                                        as base_contracts,
    count(*) filter (where base_ratio is not null and base_ratio not between 0.2 and 5)         as base_outliers,
    coalesce(sum(contract_value) filter (where base_ratio between 0.2 and 5), 0)                as base_contract_value,
    coalesce(sum(base_price) filter (where base_ratio between 0.2 and 5), 0)                    as base_price_total,
    count(*) filter (where base_ratio between 0.2 and 5 and base_ratio < 1)                     as below_base_contracts,
    count(*) filter (where base_ratio = 1)                                                      as at_base_contracts,
    median(base_ratio) filter (where base_ratio between 0.2 and 5)                              as median_base_ratio,
    count(*) filter (where effective_ratio between 0.2 and 5)                                   as closed_contracts,
    count(*) filter (where effective_ratio is not null and effective_ratio not between 0.2 and 5) as closed_outliers,
    coalesce(sum(contract_value) filter (where effective_ratio between 0.2 and 5), 0)           as closed_contract_value,
    coalesce(sum(effective_price) filter (where effective_ratio between 0.2 and 5), 0)          as closed_effective_value,
    count(*) filter (where effective_ratio between 1.0001 and 5)                                as closed_above_contract
from f
group by all
