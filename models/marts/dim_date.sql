-- Daily calendar covering the analysis years.
select
    d::date                                         as date_day,
    year(d)                                         as year_number,
    'Q' || quarter(d)                               as quarter_name,
    month(d)                                        as month_number,
    strftime(d, '%b')                               as month_name,
    date_trunc('month', d)::date                    as month_start,
    month(d) = 12                                   as is_december
from range(make_date({{ var('first_year') }}, 1, 1), make_date({{ var('last_year') + 1 }}, 1, 1), interval 1 day) t(d)
