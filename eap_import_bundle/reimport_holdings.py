# -*- coding: utf-8 -*-
"""清掉 EAP 上的舊 HOLDS 邊，重灌真實持股（含 2026-06-11 細產業 sector）。

背景：EAP Graph 上只有 96 條舊 HOLDS 邊（舊版前幾大持股），完整 724 列真實持股
從未上雲；且 sector 欄已改為 31 類細產業（見 data/snapshot_2026-06-05/
AI_GENERATED_PROMPTS.md §5）。import 對邊沒有去重 key，直接重灌會新舊並存，
所以先用 chat Cypher 刪舊邊再灌。

執行（會修改雲端共用 Graph，請確認後再跑）：
    cd eap_import_bundle && python3 reimport_holdings.py

token 來源：環境變數 EAP_TOKEN，沒有的話自動讀 ../demo/.env。
"""
import json
import os
import re
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / "data" / "snapshot_2026-06-05" / "holdings_2026-06-05.csv"
B = "https://cloud.geminidata.com/api/v1"


def get_token() -> str:
    tok = os.environ.get("EAP_TOKEN")
    if not tok:
        env = ROOT / "demo" / ".env"
        if env.exists():
            m = re.search(r"^EAP_TOKEN=(.+)$", env.read_text(), re.M)
            if m:
                tok = m.group(1).strip()
    if not tok:
        sys.exit("找不到 EAP_TOKEN（環境變數或 demo/.env）")
    return tok


H = {"Authorization": f"Bearer {get_token()}", "Content-Type": "application/json"}
c = httpx.Client(timeout=120)


# ── chat Cypher 工具 ─────────────────────────────────────────────
def new_chat(title: str) -> str:
    r = c.post(f"{B}/chat/create", headers=H, json={"title": title})
    r.raise_for_status()
    return r.json()["insertedId"]


def ask(chat_id: str, q: str) -> str:
    """非 streaming 問一句，回最後一筆 result。"""
    r = c.post(f"{B}/chat/{chat_id}", headers=H, json={"q": q, "streaming": False})
    r.raise_for_status()
    last = None
    for line in r.text.splitlines():
        m = re.match(r"^data:\s*(\{.*\})\s*$", line)
        if m:
            try:
                obj = json.loads(m.group(1))
                if obj.get("result"):
                    last = obj["result"]
            except json.JSONDecodeError:
                pass
    return (last or r.text[:300]).strip()


def count_holds(chat_id: str) -> str:
    return ask(chat_id, "請直接執行這條 Cypher 並只回傳數字，不要改寫: "
                        "MATCH ()-[h:HOLDS]->() RETURN count(h)")


# ── import 流程（照抄 import_to_eap.py，改用 httpx）──────────────
def import_holdings() -> dict:
    mapping = {
        "creator": "leader32@workshop.com", "version": "1.1",
        "graph": {
            "nodes": [
                {"id": "etf_ticker", "tags": ["ETF"],
                 "properties": {"ticker": "etf_ticker", "label": "etf_ticker"},
                 "meta": {"keys": ["ticker"], "tags": ["ETF"]}},
                {"id": "stock_ticker", "tags": ["Stock"],
                 "properties": {"ticker": "stock_ticker", "name": "stock_name",
                                "sector": "sector", "label": "stock_name"},
                 "meta": {"keys": ["ticker"], "tags": ["Stock"]}},
            ],
            "edges": [{
                "source": "etf_ticker", "target": "stock_ticker", "label": "HOLDS",
                "properties": {"weight_pct": "weight_pct", "date": "date"},
                "meta": {"keys": [], "tags": ["HOLDS"]},
            }],
        },
    }

    r = c.post(f"{B}/import/uploads/signed-url", headers=H,
               json={"fileName": CSV.name, "contentType": "text/csv"})
    r.raise_for_status()
    su = r.json()
    print(f"   ① signed url ok")

    c.put(su["signedUrl"], content=CSV.read_bytes()).raise_for_status()
    print(f"   ② uploaded {CSV.stat().st_size:,} bytes")

    r = c.put(f"{B}/import/sources", headers=H,
              json={"name": "holdings_real_sectors", "type": "csv",
                    "config": {"fileName": CSV.name, "uploadId": su["uploadId"],
                               "encoding": "utf-8"}})
    r.raise_for_status()
    sid = r.json()["_id"]
    print(f"   ③ source {sid}")

    r = c.put(f"{B}/import/models", headers=H,
              json={"name": "holdings_real_sectors_model", "mapping": mapping})
    r.raise_for_status()
    mid = r.json()["_id"]
    print(f"   ④ model {mid}")

    r = c.put(f"{B}/import/flows", headers=H,
              json={"name": "holdings_real_sectors_flow",
                    "source_id": sid, "model_id": mid})
    r.raise_for_status()
    fid = r.json()["_id"]
    print(f"   ⑤ flow {fid}")

    c.post(f"{B}/import/flows/{fid}/start", headers=H).raise_for_status()
    print(f"   ⑥ started, polling…")

    p = {}
    for _ in range(90):
        r = c.get(f"{B}/import/flows/{fid}/status", headers=H)
        r.raise_for_status()
        p = r.json().get("$__parent", {}).get("status", {})
        st = p.get("status")
        if st in ("completed", "failed") or (
                st == "stopped" and (p.get("progressPercentage") or p.get("ingestedRecords"))):
            break
        time.sleep(2)
    return p


def delete_old_flow():
    """刪掉舊的 holdings_flow / model / source（只是匯入設定，可重建）。
    目的：測試平台會不會連帶回收該 flow 灌進圖裡的舊邊。"""
    flows = c.get(f"{B}/import/flows?flat=true", headers=H)
    flows.raise_for_status()
    old = [f for f in flows.json() if f["name"] in ("holdings_flow",
                                                    "holdings_real_sectors_flow")]
    if not old:
        print("   （沒有舊的 holdings flow，跳過）")
        return
    for f in old:
        print(f"   刪 flow {f['name']} ({f['_id']})")
        for kind, iid in (("flows", f["_id"]), ("models", f.get("model_id")),
                          ("sources", f.get("source_id"))):
            if not iid:
                continue
            r = c.delete(f"{B}/import/{kind}/{iid}", headers=H)
            print(f"      DELETE {kind}/{iid} → {r.status_code}")


def main():
    chat_id = new_chat("reimport holdings 驗證")
    print(f"chat: {chat_id}\n")

    print("Step 1/4 — 現況")
    before = count_holds(chat_id)
    print(f"   HOLDS 邊數（刪除前）: {before}\n")

    print("Step 2/4 — 清除舊資料")
    # 2a. chat Cypher 刪邊（實測 2026-06-12：chat 為唯讀模式，多半會失敗，留著以防平台開放）
    out = ask(chat_id, "請直接執行這條 Cypher，一字不改，不要加任何條件: "
                       "MATCH ()-[h:HOLDS]->() DELETE h")
    print(f"   2a chat Cypher 刪邊 → {out[:80]}")
    # 2b. 刪舊 import flow，看資料會不會跟著回收
    print("   2b 刪舊 holdings flow/model/source：")
    delete_old_flow()
    after_del = count_holds(chat_id)
    print(f"   HOLDS 邊數（清除後）: {after_del}")
    cleaned = after_del.split()[-1:][0][:4].startswith("0")
    if not cleaned:
        print("   ⚠️ 舊邊仍在（平台不支援由 API 回收圖資料）。")
        print("   選擇一：到前台 Data Explorer → Source Data 手動刪 HOLDS 後重跑。")
        print("   選擇二：加 --force 重跑，接受 96 條舊邊與新資料並存（節點屬性仍會正確更新）。")
        if "--force" not in sys.argv:
            sys.exit(1)
        print("   （--force：照灌）")
    print()

    print("Step 3/4 — 重灌 holdings（724 列，含 31 類細產業 sector）")
    p = import_holdings()
    emoji = "✅" if p.get("status") == "completed" else "❌"
    print(f"   {emoji} {p.get('status')} — {p.get('ingestedRecords')} records, "
          f"{p.get('progressPercentage')}%  {p.get('reason') or ''}\n")

    print("Step 4/4 — 驗證")
    print(f"   HOLDS 邊數（重灌後，預期 724）: {count_holds(chat_id)}")
    print("   台積電 sector（預期 晶圓代工）:",
          ask(chat_id, "請直接執行這條 Cypher，一字不改: "
                       "MATCH (s:Stock) WHERE s.name = '台積電' RETURN s.sector"))
    print("   國巨 sector（預期 被動元件）:",
          ask(chat_id, "請直接執行這條 Cypher，一字不改: "
                       "MATCH (s:Stock) WHERE s.name STARTS WITH '國巨' RETURN s.name, s.sector"))


if __name__ == "__main__":
    main()
