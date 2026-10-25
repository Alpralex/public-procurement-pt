# Master items

Create these under **Master items** after the first reload. They mirror the Power BI measures one to one
(same names). All amounts are EUR without VAT. Contract counts use the `_Contract` field (1 per contract),
so they ignore the bridge: selecting a supplier still counts each of its contracts once.

Fields that drive the expressions:

- `ContractValue` (Contracts): contract price; NULL for the 72 negative prices.
- `AllocatedValue` (ContractSupplier): the contract value split equally among the awardees, computed at load.
- Flags in Contracts: `_HasBidderList`, `_SingleBid`, `_HasBasePrice`, `_AtBasePrice`, `_BelowBasePrice`, `_Closed`,
  `_EndedAbove`, `_LimitPeriod` (dated up to 30 September 2026).
- Flags in MasterCalendar: `_December`, `_FullYear` (2019–2025).

## Measures

### 1 Spend

| Name | Expression | Format |
|---|---|---|
| Contract Value | `Sum(ContractValue)` | Money `€#,##0;-€#,##0` |
| Contract Count | `Sum(_Contract)` | `#,##0` |
| Average Contract Value | `Sum(ContractValue) / Sum(_Contract)` | Money |
| Value Share of Selection | `Sum(ContractValue) / Sum(TOTAL ContractValue)` | `0.0%` |
| Contract Value PY | `Sum({<Year={$(=Max(Year)-1)}, YearMonth=, Month=, Quarter=, %Date=>} ContractValue)`: use with one year selected or on a KPI | Money |
| Contract Value YoY % | `Sum(ContractValue) / Sum({<Year={$(=Max(Year)-1)}, YearMonth=, Month=, Quarter=, %Date=>} ContractValue) - 1` | `+0.0%;-0.0%` |
| December Value % | `Sum({<_December={1}>} ContractValue) / Sum(ContractValue)` (add `_FullYear={1}` in both sets to use complete years only) | `0.0%` |

### 2 Competition

| Name | Expression | Format |
|---|---|---|
| Direct Award Contracts % | `Sum({<[Procedure Group]={'Direct award','Simplified direct award'}>} _Contract) / Sum(_Contract)` | `0.0%` |
| Direct Award Value % | `Sum({<[Procedure Group]={'Direct award','Simplified direct award'}>} ContractValue) / Sum(ContractValue)` | `0.0%` |
| Open Tender Contracts % | `Sum({<[Procedure Group]={'Open tender'}>} _Contract) / Sum(_Contract)` | `0.0%` |
| Open Tender Value % | `Sum({<[Procedure Group]={'Open tender'}>} ContractValue) / Sum(ContractValue)` | `0.0%` |
| Contracts With Bidder List | `Sum(_HasBidderList)` | `#,##0` |
| Single Bid Contracts | `Sum(_SingleBid)` | `#,##0` |
| Single Bid % | `Sum(_SingleBid) / Sum(_HasBidderList)` | `0.0%` |
| Average Bidders | `Avg(Bidders)` | `0.00` |

In a chart with `[Procedure Group]` as the dimension, the two "share" measures that should ignore the row
need `TOTAL`: share of contracts `Sum(_Contract) / Sum(TOTAL _Contract)`, share of value
`Sum(ContractValue) / Sum(TOTAL ContractValue)`.

### 3 Value limits

The eight limit measures mirror the DAX ones. `vBand` in the script holds the pattern.

| Name | Expression | Format |
|---|---|---|
| GS Direct Award Limit 20k Below | `Sum({<[Threshold Family]={'Goods and services'}, _LimitPeriod={1}, ContractValue={">=19000<20000"}>} _Contract)` | `#,##0` |
| GS Direct Award Limit 20k Above | same with `ContractValue={">=20000<21000"}` | `#,##0` |
| GS Prior Consultation Limit 75k Below | same with `ContractValue={">=74000<75000"}` | `#,##0` |
| GS Prior Consultation Limit 75k Above | same with `ContractValue={">=75000<76000"}` | `#,##0` |
| Works Direct Award Limit 30k Below | `Sum({<[Threshold Family]={'Public works'}, _LimitPeriod={1}, ContractValue={">=29000<30000"}>} _Contract)` | `#,##0` |
| Works Direct Award Limit 30k Above | same with `ContractValue={">=30000<31000"}` | `#,##0` |
| Works Prior Consultation Limit 150k Below | same with `ContractValue={">=149000<150000"}` | `#,##0` |
| Works Prior Consultation Limit 150k Above | same with `ContractValue={">=150000<151000"}` | `#,##0` |
| Contracts in Band | `Sum({<_LimitPeriod={1}>} _Contract)` with dimension `[Value Band]` | `#,##0` |

`[Value Band]` is a dual (text "€19k", number 19000), so a bar chart sorted numerically by `[Value Band]` is
the histogram; colour bars by expression
`If(Match(Num([Value Band]), 19000, 74000, 29000, 149000), '#eb6834', '#2a78d6')`.

### 4 Suppliers

| Name | Expression | Format |
|---|---|---|
| Supplier Value | `Sum(AllocatedValue)` | Money |
| Supplier Contract Count | `Count(DISTINCT ContractID)` (with a supplier dimension: the contracts it took part in) | `#,##0` |
| Supplier Value Share | `Sum(AllocatedValue) / Sum(TOTAL AllocatedValue)` | `0.00%` |
| Supplier Rank | `If([Supplier Visibility] = 'Named', Rank(TOTAL Sum({<[Supplier Visibility]={'Named'}>} AllocatedValue)))` with dimension Supplier | `0` |
| Top 10 Named Supplier Share | `Sum({<SupplierID={"=Rank(Sum({<[Supplier Visibility]={'Named'}>} AllocatedValue), 4) <= 10"}, [Supplier Visibility]={'Named'}>} AllocatedValue) / Sum(AllocatedValue)` | `0.0%` |
| Withheld Supplier Value % | `Sum({<[Supplier Visibility]={'Withheld'}>} AllocatedValue) / Sum(AllocatedValue)` | `0.0%` |
| Dynamic HHI | `Sum(Aggr(Sqr(Sum(AllocatedValue) / Sum(TOTAL <CPVDivision> AllocatedValue)), CPVDivision, SupplierID)) * 10000` with dimension `[CPV Division]` | `#,##0` |
| Division HHI | `Sum({<[Concentration Period]={'2019-2026'}>} [Conc HHI])` with dimension `[CPV Division]` | `#,##0` |
| Division Top 5 Share | `Sum({<[Concentration Period]={'2019-2026'}>} [Conc Top 5 Share])` | `0.0%` |

**Dynamic HHI** responds to every selection (years, entity type, a single hospital), which Power BI can only do
with a heavier DAX pattern. It treats each withheld group (individuals, no Portuguese NIF, not reported) as one
supplier, so it is slightly higher than **Division HHI** from dbt, which counts each withheld individual separately
(CPV 45: 75 against 59; CPV 09: 1,085 against 1,072).

In `Top 10 Named Supplier Share` the set uses an advanced search on `SupplierID`: each supplier is ranked by its
value in the current selection and the ten best are kept. Rank mode 4 gives ties the lowest rank, so exactly ten
remain.

### 5 Prices

| Name | Expression | Format |
|---|---|---|
| Value With Base Price | `Sum({<_HasBasePrice={1}>} ContractValue)` | Money |
| Base Price Total | `Sum(BasePrice)` | Money |
| Price vs Base % | `Sum({<_HasBasePrice={1}>} ContractValue) / Sum(BasePrice) - 1` | `+0.0%;-0.0%` |
| At Base Price % | `Sum(_AtBasePrice) / Sum(_HasBasePrice)` | `0.0%` |
| Below Base Price % | `Sum(_BelowBasePrice) / Sum(_HasBasePrice)` | `0.0%` |
| Value of Closed Contracts | `Sum({<_Closed={1}>} ContractValue)` | Money |
| Effective Price Total | `Sum(EffectivePrice)` | Money |
| Final vs Signed % | `Sum(EffectivePrice) / Sum({<_Closed={1}>} ContractValue) - 1` | `+0.0%;-0.0%` |
| Ended Above Contract % | `Sum(_EndedAbove) / Sum(_Closed)` | `0.0%` |

## Dimensions

- **Buyer** (drill-down): Entity Type → Entity
- **Category** (drill-down): CPV Division → (contract list)
- **Procedure** (drill-down): Procedure Group → Procedure
- **Time** (drill-down): Year → Quarter → YearMonth
- **Place** (drill-down): Region Group → Region
- **Supplier**: Supplier (with `[Supplier Visibility]` as a filter: Named / Withheld)
- Contract Type, Threshold Family, Competition Type, Value Band

## Colours

Use the web page palette so all three tools look alike: blue `#2a78d6` for the main series, orange `#eb6834`
for the comparison series and for the bands just below a legal limit, grey `#5d6876` for totals and for regions
shown apart (multiple districts, Portugal unspecified). Assign master colours to `[Procedure Group]` values:
Open tender blue, Prior consultation orange, Direct award grey, the rest light grey.
