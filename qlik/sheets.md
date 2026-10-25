# Sheet guide

Seven sheets. Qlik is the lead tool for this project: the associative model lets a reader start from any
contracting entity, supplier or CPV division and see the rest follow (entity ↔ contract ↔ supplier ↔ CPV),
which is how a category manager or a spend analyst explores procurement data. Build the master items first;
each sheet takes 20 to 40 minutes.

Common to all sheets: a filter pane with Year, Contract Type, Entity Type, `[Procedure Group]` and
`[CPV Division]`, and the selections bar visible. Titles describe what the data show; they never say that an
entity or supplier did something wrong.

## 1. Overview: "Where does the money go?"
- KPIs: Contract Value, Contract Count, Average Contract Value, Direct Award Contracts %, Open Tender Value %.
- Bar chart: Year, Contract Value (subtitle: 2026 runs to 24 October).
- Bar chart: Entity Type, Contract Value, sorted descending, Value Share of Selection in the tooltip.
  **Health €31.31bn (26.0%), Municipality €30.08bn (25.0%).**
- Bar chart: `[CPV Division]`, Contract Value, limit to the top 12. **45 Construction work €35.85bn (29.7%),
  33 Medical and pharmaceutical €22.76bn (18.9%).**
- Map or bar chart: Region (sorted by its dual number), Contract Value.

## 2. Buyers and suppliers: "Who buys what from whom?" (associative exploration)
- Three filter panes side by side: Entity (searchable), `[CPV Division]`, Supplier.
- Table: Entity, Entity Type, Contract Value, Contract Count, Supplier Value. Sorted by Contract Value.
- Table: Supplier, `[Supplier Type]`, Supplier Value, Supplier Contract Count, Supplier Value Share.
  Add `[Supplier Visibility]` = Named as a dimension limit if the withheld rows should be hidden.
- Treemap: `[CPV Division]` → Entity Type, Contract Value.
- Try: select **Petrogal, S.A.** in Supplier: 5,191 contracts with 978 entities, €1.35bn; the Entity table
  then lists the buyers (largest: Estado Maior da Força Aérea, €162.2M). Select an entity instead and the
  supplier table shows its supplier base. The grey (excluded) values in each filter pane are the
  associations that do not exist, for example the CPV divisions a supplier never sold in.

## 3. Competition: "How is it bought?"
- KPIs: Direct Award Contracts %, Direct Award Value %, Single Bid %, Average Bidders.
- Bar chart: `[Procedure Group]`, two measures with TOTAL (share of contracts, share of value).
  **Direct awards 49.8% of contracts and 16.6% of value; open tenders 13.7% and 50.7%.**
- Line chart: Year, Single Bid %, dimension `[Procedure Group]` limited to Open tender, Prior consultation,
  Framework call-off. **Open tender 9.0% (2019) → 12.6% (2025); prior consultation 35.6% → 47.0%.**
- Table: `[Procedure Group]`, Procedure, Contract Count, Contracts With Bidder List, Average Bidders, Single Bid %.
  Note in the sheet: bidder lists exist for 688,077 contracts; direct awards normally list only the invited supplier.

## 4. Value limits: "Where do contract values sit around the legal limits?"
- Filter: `[Threshold Family]` = Goods and services (one value always selected).
- Bar chart: dimension `[Value Band]` (sort numerically), measure Contracts in Band, bars coloured by expression
  (orange for the band just below a limit). Reference lines at 20,000 and 75,000 for goods and services,
  30,000 and 150,000 for public works (set the reference line value as an expression on the band axis or use a
  combo chart with a constant line).
- KPIs: the eight limit measures. **Goods and services: 50,519 contracts at €19,000–19,999 against 12,290 at
  €20,000–20,999; 11,401 at €74,000–74,999 against 1,782 at €75,000–75,999. Public works: 3,616 against 521
  around €30,000; 1,789 against 100 around €150,000.**
- Table of LimitSummary: Limit Procedure, Limit EUR, Limit Contracts Below, Limit Contracts Above,
  Limit Neighbour Avg, `[Limit Contracts Below] / [Limit Neighbour Avg]` labelled "Below vs nearby", Limit Legal Source.
- Text box: "Limits of the Public Contracts Code in force from 2018 to 30 September 2026 (DL 111-B/2017 version);
  from 1 October 2026 DL 177/2026 raised them. The chart shows where values sit; it does not say why."

## 5. Concentration: "How concentrated is each category?"
- Table: `[CPV Division]`, Supplier Value, Dynamic HHI, Division HHI, Division Top 5 Share, Top 10 Named Supplier Share,
  Withheld Supplier Value %; background colour on Division HHI above 1,000.
  **CPV 45: HHI 59, top 5 11.6%. CPV 09 Energy and fuel: HHI 1,072, top 5 64.6%. CPV 64 Postal and telecom: HHI 1,634.**
- Scatter: `[CPV Division]`, x = Supplier Value, y = Dynamic HHI, bubble = Contract Count.
- Bar chart: Supplier (Named only), Supplier Value, top 15. **Top 10 named suppliers: 9.7% of all value.**
- Select one hospital (Entity) and watch Dynamic HHI change per division: the supplier base of one buyer.

## 6. Prices and timing: "How do prices compare with the base price, and when is the money committed?"
- Bar chart: `[Procedure Group]`, Price vs Base %. **Open tender −10.9%, prior consultation −6.1%, direct award −1.6%.**
- Table: `[Procedure Group]`, At Base Price %, Below Base Price %, Value of Closed Contracts, Final vs Signed %,
  Ended Above Contract %. **84.6% of direct awards are signed at exactly the base price; closed open tenders end
  2.6% above the signed value.**
- Bar chart: Month, Contract Value, with `_FullYear` = 1 (2019–2025). **December 10.2% of the value against an even 8.3%.**
- Bar chart: Entity Type, December Value % (complete years). Central government is the highest at 17.7%.

## 7. Contract explorer
- Straight table: ContractID, %Date, Entity, Entity Type, Supplier, `[CPV Division]`, Procedure, Contract Type,
  Region, ContractValue, BasePrice, EffectivePrice, Bidders. Limit the rows with selections first.
- This is the detail behind every other sheet; contract descriptions are not loaded (they can mention people).

## Bookmarks for the demo video
1. **"Just below €20,000"**: Threshold Family = Goods and services, Value Band = €19k on sheet 4.
2. **"Municipal works near €150,000"**: Entity Type = Municipality, Threshold Family = Public works on sheet 4
   (1,193 municipal works contracts at €149,000–149,999, €178.4M).
3. **"Single-bid prior consultations"**: Procedure Group = Prior consultation, `_SingleBid` = 1 on sheet 3.
4. **"Energy concentration"**: CPV Division = 09 Energy and fuel on sheet 5.
5. **"Hospital pharmacy suppliers"**: Entity Type = Health, CPV Division = 33 Medical and pharmaceutical on sheet 2.
6. **"December, central government"**: Entity Type = Central government, Month = Dec on sheet 6.
7. **"One supplier's buyers"**: Supplier = Petrogal, S.A. on sheet 2.

## Reference numbers (check after the first reload)

Computed with DuckDB from the Parquet files. Power BI must return the same values (see `../powerbi/README.md`).

| Check | Value |
| --- | ---: |
| Contract Count | 1,550,674 |
| Contract Value | 120,544,282,064 |
| Supplier Value (all suppliers) | 120,544,282,064 |
| Contract Value 2019 / 2022 / 2025 / 2026 | 8,994,807,328 / 13,105,511,434 / 23,751,746,455 / 16,655,163,350 |
| Contract Value, Health / Municipality | 31,309,318,521 / 30,083,125,589 |
| Direct Award Contracts % / Value % | 49.8% / 16.6% |
| Open Tender Contracts % / Value % | 13.7% / 50.7% |
| Contracts With Bidder List / Single Bid % / Average Bidders | 688,077 / 45.5% / 4.27 |
| Single Bid %, Open tender / Prior consultation | 10.2% / 43.4% |
| Limit measures (GS 20k, GS 75k, Works 30k, Works 150k; below / above) | 50,519 / 12,290; 11,401 / 1,782; 3,616 / 521; 1,789 / 100 |
| Contracts with a Value Band (0 – 199,999) | 1,472,360 |
| Top 10 Named Supplier Share | 9.7% |
| Withheld Supplier Value % | 6.3% |
| Division HHI, CPV 45 / 09 / 64 / 33 | 59 / 1,072 / 1,634 / 192 |
| Dynamic HHI, CPV 45 / 09 / 64 / 33 | 75 / 1,085 / 1,651 / 200 |
| Price vs Base %, Open tender / Prior consultation / Direct award | −10.9% / −6.1% / −1.6% |
| At Base Price %, Direct award | 84.6% |
| Final vs Signed %, Open tender | +2.6% |
| December Value %, 2019–2025 | 10.2% |
| Largest entity by value | Infraestruturas de Portugal, SA: 7,933,157,048 (5,443 contracts) |

## On first open, check

- The data model viewer shows no synthetic keys and no circular references: Contracts links to every dimension,
  ContractSupplier links Contracts (ContractID) to Suppliers (SupplierID), Concentration hangs off CPVDivision,
  LimitSummary stands alone.
- Contract Value and Supplier Value are equal with no selections.
- Supplier lists show *Individual (name withheld)* and *No Portuguese NIF (name withheld)*, never a person's name.
- The KPIs on sheets 3 and 4 match the table above.
