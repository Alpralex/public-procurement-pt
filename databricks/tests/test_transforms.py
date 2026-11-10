"""Unit tests for the bronze -> silver transformations (local Spark, no Databricks needed)."""

from datetime import date
from decimal import Decimal

from procurement import transforms as T

COLUMNS = [
    "idcontrato", "Ano", "nAnuncio", "tipoContrato", "idprocedimento", "tipoprocedimento", "objectoContrato",
    "adjudicante", "adjudicatarios", "dataPublicacao", "dataCelebracaoContrato", "precoContratual", "CPV",
    "prazoExecucao", "LocalExecucao", "fundamentacao", "ProcedimentoCentralizado", "numAcordoQuadro",
    "precoBaseProcedimento", "dataDecisaoAdjudicacao", "dataFechoContrato", "PrecoTotalEfetivo", "regime",
    "tipoFimContrato", "concorrentes", "ContratEcologico", "TipoCriterioAdjudicacao", "adjudicatarioPMEs",
    "Lotes", "NUTs", "_source_file",
]


def row(**kw):
    base = {c: None for c in COLUMNS}
    base.update(
        idcontrato="1001", Ano="2024", tipoContrato="Aquisição de serviços", tipoprocedimento="Ajuste Direto Regime Geral",
        adjudicante="600000001 - Câmara Municipal de Évora", adjudicatarios="500000001 - Alfa &amp; Beta, Lda",
        dataCelebracaoContrato="45306", precoContratual="19500.5", CPV="79410000-1 - Serviços de consultoria",
        _source_file="dbfs:/Volumes/workspace/raw/landing/contratos_2024.parquet",
    )
    base.update(kw)
    return tuple(base[c] for c in COLUMNS)


def bronze(spark, *rows):
    schema = ", ".join(f"`{c}` string" for c in COLUMNS)
    return T.with_source_year(spark.createDataFrame(list(rows), schema))


def test_parses_types_dates_and_html(spark):
    out = T.parse_contracts(bronze(spark, row())).collect()[0]
    assert out.contract_id == 1001
    assert out.source_file_year == 2024
    assert out.signature_date == date(2024, 1, 15)  # Excel serial 45306
    assert out.contract_date == date(2024, 1, 15) and out.contract_date_basis == "signature"
    assert out.contract_value == Decimal("19500.50")
    assert out.entity_key == "600000001" and out.entity_name == "Câmara Municipal de Évora"
    assert out.cpv_code == "79410000" and out.cpv_division == "79"
    assert out.n_awardees == 1 and out.bidders_count is None


def test_cpv_key_value_format_of_the_2026_republication(spark):
    cpv = "cpvID=71330000-0|cpvdescricao=Serviços diversos de engenharia|cpvValor=12800.00|CPVObjeto=Principal"
    out = T.parse_contracts(bronze(spark, row(CPV=cpv))).collect()[0]
    assert out.cpv_code == "71330000" and out.cpv_division == "71"


def test_empty_and_placeholder_become_null_and_negative_prices_drop(spark):
    out = T.parse_contracts(bronze(spark, row(precoContratual="-5", CPV="∅", concorrentes="  "))).collect()[0]
    assert out.contract_value is None and out.contract_price == Decimal("-5.00")
    assert out.cpv_code is None and out.cpv_division == "00"
    assert out.bidders_count is None


def test_date_falls_back_to_closing_then_publication(spark):
    a = T.parse_contracts(bronze(spark, row(dataCelebracaoContrato=None, dataFechoContrato="45307"))).collect()[0]
    b = T.parse_contracts(bronze(spark, row(dataCelebracaoContrato=None, dataPublicacao="45308"))).collect()[0]
    assert (a.contract_date, a.contract_date_basis) == (date(2024, 1, 16), "closing")
    assert (b.contract_date, b.contract_date_basis) == (date(2024, 1, 17), "publication")


def test_duplicates_keep_one_row_deterministically(spark):
    rows = [row(TipoCriterioAdjudicacao="Preço"), row(TipoCriterioAdjudicacao=None), row(idcontrato="1002")]
    out = T.parse_contracts(bronze(spark, *rows)).orderBy("contract_id").collect()
    assert [r.contract_id for r in out] == [1001, 1002]
    assert out[0].award_criterion == "Preço"


def test_unparseable_numbers_do_not_fail_in_ansi_mode(spark):
    out = T.parse_contracts(bronze(spark, row(idcontrato="abc", precoContratual="n/a", prazoExecucao="30 dias"))).collect()[0]
    assert out.contract_id is None and out.contract_value is None and out.execution_days is None


def test_entity_without_nif_gets_a_name_key(spark):
    out = T.parse_contracts(bronze(spark, row(adjudicante=" - Junta de Freguesia X"))).collect()[0]
    assert out.entity_key.startswith("NAME-") and len(out.entity_key) == 15


def test_awardees_are_classified_and_people_are_withheld(spark):
    awardees = "\n".join([
        "500000001 - Alfa, Lda",         # company NIF
        "123456789 - Maria Silva",        # natural person NIF
        " - - John Smith",                # no NIF, no company word -> individual
        " - - Acme GmbH",                 # no NIF, company word -> foreign company
        "",
    ])
    contracts = T.parse_contracts(bronze(spark, row(adjudicatarios=awardees)))
    out = {r.awardee_seq: r for r in T.parse_awardees(contracts).collect()}
    assert len(out) == 4 and out[1].n_awardees == 4
    assert (out[1].supplier_key, out[1].awardee_class) == ("500000001", "Company")
    assert (out[2].supplier_key, out[2].awardee_class) == ("WITHHELD-IND", "Individual")
    assert (out[3].supplier_key, out[3].awardee_class) == ("WITHHELD-IND", "Individual")
    assert (out[4].supplier_key, out[4].awardee_class) == ("WITHHELD-NONIF", "No Portuguese NIF")


def test_name_seen_with_a_company_nif_is_not_a_person(spark):
    rows = [
        row(idcontrato="1", adjudicatarios="500000009 - Clinica Sol"),
        row(idcontrato="2", adjudicatarios=" - - Clinica Sol"),
    ]
    awardees = T.parse_awardees(T.parse_contracts(bronze(spark, *rows)))
    second = awardees.where("contract_id = 2").collect()[0]
    assert second.supplier_key == "WITHHELD-NONIF"


def test_location_lines(spark):
    loc = "Portugal, Lisboa, Lisboa\nPortugal, Porto, Maia\n"
    lines = T.parse_location_lines(T.parse_contracts(bronze(spark, row(LocalExecucao=loc)))).collect()
    assert [(r.line_seq, r.country, r.district) for r in lines] == [(1, "Portugal", "Lisboa"), (2, "Portugal", "Porto")]


def test_missing_optional_columns_become_null(spark):
    df = spark.createDataFrame([row()], ", ".join(f"`{c}` string" for c in COLUMNS)).drop("TipoCriterioAdjudicacao", "NUTs")
    out = T.parse_contracts(T.with_source_year(df)).collect()[0]
    assert out.contract_id == 1001 and out.award_criterion is None
