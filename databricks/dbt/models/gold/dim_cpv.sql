-- CPV divisions (first two digits of the Common Procurement Vocabulary code), English names.
select
    cpv_division,
    cpv_division_name,
    cpv_short_name,
    cpv_division || ' ' || cpv_short_name as cpv_label
from {{ ref('cpv_divisions') }}
