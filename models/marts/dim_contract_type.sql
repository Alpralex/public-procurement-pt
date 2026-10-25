-- Contract types in English, with the family used for the value limits (goods and services vs public works).
select distinct contract_type, threshold_family
from {{ ref('contract_types') }}
