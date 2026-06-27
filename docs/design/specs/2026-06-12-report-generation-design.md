# 報告產出功能設計（2026-06-12，已獲核准）

## 目標

demo app 新增「產出報告 → 預覽 → 選擇是否儲存」功能。兩種報告皆**純本地計算**（重用 `penetrate.py`，不打 EAP），秒產、斷網可演。

## 報告 A — 組合健檢報告

輸入：左側目前持股。章節：

1. **封面摘要** — 投入總額、ETF 檔數、產出時間、資料快照 2026-06-05；三枚判定徽章：
   - 集中度：最大單一個股曝險 🔴>25% / 🟡15–25% / 🟢<15%
   - 名實：組合內各 ETF 主題對齊度最低值 <60% 即 🔴
   - 漂綠：任一檔 ESG 溢價 ≤0 即 🟡（無 ESG 主題檔則 ⚪ 不適用）
2. **穿透分析** — 前十大個股曝險表 + Mermaid 穿透圖 + 最大單一曝險警示（`penetrate()`）
3. **重複曝險拆解** — 各 ETF 對最大單一個股的貢獻表（`penetrate()` 的 `by_etf`）
4. **各檔名實相符** — 每檔 `name_reality()` 彙整對齊度表
5. **漂綠檢測** — 每檔 `greenwash()`：加權 ESG vs 市場平均，含可評估比例誠實揭露
6. **資料來源與免責** — holdings CSV（etfinfo.tw）、AI 生成標籤 prompt 出處（AI_GENERATED_PROMPTS.md）、不構成投資建議；結尾官方 slogan「將冷冰冰的資料，轉化為有溫度的決策」

## 報告 B — 單檔 ETF 透視報告

輸入：16 檔之一（下拉）。章節：該檔前十大持股與產業分布（`penetrate()` 餵單一持股）、名實相符、漂綠檢測、資料來源與免責。

## 後端

- 新模組 `demo/report.py`：`portfolio_report(holdings) -> {title, markdown, meta}`、`etf_report(ticker) -> 同形`。**import penetrate.py，不複製計算邏輯。** meta 含 `{kind, as_of, created_at, holdings|ticker}`。
- `server.py` 新端點：
  - `POST /api/passport/report/portfolio`（body: `{holdings}`）
  - `GET  /api/passport/report/etf/{ticker}`
  - `POST /api/reports` 儲存 → `demo/reports/{YYYYMMDD-HHMMSS}.json`（內容 `{title, markdown, meta}`）
  - `GET  /api/reports` 列表（id、title、created_at）
  - `GET  /api/reports/{id}` 單筆
  - `DELETE /api/reports/{id}`
- `demo/reports/` 內容不進版控（.gitignore + .gitkeep）。

## 前端

- 左側持股區下方「📋 報告」區塊：兩鈕 —「產出組合健檢報告」、「單檔透視」+ 16 檔下拉。
- 報告以**全頁 modal** 預覽（沿用 marked + DOMPurify + Mermaid 渲染管線）。底部動作列：
  「💾 儲存到報告櫃」「⬇️ 下載 HTML」「🖨 列印 / PDF」「捨棄」— 即「選擇要不要儲存」。
- **報告櫃**：右側欄新增 tab（與引用欄並列），列出已存報告（標題＋時間），點開重看 modal、可刪除。
- 下載 HTML：self-contained 單檔（inline 樣式 + 已渲染 Mermaid SVG），瀏覽器列印即 PDF。

## 刻意不做（v1）

- 不打 EAP（數字我方自算是既定口徑；EAP 質化總評留作日後可選項）
- 不做使用者帳號；報告櫃為單一共用清單

## 錯誤處理與驗證

- 快照中不存在的 ETF：略過並在報告開頭列示（沿用 penetrate 現行做法）；組合全數無效 → 前端提示，不產報告。
- 單檔報告 ticker 不在快照 → 404 + 前端提示。
- 儲存/刪除失敗 → modal 內警告，不靜默。
- `report.py` 加 `_selftest()`（仿 penetrate.py）。
- 手動 QA：三 persona 各產一份健檢報告 + 抽兩檔單檔報告，數字須與聊天回答一致。
