-- Contracts per yearly file in fct_contracts equal the distinct idcontrato of that raw file
-- (rows minus the in-file duplicates), and the total equals the distinct ids across all files.
with raw as (
    select
        regexp_extract(filename, 'contratos_(\d{4})\.parquet', 1)::integer as source_file_year,
        count(distinct idcontrato) as raw_contracts
    from read_parquet('{{ var("raw_path") }}/contratos_*.parquet', filename = true)
    group by 1
),

model as (
    select source_file_year, count(*) as model_contracts
    from {{ ref('fct_contracts') }}
    group by 1
)

select coalesce(r.source_file_year, m.source_file_year) as source_file_year, r.raw_contracts, m.model_contracts
from raw r
full join model m using (source_file_year)
where r.raw_contracts is distinct from m.model_contracts

union all
select null, (select count(distinct idcontrato) from read_parquet('{{ var("raw_path") }}/contratos_*.parquet')),
       (select count(*) from {{ ref('fct_contracts') }})
where (select count(distinct idcontrato) from read_parquet('{{ var("raw_path") }}/contratos_*.parquet'))
      <> (select count(*) from {{ ref('fct_contracts') }})
