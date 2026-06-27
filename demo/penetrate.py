# -*- coding: utf-8 -*-
"""ETF 透視鏡 — 我方後端穿透計算引擎（不經 EAP LLM，數字 100% 可控）。

背景：實測 EAP chat 自動產的 Cypher 不可靠（ticker 存成 float、LLM 會無視指令
重寫並丟掉金額參數），因此所有「數字型」答案改由本模組直接從快照 CSV 計算；
EAP chat 只負責質化/Vector 敘述。詳見 memory `project_eap_cypher_unreliable`。

資料來源（單一真實來源，見 CLAUDE.md）：data/snapshot_2026-06-05/
"""
from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
from typing import Optional

DATA = Path(__file__).resolve().parent.parent / "data" / "snapshot_2026-06-05"
# 持股為真實成分股(etfinfo.tw,經元大官網直抓交叉驗證),as-of 2026-06-05;
# 每檔權重不足 100% 的部分以 _OTHER 列補足。
ASOF = "2026-06-05"


@lru_cache(maxsize=1)
def _load():
    """讀所有快照 CSV，回傳記憶體結構。lru_cache 確保只讀一次。"""
    holdings: dict[str, list[dict]] = {}
    # 同一檔個股在不同 ETF 名單寫法不一（台積電/台灣積體、聯電/聯華電子），
    # 輸出統一用最短寫法，避免表格內名稱忽長忽短
    canon: dict[str, str] = {}
    with open(DATA / "holdings_2026-06-05.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        tk, nm = r["stock_ticker"], r["stock_name"]
        if tk not in canon or len(nm) < len(canon[tk]):
            canon[tk] = nm
    for r in rows:
        holdings.setdefault(r["etf_ticker"], []).append({
            "stock_ticker": r["stock_ticker"],
            "stock_name": canon[r["stock_ticker"]],
            "sector": r["sector"],
            "weight_pct": float(r["weight_pct"]),
        })

    meta = {}
    with open(DATA / "etf_metadata.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            meta[r["ticker"]] = r

    esg = {}
    p = DATA / "stock_esg.csv"
    if p.exists():
        with open(p, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                esg[r["stock_ticker"]] = float(r["esg_score"])

    # BELONGS_TO_THEME: (stock_ticker, theme) -> weight
    belong: dict[tuple[str, str], float] = {}
    p = DATA / "stock_themes.csv"
    if p.exists():
        with open(p, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                belong[(r["stock_ticker"], r["theme_name"])] = float(r["weight"])

    # LABELED_AS: etf -> [claimed themes]
    claimed: dict[str, list[str]] = {}
    p = DATA / "etf_claimed_themes.csv"
    if p.exists():
        with open(p, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                claimed.setdefault(r["etf_ticker"], []).append(r["theme_name"])

    return {"holdings": holdings, "meta": meta, "esg": esg,
            "belong": belong, "claimed": claimed}


def _name(ticker: str) -> str:
    return _load()["meta"].get(ticker, {}).get("name", ticker)


def etf_list() -> list[dict]:
    """16 檔 ETF 清單（給前端下拉與報告封面用）。"""
    return [{"ticker": t, "name": m["name"],
             "is_active": str(m.get("is_active", "")).lower() == "true"}
            for t, m in _load()["meta"].items()]


def penetrate(portfolio: list[dict], focus: str = "2330") -> dict:
    """對一組持股做穿透。

    portfolio: [{"ticker": "0050", "amount": 100000}, ...]
    focus:     要凸顯的個股 ticker（預設台積電 2330）

    回傳：總投入、各個股穿透曝險（金額+占比，降序）、focus 個股 hero、各 ETF 對 focus 的貢獻。
    """
    db = _load()
    holdings = db["holdings"]
    cleaned = []
    for h in portfolio:
        try:
            amount = float(h.get("amount", 0))
        except (TypeError, ValueError):
            amount = 0.0
        cleaned.append({"ticker": str(h.get("ticker", "")).upper(), "amount": amount})

    total_input = sum(h["amount"] for h in cleaned)
    if total_input <= 0:
        return {"error": "總投入金額需大於 0"}

    by_stock: dict[str, dict] = {}
    focus_by_etf = []
    unknown = []
    total_valid = 0.0

    for pos in cleaned:
        tk, amt = pos["ticker"], float(pos["amount"])
        rows = holdings.get(tk)
        if not rows:
            unknown.append(tk)
            continue
        total_valid += amt
        focus_w = 0.0
        for h in rows:
            twd = amt * h["weight_pct"] / 100.0
            s = by_stock.setdefault(h["stock_ticker"], {
                "stock_ticker": h["stock_ticker"], "stock_name": h["stock_name"],
                "sector": h["sector"], "exposure_twd": 0.0})
            s["exposure_twd"] += twd
            if h["stock_ticker"] == focus:
                focus_w = h["weight_pct"]
        # 不持有 focus 的 ETF 也要列出（weight 0）— 「以為有分散、其實不持有」是重點洞察
        focus_by_etf.append({
            "etf": tk, "etf_name": _name(tk),
            "weight_pct": round(focus_w, 2),
            "invest": amt, "exposure_twd": round(amt * focus_w / 100.0)})

    if total_valid <= 0:
        return {"error": f"查無可計算 ETF：{', '.join(unknown)}"}

    stocks = []
    for s in by_stock.values():
        s["exposure_twd"] = round(s["exposure_twd"])
        s["exposure_pct"] = round(s["exposure_twd"] / total_valid * 1000) / 10.0
        stocks.append(s)
    # 具名個股在前、_OTHER 殿後，皆按曝險降序
    stocks.sort(key=lambda x: (x["stock_ticker"] == "_OTHER", -x["exposure_twd"]))

    focus_row = next((s for s in stocks if s["stock_ticker"] == focus), None)
    focus_name = _name_stock(focus, stocks)
    by_etf = sorted(focus_by_etf, key=lambda x: -x["weight_pct"])
    return {
        "as_of": ASOF,
        "total_invest": total_valid,
        "total_input": total_input,
        "etf_count": len(cleaned) - len(unknown),
        "input_etf_count": len(cleaned),
        "stocks": stocks,
        "unknown_tickers": unknown,
        "focus": {
            "stock_ticker": focus,
            "stock_name": focus_name,
            "exposure_twd": focus_row["exposure_twd"] if focus_row else 0,
            "exposure_pct": focus_row["exposure_pct"] if focus_row else 0.0,
            "by_etf": by_etf,
        },
        "diagram": _diagram(by_etf, focus_name,
                            focus_row["exposure_twd"] if focus_row else 0,
                            focus_row["exposure_pct"] if focus_row else 0.0),
    }


def _diagram(by_etf: list[dict], focus_name: str,
             focus_twd: int, focus_pct: float) -> str:
    """Mermaid graph LR：多檔 ETF 殊途同歸匯入同一檔 focus 個股（穩定、可靠渲染）。
    不持有 focus 的 ETF 用虛線 0% 表示 — 視覺化「加它沒有分散效果」。"""
    lines = ["graph LR"]
    lines.append(f'  T(("{focus_name}<br/>NT${focus_twd:,}<br/>{focus_pct}%"))')
    for i, e in enumerate(by_etf):
        arrow = "-->" if e["weight_pct"] > 0 else "-.->"
        label = f'{e["weight_pct"]}%' if e["weight_pct"] > 0 else "0%（不持有）"
        lines.append(f'  E{i}["{e["etf"]}<br/>{e["etf_name"]}"] {arrow}|"{label}"| T')
    lines.append("  style T fill:#fde68a,stroke:#b45309,stroke-width:3px")
    return "\n".join(lines)


def _name_stock(ticker, stocks):
    for s in stocks:
        if s["stock_ticker"] == ticker:
            return s["stock_name"]
    return ticker


def focus_ranking(focus: str = "2330", limit: int = 5,
                  active_only: bool = False, cap: Optional[float] = None) -> dict:
    """ETF 對 focus 個股的持股權重排名。active_only=True 時限主動式 ETF。"""
    db = _load()
    meta, holdings = db["meta"], db["holdings"]
    rows = []
    focus_name = focus
    for tk, m in meta.items():
        is_active = str(m.get("is_active", "")).lower() == "true"
        if active_only and not is_active:
            continue
        for h in holdings.get(tk, []):
            if h["stock_ticker"] == focus:
                focus_name = h["stock_name"]
                row = {
                    "etf": tk, "etf_name": m["name"],
                    "weight_pct": round(h["weight_pct"], 2),
                    "is_active": is_active,
                }
                if cap is not None:
                    row["room_to_cap_pct"] = round(cap - h["weight_pct"], 2)
                rows.append(row)
                break
    rows.sort(key=lambda x: -x["weight_pct"])
    return {
        "as_of": ASOF, "focus": focus, "focus_name": focus_name,
        "active_only": active_only, "cap_pct": cap, "ranking": rows[:limit],
    }


def active_focus_ranking(focus: str = "2330", limit: int = 5,
                         cap: float = 25.0) -> dict:
    """主動式 ETF 對 focus 個股的持股權重排名，附距單一持股上限的空間。"""
    return focus_ranking(focus=focus, limit=limit, active_only=True, cap=cap)


# ─────────────────────── Q-F 看好產業選 ETF ───────────────────────
# 傘狀詞：一個關鍵詞聚合多個細產業（sector 欄 31 類，分類見
# data/snapshot_2026-06-05/backfill_sectors.py 與 AI_GENERATED_PROMPTS.md §5）
SECTOR_GROUPS = {
    "半導體": ["晶圓代工", "IC設計", "記憶體", "封測", "半導體設備材料"],
    "電子零組件": ["被動元件", "PCB", "散熱", "連接器線材", "電源供應",
                "光電顯示", "其他電子"],
}

# 同義詞 → (kind, 正式名)。kind: sector=單一細產業 / group=傘狀詞 / theme=主題標籤
SECTOR_ALIASES = {
    "AI": ("theme", "AI供應鏈"), "人工智慧": ("theme", "AI供應鏈"),
    "5G": ("theme", "5G通訊"), "ESG": ("theme", "ESG永續"),
    "永續": ("theme", "ESG永續"), "高息": ("theme", "高股息"),
    "股息": ("theme", "高股息"), "科技": ("theme", "科技"),
    "晶片設計": ("sector", "IC設計"), "DRAM": ("sector", "記憶體"),
    "NAND": ("sector", "記憶體"), "封裝": ("sector", "封測"),
    "半導體設備": ("sector", "半導體設備材料"),
    "MLCC": ("sector", "被動元件"), "載板": ("sector", "PCB"),
    "印刷電路板": ("sector", "PCB"), "銅箔基板": ("sector", "PCB"),
    "面板": ("sector", "光電顯示"), "顯示器": ("sector", "光電顯示"),
    "光學": ("sector", "光學鏡頭"), "網通": ("sector", "網通設備"),
    "光通訊": ("sector", "網通設備"), "連接器": ("sector", "連接器線材"),
    "電源": ("sector", "電源供應"), "電池": ("sector", "電源供應"),
    "伺服器": ("sector", "電子代工"), "代工": ("sector", "電子代工"),
    "通路": ("sector", "電子通路"), "電信": ("sector", "電信服務"),
    "金控": ("sector", "金融"), "銀行": ("sector", "金融"),
    "海運": ("sector", "航運"), "航空": ("sector", "航運"),
    "石化": ("sector", "塑化"), "塑膠": ("sector", "塑化"),
    "營建": ("sector", "水泥營建"), "水泥": ("sector", "水泥營建"),
    "紡織": ("sector", "紡織製鞋"), "製鞋": ("sector", "紡織製鞋"),
    "車用": ("sector", "汽車"), "機械": ("sector", "機械自動化"),
    "自動化": ("sector", "機械自動化"), "機器人": ("sector", "機械自動化"),
    "重電": ("sector", "重電綠能"), "綠能": ("sector", "重電綠能"),
    "生技": ("sector", "生技醫療"), "醫療": ("sector", "生技醫療"),
}

# 不開放查詢的殘差類別（「其他」對使用者沒有意義）
_UNQUERYABLE = {"其他", "其他電子"}


def _sector_vocab() -> dict[str, tuple[str, str]]:
    """關鍵詞 → (kind, 正式名)。含細產業本名、傘狀詞、主題本名、同義詞。"""
    db = _load()
    vocab: dict[str, tuple[str, str]] = {}
    sectors = {h["sector"] for rows in db["holdings"].values() for h in rows
               if h["sector"] and h["sector"] not in _UNQUERYABLE}
    for s in sectors:
        vocab[s] = ("sector", s)
    for g in SECTOR_GROUPS:
        vocab[g] = ("group", g)
    for (_, theme) in db["belong"]:
        # 與 sector/group 同名時讓 sector/group 優先（覆蓋面較完整）
        vocab.setdefault(theme, ("theme", theme))
    vocab.update(SECTOR_ALIASES)
    return vocab


def extract_sector_keyword(question: str) -> Optional[tuple[str, str, str]]:
    """從問題抓產業關鍵詞，回 (命中詞, kind, 正式名)；長詞優先避免誤判。"""
    q = question.upper()
    for kw in sorted(_sector_vocab(), key=len, reverse=True):
        if kw.upper() in q:
            kind, name = _sector_vocab()[kw]
            return kw, kind, name
    return None


def supported_sector_keywords() -> list[str]:
    """給前端顯示「目前支援的產業詞」用（細產業 + 傘狀詞 + 主題）。"""
    vocab = _sector_vocab()
    return sorted({name for (_, name) in vocab.values()})


def sector_ranking(question: str, limit: int = 5) -> dict:
    """Q-F：看好某產業/主題 → 16 檔 ETF 依「持股對齊該產業的加權比重」排名。

    sector/group → 直接加總 holdings 該細產業權重；
    theme → 權重 × stock_themes 的 BELONGS_TO_THEME 對齊度（涵蓋檔數有限，須揭露）。
    """
    db = _load()
    hit = extract_sector_keyword(question)
    if not hit:
        return {"error": "no_keyword",
                "supported": supported_sector_keywords()}
    kw, kind, name = hit
    members = (SECTOR_GROUPS[name] if kind == "group" else [name])

    theme_stocks = ({tk for (tk, th) in db["belong"] if th == name}
                    if kind == "theme" else set())

    ranking = []
    for etf, m in db["meta"].items():
        rows = db["holdings"].get(etf, [])
        contribs = []
        for h in rows:
            if h["stock_ticker"] == "_OTHER":
                continue
            if kind == "theme":
                w = h["weight_pct"] * db["belong"].get((h["stock_ticker"], name), 0.0)
            else:
                w = h["weight_pct"] if h["sector"] in members else 0.0
            if w > 0:
                contribs.append({"stock_name": h["stock_name"],
                                 "contrib_pct": round(w, 2)})
        contribs.sort(key=lambda x: -x["contrib_pct"])
        aligned = sum(c["contrib_pct"] for c in contribs)
        ranking.append({
            "etf": etf, "etf_name": m["name"],
            "is_active": str(m.get("is_active", "")).lower() == "true",
            "aligned_pct": round(aligned, 1),
            "top_stocks": contribs[:3],
        })
    ranking.sort(key=lambda x: -x["aligned_pct"])
    return {
        "as_of": ASOF, "keyword": kw, "kind": kind, "name": name,
        "members": members if kind != "theme" else [],
        "theme_stock_count": len(theme_stocks),
        "etf_total": len(ranking),
        "ranking": ranking[:limit],
    }


def greenwash(etf_ticker: str) -> dict:
    """Q3 漂綠檢測：ETF 具名持股的加權 ESG vs 全市場平均。"""
    db = _load()
    esg, holdings = db["esg"], db["holdings"]
    if not esg:
        return {"error": "尚無 ESG 資料（stock_esg.csv）"}
    rows = holdings.get(etf_ticker)
    if not rows:
        return {"error": f"查無 {etf_ticker} 持股"}
    num = den = 0.0
    for h in rows:
        sc = esg.get(h["stock_ticker"])
        if sc is not None:
            num += h["weight_pct"] * sc
            den += h["weight_pct"]
    market_avg = sum(esg.values()) / len(esg)
    weighted = num / den if den else 0.0
    return {
        "etf": etf_ticker, "etf_name": _name(etf_ticker),
        "claimed_themes": db["claimed"].get(etf_ticker, []),
        "weighted_esg": round(weighted, 1),
        "market_avg_esg": round(market_avg, 1),
        "esg_premium": round(weighted - market_avg, 1),
        "evaluable_weight_pct": round(den, 1),
        "unevaluable_weight_pct": round(100 - den, 1),
    }


def name_reality(etf_ticker: str) -> dict:
    """Q1 名實相符：ETF 標榜主題 vs 持股實際對齊該主題的權重。"""
    db = _load()
    holdings, belong, claimed = db["holdings"], db["belong"], db["claimed"]
    rows = holdings.get(etf_ticker)
    themes = claimed.get(etf_ticker, [])
    if not rows or not themes:
        return {"error": f"{etf_ticker} 無持股或無標榜主題"}
    out = []
    named = sum(h["weight_pct"] for h in rows if h["stock_ticker"] != "_OTHER")
    # stock_themes.csv 沒標記的主題（如「台灣大型權值」「主動選股」）對齊度
    # 結構性為 0 — 是資料覆蓋缺口、不是名實落差，回傳 has_tag_data 讓呼叫端區分
    tagged_themes = {th for (_, th) in belong}
    for theme in themes:
        aligned = sum(h["weight_pct"] * belong.get((h["stock_ticker"], theme), 0.0)
                      for h in rows)
        out.append({"claimed_theme": theme,
                    "aligned_pct": round(aligned, 1),
                    "has_tag_data": theme in tagged_themes})
    return {
        "etf": etf_ticker, "etf_name": _name(etf_ticker),
        "named_weight_pct": round(named, 1),
        "other_weight_pct": round(100 - named, 1),
        "themes": out,
    }


# ─────────────────────────── self-test ───────────────────────────
def _selftest():
    print("=== penetrate.py self-test ===\n")
    pf = [{"ticker": t, "amount": 100000}
          for t in ("0050", "006208", "00878", "00992A")]
    r = penetrate(pf)
    f = r["focus"]
    print(f"Hero 穿透：4 檔各 10 萬 → 台積電曝險 {f['exposure_twd']:,} 元"
          f"（{f['exposure_pct']}%）")
    for e in f["by_etf"]:
        print(f"   {e['etf']:7} {e['etf_name']:14} TSMC {e['weight_pct']:>5}%"
              f" → {e['exposure_twd']:>7,}")
    assert f["exposure_pct"] == 31.1, f"預期 31.1%，得到 {f['exposure_pct']}"
    assert f["exposure_twd"] == 124230, f"預期 124230，得到 {f['exposure_twd']}"
    # 4 檔都要列出（含不持有台積電的 00878，weight 0）
    assert len(f["by_etf"]) == 4, f"by_etf 應含全部 4 檔，得到 {len(f['by_etf'])}"
    assert any(e["etf"] == "00878" and e["weight_pct"] == 0 for e in f["by_etf"])
    print("   ✅ 31.1% / 124,230 一致；4 檔全列（含 00878 0%）\n")

    print("前 3 大穿透曝險個股：")
    for s in r["stocks"][:3]:
        print(f"   {s['stock_name']:6} {s['exposure_pct']:>5}%  {s['exposure_twd']:>8,}")

    print("\nQ1 名實 — 00881 國泰台灣5G+：")
    nr = name_reality("00881")
    for t in nr["themes"]:
        print(f"   標榜「{t['claimed_theme']}」實際對齊 {t['aligned_pct']}%"
              f"（具名 {nr['named_weight_pct']}%）")
    assert nr["themes"][0]["aligned_pct"] == 24.7

    print("\n主動式 ETF — 台積電持股排名（真實，主動組皆 ≤10%，無逼近上限情形）：")
    ar = active_focus_ranking()
    for row in ar["ranking"]:
        print(f"   {row['etf']:7} {row['etf_name']:14} {row['weight_pct']:>5}%")
    assert ar["ranking"][0]["etf"] == "00981A" and ar["ranking"][0]["weight_pct"] == 10.03

    print("\nQ3 漂綠 — 00878 國泰永續高股息：")
    gw = greenwash("00878")
    print(f"   加權 ESG {gw['weighted_esg']} vs 市場 {gw['market_avg_esg']}"
          f"（溢價 {gw['esg_premium']:+}）；可評估 {gw['evaluable_weight_pct']}%")
    # 註：stock_esg.csv 仍為有限樣本，真實持股換入後可評估權重降至 ~39%，此處僅作回歸基準。
    assert gw["weighted_esg"] == 73.9 and gw["esg_premium"] == -1.4

    print("\nQ-F 看好產業選 ETF：")
    for q in ("我看好被動元件，該買哪檔 ETF？", "看好半導體", "我看好 AI",
              "重電是不是要起飛了，買哪檔？"):
        sr = sector_ranking(q)
        top = sr["ranking"][0]
        kind_label = {"sector": "細產業", "group": "傘狀", "theme": "主題"}[sr["kind"]]
        print(f"   「{sr['keyword']}」({kind_label} {sr['name']}) → "
              f"{top['etf']} {top['etf_name']} {top['aligned_pct']}%")
    assert sector_ranking("看好半導體")["kind"] == "group"
    assert sector_ranking("我看好 AI")["name"] == "AI供應鏈"
    assert "supported" in sector_ranking("我看好元宇宙")  # 無此標籤 → 回支援清單
    # 「晶圓代工」要長詞優先，不能被「代工」吃掉
    assert sector_ranking("看好晶圓代工")["name"] == "晶圓代工"

    lst = etf_list()
    assert len(lst) == 16 and {"ticker", "name", "is_active"} <= set(lst[0])
    print(f"\netf_list：{len(lst)} 檔 OK")

    print("\n✅ 全部 self-test 通過")


if __name__ == "__main__":
    _selftest()
