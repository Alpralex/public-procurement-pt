-- One row per contract (idcontrato), parsed from the yearly Portal BASE files.
-- Every source column is text. Dates are Excel serial numbers, amounts use '.' decimals.
-- 4,566 contract ids appear more than once inside the same yearly file (9,144 rows; none across files).
-- The copies differ only in secondary fields such as TipoCriterioAdjudicacao, so one row is kept per id:
-- latest file first, then a fixed order, which makes the choice deterministic.
with src as (
    select
        *,
        regexp_extract(filename, 'contratos_(\d{4})\.parquet', 1)::integer as source_file_year
    from read_parquet('{{ var("raw_path") }}/contratos_*.parquet', filename = true)
),

dedup as (
    select *
    from src
    qualify row_number() over (
        partition by idcontrato
        order by source_file_year desc, TipoCriterioAdjudicacao nulls last, nAnuncio nulls last,
                 md5(concat_ws('|', coalesce(adjudicatarios, ''), coalesce(concorrentes, ''), coalesce(Lotes, ''), coalesce(NUTs, '')))
    ) = 1
),

parsed as (
    select
        idcontrato::bigint                                         as contract_id,
        source_file_year,
        try_cast(Ano as integer)                                   as file_year_column,
        {{ clean('idprocedimento') }}                              as procedure_id,
        {{ clean('nAnuncio') }}                                    as announcement_no,
        case when tipoContrato like '%' || chr(10) || '%' then 'Mixed'
             else coalesce({{ clean('tipoContrato') }}, 'Not reported') end as contract_type_pt,
        coalesce({{ clean('tipoprocedimento') }}, 'Not reported') as procedure_name_pt,

        -- contracting authority: "NIF - Name"
        trim(split_part(adjudicante, ' - ', 1))                    as entity_nif_raw,
        {{ decode_html("substr(adjudicante, strpos(adjudicante, ' - ') + 3)") }} as entity_name,
        adjudicante is null                                        as entity_missing,

        {{ clean('adjudicatarios') }}                              as awardees_raw,
        {{ clean('concorrentes') }}                                as bidders_raw,
        {{ clean('adjudicatarioPMEs') }}                           as sme_awardees_raw,

        {{ excel_date('dataPublicacao') }}                         as publication_date,
        {{ excel_date('dataCelebracaoContrato') }}                 as signature_date,
        {{ excel_date('dataDecisaoAdjudicacao') }}                 as award_decision_date,
        {{ excel_date('dataFechoContrato') }}                      as closing_date,

        {{ amount('precoContratual') }}                            as contract_price,
        -- the few negative base and effective prices (27 and 21) are set to NULL like negative contract prices
        {{ amount('precoBaseProcedimento') }}                      as base_price_raw,
        {{ amount('PrecoTotalEfetivo') }}                          as effective_price_raw,

        split_part({{ clean('CPV') }}, chr(10), 1)                 as cpv_first,
        len(string_split({{ clean('CPV') }}, chr(10)))             as cpv_count,
        try_cast({{ clean('prazoExecucao') }} as integer)          as execution_days,
        {{ clean('LocalExecucao') }}                               as location_raw,
        {{ clean('fundamentacao') }}                               as legal_basis,
        {{ clean('ProcedimentoCentralizado') }} = 'Sim'            as is_centralised,
        {{ clean('numAcordoQuadro') }}                             as framework_agreement_no,
        {{ clean('regime') }}                                      as legal_regime,
        {{ clean('tipoFimContrato') }}                             as end_reason,
        {{ clean('ContratEcologico') }} = 'Sim'                    as is_ecological,
        {{ clean('TipoCriterioAdjudicacao') }}                     as award_criterion,
        {{ clean('objectoContrato') }}                             as contract_object
    from dedup
)

select
    * exclude (base_price_raw, effective_price_raw),
    -- Analysis date: the signature date. Simplified direct awards (art. 128) have no written contract and no
    -- signature date; for them the closing date is used, then the publication date. With this rule the year
    -- equals the file year (Ano) for every row, i.e. it is the year IMPIC files the contract under.
    coalesce(signature_date, closing_date, publication_date)       as contract_date,
    case when signature_date is not null then 'signature'
         when closing_date is not null then 'closing'
         else 'publication' end                                    as contract_date_basis,
    case when regexp_full_match(entity_nif_raw, '\d{9}') then entity_nif_raw
         when entity_missing then 'UNKNOWN'
         else 'NAME-' || left(md5(lower(entity_name)), 10) end      as entity_key,
    case when regexp_matches(cpv_first, '^\d{8}') then left(cpv_first, 8) end as cpv_code,
    case when regexp_matches(cpv_first, '^\d{8}') then left(cpv_first, 2) else '00' end as cpv_division,
    case when awardees_raw is null then 0
         else len(list_filter(string_split(awardees_raw, chr(10)), lambda x: trim(x) <> '')) end as n_awardees,
    case when bidders_raw is null then null
         else len(list_filter(string_split(bidders_raw, chr(10)), lambda x: trim(x) <> '')) end as bidders_count,
    case when contract_price < 0 then null else contract_price end as contract_value,
    case when base_price_raw < 0 then null else base_price_raw end as base_price,
    case when effective_price_raw < 0 then null else effective_price_raw end as effective_price
from parsed
