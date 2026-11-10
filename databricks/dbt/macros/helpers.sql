{# Accent-free text, like DuckDB strip_accents (Databricks SQL has no built-in). #}
{% macro strip_accents(col) -%}
translate({{ col }}, 'ÁÀÂÃÄÅÇÉÈÊËÍÌÎÏÑÓÒÔÕÖÚÙÛÜÝáàâãäåçéèêëíìîïñóòôõöúùûüýÿ', 'AAAAAACEEEEIIIINOOOOOUUUUYaaaaaaceeeeiiiinooooouuuuyy')
{%- endmacro %}

{# Silver tables live in the schema the pipeline publishes to. #}
{% macro generate_schema_name(custom_schema_name, node) -%}
{%- if custom_schema_name is none -%}{{ target.schema }}{%- else -%}{{ custom_schema_name | trim }}{%- endif -%}
{%- endmacro %}
