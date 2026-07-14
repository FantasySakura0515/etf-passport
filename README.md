# ETF 透視鏡 PASSPORT

台股 ETF 穿透分析助手。輸入你手上的幾檔 ETF 和金額，它把每檔穿透到底層個股、合併計算整個組合對單一個股的真實曝險，並用自然語言回答「為什麼這麼集中」。所有數字來自確定性計算並附引用來源，LLM 只負責解釋。

這是 **2026 精誠集團 AI 創新競賽**（主辦：精誠資訊 SYSTEX）的參賽作品，獲 **AI 駕馭獎**。競賽要求各隊在主辦方的企業 AI 平台 EAP（`cloud.geminidata.com`）上打造結合 Graph RAG 與 Vector RAG 的混合式檢索應用，從找資料、清洗溯源、設計知識圖譜 schema 與 system prompt，到做出能現場操作的 Demo。

---

## 它解決什麼問題

> 你以為買了 4 檔 ETF 是分散，其實只是用 4 種包裝買了同一籃台積電。

範例組合（各投入 10 萬，橫跨市值、高股息、主動式三種風格）：

| ETF | 投入 | 台積電權重 | 貢獻曝險 |
|---|---:|---:|---:|
| 0050 元大台灣50 | 100,000 | 57.91% | 57,910 |
| 006208 富邦台50 | 100,000 | 57.94% | 57,940 |
| 00992A 主動富邦台灣動能 | 100,000 | 8.38% | 8,380 |
| 00878 國泰永續高股息 | 100,000 | 0%（不持台積電） | 0 |
| **合計** | **400,000** | | **124,230 → 31.1%** |

四檔「看似分散」的 ETF，穿透後台積電一檔就佔組合 **31.1%**：0050 與 006208 同追 FTSE TWSE Taiwan 50，光這兩檔就吃掉近 6 成台積電，而想用來稀釋的 00878 一股台積電都沒有。要自己查，得翻 4 份共約 400 頁的公開說明書，而且翻完也拿不到加權後的答案。

這個 31.1% 不是簡報上編的數字：可以從 [`data/snapshot_2026-06-05/holdings_2026-06-05.csv`](data/snapshot_2026-06-05/holdings_2026-06-05.csv)（16 檔、724 列真實成分股）重算出來，[`demo/penetrate.py`](demo/penetrate.py) 的 self-test 就在驗證這件事。

![ETF 透視鏡 PASSPORT — 穿透分析畫面](docs/assets/demo-hero-penetration.png)

---

## 功能

Demo 支援六種題型加報告產出，每種背後走的檢索路徑不同（詳見下節）：

| 功能 | 路徑 | 實例 |
|---|---|---|
| 跨檔穿透曝險 | Hybrid | 4 檔組合台積電真實曝險 31.1%，附 Mermaid 穿透流向圖與集中原因 |
| 持股排名查詢 | Graph | 主動式 ETF 台積電持股前 5（最高 00981A 10.03%，全部 ≤10%——真正重押台積電的是被動市值型） |
| 配息語意拆解 | Vector | 讀 SITCA 收益分配公告，拆出 00878 收益平準金佔配息 5.71%。平準金本質是返還本金，混在配息率裡會高估殖利率 |
| 名實對齊檢測 | Graph | 00881 標榜 5G，成分股加權後實際對齊度 24.7% |
| 漂綠檢測 | Hybrid | 00878 名稱訴求 ESG/永續，成分股加權 ESG 低於市場基準（名實溢價 −1.4） |
| 看好產業選 ETF | Graph | 反向查詢：「半導體」→ 0052 富邦科技，半導體曝險 79.4% |
| 報告產出 | 本地計算 | 一鍵「組合健檢報告」/「單檔透視報告」，可下載 self-contained HTML、列印成 PDF |

注意：名實對齊與漂綠檢測展示的是**方法**——主題標籤與 ESG 評分屬 AI 生成示意資料、覆蓋有限（見下方「資料」節），數字不能當正式評等用。

---

## 運作方式

### Hybrid RAG：數字走 Graph，語意走 Vector

問題進來先經 Query Router（寫在 EAP 的 system prompt「Robot Setting」裡）分流：

```
含時間 / 排序 / Top-N     → Graph RAG（Cypher 查持股 HOLDS 邊）
含為什麼 / 定義 / 差異    → Vector RAG（公開說明書、配息公告 embedding）
兩者都有（最常見）        → Hybrid：Graph 取數 → Vector 找佐證 → LLM 合成
```

Graph 端是 Neo4j v5 schema：ETF、Stock、Index、Issuer、Theme、DividendEvent 等節點，主邊是 `HOLDS {date, weight_pct}`（16 檔真實成分股）；`Theme(claimed)`（說明書宣稱）對 `Theme(real)`（個股標註加權）的落差就是漂綠檢測的機制。完整 DDL 在 [`research/graph_schema.cypher`](research/graph_schema.cypher)。Vector 端是配息公告與說明書 PDF（[`eap_import_bundle/vector_pdfs/`](eap_import_bundle/vector_pdfs/)），經 EAP 平台匯入。

### 防幻覺：LLM 不准算數字

所有百分比與金額一律走確定性計算，查無資料就回「快照無此資料」，每個數字附引用回鏈到資料快照日期。

這條原則有個實戰背景：EAP 平台自動產生的 Cypher 不可靠——會把 ticker 存成 float、無視指令重寫查詢並丟掉金額參數。因此所有數字型答案改由 [`demo/penetrate.py`](demo/penetrate.py) 直接從快照 CSV 計算（可離線、可重算、附 self-test），EAP 的 LLM 只負責質化敘述。

### Demo App

```
Browser ──→ FastAPI proxy（demo/server.py）──→ EAP Chat API
   ↑              │
   └── 靜態檔案 ──┘
```

前端是原生 JavaScript + Tailwind，含逐 token 串流顯示、Markdown/Mermaid 渲染、引用回鏈側欄。proxy 負責轉發 EAP API、把 token 留在 server 端、解決 CORS。

預設跑**全程本地模式**：數字題走本地計算、質化題走預錄回應（`mock_responses.js`），完全不依賴外部網路——這是為了決賽現場零開天窗風險設計的三重保險（本地計算失敗自動退預錄）。

完整四層架構見 [`research/architecture.md`](research/architecture.md)。

---

## 資料

快照日 2026-06-05，涵蓋 16 檔 ETF（0050、006208、0056、00878、00919、00940、00929、00713、0052、00881、00922，加上 00992A、00400A、00982A、00984A、00981A 五檔主動式）。哪些是真的、哪些是示意，分層如下：

| 資料 | 真假 | 來源 |
|---|---|---|
| 持股權重（724 列完整成分股） | **真實** | etfinfo.tw，經元大投信官網直抓交叉驗證（0050 一字不差） |
| 配息來源占比（含平準金） | **真實** | SITCA 收益分配公告 PDF |
| ETF 基本資料 | 多為真實 | TWSE OpenAPI |
| ESG 評分、主題標籤、受益人結構 | **AI 生成示意，覆蓋有限** | 生成 prompt 全文記錄在 [`AI_GENERATED_PROMPTS.md`](data/snapshot_2026-06-05/AI_GENERATED_PROMPTS.md) |

詳細分層與 31.1% 的計算稽核見 [`data/snapshot_2026-06-05/README.md`](data/snapshot_2026-06-05/README.md)。

---

## 本地執行

```bash
cd demo
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
bash fetch_vendor.sh          # 下載前端 JS 依賴到 vendor/（一次性）
python3 server.py             # 開 http://localhost:8000
```

預設本地模式不需要任何帳號或網路即可操作。若要接真實 EAP 平台：複製 `demo/.env.example` 為 `demo/.env` 填入 token，並取消前端「Mock」勾選。詳見 [`demo/README.md`](demo/README.md)。

---

## 專案結構

```
.
├── demo/                # Web App：FastAPI proxy + 原生 JS 前端 + 本地穿透計算引擎（penetrate.py）
├── data/
│   └── snapshot_2026-06-05/   # 16 檔真實成分股快照 + 資料真假分層 + AI 生成資料的 prompt
├── research/            # 設計文件
│   ├── architecture.md      # 四層技術架構 + Hybrid RAG 路由
│   ├── graph_schema.cypher  # 知識圖譜 schema（Neo4j v5）
│   └── prompt_design.md     # Robot Setting（system prompt）設計
├── eap_import_bundle/   # 匯入 EAP 的知識庫：Graph 匯入腳本 + Vector PDF + Robot Setting 全文
└── docs/                # 圖片素材與設計 spec
```

---

## 免責聲明

本專案為競賽與技術展示用途，所有內容不構成任何投資建議。資料快照僅反映特定日期、且包含部分示意資料，請勿用於實際投資決策。
