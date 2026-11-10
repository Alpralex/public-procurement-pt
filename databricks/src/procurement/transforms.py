"""Bronze -> silver transformations for the Portal BASE contract files, in PySpark.

The same functions run in three places:
  * the Lakeflow declarative pipeline on Databricks (src/pipeline/procurement_pipeline.py),
  * the unit tests (tests/test_transforms.py, local Spark, no Databricks needed),
  * scripts/run_local.py, which rebuilds silver from the real Parquet files and checks the totals against the
    DuckDB version of the project.

They port the dbt staging models in ../../models/staging (DuckDB SQL) to Spark. Business rules that need
reference data (entity types, districts, procedure groups) stay in the dbt gold layer.

Every source column is text. Dates are Excel serial numbers, amounts use '.' decimals, names carry HTML entities.
"""

from __future__ import annotations

from pyspark.sql import Column, DataFrame, Window
from pyspark.sql import functions as F

NL = "\n"

# Accented letters found in Portuguese and other European names -> plain letters (DuckDB's strip_accents).
_ACCENTED = "ÁÀÂÃÄÅÇÉÈÊËÍÌÎÏÑÓÒÔÕÖÚÙÛÜÝáàâãäåçéèêëíìîïñóòôõöúùûüýÿ"
_PLAIN = "AAAAAACEEEEIIIINOOOOOUUUUYaaaaaaceeeeiiiinooooouuuuyy"

# Company-form words in an awardee name, used for awardees without a NIF (foreign companies, associations).
COMPANY_WORDS = (
    r"(\bS\.?\s?A\.?U?\b|\bS\.?\s?L\.?U?\b|\bLDA\b|\bL\.DA\b|LIMITED|\bLTD\b|GMBH|\bB\.?\s?V\.?\b|\bINC\b"
    r"|\bS\.?R\.?L\b|\bAG\b|\bSAS\b|\bLLC\b|\bN\.?\s?V\.?\b|CORPORATION|COMPANY|ASSOCIA|UNIPESSOAL|\bS\.?P\.?A\b"
    r"|\bA/S\b|\bOY\b|SOCIEDAD|GROUP|\bPLC\b|\bKG\b|FUNDA|UNIVERSI|INSTITUT|\bSARL\b|\bS\.?A\.?S\b|\bCO\.)"
)

# NIF prefixes of natural persons, sole traders and estates: never named downstream.
PERSON_NIF = r"^([123]|45|70|74|75|8)"


# --------------------------------------------------------------------------------------------- helpers
def clean(c: str | Column) -> Column:
    """Trim; empty strings and the source's '∅' placeholder become NULL."""
    col = F.col(c) if isinstance(c, str) else c
    return F.nullif(F.nullif(F.trim(col), F.lit("")), F.lit("∅"))


def decode_html(col: Column) -> Column:
    """Decode the HTML entities found in names and drop escaped control characters (&#x13; etc.)."""
    out = col
    for entity, char in [("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'"), ("&amp;", "&")]:
        out = F.replace(out, F.lit(entity), F.lit(char))
    return F.trim(F.regexp_replace(out, r"&#x[0-9A-Fa-f]{1,2};", ""))


_INT = r"^-?[0-9]+$"
_NUM = r"^-?[0-9]+(\.[0-9]+)?([eE][-+]?[0-9]+)?$"


def to_int(col: Column, kind: str = "int") -> Column:
    """try_cast for integers that also works on runtimes without Column.try_cast and with ANSI mode on."""
    return F.when(col.rlike(_INT), col.cast(kind))


def to_double(col: Column) -> Column:
    return F.when(col.rlike(_NUM), col.cast("double"))


def excel_date(c: str) -> Column:
    """Excel serial day number stored as text -> DATE (1899-12-30 + n days)."""
    return F.date_add(F.lit("1899-12-30").cast("date"), to_int(clean(c)))


def amount(c: str) -> Column:
    """Amount text with '.' decimals -> DECIMAL(18,2)."""
    return F.round(to_double(clean(c)), 2).cast("decimal(18,2)")


def strip_accents(col: Column) -> Column:
    return F.translate(col, _ACCENTED, _PLAIN)


def nonblank_lines(col: Column) -> Column:
    """Split a multi-line cell into its non-blank lines (NULL stays NULL)."""
    return F.filter(F.split(col, NL), lambda x: F.trim(x) != "")


def _after_dash(col: Column) -> Column:
    pos = F.instr(col, " - ")
    return F.substr(col, pos + F.lit(3))


# --------------------------------------------------------------------------------------------- bronze
# Source columns the transformations read. IMPIC changes the published files from time to time (the November
# 2026 republication dropped TipoCriterioAdjudicacao, for example); a column that is missing is added as NULL so
# the pipeline keeps running, and the column list shows exactly which fields the model depends on.
REQUIRED = ["idcontrato", "Ano"]
OPTIONAL = [
    "nAnuncio", "tipoContrato", "idprocedimento", "tipoprocedimento", "objectoContrato", "adjudicante",
    "adjudicatarios", "dataPublicacao", "dataCelebracaoContrato", "precoContratual", "CPV", "prazoExecucao",
    "LocalExecucao", "fundamentacao", "ProcedimentoCentralizado", "numAcordoQuadro", "precoBaseProcedimento",
    "dataDecisaoAdjudicacao", "dataFechoContrato", "PrecoTotalEfetivo", "regime", "tipoFimContrato", "concorrentes",
    "ContratEcologico", "TipoCriterioAdjudicacao", "adjudicatarioPMEs", "Lotes", "NUTs",
]


def missing_columns(bronze: DataFrame) -> list[str]:
    have = set(bronze.columns)
    return [c for c in REQUIRED + OPTIONAL if c not in have]


def with_source_year(bronze: DataFrame, file_col: str = "_source_file") -> DataFrame:
    """Year of the yearly file a row came from (contratos_YYYY.parquet); adds missing optional columns as NULL."""
    absent = missing_columns(bronze)
    if any(c in REQUIRED for c in absent):
        raise ValueError(f"source files lack required columns: {[c for c in absent if c in REQUIRED]}")
    for c in absent:
        bronze = bronze.withColumn(c, F.lit(None).cast("string"))
    return bronze.withColumn(
        "source_file_year", to_int(F.regexp_extract(F.col(file_col), r"contratos_(\d{4})\.parquet", 1))
    )


# --------------------------------------------------------------------------------------------- silver
def dedup_contracts(bronze: DataFrame) -> DataFrame:
    """One row per idcontrato.

    4,566 ids appear more than once inside the same yearly file (9,144 rows; none across files). The copies differ
    only in secondary fields, so the latest file wins, then a fixed order, which makes the choice deterministic.
    """
    tiebreak = F.md5(
        F.concat_ws(
            "|",
            *[F.coalesce(F.col(c), F.lit("")) for c in ("adjudicatarios", "concorrentes", "Lotes", "NUTs")],
        )
    )
    w = Window.partitionBy("idcontrato").orderBy(
        F.col("source_file_year").desc(),
        F.col("TipoCriterioAdjudicacao").asc_nulls_last(),
        F.col("nAnuncio").asc_nulls_last(),
        tiebreak.asc(),
    )
    return bronze.withColumn("_rn", F.row_number().over(w)).where("_rn = 1").drop("_rn")


def parse_contracts(bronze: DataFrame) -> DataFrame:
    """Typed, cleaned contract rows (one per contract). Port of models/staging/stg_contracts.sql."""
    src = dedup_contracts(bronze)
    cpv = clean("CPV")
    parsed = src.select(
        to_int(F.trim(F.col("idcontrato")), "bigint").alias("contract_id"),
        "source_file_year",
        to_int(F.trim(F.col("Ano"))).alias("file_year_column"),
        clean("idprocedimento").alias("procedure_id"),
        clean("nAnuncio").alias("announcement_no"),
        F.when(F.col("tipoContrato").contains(NL), F.lit("Mixed"))
        .otherwise(F.coalesce(clean("tipoContrato"), F.lit("Not reported")))
        .alias("contract_type_pt"),
        F.coalesce(clean("tipoprocedimento"), F.lit("Not reported")).alias("procedure_name_pt"),
        F.trim(F.split_part(F.col("adjudicante"), F.lit(" - "), F.lit(1))).alias("entity_nif_raw"),
        decode_html(_after_dash(F.col("adjudicante"))).alias("entity_name"),
        F.col("adjudicante").isNull().alias("entity_missing"),
        clean("adjudicatarios").alias("awardees_raw"),
        clean("concorrentes").alias("bidders_raw"),
        clean("adjudicatarioPMEs").alias("sme_awardees_raw"),
        excel_date("dataPublicacao").alias("publication_date"),
        excel_date("dataCelebracaoContrato").alias("signature_date"),
        excel_date("dataDecisaoAdjudicacao").alias("award_decision_date"),
        excel_date("dataFechoContrato").alias("closing_date"),
        amount("precoContratual").alias("contract_price"),
        amount("precoBaseProcedimento").alias("base_price_raw"),
        amount("PrecoTotalEfetivo").alias("effective_price_raw"),
        F.split_part(cpv, F.lit(NL), F.lit(1)).alias("cpv_first"),
        F.when(cpv.isNotNull(), F.size(F.split(cpv, NL))).alias("cpv_count"),
        to_int(clean("prazoExecucao")).alias("execution_days"),
        clean("LocalExecucao").alias("location_raw"),
        clean("fundamentacao").alias("legal_basis"),
        (clean("ProcedimentoCentralizado") == "Sim").alias("is_centralised"),
        clean("numAcordoQuadro").alias("framework_agreement_no"),
        clean("regime").alias("legal_regime"),
        clean("tipoFimContrato").alias("end_reason"),
        (clean("ContratEcologico") == "Sim").alias("is_ecological"),
        clean("TipoCriterioAdjudicacao").alias("award_criterion"),
        clean("objectoContrato").alias("contract_object"),
    )

    awardee_lines = nonblank_lines(F.col("awardees_raw"))
    bidder_lines = nonblank_lines(F.col("bidders_raw"))
    return parsed.select(
        *[c for c in parsed.columns if c not in ("base_price_raw", "effective_price_raw")],
        # Analysis date: signature date; simplified direct awards (art. 128) have none, so closing date, then
        # publication date. With this rule the year equals the file year for every row.
        F.coalesce("signature_date", "closing_date", "publication_date").alias("contract_date"),
        F.when(F.col("signature_date").isNotNull(), "signature")
        .when(F.col("closing_date").isNotNull(), "closing")
        .otherwise("publication")
        .alias("contract_date_basis"),
        F.when(F.col("entity_nif_raw").rlike(r"^\d{9}$"), F.col("entity_nif_raw"))
        .when(F.col("entity_missing"), F.lit("UNKNOWN"))
        .otherwise(F.concat(F.lit("NAME-"), F.left(F.md5(F.lower("entity_name")), F.lit(10))))
        .alias("entity_key"),
        F.when(F.col("cpv_first").rlike(r"^\d{8}"), F.left("cpv_first", F.lit(8))).alias("cpv_code"),
        F.when(F.col("cpv_first").rlike(r"^\d{8}"), F.left("cpv_first", F.lit(2))).otherwise("00").alias("cpv_division"),
        F.when(F.col("awardees_raw").isNull(), 0).otherwise(F.size(awardee_lines)).alias("n_awardees"),
        F.when(F.col("bidders_raw").isNotNull(), F.size(bidder_lines)).alias("bidders_count"),
        F.when(F.col("contract_price") >= 0, F.col("contract_price")).alias("contract_value"),
        F.when(F.col("base_price_raw") >= 0, F.col("base_price_raw")).alias("base_price"),
        F.when(F.col("effective_price_raw") >= 0, F.col("effective_price_raw")).alias("effective_price"),
    )


def parse_awardees(contracts: DataFrame) -> DataFrame:
    """One row per awardee line of a contract, with a privacy-safe supplier key.

    Port of models/staging/stg_contract_awardees.sql. Natural persons are never keyed by NIF or name: they all map
    to WITHHELD-IND. The raw name stays in this silver table only (it is needed to count distinct withheld awardees
    in the concentration mart); gold dimensions never carry a natural person's name.
    """
    lines = contracts.where("n_awardees > 0").select(
        "contract_id",
        "n_awardees",
        F.posexplode(nonblank_lines(F.col("awardees_raw"))).alias("pos", "awardee_raw"),
    )
    parsed = lines.select(
        "contract_id",
        "n_awardees",
        (F.col("pos") + 1).alias("awardee_seq"),
        F.regexp_replace(F.trim(F.split_part("awardee_raw", F.lit(" - "), F.lit(1))), "[^0-9]", "").alias("nif_digits"),
        decode_html(_after_dash(F.col("awardee_raw"))).alias("awardee_name"),
    )
    classified = parsed.select(
        "*",
        F.when(F.length("nif_digits") >= 9, F.left("nif_digits", F.lit(9)))
        .when(F.length("nif_digits") > 0, F.col("nif_digits"))
        .alias("nif"),
        F.upper(strip_accents(F.col("awardee_name"))).rlike(COMPANY_WORDS).alias("has_company_word"),
    )
    # A line without NIF whose name also appears with a company or public-body NIF is that organisation.
    registered = (
        classified.where(F.col("nif").isNotNull() & ~F.col("nif").rlike(PERSON_NIF))
        .select(F.lower("awardee_name").alias("name_lc"))
        .distinct()
        .withColumn("is_registered_name", F.lit(True))
    )
    flagged = classified.join(
        registered, F.lower(classified["awardee_name"]) == registered["name_lc"], "left"
    ).withColumn(
        "looks_like_organisation", F.col("has_company_word") | F.coalesce(F.col("is_registered_name"), F.lit(False))
    )

    no_nif = F.col("nif").isNull()
    person_nif = F.col("nif").rlike(PERSON_NIF)
    org = F.col("looks_like_organisation")
    return flagged.select(
        "contract_id",
        "n_awardees",
        "awardee_seq",
        "nif",
        "awardee_name",
        F.when(no_nif & ~org, "WITHHELD-IND")
        .when(no_nif, "WITHHELD-NONIF")
        .when(person_nif, "WITHHELD-IND")
        .otherwise(F.col("nif"))
        .alias("supplier_key"),
        F.when(no_nif & ~org, "Individual")
        .when(no_nif, "No Portuguese NIF")
        .when(person_nif, "Individual")
        .when(F.left("nif", F.lit(1)) == "5", "Company")
        .when(F.left("nif", F.lit(1)) == "6", "Public body")
        .when(F.col("nif").rlike(r"^(71|98)"), "Non-resident entity")
        .otherwise("Other legal person")
        .alias("awardee_class"),
    )


def parse_location_lines(contracts: DataFrame) -> DataFrame:
    """One row per place-of-execution line ("Country, District, Municipality").

    The district mapping (seed table districts) is applied in the dbt gold layer.
    """
    lines = contracts.where(F.col("location_raw").isNotNull()).select(
        "contract_id", F.posexplode(F.split("location_raw", NL)).alias("pos", "line")
    )
    return lines.where(F.trim("line") != "").select(
        "contract_id",
        (F.col("pos") + 1).alias("line_seq"),
        F.trim(F.split_part("line", F.lit(","), F.lit(1))).alias("country"),
        F.trim(F.split_part("line", F.lit(","), F.lit(2))).alias("district"),
    )
