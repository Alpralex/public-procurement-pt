// Generates the PBIR pages, visuals and "ProcurementPT" theme for powerbi/ProcurementPT.Report.
// Run from the repo root: node scripts/build_powerbi_report.mjs
// The script owns every page listed below and the ProcurementPT theme; it rewrites them on each run.
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";

const REPORT = path.resolve("powerbi/ProcurementPT.Report");
const DEF = path.join(REPORT, "definition");
const VISUAL_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.9.0/schema.json";
const PAGE_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json";

// Same visual style as the AtlanticaFPA report in finance-fpa-analytics.
const C = {
  page: "#F7F8F9", card: "#FFFFFF", border: "#DCE0E5", text: "#1B2430", muted: "#5D6876", grid: "#ECEFF2",
  blue: "#2A78D6", orange: "#EB6834", green: "#1F7A35", amber: "#B25B00", grey: "#5D6876", red: "#B42318",
  greenSoft: "#E3F1E6", redSoft: "#FBE4E1", subtotal: "#EEF1F4",
};

// ---------- expression helpers ----------
const lit = (v) => ({ expr: { Literal: { Value: v } } });
const str = (s) => lit(`'${s.replace(/'/g, "''")}'`);
const num = (n) => lit(`${n}D`);
const int = (n) => lit(`${n}L`);
const bool = (b) => lit(b ? "true" : "false");
const fill = (hex) => ({ solid: { color: lit(`'${hex}'`) } });
const col = (entity, prop) => ({ Column: { Expression: { SourceRef: { Entity: entity } }, Property: prop } });
const proj = (field) => {
  const f = field.Column || field.Measure;
  const entity = f.Expression.SourceRef.Entity;
  return { field, queryRef: `${entity}.${f.Property}`, nativeQueryRef: f.Property };
};
const named = (field, displayName) => ({ ...proj(field), displayName });
const ref = (field) => proj(field).queryRef;
const id = (...parts) => crypto.createHash("sha1").update(parts.join("|")).digest("hex").slice(0, 20);
const filterId = (...parts) => "Filter" + crypto.createHash("sha1").update(parts.join("|")).digest("hex").slice(0, 24);

// Basic visual-level filter: column IN (literals).
function inFilter(page, key, field, literals) {
  const c = field.Column;
  const entity = c.Expression.SourceRef.Entity;
  return {
    name: filterId(page, key),
    field,
    type: "Categorical",
    filter: {
      Version: 2,
      From: [{ Name: "f", Entity: entity, Type: 0 }],
      Where: [{
        Condition: {
          In: {
            Expressions: [{ Column: { Expression: { SourceRef: { Source: "f" } }, Property: c.Property } }],
            Values: literals.map((v) => [{ Literal: { Value: v } }]),
          },
        },
      }],
    },
    howCreated: "User",
  };
}

// Column NOT IN (literals).
function notInFilter(page, key, field, literals) {
  const f = inFilter(page, key, field, literals);
  f.filter.Where[0].Condition = { Not: { Expression: f.filter.Where[0].Condition } };
  return f;
}


// ---------- fields ----------
const meas = (prop) => ({ Measure: { Expression: { SourceRef: { Entity: "_Measures" } }, Property: prop } });

const F = {
  year: col("dim_date", "year_number"),
  month: col("dim_date", "month_name"),
  contractType: col("dim_contract_type", "contract_type"),
  family: col("dim_contract_type", "threshold_family"),
  entityType: col("dim_entity", "entity_type"),
  cpv: col("dim_cpv", "cpv_label"),
  region: col("dim_region", "region"),
  procedure: col("dim_procedure", "procedure_group"),
  band: col("value_band", "band_start"),
  supplier: col("dim_supplier", "supplier_name"),
  withheld: col("dim_supplier", "is_withheld"),
  th: (name) => col("mart_threshold_summary", name),
};

const scopeOf = (field, literal) => ({
  data: [{ scopeId: { Comparison: { ComparisonKind: 0, Left: field, Right: { Literal: { Value: literal } } } } }],
});

// Top N filter on a category, ranked by a measure.
function topN(page, key, field, measure, n) {
  const c = field.Column;
  const entity = c.Expression.SourceRef.Entity;
  return {
    name: filterId(page, key),
    field,
    type: "TopN",
    filter: {
      Version: 2,
      From: [
        {
          Name: "subquery",
          Expression: {
            Subquery: {
              Query: {
                Version: 2,
                From: [{ Name: "d", Entity: entity, Type: 0 }, { Name: "m", Entity: "_Measures", Type: 0 }],
                Select: [{ Column: { Expression: { SourceRef: { Source: "d" } }, Property: c.Property }, Name: "field" }],
                OrderBy: [{ Direction: 2, Expression: { Measure: { Expression: { SourceRef: { Source: "m" } }, Property: measure.Measure.Property } } }],
                Top: n,
              },
            },
          },
          Type: 2,
        },
        { Name: "d", Entity: entity, Type: 0 },
      ],
      Where: [{
        Condition: {
          In: {
            Expressions: [{ Column: { Expression: { SourceRef: { Source: "d" } }, Property: c.Property } }],
            Table: { SourceRef: { Source: "subquery" } },
          },
        },
      }],
    },
    howCreated: "User",
  };
}

// column BETWEEN lo AND hi (integer column).
function betweenFilter(page, key, field, lo, hi) {
  const c = field.Column;
  const ref = { Column: { Expression: { SourceRef: { Source: "f" } }, Property: c.Property } };
  return {
    name: filterId(page, key),
    field,
    type: "Advanced",
    filter: {
      Version: 2,
      From: [{ Name: "f", Entity: c.Expression.SourceRef.Entity, Type: 0 }],
      Where: [{
        Condition: {
          And: {
            Left: { Comparison: { ComparisonKind: 2, Left: ref, Right: { Literal: { Value: `${lo}L` } } } },
            Right: { Comparison: { ComparisonKind: 4, Left: ref, Right: { Literal: { Value: `${hi}L` } } } },
          },
        },
      }],
    },
    howCreated: "User",
  };
}

// Year, contract type and entity type dropdowns, synced across pages.
function slicers(page) {
  const dropdown = (key, field, label, x, w) => container(page, key, { x, y: 16, w, h: 80 }, {
    visualType: "slicer",
    syncGroup: { groupName: `${key}Sync`, fieldChanges: true, filterChanges: true },
    query: { queryState: { Values: { projections: [proj(field)] } } },
    objects: {
      data: [{ properties: { mode: str("Dropdown") } }],
      header: [{ properties: { show: bool(true), text: str(label) } }],
    },
    visualContainerObjects: {
      general: [{ properties: { altText: str(`${label} filter dropdown. Applies to every page.`) } }],
      padding: [vcoPadding(8)],
    },
  });
  return [
    dropdown("slicer_year", F.year, "Year", 552, 200),
    dropdown("slicer_contract_type", F.contractType, "Contract type", 768, 240),
    dropdown("slicer_entity_type", F.entityType, "Contracting authority", 1024, 240),
  ];
}

function bars(page, key, pos, category, measure, title, alt, opts = {}) {
  return container(page, key, pos, {
    visualType: opts.type || "clusteredBarChart",
    query: {
      queryState: {
        Category: { projections: [named(category, opts.categoryName || "Category")] },
        Y: { projections: [named(measure, opts.valueName || "Value")] },
        ...(opts.tooltip ? { Tooltips: { projections: [named(opts.tooltip, opts.tooltipName || "Share")] } } : {}),
      },
      sortDefinition: { sort: [{ field: opts.sortField || measure, direction: opts.sort || "Descending" }], isDefaultSort: true },
    },
    objects: {
      dataPoint: opts.dataPoint || [{ properties: { fill: fill(opts.color || C.blue) } }],
      labels: [{
        properties: {
          show: bool(true), fontSize: num(9), color: fill(C.text),
          ...(opts.units ? { labelDisplayUnits: num(opts.units), labelPrecision: int(opts.precision ?? 1) } : {}),
        },
      }],
      categoryAxis: [{ properties: { ...axisOn, fontSize: num(9) } }],
      valueAxis: [{ properties: { show: bool(false), gridlineShow: bool(false), showAxisTitle: bool(false) } }],
      legend: [{ properties: { show: bool(false) } }],
    },
    visualContainerObjects: chartVcos(title, alt, opts.subtitle),
  }, opts.filters ? { filterConfig: { filters: opts.filters } } : {});
}

function table(page, key, pos, columns, title, alt, subtitle, opts = {}) {
  return container(page, key, pos, {
    visualType: "tableEx",
    query: {
      queryState: { Values: { projections: columns.map(([f, n]) => named(f, n)) } },
      ...(opts.sort ? { sortDefinition: { sort: [{ field: opts.sort, direction: opts.direction || "Descending" }], isDefaultSort: true } } : {}),
    },
    objects: {
      columnHeaders: [{ properties: { columnAdjustment: str("growToFit"), autoSizeColumnWidth: bool(true), fontSize: num(opts.fontSize || 10) } }],
      values: [{ properties: { fontSize: num(opts.fontSize || 10) } }],
      total: [{ properties: { totals: bool(false) } }],
    },
    visualContainerObjects: chartVcos(title, alt, subtitle),
  }, opts.filters ? { filterConfig: { filters: opts.filters } } : {});
}

// ---------- pages ----------
const PAGE_IDS = {
  spend: "b1c2d3e4f5a6b7c8d901", buying: "b1c2d3e4f5a6b7c8d902", limits: "b1c2d3e4f5a6b7c8d903",
  suppliers: "b1c2d3e4f5a6b7c8d904", prices: "b1c2d3e4f5a6b7c8d905",
};
const BN = 1000000000;

function spendPage() {
  const p = PAGE_IDS.spend;
  z = 0;
  const cards = [
    card(p, "card_value", { x: 16, y: 112, w: 405, h: 104 }, meas("Contract Value"), "Contract value (EUR, without VAT)", {
      units: "1000000000", precision: 1, alt: "Total contract value in euros without VAT.",
    }),
    card(p, "card_count", { x: 437, y: 112, w: 405, h: 104 }, meas("Contract Count"), "Contracts", {
      units: "1000000", precision: 2, alt: "Number of contracts.",
    }),
    card(p, "card_average", { x: 858, y: 112, w: 406, h: 104 }, meas("Average Contract Value"), "Average contract value", {
      units: "1000", precision: 1, alt: "Average value per contract.",
    }),
  ];
  const byYear = bars(p, "column_year", { x: 16, y: 232, w: 616, h: 224 }, F.year, meas("Contract Value"),
    "Contract value by year (2026 runs to 24 October)",
    "Column chart of contract value by year from 2019 to 2026; 2026 covers contracts up to 24 October.",
    { type: "clusteredColumnChart", sortField: F.year, sort: "Ascending", units: BN, categoryName: "Year", valueName: "Contract value", subtitle: "EUR billions" });
  const byEntity = bars(p, "bar_entity_type", { x: 648, y: 232, w: 616, h: 224 }, F.entityType, meas("Contract Value"),
    "Contract value by type of contracting authority",
    "Bar chart of contract value by type of contracting authority, largest first; health and municipalities lead.",
    { units: BN, categoryName: "Authority type", valueName: "Contract value", tooltip: meas("Value Share of Selection"), tooltipName: "Share of value", subtitle: "EUR billions" });
  const byCpv = bars(p, "bar_cpv", { x: 16, y: 472, w: 616, h: 232 }, F.cpv, meas("Contract Value"),
    "Top 12 CPV divisions by contract value",
    "Bar chart of the twelve CPV divisions (types of goods, services and works) with the highest contract value.",
    { units: BN, categoryName: "CPV division", valueName: "Contract value", subtitle: "EUR billions", filters: [topN(p, "top12_cpv", F.cpv, meas("Contract Value"), 12)] });
  const byRegion = bars(p, "bar_region", { x: 648, y: 472, w: 616, h: 232 }, F.region, meas("Contract Value"),
    "Contract value by district or region",
    "Bar chart of contract value by district or autonomous region where the contract is executed, in the official district order.",
    { units: BN, categoryName: "District or region", valueName: "Contract value", sortField: F.region, sort: "Ascending", subtitle: "EUR billions, place of execution" });
  return {
    name: p, displayName: "Where the money goes",
    visuals: [...header(p, "Where does public money go?", "Portuguese public contracts on Portal BASE, 2019 to 24 October 2026"),
      ...slicers(p), ...cards, byYear, byEntity, byCpv, byRegion],
  };
}

function buyingPage() {
  const p = PAGE_IDS.buying;
  z = 0;
  const pos = (i) => ({ x: 16 + i * 316, y: 112, w: 300, h: 104 });
  const cards = [
    card(p, "card_da_contracts", pos(0), meas("Direct Award Contracts %"), "Contracts by direct award", { alt: "Share of contracts awarded directly or by simplified direct award." }),
    card(p, "card_da_value", pos(1), meas("Direct Award Value %"), "Value by direct award", { alt: "Share of contract value awarded directly." }),
    card(p, "card_ot_value", pos(2), meas("Open Tender Value %"), "Value by open tender", { alt: "Share of contract value awarded by open tender." }),
    card(p, "card_single_bid", pos(3), meas("Single Bid %"), "Single-bid contracts", { alt: "Share of contracts with a bidder list that had only one bidder." }),
  ];
  const shares = container(p, "bar_procedure_share", { x: 16, y: 232, w: 616, h: 232 }, {
    visualType: "clusteredBarChart",
    query: {
      queryState: {
        Category: { projections: [named(F.procedure, "Procedure")] },
        Y: { projections: [named(meas("Contract Share of Selection"), "Share of contracts"), named(meas("Value Share of Selection"), "Share of value")] },
      },
      sortDefinition: { sort: [{ field: F.procedure, direction: "Ascending" }], isDefaultSort: true },
    },
    objects: {
      dataPoint: [
        { properties: { fill: fill(C.grey) }, selector: { metadata: ref(meas("Contract Share of Selection")) } },
        { properties: { fill: fill(C.blue) }, selector: { metadata: ref(meas("Value Share of Selection")) } },
      ],
      labels: [{ properties: { show: bool(true), fontSize: num(9), color: fill(C.text) } }],
      categoryAxis: [{ properties: { ...axisOn, fontSize: num(9) } }],
      valueAxis: [{ properties: { show: bool(false), gridlineShow: bool(false), showAxisTitle: bool(false) } }],
      legend: legendTop,
    },
    visualContainerObjects: chartVcos("Share of contracts and of value, by procedure",
      "Clustered bar chart comparing each procedure's share of contracts (grey) with its share of contract value (blue); direct awards are half the contracts but a sixth of the value.", null),
  });
  const singleBid = container(p, "line_single_bid", { x: 648, y: 232, w: 616, h: 232 }, {
    visualType: "lineChart",
    query: {
      queryState: {
        Category: { projections: [named(F.year, "Year")] },
        Y: { projections: [named(meas("Single Bid %"), "Single-bid share")] },
        Series: { projections: [named(F.procedure, "Procedure")] },
      },
    },
    objects: {
      dataPoint: [["Open tender", C.blue], ["Prior consultation", C.orange], ["Framework call-off", C.grey]]
        .map(([v, c]) => ({ properties: { fill: fill(c) }, selector: scopeOf(F.procedure, `'${v}'`) })),
      lineStyles: [{ properties: { strokeWidth: num(2), lineChartType: str("linear"), areaShow: bool(false) } }],
      legend: legendTop,
      labels: [{ properties: { show: bool(false) } }],
      categoryAxis: [{ properties: { ...axisOn } }],
      valueAxis: [{ properties: { ...axisOn, gridlineShow: bool(true), gridlineColor: fill(C.grid) } }],
    },
    visualContainerObjects: chartVcos("Single-bid share by year, competitive procedures",
      "Line chart of the share of contracts with only one bidder by year, for open tenders, prior consultations and framework call-offs.",
      "Contracts with a bidder list only"),
  }, { filterConfig: { filters: [inFilter(p, "competitive", F.procedure, ["'Open tender'", "'Prior consultation'", "'Framework call-off'"])] } });
  const stats = table(p, "table_procedure", { x: 16, y: 480, w: 1248, h: 224 }, [
    [F.procedure, "Procedure"], [meas("Contract Count"), "Contracts"], [meas("Contracts With Bidder List"), "With bidder list"],
    [meas("Average Bidders"), "Average bidders"], [meas("Single Bid %"), "Single bid"],
  ], "Competition by procedure", "Table by procedure group with the number of contracts, contracts with a bidder list, average bidders and single-bid share.",
  "Bidder lists are blank for most direct awards", { sort: F.procedure, direction: "Ascending" });
  return {
    name: p, displayName: "How it is bought",
    visuals: [...header(p, "How is it bought?", "Procedures, direct awards and single-bid contracts"),
      ...slicers(p), ...cards, shares, singleBid, stats],
  };
}

function limitsPage() {
  const p = PAGE_IDS.limits;
  z = 0;
  const histogram = (key, x, family, maxBand, limits, title, alt) => container(p, key, { x, y: 112, w: 616, h: 256 }, {
    visualType: "clusteredColumnChart",
    query: {
      queryState: {
        Category: { projections: [named(F.band, "Value band (EUR)")] },
        Y: { projections: [named(meas("Contracts in Band"), "Contracts")] },
      },
      sortDefinition: { sort: [{ field: F.band, direction: "Ascending" }], isDefaultSort: true },
    },
    objects: {
      dataPoint: [
        { properties: { fill: fill("#AEB6BF") } },
        ...limits.map((b) => ({ properties: { fill: fill(C.orange) }, selector: scopeOf(F.band, `${b}L`) })),
      ],
      labels: [{ properties: { show: bool(false) } }],
      categoryAxis: [{ properties: { ...axisOn, axisType: str("Scalar"), fontSize: num(9), labelDisplayUnits: num(1000) } }],
      valueAxis: [{ properties: { ...axisOn, gridlineShow: bool(true), gridlineColor: fill(C.grid), labelDisplayUnits: num(1000) } }],
      legend: [{ properties: { show: bool(false) } }],
    },
    visualContainerObjects: chartVcos(title, alt, `Contracts (thousands) per EUR 1,000 band. Orange: the band just below a limit. To 30 September 2026`),
  }, {
    filterConfig: {
      filters: [
        inFilter(p, key + "_family", F.family, [`'${family}'`]),
        betweenFilter(p, key + "_bands", F.band, 1000, maxBand),
      ],
    },
  });
  const gs = histogram("column_gs", 16, "Goods and services", 99000, [19000, 74000],
    "Goods and services: contracts by value (limits €20,000 and €75,000)",
    "Column chart of goods and services contracts in EUR 1,000 value bands from 1,000 to 99,000; the bands just below the 20,000 and 75,000 limits are orange and stand out.");
  const works = histogram("column_works", 648, "Public works", 199000, [29000, 149000],
    "Public works: contracts by value (limits €30,000 and €150,000)",
    "Column chart of public works contracts in EUR 1,000 value bands from 1,000 to 199,000; the bands just below the 30,000 and 150,000 limits are orange.");
  const limitCards = [
    ["GS Direct Award Limit 20k Below", "€19–20k"], ["GS Direct Award Limit 20k Above", "€20–21k"],
    ["GS Prior Consultation Limit 75k Below", "€74–75k"], ["GS Prior Consultation Limit 75k Above", "€75–76k"],
    ["Works Direct Award Limit 30k Below", "€29–30k"], ["Works Direct Award Limit 30k Above", "€30–31k"],
    ["Works Prior Consultation Limit 150k Below", "€149–150k"], ["Works Prior Consultation Limit 150k Above", "€150–151k"],
  ].map(([m, label], i) => card(p, `card_limit_${i}`, { x: 16 + i * 157, y: 400, w: 145, h: 80 }, meas(m), label, {
    units: "1", alt: `${i < 4 ? "Goods and services" : "Public works"} contracts with a value from ${label}.`,
  }));
  const familyLabel = (key, x, text) => textbox(p, key, { x, y: 376, w: 616, h: 20 }, text,
    { fontFamily: "Segoe UI Semibold", fontSize: "12px", color: C.text });
  const families = [familyLabel("label_goods", 16, "Goods and services: contracts just below and above each limit"), familyLabel("label_works", 644, "Public works: contracts just below and above each limit")];
  const summary = table(p, "table_threshold_summary", { x: 16, y: 496, w: 1248, h: 208 }, [
    [F.th("threshold_family"), "Contract family"], [F.th("procedure_limit"), "Procedure up to the limit"], [F.th("threshold_eur"), "Limit (EUR)"],
    [F.th("contracts_just_below"), "Contracts €1,000 below"], [F.th("contracts_just_above"), "Contracts €1,000 above"], [F.th("neighbour_bin_avg"), "Average of nearby bands"],
  ], "The legal limits and the contracts next to them", "Table of each legal value limit with the contracts in the EUR 1,000 band below and above it and the average of the nearby bands.",
  null, { sort: F.th("threshold_eur"), direction: "Ascending", fontSize: 9 });
  return {
    name: p, displayName: "Values near the limits",
    visuals: [...header(p, "Contract values near the legal limits", "Below each limit a simpler procedure is allowed. This shows where values sit, not why"),
      ...slicers(p), gs, works, ...families, ...limitCards, summary],
  };
}

function suppliersPage() {
  const p = PAGE_IDS.suppliers;
  z = 0;
  const top = table(p, "table_top_suppliers", { x: 16, y: 112, w: 640, h: 592 }, [
    [F.supplier, "Supplier"], [meas("Supplier Value"), "Value"],
    [meas("Supplier Value Share"), "Share"], [meas("Contract Count by Supplier"), "Contracts"],
  ], "Top 25 named suppliers by allocated value",
  "Table of the 25 named suppliers with the highest allocated contract value, with rank, value, share of all supplier value and number of contracts. Individuals are never named.",
  "A contract with several awardees is split equally between them", {
    sort: meas("Supplier Value"), fontSize: 9,
    filters: [inFilter(p, "named_only", F.withheld, ["false"]), topN(p, "top25", F.supplier, meas("Supplier Value"), 25)],
  });
  const conc = container(p, "matrix_concentration", { x: 672, y: 112, w: 592, h: 440 }, {
    visualType: "pivotTable",
    query: {
      queryState: {
        Rows: { projections: [named(F.cpv, "CPV division")] },
        Values: {
          projections: [
            named(meas("Supplier Value"), "Value"), named(meas("Top 10 Named Supplier Share"), "Top 10"),
            named(meas("Division HHI"), "HHI"), named(meas("Division Top 5 Share"), "Top 5"),
          ],
        },
      },
      sortDefinition: { sort: [{ field: meas("Supplier Value"), direction: "Descending" }], isDefaultSort: true },
    },
    objects: {
      columnHeaders: [{ properties: { columnAdjustment: str("growToFit"), autoSizeColumnWidth: bool(true), fontSize: num(9) } }],
      rowHeaders: [{ properties: { fontSize: num(9) } }],
      values: [{ properties: { fontSize: num(9) } }],
      columnFormatting: [{ properties: { labelDisplayUnits: str("1000000"), labelPrecision: int(0) }, selector: { metadata: ref(meas("Supplier Value")) } }],
    },
    visualContainerObjects: chartVcos("Supplier concentration by CPV division",
      "Matrix of CPV divisions with allocated value, the share of the ten largest named suppliers, the Herfindahl-Hirschman index and the share of the five largest suppliers.",
      "Value in EUR millions. HHI and top 5 for 2019–2026"),
  });
  const withheld = card(p, "card_withheld", { x: 672, y: 568, w: 592, h: 136 }, meas("Withheld Supplier Value %"),
    "Value to withheld names (individuals, foreign awardees)", {
      alt: "Share of supplier value going to natural persons and awardees without a Portuguese NIF, whose names are never shown.",
    });
  return {
    name: p, displayName: "Suppliers",
    visuals: [...header(p, "Who wins the contracts?", "Named companies only: individuals are grouped as Individual (name withheld)"),
      ...slicers(p), top, conc, withheld],
  };
}

function pricesPage() {
  const p = PAGE_IDS.prices;
  z = 0;
  const vsBase = meas("Price vs Base %");
  const priceBar = bars(p, "bar_price_vs_base", { x: 16, y: 112, w: 616, h: 296 }, F.procedure, vsBase,
    "Contract price against the base price, by procedure",
    "Bar chart of the contract price against the base price of the procedure, by procedure group; open tenders end about 11% below the base price, direct awards close to it.",
    {
      categoryName: "Procedure", valueName: "Price vs base", sortField: F.procedure, sort: "Ascending",
      subtitle: "Procedures with one contract and a comparable base price",
      dataPoint: [{ properties: { fill: { solid: { color: signCases(vsBase, C.orange, C.blue) } } }, selector: { data: [{ dataViewWildcard: { matchingOption: 1 } }] } }],
    });
  const priceTable = table(p, "table_prices", { x: 648, y: 112, w: 616, h: 296 }, [
    [F.procedure, "Procedure"], [meas("At Base Price %"), "At base price"], [meas("Below Base Price %"), "Below base"],
    [meas("Final vs Signed %"), "Final vs signed"], [meas("Ended Above Contract %"), "Ended above"],
  ], "Base prices and final prices, by procedure",
  "Table by procedure group with the share of contracts signed exactly at the base price, below it, the change from signed to final price and the share that ended above the contract price.",
  "Final prices: closed contracts only", { sort: F.procedure, direction: "Ascending", fontSize: 9 });
  const months = container(p, "column_month", { x: 16, y: 424, w: 1248, h: 280 }, {
    visualType: "clusteredColumnChart",
    query: {
      queryState: {
        Category: { projections: [named(F.month, "Month")] },
        Y: { projections: [named(meas("Contract Value"), "Contract value")] },
      },
      sortDefinition: { sort: [{ field: F.month, direction: "Ascending" }], isDefaultSort: true },
    },
    objects: {
      dataPoint: [
        { properties: { fill: fill("#AEB6BF") } },
        { properties: { fill: fill(C.orange) }, selector: scopeOf(F.month, "'Dec'") },
      ],
      labels: [{ properties: { show: bool(true), fontSize: num(9), color: fill(C.text), labelDisplayUnits: num(BN), labelPrecision: int(1) } }],
      categoryAxis: [{ properties: { ...axisOn } }],
      valueAxis: [{ properties: { show: bool(false), gridlineShow: bool(false), showAxisTitle: bool(false) } }],
      legend: [{ properties: { show: bool(false) } }],
    },
    visualContainerObjects: chartVcos("Contract value by month, 2019–2025",
      "Column chart of contract value by calendar month over the complete years 2019 to 2025; December, in orange, is the largest month.",
      "EUR billions. December in orange: budgets are spent before the year closes"),
  }, { filterConfig: { filters: [betweenFilter(p, "complete_years", F.year, 2019, 2025)] } });
  return {
    name: p, displayName: "Prices and timing",
    visuals: [...header(p, "What is paid, and when?", "Signed prices against base prices, final prices, and the December peak"),
      ...slicers(p), priceBar, priceTable, months],
  };
}


// ---------- visual builders ----------
let z = 0;
function container(page, key, pos, visual, extra = {}) {
  z += 1000;
  return {
    $schema: VISUAL_SCHEMA,
    name: id(page, key),
    position: { x: pos.x, y: pos.y, z, height: pos.h, width: pos.w, tabOrder: z },
    visual,
    ...extra,
  };
}

const vcoPadding = (p) => ({ properties: { top: num(p), bottom: num(p), left: num(p), right: num(p) } });

function chartVcos(title, alt, subtitle) {
  return {
    title: [{ properties: { show: bool(true), text: str(title) } }],
    general: [{ properties: { altText: str(alt) } }],
    padding: [vcoPadding(12)],
    // Without an explicit subtitle Desktop shows an auto-generated one in the UI language.
    subTitle: [{ properties: subtitle ? { show: bool(true), text: str(subtitle) } : { show: bool(false) } }],
  };
}

function textbox(page, key, pos, text, style) {
  return container(page, key, pos, {
    visualType: "textbox",
    objects: {
      general: [{
        properties: {
          paragraphs: [{ textRuns: [{ value: text, textStyle: style }], horizontalTextAlignment: "left" }],
        },
      }],
    },
    visualContainerObjects: {
      background: [{ properties: { show: bool(false) } }],
      border: [{ properties: { show: bool(false) } }],
      padding: [vcoPadding(0)],
    },
  });
}

function header(page, title, subtitle) {
  return [
    textbox(page, "title", { x: 16, y: 16, w: 520, h: 40 }, title,
      { fontFamily: "Segoe UI Semibold", fontSize: "22px", color: C.text }),
    textbox(page, "subtitle", { x: 16, y: 58, w: 520, h: 40 }, subtitle,
      { fontFamily: "Segoe UI", fontSize: "13px", color: C.muted }),
  ];
}

// Entity (multi-select dropdown) and fiscal year (single select, preset to 2026), synced across pages.
function card(page, key, pos, field, label, opts = {}) {
  const objects = {
    value: [{
      properties: {
        fontSize: num(20),
        ...(opts.units ? { labelDisplayUnits: str(opts.units) } : {}),
        ...(opts.precision !== undefined ? { labelPrecision: int(opts.precision) } : {}),
      },
      selector: { id: "default" },
    }],
    label: [{ properties: { show: bool(true), text: str(label), fontSize: num(11), fontColor: fill(C.muted) }, selector: { id: "default" } }],
    padding: [{ properties: { paddingUniform: num(8) }, selector: { id: "default" } }],
    layout: [{ properties: { paddingUniform: num(0) }, selector: { id: "default" } }],
    outline: [{ properties: { show: bool(false) }, selector: { id: "default" } }],
    divider: [{ properties: { show: bool(false) }, selector: { id: "default" } }],
  };
  if (opts.reference) {
    const refId = id(page, key, "ref");
    const sel = { data: [{ dataViewWildcard: { matchingOption: 0 } }], metadata: ref(field), id: refId, order: 0 };
    const partSel = { data: [{ dataViewWildcard: { matchingOption: 1 } }], metadata: ref(field), id: refId };
    objects.referenceLabel = [{ properties: { value: { expr: opts.reference.field } }, selector: sel }];
    const titleProps = { show: bool(true), titleContentType: str("custom"), titleText: str(opts.reference.title), titleFontColor: fill(C.muted) };
    objects.referenceLabelTitle = [
      { properties: titleProps, selector: { id: "default" } },
      { properties: titleProps, selector: partSel },
    ];
    const valueProps = { show: bool(true), valueFontColor: opts.reference.signColor ? signFont(opts.reference.field) : fill(C.text), valueBold: bool(true) };
    if (opts.reference.units) valueProps.valueDisplayUnits = str(opts.reference.units);
    if (opts.reference.precision !== undefined) valueProps.valuePrecision = int(opts.reference.precision);
    objects.referenceLabelValue = [{ properties: valueProps, selector: partSel }];
  }
  return container(page, key, pos, {
    visualType: "cardVisual",
    query: { queryState: { Data: { projections: [proj(field)] } } },
    objects,
    visualContainerObjects: {
      title: [{ properties: { show: bool(false) } }],
      general: [{ properties: { altText: str(opts.alt || label) } }],
      padding: [vcoPadding(8)],
      spacing: [{ properties: { customizeSpacing: bool(true), verticalSpacing: num(2) }, selector: { id: "default" } }],
    },
  });
}

// Green when the measure is above zero, red when below (the reporting sign makes > 0 favourable on every line).
function signCases(field, pos, neg) {
  return {
    expr: {
      Conditional: {
        Cases: [
          { Condition: { Comparison: { ComparisonKind: 1, Left: field, Right: { Literal: { Value: "0D" } } } }, Value: { Literal: { Value: `'${pos}'` } } },
          { Condition: { Comparison: { ComparisonKind: 3, Left: field, Right: { Literal: { Value: "0D" } } } }, Value: { Literal: { Value: `'${neg}'` } } },
        ],
      },
    },
  };
}
const signFont = (field) => ({ solid: { color: signCases(field, C.green, C.red) } });
const signBack = (field) => ({ solid: { color: signCases(field, C.greenSoft, C.redSoft) } });

const axisOn = { show: bool(true), fontSize: num(10), labelColor: fill(C.muted), showAxisTitle: bool(false) };
const legendTop = [{ properties: { show: bool(true), position: str("Top"), fontSize: num(10), labelColor: fill(C.muted) } }];

function lineChart(page, key, pos, category, series, title, alt, opts = {}) {
  return container(page, key, pos, {
    visualType: "lineChart",
    query: {
      queryState: {
        Category: { projections: [proj(category)] },
        Y: { projections: series.map((s) => named(s.field, s.name)) },
      },
    },
    objects: {
      dataPoint: series.map((s) => ({ properties: { fill: fill(s.color) }, selector: { metadata: ref(s.field) } })),
      lineStyles: [
        { properties: { strokeWidth: num(2), lineChartType: str("linear"), areaShow: bool(false) } },
        ...series.filter((s) => s.dashed).map((s) => ({ properties: { lineStyle: str("dashed") }, selector: { metadata: ref(s.field) } })),
      ],
      legend: legendTop,
      labels: [{ properties: { show: bool(false) } }],
      categoryAxis: [{ properties: { ...axisOn } }],
      valueAxis: [{ properties: { ...axisOn, gridlineShow: bool(true), gridlineColor: fill(C.grid), ...(opts.units ? { labelDisplayUnits: str(opts.units) } : {}) } }],
    },
    visualContainerObjects: chartVcos(title, alt, opts.subtitle),
  }, opts.filters ? { filterConfig: { filters: opts.filters } } : {});
}


// ---------- theme ----------
function theme(name) {
  const axis = { gridlineColor: { solid: { color: C.grid } }, labelColor: { solid: { color: C.muted } } };
  return {
    $schema: "https://raw.githubusercontent.com/microsoft/powerbi-desktop-samples/main/Report%20Theme%20JSON%20Schema/reportThemeSchema-2.153.json",
    name,
    dataColors: [C.blue, C.orange, C.green, C.amber, C.grey],
    good: C.green, neutral: C.grey, bad: C.red,
    maximum: "#256ABF", center: "#79A6DD", minimum: "#CDE2FB", null: C.grey,
    foreground: C.text, foregroundNeutralSecondary: C.muted, foregroundNeutralTertiary: C.muted,
    background: C.card, backgroundLight: C.grid, backgroundNeutral: C.border, tableAccent: C.blue,
    textClasses: {
      callout: { fontSize: 20, fontFace: "Segoe UI Semibold", color: C.text },
      title: { fontSize: 12, fontFace: "Segoe UI Semibold", color: C.text },
      header: { fontSize: 12, fontFace: "Segoe UI Semibold", color: C.text },
      label: { fontSize: 10, fontFace: "Segoe UI", color: C.text },
    },
    visualStyles: {
      "*": {
        "*": {
          background: [{ show: true, color: { solid: { color: C.card } }, transparency: 0 }],
          border: [{ show: true, color: { solid: { color: C.border } }, radius: 6, width: 1 }],
          dropShadow: [{ show: false }],
          padding: [{ top: 8, bottom: 8, left: 8, right: 8 }],
          title: [{ show: true, fontFamily: "Segoe UI Semibold", fontSize: 12, fontColor: { solid: { color: C.text } } }],
          subTitle: [{ fontFamily: "Segoe UI", fontSize: 10, fontColor: { solid: { color: C.muted } } }],
          categoryAxis: [{ ...axis, gridlineStyle: "solid" }],
          valueAxis: [{ ...axis, gridlineStyle: "solid" }],
          legend: [{ labelColor: { solid: { color: C.muted } } }],
        },
      },
      textbox: { "*": { padding: [{ top: 0, bottom: 0, left: 0, right: 0 }], background: [{ show: false }], border: [{ show: false }] } },
      cardVisual: { "*": { value: [{ bold: true, $id: "default" }], label: [{ show: true, $id: "default" }], title: [{ show: false }] } },
      slicer: {
        "*": {
          header: [{ fontFamily: "Segoe UI Semibold", textSize: 10, fontColor: { solid: { color: C.text } }, outlineStyle: 0 }],
          items: [{ fontFamily: "Segoe UI", textSize: 10, fontColor: { solid: { color: C.text } }, outlineStyle: 0, padding: 2 }],
        },
      },
      tableEx: {
        "*": {
          columnHeaders: [{ autoSizeColumnWidth: true, columnAdjustment: "growToFit", backColor: { solid: { color: C.page } }, fontColor: { solid: { color: C.text } }, bold: true }],
          values: [{ backColorPrimary: { solid: { color: C.card } }, backColorSecondary: { solid: { color: "#FAFBFC" } }, fontColorPrimary: { solid: { color: C.text } }, fontColorSecondary: { solid: { color: C.text } } }],
        },
      },
      pivotTable: {
        "*": {
          columnHeaders: [{ autoSizeColumnWidth: true, columnAdjustment: "growToFit", backColor: { solid: { color: C.page } }, fontColor: { solid: { color: C.text } }, bold: true }],
          rowHeaders: [{ fontColor: { solid: { color: C.text } } }],
          values: [{ backColorPrimary: { solid: { color: C.card } }, backColorSecondary: { solid: { color: C.card } }, fontColorPrimary: { solid: { color: C.text } }, fontColorSecondary: { solid: { color: C.text } } }],
        },
      },
    },
  };
}

// ---------- write ----------
const write = (file, obj) => {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, JSON.stringify(obj, null, 2) + "\n");
};

const pages = [spendPage(), buyingPage(), limitsPage(), suppliersPage(), pricesPage()];
for (const page of pages) {
  const dir = path.join(DEF, "pages", page.name);
  fs.rmSync(path.join(dir, "visuals"), { recursive: true, force: true });
  write(path.join(dir, "page.json"), {
    $schema: PAGE_SCHEMA,
    name: page.name,
    displayName: page.displayName,
    displayOption: "FitToPage",
    height: 720,
    width: 1280,
    objects: {
      background: [{ properties: { color: fill(C.page), transparency: num(0) } }],
      outspace: [{ properties: { color: fill(C.page), transparency: num(0) } }],
    },
    ...(page.filters ? { filterConfig: { filters: page.filters } } : {}),
  });
  for (const v of page.visuals) write(path.join(dir, "visuals", v.name, "visual.json"), v);
}

const pagesJsonPath = path.join(DEF, "pages", "pages.json");
const pagesJson = JSON.parse(fs.readFileSync(pagesJsonPath, "utf8"));
pagesJson.pageOrder = pages.map((p) => p.name);
pagesJson.activePageName = pages[0].name;
write(pagesJsonPath, pagesJson);

// Theme: rotate the file name on every run so Desktop does not serve a cached copy.
const regDir = path.join(REPORT, "StaticResources", "RegisteredResources");
fs.mkdirSync(regDir, { recursive: true });
for (const f of fs.readdirSync(regDir)) if (/^ProcurementPT-[0-9a-f]+\.json$/.test(f)) fs.rmSync(path.join(regDir, f));
const themeName = `ProcurementPT-${crypto.randomBytes(4).toString("hex")}.json`;
write(path.join(regDir, themeName), theme(themeName));

const reportPath = path.join(DEF, "report.json");
const report = JSON.parse(fs.readFileSync(reportPath, "utf8"));
report.themeCollection.customTheme = {
  name: themeName,
  reportVersionAtImport: report.themeCollection.baseTheme.reportVersionAtImport,
  type: "RegisteredResources",
};
report.resourcePackages = report.resourcePackages.filter((r) => r.type !== "RegisteredResources");
report.resourcePackages.push({
  name: "RegisteredResources",
  type: "RegisteredResources",
  items: [{ name: themeName, path: themeName, type: "CustomTheme" }],
});
write(reportPath, report);

console.log(`Wrote ${pages.length} pages, ${pages.reduce((n, p) => n + p.visuals.length, 0)} visuals, theme ${themeName}`);
