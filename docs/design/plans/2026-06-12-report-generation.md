# 報告產出功能 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** demo app 新增「組合健檢報告」與「單檔 ETF 透視報告」一鍵產出，modal 預覽後可儲存到報告櫃（server 端 `demo/reports/`）、下載 self-contained HTML、列印成 PDF，或捨棄。

**Architecture:** 新模組 `demo/report.py` 重用 `penetrate.py` 的計算函式組 Markdown 報告（純本地、不打 EAP）；`server.py` 加報告產製端點與報告櫃 CRUD（JSON 檔存 `demo/reports/`）；前端新增 `demo/report_ui.js`（沿用 app.js 既有的 `renderMarkdown` / `renderMermaidIn` 全域函式），index.html 加報告按鈕區、全頁 modal、右側欄「報告櫃」tab。

**Tech Stack:** Python 3 / FastAPI（既有）、原生 JS + marked + DOMPurify + Mermaid（既有 vendor）。無新依賴。

**Spec:** `docs/superpowers/specs/2026-06-12-report-generation-design.md`

**測試慣例：** 本 repo 無 pytest；後端模組用 `_selftest()`（仿 `penetrate.py`），端點用 curl 驗證，前端手動 QA。

---

### Task 1: penetrate.py 加 `etf_list()`（前端下拉與報告需要 16 檔清單）

**Files:**
- Modify: `demo/penetrate.py`（在 `_name()` 之後加函式；`_selftest()` 末尾加 assert）

- [ ] **Step 1: 在 `_selftest()` 內（`print("\n✅ 全部 self-test 通過")` 之前）加失敗中的 assert**

```python
    lst = etf_list()
    assert len(lst) == 16 and {"ticker", "name", "is_active"} <= set(lst[0])
    print(f"\netf_list：{len(lst)} 檔 OK")
```

- [ ] **Step 2: 跑 selftest 確認失敗**

Run: `cd demo && python3 penetrate.py`
Expected: `NameError: name 'etf_list' is not defined`

- [ ] **Step 3: 實作（放在 `_name()` 函式之後）**

```python
def etf_list() -> list[dict]:
    """16 檔 ETF 清單（給前端下拉與報告封面用）。"""
    return [{"ticker": t, "name": m["name"],
             "is_active": str(m.get("is_active", "")).lower() == "true"}
            for t, m in _load()["meta"].items()]
```

- [ ] **Step 4: 跑 selftest 確認全過**

Run: `cd demo && python3 penetrate.py`
Expected: `✅ 全部 self-test 通過`（含 `etf_list：16 檔 OK`）

- [ ] **Step 5: Commit**

```bash
git add demo/penetrate.py
git commit -m "penetrate.py 加 etf_list()：16 檔清單供報告功能使用"
```

### Task 2: 新模組 demo/report.py（兩種報告的 Markdown 產製）

**Files:**
- Create: `demo/report.py`

- [ ] **Step 1: 建立 `demo/report.py` 全檔**

```python
# -*- coding: utf-8 -*-
"""ETF 透視鏡 — 報告產製引擎（純本地，重用 penetrate.py，不經 EAP）。

兩種報告（spec: docs/superpowers/specs/2026-06-12-report-generation-design.md）：
  portfolio_report(holdings) — 組合健檢報告
  etf_report(ticker)         — 單檔 ETF 透視報告
皆回傳 {"title", "markdown", "meta"}；Markdown 由前端沿用 marked + Mermaid 渲染。
"""
from __future__ import annotations

from datetime import datetime

from penetrate import ASOF, etf_list, greenwash, name_reality, penetrate

SLOGAN = "將冷冰冰的資料，轉化為有溫度的決策"


def _nf(n) -> str:
    return f"{round(n):,}"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


# ───────────────────────── 判定徽章 ─────────────────────────
def _concentration_badge(pct: float) -> tuple[str, str]:
    if pct > 25:
        return "🔴", f"高度集中：最大單一個股曝險 {pct}%（> 25%）"
    if pct >= 15:
        return "🟡", f"中度集中：最大單一個股曝險 {pct}%（15–25%）"
    return "🟢", f"集中度健康：最大單一個股曝險 {pct}%（< 15%）"


def _name_badge(nrs: list[dict]) -> tuple[str, str]:
    """nrs: 各 ETF 的 name_reality() 成功結果。以各檔主標榜主題（themes[0]）對齊度的最低值判定。"""
    if not nrs:
        return "⚪", "名實相符：無可評估的標榜主題"
    worst = min(nrs, key=lambda d: d["themes"][0]["aligned_pct"])
    t0 = worst["themes"][0]
    if t0["aligned_pct"] < 60:
        return "🔴", (f"名實落差：{worst['etf_name']} 標榜「{t0['claimed_theme']}」"
                      f"實際僅 {t0['aligned_pct']}% 對齊")
    return "🟢", f"名實大致相符：各檔主標榜主題對齊度最低 {t0['aligned_pct']}%"


def _green_badge(gws: list[dict]) -> tuple[str, str]:
    """gws: 各 ETF 的 greenwash() 成功結果。任一檔 ESG 溢價 ≤ 0 → 🟡。"""
    if not gws:
        return "⚪", "漂綠檢測：無 ESG 資料可評估"
    bad = [g for g in gws if g["esg_premium"] <= 0]
    if bad:
        names = "、".join(g["etf_name"] for g in bad)
        return "🟡", f"漂綠疑慮：{names} 加權 ESG 未高於市場平均"
    return "🟢", "無漂綠跡象：各檔加權 ESG 皆高於市場平均"


# ───────────────────────── 共用章節 ─────────────────────────
def _name_reality_section(nrs: list[dict], errs: list[str]) -> str:
    md = "## 名實相符檢測\n\n"
    if nrs:
        md += "| ETF | 標榜主題 | 實際對齊權重 | 具名持股 |\n|---|---|--:|--:|\n"
        for d in nrs:
            for i, t in enumerate(d["themes"]):
                etf_cell = f"{d['etf']} {d['etf_name']}" if i == 0 else ""
                named = f"{d['named_weight_pct']}%" if i == 0 else ""
                md += f"| {etf_cell} | {t['claimed_theme']} | {t['aligned_pct']}% | {named} |\n"
        md += "\n_名字是行銷，持股才是事實。_\n\n"
    if errs:
        md += f"> 無標榜主題資料、未列入檢測：{'、'.join(errs)}\n\n"
    return md


def _greenwash_section(gws: list[dict], errs: list[str]) -> str:
    md = "## 漂綠檢測\n\n"
    if gws:
        md += ("| ETF | 加權 ESG | 市場平均 | ESG 溢價 | 可評估持股 |\n"
               "|---|--:|--:|--:|--:|\n")
        for g in gws:
            md += (f"| {g['etf']} {g['etf_name']} | {g['weighted_esg']} "
                   f"| {g['market_avg_esg']} | {g['esg_premium']:+} "
                   f"| {g['evaluable_weight_pct']}% |\n")
        md += ("\n> ⚠️ 誠實揭露：ESG 評分僅覆蓋部分個股，"
               "「可評估持股」以外的權重無法驗證。\n\n")
    if errs:
        md += f"> 無法評估：{'、'.join(errs)}\n\n"
    return md


def _sources_section() -> str:
    return (
        "## 資料來源與免責\n\n"
        f"- 持股權重：`holdings_{ASOF}.csv`（etfinfo.tw 真實成分股，"
        f"as-of {ASOF}，經元大投信官網交叉驗證；各檔以 `_OTHER` 列補足 100%）\n"
        "- 細產業分類、主題標籤、ESG 評分：AI 生成（prompt 見 "
        "`data/snapshot_2026-06-05/AI_GENERATED_PROMPTS.md`）\n"
        "- 全部數字由我方後端 `penetrate.py` 從快照 CSV 計算，不經 LLM\n\n"
        "> ⚠️ 本報告為持股結構分析，不構成投資建議；"
        f"持股資料以 {ASOF} 快照為準，過去績效不代表未來。\n\n"
        f"---\n\n_{SLOGAN} — ETF 透視鏡 PASSPORT_\n"
    )


def _collect(etfs: list[str], fn) -> tuple[list[dict], list[str]]:
    """對每檔 ETF 跑 fn，分離成功結果與出錯檔（錯誤不中斷報告）。"""
    oks, errs = [], []
    for t in etfs:
        d = fn(t)
        (errs if d.get("error") else oks).append(t if d.get("error") else d)
    return oks, errs


# ───────────────────────── 報告 A：組合健檢 ─────────────────────────
def portfolio_report(holdings: list[dict]) -> dict:
    pen = penetrate(holdings)
    if pen.get("error"):
        return {"error": pen["error"]}
    # hero = 實際最大單一個股（不一定是台積電）；focus 對準它再算一次
    top = pen["stocks"][0]
    if top["stock_ticker"] != "2330":
        pen = penetrate(holdings, focus=top["stock_ticker"])
    f = pen["focus"]

    etfs = [e["etf"] for e in f["by_etf"]]
    nrs, nr_errs = _collect(etfs, name_reality)
    gws, gw_errs = _collect(etfs, greenwash)

    c_icon, c_text = _concentration_badge(f["exposure_pct"])
    n_icon, n_text = _name_badge(nrs)
    g_icon, g_text = _green_badge(gws)

    md = f"# 我的 ETF 組合健檢報告\n\n"
    md += (f"產出時間 {_now()}｜資料快照 {ASOF}｜"
           f"投入 **{pen['etf_count']} 檔 ETF**、共 **NT${_nf(pen['total_invest'])}**\n\n")
    if pen["unknown_tickers"]:
        md += f"> ⚠️ 已略過快照中不存在的 ETF：{'、'.join(pen['unknown_tickers'])}\n\n"
    md += "## 健檢總評\n\n"
    md += f"| 判定 | 說明 |\n|:--:|---|\n"
    md += f"| {c_icon} | {c_text} |\n| {n_icon} | {n_text} |\n| {g_icon} | {g_text} |\n\n"

    md += "## 穿透分析\n\n"
    md += (f"> **{f['stock_name']} 是你最大的單一曝險：NT${_nf(f['exposure_twd'])}，"
           f"占 {f['exposure_pct']}%。**\n\n")
    md += "**穿透後前十大個股曝險**\n\n| 個股 | 產業 | 曝險 | 占比 |\n|---|---|--:|--:|\n"
    named = [s for s in pen["stocks"] if s["stock_ticker"] != "_OTHER"][:10]
    for s in named:
        md += (f"| {s['stock_name']} | {s['sector']} "
               f"| NT${_nf(s['exposure_twd'])} | {s['exposure_pct']}% |\n")
    md += f"\n```mermaid\n{pen['diagram']}\n```\n\n"

    md += "## 重複曝險拆解\n\n"
    md += (f"| ETF | {f['stock_name']} 權重 | 投入 | 貢獻曝險 |\n|---|--:|--:|--:|\n")
    for e in f["by_etf"]:
        md += (f"| {e['etf']} {e['etf_name']} | {e['weight_pct']}% "
               f"| NT${_nf(e['invest'])} | NT${_nf(e['exposure_twd'])} |\n")
    md += (f"\n_你以為買了 {pen['etf_count']} 檔 ETF 是分散，"
           f"其實有 {f['exposure_pct']}% 壓在同一檔 {f['stock_name']}。_\n\n")

    md += _name_reality_section(nrs, nr_errs)
    md += _greenwash_section(gws, gw_errs)
    md += _sources_section()

    return {
        "title": f"組合健檢報告 {_now()}（{pen['etf_count']} 檔）",
        "markdown": md,
        "meta": {"kind": "portfolio", "as_of": ASOF, "created_at": _now(),
                 "holdings": [{"ticker": e["etf"], "amount": e["invest"]}
                              for e in f["by_etf"]]},
    }


# ───────────────────────── 報告 B：單檔透視 ─────────────────────────
def etf_report(ticker: str) -> dict:
    ticker = ticker.upper()
    pen = penetrate([{"ticker": ticker, "amount": 100000}])
    if pen.get("error"):
        return {"error": f"查無 {ticker} 持股"}
    info = next((e for e in etf_list() if e["ticker"] == ticker), {})
    etf_name = info.get("name", ticker)
    kind = "主動式" if info.get("is_active") else "被動式"

    named = [s for s in pen["stocks"] if s["stock_ticker"] != "_OTHER"]
    other_pct = round(100 - sum(s["exposure_pct"] for s in named), 1)

    sectors: dict[str, float] = {}
    for s in named:
        sectors[s["sector"]] = sectors.get(s["sector"], 0.0) + s["exposure_pct"]
    sector_rows = sorted(sectors.items(), key=lambda kv: -kv[1])[:8]

    nrs, nr_errs = _collect([ticker], name_reality)
    gws, gw_errs = _collect([ticker], greenwash)

    md = f"# 單檔 ETF 透視報告：{etf_name}（{ticker}）\n\n"
    md += f"產出時間 {_now()}｜資料快照 {ASOF}｜類型：{kind}\n\n"
    md += "## 前十大持股\n\n| 個股 | 產業 | 權重 |\n|---|---|--:|\n"
    for s in named[:10]:
        md += f"| {s['stock_name']} | {s['sector']} | {s['exposure_pct']}% |\n"
    md += (f"\n具名持股共 {round(sum(s['exposure_pct'] for s in named), 1)}%，"
           f"其餘 {other_pct}% 為未個別揭露的「其他持股」。\n\n")
    md += "## 產業分布（具名持股）\n\n| 產業 | 權重 |\n|---|--:|\n"
    for sec, w in sector_rows:
        md += f"| {sec} | {round(w, 1)}% |\n"
    md += "\n"
    md += _name_reality_section(nrs, nr_errs)
    md += _greenwash_section(gws, gw_errs)
    md += _sources_section()

    return {
        "title": f"單檔透視：{etf_name}（{ticker}）{_now()}",
        "markdown": md,
        "meta": {"kind": "etf", "as_of": ASOF, "created_at": _now(),
                 "ticker": ticker},
    }


# ─────────────────────────── self-test ───────────────────────────
def _selftest():
    print("=== report.py self-test ===\n")
    pf = [{"ticker": t, "amount": 100000}
          for t in ("0050", "006208", "00878", "00992A")]
    r = portfolio_report(pf)
    assert not r.get("error")
    assert {"title", "markdown", "meta"} <= set(r)
    md = r["markdown"]
    # hero 數字必須與 penetrate selftest 基準一致（31.1% / 124,230）
    assert "31.1%" in md and "124,230" in md, "穿透 hero 數字不一致"
    for sec in ("健檢總評", "穿透分析", "重複曝險拆解", "名實相符檢測",
                "漂綠檢測", "資料來源與免責"):
        assert sec in md, f"缺章節：{sec}"
    assert "```mermaid" in md and SLOGAN in md
    assert r["meta"]["kind"] == "portfolio" and len(r["meta"]["holdings"]) == 4
    print(f"組合健檢 OK：{r['title']}（{len(md)} chars）")

    # 無效 ticker 混入：略過並照產
    r2 = portfolio_report(pf + [{"ticker": "9999X", "amount": 50000}])
    assert "9999X" in r2["markdown"] and "31.1%" not in r2["markdown"]
    print("含無效 ticker：有列示、總額重算 OK")

    # 全部無效 → error
    assert portfolio_report([{"ticker": "9999X", "amount": 1}]).get("error")
    print("全無效 → error OK")

    e = etf_report("00881")
    assert not e.get("error")
    for sec in ("前十大持股", "產業分布", "名實相符檢測", "漂綠檢測"):
        assert sec in e["markdown"], f"缺章節：{sec}"
    assert "24.7%" in e["markdown"], "00881 5G 對齊度應為 24.7%"
    assert e["meta"]["ticker"] == "00881"
    print(f"單檔透視 OK：{e['title']}")

    assert etf_report("9999X").get("error")
    print("單檔無效 ticker → error OK")

    print("\n✅ report.py self-test 全過")


if __name__ == "__main__":
    _selftest()
```

- [ ] **Step 2: 跑 selftest**

Run: `cd demo && python3 report.py`
Expected: `✅ report.py self-test 全過`（若 assert 失敗，修 report.py 至全過）

- [ ] **Step 3: Commit**

```bash
git add demo/report.py
git commit -m "report.py：組合健檢與單檔透視兩種報告的 Markdown 產製引擎"
```

### Task 3: server.py 報告端點 + 報告櫃 CRUD

**Files:**
- Modify: `demo/server.py`（import 區、`api_name_reality` 之後加端點）
- Modify: `.gitignore`（repo 根目錄）
- Create: `demo/reports/.gitkeep`

- [ ] **Step 1: server.py 加 import（在 `from penetrate import ...` 之後）**

```python
import re
from datetime import datetime

from report import etf_report, portfolio_report
from penetrate import etf_list
```

（與既有 import 合併整理：`re`/`datetime` 放標準庫區。）

- [ ] **Step 2: 在 `api_name_reality` 端點之後、proxy 之前加端點**

```python
@app.get("/api/passport/etfs")
async def api_etfs():
    """16 檔 ETF 清單（前端報告下拉用）。"""
    return etf_list()


@app.post("/api/passport/report/portfolio")
async def api_report_portfolio(req: Request):
    """組合健檢報告。body: {holdings:[{ticker,amount}]}"""
    body = await req.json()
    holdings = body.get("holdings") or []
    if not holdings:
        raise HTTPException(400, "holdings 不可為空")
    r = portfolio_report(holdings)
    if r.get("error"):
        raise HTTPException(400, r["error"])
    return r


@app.get("/api/passport/report/etf/{ticker}")
async def api_report_etf(ticker: str):
    """單檔 ETF 透視報告。"""
    r = etf_report(ticker)
    if r.get("error"):
        raise HTTPException(404, r["error"])
    return r


# ─────────────── 報告櫃（JSON 檔存 demo/reports/）───────────────
REPORTS_DIR = ROOT / "reports"
_REPORT_ID = re.compile(r"\d{8}-\d{6}(-\d+)?")


def _report_path(report_id: str) -> Path:
    if not _REPORT_ID.fullmatch(report_id):   # 防 path traversal
        raise HTTPException(400, "report id 格式錯誤")
    return REPORTS_DIR / f"{report_id}.json"


@app.post("/api/reports")
async def save_report(req: Request):
    """儲存報告。body: {title, markdown, meta}"""
    body = await req.json()
    if not body.get("title") or not body.get("markdown"):
        raise HTTPException(400, "title 與 markdown 為必填")
    REPORTS_DIR.mkdir(exist_ok=True)
    rid = datetime.now().strftime("%Y%m%d-%H%M%S")
    n = 1
    while (REPORTS_DIR / f"{rid}.json").exists():
        rid = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{n}"
        n += 1
    (REPORTS_DIR / f"{rid}.json").write_text(json.dumps({
        "id": rid, "title": body["title"], "markdown": body["markdown"],
        "meta": body.get("meta", {}),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"id": rid}


@app.get("/api/reports")
async def list_reports():
    """報告櫃列表（新到舊）。"""
    if not REPORTS_DIR.exists():
        return []
    out = []
    for p in sorted(REPORTS_DIR.glob("*.json"), reverse=True):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            out.append({"id": d["id"], "title": d["title"],
                        "created_at": d.get("meta", {}).get("created_at", "")})
        except (json.JSONDecodeError, KeyError):
            continue
    return out


@app.get("/api/reports/{report_id}")
async def get_report(report_id: str):
    p = _report_path(report_id)
    if not p.exists():
        raise HTTPException(404, "報告不存在")
    return json.loads(p.read_text(encoding="utf-8"))


@app.delete("/api/reports/{report_id}")
async def delete_report(report_id: str):
    p = _report_path(report_id)
    if not p.exists():
        raise HTTPException(404, "報告不存在")
    p.unlink()
    return {"deleted": report_id}
```

- [ ] **Step 3: `.gitignore` 加報告櫃內容、建 `.gitkeep`**

`.gitignore` 追加：
```
demo/reports/*
!demo/reports/.gitkeep
```

```bash
mkdir -p demo/reports && touch demo/reports/.gitkeep
```

- [ ] **Step 4: 起 server 用 curl 驗證**

Run（背景起 server 後）：
```bash
cd demo && python3 server.py &   # 或既有方式啟動
curl -s localhost:8000/api/passport/etfs | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d))"
# Expected: 16
curl -s -X POST localhost:8000/api/passport/report/portfolio \
  -H 'Content-Type: application/json' \
  -d '{"holdings":[{"ticker":"0050","amount":100000},{"ticker":"006208","amount":100000},{"ticker":"00878","amount":100000},{"ticker":"00992A","amount":100000}]}' \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['title']); assert '31.1%' in d['markdown']"
# Expected: 組合健檢報告 …（4 檔）
curl -s localhost:8000/api/passport/report/etf/00881 | python3 -c "import json,sys; print(json.load(sys.stdin)['title'])"
# Expected: 單檔透視：國泰台灣5G+（00881）…
# 報告櫃 CRUD：
curl -s -X POST localhost:8000/api/reports -H 'Content-Type: application/json' \
  -d '{"title":"t","markdown":"# m","meta":{"created_at":"x"}}'
# Expected: {"id":"YYYYMMDD-HHMMSS"}
curl -s localhost:8000/api/reports          # Expected: 含上面那筆
curl -s localhost:8000/api/reports/<id>     # Expected: 完整 JSON
curl -s -X DELETE localhost:8000/api/reports/<id>   # Expected: {"deleted":...}
curl -s localhost:8000/api/reports/../../.env -o /dev/null -w "%{http_code}"  # Expected: 400/404（非 200）
```

- [ ] **Step 5: Commit**

```bash
git add demo/server.py .gitignore demo/reports/.gitkeep
git commit -m "server.py 報告端點 + 報告櫃 CRUD（demo/reports/ JSON 檔）"
```

### Task 4: 前端 — 報告按鈕、modal 預覽、報告櫃 tab

**Files:**
- Modify: `demo/index.html`
- Create: `demo/report_ui.js`
- Modify: `demo/styles.css`

- [ ] **Step 1: index.html — 左側 `provenance` 區塊之前加報告工具**

```html
        <div class="report-tools">
          <div class="holdings-head"><h3>報告</h3></div>
          <button id="gen-portfolio-report" class="report-btn primary">📋 產出組合健檢報告</button>
          <div class="etf-report-row">
            <select id="etf-report-select"></select>
            <button id="gen-etf-report" class="report-btn">單檔透視</button>
          </div>
        </div>
```

- [ ] **Step 2: index.html — 右側欄改成雙 tab（引用回鏈 / 報告櫃）**

把右側 `<aside class="panel side">` 內容改為：

```html
      <div class="side-tabs">
        <button class="side-tab active" data-tab="citations-pane">引用回鏈</button>
        <button class="side-tab" data-tab="shelf-pane">報告櫃</button>
      </div>
      <div id="citations-pane">
        <div class="panel-head"><h2>引用回鏈</h2><span class="panel-sub">EVIDENCE</span></div>
        <div id="citations">
          <p class="empty-hint">送出問題後，每則回答的證據來源會蓋章在這裡。</p>
        </div>
      </div>
      <div id="shelf-pane" class="hidden">
        <div class="panel-head"><h2>報告櫃</h2><span class="panel-sub">REPORTS</span></div>
        <div id="report-shelf"><p class="empty-hint">尚無已儲存的報告。</p></div>
      </div>
```

- [ ] **Step 3: index.html — `</main>` 之後加報告 modal，並在 `app.js` 之後載入 `report_ui.js`**

```html
  <div id="report-modal" class="report-modal hidden">
    <div class="report-modal-box">
      <div id="report-body" class="report-body"></div>
      <div class="report-actions">
        <button id="report-save">💾 儲存到報告櫃</button>
        <button id="report-download">⬇️ 下載 HTML</button>
        <button id="report-print">🖨 列印 / PDF</button>
        <button id="report-discard" class="ghost">捨棄</button>
      </div>
    </div>
  </div>
```

```html
  <script src="report_ui.js"></script>
```

- [ ] **Step 4: 建立 `demo/report_ui.js` 全檔**

```javascript
// ─────────────────────────────────────────────
// ETF 透視鏡 PASSPORT — 報告產出 / 報告櫃
// 依賴 app.js 的全域：renderMarkdown、renderMermaidIn、getActiveHoldings、
// escapeHtml、appendBotMessage
// ─────────────────────────────────────────────

const reportState = { current: null, saved: false };

async function initReportUI() {
  // 16 檔下拉
  try {
    const list = await (await fetch("/api/passport/etfs")).json();
    $("#etf-report-select").innerHTML = list
      .map((e) => `<option value="${e.ticker}">${e.ticker} ${e.name}</option>`)
      .join("");
  } catch (e) {
    console.warn("etf list fetch failed", e);
  }

  $("#gen-portfolio-report").addEventListener("click", genPortfolioReport);
  $("#gen-etf-report").addEventListener("click", () =>
    genEtfReport($("#etf-report-select").value)
  );

  // 右側欄 tab 切換
  $$(".side-tab").forEach((btn) =>
    btn.addEventListener("click", () => {
      $$(".side-tab").forEach((b) => b.classList.toggle("active", b === btn));
      $("#citations-pane").classList.toggle("hidden", btn.dataset.tab !== "citations-pane");
      $("#shelf-pane").classList.toggle("hidden", btn.dataset.tab !== "shelf-pane");
      if (btn.dataset.tab === "shelf-pane") refreshShelf();
    })
  );

  // modal 動作列
  $("#report-save").addEventListener("click", saveCurrentReport);
  $("#report-download").addEventListener("click", downloadCurrentReport);
  $("#report-print").addEventListener("click", printCurrentReport);
  $("#report-discard").addEventListener("click", closeReportModal);
  $("#report-modal").addEventListener("click", (e) => {
    if (e.target === $("#report-modal")) closeReportModal();
  });

  refreshShelf();
}

// ────────────────────────── 產報告 ──────────────────────────
async function genPortfolioReport() {
  const holdings = getActiveHoldings();
  if (!holdings.length) {
    appendBotMessage("⚠️ 請先在左側輸入持股（或點 Persona 一鍵載入），再產出組合健檢報告。", []);
    return;
  }
  const btn = $("#gen-portfolio-report");
  btn.disabled = true; btn.textContent = "⏳ 產製中…";
  try {
    const r = await fetch("/api/passport/report/portfolio", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ holdings }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || r.status);
    await openReportModal(d, { savedView: false });
  } catch (err) {
    appendBotMessage(`⚠️ 報告產製失敗：${err.message}`, []);
  } finally {
    btn.disabled = false; btn.textContent = "📋 產出組合健檢報告";
  }
}

async function genEtfReport(ticker) {
  if (!ticker) return;
  const btn = $("#gen-etf-report");
  btn.disabled = true; btn.textContent = "⏳…";
  try {
    const r = await fetch(`/api/passport/report/etf/${encodeURIComponent(ticker)}`);
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || r.status);
    await openReportModal(d, { savedView: false });
  } catch (err) {
    appendBotMessage(`⚠️ 報告產製失敗：${err.message}`, []);
  } finally {
    btn.disabled = false; btn.textContent = "單檔透視";
  }
}

// ────────────────────────── modal ──────────────────────────
async function openReportModal(report, { savedView }) {
  reportState.current = report;
  reportState.saved = savedView;
  const body = $("#report-body");
  body.innerHTML = renderMarkdown(report.markdown);
  $("#report-modal").classList.remove("hidden");
  await renderMermaidIn(body);   // modal 可見後再 render，Mermaid 量測才正確
  $("#report-save").textContent = savedView ? "✓ 已在報告櫃" : "💾 儲存到報告櫃";
  $("#report-save").disabled = savedView;
  body.scrollTop = 0;
}

function closeReportModal() {
  $("#report-modal").classList.add("hidden");
  reportState.current = null;
}

async function saveCurrentReport() {
  const rep = reportState.current;
  if (!rep || reportState.saved) return;
  try {
    const r = await fetch("/api/reports", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: rep.title, markdown: rep.markdown, meta: rep.meta }),
    });
    if (!r.ok) throw new Error(r.status);
    reportState.saved = true;
    $("#report-save").textContent = "✓ 已儲存";
    $("#report-save").disabled = true;
    refreshShelf();
  } catch (err) {
    $("#report-save").textContent = `⚠️ 儲存失敗（${err.message}）`;
  }
}

// 下載 self-contained HTML（Mermaid 已是 SVG，無外部依賴）
function standaloneHtml(rep) {
  return `<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">
<title>${escapeHtml(rep.title)}</title>
<style>
body{font-family:"PingFang TC","Noto Sans TC",sans-serif;max-width:860px;
margin:2rem auto;padding:0 1.5rem;color:#2c261a;line-height:1.7}
table{border-collapse:collapse;width:100%;margin:.8rem 0}
th,td{border:1px solid #d8cfae;padding:.4rem .6rem;font-size:.92rem}
th{background:#f3ecd9;text-align:left}
blockquote{border-left:4px solid #b3a36f;background:#faf6ea;margin:.8rem 0;
padding:.5rem 1rem}
h1,h2{border-bottom:2px solid #e4dbc0;padding-bottom:.3rem}
svg{max-width:100%;height:auto}
@media print{body{margin:0}}
</style></head><body>${$("#report-body").innerHTML}</body></html>`;
}

function downloadCurrentReport() {
  const rep = reportState.current;
  if (!rep) return;
  const blob = new Blob([standaloneHtml(rep)], { type: "text/html;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `${rep.title.replace(/[\\/:*?"<>|\s]+/g, "_")}.html`;
  a.click();
  URL.revokeObjectURL(a.href);
}

function printCurrentReport() {
  const rep = reportState.current;
  if (!rep) return;
  const w = window.open("", "_blank");
  w.document.write(standaloneHtml(rep));
  w.document.close();
  w.focus();
  w.print();
}

// ────────────────────────── 報告櫃 ──────────────────────────
async function refreshShelf() {
  const shelf = $("#report-shelf");
  try {
    const list = await (await fetch("/api/reports")).json();
    if (!list.length) {
      shelf.innerHTML = `<p class="empty-hint">尚無已儲存的報告。</p>`;
      return;
    }
    shelf.innerHTML = "";
    for (const item of list) {
      const card = document.createElement("div");
      card.className = "shelf-card";
      card.innerHTML = `
        <button class="shelf-open">
          <span class="shelf-title">${escapeHtml(item.title)}</span>
          <span class="shelf-time">${escapeHtml(item.created_at)}</span>
        </button>
        <button class="shelf-del" title="刪除">×</button>`;
      card.querySelector(".shelf-open").addEventListener("click", async () => {
        const r = await fetch(`/api/reports/${item.id}`);
        if (r.ok) await openReportModal(await r.json(), { savedView: true });
      });
      card.querySelector(".shelf-del").addEventListener("click", async () => {
        await fetch(`/api/reports/${item.id}`, { method: "DELETE" });
        refreshShelf();
      });
      shelf.appendChild(card);
    }
  } catch (e) {
    shelf.innerHTML = `<p class="empty-hint">⚠️ 報告櫃載入失敗。</p>`;
  }
}

initReportUI();
```

- [ ] **Step 5: styles.css 追加（檔尾）**

```css
/* ───────────── 報告功能 ───────────── */
.report-tools { margin-top: .9rem; }
.report-btn {
  width: 100%; padding: .5rem .6rem; border: 1.5px solid #b3a36f;
  border-radius: 8px; background: #fdfaf1; cursor: pointer;
  font-weight: 600; color: #4a3f28;
}
.report-btn.primary { background: #f0e6c8; }
.report-btn:hover { background: #ece1bd; }
.report-btn:disabled { opacity: .6; cursor: wait; }
.etf-report-row { display: flex; gap: .4rem; margin-top: .45rem; }
.etf-report-row select {
  flex: 1; min-width: 0; border: 1.5px solid #d8cfae; border-radius: 8px;
  padding: .35rem .4rem; background: #fff; font-size: .85rem;
}
.etf-report-row .report-btn { width: auto; white-space: nowrap; }

.side-tabs { display: flex; gap: .3rem; margin-bottom: .6rem; }
.side-tab {
  flex: 1; padding: .35rem 0; border: 1.5px solid #d8cfae; border-radius: 8px;
  background: #faf6ea; cursor: pointer; font-weight: 600; color: #6b614a;
}
.side-tab.active { background: #f0e6c8; border-color: #b3a36f; color: #2c261a; }

.shelf-card {
  display: flex; align-items: stretch; gap: .3rem; margin-bottom: .5rem;
}
.shelf-card .shelf-open {
  flex: 1; text-align: left; border: 1.5px solid #d8cfae; border-radius: 8px;
  background: #fdfaf1; padding: .45rem .6rem; cursor: pointer;
}
.shelf-card .shelf-open:hover { background: #f3ecd9; }
.shelf-title { display: block; font-weight: 600; font-size: .85rem; }
.shelf-time { display: block; font-size: .72rem; color: #8a7d5c; }
.shelf-del {
  border: 1.5px solid #d8cfae; border-radius: 8px; background: #fdfaf1;
  cursor: pointer; padding: 0 .55rem; color: #a33;
}
.shelf-del:hover { background: #f6e3e0; }

.report-modal {
  position: fixed; inset: 0; z-index: 50; display: flex;
  align-items: center; justify-content: center;
  background: rgba(44, 38, 26, .55);
}
.report-modal.hidden { display: none; }
.report-modal-box {
  width: min(880px, 92vw); height: min(86vh, 980px);
  display: flex; flex-direction: column;
  background: #fffdf6; border: 2px solid #b3a36f; border-radius: 14px;
  box-shadow: 0 18px 50px rgba(44, 38, 26, .35); overflow: hidden;
}
.report-body { flex: 1; overflow-y: auto; padding: 1.4rem 1.8rem; }
.report-actions {
  display: flex; gap: .5rem; padding: .7rem 1rem;
  border-top: 1.5px solid #e4dbc0; background: #faf6ea;
}
.report-actions button {
  padding: .45rem .8rem; border: 1.5px solid #b3a36f; border-radius: 8px;
  background: #fdfaf1; cursor: pointer; font-weight: 600;
}
.report-actions button:hover:not(:disabled) { background: #ece1bd; }
.report-actions button:disabled { opacity: .65; cursor: default; }
.report-actions .ghost { margin-left: auto; border-color: #d8cfae; color: #8a7d5c; }
.hidden { display: none; }
```

注意：app.js 既有 `showCitations` 操作 `#citations`，上面結構保留了該 id（包在 `#citations-pane` 內），**不需要動 app.js**。

- [ ] **Step 6: 瀏覽器手動驗證（server 跑著）**

打開 `http://localhost:8000`：
1. 點「主題追熱」persona → 「產出組合健檢報告」→ modal 出現，含三徽章表、穿透表、Mermaid 圖、名實表、漂綠表、slogan
2. 「儲存到報告櫃」→ 變「✓ 已儲存」；切右側「報告櫃」tab → 出現該筆；點開重看 OK；刪除 OK
3. 「下載 HTML」→ 開啟下載檔，表格與 SVG 圖完整顯示
4. 「捨棄」與點背景 → modal 關閉
5. 下拉選 00881 →「單檔透視」→ 前十大持股、產業分布、名實 24.7% 正確
6. 清空持股 → 「產出組合健檢報告」→ 聊天區出現提示，不開 modal
7. 引用回鏈 tab 原功能不受影響（問一題 Q-A 確認）

- [ ] **Step 7: Commit**

```bash
git add demo/index.html demo/report_ui.js demo/styles.css
git commit -m "前端報告功能：產出按鈕、modal 預覽、報告櫃 tab、下載/列印"
```

### Task 5: 文件更新 + 最終 QA

**Files:**
- Modify: `demo/README.md`（功能清單、檔案表、checklist）

- [ ] **Step 1: README.md 更新**

功能清單加一條：
```markdown
- **報告產出** — 一鍵「組合健檢報告」/「單檔透視報告」（純本地計算、斷網可演）；modal 預覽後可儲存到報告櫃（`reports/`）、下載 self-contained HTML、列印成 PDF
```
檔案表加兩列：
```markdown
| `report.py` | 報告 Markdown 產製引擎（重用 penetrate.py） |
| `report_ui.js` | 報告按鈕 / modal / 報告櫃前端邏輯 |
```
決賽前 checklist 加一條：
```markdown
- [ ] 報告功能驗證：主題追熱 persona 產健檢報告 → 儲存 → 報告櫃重開 → 下載 HTML
```

- [ ] **Step 2: 三 persona 各產一份健檢報告 + 兩檔單檔報告，抽查數字與聊天回答一致**

Run: 瀏覽器逐一操作；另跑 `cd demo && python3 penetrate.py && python3 report.py` 確認回歸全綠。

- [ ] **Step 3: Commit**

```bash
git add demo/README.md
git commit -m "README：報告產出功能說明與決賽 checklist"
```

---

## Self-Review 紀錄

- Spec 覆蓋：報告 A 六章節（Task 2 portfolio_report）、報告 B（etf_report）、後端端點與報告櫃（Task 3）、前端按鈕/modal/報告櫃 tab/下載/列印（Task 4）、.gitignore（Task 3 Step 3）、錯誤處理（unknown ticker 列示、全無效 error、404、儲存失敗警告）、selftest、手動 QA（Task 5）— 全有對應。
- 型別/命名一致：`{title, markdown, meta}` 貫穿後端與前端；`#citations` id 保留使 app.js 免改。
- 無占位符。
