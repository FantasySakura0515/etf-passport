# 資料快照（持股 as-of 2026-06-05）

**持股已改為真實成分股資料**（來源 etfinfo.tw，經元大投信官網直抓交叉驗證；每檔以 `_OTHER` 列補足至 100%）。ESG／主題／受益人等輔助層仍為示意值。

## 為什麼存在這個資料夾

提案的 hero 數字（Q-Demo-C 的「31.1% 台積電穿透曝險」）必須**從這個資料夾的 CSV 算得出來**。否則簡報講的、`penetrate.py` 算的、Mock 模式回的會三邊不一致 — 評審一問就破。

`research/graph_schema.cypher` 的 hero query 直接 LOAD CSV 讀這裡的檔案；`demo/mock_responses.js` 的數字也對齊這裡。

## 資料層級

| 來源 | 真假 | 處理方式 |
|---|---|---|
| ETF 基本資料（代號、名稱、發行商、追蹤指數、上市日期） | 多為真實 | 從 TWSE OpenAPI t187ap47_L 取，部分主動式 ETF 名稱為示意 |
| 持股權重（完整成分股） | **真實** | etfinfo.tw 全成分股，as-of 2026-06-05；以元大投信官網 `__NUXT__` 直抓交叉驗證（0050 一字不差） |
| 配息來源占比 | **真實** | SITCA 收益分配公告（`eap_import_bundle/vector_pdfs/`）；如 00878 收益平準金 5.71% |
| 受益人結構 | **AI 生成示意** | `holder_distribution.csv`；prompt 見 `AI_GENERATED_PROMPTS.md`；上線從 TDCC 股權分散表取 |
| ESG 評分 | **AI 生成示意（覆蓋有限）** | `stock_esg.csv`；僅蓋部分個股，真實持股換入後可評估權重偏低；上線從 TWSE t187ap46 取 |
| 主題標籤（名/實） | **AI 生成示意（覆蓋有限）** | `etf_claimed_themes.csv`（名）＋`stock_themes.csv`（實）；prompt 見 `AI_GENERATED_PROMPTS.md` |

## 16 檔 ETF 範圍

| 類型 | ETF 代號 | 用途 |
|---|---|---|
| 12 檔散戶熱門 | 0050, 006208, 0056, 00878, 00919, 00940, 00929, 00713, 0052, 00881, 00922, 00992A | Q-Demo-C 主秀 + 其他 hero query |
| +4 檔主動式對照 | 00400A, 00982A, 00984A, 00981A | Q-Demo-A 主動式 TSMC 前 5（00992A 也算入） |
| **合計 16 檔（00992A 重疊）** | | |

> 有 5 檔主動式 ETF（含 00992A）對 Q-Demo-A「主動式中台積電持股前 5」是必要的，否則該題會破題。

## 檔案

| 檔案 | 內容 | 行數 |
|---|---|---|
| `etf_metadata.csv` | 16 檔基本資料 | 17（含 header） |
| `holdings_2026-06-05.csv` | 完整成分股權重（真實，as-of 2026-06-05） | 725（16 檔 724 列 + header） |
| `personas.json` | 三 Persona 的示範組合 | — |
| `regulatory_events.csv` | 法規事件（dormant，demo 不再使用） | 2 |
| `dividends_2024-2025.csv` | 配息事件範例 | 25 |
| `mock_citations.json` | hero query 的引用回鏈 | — |

## Hero 數字的計算稽核（真實持股 2026-06-05）

### Q-Demo-C：四檔組合台積電穿透曝險 = 31.1%

組合：0050 + 006208 + 00878 + 00992A 各 100,000 元 = 400,000 元

| ETF | 投入 | TSMC 權重 | TSMC 曝險 |
|---|---:|---:|---:|
| 0050 | 100,000 | 57.91% | 57,910 |
| 006208 | 100,000 | 57.94% | 57,940 |
| 00878 | 100,000 | 0%（高股息不持台積電） | 0 |
| 00992A | 100,000 | 8.38% | 8,380 |
| **合計** | **400,000** | | **124,230** |

**TSMC 曝險率：124,230 / 400,000 = 31.1%**（可由 `demo/penetrate.py` self-test 重現）

> 關鍵洞察：0050 與 006208 同追 FTSE TWSE Taiwan 50，兩檔就吃掉近 6 成台積電；加的高股息 00878 對台積電 0 稀釋 → 「以為分散其實重押」。

### 主動式 ETF 台積電持股（真實，皆 ≤10%）

| ETF | TSMC 權重 |
|---|---:|
| 00981A 主動群益優選成長 | 10.03% |
| 00982A 主動野村台灣優勢 | 8.65% |
| 00992A 主動富邦台灣動能 | 8.38% |
| 00400A 主動國泰動能高息 | 8.23% |
| 00984A 主動凱基台股增長 | 2.73% |

> 真正高度集中台積電的是**被動市值型**：0052 富邦科技 64%、006208 57.94%、0050 57.91%、00922 40%、00881 38%。

## 在 Neo4j 中載入

```cypher
LOAD CSV WITH HEADERS FROM 'file:///etf_metadata.csv' AS row
MERGE (i:Issuer {name: row.issuer})
MERGE (e:ETF {ticker: row.ticker})
SET e.name = row.name,
    e.type = row.type,
    e.is_active = (row.is_active = 'true'),
    e.tracked_index_code = row.tracked_index,
    e.listed_date = date(row.listed_date)
MERGE (e)-[:ISSUED_BY]->(i);

LOAD CSV WITH HEADERS FROM 'file:///holdings_2026-06-05.csv' AS row
MERGE (s:Stock {ticker: row.stock_ticker})
SET s.name = row.stock_name,
    s.sector = row.sector
WITH row, s
MATCH (e:ETF {ticker: row.etf_ticker})
MERGE (e)-[h:HOLDS {date: date(row.date)}]->(s)
SET h.weight_pct = toFloat(row.weight_pct);
```

## 持股已真實化（2026-06-05 完成）

持股權重已從 etfinfo.tw 抓取全 16 檔完整成分股並覆蓋本檔，流程見 memory `reference_real_data_sources`。
數字變動已同步傳播到 `penetrate.py`、`mock_responses.js`、`demo_script.md`、`prompt_design.md`、`graph_schema.cypher`。

**仍待補的示意層（覆蓋有限）：**

1. `stock_esg.csv`：真實持股換入後 ESG 可評估權重偏低（00878 約 38.6%）→ Q-E 只能當「誠實揭露覆蓋有限」展示；上線從 TWSE t187ap46 取
2. `stock_themes.csv` / `etf_claimed_themes.csv`：主題對齊覆蓋仍有限（00881 目前 5G 對齊 24.7%）→ Q-D 可展示方法，但不可包裝成正式評等
3. 改任何數字時，仍須同步 `mock_responses.js`、`demo_script.md`、`prompt_design.md`、`graph_schema.cypher`、`README.md`
