# Where does Portugal's public procurement money go, and how is it bought?

A spend-analytics project on real open data: 1.55 million public contracts published on Portal BASE from
January 2019 to October 2026, €120.5bn without VAT. It looks at who buys what, how contracts are awarded, where
contract values sit around the legal limits, how concentrated each category is, and how prices compare with the
base price. The data are modelled in SQL with dbt on DuckDB and tested. The same marts feed a web dashboard, a
Qlik Sense app and a Power BI model.

**Live dashboard:** [`web/`](web/) · **Qlik Sense:** [`qlik/`](qlik/) · **Power BI:** [`powerbi/`](powerbi/)
**Stack:** Python, SQL, dbt, DuckDB, Qlik Sense (load script, set analysis, associative model), Power BI (PBIP/TMDL, DAX)

This is descriptive spend analysis of published records. The figures show patterns in the data; they say nothing
about whether any entity or supplier acted wrongly.

## Findings (2019 – 24 October 2026)

1. **Health and municipalities buy half of everything.** Health bodies (hospitals and local health units) signed
   €31.31bn (26.0%, 555,771 contracts) and municipalities €30.08bn (25.0%, 385,530). By category, construction work
   (CPV 45) is €35.85bn (29.7%) and medical and pharmaceutical products (CPV 33) €22.76bn (18.9%). The largest single
   buyer is Infraestruturas de Portugal: €7.93bn in 5,443 contracts.
2. **Half the contracts are direct awards, half the money goes through open tenders.** Direct awards (general and
   simplified) are 49.8% of contracts but 16.6% of value; open tenders are 13.7% of contracts and 50.7% of value.
   Where bidders are listed, 10.2% of open tenders and 43.4% of prior consultations received a single bid. The open
   tender share with one bid rose from 9.0% in 2019 to 12.6% in 2025, prior consultations from 35.6% to 47.0%.
3. **Contract values cluster just below the procedure limits.** For goods and services, 50,519 contracts fall between
   €19,000 and €19,999, against 12,290 between €20,000 and €20,999: 3.2 times the average of the neighbouring
   €1,000 bands. The pattern repeats below €75,000 (11,401 against 1,782, 5.2×), and for public works below €30,000
   (3,616 against 521, 4.5×) and €150,000 (1,789 against 100, 5.6×). The limits decide which procedures may be used,
   so values just below them are expected; the size of the step is what the chart shows.
4. **Most categories are competitive markets; energy and telecoms are not.** Construction (CPV 45) has an HHI of 59
   and its five largest suppliers hold 11.6%. Energy and fuel (CPV 09) has an HHI of 1,072 with 64.6% for the top
   five, postal and telecom services (CPV 64) 1,634 and 79.4%. Across all categories the ten largest named suppliers
   hold 9.7% of the value.
5. **Competitive procedures sign below the base price; contracts end slightly above it.** Open tenders sign 10.9%
   below the base price, prior consultations 6.1% and direct awards 1.6%; 84.6% of direct awards are signed at exactly
   the base price. Closed open tenders end 2.6% above the signed value, and 14.1% of them end above it. December holds
   10.2% of the value of 2019–2025 against 8.3% for an even month; central government is the highest at 17.7%.

## Model

```
data/raw/contratos_YYYY.parquet (39 text columns, one file per year)
        │
staging (views)                      marts (tables)
stg_contracts ──────────────┬──────▶ fct_contracts             one row per contract (1,550,674)
stg_contract_awardees ──────┼──────▶ bridge_contract_supplier  contract × awardee, value split equally (1,576,333)
stg_contract_locations ─────┘        dim_entity, dim_supplier, dim_cpv, dim_procedure, dim_region,
                                     dim_contract_type, dim_date (daily 2019–2026)
seeds                                mart_spend_summary          year × entity type × CPV × procedure × region
cpv_divisions, procedure_types,      mart_competition            procedure mix, bidders, single-bid share
contract_types, districts,           mart_threshold_bunching     €1,000 bands around each legal limit
entity_type_rules, thresholds        mart_threshold_summary      below / above / neighbour average per limit
                                     mart_supplier_concentration top-1/5/10 shares and HHI per CPV division
                                     mart_top_suppliers          ranked named suppliers
                                     mart_price_vs_base          contract vs base price, final vs signed price
                                     mart_monthly_spend          month profile, December share
```

- **20 models, 100 tests, 6 seeds** (`dbt build`: 126 nodes, all pass). Besides unique, not-null, relationships,
  accepted values and unique combinations, six singular tests check the data end to end: contract counts reconcile
  to the raw files, the analysis year equals the file year for every contract, the bridge allocates exactly the
  contract value, every mart adds up to the fact, no person's name reaches `dim_supplier`, and no withheld group is
  ranked among the top suppliers.
- **Contract date:** signature date, else the closing date (simplified direct awards have no signature date), else
  the publication date. With this rule the year equals the source file's year for 100% of contracts.
- **Duplicates:** 4,566 contract ids appear twice inside the same yearly file; one row is kept by a fixed rule.
- **Values:** contract price in EUR without VAT; 72 negative prices are treated as missing.
- **Multi-awardee contracts** (framework agreements, consortia) are split equally among the awardees in the bridge.
- **Entity type** is classified from the entity's name and NIF with 11 ordered rules in
  `seeds/entity_type_rules.csv` (Health, Parish, Municipality, Municipal company, Intermunicipal body, Education and
  research, Regional government, State-owned company, Central government...); anything unmatched is *Other public-law body*.
- **CPV:** the division (first two digits) with English names in `seeds/cpv_divisions.csv`.

## Privacy

Natural persons are never named in any output (Parquet, JSON, the apps or this README):

- Awardees with a Portuguese individual NIF (prefixes 1, 2, 3, and 45 for non-residents), a sole-trader or estate
  NIF (70, 74, 75, 8), or no NIF and a name without any company word, are collapsed into one supplier,
  *Individual (name withheld)* (`supplier_id` −1).
- Awardees without a Portuguese NIF whose name looks like a company's (mostly foreign firms) are
  *No Portuguese NIF (name withheld)* (−2), since the name alone cannot prove it is not a person. *Awardee not
  reported* is −3.
- Companies and public bodies are named. Contract descriptions are not exported (they can mention people).
- A dbt test and a final check in `scripts/export.py` fail the build if a withheld name appears in any export.

For the concentration figures computed in dbt, each withheld individual still counts as a separate supplier (an
internal hashed key that never leaves the database), so collapsing them does not inflate the HHI.

## Legal limits used

The Public Contracts Code (CCP, DL 18/2008 as revised by DL 111-B/2017), in force from 2018 to 30 September 2026:

| Contract type | Direct award | Prior consultation | Source |
| --- | --- | --- | --- |
| Goods and services | below €20,000 | below €75,000 | CCP art. 20 n.1 d) and c) |
| Public works | below €30,000 | below €150,000 | CCP art. 19 d) and c) |
| Goods and services, simplified direct award | up to €5,000 | | CCP art. 128 |

DL 177/2026 of 4 September 2026 raised the limits from 1 October 2026 (goods and services €75,000 and €130,000;
works €150,000 and €1,000,000), so the limit analysis uses contracts dated up to 30 September 2026. The special
measures of Lei 30/2021 also allowed simplified direct awards up to €15,000 in some cases. Sources: the Public
Contracts Code; the Segurança Social public procurement FAQ
(https://sisscontent.seg-social.pt/documents/10152/18433474/FAQS_CONTRATA%C3%87%C3%83O+P%C3%9ABLICA.pdf/938be50e-1705-405c-ab4b-3020997e39cf);
APCMC circular 70/2026 on DL 177/2026 (https://apcmc.pt/wp-content/uploads/circular-70-2026.pdf).
All limits, with their legal basis, are in `seeds/thresholds.csv`.

## Run it

```bash
pip install dbt-duckdb==1.9.1
python scripts/get_data.py          # downloads contratos2019-2026.xlsx, writes data/raw/contratos_YYYY.parquet
dbt build --profiles-dir .          # 20 models, 100 tests, 6 seeds
python scripts/export.py            # powerbi/data/*.parquet (24.3 MB) and web/data/*.json (1.2 MB)
```

The raw files were downloaded on 2026-10-25 on a Windows machine: the container that built this project could not
reach dados.gov.pt. `get_data.py` looks up the current file URLs through the dados.gov.pt API and runs anywhere with
internet access; `--skip-download` converts xlsx files placed in `data/xlsx/` by hand. Raw data are not committed
(`/data/` is in `.gitignore`).

Open `web/index.html` through any static server (`python -m http.server` in `web/`). The Qlik and Power BI versions
read the Parquet files in `powerbi/data/`; see their folders for the steps.

## Three tools, one model

- **Qlik Sense** (`qlik/`): the lead version. `load_script.qvs` loads the star schema and the supplier bridge with no
  synthetic keys, so selecting an entity, a supplier or a CPV division filters everything else
  (entity ↔ contract ↔ supplier ↔ CPV). `master_items.md` has the measures in set analysis, including an HHI that
  follows every selection; `sheets.md` the seven sheets and the demo bookmarks.
- **Power BI** (`powerbi/`): PBIP project with the model in TMDL, 43 DAX measures that mirror the Qlik ones, a daily
  date table, a `DataFolder` parameter and a five-page report spec.
- **Web** (`web/`): a static page with the five questions, filters by year, contract type and entity type, and the method.

## Data source and licence

Portal BASE contracts published by IMPIC on dados.gov.pt, dataset *Contratos Públicos - Portal BASE - IMPIC -
Contratos de 2012 a 2026* (https://dados.gov.pt/pt/datasets/66d72d488ca4b7cb2de28712/), open data under the terms
stated on the dataset page. Downloaded 2026-10-25; `data/raw/schema.md` lists the files, row counts and URLs.
This project is not affiliated with IMPIC or dados.gov.pt.

## Caveats

- 2026 is partial (to 24 October) and the limits changed on 1 October 2026.
- Bidder lists exist for 688,077 contracts (44%); direct awards usually list only the invited supplier, so single-bid
  shares are quoted for competitive procedures.
- The base price belongs to the procedure, which can have several lots and contracts; it is compared only for
  procedures with one contract and a value-to-base ratio between 0.2 and 5. Final prices are compared only for closed
  contracts, with the same ratio range.
- The SME flag (`adjudicatarioPMEs`) is filled mostly from 2024 and not consistently (large companies are flagged
  in some contracts and not in others), so it is not used for findings.
- €21.47bn (17.8%) has a place of execution of "Portugal" with no district, and €6.51bn spans several districts.
- Entity types come from name rules and are approximate for unusual names.
- Each contract appears once, at its signature value; later modifications (a separate dataset) are not included.

## Reference numbers for the apps

Both apps should show these with no selections (more in `powerbi/README.md` and `qlik/sheets.md`).

| Check | Value |
| --- | ---: |
| Contracts | 1,550,674 |
| Contract value (= supplier value through the bridge) | 120,544,282,064 |
| Value 2019 / 2020 / 2021 / 2022 | 8,994,807,328 / 11,158,713,662 / 13,160,652,350 / 13,105,511,434 |
| Value 2023 / 2024 / 2025 / 2026 | 15,532,745,622 / 18,184,941,863 / 23,751,746,455 / 16,655,163,350 |
| Contracting entities / named suppliers | 8,845 / 74,389 |
| Direct award contracts % / value % | 49.8% / 16.6% |
| Single bid %, all contracts with a bidder list | 45.5% |
| Goods and services €19,000–19,999 / €20,000–20,999 | 50,519 / 12,290 |
| Top 10 named supplier share / withheld supplier value | 9.7% / 6.3% |
| Price vs base, open tender | −10.9% |

## Files

```
scripts/get_data.py        download the yearly xlsx files and convert them to Parquet
seeds/                     CPV divisions, procedure types, contract types, districts, entity rules, legal limits
models/                    dbt staging and marts
tests/                     generic tests (unique combination, non-negative) and singular reconciliation and privacy tests
scripts/export.py          Parquet for Power BI and Qlik, JSON for the web page, privacy check
web/                       static dashboard
qlik/                      load script, master items, sheets and bookmarks
powerbi/                   PBIP project: TMDL model and DAX measures
screenshots/               the web page at 1280 and 390 px, light and dark
```
