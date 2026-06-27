# ETF 透視鏡 PASSPORT — 深度研究報告

研究日期：2026/05/06。所有 URL 已實際呼叫驗證；標「需驗證」者代表頁面存在但需人工再確認資料新鮮度。

---

## 1. 台灣 ETF 資料生態盤點（已驗證）

### 1.1 集保結算所 TDCC — 受益人 / 規模

**入口**
- 開放資料總目錄：https://www.tdcc.com.tw/portal/zh/stats/openData
- TDCC OpenAPI Swagger：https://openapi.tdcc.com.tw/swagger-ui/index.html
- 股權分散查詢頁：https://www.tdcc.com.tw/portal/zh/smWeb/qryStock
- ETF 觀測站：https://tdcc-t.fundclear.com.tw/etf/product
- 政府資料平臺鏡像：https://data.gov.tw/dataset/11452

**已實測 endpoint**

| ID | 名稱 | URL | 頻率 | 狀態 |
|---|---|---|---|---|
| 1-1 | 證券基本資料（含 ETF） | `https://opendata.tdcc.com.tw/getOD.ashx?id=1-1` | 每日 | 14.5 MB CSV，可用 |
| 2-25 | 上市保管有價證券週餘額表 | `https://opendata.tdcc.com.tw/getOD.ashx?id=2-25` | 每週 | 1.95 MB CSV，可用 |
| 2-41 | **集中保管 ETF 月分析表** | `https://opendata.tdcc.com.tw/getOD.ashx?id=2-41` | 每月 | **目前回空 — 須備援爬蟲** |
| 2-42 | 集中保管開放式受益憑證月分析表 | `https://opendata.tdcc.com.tw/getOD.ashx?id=2-42` | 每月 | 同上需驗證 |
| 3-29 | 境外基金總覽-ETF | `https://opendata.tdcc.com.tw/getOD.ashx?id=3-29` | 每日 | 目前 1 列空資料 |

**2-41 欄位**：`資料年月, 證券代號, 證券名稱, 本月底保管數, 前月底保管數, 增減數額, 增減百分比, 發行單位數, 集保戶數`

**Fallback**：股權分散表（每週）有 15 個持股張數級距 × 各自人數/股數/比例 — Graph 中 `(InvestorBucket)-[HOLDS]->(ETF)` 的關鍵原料，能算「散戶 vs 大戶誰在買」。

### 1.2 TWSE OpenAPI

- Swagger：https://openapi.twse.com.tw/
- Spec：https://openapi.twse.com.tw/v1/swagger.json

**ETF 相關 endpoint（極少，重要發現）**

| Path | 用途 |
|---|---|
| `/v1/opendata/t187ap47_L` | 基金基本資料彙總表（256 檔基金，含全部上市 ETF）|
| `/v1/ETFReport/ETFRank` | 定期定額交易戶數月排行 |

**256 檔分類**：國外成分 ETF 92 檔、國內成分 67、槓反 51、國內主動式股票 15、期信 8、國外主動式股票 6、國外主動債 3、平衡 2 等。

**樣本（00400A 主動國泰動能高息）**：
```json
{"基金代號":"00400A","基金簡稱":"主動國泰動能高息",
 "基金類型":"國內成分證券主動式交易所交易基金(股票)",
 "成立日期":"1150330","上市日期":"1150409",
 "基金經理人":"梁恩溢","發行單位數":"1455140000"}
```

**TWSE 沒有的**：ETF 持股、淨值、折溢價、配息公告 — 這些都得從其他來源拿：
- iNAV 即時：https://mis.twse.com.tw/stock/data/all_etf.txt（每 15 秒；欄位 a=代號、c=淨值、e=現價、g=漲跌幅）
- 配息查詢頁：https://www.twse.com.tw/zh/products/securities/etf/products/div.html（HTML 表單，須爬蟲）
- 配息新制：https://www.twse.com.tw/market_insights/zh/detail/ff8080818bf08529018bf6c5d9550014（2023/11/1 起）
- ETF 商品總覽：https://www.twse.com.tw/zh/ETF/etfDiv 與 https://www.twse.com.tw/zh/ETF/domestic
- e添富散戶：https://www.twse.com.tw/zh/ETFortune/index
- e添富機構（配息日曆）：https://www.twse.com.tw/zh/ETFortune-institute/dividendCalendar
- 個別 ETF 詳情：`https://www.twse.com.tw/zh/ETFortune-institute/etfInfo/{代號}`
- iNAV 介接格式 PDF：https://dsp.twse.com.tw/public/static/downloads/tradingDepartment/ETF%20申贖資訊及即時淨值揭露專區介接格式說明_20250109142554.pdf

### 1.3 TPEx OpenAPI

- Spec：https://www.tpex.org.tw/openapi/swagger.json（225 paths，**無 ETF tag**）
- 對追蹤櫃買指數的 ETF 有用：`/tpex_index_consti`、`/tpex50_constituents`、`/tphd_constituents`（高殖利率）、`/tpci_constituents`（薪酬）、`/tpcgi_constituents`（公司治理）

### 1.4 SITCA 投信投顧公會

入口：https://www.sitca.org.tw/

**ETF 專區（無公開 API，須爬蟲）**：
- 主頁：https://www.sitca.org.tw/ROC/SITCA_ETF/index.html
- 產業概況：https://www.sitca.org.tw/ROC/SITCA_ETF/etf_industry_overview1.aspx
- ETF 總覽：https://www.sitca.org.tw/ROC/SITCA_ETF/etf-section-overview.html
- **ETF 明細**（每日淨值/規模/市佔/單位淨值/受益權單位數）：https://www.sitca.org.tw/ROC/SITCA_ETF/etf-statement.html
- 基金統計：https://www.sitca.org.tw/ROC/Industry/IN2201.aspx?pid=IN2221_01

### 1.5 各發行商 ETF 專區（每家結構不同）

| 發行商 | ETF 區 | PCF 申購買回 | 公開說明書 / 月報 |
|---|---|---|---|
| 元大 | https://www.yuantaetfs.com/ | `/tradeInfo/pcf/{ETF}` 每日 Excel | `/product/detail/{ETF}/download` |
| 國泰 | https://www.cathaysite.com.tw/ETF/ | 同站 | `/ETF/detail/ECN?tab=etf3` |
| 富邦 | https://websys.fsit.com.tw/FubonETF/ | `/Trade/Pcf.aspx` | 同站 |
| 群益 | http://etf.skit.com.tw/ | `/Home/Pcf` | 同站 |
| 永豐 | https://sitc.sinopac.com/SinopacEtfs/Etfs/ | `/Pcf` | 同站 |
| 兆豐 | https://www.megafunds.com.tw/MEGA/etf/ | `/trade_pcf.aspx` | 例：00692 公開說明書 https://www.megafunds.com.tw/MEGA/download/c_fund_download_vg/238_2.pdf（171 頁）|
| 復華 | https://www.fhtrust.com.tw/ETF/ | `/etf_data_value` 即時 iNAV | — |
| 野村 | https://www.nomurafunds.com.tw/ETFWEB/inav | iNAV | — |
| 凱基 | https://etf.masterlink.com.tw/ | `/Ranking2.html` | — |
| 中信 | https://www.ctbcinvestments.com/ | — | act 子站 PDF |
| 統一 | https://www.ezmoney.com.tw/ETF/Transaction/Estimate | — | — |

**PCF 注意**：是「申購單位」對應的籃子，不是基金總持股；多數股票 ETF 兩者比例≈，但**債券 / 黃金期貨 ETF 不一定**。完整持股看月報或基金網頁的「持股權重」（多數每日揭露）。

### 1.6 MOPS 公開資訊觀測站

- 基金公開說明書：https://mops.twse.com.tw/mops/web/t57sb01_q7（表單查詢）
- ETF 公開說明書頁數量級實測：00692 = **171 頁 / 2.4 MB**，章節含基金概況、投資策略、風險揭露、費用結構、配息政策（含收益平準金）、追蹤誤差、申購買回流程。

### 1.7 第三方資料源

| 來源 | URL | 商用性 |
|---|---|---|
| MoneyDJ ETF | https://www.moneydj.com/etf/x/basic/basic0007.xdjhtm?etfid=0050.tw | 免費可爬 |
| MoneyDJ 受益人排行 | https://www.moneydj.com/etf/x/rank/rank0016.xdjhtm | 免費 |
| CMoney 重疊度 | https://www.cmoney.tw/etf/tw/overlap/ | 免費 |
| 玩股網受益人排行 | https://www.wantgoo.com/stock/etf/ranking/shareholders | 免費 |
| 玩股網成分股 | https://www.wantgoo.com/stock/etf/{代號}/constituent | 免費 |
| 口袋證券 | https://www.pocket.tw/etf/tw/{代號}/ | 免費 |
| MacroMicro Screener | https://en.macromicro.me/etf/tw/screener | 部分付費 |
| FinMind | https://finmind.github.io/ | 免費 300 req/hr，**ETF 持股不在主資料集** |
| TEJ | https://www.tejwin.com/ | 付費 |
| 集保 fundclear | https://www.fundclear.com.tw/etf | 免費 |

### 1.8 指數編製規則

- **臺灣指數公司 TIP**（最大供應商）：https://taiwanindex.com.tw/
- 編製規則下載：https://taiwanindex.com.tw/en/downloads/compilation_rule
- 樣本 00919 對應「臺灣精選高息指數」：https://taiwanindex.com.tw/en/indexes/IX0170 — 年度 5 月與 12 月審查、2 月與 8 月再平衡、依股息殖利率降序選 40 檔、按因子加權
- 對應 ETF（需驗證最新版）：00919（精選高息）、00940（價值高息）、00713（高息低波）、00922（領袖 50）、00929（科技優息）
- FTSE TWSE 50：0050 / 006208 共追
- FTSE 高股息：0056
- MSCI ESG 永續高股息精選 30：00878
- 櫃買指數系列：https://www.tpex.org.tw/zh-tw/indices/stock-index/serial_etf_etn.html

---

## 2. 揭露規則總表

| 揭露項目 | 主動式 ETF | 被動國內 | 被動國外 |
|---|---|---|---|
| **PCF（申購籃子）** | 每日 | 每日 | 每日 |
| **持股權重明細** | **每日全持股** | **每日**（多數） | 每日（部分前一日） |
| **iNAV** | 每 15 秒 | 每 15 秒 | 每 15 秒 |
| **折溢價** | 即時 | 即時 | 即時 |
| **月報** | 每月 | 每月 | 每月 |
| **季報** | 次月底前 | 同 | 同 |
| **配息公告** | 除息日前；2023/11/1 起 mops 統一申報 | 同 | 同 |
| **公開說明書** | 重大事項變更 / 年度更新 | 同 | 同 |
| **股權分散（受益人）** | 每週 TDCC | 每週 | 每週 |
| **集保月分析** | 每月 | 每月 | 每月 |

**法規大事 2026/04/24**：金管會放寬投信基金 / 主動式 ETF 投資單一公司股票上限自 10% → 25%（「台積電條款」）
- https://newtalk.tw/news/view/2026-04-24/1031531
- https://tw.stock.yahoo.com/news/金管會放寬國內股票型基金-主動式etf投資單一-公司股票上限至25-003000585.html

---

## 3. 競品盤點

### 3.1 12 列差異化矩陣（國際 + 國內 × 法人 + 散戶 × LLM 助手）

| 工具（類型 / 受眾 / 收費） | 多檔穿透 | 自然語言 | 名實/漂綠 | 配息語意 | 中文 PDF 引用回鏈 |
|---|:-:|:-:|:-:|:-:|:-:|
| Morningstar Portfolio X-Ray（國際 / 散戶 / 部分付費） | ✓ ~10 檔（國際） | × | × | × | × |
| justETF / ETF.com Screener（國際 / 散戶 / 免費） | × | × | × | × | × |
| Bloomberg Terminal（國際 / 法人 / 付費 NTD 70 萬+/年） | ✓ | BloombergGPT | × | × | × |
| FactSet / Refinitiv（國際 / 法人 / 付費） | ✓ | × | × | × | × |
| TEJ 台灣經濟新報（國內 / 法人 / 付費） | × | × | × | × | × |
| MoneyDJ ETF（國內 / 散戶 / 免費） | × | × | × | × | × |
| CMoney 重疊檢查（國內 / 散戶 / 免費） | 2 檔 | × | × | × | × |
| TWSE e添富 + 集保 fundclear（國內 / 官方） | ≤2 檔 | × | × | × | × |
| MacroMicro 財經 M 平方（國內 / 部分付費） | 2 檔 | × | × | × | × |
| 券商 GPT（玉山小 i / 富邦 Money / 新光 AI） | × | FAQ 式 | × | × | × |
| LINE bot（嗨投資 / 股海撈金） | × | FAQ 式 | × | × | × |
| ★ **ETF 透視鏡 PASSPORT**（我們 / 散戶 / 免費） | **✓ N 檔** | **✓** | **✓** | **✓** | **✓** |

**結論**：12 個玩家的天花板都是「兩檔重疊 + 篩選器 + FAQ 式 LLM」。**沒有人同時做「跨多檔合併穿透 + 自然語言 + 名實/漂綠 + 配息語意 + 中文 PDF 引用回鏈」**。

### 3.2 為什麼 Morningstar / TEJ 不做台灣版？

評審 80% 會問這題。**答案是這 4 個結構性原因，反而是我們的護城河**：

1. **資料授權碎片化**：12 家投信揭露格式各異（PCF Excel、PDF 月報、HTML 表格），國際工具沒人有時間 normalize 台灣的 ETF 持股資料
2. **市場規模對全球視角邊緣**：台股 ETF 受益人 1,458 萬，對 Morningstar 是亞洲一隅；對 Bloomberg 不值得單獨做 UI
3. **中文 PDF 處理成本高**：公開說明書 100+ 頁中文，OCR / NLP / chunking / 章節 metadata 對國際工具是技術 + 成本雙重不划算
4. **法遵獨特**：台灣金管會配息規則（含**收益平準金**）、2026/4/24 25% 新令、ETF 揭露時程 — 國際工具沒有這些 domain model

**敘事**：「我們做的是 Morningstar 不會做的縫隙。」這四個結構性護城河同時是**國際大廠不會進場的理由**，也是**我們在台灣市場可長期經營**的理由。

**已驗證散戶痛點**：
1. 高股息 ETF 換股率高達 7 成，散戶無法即時掌握真實成分（udn.com 2026/04 系列）
2. 名為「高股息」但殖利率僅 3% 的不在少數
3. 持有 0050+0056+00878+00919，台積電/金融實際曝險可能 60%+ 但散戶不知
4. ESG / 永續名稱可能漂綠
5. 配息含「收益平準金」（資本返還非真正股息），藏在公開說明書 p.80
6. 主題 ETF 名實不符
7. 投資哲學差異需讀完兩本 170 頁公開說明書
8. 月報「投資觀點」散戶不讀

---

## 4. 8 個 Hybrid RAG 殺手 query

設計原則：**結構化 + 非結構化雙邊都用上**，否則就是 join + group by。

### Q1. 名實相符度 — 「我買的『電動車 ETF』真的是電動車嗎？」
- Vector：公開說明書「投資目標」「成分股篩選」、月報「主題敘事」、指數編製規則 PDF
- Graph：`(ETF)-[HOLDS@權重]->(Stock)-[IN_THEME]->(主題)`；Stock 掛 LLM 預先標註的真實主題
- 合成：比對宣稱主題 vs 實際持股加權主題分布 → 名實相符分數 + 偏離 Top 3
- 為何非 Hybrid 不可：「主題」是語意（純 SQL 沒此欄位），「權重加總」是計算（純向量會幻覺）

### Q2. 跨多檔組合穿透（hero）— 「我同時買 0050+006208+00878+00992A 各 10 萬，台積電真實曝險多少？」
- Graph：`(Portfolio)-[HOLDS_ETF@金額]->(ETF)-[HOLDS@權重]->(Stock)`，多跳遍歷 + 加權求和
- Vector：用公開說明書解釋為何集中（兩檔追類似指數）
- 合成：「為何這四檔合計給你 X% 台積電 — 0050 直接給 53%，00878 名雖永續但 ESG 高分前幾名是台積電…」
- 為何非 Hybrid 不可：純 Graph 只給數字，缺因果敘事；純 Vector 永遠算不對權重

### Q3. 漂綠檢測 — 「00xxx ESG 高股息，但成分股 ESG 真的高？」
- Vector：CSR / 永續報告書、ETF 公開說明書 ESG 篩選方法論、指數編製 ESG 標準段
- Graph：`(Stock)-[ESG_RATED@分數]->(評等機構)`；可從 TWSE ESG 揭露（22 個 t187ap46 子表）取結構化指標
- 合成：對成分股加權平均 ESG vs 大盤；列出「ESG 標籤 vs 實際分數低於大盤」的成分股
- 為何非 Hybrid 不可：「方法論」在文件、「分數」在資料表

### Q4. 配息政策語意比較 — 「00919 vs 00878 vs 00940 配息政策差在哪？哪一檔有收益平準金陷阱？」
- Vector：三檔公開說明書「配息政策」+ 配息公告 PDF
- Graph：`(ETF)-[PAID@金額,日期,類型]->(Investor)`，類型分「股利所得 / 資本利得 / 收益平準金」
- 合成：摘要三檔配息來源歷史比例 + 引用公開說明書關鍵句佐證
- 為何非 Hybrid 不可：「收益平準金」是法律名詞純 SQL 無語意；分配金額是純結構化

### Q5. 投資哲學差異 — 「同樣追台灣 50，0050 vs 006208 真的等價？」
- Vector：兩檔公開說明書、月報、追蹤誤差說明
- Graph：`(ETF)-[TRACKS]->(Index)`、`HAS_FEE`、`TRACKING_ERR`
- 合成：表面追同指數但費用、流動性、追蹤誤差、稅後配息有別
- 為何非 Hybrid 不可：純表給不出「為什麼選一個不選另一個」的決策語言

### Q6. 月報觀點 vs 隔月績效對賭
- Vector：每月主動式 ETF 月報「展望」段
- Graph：`(月報)-[ON_DATE]->(月份)-[FOLLOWED_BY]->(下月績效)`
- 合成：「該主動式 ETF 過去 12 個月月報看多時下月正報酬比例 X%」— 主動式 ETF 法規 2024+ 才大量發行，搶時效
- 為何非 Hybrid 不可：月報觀點 NLP 抽；績效結構化

### Q7. 重複曝險早期警告 — 「我加買 00xxx 是分散還是雪上加霜？」
- Graph：對既有持股 + 候選 ETF 算 Jaccard / 加權重疊
- Vector：解釋為何重疊（兩個指數篩選條件相似，從編製規則 PDF 抽）
- 合成：「加買後 Top 10 集中度從 42% → 58%」+「主因：兩者都用『市值前 100 + 殖利率前 30%』篩選邏輯」
- 為何非 Hybrid 不可：CMoney 只能算數字，給不出「為何重疊」的解釋

### Q8. 法規衝擊問答 — 「2026/4 金管會 25% 新令，我手上的主動式 ETF 會怎樣？」
- Vector：金管會新聞稿、新令文、各投信公告
- Graph：`(ETF)-[HOLDS]->(Stock)`，篩 Stock=台積電且權重 >10% 的 ETF
- 合成：法規語意 + 結構化清單 + 曝險變化預測
- 為何非 Hybrid 不可：時效性 + 因果 + 量化缺一不可

---

## 5. 工程可行性

### 範圍
**範圍 16 檔**：12 檔散戶熱門（依 MoneyDJ 受益人排行 2026/05）0050、00878、0056、00919、006208、00940、00929、00713、0052、00881、00922、00992A ＋ 4 檔主動式對照組 00400A、00981A、00982A、00984A
**Demo Persona**：小資高股息族、市值派、主題追熱族
**資料**：6/5 真實成分股凍結快照（etfinfo.tw），現場不打 live API

### 量級

| 資料 | 量級 |
|---|---|
| 16 × 公開說明書 | ≈ 2,400 頁 → 4,000–6,500 chunks |
| 16 × 月報 × 12 月 | ≈ 192 份 → 3,300–4,600 chunks |
| 指數編製規則（多檔共用） | ≈ 8 份 → 500 chunks |
| 16 × 季報 + 年報 | ≈ 80 份 → 2,700 chunks |
| **Vector 總量** | **約 10,000–14,000 chunks，~65 MB（1536 維）** |
| HOLDS 邊（一年） | 16 × 30 × 365 ≈ 175 K 邊 |
| 配息事件 | ≈ 190 筆（16 檔 × 約 12 月） |
| 受益人結構（每週） | 16 × 15 × 52 = 12,480 筆 |
| ESG 評分 | 全市場約 1,500 檔 × 22 子題 |

### 框架建議
LangChain / LlamaIndex + Chroma + Neo4j + Streamlit + Claude / GPT-4o

### 5 週時程

| 週 | 任務 |
|---|---|
| W1 | 資料源確認 + 16 檔抓取腳本 |
| W2（5/10 前） | **PPT 完成 + 1 個 hero query 跑通**（建議 Q2 跨多檔穿透，做 demo gif） |
| W3 | Graph schema 落定 + Vector ingestion |
| W4 | 8 個 hero queries 全部跑通，prompt 收斂 |
| W5 | 視覺化（穿透流向圖、漂綠表格/雷達）+ Demo 排練 |
| W6（6/26 前） | 現場排練、備援快照、容錯 |

### Rate limit / 爬蟲注意
- TWSE OpenAPI：> 30 req/sec 會 429，建議 0.5–1 req/sec
- TDCC：CSV 每檔 1–14 MB，不要密集打
- FinMind：免費 300 req/hr
- 各投信網站：playwright，月報一次性下載
- mis.twse iNAV：盤中爬會被 ban — **Demo 用快照**

---

## 6. 撞題風險與差異化

- 散戶痛點熱門題，**估計撞題 20–35%**
- 但「Hybrid RAG 雙鏈真做」隊伍預估 < 5%，多數會做純 Vector + SQL

**差異化武器（按重要性排序）**
1. **穿透流向圖視覺化** — 左 ETF 組合 / 中 個股穿透 / 右 產業集中度，一張圖讓評審秒懂；現場 Demo 採 Mermaid `graph LR`，穩定優先
2. **漂綠雷達 + 名實相符分數** — 可量化指標，輿論性強
3. **三 Persona Demo** — 小資 / 市值 / 主題追熱，展示泛化
4. **集中度震句**（0052 富邦科技 64% 是台積電一檔）— 開場 30 秒 hook
5. **引用回鏈** — 每答附「來源：真實成分股持股表 2026-06-05 + SITCA 配息公告」，法遵級可追溯

---

## 7. 提案敘事

### 7.1 名稱：**ETF 透視鏡 PASSPORT**
Penetration · Allocation · Sustainability · Strategy · Portfolio Overlap · Risk Tracker（PPT 一頁拆解 6 字）

### 7.2 受眾 × 痛點 4×表

| 受眾 | 痛點 1 | 痛點 2 | 痛點 3 | 解法 |
|---|---|---|---|---|
| 小資高股息族（0056/00878/00919） | 三檔重複度高 | 配息有「收益平準金」 | 換股後成分變了 | Q2 + Q4 + 換股提醒 |
| 市值派（0050/006208） | 兩檔差異 | 台積電佔比破 50% | 追蹤誤差差很多 | Q5 + 即時權重 |
| 主題追熱族 | 名實不符 | 漂綠 | 主題輪動快 | Q1 + Q3 + Q6 |
| 主動式 ETF 新進（00981A/00992A） | 經理人怎挑 | 月報展望可信？ | 法規剛改 | Q6 + Q8 |

### 7.3 三句金句
1. 「**台股 ETF 受益人破 1458 萬，但你真的知道你買了什麼嗎？**」（udn 2026/04/30）
2. 「**你以為買了 4 檔 ETF 是分散，其實你只是用 4 種包裝買了同一籃台積電。**」
3. 「**冷的是公開說明書 171 頁、月報 PDF、配息公告；溫的是 30 秒就讓你看清自己。**」

### 7.4 一分鐘 Demo 開場

> ⚠️ 此為早期草稿；現行開場見 `research/demo_script.md`（已移除過時的 25% 上限鉤子，改用真實集中度）。
>
> *（封面）*
> 「富邦科技 0052 有 64% 是台積電一檔，連 0050 也有近 58% — 你以為的分散其實是同一籃台積電。」
>
> *（切：使用者輸入「我有 0050、006208、00878、00992A 各 10 萬」）*
> 「小明的問題：『我這個組合，台積電曝險多高？』」
>
> *（系統秒回穿透流向圖：ETF → 台積電；台積電亮紅，31.1%）*
> 「31.1%。我橫跨 4 種風格，其實 1/3 壓在一檔；連加的高股息 00878 都 0% 台積電，毫無稀釋。」
>
> *（右側引用回鏈：真實成分股持股表 2026-06-05、0050/006208 同追 FTSE TWSE Taiwan 50 指數事實）*
> 「這就是 ETF 透視鏡 — Hybrid RAG 把真實持股圖譜 × 配息公告語意結合，讓散戶 30 秒看清自己。」
>
> *（跳出三聊天泡泡：「電動車 ETF 真的是電動車嗎？」「00919 跟 00878 配息政策差在哪？」— 暗示泛化）*

---

## 8. 風險清單

| 風險 | 緩解 |
|---|---|
| TDCC 2-41 endpoint 回空 | 預先寫 web scrape，Demo 用快照 |
| 各投信網站結構差異 | 只做這 16 檔；元大/國泰/富邦/群益/復華 5 家覆蓋 9 檔 |
| 公開說明書 OCR 品質 | 大廠 PDF 是文字檔可直接抽；小廠 PyMuPDF + pdfplumber + 後備 OCR |
| LLM 幻覺權重數字 | 結構化計算走 Graph，LLM 只做敘事與引用 |
| 6/26 Demo 資料過期 | 6/5 真實成分股凍結（距決賽僅三週）；評審可拿公開持股核對 |
| 撞題 | 穿透流向圖 + 漂綠/名實檢測 + 個人組合穿透切角差異化 |

---

## 9. 待人工驗證

1. TDCC 2-41 是否長期空 → 點開 https://www.tdcc.com.tw/portal/zh/stats/openData 實際下載
2. 16 檔目標各家 PCF / 公開說明書直連（5 家發行商即足夠）
3. 主動式 ETF 每日全持股揭露頁 → https://www.twse.com.tw/zh/products/securities/etf/products/active-list.html
4. 漂綠案例：找 1–2 檔 ESG ETF 的成分股 ESG 分數實算，做 PPT 鎮店之寶截圖

---

## Sources（核心 URL，已實測）

- TWSE OpenAPI：https://openapi.twse.com.tw/ ｜ Spec: https://openapi.twse.com.tw/v1/swagger.json
- TPEx OpenAPI：https://www.tpex.org.tw/openapi/ ｜ Spec: https://www.tpex.org.tw/openapi/swagger.json
- TDCC 開放資料：https://www.tdcc.com.tw/portal/zh/stats/openData
- TDCC OpenAPI：https://openapi.tdcc.com.tw/
- TDCC 股權分散：https://www.tdcc.com.tw/portal/zh/smWeb/qryStock
- 集保 fundclear：https://www.fundclear.com.tw/etf
- TWSE ETF 列表：https://www.twse.com.tw/zh/products/securities/etf/products/list.html
- TWSE 主動式 ETF：https://www.twse.com.tw/zh/products/securities/etf/products/active-list.html
- TWSE ETF 配息：https://www.twse.com.tw/zh/products/securities/etf/products/div.html
- TWSE iNAV 即時：https://mis.twse.com.tw/stock/data/all_etf.txt
- TWSE 收益分配新制：https://www.twse.com.tw/market_insights/zh/detail/ff8080818bf08529018bf6c5d9550014
- TWSE e添富散戶：https://www.twse.com.tw/zh/ETFortune/index
- TWSE e添富機構：https://www.twse.com.tw/zh/ETFortune-institute/index
- MOPS 公開說明書：https://mops.twse.com.tw/mops/web/t57sb01_q7
- SITCA ETF 專區：https://www.sitca.org.tw/ROC/SITCA_ETF/index.html
- SITCA ETF 明細：https://www.sitca.org.tw/ROC/SITCA_ETF/etf-statement.html
- 臺灣指數公司：https://taiwanindex.com.tw/
- 編製規則下載：https://taiwanindex.com.tw/en/downloads/compilation_rule
- 元大 0050 PCF：https://www.yuantaetfs.com/tradeInfo/pcf/0050
- 元大 0050 文件：https://www.yuantaetfs.com/product/detail/0050/download
- 兆豐 00692 公開說明書（171 頁樣本）：https://www.megafunds.com.tw/MEGA/download/c_fund_download_vg/238_2.pdf
- MoneyDJ 受益人排行：https://www.moneydj.com/etf/x/rank/rank0016.xdjhtm
- CMoney 熱門 ETF：https://www.cmoney.tw/forum/etf/hot
- 玩股網受益人排行：https://www.wantgoo.com/stock/etf/ranking/shareholders
- MacroMicro Screener：https://en.macromicro.me/etf/tw/screener
- 金管會 25% 新令：https://newtalk.tw/news/view/2026-04-24/1031531
- HybridRAG 論文：https://arxiv.org/html/2408.04948v1
- HierFinRAG 論文：https://www.mdpi.com/2227-9709/13/2/30
