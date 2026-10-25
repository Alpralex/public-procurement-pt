-- One row per awardee line of a contract ("NIF - Name", one per line; natural persons and suppliers
-- without a Portuguese NIF appear as "- - Name").
-- Privacy: this view still carries the raw names because it reads the source; marts keep only the
-- masked supplier key and label, never a natural person's name.
with lines as (
    select
        contract_id,
        n_awardees,
        list_filter(string_split(awardees_raw, chr(10)), lambda x: trim(x) <> '') as awardee_lines
    from {{ ref('stg_contracts') }}
    where n_awardees > 0
),

unnested as (
    select
        contract_id,
        n_awardees,
        generate_subscripts(awardee_lines, 1) as awardee_seq,
        unnest(awardee_lines)                 as awardee_raw
    from lines
),

parsed as (
    select
        contract_id,
        n_awardees,
        awardee_seq,
        regexp_replace(trim(split_part(awardee_raw, ' - ', 1)), '[^0-9]', '', 'g') as nif_digits,
        {{ decode_html("substr(awardee_raw, strpos(awardee_raw, ' - ') + 3)") }}    as awardee_name
    from unnested
),

classified as (
    select
        *,
        case when length(nif_digits) >= 9 then left(nif_digits, 9)
             when length(nif_digits) > 0 then nif_digits end as nif,
        -- company-form words in a name (used for awardees without NIF: foreign companies, associations)
        regexp_matches(upper(strip_accents(awardee_name)),
            '(\bS\.?\s?A\.?U?\b|\bS\.?\s?L\.?U?\b|\bLDA\b|\bL\.DA\b|LIMITED|\bLTD\b|GMBH|\bB\.?\s?V\.?\b|\bINC\b|\bS\.?R\.?L\b|\bAG\b|\bSAS\b|\bLLC\b|\bN\.?\s?V\.?\b|CORPORATION|COMPANY|ASSOCIA|UNIPESSOAL|\bS\.?P\.?A\b|\bA/S\b|\bOY\b|SOCIEDAD|GROUP|\bPLC\b|\bKG\b|FUNDA|UNIVERSI|INSTITUT|\bSARL\b|\bS\.?A\.?S\b|\bCO\.)')
            as has_company_word
    from parsed
),

-- names that also appear with a company or public-body NIF: a line without NIF carrying such a name is that
-- organisation written without its NIF, not a person
registered_names as (
    select distinct lower(awardee_name) as name_lc
    from classified
    where nif is not null and not regexp_matches(nif, '^([123]|45|70|74|75|8)')
),

flagged as (
    select c.*, (c.has_company_word or r.name_lc is not null) as looks_like_organisation
    from classified c
    left join registered_names r on r.name_lc = lower(c.awardee_name)
)

select
    contract_id,
    n_awardees,
    awardee_seq,
    nif,
    awardee_name,
    case
        when nif is null and not looks_like_organisation                         then 'WITHHELD-IND'
        when nif is null                                                   then 'WITHHELD-NONIF'
        when regexp_matches(nif, '^([123]|45|70|74|75|8)')                 then 'WITHHELD-IND'
        else nif
    end as supplier_key,
    case
        -- natural persons: no NIF and no company word, or an individual / sole-trader / estate NIF
        when nif is null and not looks_like_organisation                         then 'Individual'
        when nif is null                                                   then 'No Portuguese NIF'
        when regexp_matches(nif, '^([123]|45|70|74|75|8)')                 then 'Individual'
        when left(nif, 1) = '5'                                            then 'Company'
        when left(nif, 1) = '6'                                            then 'Public body'
        when regexp_matches(nif, '^(71|98)')                               then 'Non-resident entity'
        else 'Other legal person'
    end as awardee_class
from flagged
