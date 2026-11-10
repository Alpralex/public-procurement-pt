-- Q4 Supplier concentration per CPV division, for 2019-2026 and for each year. Values are the bridge's allocated
-- values. Withheld awardees are counted as separate suppliers through a key derived inside this query only.
-- HHI = sum of squared value shares x 10,000 (0 = fragmented, 10,000 = one supplier).
with alloc as (
    select
        b.contract_id,
        f.contract_year,
        f.cpv_division,
        b.is_sme_flagged,
        b.supplier_key like 'WITHHELD-%'                               as is_withheld,
        case when b.supplier_key like 'WITHHELD-%' then 'W-' || md5(lower(a.awardee_name)) else b.supplier_key end as calc_key,
        b.allocated_value
    from {{ ref('bridge_contract_supplier') }} b
    join {{ ref('fct_contracts') }} f on f.contract_id = b.contract_id
    left join {{ source('silver', 'silver_contract_awardees') }} a
        on a.contract_id = b.contract_id and a.awardee_seq = b.awardee_seq
    where b.allocated_value > 0 and b.supplier_key <> 'NOT-REPORTED'
),

periods as (
    select *, '2019-2026' as period from alloc
    union all
    select *, cast(contract_year as string) as period from alloc
),

by_supplier as (
    -- double, not decimal: decimal division keeps 6 decimals, which rounds small shares and lowers the HHI
    select period, cpv_division, calc_key, cast(sum(allocated_value) as double) as v
    from periods group by all
),

ranked as (
    select *,
           v / sum(v) over (partition by period, cpv_division)                                   as s,
           row_number() over (partition by period, cpv_division order by v desc, calc_key)      as rk
    from by_supplier
),

conc as (
    select
        period, cpv_division,
        sum(v)                          as supplier_value,
        count(*)                        as suppliers,
        sum(s) filter (where rk = 1)    as top1_share,
        sum(s) filter (where rk <= 5)   as top5_share,
        sum(s) filter (where rk <= 10)  as top10_share,
        sum(s * s) * 10000              as hhi
    from ranked group by all
),

extra as (
    select
        period, cpv_division,
        sum(allocated_value) filter (where is_withheld) / sum(allocated_value)          as withheld_share,
        sum(allocated_value) filter (where is_sme_flagged and contract_year >= 2024)
            / nullif(sum(allocated_value) filter (where contract_year >= 2024), 0)     as sme_flag_share_2024_on
    from periods group by all
)

select c.*, e.withheld_share, e.sme_flag_share_2024_on
from conc c join extra e on e.period = c.period and e.cpv_division = c.cpv_division
