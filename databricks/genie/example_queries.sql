-- Quanto gastou cada tipo de entidade por ano? (How much did each type of public body spend per year?)
SELECT contract_year, entity_type, round(sum(contract_value_eur) / 1e6, 1) AS value_m_eur, count(*) AS contracts
FROM workspace.gold.contracts_enriched
GROUP BY ALL
ORDER BY contract_year, value_m_eur DESC;

-- Percentagem de concursos públicos com uma só proposta, por ano (single-bid share of open tenders)
SELECT contract_year,
       round(avg(CAST(is_single_bid AS INT)) * 100, 1) AS single_bid_pct,
       count(*) AS tenders_with_bidders_listed
FROM workspace.gold.contracts_enriched
WHERE procedure_group = 'Open tender' AND bidders_count IS NOT NULL
GROUP BY contract_year
ORDER BY contract_year;

-- Maiores fornecedores (empresas) por valor desde 2019 (largest named suppliers)
SELECT t.supplier_rank, s.supplier_name, round(t.allocated_value / 1e6, 1) AS value_m_eur, t.contracts,
       round(t.share_of_scope * 100, 2) AS share_pct
FROM workspace.gold.mart_top_suppliers t
JOIN workspace.gold.dim_supplier s USING (supplier_key)
WHERE t.rank_scope = 'All divisions' AND NOT s.is_withheld
ORDER BY t.supplier_rank;

-- Contratos logo abaixo dos limites legais (contracts just below the legal limits)
SELECT procedure_limit, threshold_family, threshold_eur, contracts_just_below, contracts_just_above,
       round(contracts_just_below / neighbour_bin_avg, 1) AS times_neighbour_average
FROM workspace.gold.mart_threshold_summary
ORDER BY threshold_family, threshold_eur;

-- Quanto gastaram os hospitais e outras entidades de saúde em 2025? (health spending in 2025)
SELECT round(sum(contract_value_eur) / 1e6, 1) AS value_m_eur, count(*) AS contracts
FROM workspace.gold.contracts_enriched
WHERE entity_type = 'Health' AND contract_year = 2025;

-- Que distritos tiveram mais valor em obras públicas em 2024? (districts with the most public-works value in 2024)
SELECT region, round(sum(contract_value_eur) / 1e6, 1) AS value_m_eur, count(*) AS contracts
FROM workspace.gold.contracts_enriched
WHERE contract_type = 'Public works' AND contract_year = 2024
  AND region_group NOT IN ('Multiple or national', 'Abroad', 'Not reported')
GROUP BY region
ORDER BY value_m_eur DESC
LIMIT 10;
