"""
ETF 透視鏡 PASSPORT — 前端 Demo Server

職責：
1. 服務靜態檔案（index.html / app.js / styles.css / mock_responses.js）
2. Proxy /api/v1/* 到 EAP Chat API，自動帶上 Authorization header
3. 對 streaming 端點保留原始 chunk 順序與時間（不做緩存）

啟動：
    python3 server.py
"""
from __future__ import annotations

import os
import json
import re
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

# 我方穿透計算引擎（數字一律走這裡，不經 EAP LLM）
from penetrate import (penetrate as compute_penetrate, greenwash, name_reality,
                       focus_ranking, active_focus_ranking, sector_ranking,
                       etf_list)
from report import etf_report, portfolio_report

load_dotenv()

EAP_TOKEN = os.getenv("EAP_TOKEN", "")
EAP_PROJECT_ID = os.getenv("EAP_PROJECT_ID", "")
EAP_BASE_URL = os.getenv("EAP_BASE_URL", "https://cloud.geminidata.com/api/v1")
PORT = int(os.getenv("PORT", "8000"))

ROOT = Path(__file__).parent

app = FastAPI(title="ETF Passport Demo")


@app.get("/api/config")
async def config():
    """前端啟動時取得 project_id 與 base 路徑（不回傳 token）"""
    return {
        "project_id": EAP_PROJECT_ID,
        "has_token": bool(EAP_TOKEN),
        "snapshot_date": "2026-06-05",
    }


# ─────────────────────────────────────────────────────────────
# 我方計算端點（穿透 / 漂綠 / 名實）— 數字 100% 由本地快照算，不碰 EAP
# 背景見 memory project_eap_cypher_unreliable：EAP chat 自動 Cypher 不可靠
# ─────────────────────────────────────────────────────────────
@app.post("/api/passport/penetrate")
async def api_penetrate(req: Request):
    """穿透計算。body: {holdings:[{ticker,amount}], focus?:"2330"}"""
    body = await req.json()
    holdings = body.get("holdings") or []
    if not holdings:
        raise HTTPException(400, "holdings 不可為空")
    return compute_penetrate(holdings, focus=body.get("focus", "2330"))


@app.get("/api/passport/active-ranking")
async def api_active_ranking(focus: str = "2330"):
    """主動式 ETF 對個股持股排名（預設台積電 2330；保留作延伸展示）。"""
    return active_focus_ranking(focus=focus)


@app.get("/api/passport/focus-ranking")
async def api_focus_ranking(focus: str = "2330"):
    """Q-A 全市場 ETF 對個股持股排名（預設台積電 2330）。"""
    return focus_ranking(focus=focus)


@app.get("/api/passport/sector-ranking")
async def api_sector_ranking(q: str):
    """Q-F 看好產業選 ETF：從問句抓產業詞，回 16 檔 ETF 對齊權重排名。"""
    return sector_ranking(q)


@app.get("/api/passport/greenwash/{etf}")
async def api_greenwash(etf: str):
    """Q3 漂綠檢測：ETF 加權 ESG vs 市場平均。"""
    return greenwash(etf)


@app.get("/api/passport/name-reality/{etf}")
async def api_name_reality(etf: str):
    """Q1 名實相符：ETF 標榜主題 vs 持股實際對齊。"""
    return name_reality(etf)


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
    """儲存報告到報告櫃。body: {title, markdown, meta}"""
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


@app.api_route("/api/v1/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy(path: str, request: Request):
    """
    透明 proxy 到 EAP API。
    - 對 streaming 端點（POST /chat/{chat_id}）保持 chunked transfer
    - 其餘端點直接回傳 JSON
    """
    if not EAP_TOKEN:
        raise HTTPException(500, "EAP_TOKEN not configured (.env)")

    upstream_url = f"{EAP_BASE_URL}/{path}"
    method = request.method
    headers = {
        "Authorization": f"Bearer {EAP_TOKEN}",
        "Content-Type": request.headers.get("content-type", "application/json"),
        "Accept": request.headers.get("accept", "application/json"),
    }
    body = await request.body() if method in ("POST", "PUT") else None
    params = dict(request.query_params)

    is_streaming = method == "POST" and path.count("/") == 1 and path.startswith("chat/")

    if is_streaming:
        async def stream_iter():
            timeout = httpx.Timeout(180.0, connect=10.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    method, upstream_url, headers=headers, content=body, params=params
                ) as r:
                    if r.status_code >= 400:
                        # 注意：不可命名為 body — 會遮蔽外層閉包變數造成 UnboundLocalError
                        err_body = await r.aread()
                        msg = err_body.decode("utf-8", errors="replace")[:500]
                        payload = json.dumps({
                            "error": f"EAP upstream {r.status_code}",
                            "detail": msg,
                        }, ensure_ascii=False)
                        yield f"data: {payload}\n\n".encode("utf-8")
                        return
                    async for chunk in r.aiter_raw():
                        if chunk:
                            yield chunk
        return StreamingResponse(stream_iter(), media_type="text/event-stream")

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.request(
            method, upstream_url, headers=headers, content=body, params=params
        )
        return StreamingResponse(
            iter([r.content]),
            status_code=r.status_code,
            media_type=r.headers.get("content-type", "application/json"),
        )


# 靜態檔案（最後掛，避免吃掉 /api 路由）
@app.get("/")
async def index():
    return FileResponse(ROOT / "index.html")


class SafeStaticFiles(StaticFiles):
    """擋掉不該從瀏覽器拿得到的檔案：.env 等 dotfile、後端原始碼、報告櫃。

    （StaticFiles 直接掛整個 demo/ 會把 .env 連同 EAP_TOKEN 端出去 —
    proxy 的初衷就是 token 不出 server，這裡必須擋。）
    """
    _BLOCKED_SUFFIXES = (".py", ".env")

    async def get_response(self, path: str, scope):
        parts = Path(path).parts
        if (any(p.startswith(".") for p in parts)
                or path.endswith(self._BLOCKED_SUFFIXES)
                or (parts and parts[0] in ("reports", "__pycache__"))):
            raise HTTPException(404)
        return await super().get_response(path, scope)


app.mount("/", SafeStaticFiles(directory=ROOT, html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    print(f"🚀 ETF Passport demo on http://localhost:{PORT}")
    print(f"   project_id = {EAP_PROJECT_ID or '(not set)'}")
    print(f"   token      = {'[set]' if EAP_TOKEN else '(not set — mock mode)'}")
    uvicorn.run("server:app", host="0.0.0.0", port=PORT, reload=False)
