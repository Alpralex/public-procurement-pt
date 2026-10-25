# Portuguese public procurement in Power BI

The procurement spend model as a Power BI project (PBIP). The semantic model is written in TMDL, so every
table, relationship and DAX measure is readable in Git. The data are the Parquet files that
`scripts/export.py` writes to `powerbi/data/` (the same files the Qlik app loads, 24.3 MB in all).

## Open it

1. Copy this repository to the Windows machine, for example `C:\public-procurement-pt`.
2. Open `powerbi/ProcurementPT.pbip` in Power BI Desktop. If Desktop asks, turn on the PBIP and TMDL preview
   features in *Options > Preview features*.
3. In *Transform data > Manage parameters*, set **DataFolder** to the folder that holds the Parquet files,
   with a trailing backslash, for example `C:\public-procurement-pt\powerbi\data\`.
4. Select **Refresh**. The model loads about 1.55 million contracts and 1.58 million bridge rows; expect a
   refresh of under a minute.

If Desktop refuses the project, open a blank report instead, go to **TMDL view**, paste the whole of
`tmdl-view-script.tmdl` and select **Apply**. That creates the same parameter, tables, relationships and
measures. Then set DataFolder and refresh.

## Model

Star schema around one contract fact, plus a bridge for the suppliers. Every relationship is many-to-one,
single direction. `dim_date` is a daily calendar marked as the date table (`dataCategory: Time`, key `date_day`).

```
dim_date ─────────┐ contract_date → date_day
dim_entity ───────┤ entity_id
dim_cpv ──────────┼── fct_contracts (1,550,674) ──< bridge_contract_supplier (1,576,333) >── dim_supplier
dim_procedure ────┤ procedure_key                        contract_id                          supplier_id
dim_region ───────┤ region_key
dim_contract_type ┘ contract_type

dim_cpv ──< mart_supplier_concentration (CPV division × period)
dim_supplier ──< mart_top_suppliers
mart_threshold_summary, value_band (disconnected)      _Measures (measure table)
```

| Table | Grain and notes |
| --- | --- |
| fct_contracts | One row per contract, 2019-01-01 to 2026-10-24. `contract_value` = contract price in EUR without VAT. `base_price_comparable` is filled only for procedures with one contract and a value-to-base ratio between 0.2 and 5; `effective_price_closed` only for closed contracts with a final-to-contract ratio between 0.2 and 5. `bidders_count` is blank where the source lists no bidders. |
| bridge_contract_supplier | One row per contract and awardee. `allocation_share` = 1 / number of awardees, so shares add up to 1 per contract. |
| dim_supplier | Named suppliers keyed by NIF (`supplier_id` = NIF as a number). Natural persons are one row, `supplier_id` −1, *Individual (name withheld)*; awardees without a Portuguese NIF are −2, *No Portuguese NIF (name withheld)*; −3 is *Awardee not reported*. |
| dim_entity | Contracting authorities with their latest name and an entity type from the rules in `seeds/entity_type_rules.csv`. |
| mart_supplier_concentration | Top-1/5/10 shares and HHI per CPV division for `period` = `2019-2026` and for each year. Withheld individuals count as separate suppliers here, which the model itself cannot do. |
| mart_threshold_summary | Contracts in the EUR 1,000 below and above each legal limit (2019 – Sep 2026). |
| value_band | 200 EUR 1,000 bands (0 – 199,000), disconnected, for the histogram. |

Supplier filters reach the contract fact only through the bridge. `Supplier Value` iterates the bridge, so it
follows every dimension. For contract counts by supplier use `Contract Count by Supplier`, which switches the
bridge relationship to both directions inside the measure (`CROSSFILTER`), instead of a bidirectional
relationship in the model.

## Measures

All measures are in `_Measures` (44, in display folders). No measure shares a name with a column, ignoring
case: Power BI names are case-insensitive, so for example the count is *Contract Count*, not *Contracts*,
because three tables have a `contracts` column.

| Folder | Measures |
| --- | --- |
| 1 Spend | Contract Value, Contract Count, Average Contract Value, Value Share of Selection, Contract Share of Selection, Contract Value PY, Contract Value YoY %, December Value % |
| 2 Competition | Direct Award Contracts %, Direct Award Value %, Open Tender Contracts %, Open Tender Value %, Contracts With Bidder List, Single Bid Contracts, Single Bid %, Average Bidders |
| 3 Value limits | GS Direct Award Limit 20k Below / Above, GS Prior Consultation Limit 75k Below / Above, Works Direct Award Limit 30k Below / Above, Works Prior Consultation Limit 150k Below / Above, Contracts in Band |
| 4 Suppliers | Supplier Value, Supplier Contract Count, Supplier Value Share, Supplier Rank, Top 10 Named Supplier Share, Withheld Supplier Value %, Contract Count by Supplier, Contract Value by Supplier Filter, Division HHI, Division Top 5 Share |
| 5 Prices | Value With Base Price, Base Price Total, Price vs Base %, At Base Price %, Below Base Price %, Value of Closed Contracts, Effective Price Total, Final vs Signed %, Ended Above Contract % |

Key definitions:

| Measure | Definition |
| --- | --- |
| Direct Award Contracts % | Contracts in procedure groups *Direct award* and *Simplified direct award* over all contracts |
| Single Bid % | Contracts with `bidders_count` = 1 over contracts with a bidder list |
| GS Direct Award Limit 20k Below | Goods and services contracts from €19,000 to €19,999.99, dated up to 30 September 2026 (the limits rose on 1 October 2026) |
| Contracts in Band | Contracts in the €1,000 band of `value_band[band_start]`, same date cut; put `band_start` on the axis |
| Supplier Value | `SUMX(bridge, allocation_share × RELATED(fct_contracts[contract_value]))` |
| Top 10 Named Supplier Share | The ten named suppliers with the highest Supplier Value in context, over all Supplier Value (withheld rows included in the denominator) |
| Price vs Base % | Σ contract value ÷ Σ base_price_comparable − 1, over contracts with a comparable base price |
| Final vs Signed % | Σ effective_price_closed ÷ Σ contract value of the same contracts − 1 |
| December Value % | Value dated in December over the value in context; read it for complete years (2019–2025) |

## Report to build (five pages, 1280 × 720)

The report scaffold has the five pages, empty. Common header on every page: slicers for `dim_date[year_number]`,
`dim_contract_type[contract_type]` and `dim_entity[entity_type]`.

1. **Where the money goes**
   - Cards: Contract Value, Contract Count, Average Contract Value.
   - Clustered column: `dim_date[year_number]`, Contract Value (2026 runs to 24 October; say so in the title).
   - Bar: `dim_entity[entity_type]`, Contract Value, data labels with Value Share of Selection in the tooltip.
   - Bar: `dim_cpv[cpv_label]`, Contract Value, Top N = 12.
   - Filled map or bar: `dim_region[region]` (sorted by `sort_order`), Contract Value.
2. **How it is bought**
   - Cards: Direct Award Contracts %, Direct Award Value %, Open Tender Value %, Single Bid %.
   - Clustered bar: `dim_procedure[procedure_group]`, Value Share of Selection and a contract-share twin
     (`DIVIDE([Contract Count], CALCULATE([Contract Count], ALLSELECTED()))` as a visual calculation, or two visuals).
   - Line: `dim_date[year_number]`, Single Bid %, legend `dim_procedure[procedure_group]`, filtered to Open tender,
     Prior consultation and Framework call-off.
   - Table: procedure_group, Contract Count, Contracts With Bidder List, Average Bidders, Single Bid %.
3. **Values near the limits**
   - Column chart: axis `value_band[band_start]` (continuous off, bands 1,000 – 99,000), value Contracts in Band,
     slicer `dim_contract_type[threshold_family]` = Goods and services. Add constant lines at 19,500 and 74,500
     or colour the bands 19,000 and 74,000 with a rule.
   - Same for Public works with bands up to 199,000 (limits 30,000 and 150,000).
   - Cards: the eight limit measures; table of `mart_threshold_summary`.
   - Title wording: "Contract values near the legal limits". It describes where values sit, not why.
4. **Suppliers**
   - Table: `dim_supplier[supplier_name]`, Supplier Rank, Supplier Value, Supplier Value Share, Contract Count by Supplier,
     filter `dim_supplier[is_withheld]` = False, Top N 25 by Supplier Value.
   - Matrix: `dim_cpv[cpv_label]`, Supplier Value, Top 10 Named Supplier Share, Division HHI, Division Top 5 Share.
   - Card: Withheld Supplier Value %. Note under it that individuals are never named.
   - Clicking a supplier filters the other visuals through the bridge (supplier → bridge → contract → entity needs
     the CROSSFILTER measures for contract-level numbers).
5. **Prices and timing**
   - Bar: `dim_procedure[procedure_group]`, Price vs Base %; table with At Base Price %, Below Base Price %,
     Final vs Signed %, Ended Above Contract %.
   - Column: `dim_date[month_name]` (sorted by month_number), Contract Value, years 2019–2025, December highlighted.

Publish with *Publish to web* from your own Fabric workspace and put the link in the portfolio.

## Reference numbers

Computed with DuckDB from the Parquet files in `powerbi/data/`. The Qlik app must return the same values
(see `../qlik/sheets.md`). No filters unless stated.

| Check | Value |
| --- | ---: |
| Contract Count | 1,550,674 |
| Contract Value | 120,544,282,064 |
| Supplier Value (all suppliers) | 120,544,282,064 |
| Contract Value, year 2019 / 2022 / 2025 / 2026 | 8,994,807,328 / 13,105,511,434 / 23,751,746,455 / 16,655,163,350 |
| Contract Value, entity type Health / Municipality | 31,309,318,521 / 30,083,125,589 (26.0% / 25.0%) |
| Contract Count, entity type Health / Municipality | 555,771 / 385,530 |
| Direct Award Contracts % / Direct Award Value % | 49.8% / 16.6% |
| Open Tender Contracts % / Open Tender Value % | 13.7% / 50.7% |
| Contracts With Bidder List / Single Bid % / Average Bidders | 688,077 / 45.5% / 4.27 |
| Single Bid %, Open tender / Prior consultation | 10.2% / 43.4% |
| GS Direct Award Limit 20k Below / Above | 50,519 / 12,290 |
| GS Prior Consultation Limit 75k Below / Above | 11,401 / 1,782 |
| Works Direct Award Limit 30k Below / Above | 3,616 / 521 |
| Works Prior Consultation Limit 150k Below / Above | 1,789 / 100 |
| Top 10 Named Supplier Share | 9.7% |
| Withheld Supplier Value % | 6.3% |
| Division HHI, CPV 45 / 09 / 64 | 59 / 1,072 / 1,634 |
| Price vs Base %, Open tender / Prior consultation / Direct award | −10.9% / −6.1% / −1.6% |
| At Base Price %, Direct award | 84.6% |
| Final vs Signed %, Open tender | +2.6% |
| December Value %, years 2019–2025 | 10.2% |

## On first open, check

- Refresh runs without errors once DataFolder points at the Parquet folder (the decimal columns arrive as
  Decimal Number; the model types them as double).
- The model view shows `_Measures` with the measure-table icon, ten relationships, all single direction, none inactive.
- `dim_date` is marked as the date table (*Table tools > Mark as date table* shows `date_day`).
- Contract Value and Supplier Value both show 120,544,282,064 with no filter: the bridge loses nothing.
- `dim_supplier[supplier_name]` shows *Individual (name withheld)* and *No Portuguese NIF (name withheld)*, never a person's name.
- The cards on page 2 and the limit measures on page 3 match the table above.
