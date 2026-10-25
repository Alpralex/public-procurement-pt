-- CPV divisions (first two digits of the Common Procurement Vocabulary code), English names from the EU CPV 2008 list.
select
    s.cpv_division,
    s.cpv_division_name,
    s.cpv_short_name,
    s.cpv_division || ' ' || s.cpv_short_name as cpv_label
from {{ ref('cpv_divisions') }} s
