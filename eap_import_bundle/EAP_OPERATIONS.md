# EAP 平台完整操作手冊

> 寫給接手 ETF 透視鏡 PASSPORT 專案的人（不論是隊員、決賽協作者，還是另一個 AI agent）。  
> 內容是從實際操作中踩過的坑整理出來，不是官方文件的翻譯 — **每一條都遇過**。

---

## 0. 平台基本資訊
ㄌ
| 項目 | 值 |
|---|---|
| 平台名稱 | EAP (Enterprise Assistant Platform) |
| 提供商 | 精誠資訊 SYSTEX |
| Web 入口 | `https://cloud.geminidata.com` |
| API base | `https://cloud.geminidata.com/api/v1` |
| 文檔 | 平台內 API Verify 頁面（chat 列表內建範本） |
| 認證方式 | JWT Bearer Token，**單一固定**（非 OAuth、非 refresh） |
| 資源範圍 | 一個 token 通常綁一個 user × 一個 tenant，但可跨多個 project |

---

## 1. 認證與取得 project_id

### 1.1 取 token

- 競賽情境下，token 直接由使用者貼給你（從前台「API Verify」頁面複製）
- token 是 JWT，**不要試圖解析或 refresh** — 過期就請使用者重發
- 過期回應：`HTTP 401 {"error": "..."}`

### 1.2 取 project_id

進入前台後 URL 形如：

```
https://cloud.geminidata.com/portal/project/69eafd09e2d327002b0c63aa/assistant/chat/...
                                              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                              這串就是 project_id
```

所有 API 路徑（chat / import）都隱含在這個 project 底下 — 切 project 要重抓 project_id。

### 1.3 標準 Python header

```python
import requests
TOKEN = "eyJhbGc..."          # 從使用者拿
PROJECT_ID = "69eafd09..."
BASE = "https://cloud.geminidata.com/api/v1"
H = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}
```

### 1.4 驗證 token 可用

```python
r = requests.get(f"{BASE}/chat", headers=H)
assert r.status_code == 200, "token failed"
```

---

## 2. Graph 資料匯入 — 最坑的部分

### 2.1 端點

```
POST /api/v1/import/graph
```

### 2.2 必要 body shape（**properties.label 是必填**）

這個格式是 trial-and-error 反推出來的 — 官方範例少寫了關鍵欄位：

```json
{
  "csv_url": "https://your-storage.example.com/etf_metadata.csv",
  "mapping": {
    "graph": {
      "nodes": [
        {
          "label_field": "ticker",
          "label_type": "ETF",
          "properties": {
            "label": "{{name}}",        ←  必填！缺它整批匯入失敗
            "issuer": "{{issuer}}",
            "type": "{{type}}",
            "expense_ratio": "{{expense_ratio}}"
          }
        },
        {
          "label_field": "stock_ticker",
          "label_type": "Stock",
          "properties": {
            "label": "{{stock_name}}",  ←  每個 node 都要 label
            "sector": "{{sector}}"
          }
        }
      ],
      "edges": [
        {
          "from_field": "etf_ticker",
          "to_field": "stock_ticker",
          "label_type": "HOLDS",
          "properties": {
            "weight_pct": "{{weight_pct}}",
            "date": "{{date}}"
          }
        }
      ]
    }
  }
}
```

### 2.3 我踩過的具體錯誤

| 嘗試的 mapping | 結果 |
|---|---|
| `properties` 為 `{}`（空物件） | `500 Internal Server Error` |
| `{ "name": "{{name}}" }`（沒 label 欄位） | `500`，錯誤訊息隱晦 |
| `{ "label": "{{name}}" }` | ✅ 成功 |
| 把 nodes/edges 寫在 mapping 最外層（沒包 graph） | `400 invalid mapping` |

**結論：每個 node 物件的 `properties` 內一定要有 `label` key，值是 CSV 欄位的 `{{template}}`。**

### 2.4 上傳 CSV 的方式

`csv_url` 需要是 **EAP 能直接 fetch 到的 HTTPS URL**。三種做法：

1. **預先傳到 storage**：S3 presigned URL / GitHub raw / pastebin raw — 最常用
2. **base64 inline**（如果 API 支援）：把 CSV 內容 base64 後塞 `csv_inline` 欄位 — 平台版本不一定支援
3. **前台 UI 上傳**：手動進 Data Explorer → Import → 拖檔，這條最穩但無法自動化

### 2.5 驗證匯入結果

```python
# A. 確認 status
r = requests.get(f"{BASE}/import/graph/{import_job_id}", headers=H)

# B. 直接看節點數
r = requests.post(
    f"{BASE}/chat/{chat_id}",
    headers=H,
    json={"q": "請執行: MATCH (n:ETF) RETURN count(n)", "streaming": False},
)
```

或最直觀：到前台 **Data Explorer → Source Data 面板**看每個 label_type 的節點數對不對。

### 2.6 大批匯入注意

- 一次 push 不要超過 ~10 MB CSV（會超時）
- 多個 CSV 序列 push 比一個大 CSV 穩
- import 是非同步，status pending → success/failed，不要立即查節點

### 2.7 重灌（re-import）的真實行為 — 2026-06-12 實測

重灌 holdings（96 條舊邊 → 灌 724 列新資料）時踩出來的，全部都驗證過：

1. **節點會 MERGE**（`meta.keys` 有設 key 的話）：同 ticker 的 Stock 節點屬性被新值覆蓋。
   注意 name 也會被蓋 — 不同 ETF 對同一檔個股的名稱寫法不同（如 2330 有「台積電」
   和「台灣積體」兩種），最後處理到的那列贏。
2. **邊不去重**：`meta.keys: []` 的邊（HOLDS）重灌是「累加」不是覆蓋 —
   實測後總邊數 = 96（舊）+ 724（新）= 820。
3. **chat 的 Cypher 是唯讀模式**：`DELETE` / 寫入操作一律回「唯讀模式不可執行」。
   別想用 chat 清資料。
4. **刪 import flow/model/source 不會回收已灌入的圖資料**：DELETE 全部回 200，
   但邊數不變。**平台沒有任何 API 可以刪圖資料** — 要嘛前台手動處理，要嘛接受殘留。
5. **chat 數 count 偶爾數錯**：同一條 `MATCH ()-[h:HOLDS]->() RETURN count(h)`
   前後兩次回 96 和 0。關鍵數字多問一次。
6. 殘留的舊節點不會消失：不在新 CSV 裡的舊個股（如台泥 1101，sector=水泥）會留在圖上。

→ 結論：**圖資料實務上是 append-only**。規劃 schema 時就要想好重灌策略
（例如邊帶 version/date 屬性 + 查詢時過濾），不要假設之後能清掉重來。
完整重灌腳本：[reimport_holdings.py](reimport_holdings.py)。

---

## 3. Vector 知識庫匯入（PDF / 文檔）

### 3.1 端點

```
GET  /api/v1/import/vector/knowledge   # 列出已上傳文件(file_name/file_status/chunk_ids/labels)
POST /api/v1/import/vector/knowledge   # 上傳一份 PDF —— 必須 multipart/form-data
```

### 3.2 上傳格式 — **multipart，不是 JSON**（2026-06-05 實測）

⚠️ 用 JSON body（`{file_url/uploadId/...}`）後端會崩成 **502/503**（真失敗，檔案不會進）。
正確做法是直接 multipart 傳檔，平台會自己向量化、產 title/summary/chunks：

```bash
curl -H "Authorization: Bearer $TOK" \
  -F "file=@00878_dividend_112Q4.pdf;type=application/pdf" \
  -F "doc_type=dividend_notice" \
  -F "labels=00878,2026-06-05,dividend_notice,zh-TW,SITCA" \
  "$BASE/import/vector/knowledge"
# → HTTP 200（body 空）。不需 signed-url，不需先 PUT S3。
```

### 3.3 確認已索引

上傳是非同步向量化。送出後 **~10-25 秒**再 `GET /import/vector/knowledge`，
該檔 `file_status` 應為 `1` 且 `chunk_ids` 非空：

```python
import time, requests
time.sleep(20)
ks = requests.get(f"{BASE}/import/vector/knowledge", headers=H).json()["knowledge"]
ok = [k for k in ks if k["file_name"]==fname and k["file_status"]==1 and k["chunk_ids"]]
```

### 3.4 檢索 grounding — **問法要鎖定文件，否則 LLM 會幻覺**

實測：chat 檢索**會用到**上傳文件，但只在問題**指名特定文件**時可靠。

- ✅ 「依據 00878 民國112/10/31 收益分配公告，各類占比?」→ 正確回 股利31.36/利息0.07/平準金5.71/資本利得62.86（與公告一致）
- ❌ 「00878 最近一次配息收益平準金占多少?」→ LLM 改用訓練資料**幻覺**（回 78/12/10 假數字）

對策：① Robot Setting 寫死「優先用知識庫、不准憑記憶估算」；② demo 問法鎖定文件；
③ 數字不確定就走 mock 秒回（`mock_responses.js` Q-B 已含真數字 5.71%）。
chat 回應 JSON 無顯式 sources 欄位，要看內容是否命中真數字來判斷有沒有 grounding。

---

## 4. Robot Setting（System Prompt）

### 4.1 兩條路注入

**方式 A — 前台貼（推薦）**：
1. 進 EAP → 機器人設定 → 編輯
2. 整段 prompt 貼進去（可以 200+ 行）
3. 儲存

**方式 B — API**：
```
POST /api/v1/robot/setting
  body: { "system_prompt": "..." }
```
版本不一定都支援，API Verify 頁面如果沒列就用前台貼。

### 4.2 重要：**改完要新開 chat**

舊 chat 沿用建立時的 Robot Setting 快照，**改 setting 不影響已存在的 chat**。

測試 setting 是否生效：

```python
# 1. 改完 setting
# 2. 新開 chat
r = requests.post(f"{BASE}/chat/create", headers=H, json={"title": "test new setting"})
chat_id = r.json()["insertedId"]
# 3. 問一個會觸發 setting 規則的問題
# 例如「我該買 0050 嗎？」應該被拒答條款攔截
```

### 4.3 Prompt 結構建議

Robot Setting 200 行 prompt 我們切成 6 段（見 `robot_setting.txt`）：

1. **角色與語氣** — 散戶顧問、白話翻譯
2. **數字鐵則** — 百分比/權重一律走 Graph，禁 LLM 心算
3. **Cypher v5 約束** — 禁 OVER()、persist date filter
4. **引用回鏈格式** — Graph / Vector / 法規 三種引用
5. **拒答條款** — 個股建議、漲跌預測直接回拒
6. **答題決策樹** — A/B/C 路由邏輯

---

## 5. Chat API — 最常用的部分

### 5.1 建立 chat

```python
r = requests.post(
    f"{BASE}/chat/create",
    headers=H,
    json={"title": "Q-Demo-A: 主動式 ETF 台積電 Top 5"},
)
chat_id = r.json()["insertedId"]   # ← 注意這個欄位名
```

### 5.2 送問題

```python
r = requests.post(
    f"{BASE}/chat/{chat_id}",
    headers=H,
    json={
        "q": "請列出主動式 ETF 中對台積電持股 Top 5",   # ← body field 是 q
        "streaming": False,    # True 走 SSE
    },
    timeout=300,
)
```

### 5.3 重要的 field name 坑

| 試過的 field | 結果 |
|---|---|
| `"text": "..."` | ❌ 400 |
| `"message": "..."` | ❌ 400 |
| `"prompt": "..."` | ❌ 400 |
| `"question": "..."` | ❌ 400 |
| `"q": "..."` | ✅ |

文檔沒寫清楚 — 這條我踩了兩次才確認。

### 5.4 解析 streaming response

```python
import re, json
r = requests.post(f"{BASE}/chat/{chat_id}", headers=H,
                  json={"q": question, "streaming": True}, stream=True)
result = None
for line in r.iter_lines():
    if line.startswith(b"data: "):
        chunk = json.loads(line[6:])
        if chunk.get("event") == "done":
            result = chunk.get("result")
```

非 streaming（`"streaming": False`）會等到完整回應再回，但同樣是 SSE 格式 — 找 `data: {...}` 取最後一行：

```python
match = re.search(r'data: (\{.+\})', r.text, re.DOTALL)
data = json.loads(match.group(1))
print(data["result"])
```

### 5.5 取歷史訊息

```python
r = requests.get(f"{BASE}/chat/{chat_id}/messages", headers=H)
# 回包含 user / assistant 兩種 role 的 list
```

### 5.6 圖表生成（chartgen）

```
POST /api/v1/chat/{chat_id}/{message_id}/chartgen
```

需要對特定 message 後追問「請畫圖」。EAP 會根據 message 內的數據生 Sankey / Radar / Stacked Bar。**但我們實作上發現 Mermaid 內聯更穩**（下節）。

---

## 6. Mermaid 視覺化技巧（強推）

### 6.1 為什麼用 Mermaid

EAP chat **內建 Mermaid 渲染**（前台 chat 視窗會自動把 ```mermaid 區塊轉成 SVG）。比 chartgen API 穩、比 Canvas 穩。

### 6.2 怎麼觸發

問題裡明確要求 LLM 輸出 Mermaid 程式碼塊：

```
請執行 Cypher：
MATCH (e:ETF {ticker:'0050'})-[h:HOLDS]->(s:Stock)
WHERE h.date='2026-06-05'
RETURN s.label, h.weight_pct
ORDER BY h.weight_pct DESC LIMIT 5

然後將結果用 Mermaid graph LR 語法視覺化：
- 0050 節點 → 5 個個股節點
- 每條邊標明 weight%

請務必輸出 ```mermaid 程式碼塊。
```

### 6.3 截圖技巧

前台 chat 視窗渲染完 Mermaid SVG 後：
- 瀏覽器開 DevTools → Inspect 那個 SVG 節點 → Copy element → 貼到 [draw.io](https://app.diagrams.net) 或直接截圖
- 或用 Playwright headless：渲染等 SVG 出現 → `page.locator("svg").screenshot()`

我們的 `kg_mermaid_clean.png` 就是這樣抓的（見 `slides/assets/`）。

---

## 7. Canvas Graph Explorer — 別自動化

### 7.1 為什麼

前台 **Data Explorer → On Canvas** 是用 **PIXI.js 渲染 WebGL**，不是 DOM。

### 7.2 試過的全失敗手法

| 工具 | 為什麼失敗 |
|---|---|
| `playwright.mouse.down/move/up` | 事件被 PIXI 的 pointerdown handler 攔截 |
| HTML5 drag & drop API | Canvas 不接受 HTML5 drag 事件 |
| `playwright.locator.drag_to()` | 同上 |
| Synthetic touch events | PIXI 有 anti-bot 檢查 isTrusted=true |
| 注 JS 直接呼叫 PIXI internal API | 內部 API 經混淆，沒文檔 |

### 7.3 替代方案

**用 Mermaid（第 6 節）** — 99% 情境下夠用。

真的需要 Canvas layout 截圖（例如要展示 EAP 介面）：請使用者**手動拖**，再請他存圖。**別花超過 15 分鐘想自動化這塊。**

---

## 8. 標準操作流程（端到端）

新接手案子，建議照這個順序操作 EAP：

```text
[1] 拿 token + project_id
    └─ GET /chat 驗 401? 沒 401 就 OK

[2] 規劃 graph schema
    └─ 寫 .cypher DDL 檔
    └─ 為每種 node type 想清楚 properties.label 對應 CSV 哪一欄

[3] 準備資料 CSV
    └─ 標準化 UTF-8、欄名英文、日期 YYYY-MM-DD
    └─ 把 CSV 上傳到可被 EAP 公開 fetch 的 URL

[4] Import graph（一個 label_type 一次）
    └─ POST /import/graph，properties.label 必填
    └─ GET /import/graph/{job_id} 等 succeeded
    └─ 前台 Data Explorer 確認節點數

[5] Import vector knowledge（PDF）
    └─ POST /import/vector/knowledge，附 metadata
    └─ 502 別怕，GET 列表確認

[6] 寫 Robot Setting
    └─ 前台貼整段 prompt
    └─ 新開 chat 測 — 不要在舊 chat 測

[7] 跑 demo 題
    └─ POST /chat/create 拿 chat_id
    └─ POST /chat/{chat_id} body 用 q
    └─ 解析 SSE 取 result

[8] 視覺化
    └─ 問題裡要求 ```mermaid 輸出
    └─ 前台 chat 視窗截圖
```

---

## 9. 除錯查表

| 症狀 | 最可能的原因 | 第一步檢查 |
|---|---|---|
| `401 Unauthorized` | Token 過期 / 沒帶 `Bearer ` 前綴 | 重貼 token、檢查 `Authorization: Bearer xxx` |
| `400 Bad Request` on chat | body field 不是 `q` | grep 你的程式碼有沒有寫 `text=` / `message=` |
| `500` on import graph | `properties.label` 缺欄 | 看 mapping JSON 每個 node 都有 `properties.label` |
| `502 Bad Gateway` (CloudFront) | CDN 抖動，未必真失敗 | `GET /import/...` 列出確認檔案存在 |
| Chat 回應空 | streaming flag 跟解析方式不匹配 | streaming=False 就 regex 抓最後 `data: {...}` |
| Chat 回應跟預期不符 | Robot Setting 未生效 | 確認是新 chat（建 chat 後才能載入新 setting） |
| Mermaid 沒渲染 | LLM 沒輸出 ```mermaid 區塊 | 問題裡明確說「請務必輸出 ```mermaid 程式碼塊」 |
| Cypher 報 `OVER 不支援` | Neo4j v5 不認 OVER() | 改用 `WITH ... ORDER BY ... COLLECT(..)[..N]` |
| 持股查詢回空 | 缺 date filter | `WHERE h.date = date('2026-06-05')` |
| Vector retrieval 撈到無關 chunk | 沒 filter | `filter: {section: '配息政策'}` |

---

## 10. 本專案實作參考

| 檔案 | 用途 |
|---|---|
| [import_to_eap.py](import_to_eap.py) | Graph 匯入完整腳本，跑過實測 |
| [robot_setting.txt](robot_setting.txt) | 完整 200 行 system prompt（6 段），貼進 Generate Response 格 |
| [robot_setting_slots.md](robot_setting_slots.md) | Robot Settings 8 格插槽各自的貼入內容 + 驗收清單 |
| [etf_metadata.csv](etf_metadata.csv) / [holdings.csv](holdings.csv) | Graph 來源資料 |
| [dividends.csv](dividends.csv) / [regulatory_events.csv](regulatory_events.csv) | 事件節點來源 |
| [graph_schema.cypher](graph_schema.cypher) | Neo4j v5 DDL（節點/邊類型定義 + 6 大 Demo Query 範本） |
| [../research/prompt_design.md](../research/prompt_design.md) | 三類 Demo Prompt + 子任務 prompt §3.1–§3.4 |
| [../slides/assets/Q-Demo-*_chat_screenshot.png](../slides/assets/) | 三題 demo 在 EAP chat 上跑出來的真實截圖 |
| [../slides/assets/kg_mermaid_clean.png](../slides/assets/) | 0050 持股 Top 5 Mermaid 渲染（chat 內生成） |

---

## 11. 不要做的事 — 把這條讀完省 4 小時

1. **不要試 OAuth refresh flow** — 直接 JWT，過期請使用者重給
2. **不要在舊 chat 測新 Robot Setting** — 改完要重開
3. **不要用 Playwright 拖 Canvas** — PIXI 擋你
4. **不要假設 502 = 失敗** — 先 GET 確認
5. **不要把 nodes/edges 寫在 mapping 最外層** — 要包在 `mapping.graph.{...}` 裡
6. **不要忽略 `properties.label`** — 每個 node 必填
7. **不要在 Cypher 用 OVER()** — Neo4j v5 不支援
8. **不要忘了 date filter** — 持股是 time-series，沒 date filter 會撈到全年所有快照
9. **不要把 prompt 寫太長進 Robot Setting 的單一段** — 切 6 段以上更穩定
10. **不要對 chartgen 期望太高** — Mermaid 內聯比較穩

---

## 12. 如果還有時間 — 加分項

這些是進階用法，初賽用不到，決賽前可以做：

- **多 project 切換**：同一 token 可跨 project，但要切 project_id；如果是不同 tenant 要重發 token
- **Robot Setting A/B test**：建兩個 chat，一個用舊 setting，一個用新 setting，同一個問題各問一次，比答案差異
- **Cypher 範本快取**：把常用 Cypher 寫成 query template，runtime 只填 $param，比每次讓 LLM 重生快且穩
- **Vector + Graph 結果手動 fusion**：把 Graph 數字鎖死後拼 prompt context 餵 LLM，避免讓 LLM 自由發揮
- **EAP Workspace 共用**：團隊多人協作時，把 token 收進 1Password / secrets manager，不要塞在程式碼裡

---

## 結語

EAP 不是 LangChain / LlamaIndex 那種「寫 Python 就行」的框架，它是有自己 UI、自己 schema convention、自己 quirks 的 SaaS 平台。**操作上 60% 在 API、30% 在前台、10% 在搞清楚他們的 mapping format**。

最大的學習成本是 graph import 那段 `properties.label` 跟 chat body field `q` —— 這兩個地雷踩過後，剩下就是熟練度問題。
