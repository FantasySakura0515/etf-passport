# ETF 透視鏡 PASSPORT — 前端 Demo

對接 EAP Chat API（cloud.geminidata.com）的單頁應用，作為決賽 6/26 現場 Demo 用。

## 功能

- 持股輸入區（4 個 ETF + 金額，三 Persona 一鍵載入）
- 對話框：**逐 token 顯現**（打字機效果，模擬 LLM streaming；散文逐字、表格/Mermaid 整塊浮現）、Markdown 渲染、Mermaid 流向圖（`graph LR`）
- 每則 AI 回覆有「複製」按鈕（簡報指定；Clipboard API 失敗自動退 execCommand，永不崩）
- 引用回鏈側欄
- **決賽現場：全程本地模式（預設 ON）** — 數字題走本地確定性計算（`penetrate.py`，秒回、可重算）、質化題走預錄（`mock_responses.js`），**完全不依賴 EAP / 網路，零開天窗風險**。本地計算若失敗還會自動退到預錄（三重保險）。取消勾選「Mock」才會改走 EAP（僅供排練比對）。
- **報告產出** — 一鍵「組合健檢報告」/「單檔透視報告」（純本地計算、斷網可演）；modal 預覽後可儲存到報告櫃（`reports/`）、下載 self-contained HTML、列印成 PDF

## 快速開始

```bash
cd demo
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
bash fetch_vendor.sh   # 下載 4 個 JS 依賴到 vendor/（一次性，~3.7 MB）
cp .env.example .env   # 填入 EAP_TOKEN 與 EAP_PROJECT_ID
python3 server.py      # 預設 http://localhost:8000
```

> ⚠️ **決賽現場備援**：`fetch_vendor.sh` 一定要在有網路時先跑過。執行後 `vendor/` 內就有 `tailwindcss.js`、`marked.min.js`、`dompurify.min.js`、`mermaid.min.js` — 即使 6/26 當天網路斷了，Q-A/Q-C/Q-D/Q-E/Q-F 仍可走本地端點，Q-B 可切 Mock 秒回。

## 架構

```
Browser ─→ FastAPI proxy (server.py) ─→ EAP Chat API
   ↑              │
   └── 靜態檔案 ──┘
```

Proxy 的工作：
- 把 `/api/v1/*` 轉發到 `https://cloud.geminidata.com/api/v1/*`，自動帶上 `Authorization: Bearer $EAP_TOKEN`
- 解決瀏覽器 CORS 限制
- 把 token 留在 server 端，不暴露給前端（即使簡報說「暫不考慮安全性」，這是低成本的好習慣）

## 設定

`.env`:
```
EAP_TOKEN=your_token_here
EAP_PROJECT_ID=68d53fa8c1e133002bdeff1d  # 換成你們的
EAP_BASE_URL=https://cloud.geminidata.com/api/v1
PORT=8000
```

## 決賽現場 checklist（全程本地模式，不靠網路）

- [ ] **先殺佔用 8000 的舊 server 實例**再起新的：`lsof -ti:8000 | xargs kill -9; python3 server.py`
      （舊實例會服務舊版端點 → `etfs` 只回 1 檔之類的怪象；務必確認跑的是最新碼）
- [ ] 開 `http://localhost:8000`，右上角顯示綠色 **「現場模式（本地）」**、「Mock」已勾選
- [ ] 六題展示 query 全跑一次，確認逐字顯現 + 表格/Mermaid 渲染：
      Q-C 穿透（31.1% 流向圖）/ Q-A 排名 / Q-B 平準金 / Q-D 名實 / Q-E 漂綠 / Q-F 選產業
- [ ] 複製鈕按一次出現「✓ 已複製」
- [ ] 報告功能：主題追熱 persona 產健檢報告 → 儲存 → 報告櫃重開 → 下載 HTML
- [ ] 拔網路再走一次（驗證真的零外部依賴）

> 排練比對才需要：EAP token + project_id 填入 `.env`、Robot Setting 貼上 EAP 後台、取消勾「Mock」走真 EAP。**正式上台一律保持本地模式。**

## 檔案

| 檔案 | 用途 |
|---|---|
| `server.py` | FastAPI proxy + 靜態檔案 server |
| `index.html` | 主頁面（Tailwind CDN + marked + mermaid） |
| `app.js` | 前端邏輯（streaming 解析、Mermaid 渲染、複製按鈕） |
| `styles.css` | 自訂樣式（覆蓋 Tailwind 細節） |
| `mock_responses.js` | Q-A/Q-B/Q-C 預錄回應（決賽備援） |
| `report.py` | 報告 Markdown 產製引擎（重用 penetrate.py） |
| `report_ui.js` | 報告按鈕 / modal / 報告櫃前端邏輯 |
| `requirements.txt` | Python 依賴 |
| `.env.example` | 環境變數範本 |

## 注意

EAP streaming 格式 — 本程式同時支援 SSE (`data: ...\n\n`) 與 NDJSON (`{...}\n{...}`) 兩種；若實際格式不同，調整 `app.js` 的 `parseStreamLine()`。
