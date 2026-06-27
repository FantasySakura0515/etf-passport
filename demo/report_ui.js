// ─────────────────────────────────────────────
// ETF 透視鏡 PASSPORT — 報告產出 / 報告櫃
// 依賴 app.js 的全域：$、$$、renderMarkdown、renderMermaidIn、
// getActiveHoldings、escapeHtml、appendBotMessage
// ─────────────────────────────────────────────

const reportState = { current: null, saved: false };

async function initReportUI() {
  // 16 檔下拉
  try {
    const list = await (await fetch("/api/passport/etfs")).json();
    $("#etf-report-select").innerHTML = list
      .map((e) => `<option value="${escapeHtml(e.ticker)}">${escapeHtml(`${e.ticker} ${e.name}`)}</option>`)
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

// 下載 self-contained HTML（Mermaid 已是 SVG，無外部依賴；
// 內容 = #report-body 的 innerHTML，已經過 DOMPurify 消毒）
function standaloneHtml(rep, { autoPrint = false } = {}) {
  return `<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">
<title>${escapeHtml(rep.title)}</title>
${autoPrint ? '<script>addEventListener("load",()=>print())<\/script>' : ""}
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
  const blob = new Blob([standaloneHtml(rep, { autoPrint: true })],
                        { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  window.open(url, "_blank");
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
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
