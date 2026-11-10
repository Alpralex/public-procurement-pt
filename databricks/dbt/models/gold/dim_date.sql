-- Daily calendar covering the analysis years.
with days as (
    select explode(sequence(
        make_date({{ var('first_year') }}, 1, 1),
        make_date({{ var('last_year') }}, 12, 31),
        interval 1 day)) as d
)

select
    d                                   as date_day,
    year(d)                             as year_number,
    'Q' || quarter(d)                   as quarter_name,
    month(d)                            as month_number,
    date_format(d, 'MMM')               as month_name,
    cast(trunc(d, 'MM') as date)        as month_start,
    month(d) = 12                       as is_december
from days
