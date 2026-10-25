-- Place of execution: district (distrito) or autonomous region, plus an approximate district group (not NUTS).
select
    district_pt  as region_key,
    region,
    region_group,
    sort_order
from {{ ref('districts') }}
