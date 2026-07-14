# ETF 透視鏡 PASSPORT

> 把冷冰冰的公開說明書，30 秒變成有溫度的曝險決策。
>
> 一個用 **Hybrid RAG（Graph + Vector）** 打造的台股 ETF 穿透分析助手：丟進你手上的幾檔 ETF，馬上看清你「真正」重押了哪幾檔個股。

**PASSPORT** = Penetration · Allocation · Sustainability · Strategy · Portfolio · Overlap · Risk · Tracker

---

## 🏆 關於這個競賽

這個專案是 **2026 精誠集團 AI 創新競賽**（主辦：**精誠資訊 SYSTEX**）的參賽作品，並獲得 **AI 駕馭獎**。

競賽在做什麼：主辦方提供企業級 AI 平台 **EAP（Enterprise AI Platform，`cloud.geminidata.com`）**，要求各隊在上面設計一套**結合 Graph RAG 與 Vector RAG 的混合式檢索應用**——自己找資料源、做資料清洗與溯源、設計知識圖譜 schema 與 system prompt（Robot Setting），最後做出一個能現場操作的 Demo，向評審展示「如何把公開資料轉化成有價值的決策」。評分涵蓋應用情境、技術深度、整合創新、介面設計與現場 Demo。

本作品選的題目是 **ETF 穿透分析**：台股 ETF 受益人已突破 1,458 萬，但多數散戶並不知道自己手上幾檔 ETF 穿透到個股後，其實高度重疊、重押在同一籃股票上。

---

## 💡 這是什麼

ETF 透視鏡 PASSPORT 接受一組「ETF + 投入金額」，把每檔 ETF **穿透到底層個股**，合併計算出整個組合對單一個股的**真實曝險**，並用自然語言回答「為什麼這麼集中」。

它解決的核心痛點：

> **你以為買了 4 檔 ETF 是分散，其實只是用 4 種包裝買了同一籃台積電。**

範例組合（各投入 10 萬，看似橫跨市值、高股息、主動式三種風格）：

| ETF | 投入 | 台積電權重 | 貢獻曝險 |
|---|---:|---:|---:|
| 0050 元大台灣50 | 100,000 | 57.91% | 57,910 |
| 006208 富邦台50 | 100,000 | 57.94% | 57,940 |
| 00992A 主動富邦台灣動能 | 100,000 | 8.38% | 8,380 |
| 00878 國泰永續高股息 | 100,000 | 0%（不持台積電） | 0 |
| **合計** | **400,000** | | **124,230 → 31.1%** |

四檔「看似分散」的 ETF，穿透後台積電一檔就佔了整個組合的 **31.1%**——因為 0050 與 006208 同追 FTSE TWSE Taiwan 50，光這兩檔就吃掉近 6 成台積電，而想用來稀釋的高股息 00878 根本一股台積電都沒有。

過去要回答這個問題，得自己翻 4 份公開說明書、約 400 頁，而且翻完也拿不到「加權後」的答案。現在用講的就可以：「我這組合台積電真實曝險多少？為什麼這麼集中？」30 秒拿到穿透流向圖、集中原因與引用來源。

---

## 🆚 既有工具做不到什麼

市面上的工具，穿透、漂綠檢測、配息語意，沒有一個能同時做：

| 工具 | 多檔穿透 | 自然語言 | 名實/漂綠 | 配息語意 | 中文 PDF | 引用回鏈 |
|---|---|---|---|---|---|---|
| Morningstar X-Ray | ✓（國際） | – | – | – | – | – |
| Bloomberg Terminal | ✓ | BBG GPT | – | – | – | – |
| FactSet · Refinitiv | ✓ | – | – | – | – | – |
| TEJ 台灣經濟新報 | – | – | – | – | – | – |
| MoneyDJ · CMoney | ≤2 檔 | – | – | – | – | – |
| TWSE e添富 · 集保 fundclear | ≤2 檔 | – | – | – | – | – |
| 券商 GPT（玉山小 i · 富邦 Money） | – | FAQ 式 | – | – | – | – |
| **本案 ETF 透視鏡** | **✓ 16 檔** | **✓** | **✓** | **✓** | **✓** | **✓** |

為什麼國際大廠不做台灣版？授權碎片化（12 家投信揭露格式各異）、市場規模對全球視角太邊緣、100+ 頁中文 PDF 的 OCR/NLP 成本不划算，加上「收益平準金」這類在地語意沒有現成模型。這個空隙正好是本案的切入點。

---

## 📸 實際畫面

![ETF 透視鏡 PASSPORT — 穿透分析畫面](docs/assets/demo-hero-penetration.png)

左側輸入持股組合，中間即時算出穿透結果與台積電 31.1% 曝險、穿透後前五大個股，右側「引用回鏈」標示每個數字來自 Graph、Vector 還是原始資料源——讓每個結論都可追溯、可被當場核對。

---

## ✨ 功能

同一套 Hybrid 後端，接出八個場景。前四個已在 Demo 完整展示，後四個是同一後端的延伸：

### 穿透曝險分析（Hybrid）

主功能。輸入「ETF + 投入金額」的組合，穿透到底層個股後合併計算真實曝險，並回答「為什麼這麼集中」。範例：4 檔組合的台積電真實曝險 **31.1%**，附穿透流向圖與三大集中原因。加碼前可先用「重複曝險警告」檢查：這筆加碼是分散，還是更集中。

### 漂綠雷達（Hybrid）

比對 ETF **名稱宣稱的主題**（公開說明書）與**成分股加權後的實際樣貌**（個股標註 × 權重彙總），算出名實溢價。範例：00878 名稱訴求 ESG/永續，成分股加權 ESG 73.9 卻低於市場基準 75.3，名實溢價 **−1.4**，是名實不符的訊號。（註：ESG 評分屬示意資料，見下方資料真實性說明。）

### 名實對齊檢測（Graph）

同一套機制用在主題型 ETF：檢查基金名稱與實際持股的對齊程度。範例：00881 標榜 5G，實際對齊度只有 **24.7%**——名為電動車或 5G 的 ETF，成分股可能三成是傳產。

### 看好產業選 ETF（Graph）

反向查詢：先講你看好的產業，再從 16 檔中找出對該產業曝險最高的 ETF。範例：「半導體」→ 0052 富邦科技，半導體曝險度 **79.4%**。

### 單檔透視報告（Graph）

單檔 ETF 的一鍵健檢：曝險結構、配息組成、名實對齊一次產出，可存檔、可下載。

### 配息政策比一比（Vector）

真的讀進收益分配公告，把配息來源拆開，特別標出「收益平準金」佔比。範例：00878 股利所得佔 31.36%、收益平準金佔 **5.71%**——平準金本質是「拿你的本金配給你」，混在配息率裡會高估真實殖利率。

### 法規影響快訊（Vector · 資料已入庫，介面開發中）

法規與公告的時效推送，標示哪些 ETF 受影響。

### 月報觀點對賭（Hybrid · 路線圖）

比對投信月報的展望說法與實際持股變化，抓出「策略講得漂亮、持股對不上」的落差。

---

## ⚙️ 運作原理

核心是一套 **Hybrid RAG** 架構，依問題類型路由到不同的檢索鏈：

```
使用者自然語言提問
        │
        ▼
  Query Router（在 Robot Setting 內）
        │
   ┌────┴───────────────┬─────────────────────┐
   ▼                    ▼                     ▼
數字 / 排序 / Top-N   為什麼 / 定義 / 差異     兩者都有（最常見）
   │                    │                     │
Graph RAG            Vector RAG            Hybrid：先取數再找佐證
（持股 HOLDS 邊）    （公開說明書/配息公告）   最後合成 + 引用回鏈
```

| | Graph RAG | Vector RAG |
|---|---|---|
| **負責** | 數字、權重、排名、穿透計算 | 語意、定義、為什麼、配息條款 |
| **資料** | 16 檔 ETF 真實成分股持股關係（`HOLDS` 邊，Neo4j v5 schema） | 公開說明書、指數編製規則、SITCA 收益分配公告 |

三種路徑各自對應的典型問題：

- 「台積電持股 Top 5」→ **Graph**（Cypher 純結構查詢）
- 「『收益平準金』是什麼？」→ **Vector**（embedding 純語意）
- 「4 檔組合台積電曝險多少？為什麼？」→ **Hybrid**（Graph 取數 + Vector 找佐證 → LLM 合成），這也是 Demo 的主秀

**最重要的設計原則：防幻覺。** 所有百分比與金額一律走確定性計算、**LLM 不准心算**；查無資料就回「尚無此資料」，絕不估算；每個數字都附引用回鏈到資料快照日期。

> 實作上踩到一個關鍵坑：EAP 平台自動產生的 Cypher 不可靠（會把 ticker 存成 float、無視指令重寫查詢並丟掉金額參數）。因此所有「數字型」答案改由自家後端 [`demo/penetrate.py`](demo/penetrate.py) 直接從快照 CSV 確定性計算，EAP 的 LLM 只負責質化敘述。這個「踩坑後的工程決策」本身就是把可靠性放在第一位的取捨。

完整四層架構（Use Case → API/前端 → Hybrid 語意知識網 → 資料源）見 [`research/architecture.md`](research/architecture.md)。

---

## 🗺️ 資料地圖：Graph 結構化 ╱ Vector 非結構化

每筆資料都標註來源、取得方式與清洗流程；AI 生成欄位必附 prompt（標 🤖 者）。

**Graph RAG · 結構化 8 源，708 條 HOLDS 邊：**

| # | 資料 | 來源 | 取得方式 |
|---|---|---|---|
| G1 | ETF 基本資料 | TWSE OpenAPI | OpenAPI |
| G2 | 每日持股權重 | etfinfo + 投信 | 爬蟲 |
| G3 | 配息事件 🤖 | TWSE + 公告 PDF | HTML + PDF |
| G4 | 受益人級距 | TDCC qryStock | 爬蟲 |
| G5 | ESG 評分 | TWSE OpenAPI | OpenAPI |
| G6 | 即時淨值 | mis.twse | HTTP 輪詢 |
| G7 | 指數編製規則 | 臺灣指數公司 | 手動 PDF |
| G8 | 個股主題標註 🤖 | MOPS 年報 | API + LLM |

**Vector RAG · 非結構化 6 源，約 10K chunks：**

| # | 資料 | 量級 | 來源 |
|---|---|---|---|
| V1 | 公開說明書 | ~1,800 頁 | MOPS |
| V2 | 月報 🤖 | ~144 份 | 投信網站 |
| V3 | 季 / 年報 | ~60 份 | 投信網站 |
| V4 | 指數編製規則 | ~8 份 | 指數公司 |
| V5 | 配息公告 🤖 | 144 筆 | TWSE + MOPS |
| V6 | 法規新聞 | ~30 篇 | 公告 + 媒體 |

---

## 🕸️ Knowledge Graph 模型

Neo4j v5 schema，實體包含 ETF、Stock、Theme、Index、Issuer、DividendEvent、受益人級距（HOLDER_DIST）與法規事件（RegulatoryEvent）。已驗證匯入 EAP Data Explorer：**259 個資料節點、844 條資料關連**，真實成分股持股邊（HOLDS）可於 Data Explorer 直查。

```
Theme(real) ┄┄相符分數 0–1┄┄ Theme(claimed)        Issuer
     │        （漂綠檢測）          │                  │
BELONGS_TO_THEME              LABELED_AS          ISSUED_BY
     │                             │                  │
   Stock ──HOLDS {date,w}──▶     ETF   ──TRACKS──▶  Index
                                   │
              ┌────────────────────┼────────────────────┐
             PAID            HAS_HOLDERS             AFFECTS
              │                    │                    │
       DividendEvent         HOLDER_DIST         RegulatoryEvent
      （股利/資本/平準金）    （受益人 15 級距）    （法規影響快訊）
```

其中 `Theme(claimed)`（公開說明書宣稱）與 `Theme(real)`（個股 LLM 標註加權彙總）的相符分數，就是漂綠檢測的機制。完整 schema 見 [`research/graph_schema.cypher`](research/graph_schema.cypher)。

---

## 🧰 技術棧

- **後端**：Python · FastAPI · httpx（反向代理 EAP Chat API、隱藏 token、解決 CORS）
- **穿透計算引擎**：純 Python，從快照 CSV 確定性計算，可離線、可重算、附 self-test
- **前端**：原生 JavaScript · Tailwind · `marked`（Markdown）· `mermaid`（穿透流向圖）· 逐 token 顯現的串流效果
- **知識庫**：Graph（Neo4j v5 schema）+ Vector（公開說明書/公告），透過 EAP 平台匯入
- **資料**：16 檔 ETF 真實成分股快照（as-of 2026-06-05）+ 完整資料溯源

---

## 🚀 本地執行

```bash
cd demo
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
bash fetch_vendor.sh          # 下載前端 JS 依賴到 vendor/（一次性）
python3 server.py             # 開 http://localhost:8000
```

預設為**全程本地模式**：數字題走本地確定性計算、質化題走預錄回應，**完全不依賴外部網路**即可操作。若要改接真實 EAP 平台，複製 `demo/.env.example` 為 `demo/.env` 並填入 token 後取消前端「Mock」勾選。詳見 [`demo/README.md`](demo/README.md)。

---

## 📂 專案結構

```
.
├── demo/                # 穿透分析 Web App（FastAPI 代理 + 原生 JS 前端 + 本地計算引擎）
├── data/                # 16 檔 ETF 真實成分股快照 + 資料溯源與 AI 生成資料的 prompt
│   └── snapshot_2026-06-05/
├── research/            # 設計文件
│   ├── architecture.md      # 四層技術架構 + Hybrid RAG 路由
│   ├── graph_schema.cypher  # 知識圖譜 schema（Neo4j v5）
│   ├── prompt_design.md     # 三層 Prompt / Robot Setting 設計
│   └── etf_passport_research.md
├── eap_import_bundle/   # Hybrid RAG 知識庫匯入（Graph schema + Vector PDF + Robot Setting）
└── docs/                # 圖片素材與設計 spec
```

---

## 🔎 資料來源與真實性

所有 hero 數字（如 31.1% 穿透曝險）都能從 [`data/snapshot_2026-06-05/`](data/snapshot_2026-06-05/) 的 CSV 重算回來，避免「簡報講的」與「程式算的」不一致。

- **持股權重**：真實成分股，來源 etfinfo.tw，經元大投信官網交叉驗證，as-of 2026-06-05
- **配息來源占比**：真實，來自 SITCA 收益分配公告
- **受益人結構 / ESG / 主題標籤**：部分為 AI 生成示意資料，覆蓋有限，對應 prompt 完整記錄於 [`data/snapshot_2026-06-05/AI_GENERATED_PROMPTS.md`](data/snapshot_2026-06-05/AI_GENERATED_PROMPTS.md)

詳細真假分層與計算稽核見 [`data/snapshot_2026-06-05/README.md`](data/snapshot_2026-06-05/README.md)。

---

## ⚠️ 免責聲明

本專案為競賽與技術展示用途，所有內容**不構成任何投資建議**。資料快照僅反映特定日期、且包含部分示意資料，請勿用於實際投資決策。
