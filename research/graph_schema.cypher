// =============================================================
// ETF 透視鏡 PASSPORT — Neo4j v5 Graph Schema
// 持股快照日：2026-06-05（真實成分股，HOLDS query 一律 date('2026-06-05')）
// 規則：不使用 OVER() 視窗函式（neo4j 5.x 不支援）；改用 WITH/COLLECT/ORDER BY
//
// 所有 hero 數字（如 31.1% 台積電穿透曝險）都應該從這個 schema +
// data/snapshot_2026-06-05/ 的 CSV 直接重算得出。
// =============================================================

// -------------------------------------------------------------
// 1. CONSTRAINTS（neo4j v5 語法）
// -------------------------------------------------------------
CREATE CONSTRAINT etf_ticker IF NOT EXISTS
  FOR (e:ETF) REQUIRE e.ticker IS UNIQUE;

CREATE CONSTRAINT stock_ticker IF NOT EXISTS
  FOR (s:Stock) REQUIRE s.ticker IS UNIQUE;

CREATE CONSTRAINT issuer_name IF NOT EXISTS
  FOR (i:Issuer) REQUIRE i.name IS UNIQUE;

CREATE CONSTRAINT index_code IF NOT EXISTS
  FOR (idx:Index) REQUIRE idx.code IS UNIQUE;

CREATE CONSTRAINT theme_name IF NOT EXISTS
  FOR (t:Theme) REQUIRE t.name IS UNIQUE;

CREATE CONSTRAINT sector_code IF NOT EXISTS
  FOR (sec:Sector) REQUIRE sec.code IS UNIQUE;

CREATE CONSTRAINT bucket_name IF NOT EXISTS
  FOR (b:InvestorBucket) REQUIRE b.name IS UNIQUE;

CREATE CONSTRAINT document_id IF NOT EXISTS
  FOR (d:Document) REQUIRE d.id IS UNIQUE;

CREATE CONSTRAINT regulatory_id IF NOT EXISTS
  FOR (r:RegulatoryEvent) REQUIRE r.id IS UNIQUE;

CREATE CONSTRAINT div_event_id IF NOT EXISTS
  FOR (de:DividendEvent) REQUIRE de.id IS UNIQUE;

CREATE INDEX holds_date IF NOT EXISTS FOR ()-[h:HOLDS]-() ON (h.date);
CREATE INDEX div_ex_date IF NOT EXISTS FOR (de:DividendEvent) ON (de.ex_date);
CREATE INDEX bucket_dist_date IF NOT EXISTS FOR ()-[hd:HOLDER_DIST]-() ON (hd.date);


// -------------------------------------------------------------
// 2. 節點 SCHEMA 說明（DDL 註解）
// -------------------------------------------------------------
//
// (:ETF { ticker, name, type, listed_date, issuer_name,
//         tracked_index_code, total_units, aum_twd,
//         mgmt_fee_pct, total_expense_ratio, is_active, status })
//   type ∈ {"被動國內","被動國外","主動國內","主動國外","槓反","期信","平衡","債券"}
//   is_active = true → 主動式 ETF
//
// (:Stock { ticker, name, market, sector,
//           esg_score, esg_score_source, esg_updated_at,
//           real_themes /* string[]，LLM 抽取的真實主題 */ })
//
// (:Issuer { name, name_en })
//
// (:Index { code, name, compiler, methodology_doc_id, last_review_date })
//
// (:Theme { name, type })
//   type ∈ {"market","esg","income","sector","factor"}
//
// (:Sector { code, name })
//
// (:InvestorBucket { name, range_min_shares, range_max_shares })
//
// (:Document { id, type, uri, page_count, last_updated, etf_ticker })
//   type ∈ {"prospectus","monthly","quarterly","annual",
//           "index_methodology","disclosure","press_release"}
//
// (:DividendEvent { id, ex_date, payment_date,
//                   amount_per_unit, currency,
//                   pct_股利所得, pct_資本利得, pct_收益平準金 })
//
// (:MonthlyView { id, month, view_text_uri, sentiment, key_topics })
//
// (:RegulatoryEvent { id, date, title, summary_uri,
//                     impact_type })


// -------------------------------------------------------------
// 3. RELATIONSHIPS
// -------------------------------------------------------------
//
// (ETF)-[:ISSUED_BY]->(Issuer)
// (ETF)-[:TRACKS]->(Index)
// (Index)-[:METHODOLOGY_DOC]->(Document)
// (ETF)-[:LABELED_AS {claimed:true}]->(Theme)
// (Stock)-[:BELONGS_TO_THEME {weight, llm_confidence, evidence}]->(Theme)
// (Stock)-[:IN_SECTOR]->(Sector)
// (ETF)-[:HOLDS {date, weight_pct, shares, market_value_twd}]->(Stock)
//   主邊：按日 snapshot；查詢一律 WHERE h.date = $asOf（h 為 HOLDS 關係變數）
// (ETF)-[:PAID]->(DividendEvent)
// (ETF)-[:HOLDER_DIST {date, persons, shares, share_pct}]->(InvestorBucket)
// (ETF)-[:DESCRIBED_IN]->(Document)
// (ETF)-[:PUBLISHED]->(MonthlyView)
// (RegulatoryEvent)-[:AFFECTS]->(ETF)


// =============================================================
// 4. SEED — 從 data/snapshot_2026-06-05/ 載入
// =============================================================
//
// 把 data/snapshot_2026-06-05/*.csv 複製或軟連結到 Neo4j 的
// import/ 資料夾後執行：

LOAD CSV WITH HEADERS FROM 'file:///etf_metadata.csv' AS row
MERGE (i:Issuer {name: row.issuer})
MERGE (e:ETF {ticker: row.ticker})
SET e.name = row.name,
    e.type = row.type,
    e.is_active = (row.is_active = 'true'),
    e.tracked_index_code = row.tracked_index,
    e.listed_date = date(row.listed_date),
    e.issuer_name = row.issuer
MERGE (e)-[:ISSUED_BY]->(i);

LOAD CSV WITH HEADERS FROM 'file:///holdings_2026-06-05.csv' AS row
MERGE (s:Stock {ticker: row.stock_ticker})
SET s.name = row.stock_name,
    s.sector = row.sector
WITH row, s
MATCH (e:ETF {ticker: row.etf_ticker})
MERGE (e)-[h:HOLDS {date: date(row.date)}]->(s)
SET h.weight_pct = toFloat(row.weight_pct);

LOAD CSV WITH HEADERS FROM 'file:///regulatory_events.csv' AS row
MERGE (r:RegulatoryEvent {id: row.id})
SET r.date = date(row.date),
    r.title = row.title,
    r.impact_type = row.impact_type,
    r.summary = row.summary,
    r.url = row.url;

// 法規 4/24 25% 新令影響「全部主動式 ETF」
MATCH (r:RegulatoryEvent {id:'fsc_2026_04_24_25pct'})
MATCH (e:ETF {is_active:true})
MERGE (r)-[:AFFECTS]->(e);

LOAD CSV WITH HEADERS FROM 'file:///dividends_2024-2025.csv' AS row
MERGE (d:DividendEvent {id: row.id})
SET d.ex_date = date(row.ex_date),
    d.payment_date = date(row.payment_date),
    d.amount_per_unit = toFloat(row.amount_per_unit),
    d.currency = row.currency,
    d.pct_股利所得 = toFloat(row.pct_股利所得),
    d.pct_資本利得 = toFloat(row.pct_資本利得),
    d.pct_收益平準金 = toFloat(row.pct_收益平準金)
WITH d, row
MATCH (e:ETF {ticker: row.etf_ticker})
MERGE (e)-[:PAID]->(d);


// =============================================================
// 5. HERO QUERIES — 對應 8 個殺手 query
// =============================================================

// -------------------------------------------------------------
// Q-Demo-C / Q2 — Hero：跨多檔組合穿透（台積電曝險）
// 預期輸出：tsmc_pct = 31.1（真實持股：0050 57.91% + 006208 57.94% + 00878 0% + 00992A 8.38%）
// -------------------------------------------------------------
WITH date('2026-06-05') AS asOf,
     [{ticker:'0050',   invest:100000},
      {ticker:'006208', invest:100000},
      {ticker:'00878',  invest:100000},
      {ticker:'00992A', invest:100000}] AS portfolio
WITH asOf, portfolio,
     reduce(t = 0.0, p IN portfolio | t + p.invest) AS total_invest
UNWIND portfolio AS p
MATCH (e:ETF {ticker: p.ticker})-[h:HOLDS {date: asOf}]->(s:Stock)
WHERE s.ticker <> '_OTHER'
WITH s, total_invest,
     sum(p.invest * h.weight_pct / 100.0) AS exposure_twd
RETURN s.ticker  AS ticker,
       s.name    AS name,
       s.sector  AS sector,
       round(exposure_twd)                                AS exposure_twd,
       round(exposure_twd / total_invest * 10000) / 100.0 AS exposure_pct
ORDER BY exposure_pct DESC
LIMIT 10;

// -------------------------------------------------------------
// 主動式 ETF 中對台積電持股排名（真實，主動組皆 ≤10%）
// 預期輸出：00981A 10.03% / 00982A 8.65% / 00992A 8.38% / 00400A 8.23% / 00984A 2.73%
// -------------------------------------------------------------
MATCH (e:ETF {is_active: true})-[h:HOLDS {date: date('2026-06-05')}]->(s:Stock {ticker: '2330'})
RETURN e.ticker         AS etf,
       e.name           AS name,
       e.issuer_name    AS issuer,
       round(h.weight_pct * 100) / 100.0 AS tsmc_weight_pct
ORDER BY tsmc_weight_pct DESC
LIMIT 5;

// -------------------------------------------------------------
// Q1 — 名實相符度（漂綠／掛羊頭檢測）
// -------------------------------------------------------------
MATCH (e:ETF {ticker: $etfTicker})-[:LABELED_AS]->(claimed:Theme)
MATCH (e)-[h:HOLDS {date: date('2026-06-05')}]->(s:Stock)
WHERE s.ticker <> '_OTHER'
OPTIONAL MATCH (s)-[bt:BELONGS_TO_THEME]->(claimed)
WITH claimed,
     sum(h.weight_pct * coalesce(bt.weight, 0) / 100.0) AS aligned_pct,
     sum(h.weight_pct)                                   AS total_weight
RETURN claimed.name                                AS claimed_theme,
       round(aligned_pct * 100) / 100.0            AS aligned_weight_pct,
       round(aligned_pct / total_weight * 10000)
         / 100.0                                   AS coherence_score
ORDER BY coherence_score ASC;  // 分數越低 = 名實越不相符

// -------------------------------------------------------------
// Q3 — 漂綠檢測：成分股加權 ESG vs 大盤平均
// -------------------------------------------------------------
MATCH (e:ETF {ticker: $etfTicker})-[h:HOLDS {date: date('2026-06-05')}]->(s:Stock)
WHERE s.esg_score IS NOT NULL AND s.ticker <> '_OTHER'
WITH e,
     sum(h.weight_pct * s.esg_score) / sum(h.weight_pct) AS weighted_esg
MATCH (mkt:Stock) WHERE mkt.esg_score IS NOT NULL AND mkt.ticker <> '_OTHER'
WITH e, weighted_esg, avg(mkt.esg_score) AS market_avg
RETURN e.ticker AS etf,
       round(weighted_esg * 100) / 100.0      AS etf_weighted_esg,
       round(market_avg   * 100) / 100.0      AS market_avg_esg,
       round((weighted_esg - market_avg) * 100) / 100.0 AS esg_premium;

// -------------------------------------------------------------
// Q4 — 配息政策：三檔比較收益平準金佔比
// -------------------------------------------------------------
UNWIND ['00919','00878','00940'] AS t
MATCH (e:ETF {ticker: t})-[:PAID]->(d:DividendEvent)
WHERE d.ex_date >= date('2024-01-01')
WITH e,
     sum(d.amount_per_unit * d.pct_股利所得)      AS sum_sd,
     sum(d.amount_per_unit * d.pct_資本利得)      AS sum_cap,
     sum(d.amount_per_unit * d.pct_收益平準金)    AS sum_lev,
     sum(d.amount_per_unit)                       AS sum_amt
RETURN e.ticker                                          AS etf,
       round(sum_sd  / sum_amt * 10000) / 100.0          AS pct_股利所得,
       round(sum_cap / sum_amt * 10000) / 100.0          AS pct_資本利得,
       round(sum_lev / sum_amt * 10000) / 100.0          AS pct_收益平準金
ORDER BY pct_收益平準金 DESC;

// -------------------------------------------------------------
// Q7 — 重複曝險警告：加買新 ETF 是分散還是雪上加霜？
// 範例：既有 0050+006208+00878 各 10 萬，候選加買 00919 10 萬
// -------------------------------------------------------------
WITH date('2026-06-05') AS asOf,
     [{ticker:'0050',   invest:100000},
      {ticker:'006208', invest:100000},
      {ticker:'00878',  invest:100000}] AS current_p,
     [{ticker:'00919',  invest:100000}] AS candidate_p

// (1) 既有組合：每個個股的曝險（排序）
UNWIND current_p AS p
MATCH (:ETF {ticker:p.ticker})-[h:HOLDS {date:asOf}]->(s:Stock)
WHERE s.ticker <> '_OTHER'
WITH asOf, current_p, candidate_p, s,
     sum(p.invest * h.weight_pct / 100.0) AS curr_exp
ORDER BY curr_exp DESC
WITH asOf, current_p, candidate_p,
     collect({stock: s.ticker, amt: curr_exp}) AS curr_sorted

// (2) current + candidate：每個個股的曝險（排序）
UNWIND (current_p + candidate_p) AS p2
MATCH (:ETF {ticker:p2.ticker})-[h2:HOLDS {date:asOf}]->(s2:Stock)
WHERE s2.ticker <> '_OTHER'
WITH curr_sorted, s2,
     sum(p2.invest * h2.weight_pct / 100.0) AS new_exp
ORDER BY new_exp DESC
WITH curr_sorted, collect({stock: s2.ticker, amt: new_exp}) AS new_sorted

// (3) 計算 Top10 集中度與 delta
WITH reduce(t = 0.0, x IN curr_sorted          | t + x.amt) AS curr_total,
     reduce(t = 0.0, x IN curr_sorted[..10]    | t + x.amt) AS curr_top10,
     reduce(t = 0.0, x IN new_sorted           | t + x.amt) AS new_total,
     reduce(t = 0.0, x IN new_sorted[..10]     | t + x.amt) AS new_top10
RETURN round(curr_top10 / curr_total * 10000) / 100.0 AS curr_top10_pct,
       round(new_top10  / new_total  * 10000) / 100.0 AS new_top10_pct,
       round((new_top10 / new_total - curr_top10 / curr_total) * 10000) / 100.0
         AS delta_concentration_pct;
//   delta > 0  ⇒ 加買後更集中（雪上加霜）
//   delta < 0  ⇒ 加買後更分散（分散有效）


// （已移除「25% 上限模擬」query — 該法規假設為過時時事，不再作為 demo 敘事）
