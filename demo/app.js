// ─────────────────────────────────────────────
// ETF 透視鏡 PASSPORT — 前端核心邏輯
//
// 功能要點（簡報指定）：
//   - streaming JSON chunk 解析
//   - Markdown 渲染 (marked) + DOMPurify
//   - Mermaid 圖表（graph LR 穿透流向圖等）
//   - 每則 AI 回覆有「複製」按鈕
//   - Mock 模式：網路斷掉時 fallback 到 mock_responses.js
// ─────────────────────────────────────────────

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const state = {
  config: {},
  chatId: null,
  mock: false,
  holdings: [],
  msgCounter: 0,
};

// 公開資料來源（引用回鏈附可點連結，法遵級可追溯）
const SRC = {
  etfinfo: "https://www.etfinfo.tw/",
  twseIndex: "https://taiwanindex.com.tw/en/downloads/compilation_rule",
  sitca: "https://www.sitca.org.tw/FundNote/",
  mops: "https://mops.twse.com.tw/mops/web/t57sb01_q7",
  twseApi: "https://openapi.twse.com.tw/",
  tdcc: "https://openapi.tdcc.com.tw/",
};
// AI 生成欄位的 prompt 揭露（鐵則 5.1）
const AI_PROMPT_DOC = "research/prompt_design.md + data/snapshot_2026-06-05/AI_GENERATED_PROMPTS.md";
const SNAP = () => state.config.snapshot_date || "2026-06-05";

// ────────────────────────────
// 啟動
// ────────────────────────────
async function init() {
  try {
    const r = await fetch("/api/config");
    state.config = await r.json();
  } catch (e) {
    console.warn("config fetch failed（沿用本地快照日）", e);
    state.config = { snapshot_date: "2026-06-05" };
  }
  // 決賽現場：全程本地模式（數字題走本地確定性計算、質化題走預錄），完全不依賴 EAP / 網路。
  // 要改走 EAP（僅排練比對）把這行設 false 即可。
  state.mock = true;

  // 預設載入主題追熱 persona（最豐富的 demo）
  loadPersona("theme");
  bindEvents();
  appendBotMessage("您好，我是 ETF 透視鏡 PASSPORT。\n\n試試上面的 ⭐ Q-C 穿透按鈕，或直接問我關於你 ETF 組合的任何問題。\n\n👉 提示：點左側 Persona 一鍵載入示範組合。", []);
}

// ────────────────────────────
// 事件綁定
// ────────────────────────────
function bindEvents() {
  $("#ask-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const q = $("#ask-input").value.trim();
    if (!q) return;
    $("#ask-input").value = "";
    await ask(q);
  });

  $$(".persona-btn").forEach((btn) =>
    btn.addEventListener("click", () => loadPersona(btn.dataset.persona))
  );

  $$(".hero-q").forEach((btn) =>
    btn.addEventListener("click", () => {
      const q = window.HERO_QUESTIONS[btn.dataset.q];
      $("#ask-input").value = "";
      ask(q);
    })
  );

  $("#add-holding").addEventListener("click", () =>
    addHoldingRow({ ticker: "", amount: 100000 })
  );
}

// ────────────────────────────
// 持股 UI
// ────────────────────────────
function loadPersona(name) {
  const list = window.PERSONAS[name];
  if (!list) return;
  state.holdings = [];
  $("#holdings-list").innerHTML = "";
  list.forEach((h) => addHoldingRow(h));
}

function addHoldingRow(h) {
  state.holdings.push({ ...h });
  const idx = state.holdings.length - 1;
  const row = document.createElement("div");
  row.className = "holding-row";
  row.innerHTML = `
    <input class="ticker" value="${h.ticker}" placeholder="ETF 代號" />
    <input class="amount" type="number" min="1000" step="1000" value="${h.amount}" />
    <button class="remove" title="移除">×</button>
  `;
  row.querySelector(".ticker").addEventListener("input", (e) => {
    state.holdings[idx].ticker = e.target.value.toUpperCase();
  });
  row.querySelector(".amount").addEventListener("input", (e) => {
    state.holdings[idx].amount = Number(e.target.value);
  });
  row.querySelector(".remove").addEventListener("click", () => {
    state.holdings[idx] = null;
    row.remove();
  });
  $("#holdings-list").appendChild(row);
}

function getActiveHoldings() {
  return state.holdings.filter((h) => h && h.ticker && h.amount > 0);
}

// ────────────────────────────
// 詢問流程
// ────────────────────────────
// 數字題 → 走我方後端計算（100% 可控，不經 EAP LLM；見 penetrate.py）
// 先判最具體的意圖（排名 / 漂綠 / 名實 / 穿透），其餘走 EAP / mock
const RANKING_RE = /(台積電|2330).*(前\s*[五5]|Top\s*5|排名|持股.*高)|(前\s*[五5]|Top\s*5|排名).*(台積電|2330)/i;
const GREEN_RE = /漂綠|洗綠|綠.*洗|永續.*(真|假|名|相符)|ESG.*(真|假|名|可信)|是真的.*ESG/;
const NAME_RE = /名實|名副其實|名不副實|名實相符|標榜.*(真|實|對齊)|真的.*(主題|名副|是.*嗎)/;
const PENETRATE_RE = /穿透|曝險|集中|重複|我的?組合|這\s*[四4]\s*檔|整體.*佔/;
const SECTOR_RE = /看好|該買哪|買哪檔|哪檔.*(最純|含.*最多|最對齊)|想(投資|布局|押|卡位).*(產業|族群|主題|概念)/;

// 跑我方計算 handler；成功 finalize。失敗 → 退到該題預錄 mock（三重保險），
// 仍無預錄才顯示乾淨錯誤狀態（不靜默 fall-through、不開天窗）
async function runLocal(handler, question, bubble, content, actions) {
  try {
    const cits = await handler();
    finalizeBot(bubble, content, actions, cits);
  } catch (err) {
    console.error("local compute failed → 試預錄備援", err);
    if (pickMock(question)) {
      await mockStream(question, content);
      finalizeBot(bubble, content, actions, mockCitations(question));
    } else {
      content.innerHTML = `<p class="msg-warn">⚠️ 計算服務暫時無法回應，請稍後再試。</p>`;
      finalizeBot(bubble, content, actions, []);
    }
  }
}

async function ask(question) {
  appendUserMessage(question);
  const { bubble, content, actions } = appendBotPlaceholder();

  // 數字/結構題一律走我方後端（可靠、秒回）；以下意圖互斥，先判最具體的
  if (RANKING_RE.test(question)) {
    return runLocal(() => rankingLocal(content), question, bubble, content, actions);
  }
  if (GREEN_RE.test(question)) {
    return runLocal(() => greenwashLocal(content, question), question, bubble, content, actions);
  }
  if (NAME_RE.test(question)) {
    return runLocal(() => nameRealityLocal(content, question), question, bubble, content, actions);
  }
  if (SECTOR_RE.test(question)) {
    return runLocal(() => sectorLocal(content, question), question, bubble, content, actions);
  }
  if (PENETRATE_RE.test(question) && getActiveHoldings().length) {
    return runLocal(() => penetrateLocal(content), question, bubble, content, actions);
  }

  const payload = {
    question,
    holdings: getActiveHoldings(),
    snapshot_date: state.config.snapshot_date,
  };

  if (state.mock) {
    await mockStream(question, content);
    finalizeBot(bubble, content, actions, mockCitations(question));
    return;
  }

  try {
    if (!state.chatId) await createChat();
    const cits = await streamFromEAP(payload, content);
    finalizeBot(bubble, content, actions, cits);
  } catch (err) {
    console.error("EAP stream failed → fallback to mock", err);
    content.innerHTML += `<p class="msg-warn">⚠️ EAP 連線異常，自動切換 Mock 模式。</p>`;
    await mockStream(question, content);
    finalizeBot(bubble, content, actions, mockCitations(question));
  }
}

// ────────────────────────────
// 我方穿透計算（不經 EAP）
// ────────────────────────────
async function penetrateLocal(contentEl) {
  const r = await fetch("/api/passport/penetrate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ holdings: getActiveHoldings(), focus: "2330" }),
  });
  if (!r.ok) throw new Error(`penetrate ${r.status}`);
  const d = await r.json();
  if (d.error) throw new Error(d.error);

  await streamMarkdown(contentEl, buildPenetrationMarkdown(d));

  const cits = [
    {
      type: "hybrid",
      text: `Hybrid 編排：Graph 鎖定 ${d.focus.exposure_pct}% 數字（跨多檔 HOLDS 加權）＋ Vector 引用指數編製規則解釋「為什麼集中」，LLM 只負責合成、不碰數字`,
    },
    {
      type: "graph",
      text: `跨多檔 HOLDS 邊加權求和：${d.etf_count} 檔 ETF × 各自台積電持股權重，as of ${d.as_of}`
          + `（我方後端確定性計算，非 LLM 心算）`,
    },
    {
      type: "data",
      text: `真實成分股持股表 holdings_${d.as_of}.csv ｜ 來源 etfinfo.tw，經元大投信官網交叉驗證`,
      url: SRC.etfinfo,
    },
  ];
  // 兩檔市值型同追 FTSE TWSE Taiwan 50 是集中主因 → 補指數編製規則佐證（僅在組合含此兩檔時）
  const coTrack = (d.focus.by_etf || []).filter((e) => e.etf === "0050" || e.etf === "006208");
  if (coTrack.length >= 2) {
    cits.push({
      type: "vector",
      text: `${coTrack.map((e) => e.etf).join("、")} 同追「FTSE TWSE Taiwan 50 指數」`
          + `（市值加權，台積電權重最大）— 集中原因之一，依指數編製規則`,
      url: SRC.twseIndex,
    });
  }
  if (d.unknown_tickers && d.unknown_tickers.length) {
    cits.push({
      type: "warning",
      text: `略過快照中不存在的 ETF：${d.unknown_tickers.join("、")}`,
    });
  }
  return cits;
}

async function rankingLocal(contentEl) {
  const r = await fetch("/api/passport/focus-ranking?focus=2330");
  if (!r.ok) throw new Error(`focus-ranking ${r.status}`);
  const d = await r.json();
  if (d.error) throw new Error(d.error);

  await streamMarkdown(contentEl, buildRankingMarkdown(d), { mermaid: false });
  return [
    {
      type: "graph",
      text: `16 檔 ETF 的 HOLDS 邊依 ${d.focus_name} 權重排序（ORDER BY weight DESC，禁 OVER()），as of ${d.as_of}`,
    },
    {
      type: "data",
      text: `真實成分股持股表 holdings_${d.as_of}.csv ｜ 來源 etfinfo.tw，經各投信官網交叉驗證`,
      url: SRC.etfinfo,
    },
  ];
}

// 從問題中抓 ETF 代號（如 0050 / 00878 / 00992A）
function extractTicker(q, fallback) {
  const m = q.match(/\b(00?\d{3,4}[A-Z]?)\b/);
  return m ? m[1] : fallback;
}

async function nameRealityLocal(contentEl, question) {
  const etf = extractTicker(question, "00881");
  const r = await fetch(`/api/passport/name-reality/${etf}`);
  if (!r.ok) throw new Error(`name-reality ${r.status}`);
  const d = await r.json();
  if (d.error) throw new Error(d.error);

  // 無個股標記資料的主題（如「台灣大型權值」）對齊度結構性為 0，不可判為落差
  const t0 = d.themes.find((t) => t.has_tag_data) || d.themes[0];
  const verdict = !t0.has_tag_data
    ? `**無法判定**：標榜「${t0.claimed_theme}」目前無個股主題標記資料可比對。`
    : t0.aligned_pct < 60
    ? `**名實落差大**：標榜「${t0.claimed_theme}」，但持股實際只有 ${t0.aligned_pct}% 真正對齊。`
    : `**大致名副其實**：標榜「${t0.claimed_theme}」，持股對齊度 ${t0.aligned_pct}%。`;
  let md = `### 名實相符檢測：${d.etf_name}（${d.etf}）\n\n> ${verdict}\n\n`;
  md += `| 標榜主題 | 實際對齊權重 |\n|---|--:|\n`;
  d.themes.forEach((t) => {
    md += `| ${t.claimed_theme} | ${t.has_tag_data ? `${t.aligned_pct}%` : "—（無標記資料）"} |\n`;
  });
  md += `\n具名持股共 **${d.named_weight_pct}%**，其餘 ${d.other_weight_pct}% 為未揭露的「其他持股」。`;
  await streamMarkdown(contentEl, md, { mermaid: false });
  return [
    { type: "hybrid", text: `Hybrid 融合：Graph 取持股權重（LABELED_AS / BELONGS_TO_THEME）× Vector 從公開說明書取「標榜主題」，兩來源比對算名實落差` },
    { type: "graph", text: `${d.etf_name} 標榜主題 vs 持股實際主題加權對齊；我方後端確定性計算` },
    { type: "data", text: `成分股持股 holdings_${SNAP()}.csv（etfinfo.tw）＋ 個股主題標籤 stock_themes.csv`, url: SRC.etfinfo },
    { type: "ai", text: `個股主題標註為 AI 生成（自個股年報「主要產品/業務」＋ 營收結構抽取，conf<0.5 不採計）；prompt 全文：${AI_PROMPT_DOC}` },
  ];
}

async function greenwashLocal(contentEl, question) {
  const etf = extractTicker(question, "00878");
  const r = await fetch(`/api/passport/greenwash/${etf}`);
  if (!r.ok) throw new Error(`greenwash ${r.status}`);
  const d = await r.json();
  if (d.error) throw new Error(d.error);

  const verdict = d.esg_premium > 0
    ? `可評估部分**大致名副其實**：加權 ESG ${d.weighted_esg} 高於市場平均 ${d.market_avg_esg}（+${d.esg_premium}）。`
    : `**有漂綠疑慮**：加權 ESG ${d.weighted_esg} 未高於市場平均 ${d.market_avg_esg}（${d.esg_premium}）。`;
  let md = `### 漂綠檢測：${d.etf_name}（${d.etf}）\n\n`;
  md += `標榜：${(d.claimed_themes || []).join("、") || "—"}\n\n> ${verdict}\n\n`;
  md += `| 指標 | 數值 |\n|---|--:|\n`;
  md += `| 成分股加權 ESG | ${d.weighted_esg} |\n| 全市場平均 ESG | ${d.market_avg_esg} |\n`;
  md += `| ESG 溢價 | ${d.esg_premium > 0 ? "+" : ""}${d.esg_premium} |\n`;
  md += `| 可評估持股 | ${d.evaluable_weight_pct}% |\n`;
  md += `\n> ⚠️ 誠實揭露：僅 **${d.evaluable_weight_pct}%** 持股有 ESG 資料可評估，其餘 ${d.unevaluable_weight_pct}% 為未揭露「其他持股」、無法驗證。`;
  await streamMarkdown(contentEl, md, { mermaid: false });
  return [
    { type: "hybrid", text: `Hybrid 融合：Graph 取成分股持股權重 × 各股 ESG 分數加權，對比 Vector 取公開說明書「永續/ESG」標榜 — 比對名實是否相符` },
    { type: "graph", text: `${d.etf_name} 成分股加權 ESG vs 全市場平均；持股權重 × 個股 ESG 求和，我方後端計算` },
    { type: "data", text: `成分股持股 holdings_${SNAP()}.csv（etfinfo.tw）＋ 個股 ESG 分數 stock_esg.csv`, url: SRC.etfinfo },
    { type: "warning", text: `僅 ${d.evaluable_weight_pct}% 持股有 ESG 資料可評估，其餘 ${d.unevaluable_weight_pct}% 為未揭露「其他持股」、無法驗證` },
  ];
}

// Q-F：看好某產業 → ETF 對齊權重排名（關鍵詞抽取在後端 penetrate.py 做，字典單一來源）
async function sectorLocal(contentEl, question) {
  const r = await fetch(`/api/passport/sector-ranking?q=${encodeURIComponent(question)}`);
  if (!r.ok) throw new Error(`sector-ranking ${r.status}`);
  const d = await r.json();

  if (d.error === "no_keyword") {
    await streamMarkdown(contentEl,
      `我沒在問題裡找到認得的產業／主題詞。目前支援：\n\n${d.supported.join("、")}\n\n` +
      `試試「我看好**被動元件**，該買哪檔 ETF？」`,
      { mermaid: false }
    );
    return [];
  }
  if (d.error) throw new Error(d.error);

  await streamMarkdown(contentEl, buildSectorMarkdown(d), { mermaid: false });

  const cits = [
    { type: "hybrid", text: `Hybrid 融合：Graph 取 16 檔 ETF 的成分股權重 × ${d.kind === "theme" ? "AI 主題標註" : "細產業分類"}對齊度，加權排出最對題的 ETF` },
    {
      type: "graph",
      text: `16 檔 ETF 對「${d.name}」加權對齊排名（持股權重 × 對齊度求和），as of ${d.as_of}`,
    },
    {
      type: "data",
      text: `成分股持股 holdings_${d.as_of}.csv（etfinfo.tw）`,
      url: SRC.etfinfo,
    },
    {
      type: "ai",
      text: `產業/主題分類為 AI 生成（受控詞表）；prompt 全文：${AI_PROMPT_DOC}（§5）`,
    },
  ];
  if (d.kind === "theme") {
    cits.push({
      type: "warning",
      text: `主題「${d.name}」目前僅標記 ${d.theme_stock_count} 檔個股（stock_themes.csv），對齊權重為下限估計`,
    });
  }
  return cits;
}

function buildSectorMarkdown(d) {
  const kindLabel = { sector: "細產業", group: "產業群", theme: "主題" }[d.kind];
  const top = d.ranking[0];
  let md = `### 看好「${d.name}」→ 該買哪檔 ETF？（資料快照 ${d.as_of}）\n\n`;
  md += `> 結論：${d.etf_total} 檔 ETF 中，對 **${d.name}**（${kindLabel}）曝險最高的是 `
      + `**${top.etf} ${top.etf_name}**，對齊權重 **${top.aligned_pct}%**。\n\n`;
  if (d.kind === "group") {
    md += `「${d.name}」在這裡聚合 ${d.members.length} 個細產業：${d.members.join("、")}。\n\n`;
  }
  md += `| 排名 | ETF | 類型 | 對齊權重 | 主要貢獻持股 |\n|---:|---|---|--:|---|\n`;
  d.ranking.forEach((row, idx) => {
    const tops = row.top_stocks.map((s) => `${s.stock_name} ${s.contrib_pct}%`).join("、") || "—";
    md += `| ${idx + 1} | ${row.etf} ${row.etf_name} | ${row.is_active ? "主動式" : "被動式"} | ${row.aligned_pct}% | ${tops} |\n`;
  });
  if (top.aligned_pct < 10) {
    md += `\n> ⚠️ 誠實揭露：就算第 1 名，對「${d.name}」的曝險也只有 **${top.aligned_pct}%** — `
        + `台股 ETF 裡沒有「純 ${d.name}」的選擇。看好這個產業的話，ETF 可能不是最有效率的工具。\n`;
  }
  md += `\n各檔僅就已揭露之具名持股計算，未揭露的「其他持股」不計入對齊權重。\n\n`;
  md += `⚠️ 本回答為持股結構分析，不構成投資建議；持股資料以 ${d.as_of} 快照為準。`;
  return md;
}

const nf = (n) => Number(n).toLocaleString("en-US");

function buildPenetrationMarkdown(d) {
  const f = d.focus;
  let md = `### 穿透結果（資料快照 ${d.as_of}）\n\n`;
  if (d.unknown_tickers && d.unknown_tickers.length) {
    md += `> ⚠️ 已略過快照中不存在的 ETF：${d.unknown_tickers.join("、")}。\n\n`;
  }
  md += `你投入 **${d.etf_count} 檔 ETF**、共 **NT$${nf(d.total_invest)}**。`;
  md += `穿透到個股後：\n\n`;
  md += `> **${f.stock_name} 是你最大的單一曝險：NT$${nf(f.exposure_twd)}，占 ${f.exposure_pct}%。**\n\n`;

  md += `| ETF | ${f.stock_name} 權重 | 投入 | 貢獻曝險 |\n|---|--:|--:|--:|\n`;
  f.by_etf.forEach((e) => {
    md += `| ${e.etf} ${e.etf_name} | ${e.weight_pct}% | ${nf(e.invest)} | ${nf(e.exposure_twd)} |\n`;
  });

  md += `\n**穿透後前五大個股曝險**\n\n| 個股 | 產業 | 曝險 | 占比 |\n|---|---|--:|--:|\n`;
  const top5 = d.stocks.filter((s) => s.stock_ticker !== "_OTHER").slice(0, 5);
  top5.forEach((s) => {
    md += `| ${s.stock_name} | ${s.sector} | NT$${nf(s.exposure_twd)} | ${s.exposure_pct}% |\n`;
  });
  // 其餘所有個股（含未個別揭露的「其他持股」）合計一列，讓穿透表補滿 100%
  const top5Set = new Set(top5.map((s) => s.stock_ticker));
  const rest = d.stocks.filter((s) => !top5Set.has(s.stock_ticker));
  if (rest.length) {
    const restTwd = rest.reduce((a, s) => a + s.exposure_twd, 0);
    const restPct = Math.round((restTwd / d.total_invest) * 1000) / 10;
    md += `| 其餘 ${rest.length} 檔（含未個別揭露之其他持股） | — | NT$${nf(restTwd)} | ${restPct}% |\n`;
  }

  md += `\n\`\`\`mermaid\n${d.diagram}\n\`\`\`\n\n`;
  md += `⚠️ 持股以 ${d.as_of} 快照為準，數字可由公開成分股重算；本回答為持股結構分析，不構成投資建議。`;
  return md;
}

function buildRankingMarkdown(d) {
  let md = `### ${d.focus_name} 持股排名（資料快照 ${d.as_of}）\n\n`;
  md += `結論：16 檔 ETF 中，對 **${d.focus_name}（${d.focus}）** 持股最重的是 **${d.ranking[0].etf} ${d.ranking[0].etf_name}**，權重 **${d.ranking[0].weight_pct}%**。\n\n`;
  md += `| 排名 | ETF | 類型 | ${d.focus_name} 權重 |\n|---:|---|---|--:|\n`;
  d.ranking.forEach((row, idx) => {
    md += `| ${idx + 1} | ${row.etf} ${row.etf_name} | ${row.is_active ? "主動式" : "被動式"} | ${row.weight_pct}% |\n`;
  });
  md += `\n> 洞察：真正高度集中 ${d.focus_name} 的不是主動式 ETF，而是被動市值型 / 科技型 ETF。`;
  md += `\n\n⚠️ 過去績效不代表未來；持股資料以 ${d.as_of} 快照為準。`;
  return md;
}

async function createChat() {
  // 手冊：chat/create body 是 { title }，回傳 { insertedId }
  const r = await fetch("/api/v1/chat/create", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title: "ETF Passport Demo" }),
  });
  if (!r.ok) throw new Error(`chat/create ${r.status}`);
  const data = await r.json();
  state.chatId = data.insertedId || data.chat_id || data.id;
}

async function streamFromEAP(payload, contentEl) {
  // 手冊驗證契約：body 用 { q, streaming }；SSE 每行 data:{...}，欄位 result 為完整回應，
  // cyphers / rag_chunk_info 為引用來源。result 是累計完整字串，取代即可。
  const r = await fetch(`/api/v1/chat/${state.chatId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ q: payload.question, streaming: true }),
  });
  if (!r.ok || !r.body) throw new Error(`chat ${r.status}`);

  const reader = r.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  let resultText = "";
  let lastObj = null;
  contentEl.classList.add("streaming-caret");
  // EAP 質化查詢可能要數十秒 → 先顯示進度狀態，避免空泡泡看起來像壞掉
  const PROGRESS = {
    analysing: "🧠 分析問題中…", searching: "🔍 檢索知識庫中…",
    "generating answer": "✍️ 生成回答中…", keepAlive: null,
  };
  contentEl.innerHTML = `<p class="msg-progress">⏳ 連線 EAP…</p>`;

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const lines = buf.split("\n");
    buf = lines.pop(); // 保留未完成的最後一行
    for (const line of lines) {
      const raw = parseStreamLine(line);
      if (!raw) continue;
      let obj;
      try { obj = JSON.parse(raw); } catch { continue; }
      lastObj = obj;
      if (obj.error) {
        throw new Error(`${obj.error}: ${obj.detail || ""}`);
      } else if (typeof obj.chunk === "string") {
        // streaming:true 逐字 delta
        resultText += obj.chunk;
        contentEl.innerHTML = renderMarkdown(resultText);
      } else if (typeof obj.result === "string" && obj.result) {
        // 最後一筆為完整 result（取代累計，最權威）
        resultText = obj.result;
        contentEl.innerHTML = renderMarkdown(resultText);
      } else if (obj.progress && !resultText) {
        const label = PROGRESS[obj.progress];
        if (label) contentEl.innerHTML = `<p class="msg-progress">${label}</p>`;
      }
    }
  }
  const raw = parseStreamLine(buf);
  if (raw) {
    try {
      const obj = JSON.parse(raw);
      lastObj = obj;
      if (obj.error) throw new Error(`${obj.error}: ${obj.detail || ""}`);
      if (typeof obj.result === "string" && obj.result) resultText = obj.result;
      else if (typeof obj.chunk === "string") resultText += obj.chunk;
    } catch (err) {
      if (String(err.message || err).includes("EAP upstream")) throw err;
    }
  }
  contentEl.classList.remove("streaming-caret");
  contentEl.innerHTML = renderMarkdown(resultText || "（EAP 無回應內容）");
  await renderMermaidIn(contentEl);
  return citationsFromEAP(lastObj);
}

function parseStreamLine(line) {
  const trimmed = (line || "").trim();
  if (!trimmed || trimmed === "[DONE]") return null;
  const m = trimmed.match(/^data:\s*(.+)$/);
  const raw = m ? m[1].trim() : trimmed;
  return raw === "[DONE]" ? null : raw;
}

// 從 EAP 回應的 cyphers / rag_chunk_info 組引用回鏈
function citationsFromEAP(obj) {
  const cits = [];
  if (!obj) return cits;
  for (const c of obj.cyphers || []) {
    cits.push({ type: "graph", text: c.title || "Graph 查詢" });
  }
  for (const ch of obj.rag_chunk_info || []) {
    const label = `${ch.etf || ""} ${ch.doc_type || ""} p.${ch.page || "?"}`.trim();
    cits.push({ type: "vector", text: label });
  }
  return cits;
}

// ────────────────────────────
// Mock 模式
// ────────────────────────────
function pickMock(question) {
  for (const [key, m] of Object.entries(window.MOCK_RESPONSES)) {
    for (const re of m.trigger) {
      if (new RegExp(re, "i").test(question)) return m;
    }
  }
  return null;
}

async function mockStream(question, contentEl) {
  const mock = pickMock(question) || {
    text: "抱歉，這題我這裡沒有預錄答案；請試試 ⭐ Q-C 穿透、Q-A 排名、Q-B 平準金，或 Q-D 名實 / Q-E 漂綠 / Q-F 看好產業。",
  };
  // 區塊感知逐字顯現（表格 / Mermaid 整塊浮現，散文打字機）
  await streamMarkdown(contentEl, mock.text);
}

function mockCitations(question) {
  const m = pickMock(question);
  return m ? m.citations : [];
}

// ────────────────────────────
// Markdown / Mermaid render
// ────────────────────────────
function renderMarkdown(md) {
  const html = marked.parse(md, { breaks: true });
  return DOMPurify.sanitize(html, {
    ADD_TAGS: ["pre", "code"],
    ADD_ATTR: ["class"],
  });
}

// 逐 token 顯現（打字機效果，模擬 LLM streaming）。區塊感知：
//   - 散文 / 標題 / 引言 → 逐字浮現
//   - 表格 / ```mermaid / ```code → 整塊一次浮現（半截表格/圖很醜）
//   - 全部完成後才渲染 Mermaid
// 全程不碰網路 / EAP，現場 100% 可控。
// 逐字速度（調這裡）：chars=每步顯示幾字、minMs~maxMs=每步間隔。數字越大越慢。
const STREAM = { chars: 2, minMs: 14, maxMs: 30, blockPauseMs: 160 };

async function streamMarkdown(contentEl, md, { mermaid = true } = {}) {
  contentEl.classList.add("streaming-caret");
  const blocks = String(md).split(/\n{2,}/);
  let acc = "";
  for (const block of blocks) {
    if (!block) continue;
    const prefix = acc ? acc + "\n\n" : "";
    const whole = /^\s*\|/.test(block) || /^\s*```/.test(block);
    if (whole) {
      acc = prefix + block;
      contentEl.innerHTML = renderMarkdown(acc);
      scrollToBottom();
      await sleep(STREAM.blockPauseMs);
    } else {
      const tokens = block.match(new RegExp(`[\\s\\S]{1,${STREAM.chars}}`, "g")) || [];
      let cur = "";
      for (const t of tokens) {
        cur += t;
        contentEl.innerHTML = renderMarkdown(prefix + cur);
        scrollToBottom();
        await sleep(STREAM.minMs + Math.random() * (STREAM.maxMs - STREAM.minMs));
      }
      acc = prefix + block;
    }
  }
  contentEl.classList.remove("streaming-caret");
  contentEl.innerHTML = renderMarkdown(acc);
  if (mermaid) await renderMermaidIn(contentEl);
  scrollToBottom();
}

async function renderMermaidIn(container) {
  const blocks = container.querySelectorAll('pre code.language-mermaid, pre > code');
  let i = 0;
  for (const code of blocks) {
    const text = code.textContent;
    if (!text.trim().match(/^(sankey-beta|graph|flowchart|sequenceDiagram|pie|radar|gantt)/m)) continue;
    const wrap = document.createElement("div");
    wrap.className = "mermaid-wrap";
    const pre = code.closest("pre");
    pre.replaceWith(wrap);
    try {
      const { svg } = await window.mermaid.render(`mmd-${state.msgCounter}-${i++}`, text);
      wrap.innerHTML = svg;
    } catch (err) {
      wrap.innerHTML = `<pre class="mmd-err">Mermaid render 失敗：${err.message}</pre><pre class="mmd-err">${escapeHtml(text)}</pre>`;
    }
  }
}

// ────────────────────────────
// 訊息渲染
// ────────────────────────────
function appendUserMessage(text) {
  const div = document.createElement("div");
  div.className = "flex";
  div.innerHTML = `<div class="bubble bubble-user">${escapeHtml(text)}</div>`;
  $("#messages").appendChild(div);
  scrollToBottom();
}

function appendBotMessage(text, citations = []) {
  const wrap = appendBotPlaceholder();
  wrap.content.innerHTML = renderMarkdown(text);
  finalizeBot(wrap.bubble, wrap.content, wrap.actions, citations);
}

function appendBotPlaceholder() {
  state.msgCounter++;
  const wrap = document.createElement("div");
  wrap.className = "flex";
  wrap.innerHTML = `
    <div class="bubble bubble-bot w-full">
      <div class="content"></div>
      <div class="bubble-actions"></div>
    </div>
  `;
  $("#messages").appendChild(wrap);
  scrollToBottom();
  return {
    bubble: wrap,
    content: wrap.querySelector(".content"),
    actions: wrap.querySelector(".bubble-actions"),
  };
}

function finalizeBot(bubble, content, actions, citations) {
  // 複製按鈕（鐵則：每則回覆要有「複製」按鈕）
  actions.innerHTML = `
    <button class="copy-btn">📋 複製</button>
    <button class="bookmark-btn">⭐ 收藏</button>
    <span class="cite-count">引用 ${citations.length} 條</span>
  `;
  actions.querySelector(".copy-btn").addEventListener("click", async () => {
    const btn = actions.querySelector(".copy-btn");
    const ok = await copyText(content.innerText);
    btn.textContent = ok ? "✓ 已複製" : "⚠️ 請手動選取複製";
    setTimeout(() => (btn.textContent = "📋 複製"), 1500);
  });
  actions.querySelector(".bookmark-btn").addEventListener("click", () => {
    actions.querySelector(".bookmark-btn").textContent = "⭐ 已收藏";
  });
  showCitations(citations);
}

function showCitations(citations) {
  const wrap = $("#citations");
  wrap.innerHTML = "";
  if (!citations.length) {
    // 清空避免殘留上一題的引用（面板永遠對應最新一則回覆）
    wrap.innerHTML = `<p class="empty-hint">此回覆無引用來源。</p>`;
    return;
  }
  for (const c of citations) {
    const div = document.createElement("div");
    div.className = `citation-card ${c.type || ""}`;
    const labelMap = { hybrid: "🧬 HYBRID", graph: "🔗 GRAPH", vector: "📄 VECTOR", regulatory: "⚖️ 法規", data: "📊 資料源", ai: "🤖 AI 生成", warning: "⚠️ 提醒" };
    div.innerHTML = `
      <div class="cite-type">${labelMap[c.type] || c.type}</div>
      <div class="cite-text">${escapeHtml(c.text || "")}</div>
      ${c.url ? `<a href="${c.url}" target="_blank" class="cite-link">來源連結 →</a>` : ""}
    `;
    wrap.appendChild(div);
  }
}

// ────────────────────────────
// utils
// ────────────────────────────
function escapeHtml(s) {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// 複製到剪貼簿，永不丟未捕捉錯誤：優先 Clipboard API，失敗退到 execCommand。
async function copyText(text) {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch (_) { /* 落到 execCommand 後備 */ }
  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    return ok;
  } catch (_) {
    return false;
  }
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function scrollToBottom() {
  const m = $("#messages");
  m.scrollTop = m.scrollHeight;
}

init();
