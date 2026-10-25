{# Empty strings and the '∅' placeholder of the source become NULL. #}
{% macro clean(col) -%}
nullif(nullif(trim({{ col }}), ''), '∅')
{%- endmacro %}

{# Decode the HTML entities found in names (&amp;, &lt;, &gt;, &quot;, &#39;) and drop escaped control characters (&#x13; etc.). #}
{% macro decode_html(col) -%}
trim(regexp_replace(replace(replace(replace(replace(replace({{ col }}, '&lt;', '<'), '&gt;', '>'), '&quot;', '"'), '&#39;', ''''), '&amp;', '&'), '&#x[0-9A-Fa-f]{1,2};', '', 'g'))
{%- endmacro %}

{# Excel serial day number stored as text -> DATE (1899-12-30 + n days). #}
{% macro excel_date(col) -%}
(date '1899-12-30' + try_cast({{ clean(col) }} as integer))
{%- endmacro %}

{# Amount text with '.' decimals -> DECIMAL(18,2). #}
{% macro amount(col) -%}
round(try_cast({{ clean(col) }} as double), 2)::decimal(18, 2)
{%- endmacro %}
