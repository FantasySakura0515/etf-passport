"""
ETF 透視鏡 PASSPORT — automated EAP import.
Uploads 4 CSVs, configures models, creates + starts flows, waits for completion.

Usage:
    EAP_TOKEN="<jwt>" python3 import_to_eap.py
    (token 一律從環境變數 EAP_TOKEN 取得，請勿硬編入檔案)

Pre-condition:
    requests pip pkg installed
"""
import json, os, sys, time
from pathlib import Path

import requests

# ─────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────
TOKEN = os.environ.get("EAP_TOKEN")
if not TOKEN:
    sys.exit("請先設定環境變數 EAP_TOKEN（競賽 workshop JWT），勿將 token 硬編入檔案。")
B = "https://cloud.geminidata.com/api/v1"
H = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

# CSV 的單一真實來源是 data/snapshot（見 CLAUDE.md）；本資料夾不再放複本
DATA = Path(__file__).parent.parent / "data" / "snapshot_2026-06-05"

# ─────────────────────────────────────────────────────────────────────────
# Mappings — what each CSV becomes in the graph
# ─────────────────────────────────────────────────────────────────────────
def n(id_col, tag, key, props, label_col):
    """Helper: build a node spec.
       props is dict {prop_name: source_column}; label is added automatically."""
    full_props = {**props, "label": label_col}
    return {
        "id": id_col,
        "tags": [tag],
        "properties": full_props,
        "meta": {"keys": [key], "tags": [tag]},
    }

def e(src, tgt, edge_label, props):
    """Helper: build an edge spec."""
    return {
        "source": src, "target": tgt,
        "label": edge_label,
        "properties": props,
        "meta": {"keys": [], "tags": [edge_label]},
    }

CSV_PLAN = [
    {
        "name": "etf_metadata",
        "csv":  "etf_metadata.csv",
        "mapping": {
            "creator": "leader32@workshop.com", "version": "1.0",
            "graph": {
                "nodes": [
                    n("ticker", "ETF", "ticker",
                      {"ticker": "ticker", "name": "name", "issuer": "issuer",
                       "type": "type", "is_active": "is_active",
                       "tracked_index": "tracked_index",
                       "listed_date": "listed_date", "note": "note"},
                      label_col="name"),
                ],
                "edges": [],
            },
        },
    },
    {
        "name": "holdings",
        "csv":  "holdings_2026-06-05.csv",
        "mapping": {
            "creator": "leader32@workshop.com", "version": "1.0",
            "graph": {
                "nodes": [
                    # ETF stub — MERGE with existing ETF nodes by ticker
                    n("etf_ticker", "ETF", "ticker",
                      {"ticker": "etf_ticker"},
                      label_col="etf_ticker"),
                    # Stock node — primary content
                    n("stock_ticker", "Stock", "ticker",
                      {"ticker": "stock_ticker", "name": "stock_name",
                       "sector": "sector"},
                      label_col="stock_name"),
                ],
                "edges": [
                    e("etf_ticker", "stock_ticker", "HOLDS",
                      {"weight_pct": "weight_pct", "date": "date"}),
                ],
            },
        },
    },
    {
        "name": "dividends",
        "csv":  "dividends_2024-2025.csv",
        "mapping": {
            "creator": "leader32@workshop.com", "version": "1.0",
            "graph": {
                "nodes": [
                    # ETF stub — MERGE
                    n("etf_ticker", "ETF", "ticker",
                      {"ticker": "etf_ticker"},
                      label_col="etf_ticker"),
                    # DividendEvent
                    n("id", "DividendEvent", "id",
                      {"id": "id", "etf_ticker": "etf_ticker",
                       "ex_date": "ex_date", "payment_date": "payment_date",
                       "amount_per_unit": "amount_per_unit",
                       "currency": "currency",
                       "pct_股利所得": "pct_股利所得",
                       "pct_資本利得": "pct_資本利得",
                       "pct_收益平準金": "pct_收益平準金"},
                      label_col="id"),
                ],
                "edges": [
                    # DividendEvent  ← PAID_BY  ETF (event "paid by" ETF)
                    e("id", "etf_ticker", "PAID_BY", {}),
                ],
            },
        },
    },
    {
        "name": "regulatory_events",
        "csv":  "regulatory_events.csv",
        "mapping": {
            "creator": "leader32@workshop.com", "version": "1.0",
            "graph": {
                "nodes": [
                    n("id", "RegulatoryEvent", "id",
                      {"id": "id", "date": "date", "title": "title",
                       "impact_type": "impact_type",
                       "summary": "summary", "url": "url"},
                      label_col="title"),
                ],
                "edges": [],
            },
        },
    },
]

# ─────────────────────────────────────────────────────────────────────────
# API helpers
# ─────────────────────────────────────────────────────────────────────────
def get_signed_url(filename: str):
    r = requests.post(f"{B}/import/uploads/signed-url", headers=H,
                      json={"fileName": filename, "contentType": "text/csv"})
    r.raise_for_status()
    return r.json()  # {uploadId, signedUrl, expiredAt}

def upload_to_s3(signed_url: str, csv_path: Path):
    # No checksum header — bare PUT works (we discovered earlier)
    with open(csv_path, "rb") as f:
        body = f.read()
    r = requests.put(signed_url, data=body)
    r.raise_for_status()

def create_source(name: str, upload_id: str, filename: str):
    r = requests.put(f"{B}/import/sources", headers=H,
                     json={"name": name, "type": "csv",
                           "config": {"fileName": filename,
                                      "uploadId": upload_id,
                                      "encoding": "utf-8"}})
    r.raise_for_status()
    return r.json()["_id"]

def create_model(name: str, mapping: dict):
    r = requests.put(f"{B}/import/models", headers=H,
                     json={"name": name, "mapping": mapping})
    r.raise_for_status()
    return r.json()["_id"]

def create_flow(name: str, source_id: str, model_id: str):
    r = requests.put(f"{B}/import/flows", headers=H,
                     json={"name": name, "source_id": source_id, "model_id": model_id})
    r.raise_for_status()
    return r.json()["_id"]

def start_flow(flow_id: str):
    r = requests.post(f"{B}/import/flows/{flow_id}/start", headers=H)
    r.raise_for_status()

def flow_status(flow_id: str):
    r = requests.get(f"{B}/import/flows/{flow_id}/status", headers=H)
    r.raise_for_status()
    d = r.json()
    p = d.get("$__parent", {}).get("status", {})
    return {
        "status": p.get("status"),
        "records": p.get("ingestedRecords"),
        "progress": p.get("progressPercentage"),
        "reason": p.get("reason"),
    }

def wait_flow(flow_id: str, timeout=120):
    deadline = time.time() + timeout
    while time.time() < deadline:
        s = flow_status(flow_id)
        if s["status"] in ("completed", "failed", "stopped") and s["status"] != "running":
            # First check after start may show "stopped" momentarily; require non-zero progress or final state
            if s["status"] == "completed" or s["status"] == "failed":
                return s
            if s["progress"] == 0 and s["records"] == 0 and s["reason"] is None:
                # not started yet
                pass
            else:
                return s
        time.sleep(2)
    return s

# ─────────────────────────────────────────────────────────────────────────
# Cleanup helpers — wipe failed flows/models/sources from prior probing
# ─────────────────────────────────────────────────────────────────────────
def cleanup():
    """Delete prior failed flows + their models + sources."""
    print("→ cleanup: previous flows/models/sources")
    for kind, plural in [("flow", "flows"), ("model", "models"), ("source", "sources")]:
        r = requests.get(f"{B}/import/{plural}?flat=true", headers=H)
        items = r.json()
        if isinstance(items, dict):
            items = list(items.values())
        for it in items:
            iid = it["_id"]
            requests.delete(f"{B}/import/{plural}/{iid}", headers=H)
        print(f"   deleted {len(items)} {plural}")

# ─────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────
def main():
    print("=== EAP import: ETF 透視鏡 PASSPORT ===")
    print(f"   project (g_uid): leader32@workshop.com")
    print()

    if "--clean" in sys.argv:
        cleanup()
        print()

    results = []
    for plan in CSV_PLAN:
        name = plan["name"]
        csv = DATA / plan["csv"]
        print(f"\n📂 {name}  ({csv.name}, {csv.stat().st_size:,} bytes)")

        # 1. signed url
        su = get_signed_url(csv.name)
        print(f"   ① signed url: uploadId={su['uploadId'][:8]}...")
        # 2. PUT to s3
        upload_to_s3(su["signedUrl"], csv)
        print(f"   ② uploaded to S3")
        # 3. source
        sid = create_source(name, su["uploadId"], csv.name)
        print(f"   ③ source: {sid}")
        # 4. model
        mid = create_model(f"{name}_model", plan["mapping"])
        print(f"   ④ model:  {mid}")
        # 5. flow
        fid = create_flow(f"{name}_flow", sid, mid)
        print(f"   ⑤ flow:   {fid}")
        # 6. start
        start_flow(fid)
        print(f"   ⑥ started, polling status...")
        # 7. wait
        s = wait_flow(fid, timeout=120)
        emoji = "✅" if s["status"] == "completed" else "❌"
        print(f"   {emoji} {s['status']} — {s['records']} records ingested")
        if s["status"] != "completed":
            print(f"      reason: {s['reason']}")
        results.append({"name": name, **s, "flow_id": fid})

    print()
    print("=== summary ===")
    for r in results:
        e = "✅" if r["status"] == "completed" else "❌"
        print(f"  {e} {r['name']:20s}  {r['records']:>4} records   ({r['status']})")
        if r["status"] != "completed":
            print(f"      reason: {r['reason']}")

if __name__ == "__main__":
    main()
