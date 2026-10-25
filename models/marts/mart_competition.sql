-- Q2 How competitive is it: contracts and value by procedure group, with the number of bidders where the
-- source lists them (concorrentes). A single-bid contract is one whose procedure lists exactly one bidder.
select
    f.contract_year,
    p.procedure_group,
    f.contract_type,
    e.entity_type,
    count(*)                                                        as contracts,
    coalesce(sum(f.contract_value), 0)                              as contract_value,
    count(f.bidders_count)                                          as contracts_with_bidders,
    coalesce(sum(f.bidders_count), 0)                               as bidders_total,
    count(*) filter (where f.is_single_bid)                         as single_bid_contracts,
    coalesce(sum(f.contract_value) filter (where f.is_single_bid), 0)            as single_bid_value,
    coalesce(sum(f.contract_value) filter (where f.bidders_count is not null), 0) as value_with_bidders
from {{ ref('fct_contracts') }} f
join {{ ref('dim_entity') }} e using (entity_key)
join {{ ref('dim_procedure') }} p using (procedure_key)
group by all
