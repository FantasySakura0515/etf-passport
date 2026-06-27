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


def _primary_theme(d: dict) -> dict | None:
    """ETF 的主判定主題 = 第一個有標記資料的標榜主題；全無標記則不判定。"""
    return next((t for t in d["themes"] if t.get("has_tag_data")), None)


def _name_badge(nrs: list[dict]) -> tuple[str, str]:
    """nrs: 各 ETF 的 name_reality() 成功結果。以各檔主判定主題對齊度的最低值判定；
    無標記資料的主題（如「台灣大型權值」）不列入判定。"""
    judgeable = [d for d in nrs if _primary_theme(d)]
    if not judgeable:
        return "⚪", "名實相符：標榜主題皆無個股標記資料，不判定"
    worst = min(judgeable, key=lambda d: _primary_theme(d)["aligned_pct"])
    t0 = _primary_theme(worst)
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
                aligned = (f"{t['aligned_pct']}%" if t.get("has_tag_data")
                           else "—（無標記資料，不判定）")
                md += f"| {etf_cell} | {t['claimed_theme']} | {aligned} | {named} |\n"
        md += "\n"
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
        f"---\n\nETF 透視鏡 PASSPORT · 持股穿透報告\n"
    )


def _collect(etfs: list[str], fn) -> tuple[list[dict], list[str]]:
    """對每檔 ETF 跑 fn，分離成功結果與出錯檔（單檔出錯不中斷報告）。"""
    oks, errs = [], []
    for t in etfs:
        d = fn(t)
        if d.get("error"):
            errs.append(t)
        else:
            oks.append(d)
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

    md = "# 我的 ETF 組合健檢報告\n\n"
    md += (f"產出時間 {_now()}｜資料快照 {ASOF}｜"
           f"投入 **{pen['etf_count']} 檔 ETF**、共 **NT${_nf(pen['total_invest'])}**\n\n")
    if pen["unknown_tickers"]:
        md += f"> ⚠️ 已略過快照中不存在的 ETF：{'、'.join(pen['unknown_tickers'])}\n\n"
    md += "## 健檢總評\n\n"
    md += "| 判定 | 說明 |\n|:--:|---|\n"
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
    md += f"| ETF | {f['stock_name']} 權重 | 投入 | 貢獻曝險 |\n|---|--:|--:|--:|\n"
    for e in f["by_etf"]:
        md += (f"| {e['etf']} {e['etf_name']} | {e['weight_pct']}% "
               f"| NT${_nf(e['invest'])} | NT${_nf(e['exposure_twd'])} |\n")
    md += "\n"

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
    assert "```mermaid" in md and "ETF 透視鏡 PASSPORT" in md
    # 標語類編按已移除，報告維持事實＋免責語氣
    assert "名字是行銷" not in md and "你以為" not in md, "報告殘留標語"
    assert r["meta"]["kind"] == "portfolio" and len(r["meta"]["holdings"]) == 4
    print(f"組合健檢 OK：{r['title']}（{len(md)} chars）")

    # 無效 ticker 混入：略過並照產
    r2 = portfolio_report(pf + [{"ticker": "9999X", "amount": 50000}])
    assert "9999X" in r2["markdown"] and "31.1%" in r2["markdown"]
    print("含無效 ticker：有列示、有效檔照算 OK")

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
