-- Procedure types as published (tipoprocedimento), with an English name and an analysis group.
select
    procedure_key,
    procedure_name_pt,
    procedure_name_en,
    procedure_group,
    group_order,
    is_competitive
from {{ ref('procedure_types') }}
