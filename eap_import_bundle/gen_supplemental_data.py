# -*- coding: utf-8 -*-
"""產生補充資料：ESG 評分 / 主題標籤 / 受益人分布（AI 生成，附 prompt 佐證）。

寫出 4 份 CSV 到 data/snapshot_2026-06-05/，並就地稽核 Q1（名實）、Q3（漂綠）
會算出的數字，確保 demo 故事在灌進 EAP 前就先驗證過。

執行：python3 eap_import_bundle/gen_supplemental_data.py
"""
import csv
from pathlib import Path

DATA = Path(__file__).parent.parent / "data" / "snapshot_2026-06-05"
ASOF = "2026-06-05"
SRC = "AI生成示意（參考 TWSE 公司治理評鑑 t187ap46 級距與 MSCI ESG 公開評等概念，非實際評等）"

# ── 1) ESG 評分（0–100，越高越好）────────────────────────────
#    參考各公司公開 ESG/治理聲譽的相對位置，僅為示意值。
ESG = {
    "2330": 86, "2454": 80, "3711": 74,          # 半導體
    "2308": 90,                                   # 台達電（綠能 ESG 標竿）
    "2317": 70, "2382": 72, "3231": 66, "2356": 62, "2376": 64,  # 電子代工
    "3008": 73,                                   # 光學
    "2412": 84,                                   # 中華電（電信）
    "2884": 88, "2885": 74, "2891": 78,           # 金融（玉山 ESG 強）
    "1101": 68,                                   # 台泥（高碳排但積極轉型）
}

# ── 2) 主題標籤（Stock -[BELONGS_TO_THEME {weight,conf,evidence}]-> Theme）──
#    weight = 該個股「算進這個主題」的程度 0–1；conf = LLM 信心。
SECTOR_THEME = {  # sector -> (theme_name)
    "半導體": "半導體", "電子代工": "電子代工", "金融": "金融",
    "電信": "電信", "光學": "光學", "電力電子": "電力電子", "水泥": "水泥",
}
STOCK_SECTOR = {
    "2330": "半導體", "2454": "半導體", "3711": "半導體",
    "2317": "電子代工", "2356": "電子代工", "2376": "電子代工",
    "2382": "電子代工", "3231": "電子代工",
    "2884": "金融", "2885": "金融", "2891": "金融",
    "2412": "電信", "3008": "光學", "2308": "電力電子", "1101": "水泥",
}
# factor / income / esg 主題：stock -> (theme, type, weight, conf, evidence)
THEMATIC = [
    # 5G通訊（Q1 名實主秀：00881 標榜 5G）
    ("2454", "5G通訊", "factor", 1.0, 0.95, "5G 數據機晶片全球前二，純 5G 核心"),
    ("2412", "5G通訊", "factor", 0.7, 0.80, "5G 電信營運商，基地台與頻譜布建"),
    ("2317", "5G通訊", "factor", 0.4, 0.60, "5G 基地台與終端組裝，部分相關"),
    ("3711", "5G通訊", "factor", 0.4, 0.60, "5G 晶片封測，間接相關"),
    ("2382", "5G通訊", "factor", 0.3, 0.55, "5G 網通/伺服器設備，部分相關"),
    ("2330", "5G通訊", "factor", 0.3, 0.50, "5G 晶片代工，但屬泛半導體非純 5G"),
    # AI供應鏈
    ("2330", "AI供應鏈", "factor", 0.9, 0.90, "AI 晶片先進製程主要代工"),
    ("2382", "AI供應鏈", "factor", 0.8, 0.85, "AI 伺服器代工龍頭"),
    ("2454", "AI供應鏈", "factor", 0.7, 0.85, "AI 邊緣運算 SoC"),
    ("3231", "AI供應鏈", "factor", 0.7, 0.80, "AI 伺服器/網通代工"),
    ("2376", "AI供應鏈", "factor", 0.6, 0.75, "AI 顯卡與伺服器板卡"),
    ("2317", "AI供應鏈", "factor", 0.5, 0.70, "AI 伺服器系統組裝"),
    # 科技（0052 / 00929 標榜）
    ("2330", "科技", "sector", 1.0, 0.95, "半導體龍頭"),
    ("2454", "科技", "sector", 1.0, 0.95, "IC 設計"),
    ("2317", "科技", "sector", 1.0, 0.90, "電子代工"),
    ("2382", "科技", "sector", 1.0, 0.90, "電子代工"),
    ("3231", "科技", "sector", 1.0, 0.90, "電子代工"),
    ("2356", "科技", "sector", 1.0, 0.90, "電子代工"),
    ("2376", "科技", "sector", 1.0, 0.90, "板卡"),
    ("3008", "科技", "sector", 1.0, 0.85, "光學鏡頭"),
    ("2308", "科技", "sector", 1.0, 0.90, "電源管理"),
    ("3711", "科技", "sector", 1.0, 0.90, "封測"),
    # 高股息（0056/00919/00940/00713/00878 標榜）
    ("2412", "高股息", "income", 0.9, 0.85, "電信高殖利率定存股"),
    ("2884", "高股息", "income", 0.8, 0.80, "金控穩定配息"),
    ("2885", "高股息", "income", 0.8, 0.80, "金控穩定配息"),
    ("2891", "高股息", "income", 0.8, 0.80, "金控穩定配息"),
    ("1101", "高股息", "income", 0.7, 0.75, "傳產高息"),
    ("2382", "高股息", "income", 0.6, 0.70, "代工龍頭兼具配息"),
    # ESG永續（00878 標榜）— ESG 分數高者納入
    ("2308", "ESG永續", "esg", 0.90, 0.75, "綠能/碳管理標竿"),
    ("2884", "ESG永續", "esg", 0.88, 0.72, "金融業 ESG 領先"),
    ("2330", "ESG永續", "esg", 0.86, 0.72, "供應鏈減碳與治理佳"),
    ("2412", "ESG永續", "esg", 0.84, 0.70, "電信 ESG 揭露完整"),
    ("2454", "ESG永續", "esg", 0.80, 0.68, "治理評鑑前段"),
    ("2891", "ESG永續", "esg", 0.78, 0.66, "金控 ESG 中上"),
]

# ── 3) ETF 標榜主題（ETF -[LABELED_AS {claimed:true}]-> Theme）─────
ETF_CLAIMED = {
    "0050": [("台灣大型權值", "market")],
    "006208": [("台灣大型權值", "market")],
    "00922": [("台灣大型權值", "market")],
    "0056": [("高股息", "income")],
    "00919": [("高股息", "income")],
    "00940": [("高股息", "income")],
    "00713": [("高股息", "income")],
    "00878": [("ESG永續", "esg"), ("高股息", "income")],
    "0052": [("科技", "sector")],
    "00929": [("科技", "sector")],
    "00881": [("5G通訊", "factor")],
    "00992A": [("主動選股", "factor")],
    "00400A": [("主動選股", "factor")],
    "00982A": [("主動選股", "factor")],
    "00984A": [("主動選股", "factor")],
    "00981A": [("主動選股", "factor")],
}

# ── 4) 受益人分布（TDCC 股權分散概念，4 個級距）──────────────
BUCKETS = [
    ("散戶小額", 1, 4999),
    ("散戶中額", 5000, 49999),
    ("大額", 50000, 999999),
    ("法人大戶", 1000000, None),
]
# 各 ETF 散戶集中度（散戶小額+中額 人數佔比），示意值
RETAIL_RATIO = {
    "0056": 0.96, "00878": 0.95, "00919": 0.94, "00940": 0.93, "00929": 0.93,
    "00713": 0.92, "00881": 0.90, "0052": 0.88, "0050": 0.85, "006208": 0.84,
    "00922": 0.86, "00992A": 0.82, "00400A": 0.80, "00982A": 0.80,
    "00984A": 0.79, "00981A": 0.79,
}
TOTAL_PERSONS = {  # 受益人總數（萬人）示意，呼應「全市場破 1458 萬」金句
    "0056": 108.0, "00878": 142.0, "00919": 61.0, "00940": 95.0, "00929": 40.0,
    "00713": 22.0, "00881": 33.0, "0052": 9.0, "0050": 96.0, "006208": 18.0,
    "00922": 7.0, "00992A": 6.0, "00400A": 3.0, "00982A": 2.5,
    "00984A": 2.0, "00981A": 2.2,
}


def write_csv(name, header, rows):
    p = DATA / name
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"  ✍  {name:28} {len(rows)} 列")
    return p


def main():
    print("=== 產生補充資料（ESG / 主題 / 受益人）===\n")

    # stock_esg.csv
    esg_rows = [[t, ESG[t], SRC, ASOF] for t in ESG]
    write_csv("stock_esg.csv",
              ["stock_ticker", "esg_score", "esg_score_source", "esg_updated_at"],
              esg_rows)

    # stock_themes.csv（BELONGS_TO_THEME）— sector themes + thematic
    theme_rows = []
    for t, sec in STOCK_SECTOR.items():
        theme_rows.append([t, SECTOR_THEME[sec], "sector", 1.0, 0.99,
                           f"主要營收來自{sec}"])
    for t, name, typ, w, conf, ev in THEMATIC:
        theme_rows.append([t, name, typ, w, conf, ev])
    write_csv("stock_themes.csv",
              ["stock_ticker", "theme_name", "theme_type", "weight",
               "llm_confidence", "evidence"], theme_rows)

    # etf_claimed_themes.csv（LABELED_AS）
    claim_rows = []
    for etf, claims in ETF_CLAIMED.items():
        for name, typ in claims:
            claim_rows.append([etf, name, typ, "true"])
    write_csv("etf_claimed_themes.csv",
              ["etf_ticker", "theme_name", "theme_type", "claimed"], claim_rows)

    # holder_distribution.csv（HOLDER_DIST + InvestorBucket）
    hd_rows = []
    for etf, total_wan in TOTAL_PERSONS.items():
        total = total_wan * 10000
        retail = RETAIL_RATIO[etf]
        # 4 級距人數佔比：小額、中額、大額、法人
        small = retail * 0.78
        mid = retail * 0.22
        big = (1 - retail) * 0.7
        inst = (1 - retail) * 0.3
        shares_share = {"散戶小額": small * 0.35, "散戶中額": mid * 0.9,
                        "大額": big * 2.2, "法人大戶": inst * 18.0}
        ssum = sum(shares_share.values())
        for (bname, lo, hi), pratio in zip(
                BUCKETS, [small, mid, big, inst]):
            persons = round(total * pratio)
            sharepct = round(shares_share[bname] / ssum * 100, 2)
            hd_rows.append([etf, bname, lo, hi if hi is not None else "",
                            persons, "", sharepct, ASOF])
    write_csv("holder_distribution.csv",
              ["etf_ticker", "bucket_name", "range_min_shares",
               "range_max_shares", "persons", "shares", "share_pct", "date"],
              hd_rows)

    # ── 稽核：用既有 holdings 算 Q1（名實）、Q3（漂綠）────────────
    print("\n=== 稽核：demo 會算出什麼 ===")
    holds = {}
    with open(DATA / "holdings_2026-06-05.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            holds.setdefault(r["etf_ticker"], []).append(
                (r["stock_ticker"], float(r["weight_pct"])))

    # 個股對某 theme 的歸屬 weight 查表
    belong = {}
    for t, sec in STOCK_SECTOR.items():
        belong[(t, SECTOR_THEME[sec])] = 1.0
    for t, name, typ, w, conf, ev in THEMATIC:
        belong[(t, name)] = w

    def q1(etf, claimed):
        aligned = sum(wt * belong.get((s, claimed), 0.0) for s, wt in holds[etf])
        covered = sum(wt for s, wt in holds[etf] if s != "_OTHER")
        return aligned, covered

    al, cov = q1("00881", "5G通訊")
    print(f"\nQ1 名實 — 00881 國泰台灣5G+（標榜 5G通訊）:")
    print(f"   實際對齊 5G 權重 = {al:.1f}%（具名持股共 {cov:.0f}%；其餘 {100-cov:.0f}% 為 _OTHER）")
    print(f"   → 故事：標榜 5G，最大持股是台積電 30%（半導體），真正 5G 核心聯發科僅 25%")

    al2, cov2 = q1("0052", "科技")
    print(f"\nQ1 名實 — 0052 富邦科技（標榜 科技）:")
    print(f"   實際對齊 科技 權重 = {al2:.1f}%（名實相符度高，作為對照組）")

    # Q3 漂綠：00878 加權 ESG vs 市場平均（排除 _OTHER）
    mkt_avg = sum(ESG.values()) / len(ESG)
    def q3(etf):
        num = sum(wt * ESG[s] for s, wt in holds[etf] if s in ESG)
        den = sum(wt for s, wt in holds[etf] if s in ESG)
        return num / den if den else 0, den
    we, cov3 = q3("00878")
    print(f"\nQ3 漂綠 — 00878 國泰永續高股息（標榜 ESG永續）:")
    print(f"   加權 ESG = {we:.1f}　市場平均 = {mkt_avg:.1f}　溢價 = {we-mkt_avg:+.1f}")
    print(f"   （僅評估具名且有 ESG 分數的 {cov3:.0f}% 持股，其餘 {100-cov3:.0f}% 無 ESG 示意資料 → demo 要誠實標註）")
    print(f"   → 故事：永續標榜在可評估部分沒有領先市場，且仍有過半持股缺 ESG 示意資料")

    print("\n完成。CSV 已寫入 data/snapshot_2026-06-05/")


if __name__ == "__main__":
    main()
