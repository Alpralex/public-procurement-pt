-- The analysis-date rule puts every contract in the year of the file IMPIC publishes it in.
select contract_id, contract_year, source_file_year
from {{ ref('fct_contracts') }}
where contract_year <> source_file_year
