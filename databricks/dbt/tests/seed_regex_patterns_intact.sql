-- The entity-type rules are regular expressions with backslashes (\b, \s, \.). Some seed loaders turn '\b' into a
-- backspace character; this test fails if a pattern lost its backslashes, before entity types go wrong silently.
select rule_order, pattern
from {{ ref('entity_type_rules') }}
where instr(pattern, chr(8)) > 0
   or (rule_order in (10, 20, 30) and instr(pattern, chr(92)) = 0)
