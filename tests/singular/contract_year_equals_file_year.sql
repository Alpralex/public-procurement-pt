-- The analysis date rule (signature date, else closing date, else publication date) puts every contract in
-- the year of the file IMPIC publishes it in. If a new download breaks this, the year definition needs a look.
select contract_id, contract_year, source_file_year
from {{ ref('fct_contracts') }}
where contract_year <> source_file_year
