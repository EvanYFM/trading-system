const state = {
  data: null,
  date: null,
  view: "overview",
  query: "",
  symbol: "all",
  sector: "all",
  direction: "all",
  detailQuery: "",
  detailSector: "all",
  activeSymbol: null,
  historySymbol: null,
  railCollapsed: false,
  manifest: null,
  decisions: [],
  activeDecisionId: null,
  decisionSector: "all",
  decisionSymbol: "all",
  decisionPage: 1,
  decisionQuery: "",
  editingObservationId: null,
  history: null,
  // state.historySymbol 已被「历史回看」页面占用，此处必须用独立字段名
  historyJournalSymbol: null,
  ctaQuery: "",
  ctaSector: "all",
  ctaDirection: "all",
  activeCtaSymbol: null,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[char]));
const numeric = (value) => Number(value || 0);
const signClass = (value) => numeric(value) > 0 ? "bull-text" : numeric(value) < 0 ? "bear-text" : "neutral-text";
const dirClass = (value) => numeric(value) >= 0 ? "bullish" : "bearish";
const formatSigned = (value, digits = 0) => `${numeric(value) > 0 ? "+" : ""}${numeric(value).toLocaleString("zh-CN", {maximumFractionDigits: digits, minimumFractionDigits: digits})}`;
const formatAmount = (value) => `${formatSigned(numeric(value) / 1e8, 2)} 亿`;
const formatHands = (value) => formatSigned(value, 0);
const formatDate = (date) => `${date.slice(0,4)}.${date.slice(4,6)}.${date.slice(6)}`;
const sourceFileDate = (name) => {
  const match = String(name || "").match(/(\d{8})/);
  return match ? formatDate(match[1]) : "无数据";
};
const formatAxisAmount = (value) => numeric(value) === 0 ? "0" : `${formatSigned(numeric(value) / 1e8, 1)}亿`;
const currentSnapshot = () => state.data.snapshots[state.date];
const DETAIL_SEARCH_ALIASES = { FU: "燃油", AG: "白银", JM: "焦煤", I: "铁矿石", LH: "生猪", LC: "碳酸锂", JD: "鸡蛋", P: "棕榈油", RU: "天然橡胶" };
const CORE_GROUPS = [
  ["贵金属", ["AU", "AG"]],
  ["有色金属", ["SN", "LC"]],
  ["能源化工", ["FU"]],
  ["黑色系", ["JM", "I"]],
  ["家人品种", ["FG", "SA", "AO", "SH"]],
  ["农产品", ["M", "JD", "LH", "P", "RU"]],
];
const DECISION_STORAGE_KEY = "futuresResearchDecisions.v1";

function loadDecisions() {
  try { return JSON.parse(localStorage.getItem(DECISION_STORAGE_KEY) || "[]"); }
  catch { return []; }
}

function saveDecisions() {
  localStorage.setItem(DECISION_STORAGE_KEY, JSON.stringify(state.decisions));
}

function brokerGroupLabel(entry) {
  if (entry.broker === "中信期货") return "亏损机构（特殊）";
  return entry.displayGroup || ({内资: "机构", 外资: "外资", 家人: "家人"}[entry.group] || entry.group);
}

function seatChanges(entry) {
  const longChange = entry.longChange == null ? numeric(entry.addLong) - numeric(entry.reduceLong) : numeric(entry.longChange);
  const shortChange = entry.shortChange == null ? numeric(entry.addShort) - numeric(entry.reduceShort) : numeric(entry.shortChange);
  const netChange = longChange - shortChange;
  if (!netChange) return `<span>持平 0</span>`;
  const actions = netChange > 0
    ? [["加多", Math.max(longChange, 0)], ["减空", Math.max(-shortChange, 0)]]
    : [["减多", Math.max(-longChange, 0)], ["加空", Math.max(shortChange, 0)]];
  const label = actions.sort((left, right) => right[1] - left[1])[0][0];
  return `<span class="${netChange > 0 ? "bull-text" : "bear-text"}">${label} ${formatSigned(netChange)}</span>`;
}

function rankingDominance(items) {
  const totals = items.reduce((sum, entry) => {
    sum[entry.group === "家人" ? "family" : "institution"] += Math.abs(numeric(entry.netPosition));
    return sum;
  }, {institution: 0, family: 0});
  return totals.family > totals.institution ? "家人为主" : "机构为主";
}

function maxAbs(items, getter) {
  return Math.max(1, ...items.map((item) => Math.abs(numeric(getter(item)))));
}

function renderDateControls() {
  /* 日期切换已改为顶栏日历(见 index.html 内联脚本);此处仅同步按钮文本 */
  const dateText = document.getElementById("dateText");
  if (dateText && state.date) dateText.textContent = formatDate(state.date);
  if (typeof window.initCalendar === "function") window.initCalendar(state.data.dates || [], state.date);
}

function summaryCard(label, value, note, tone = "") {
  return `<article class="summary-card"><div class="summary-label">${label}</div><div class="summary-value ${tone}">${value}</div><div class="summary-note">${note}</div></article>`;
}

function renderSummary() {
  const snapshot = currentSnapshot();
  const summary = snapshot.summary;
  const bull = summary.strongestBullish;
  const bear = summary.strongestBearish;
  $("#summaryStrip").innerHTML = [
    summaryCard("三方净方向", `${summary.bullishCount} 多 / ${summary.bearishCount} 空`, `商品样本 ${summary.instrumentCount} 个，按保证金金额判断`),
    summaryCard("强共振品种", summary.tripleCount, "内外资同向且家人反向后确认", summary.tripleCount ? "bull-text" : "neutral-text"),
    summaryCard("内外资同向", summary.domesticForeignSameCount || 0, `家人反向确认 ${summary.familyReverseCount || 0} 个`),
    summaryCard("最强净多", bull ? `${bull.variety} ${bull.symbol}` : "暂无", bull ? formatAmount(bull.amountSignal) : "今日无净多品种", "bull-text"),
    summaryCard("最强净空", bear ? `${bear.variety} ${bear.symbol}` : "暂无", bear ? formatAmount(bear.amountSignal) : "今日无净空品种", "bear-text"),
    summaryCard("保证金覆盖", `${(summary.marginCoverage * 100).toFixed(0)}%`, `${summary.marginSourceUpdate || "来源时间未披露"} · ${summary.marginCacheNote || "状态未知"}`),
  ].join("");
  const latestDisclosure = snapshot.disclosureDates.at(-1) || "未披露";
  const delayed = latestDisclosure.replaceAll("-", "") !== state.date;
  const badge = $("#freshnessBadge");
  badge.textContent = delayed ? `披露滞后 ${latestDisclosure}` : `披露已同步 ${latestDisclosure}`;
  badge.classList.toggle("is-stale", delayed);
}

function renderFocus() {
  const triples = [...currentSnapshot().tripleResonance];
  const bullish = triples.filter((item) => numeric(item.amountSignal) > 0).sort((a, b) => numeric(b.amountSignal) - numeric(a.amountSignal)).slice(0, 5);
  const bearish = triples.filter((item) => numeric(item.amountSignal) < 0).sort((a, b) => numeric(a.amountSignal) - numeric(b.amountSignal)).slice(0, 5);
  const items = [...bullish, ...bearish];
  if (!items.length) {
    $("#resonanceFocus").innerHTML = `<div class="detail-empty">今天没有满足三方强共振条件的商品品种。</div>`;
    return;
  }
  const scale = maxAbs(items, (item) => item.amountSignal);
  $("#resonanceFocus").innerHTML = items.map((item) => {
    const tone = dirClass(item.amountSignal);
    const width = Math.max(6, Math.abs(item.amountSignal) / scale * 100);
    const quote = item.quote;
    return `<button class="focus-card ${tone}" data-open-symbol="${escapeHtml(item.symbol)}">
      <div class="focus-head"><span class="focus-name">${escapeHtml(item.variety)}</span><span class="focus-code">${escapeHtml(item.symbol)}</span></div>
      <div class="focus-amount ${signClass(item.amountSignal)}">${formatAmount(item.amountSignal)}</div>
      <div class="focus-sub">三方手数 ${formatHands(item.handsSignal)} 手 · ${escapeHtml(item.marginalStructure || "边际待判")}</div>
      <div class="signal-track"><span class="signal-fill ${tone}" style="width:${width}%"></span></div>
      <div class="focus-tags"><span class="tag ${tone}">${escapeHtml(item.resonance.label || item.direction)}</span>${quote ? `<span class="tag ${dirClass(quote.changePct)}">${formatSigned(quote.changePct, 2)}%</span>` : ""}${item.trend ? `<span class="tag">趋势 ${escapeHtml(item.trend.temperature || "-")}${item.trend.fresh ? "" : "（旧）"}</span>` : ""}</div>
    </button>`;
  }).join("");
}

function renderTide() {
  const buckets = currentSnapshot().tide || [];
  $("#tideGrid").innerHTML = buckets.map((bucket, index) => {
    const tone = index === 0 || index === 1 ? "bullish" : "bearish";
    const rows = bucket.items.map((item) => `<button class="tide-row" data-open-symbol="${escapeHtml(item.symbol)}">
      <span><strong>${escapeHtml(item.variety)}</strong><small>${escapeHtml(item.symbol)} · ${escapeHtml(item.structure || "边际待判")}</small></span>
      <span class="tide-return ${signClass(item.changePct)}">${formatSigned(item.changePct, 2)}%</span>
      <span class="tide-amount ${signClass(item.amount)}">${formatAmount(item.amount)}</span>
    </button>`).join("");
    return `<article class="tide-block ${tone}"><header><span>${escapeHtml(bucket.label)}</span><strong>${bucket.count}</strong></header><div>${rows || `<p class="empty-side">该象限暂无品种</p>`}</div></article>`;
  }).join("");
}

/* 四 净持仓分布变化：全商品按当日资金净流入/流出排序取前五（剔除股指/国债） */
function renderNetFlowChanges() {
  const items = currentSnapshot().instruments
    .filter((item) => {
      const flow = numeric(item.marketFlow?.capitalFlow);
      const sector = String(item.sector || "");
      return item.marketFlow && flow !== 0 && !sector.includes("股指") && !sector.includes("国债");
    })
    .sort((a, b) => numeric(b.marketFlow.capitalFlow) - numeric(a.marketFlow.capitalFlow));
  const fresh = items.filter((item) => item.marketFlow.fresh !== false);
  const pool = fresh.length >= 10 ? fresh : items;
  if (!pool.length) {
    $("#netFlowGrid").innerHTML = `<div class="detail-empty">该日期缺少资金净流动数据（marketFlow 未覆盖）。</div>`;
    return;
  }
  const topLong = pool.slice(0, 5);
  const topShort = pool.slice(-5).reverse();
  const side = (list, title, cls) => `<div class="sector-side"><div class="side-title ${cls}">${title}</div>${list.map((item) => `
    <button class="sector-item" data-open-symbol="${escapeHtml(item.symbol)}" aria-label="查看${escapeHtml(item.variety)}详情">
      <span class="sector-item-name">${escapeHtml(item.variety)} <small>${escapeHtml(item.symbol)}</small></span>
      <span class="${signClass(item.marketFlow.capitalFlow)}"><small>资金</small><strong>${(numeric(item.marketFlow.capitalFlow) / 1e8).toLocaleString("zh-CN", {maximumFractionDigits: 2})} 亿</strong></span>
      <span class="${signClass(item.quote?.changePct)}"><small>涨跌</small><strong>${formatSigned(item.quote?.changePct, 2)}%</strong></span>
    </button>`).join("")}</div>`;
  $("#netFlowGrid").innerHTML = `<article class="sector-block netflow-block">
    <div class="sector-title"><strong>当日资金净流动</strong><span class="sector-count">口径：${escapeHtml(pool[0].marketFlow.source || "同花顺/AKShare 资金流")}</span></div>
    <div class="sector-sides">
      ${side(topLong, "净流入前五", "bull-text")}
      ${side(topShort, "净流出前五", "bear-text")}
    </div>
  </article>`;
}

/* 五 席位大资金动向：外资/内资两组，各成员席位前五流多/流空的并集（build 预计算 seatFlow） */
/* 席位大资金动向：金额口径（qhkch「净实值变化」，汇总后排序前五） */
function seatFlowSide(group, side) {
  const list = group?.[side] || [];
  if (!list.length) return `<p class="empty-side">该方向暂无席位入选</p>`;
  const scale = Math.max(...list.map((item) => Math.abs(item.netAmount || 0)), 1);
  return list.map((item) => `<button class="sector-item" data-open-symbol="${escapeHtml(item.symbol)}" aria-label="查看${escapeHtml(item.variety)}详情">
    <span class="sector-item-name">${escapeHtml(item.variety)} <small>${escapeHtml(item.symbol)}</small><em class="seatflow-brokers">${escapeHtml((item.brokers || []).join(" / "))}</em></span>
    <span class="sector-meter"><span class="sector-meter-fill ${item.netAmount > 0 ? "bull-text" : "bear-text"}" style="width:${Math.max(5, Math.abs(item.netAmount) / scale * 100)}%"></span></span>
    <strong class="${signClass(item.netAmount)}">${(item.netAmount / 1e8).toLocaleString("zh-CN", {maximumFractionDigits: 2})} 亿</strong>
  </button>`).join("");
}

function renderSeatFlow() {
  const seatFlow = currentSnapshot().seatFlow;
  if (!seatFlow) {
    $("#seatFlowGrid").innerHTML = `<div class="detail-empty">该日期缺少席位净流数据（scripts/fetch_seat_flow.py 未覆盖），缺失不回填旧日值。</div>`;
    return;
  }
  const block = (label, group, note) => `<article class="sector-block seatflow-block">
    <div class="sector-title"><strong>${label}</strong><span class="sector-count">${escapeHtml((group?.brokers || []).length ? `已覆盖：${(group.brokers || []).join(" / ")}` : note)}</span></div>
    <div class="sector-sides">
      <div class="sector-side"><div class="side-title bull-text">净流多前五（汇总金额）</div>${seatFlowSide(group, "topLong")}</div>
      <div class="sector-side"><div class="side-title bear-text">净流空前五（汇总金额）</div>${seatFlowSide(group, "topShort")}</div>
    </div>
  </article>`;
  $("#seatFlowGrid").innerHTML =
    block("外资席位", seatFlow.foreign, "高盛期货 / 瑞银期货 / 摩根大通") +
    block("内资席位", seatFlow.domestic, "国泰君安 / 东证 / 永安 / 中财 / 东吴");
}

function coreItems() {
  const indexed = new Map(currentSnapshot().instruments.map((item) => [item.symbol, item]));
  return CORE_GROUPS.map(([sector, symbols]) => ({
    sector,
    items: symbols.map((symbol) => indexed.get(symbol)).filter(Boolean),
  })).filter((group) => group.items.length);
}

function renderCorePanorama() {
  const groups = coreItems();
  if (!groups.length) {
    $("#corePanorama").innerHTML = `<div class="detail-empty">该快照没有可用重点品种。</div>`;
    return;
  }
  $("#corePanorama").innerHTML = `<div class="panorama-head panorama-head-v5"><span>板块</span><span>品种 / 行情</span><span class="num">5日</span><span class="num">10日</span><span class="num">30日</span><span>三方净变动</span><span>内资 / 外资 / 家人反向</span><span>趋势与信号</span></div>${groups.map((group) => `<section class="panorama-group"><header>${escapeHtml(group.sector)}</header><div class="panorama-group-rows">${group.items.map((item) => {
    const quote = item.quote;
    const mf = item.marketFlow || {};
    const r5 = computeReturn5d(item.symbol);
    const r10 = mf.return10d;
    const r30 = mf.return30d;
    const state = trendStateByReturn(r5);
    const rCell = (v) => v == null ? `<span class="num gray">—</span>` : `<span class="num ${v > 0 ? "bull-text" : v < 0 ? "bear-text" : "neutral-text"}">${formatSigned(v, 2)}%</span>`;
    return `<button class="panorama-row panorama-row-v5" data-open-symbol="${escapeHtml(item.symbol)}">
      <span class="panorama-name"><strong>${escapeHtml(item.variety)} ${escapeHtml(item.symbol)}</strong><small>${escapeHtml(item.sector)} · ${escapeHtml(quote?.contract || item.margin.contract || "主力待披露")}</small>${quote ? `<em>${numeric(quote.close).toLocaleString("zh-CN", {maximumFractionDigits:4})} <b class="${signClass(quote.changePct)}">${formatSigned(quote.changePct, 2)}%</b></em>` : `<em>行情暂无</em>`}</span>
      <span>${rCell(r5)}</span>
      <span>${rCell(r10)}</span>
      <span>${rCell(r30)}</span>
      <span class="panorama-signal"><strong class="${signClass(item.amountSignal)}">${formatAmount(item.amountSignal)}</strong><small class="${signClass(item.handsSignal)}">${formatHands(item.handsSignal)} 手 · ${escapeHtml(item.marginalStructure || "边际待判")}</small></span>
      <span>${groupBars(item)}</span>
      <span class="panorama-tags">${trendChip(item.trend)}<span class="tag ${dirClass(item.amountSignal)}">${escapeHtml(item.resonance.label || item.direction)}</span><span class="trend-state trend-state-${state.cls}">${escapeHtml(state.label)}</span></span>
    </button>`;
  }).join("")}</div></section>`).join("")}`;
}

function brokerSide(items, side) {
  if (!items?.length) return `<p class="empty-side">今天没有净${side === "bullish" ? "多" : "空"}贡献</p>`;
  const scale = maxAbs(items, (item) => item.displayAmount);
  return items.map((item) => `<button class="broker-highlight-row" data-open-symbol="${escapeHtml(item.symbol)}">
    <span><strong>${escapeHtml(item.broker)}（${escapeHtml(brokerGroupLabel(item))}）</strong><small>${escapeHtml(item.variety)} ${escapeHtml(item.symbol)}</small></span>
    <span class="sector-meter"><span class="sector-meter-fill ${dirClass(item.displayAmount)}" style="width:${Math.max(4, Math.abs(item.displayAmount) / scale * 100)}%"></span></span>
    <strong class="${signClass(item.displayAmount)}">${formatAmount(item.displayAmount)}</strong>
  </button>`).join("");
}

function renderBrokerHighlights() {
  const groups = currentSnapshot().brokerHighlights || {};
  const names = ["内资", "外资", "家人"];
  $("#brokerHighlights").innerHTML = names.map((name) => {
    const data = groups[name] || {bullish: [], bearish: []};
    const label = name === "家人" ? "家人反向" : name;
    return `<article class="broker-highlight"><header><strong>${label}</strong><small>${name === "家人" ? "原始方向已取反" : "正向资金"}</small></header><div class="broker-highlight-sides"><section><h3 class="bull-text">净多贡献</h3>${brokerSide(data.bullish, "bullish")}</section><section><h3 class="bear-text">净空贡献</h3>${brokerSide(data.bearish, "bearish")}</section></div></article>`;
  }).join("");
}

function renderWeather() {
  const rows = currentSnapshot().weather.slice(0, 7);
  $("#weatherList").innerHTML = rows.length ? rows.map((item) => `<div class="weather-row">
    <div><strong>${escapeHtml(item.variety)}</strong><br><small>${escapeHtml(item.window)} · ${escapeHtml(item.date)}</small></div>
    <div><span class="risk-level ${escapeHtml(item.level)}">${item.level === "high" ? "高风险" : item.level === "medium" ? "中风险" : "低风险"}</span><br><small>${escapeHtml(item.origins)}</small></div>
    <div class="weather-reason">${escapeHtml(item.types)} · ${escapeHtml(item.reason)}</div>
    <div class="weather-reflection">盘面：${escapeHtml(item.reflection || "待验证")}</div>
  </div>`).join("") : `<div class="detail-empty">该快照没有可用农业天气风险数据。</div>`;
}

function renderStockIndices() {
  const rows = currentSnapshot().stockIndices;
  $("#stockIndexList").innerHTML = rows.length ? rows.map((item) => `<div class="index-row">
    <div class="index-name"><strong>${escapeHtml(item.variety)}</strong><small>${escapeHtml(item.symbol)}${item.trend ? ` · 趋势${escapeHtml(item.trend.temperature || "-")}${item.trend.fresh ? "" : "（旧）"}` : ""}</small></div>
    <div class="index-change"><small>当日涨跌</small><strong class="${item.quote?.changePct == null ? "" : signClass(item.quote.changePct)}">${item.quote?.changePct == null ? "暂无" : `${formatSigned(item.quote.changePct, 2)}%`}</strong></div>
    <div class="index-value ${item.hasFuturesFlow ? signClass(item.amountSignal) : ""}"><small>三方资金</small><strong>${item.hasFuturesFlow ? formatAmount(item.amountSignal) : "无期货席位流"}</strong></div>
  </div>`).join("") : `<div class="detail-empty">该快照没有独立股指数据。</div>`;
}

function renderOverviewStatus() {
  const snapshot = currentSnapshot();
  const summary = snapshot.summary;
  const latestDisclosure = snapshot.disclosureDates.at(-1) || "未披露";
  $("#overviewStatus").innerHTML = [
    ["席位披露", latestDisclosure, `${summary.instrumentCount} 个商品品种`],
    ["收盘行情", sourceFileDate(summary.quoteSourceFile), `${summary.quoteFreshCount}/${summary.instrumentCount} 与报告日同日 · ${summary.quoteSource || "来源未披露"}`],
    ["趋势快照", sourceFileDate(summary.trendSourceFile), `${summary.trendFreshCount}/${summary.instrumentCount} 与报告日同日 · 趋势动物`],
    ["保证金", `${(summary.marginCoverage * 100).toFixed(0)}% 覆盖`, summary.marginSourceUpdate || "更新时间未披露"],
    ["期现基差", `${summary.basisCoveredCount || 0} 个`, sourceFileDate(summary.basisSourceFile)],
    ["仓单数据", `${summary.warehouseCoveredCount || 0} 个`, sourceFileDate(summary.warehouseSourceFile)],
  ].map(([label, value, note]) => `<article><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong><small>${escapeHtml(note)}</small></article>`).join("");
}

function filteredInstruments() {
  const query = state.query.trim().toLowerCase();
  return currentSnapshot().instruments.filter((item) => {
    const queryMatch = !query || item.variety.toLowerCase().includes(query) || item.symbol.toLowerCase().includes(query);
    const symbolMatch = state.symbol === "all" || item.symbol === state.symbol;
    const sectorMatch = state.sector === "all" || item.sector === state.sector;
    const directionMatch = state.direction === "all" || (state.direction === "bullish" ? item.amountSignal > 0 : item.amountSignal < 0);
    return queryMatch && symbolMatch && sectorMatch && directionMatch;
  });
}

function renderSectorFilter() {
  const instruments = [...currentSnapshot().instruments].sort((a, b) => a.sector.localeCompare(b.sector, "zh-CN") || a.variety.localeCompare(b.variety, "zh-CN"));
  if (state.symbol !== "all" && !instruments.some((item) => item.symbol === state.symbol)) state.symbol = "all";
  $("#symbolFilter").innerHTML = `<option value="all">全部品种</option>${instruments.map((item) => `<option value="${escapeHtml(item.symbol)}" ${state.symbol === item.symbol ? "selected" : ""}>${escapeHtml(item.variety)} ${escapeHtml(item.symbol)}</option>`).join("")}`;
  const sectors = [...new Set(currentSnapshot().instruments.map((item) => item.sector))].sort();
  $("#sectorFilter").innerHTML = `<option value="all">全部板块</option>${sectors.map((sector) => `<option value="${escapeHtml(sector)}" ${state.sector === sector ? "selected" : ""}>${escapeHtml(sector)}</option>`).join("")}`;
}

function renderDetailFilter() {
  const covered = [...currentSnapshot().instruments].sort((a, b) => a.sector.localeCompare(b.sector, "zh-CN") || a.variety.localeCompare(b.variety, "zh-CN"));
  const sectors = [...new Set(covered.map((item) => item.sector))].sort();
  $("#detailSearchInput").value = state.detailQuery;
  $("#detailSectorFilter").innerHTML = `<option value="all">全部板块</option>${sectors.map((sector) => `<option value="${escapeHtml(sector)}" ${state.detailSector === sector ? "selected" : ""}>${escapeHtml(sector)}</option>`).join("")}`;
  const query = state.detailQuery.trim().toLowerCase();
  const matches = covered.filter((item) => {
    const aliases = DETAIL_SEARCH_ALIASES[item.symbol] || "";
    const queryMatch = !query || item.variety.toLowerCase().includes(query) || item.symbol.toLowerCase().includes(query) || aliases.toLowerCase().includes(query);
    return queryMatch && (state.detailSector === "all" || item.sector === state.detailSector);
  });
  if (matches.length && !matches.some((item) => item.symbol === state.activeSymbol)) state.activeSymbol = matches[0].symbol;
  $("#detailSymbolFilter").innerHTML = matches.length
    ? matches.map((item) => `<option value="${escapeHtml(item.symbol)}" ${item.symbol === state.activeSymbol ? "selected" : ""}>${escapeHtml(item.variety)} ${escapeHtml(item.symbol)} · ${escapeHtml(item.sector)}</option>`).join("")
    : `<option value="">当前条件下没有品种</option>`;
}

function groupBars(item) {
  const values = [item.groups.domestic.amount, item.groups.foreign.amount, item.groups.familyReverse.amount];
  const labels = ["内资", "外资", "家反"];
  const max = Math.max(1, ...values.map((value) => Math.abs(value)));
  return `<div class="group-bars">${values.map((value, index) => `<div class="group-line"><label>${labels[index]}</label><span class="micro-track"><span class="micro-fill ${dirClass(value)}" style="width:${Math.max(3, Math.abs(value) / max * 100)}%"></span></span><output class="${signClass(value)}">${formatAmount(value)}</output></div>`).join("")}</div>`;
}

function trendChip(trend) {
  if (!trend) return `<span class="trend-chip">无数据</span>`;
  const bullish = ["温", "热", "沸"].includes(trend.temperature);
  const bearish = ["凉", "寒", "冻"].includes(trend.temperature);
  const tone = bullish ? "bullish" : bearish ? "bearish" : "";
  return `<span class="trend-chip ${tone} ${trend.fresh ? "" : "is-stale"}">${escapeHtml(trend.temperature || "-")} · ${formatSigned(trend.strength, 0)}${trend.fresh ? "" : "（旧）"}</span>`;
}

function renderInstrumentTable() {
  renderSectorFilter();
  const rows = filteredInstruments();
  if (!state.activeSymbol || !rows.some((item) => item.symbol === state.activeSymbol)) state.activeSymbol = rows[0]?.symbol || null;
  $("#instrumentRows").innerHTML = rows.map((item) => {
    const close = item.quote?.close;
    const dayReturn = item.quote?.changePct;
    const closeCell = close == null ? `<span class="gray">暂无</span>` : `${numeric(close).toLocaleString("zh-CN", {maximumFractionDigits: 4})}<span class="${dayReturn == null ? "gray" : signClass(dayReturn)}" style="margin-left:6px">${dayReturn == null ? "—" : `${formatSigned(dayReturn, 2)}%`}</span>`;
    return `<tr class="${item.symbol === state.activeSymbol ? "is-active" : ""}" data-symbol="${escapeHtml(item.symbol)}">
    <td><div class="instrument-name"><button type="button" data-open-detail-symbol="${escapeHtml(item.symbol)}">${escapeHtml(item.variety)}</button><small>${escapeHtml(item.symbol)} · ${escapeHtml(item.sector)}</small></div></td>
    <td class="num">${closeCell}</td>
    <td class="num ${signClass(item.handsSignal)}">${formatHands(item.handsSignal)}</td>
    <td class="num ${signClass(item.amountSignal)}">${formatAmount(item.amountSignal)}</td>
    <td>${groupBars(item)}</td>
    <td class="trend-cell">${trendChip(item.trend)}</td>
    <td><span class="tag ${dirClass(item.amountSignal)}">${escapeHtml(item.resonance.label || item.direction)}</span></td>
  </tr>`;
  }).join("") || `<tr><td colspan="7" class="detail-empty">当前筛选条件下没有品种。</td></tr>`;
}

function seriesFor(symbol) {
  return state.data.dates.filter((date) => date <= state.date).reverse().map((date) => {
    const snapshot = state.data.snapshots[date];
    if (!snapshot) return null; /* 历史快照可能尚未由后台补载完成 */
    const item = snapshot.instruments.find((entry) => entry.symbol === symbol);
    return item ? {
      date,
      hands: item.handsSignal,
      amount: item.amountSignal,
      close: item.quote?.close ?? null,
      changePct: item.quote?.changePct ?? null,
      structure: item.marginalStructure || "边际待判",
      trend: item.trend || null,
      basis: item.fundamentals?.basis?.at(-1) ?? null,
      warehouseReceipt: item.fundamentals?.warehouseReceipt?.at(-1) ?? null,
    } : null;
  }).filter(Boolean);
}

function sparkline(values, tone = "bullish", large = false, dates = [], prices = []) {
  if (!values.length) return "";
  const width = large ? 720 : 280;
  const height = large ? 220 : 72;
  const padding = large ? {top: 18, right: 16, bottom: 28, left: 64} : {top: 6, right: 6, bottom: 6, left: 6};
  const max = Math.max(...values, 0);
  const min = Math.min(...values, 0);
  const range = max - min || 1;
  const points = values.map((value, index) => {
    const x = padding.left + (values.length === 1 ? 0 : index / (values.length - 1) * (width - padding.left - padding.right));
    const y = padding.top + (max - value) / range * (height - padding.top - padding.bottom);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  const yFor = (value) => padding.top + (max - value) / range * (height - padding.top - padding.bottom);
  const zeroY = yFor(0);
  if (!large) return `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="历史净变化曲线"><line class="spark-axis" x1="0" x2="${width}" y1="${zeroY}" y2="${zeroY}"></line><polyline class="spark-line ${tone}" points="${points}"></polyline></svg>`;
  const ticks = [...new Set([max, 0, min])];
  const grid = ticks.map((tick) => `<g><line class="${tick === 0 ? "spark-zero" : "spark-grid"}" x1="${padding.left}" x2="${width - padding.right}" y1="${yFor(tick)}" y2="${yFor(tick)}"></line><text class="spark-label" x="${padding.left - 9}" y="${yFor(tick) + 4}" text-anchor="end">${formatAxisAmount(tick)}</text></g>`).join("");
  const firstDate = dates[0] ? formatDate(dates[0]) : "";
  const lastDate = dates.at(-1) ? formatDate(dates.at(-1)) : "";
  const validPrices = prices.map((value, index) => value == null ? null : [index, numeric(value)]).filter(Boolean);
  const priceValues = validPrices.map(([, value]) => value);
  const priceMax = priceValues.length ? Math.max(...priceValues) : 0;
  const priceMin = priceValues.length ? Math.min(...priceValues) : 0;
  const priceRange = priceMax - priceMin || 1;
  const pricePoints = validPrices.map(([index, value]) => `${(padding.left + (values.length === 1 ? 0 : index / (values.length - 1) * (width - padding.left - padding.right))).toFixed(1)},${(padding.top + (priceMax - value) / priceRange * (height - padding.top - padding.bottom)).toFixed(1)}`).join(" ");
  const priceLayer = priceValues.length ? `<text class="spark-label spark-price-label" x="${width - padding.right + 9}" y="${padding.top + 4}">${formatPrice(priceMax)}</text><text class="spark-label spark-price-label" x="${width - padding.right + 9}" y="${height - padding.bottom + 4}">${formatPrice(priceMin)}</text><polyline class="spark-price-line" points="${pricePoints}"></polyline>` : "";
  return `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="历史资金净变动与收盘价曲线，左轴为资金净变动金额，右轴为收盘价">${grid}<line class="spark-y-axis" x1="${padding.left}" x2="${padding.left}" y1="${padding.top}" y2="${height - padding.bottom}"></line><polyline class="spark-line ${tone}" points="${points}"></polyline>${priceLayer}<text class="spark-label" x="${padding.left}" y="${height - 7}">${firstDate}</text><text class="spark-label" x="${width - padding.right}" y="${height - 7}" text-anchor="end">${lastDate}</text></svg>`;
}

function formatPrice(value) {
  return value == null ? "暂无" : numeric(value).toLocaleString("zh-CN", {maximumFractionDigits: 4});
}

function flowAction(group) {
  const longAction = numeric(group.longChange) > 0 ? "加多" : numeric(group.longChange) < 0 ? "减多" : "多头未变";
  const shortAction = numeric(group.shortChange) > 0 ? "加空" : numeric(group.shortChange) < 0 ? "减空" : "空头未变";
  return `${longAction} · ${shortAction}`;
}

function positionVisual(value, scale) {
  const width = Math.max(3, Math.abs(numeric(value)) / Math.max(1, scale) * 50);
  return `<span class="position-visual"><span class="position-track"><span class="position-axis"></span><span class="position-fill ${dirClass(value)}" style="width:${width}%;${numeric(value) >= 0 ? "left:50%" : "right:50%"}"></span></span><output class="${signClass(value)}">${formatHands(value)}</output></span>`;
}

function rankRows(items, tone, emptyText) {
  return items.length ? items.map((entry) => {
    return `<div class="seat-rank-row"><span class="seat-rank-name">${escapeHtml(entry.broker)}（${escapeHtml(brokerGroupLabel(entry))}）</span><strong class="${tone}">${formatHands(entry.netPosition)}</strong><span class="seat-flow">${seatChanges(entry)}</span></div>`;
  }).join("") : `<div class="seat-rank-row"><span class="detail-empty">${emptyText}</span></div>`;
}

function priceFlowChart(series, variety) {
  if (!series.length) return `<div class="detail-empty">暂无历史快照。</div>`;
  const width = 920;
  const height = 310;
  const left = 64;
  const right = 72;
  const inner = width - left - right;
  const xFor = (index) => left + (series.length === 1 ? inner / 2 : index / (series.length - 1) * inner);
  const closes = series.map((entry) => entry.close).filter((value) => value != null).map(numeric);
  const priceMax = closes.length ? Math.max(...closes) : 1;
  const priceMin = closes.length ? Math.min(...closes) : 0;
  const priceRange = priceMax - priceMin || Math.max(1, Math.abs(priceMax) * 0.02);
  const priceY = (value) => 28 + (priceMax - numeric(value)) / priceRange * 126;
  const pricePoints = series.map((entry, index) => entry.close == null ? null : `${xFor(index).toFixed(1)},${priceY(entry.close).toFixed(1)}`).filter(Boolean).join(" ");
  const amountMax = Math.max(1, ...series.map((entry) => Math.abs(numeric(entry.amount))));
  const zeroY = 220;
  const barWidth = Math.max(8, Math.min(24, inner / Math.max(1, series.length) * 0.48));
  const bars = series.map((entry, index) => {
    const value = numeric(entry.amount);
    const barHeight = Math.max(2, Math.abs(value) / amountMax * 52);
    const y = value >= 0 ? zeroY - barHeight : zeroY;
    return `<rect class="detail-flow-bar ${dirClass(value)}" x="${(xFor(index) - barWidth / 2).toFixed(1)}" y="${y.toFixed(1)}" width="${barWidth.toFixed(1)}" height="${barHeight.toFixed(1)}"></rect>`;
  }).join("");
  const firstDate = formatDate(series[0].date);
  const lastDate = formatDate(series.at(-1).date);
  return `<svg class="detail-combo-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(variety)}历史收盘价与三方资金净变动">
    <line class="detail-grid" x1="${left}" x2="${width - right}" y1="28" y2="28"></line>
    <line class="detail-grid" x1="${left}" x2="${width - right}" y1="154" y2="154"></line>
    <line class="detail-zero" x1="${left}" x2="${width - right}" y1="${zeroY}" y2="${zeroY}"></line>
    <text class="detail-axis-label" x="${left - 9}" y="33" text-anchor="end">${formatPrice(priceMax)}</text>
    <text class="detail-axis-label" x="${left - 9}" y="158" text-anchor="end">${formatPrice(priceMin)}</text>
    <text class="detail-axis-label" x="${width - right + 9}" y="${zeroY - 48}" text-anchor="start">${formatAxisAmount(amountMax)}</text>
    <text class="detail-axis-label" x="${width - right + 9}" y="${zeroY + 56}" text-anchor="start">${formatAxisAmount(-amountMax)}</text>
    ${bars}
    ${pricePoints ? `<polyline class="detail-price-line" points="${pricePoints}"></polyline>` : ""}
    <text class="detail-axis-label" x="${left}" y="299">${firstDate}</text>
    <text class="detail-axis-label" x="${width - right}" y="299" text-anchor="end">${lastDate}</text>
  </svg>`;
}

function factLineChart(rows, field, label) {
  const points = (rows || []).filter((item) => item[field] != null);
  if (!points.length) return `<div class="fact-chart-empty">暂无可用历史数据</div>`;
  const width = 430, height = 150;
  const padding = {top: 14, right: 14, bottom: 25, left: 58};
  const values = points.map((item) => numeric(item[field]));
  const max = Math.max(...values), min = Math.min(...values);
  const range = max - min || Math.max(1, Math.abs(max) * 0.02);
  const x = (index) => padding.left + (points.length === 1 ? 0 : index / (points.length - 1) * (width - padding.left - padding.right));
  const y = (value) => padding.top + (max - value) / range * (height - padding.top - padding.bottom);
  const line = values.map((value, index) => `${x(index).toFixed(1)},${y(value).toFixed(1)}`).join(" ");
  return `<svg class="fact-line-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(label)}历史折线图">
    <line x1="${padding.left}" x2="${width - padding.right}" y1="${y(max)}" y2="${y(max)}"></line><line x1="${padding.left}" x2="${width - padding.right}" y1="${y(min)}" y2="${y(min)}"></line>
    <text x="${padding.left - 7}" y="${y(max) + 4}" text-anchor="end">${technicalValue(max, 0)}</text><text x="${padding.left - 7}" y="${y(min) + 4}" text-anchor="end">${technicalValue(min, 0)}</text>
    <polyline points="${line}"></polyline><text x="${padding.left}" y="${height - 6}">${escapeHtml(points[0].sourceDate)}</text><text x="${width - padding.right}" y="${height - 6}" text-anchor="end">${escapeHtml(points.at(-1).sourceDate)}</text>
  </svg>`;
}

function fundamentalEvidence(item) {
  const basis = item.fundamentals?.basis || [];
  const warehouse = item.fundamentals?.warehouseReceipt || [];
  const sourcePlan = item.fundamentals?.sourcePlan || {};
  const facts = item.fundamentals?.facts || [];
  const latestBasis = basis.at(-1);
  const latestWarehouse = warehouse.at(-1);
  const pending = (key, label, fallback) => {
    const plan = sourcePlan[key];
    if (!plan) return `<article class="fundamental-fact is-pending"><small>${label}</small><strong>来源缺失</strong><p>${fallback}</p></article>`;
    const accessLabels = {
      AUTO_PUBLIC: "自动来源",
      PUBLIC_SUMMARY: "来源已定位",
      MANUAL_PUBLIC: "来源已定位",
      LICENSE_REQUIRED: "待授权",
    };
    const access = accessLabels[plan.access] || "待接入";
    return `<article class="fundamental-fact is-pending"><small>${label}</small><strong>${access}</strong><p>${escapeHtml(plan.metric)} · ${escapeHtml(plan.frequency)}</p><a href="${escapeHtml(plan.url)}" target="_blank" rel="noreferrer">${escapeHtml(plan.source)}</a></article>`;
  };
  const actualOrPending = (key, label, fallback) => {
    const observations = facts.filter((fact) => fact.dimension === key);
    if (!observations.length) return pending(key, label, fallback);
    return `<article class="fundamental-fact has-observations"><small>${label}</small><strong>会员事实 ${observations.length} 项</strong><ul class="fundamental-observations">${observations.slice(0, 3).map((fact) => `<li><b>${escapeHtml(fact.metric)}</b><span>${technicalValue(fact.value, 2)} ${escapeHtml(fact.unit || "")}</span><em>${escapeHtml(fact.sourceDate)}${fact.frequency ? ` · ${escapeHtml(fact.frequency)}` : ""}</em></li>`).join("")}</ul><a href="${escapeHtml(observations[0].sourceUrl)}" target="_blank" rel="noreferrer">${escapeHtml(observations[0].source)}</a></article>`;
  };
  return `<div class="fundamental-evidence-grid">
    ${actualOrPending("supply", "供给", "产量、开工率与进口等品种专属数据尚未定位。")}
    ${actualOrPending("demand", "需求", "表观消费、下游开工与终端需求尚未定位。")}
    ${actualOrPending("cost", "成本", "主流企业现金成本尚未定位稳定口径。")}
    ${actualOrPending("inventory", "库存", "社会库存与产业库存尚未定位稳定口径。")}
    <article class="fundamental-fact chart-fact"><small>仓单</small><strong>${latestWarehouse ? technicalValue(latestWarehouse.warehouse_receipt, 0) : "暂无"}</strong><p>${latestWarehouse ? `${escapeHtml(latestWarehouse.sourceDate)} · 当日变化 ${formatSigned(latestWarehouse.change, 0)}` : "东方财富库存数据未覆盖该品种"}</p>${factLineChart(warehouse, "warehouse_receipt", `${item.variety}仓单`)}</article>
    <article class="fundamental-fact chart-fact"><small>期现基差</small><strong class="${latestBasis ? signClass(latestBasis.basis) : ""}">${latestBasis ? technicalValue(latestBasis.basis, 2) : "暂无"}</strong><p>${latestBasis ? `${escapeHtml(latestBasis.sourceDate)} · 现货价减主力期货价` : "公开期现表未覆盖该品种"}</p>${factLineChart(basis, "basis", `${item.variety}期现基差`)}</article>
  </div>`;
}

function detailRelationship(item) {
  const temperature = item.trend?.temperature;
  const trendDirection = ["温", "热", "沸"].includes(temperature) ? 1 : ["凉", "寒", "冻"].includes(temperature) ? -1 : 0;
  const moneyDirection = Math.sign(numeric(item.amountSignal));
  if (!trendDirection || !moneyDirection) return "资金与趋势待验证";
  return trendDirection === moneyDirection ? "资金顺势验证" : "资金与趋势背离";
}

function technicalValue(value, digits = 2, suffix = "") {
  if (value == null || Number.isNaN(Number(value))) return "暂无";
  return `${Number(value).toLocaleString("zh-CN", { minimumFractionDigits: digits, maximumFractionDigits: digits })}${suffix}`;
}

function technicalStateClass(state) {
  return state === "偏多" ? "bull-text" : state === "偏空" ? "bear-text" : "";
}

function chanZone(snapshot) {
  const zone = snapshot?.centralZone;
  return zone ? `${technicalValue(zone.lower, 0)} – ${technicalValue(zone.upper, 0)}` : "暂无有效中枢";
}

function levelText(levels, emptyText) {
  if (!Array.isArray(levels) || !levels.length) return emptyText;
  return levels.map((item) => `${escapeHtml(item.label)} ${technicalValue(item.value, 0)}`).join("；");
}

function technicalRelationship(technical, item, trend) {
  if (!technical || technical.status !== "OK") return "技术指标尚未生成";
  const dailyState = technical.dailyObservation?.state || technical.dailyState;
  const hourState = technical.hourObservation?.state || technical.chan60?.state;
  const technicalSign = dailyState === hourState && dailyState === "偏多" ? 1 : dailyState === hourState && dailyState === "偏空" ? -1 : 0;
  const moneySign = Math.sign(numeric(item.amountSignal));
  if (!technicalSign) return `日线${dailyState || "未确认"}、60分钟${hourState || "未确认"}，双周期尚未同向`;
  const direction = technicalSign > 0 ? "偏多" : "偏空";
  const moneyRead = !moneySign ? "三方资金中性" : moneySign === technicalSign ? `三方资金${direction}同向` : "三方资金反向";
  const trendSign = trend?.fresh && ["温", "热", "沸"].includes(trend.temperature) ? 1 : trend?.fresh && ["凉", "寒", "冻"].includes(trend.temperature) ? -1 : 0;
  const trendRead = !trendSign ? "趋势温度未确认" : trendSign === technicalSign ? "趋势温度同向" : "趋势温度反向";
  return `技术${direction}；${moneyRead}；${trendRead}`;
}

function momentumRead(value) {
  if (value == null || Number.isNaN(Number(value))) return "暂无";
  return `${formatSigned(value, 2)}%`;
}

function timeframeEvidence(title, snapshot, observation) {
  const state = observation?.state || snapshot?.state || "无法确认";
  return `<article class="technical-period-card"><header><span>${escapeHtml(title)}</span><strong class="${technicalStateClass(state)}">${escapeHtml(state)}</strong></header>
    <dl>
      <div><dt>缠论结构</dt><dd>${escapeHtml(snapshot?.state || "无法确认")} · 中枢 ${chanZone(snapshot)}</dd></div>
      <div><dt>动量</dt><dd>5期 ${momentumRead(snapshot?.momentum5Pct)} · 20期 ${momentumRead(snapshot?.momentum20Pct)}</dd></div>
      <div><dt>EMA关系</dt><dd>${escapeHtml(snapshot?.emaState || "无法确认")} · ${technicalValue(snapshot?.ema5, 0)} / ${technicalValue(snapshot?.ema20, 0)} / ${technicalValue(snapshot?.ema60, 0)}</dd></div>
    </dl>
  </article>`;
}

function renderDetailWorkspace() {
  renderDetailFilter();
  const item = currentSnapshot().instruments.find((entry) => entry.symbol === state.activeSymbol) || currentSnapshot().instruments[0];
  if (!item) {
    $("#detailWorkspace").innerHTML = `<div class="detail-empty">当前快照没有可用品种。</div>`;
    return;
  }
  state.activeSymbol = item.symbol;
  const series = seriesFor(item.symbol);
  const quote = item.quote;
  const marketFlow = item.marketFlow;
  const trend = item.trend;
  const technical = item.technical?.status === "OK" ? item.technical : null;
  const groupRows = [["内资机构", item.groups.domestic], ["外资机构", item.groups.foreign], ["家人原始", item.groups.family]];
  const stockScale = maxAbs(groupRows, ([, group]) => group.netPosition);
  const longTotal = item.brokerRanking.netLong.reduce((sum, entry) => sum + numeric(entry.netPosition), 0);
  const shortTotal = Math.abs(item.brokerRanking.netShort.reduce((sum, entry) => sum + numeric(entry.netPosition), 0));
  const seatBias = longTotal > shortTotal ? "多方样本占优" : shortTotal > longTotal ? "空方样本占优" : "席位样本均衡";
  const relationship = detailRelationship(item);
  const technicalRead = technicalRelationship(technical, item, trend);
  const trendState = trend ? `${trend.temperature || "-"} · ${trend.active ? (trend.stage || (trend.rightSide ? "右侧" : "左侧")) : "未进入趋势"}` : "暂无趋势数据";
  const researchState = `${item.amountSignal >= 0 ? "资金偏多" : "资金偏空"} · ${trend?.active ? relationship : "等待趋势确认"}`;
  const disclosure = currentSnapshot().disclosureDates.at(-1) || "未披露";
  const recentEvents = [...series].reverse().slice(0, 5);
  const latestBasis = item.fundamentals?.basis?.at(-1);
  const latestWarehouse = item.fundamentals?.warehouseReceipt?.at(-1);
  const fundamentalRead = latestBasis || latestWarehouse
    ? `基差 ${latestBasis ? technicalValue(latestBasis.basis, 2) : "暂无"}；仓单 ${latestWarehouse ? technicalValue(latestWarehouse.warehouse_receipt, 0) : "暂无"}。`
    : "基差与仓单尚无可用公开数据。";
  const tempOrder = ["凉", "寒", "冻", "平", "温", "热", "沸"];
  const openInterestChange = marketFlow?.openInterestChange;
  const openInterestLabel = openInterestChange == null ? "日增减仓" : openInterestChange >= 0 ? "日增仓" : "日减仓";
  const openInterestValue = openInterestChange == null ? "暂无" : `${Math.abs(numeric(openInterestChange)).toLocaleString("zh-CN", {maximumFractionDigits: 0})} 手`;
  $("#detailWorkspace").innerHTML = `<header class="instrument-detail-hero">
      <div class="instrument-detail-title"><span class="instrument-sector-mark"></span><div><p>${escapeHtml(item.sector)} · ${escapeHtml(item.margin.exchange || "交易所未披露")}</p><h2>${escapeHtml(item.variety)} <em>${escapeHtml(item.symbol)}</em></h2></div><span class="contract-pill">主力 ${escapeHtml(quote?.contract || item.margin.contract || "未披露")}</span></div>
      <div class="instrument-detail-quote"><div><small>涨跌幅</small><strong class="${quote?.changePct == null ? "" : signClass(quote.changePct)}">${quote?.changePct == null ? "暂无" : `${formatSigned(quote.changePct, 2)}%`}</strong></div><div><small>收盘价</small><strong>${formatPrice(quote?.close)}</strong></div><div><small>资金流向</small><strong class="${marketFlow?.capitalFlow == null ? "" : signClass(marketFlow.capitalFlow)}">${marketFlow?.capitalFlow == null ? "暂无" : formatAmount(marketFlow.capitalFlow)}</strong></div><div><small>${openInterestLabel}</small><strong class="${openInterestChange == null ? "" : signClass(openInterestChange)}">${openInterestValue}</strong></div></div>
    </header>
    <div class="detail-source-notice"><strong>真实快照</strong> 席位披露 ${escapeHtml(disclosure)}；行情 ${escapeHtml(quote?.sourceDate || "无数据")} ${escapeHtml(quote?.source || "")}${marketFlow ? `；资金流向/增减仓 ${escapeHtml(marketFlow.sourceDate)} ${escapeHtml(marketFlow.source)}` : ""}；趋势 ${escapeHtml(trend?.sourceDate || "无数据")}。来源日期不同则分开标记，不视为同日事实。</div>
    <section class="evidence-rail" aria-label="证据链摘要">
      <article><span>01</span><small>行情结构</small><strong class="${quote?.changePct == null ? "" : signClass(quote.changePct)}">${quote?.changePct == null ? "暂无行情" : quote.changePct > 0 ? "当日上涨" : quote.changePct < 0 ? "当日下跌" : "当日持平"}</strong><p>${quote ? `${quote.low == null || quote.high == null ? "日内高低未提供" : `${formatPrice(quote.low)}–${formatPrice(quote.high)}`} · ${escapeHtml(quote.source || "来源未披露")}` : "未取得主力行情"}</p></article>
      <article><span>02</span><small>趋势温度</small><strong>${escapeHtml(trendState)}</strong><p>${trend ? `强度 ${formatSigned(trend.strength, 1)}${trend.fresh ? "" : " · 非当日"}` : "趋势动物未匹配"}</p></article>
      <article><span>03</span><small>市场资金</small><strong class="${marketFlow?.capitalFlow == null ? "" : signClass(marketFlow.capitalFlow)}">${marketFlow?.capitalFlow == null ? "暂无" : formatAmount(marketFlow.capitalFlow)}</strong><p>${openInterestLabel} ${openInterestValue}</p></article>
      <article><span>04</span><small>席位结构</small><strong>${escapeHtml(seatBias)}</strong><p>净多 ${item.brokerRanking.netLong.length}/5 · 净空 ${item.brokerRanking.netShort.length}/5</p></article>
      <article class="decision"><span>结论</span><small>研究状态</small><strong>${escapeHtml(researchState)}</strong><p>${escapeHtml(item.resonance.label || item.direction)}</p></article>
    </section>
    <nav class="detail-subnav" aria-label="品种详情导航"><button class="is-active" data-detail-anchor="detail-overview">总览</button><button data-detail-anchor="detail-positioning">资金与席位</button><button data-detail-anchor="detail-technical">技术面</button><button data-detail-anchor="detail-trend">趋势</button><button data-detail-anchor="detail-fundamental">基本面</button><button data-detail-anchor="detail-events">历史事件</button></nav>
    <section id="detail-overview" class="detail-dashboard-grid">
      <article class="detail-surface chart-surface"><div class="detail-section-head"><div><small>PRICE & FLOW</small><h3>价格与三方资金</h3></div><div class="detail-legend"><i></i>收盘价 <b></b>资金净变动</div></div><div class="combo-chart-wrap">${priceFlowChart(series, item.variety)}</div><div class="detail-chart-foot"><span>历史快照 <b>${series.length} 日</b></span><span>今日手数 <b class="${signClass(item.handsSignal)}">${formatHands(item.handsSignal)}</b></span><span>边际结构 <b>${escapeHtml(item.marginalStructure)}</b></span></div></article>
      <aside class="detail-surface executive-surface"><div class="detail-section-head"><div><small>EXECUTIVE READ</small><h3>今日研究读数</h3></div></div><dl><div><dt>接口事实</dt><dd>${trend ? `趋势温度“${escapeHtml(trend.temperature)}”，强度 ${formatSigned(trend.strength, 1)}，${trend.rightSide ? "处于右侧" : "未处于右侧"}。` : "趋势数据暂无。"} 三方资金 ${formatAmount(item.amountSignal)}。</dd></div><div><dt>策略判断</dt><dd>${escapeHtml(relationship)}；席位信号为“${escapeHtml(item.resonance.label || item.direction)}”。这是规则化解读，不是接口原文。</dd></div><div><dt>基本面验证</dt><dd>${escapeHtml(fundamentalRead)}</dd></div></dl><button class="detail-action" data-create-decision="${escapeHtml(item.symbol)}">转入人工决策</button><button class="detail-action secondary" data-view="history">查看完整历史路径</button></aside>
    </section>
    <section id="detail-positioning" class="detail-surface detail-wide-section"><div class="detail-section-head"><div><small>POSITIONING</small><h3>资金与席位结构</h3></div><p>存量净持仓与今日边际分列；家人按原始方向展示</p></div><div class="position-matrix"><div class="position-matrix-head"><span>资金群体</span><span>存量净持仓</span><span>今日手数净变动</span><span>今日净金额</span><span>边际动作</span></div>${groupRows.map(([label, group]) => `<div class="position-matrix-row"><b>${label}</b>${positionVisual(group.netPosition, stockScale)}<strong class="${signClass(group.hands)}">${formatHands(group.hands)}</strong><strong class="${signClass(group.amount)}">${formatAmount(group.amount)}</strong><span class="${signClass(numeric(group.longChange) - numeric(group.shortChange))}">${escapeHtml(flowAction(group))}</span></div>`).join("")}</div><div class="seat-rank-grid detail-ranks"><div class="seat-rank-list"><div class="seat-rank-title bull-text">净多席位 ${item.brokerRanking.netLong.length}/5 <span>${rankingDominance(item.brokerRanking.netLong)}</span></div>${rankRows(item.brokerRanking.netLong, "bull-text", "暂无净多席位")}</div><div class="seat-rank-list"><div class="seat-rank-title bear-text">净空席位 ${item.brokerRanking.netShort.length}/5 <span>${rankingDominance(item.brokerRanking.netShort)}</span></div>${rankRows(item.brokerRanking.netShort, "bear-text", "暂无净空席位")}</div></div></section>
    <section class="detail-split">
      <article id="detail-trend" class="detail-surface"><div class="detail-section-head"><div><small>TREND REGIME</small><h3>趋势与周期</h3></div><span class="detail-stamp">API事实</span></div><div class="temperature-scale">${tempOrder.map((name) => `<span class="${trend?.temperature === name ? "is-active" : ""}">${name}</span>`).join("")}</div><div class="trend-fact-row"><span>趋势强度</span><strong>${trend ? formatSigned(trend.strength, 1) : "暂无"}</strong></div><div class="trend-fact-row"><span>右侧状态</span><strong>${trend ? (trend.rightSide ? "是" : "否") : "暂无"}</strong></div><div class="trend-fact-row"><span>进入天数</span><strong>${trend?.daysSinceEntry == null ? "暂无" : `${trend.daysSinceEntry} 天`}</strong></div><p class="detail-panel-note">趋势动物直接事实与本页资金判断分列。温度为“平”或数据非当日时，不把它写成右侧趋势确认。</p></article>
      <article id="detail-technical" class="detail-surface technical-section compact-technical"><div class="detail-section-head"><div><small>TECHNICAL EXECUTION</small><h3>双周期技术验证</h3></div><span class="detail-stamp ${technical?.bias === "偏多" ? "bullish" : technical?.bias === "偏空" ? "bearish" : "neutral"}">${technical ? escapeHtml(technical.bias) : "未接入"}</span></div>
        ${technical ? `<div class="technical-period-grid">${timeframeEvidence("日线观察", technical.dailyChan, technical.dailyObservation)}${timeframeEvidence("60分钟观察", technical.chan60, technical.hourObservation)}</div><div class="technical-compact-read"><p><b>量仓：</b>${escapeHtml(technical.marketActivity?.label || "数据不足")} · ${escapeHtml(technical.marketActivity?.impulse || "无法确认")}；成交较前日 ${technical.marketActivity?.volumeRatio == null ? "暂无" : technicalValue((technical.marketActivity.volumeRatio - 1) * 100, 1, "%")}。</p><p><b>位置：</b>支撑 ${levelText(technical.keyLevels?.supports, "暂无")}；压力 ${levelText(technical.keyLevels?.resistances, "暂无")}。</p><p><b>双周期：</b>${escapeHtml(technicalRead)}。</p></div><p class="detail-panel-note">EMA顺序为 5 / 20 / 60；数据日 ${escapeHtml(technical.sourceDate)}，60分钟截至 ${escapeHtml(technical.chan60?.endTime || "无法确认")}。技术观察不替代资金面与基本面。</p>` : `<div class="data-gap"><strong>当前技术面覆盖沪银、焦煤、燃油、生猪、碳酸锂和鸡蛋</strong><p>该品种尚未生成技术快照，不使用其他品种或旧日数据填充。</p></div>`}</article>
    </section>
    <article id="detail-fundamental" class="detail-surface detail-wide-section fundamental-surface"><div class="detail-section-head"><div><small>FUNDAMENTALS</small><h3>基本面证据板</h3></div><span class="detail-stamp neutral">事实与缺口分列</span></div>${fundamentalEvidence(item)}<p class="detail-panel-note">基差口径为现货价减主力期货价；仓单使用东方财富期货库存数据。供需、现金成本与产业库存未接入前不作推断。</p></article>
    <section id="detail-events" class="detail-surface detail-wide-section"><div class="detail-section-head"><div><small>EVENT PATH</small><h3>历史事件</h3></div><p>快照事实按披露日追溯</p></div><div class="event-timeline">${recentEvents.map((entry) => `<div><time>${formatDate(entry.date)}</time><b class="${signClass(entry.amount)}">${formatAmount(entry.amount)}</b><p>${escapeHtml(entry.structure)} · ${formatHands(entry.hands)} 手${entry.close == null ? "" : ` · 收盘 ${formatPrice(entry.close)}`}</p></div>`).join("")}</div></section>`;
}

function renderDetail() {
  const item = currentSnapshot().instruments.find((entry) => entry.symbol === state.activeSymbol);
  if (!item) {
    $("#detailPanel").innerHTML = `<div class="detail-empty">从左侧选择一个品种，查看三组资金拆解与历史路径。</div>`;
    return;
  }
  const closePrice = item.quote?.close;
  const dayReturn = item.quote?.changePct;
  $("#detailPanel").innerHTML = `<div class="detail-header"><div><h3>${escapeHtml(item.variety)} <small>${escapeHtml(item.symbol)}</small></h3><p>${escapeHtml(item.sector)} · ${escapeHtml(item.quote?.contract || item.margin.contract || "主力合约未披露")} · ${escapeHtml(item.margin.exchange || "")}</p></div><div class="detail-side"><div class="detail-market"><div class="detail-quote"><small>涨跌幅</small><strong class="${dayReturn == null ? "" : signClass(dayReturn)}">${dayReturn == null ? "暂无" : `${formatSigned(dayReturn, 2)}%`}</strong></div><div class="detail-quote"><small>收盘价</small><strong>${closePrice == null ? "暂无" : numeric(closePrice).toLocaleString("zh-CN", {maximumFractionDigits: 4})}</strong></div></div><div class="detail-direction ${signClass(item.amountSignal)}">${escapeHtml(item.direction)}</div></div></div>
    <div class="detail-metrics">
      <div class="detail-metric"><span>三方手数净变动</span><strong class="${signClass(item.handsSignal)}">${formatHands(item.handsSignal)}</strong></div>
      <div class="detail-metric"><span>三方资金净变动</span><strong class="${signClass(item.amountSignal)}">${formatAmount(item.amountSignal)}</strong></div>
      <div class="detail-metric"><span>总持仓边际</span><strong>${formatHands(item.totalPositionChange)}</strong></div>
      <div class="detail-metric"><span>一手保证金</span><strong>${numeric(item.margin.perLot).toLocaleString("zh-CN", {maximumFractionDigits:0})}</strong></div>
    </div>`;
}

function renderHistory() {
  const symbols = currentSnapshot().instruments.map((item) => ({symbol: item.symbol, variety: item.variety}));
  if (!state.historySymbol || !symbols.some((item) => item.symbol === state.historySymbol)) state.historySymbol = state.activeSymbol || symbols[0]?.symbol;
  $("#historyControls").innerHTML = `<label>观察品种 <select id="historySymbolSelect">${symbols.map((item) => `<option value="${escapeHtml(item.symbol)}" ${item.symbol === state.historySymbol ? "selected" : ""}>${escapeHtml(item.variety)} ${escapeHtml(item.symbol)}</option>`).join("")}</select></label>`;
  const series = seriesFor(state.historySymbol);
  const current = currentSnapshot().instruments.find((item) => item.symbol === state.historySymbol);
  $("#historyPanel").innerHTML = `<section class="history-chart"><div class="history-chart-head"><h3>${escapeHtml(current?.variety || state.historySymbol)} · 资金与价格</h3><span><i></i>资金净变动 <b></b>收盘价</span></div><div class="large-spark">${sparkline(series.map((entry) => entry.amount), dirClass(series.at(-1)?.amount || 0), true, series.map((entry) => entry.date), series.map((entry) => entry.close))}</div></section>
    <section class="history-table"><h3>披露日快照</h3><div class="history-rows">${[...series].reverse().map((entry) => `<div class="history-row"><span>${formatDate(entry.date)}</span><strong class="${signClass(entry.hands)}">${formatHands(entry.hands)} 手</strong><strong class="${signClass(entry.amount)}">${formatAmount(entry.amount)}</strong></div>`).join("")}</div></section>`;
}

function renderStatus() {
  const snapshot = currentSnapshot();
  const summary = snapshot.summary;
  const fetchStatus = Object.entries(summary.fetchStatus).map(([key, value]) => `<div class="status-line"><span>${escapeHtml(key)}</span><strong>${value} 个席位</strong></div>`).join("");
  $("#statusPanel").innerHTML = `<section class="status-block"><h3>席位披露</h3><div class="status-list"><div class="status-line"><span>报告日期</span><strong>${formatDate(snapshot.date)}</strong></div><div class="status-line"><span>网页披露日</span><strong>${escapeHtml(snapshot.disclosureDates.join(" / ") || "未披露")}</strong></div>${fetchStatus}</div></section>
    <section class="status-block"><h3>保证金口径</h3><div class="status-list"><div class="status-line"><span>覆盖率</span><strong>${(summary.marginCoverage * 100).toFixed(1)}%</strong></div><div class="status-line"><span>来源更新</span><strong>${escapeHtml(summary.marginSourceUpdate || "未披露")}</strong></div><div class="status-line"><span>缓存状态</span><strong>${escapeHtml(summary.marginCacheNote || "未知")}</strong></div></div></section>
    <section class="status-block"><h3>行情、趋势与基本面</h3><div class="status-list"><div class="status-line"><span>当日收盘行情</span><strong>${summary.quoteFreshCount || 0} / ${summary.instrumentCount}</strong></div><div class="status-line"><span>当日趋势品种</span><strong>${summary.trendFreshCount} / ${summary.instrumentCount}</strong></div><div class="status-line"><span>期现基差覆盖</span><strong>${summary.basisCoveredCount || 0} 个</strong></div><div class="status-line"><span>仓单覆盖</span><strong>${summary.warehouseCoveredCount || 0} 个</strong></div><div class="status-line"><span>股指独立观察</span><strong>${snapshot.stockIndices.length} 个</strong></div></div></section>`;
}

function orderDecisionSignals(items) {
  const bullish = items.filter((item) => numeric(item.amountSignal) > 0).sort((a, b) => numeric(b.amountSignal) - numeric(a.amountSignal));
  const bearish = items.filter((item) => numeric(item.amountSignal) < 0).sort((a, b) => numeric(a.amountSignal) - numeric(b.amountSignal));
  const neutral = items.filter((item) => !numeric(item.amountSignal));
  return [...bullish.slice(0, 5), ...bearish.slice(0, 5), ...[...bullish.slice(5), ...bearish.slice(5), ...neutral].sort((a, b) => Math.abs(numeric(b.amountSignal)) - Math.abs(numeric(a.amountSignal)))];
}

function upsertDecision(symbol) {
  const item = currentSnapshot().instruments.find((entry) => entry.symbol === symbol);
  if (!item) return;
  const id = `${state.date}-${symbol}`;
  let record = state.decisions.find((entry) => entry.id === id);
  if (!record) {
    record = {
      id, reportDate: state.date, symbol, variety: item.variety, sector: item.sector,
      runId: state.manifest?.runId || state.date, createdAt: new Date().toISOString(),
      amountSignal: item.amountSignal, handsSignal: item.handsSignal,
      close: item.quote?.close ?? null, changePct: item.quote?.changePct ?? null,
      trend: item.trend?.temperature || "", brokerRanking: item.brokerRanking,
      tradeStatus: "no_trade", direction: "", mainContradiction: "",
      trigger: "", positionPct: "", invalidation: "", closeNote: "", pnl: "",
      attribution: {}, reviewNote: "",
    };
    state.decisions.push(record);
  }
  state.activeDecisionId = id;
  saveDecisions();
  renderDecisionView();
}

function decisionStatusLabel(status) {
  return ({no_trade: "未交易", open: "持仓中", closed: "已平仓"})[status] || "未交易";
}

/* 保存复盘时同步写入品种历史操作回看（IndexedDB + 内存缓存），保证下方时间线即时更新 */
function syncDecisionToHistory(record) {
  if (typeof HistoryStore === "undefined") return;
  const dateText = record.reportDate ? `${record.reportDate.slice(0, 4)}-${record.reportDate.slice(4, 6)}-${record.reportDate.slice(6, 8)}` : "";
  const observation = {
    id: `ws-${record.id}`,
    source: "工作台日志",
    kind: "observation",
    date: dateText,
    variety: record.variety || "",
    symbol: record.symbol || "",
    contract: null, strike: null,
    instrumentType: null, optionType: null, moneyness: null,
    direction: record.direction || null,
    strategySource: "自己",
    executed: record.tradeStatus !== "no_trade",
    tradeStatus: record.tradeStatus,
    positionPct: record.positionPct || "",
    myPnl: record.pnl === "" || record.pnl == null ? null : numeric(record.pnl),
    pnlRatio: null,
    strategyPnlText: "",
    noTradeReason: "",
    stopLossTakeProfit: record.invalidation || "",
    trigger: record.trigger || "",
    ratings: {},
    attribution: record.attribution || {},
    review: [record.mainContradiction, record.closeNote, record.reviewNote, record.selfInquiry ? `自我问答：${record.selfInquiry}` : ""].filter(Boolean).join("\n"),
    selfInquiry: record.selfInquiry || "",
    raw: "",
  };
  HistoryStore.putObservation(observation);
}

function renderDecisionView() {
  if (state.editingObservationId) { renderObservationEditor(); return; }
  const instruments = [...currentSnapshot().instruments];
  const sectors = [...new Set(instruments.map((item) => item.sector))].sort();
  $("#decisionSectorFilter").innerHTML = `<option value="all">全部板块</option>${sectors.map((sector) => `<option value="${escapeHtml(sector)}" ${state.decisionSector === sector ? "selected" : ""}>${escapeHtml(sector)}</option>`).join("")}`;
  const sectorItems = instruments.filter((item) => state.decisionSector === "all" || item.sector === state.decisionSector);
  if (state.decisionSymbol !== "all" && !sectorItems.some((item) => item.symbol === state.decisionSymbol)) state.decisionSymbol = "all";
  $("#decisionSymbolFilter").innerHTML = `<option value="all">全部品种</option>${sectorItems.sort((a, b) => a.variety.localeCompare(b.variety, "zh-CN")).map((item) => `<option value="${escapeHtml(item.symbol)}" ${state.decisionSymbol === item.symbol ? "selected" : ""}>${escapeHtml(item.variety)} ${escapeHtml(item.symbol)}</option>`).join("")}`;
  const query = (state.decisionQuery || "").toUpperCase();
  const signals = orderDecisionSignals(sectorItems.filter((item) => state.decisionSymbol === "all" || item.symbol === state.decisionSymbol)).filter((item) => !query || item.symbol.toUpperCase().includes(query) || (item.variety || "").toUpperCase().includes(query));
  const pageCount = Math.max(1, Math.ceil(signals.length / 10));
  state.decisionPage = Math.min(state.decisionPage, pageCount);
  const pageSignals = signals.slice((state.decisionPage - 1) * 10, state.decisionPage * 10);
  $("#decisionSignals").innerHTML = signals.length ? pageSignals.map((item) => {
    const record = state.decisions.find((entry) => entry.id === `${state.date}-${item.symbol}`);
    const status = record ? decisionStatusLabel(record.tradeStatus) : "未记录";
    const statusCls = record?.tradeStatus === "open" ? "bull-text" : record?.tradeStatus === "closed" ? "bear-text" : "neutral-text";
    return `<button class="decision-signal ${dirClass(item.amountSignal)}" data-open-decision="${escapeHtml(item.symbol)}"><div><strong>${escapeHtml(item.variety)} ${escapeHtml(item.symbol)}</strong><small>${formatAmount(item.amountSignal)} · ${formatHands(item.handsSignal)} 手</small></div><em class="decision-signal-status ${statusCls}">${status}</em></button>`;
  }).join("") + (pageCount > 1 ? `<nav class="decision-pagination" aria-label="决策品种分页">${Array.from({length: pageCount}, (_, index) => `<button class="${state.decisionPage === index + 1 ? "is-active" : ""}" data-decision-page="${index + 1}">${index + 1}</button>`).join("")}</nav>` : "") : `<div class="detail-empty">当前筛选条件下没有品种。</div>`;

  const records = [...state.decisions].sort((a, b) => b.reportDate.localeCompare(a.reportDate) || a.symbol.localeCompare(b.symbol));
  $("#decisionList").innerHTML = records.length ? records.map((record) => `<button class="decision-list-item ${record.id === state.activeDecisionId ? "is-active" : ""}" data-edit-decision="${escapeHtml(record.id)}"><span><strong>${escapeHtml(record.variety)} ${escapeHtml(record.symbol)}</strong><small>${formatDate(record.reportDate)}${record.direction ? ` · ${record.direction === "空" ? "做空" : "做多"}` : ""}</small></span><em>${decisionStatusLabel(record.tradeStatus)}</em></button>`).join("") : `<div class="detail-empty">尚无日志记录，点上方任一品种开始。</div>`;

  const record = state.decisions.find((entry) => entry.id === state.activeDecisionId);
  if (!record) {
    $("#decisionEditor").innerHTML = `<div class="detail-empty">点击上方任一品种，开始写当天的交易日志。</div>`;
    return;
  }
  const snapshotItem = state.data.snapshots[record.reportDate]?.instruments.find((item) => item.symbol === record.symbol);
  const ranking = record.brokerRanking || snapshotItem?.brokerRanking || {netLong: [], netShort: []};
  const option = (value, label, current) => `<option value="${value}" ${current === value ? "selected" : ""}>${label}</option>`;
  const attrField = (key, label) => `<label>${label}<select name="attr_${key}">${option("", "—", (record.attribution || {})[label])}${option("Y", "Y", (record.attribution || {})[label])}${option("N", "N", (record.attribution || {})[label])}</select></label>`;
  const attribution = record.attribution || {};
  $("#decisionEditor").innerHTML = `<form id="decisionForm"><header><div><small>${formatDate(record.reportDate)} · ${escapeHtml(record.runId)}</small><h3>${escapeHtml(record.variety)} ${escapeHtml(record.symbol)}</h3></div><div class="decision-market-facts"><strong class="${signClass(record.amountSignal)}">${formatAmount(record.amountSignal)}</strong><strong class="${record.changePct == null ? "" : signClass(record.changePct)}">${record.changePct == null ? "涨跌 暂无" : `${formatSigned(record.changePct, 2)}%`}</strong></div></header>
    <div class="decision-facts"><span>手数 ${formatHands(record.handsSignal)}</span><span>收盘 ${formatPrice(record.close)}</span><span>趋势 ${escapeHtml(record.trend || "暂无")}</span></div>
    <details class="decision-evidence"><summary>查看当日席位证据</summary><div class="seat-rank-grid decision-ranks"><div class="seat-rank-list"><div class="seat-rank-title bull-text">净多席位 ${ranking.netLong.length}/5 <span>${rankingDominance(ranking.netLong)}</span></div>${rankRows(ranking.netLong, "bull-text", "暂无净多席位")}</div><div class="seat-rank-list"><div class="seat-rank-title bear-text">净空席位 ${ranking.netShort.length}/5 <span>${rankingDominance(ranking.netShort)}</span></div>${rankRows(ranking.netShort, "bear-text", "暂无净空席位")}</div></div></details>
    <div class="decision-form-grid">
      <label>交易状态<select name="tradeStatus">${option("no_trade","未交易",record.tradeStatus)}${option("open","持仓中",record.tradeStatus)}${option("closed","已平仓",record.tradeStatus)}</select></label>
      <label>方向<select name="direction">${option("", "未定", record.direction)}${option("多", "做多", record.direction)}${option("空", "做空", record.direction)}</select></label>
      <label class="wide">核心逻辑<textarea name="mainContradiction" rows="2" placeholder="为什么值得做，最关键的支撑和反向证据是什么">${escapeHtml(record.mainContradiction)}</textarea></label>
      <label>入场触发<input name="trigger" value="${escapeHtml(record.trigger)}" placeholder="价格或技术条件"></label>
      <label>仓位（占总仓位比例）<input name="positionPct" value="${escapeHtml(record.positionPct)}" placeholder="如 30%"></label>
      <label>失效 / 止损<input name="invalidation" value="${escapeHtml(record.invalidation)}" placeholder="错在哪里退出"></label>
      <label>平仓<textarea name="closeNote" rows="2" placeholder="平仓过程与是否按计划执行">${escapeHtml(record.closeNote)}</textarea></label>
      <label>盈亏（元，选填）<input name="pnl" type="number" step="any" value="${escapeHtml(String(record.pnl ?? ""))}" placeholder="亏损填负数"></label>
      <div class="decision-attr-grid wide"><span class="decision-attr-title">执行归因（复盘）</span>${attrField("judgment","判断错？")}${attrField("timing","时机错？")}${attrField("position","仓位错？")}${attrField("tool","工具错？")}${attrField("execution","执行错？")}</div>
      <label class="wide">最大错误与下一条规则<textarea name="reviewNote" rows="3" placeholder="最大错误：&#10;下一次只改：">${escapeHtml(record.reviewNote)}</textarea></label>
      <label class="wide">自我问答<textarea name="selfInquiry" rows="3" placeholder="这一笔交易中，哪些行为来自市场本身，哪些行为来自我对得失、对错和自我证明的执著？">${escapeHtml(record.selfInquiry || "")}</textarea></label>
    </div><p id="decisionFormMessage" class="form-message" aria-live="polite"></p><div class="decision-form-actions"><button class="decision-save" type="submit">保存复盘</button><button class="decision-delete" type="button" data-delete-decision="${escapeHtml(record.id)}">删除</button></div></form>`;
}

/* ===================== 历史复盘修订(编辑已有 observation) =====================
   直接修订 observation 本体(非 decision 体系):保留原记录全部字段,只覆盖复盘相关字段,
   经 HistoryStore.putObservation 写回(IndexedDB + 私有仓云同步,updated 新者胜)。
   适用场景:Excel/月度复盘当时没填完整,事后补盈亏、归因、认知偏差等。 */
function findObservation(id) {
  return (state.history?.observations || []).find((item) => item.id === id) || null;
}

function startObservationEdit(id) {
  if (!findObservation(id)) return;
  state.editingObservationId = id;
  switchView("decisions");
  requestAnimationFrame(() => $("#decisionEditor")?.scrollIntoView({behavior: "smooth", block: "start"}));
}

function renderObservationEditor() {
  const item = findObservation(state.editingObservationId);
  if (!item) { state.editingObservationId = null; renderDecisionView(); return; }
  const option = (value, label, current) => `<option value="${value}" ${current === value ? "selected" : ""}>${label}</option>`;
  const tradeStatus = item.tradeStatus || (item.executed ? "closed" : "no_trade");
  const attr = item.attribution || {};
  const attrField = (key, label) => `<label>${label}<select name="attr_${key}">${option("", "—", attr[label])}${option("Y", "Y", attr[label])}${option("N", "N", attr[label])}</select></label>`;
  $("#decisionEditor").innerHTML = `<form id="observationForm" data-obs-id="${escapeHtml(item.id)}">
    <header><div><small>修订复盘 · ${escapeHtml(item.date || "日期缺失")} · 来源 ${escapeHtml(historySourceBadge(item.source))}</small>
    <h3>${escapeHtml(item.variety || "")} ${escapeHtml(item.symbol || "")}</h3></div>
    <div class="decision-market-facts"><em class="decision-signal-status">${item.executed ? "已执行" : "未执行"}</em></div></header>
    <p class="decision-due">修订只覆盖下面填写的字段,原记录其余信息全部保留;保存后写入本地并同步私有数据仓。</p>
    <div class="decision-form-grid">
      <label>交易状态<select name="tradeStatus">${option("no_trade","未交易",tradeStatus)}${option("open","持仓中",tradeStatus)}${option("closed","已平仓",tradeStatus)}</select></label>
      <label>方向<select name="direction">${option("", "未定", item.direction || "")}${option("多", "做多", item.direction || "")}${option("空", "做空", item.direction || "")}</select></label>
      <label class="wide">核心逻辑<textarea name="mainContradiction" rows="2" placeholder="为什么值得做,最关键的支撑和反向证据是什么">${escapeHtml(item.mainContradiction || "")}</textarea></label>
      <label>入场触发<input name="trigger" value="${escapeHtml(item.trigger || "")}" placeholder="价格或技术条件"></label>
      <label>仓位(占总仓位比例)<input name="positionPct" value="${escapeHtml(item.positionPct || "")}" placeholder="如 30%"></label>
      <label>失效 / 止损<input name="stopLossTakeProfit" value="${escapeHtml(item.stopLossTakeProfit || "")}" placeholder="错在哪里退出"></label>
      <label>平仓<textarea name="closeNote" rows="2" placeholder="平仓过程与是否按计划执行">${escapeHtml(item.closeNote || "")}</textarea></label>
      <label>盈亏(元,选填)<input name="myPnl" type="number" step="any" value="${item.myPnl == null ? "" : escapeHtml(String(item.myPnl))}" placeholder="亏损填负数"></label>
      <label class="wide">未交易原因<input name="noTradeReason" value="${escapeHtml(item.noTradeReason || "")}"></label>
      <div class="decision-attr-grid wide"><span class="decision-attr-title">执行归因(复盘)</span>${attrField("judgment","判断错?")}${attrField("timing","时机错?")}${attrField("position","仓位错?")}${attrField("tool","工具错?")}${attrField("execution","执行错?")}</div>
      <label class="wide">最大错误与下一条规则<textarea name="reviewNote" rows="3" placeholder="最大错误:&#10;下一次只改:">${escapeHtml(item.reviewNote || "")}</textarea></label>
      <label class="wide">自我问答<textarea name="selfInquiry" rows="3" placeholder="这一笔交易中，哪些行为来自市场本身，哪些行为来自我对得失、对错和自我证明的执著？">${escapeHtml(item.selfInquiry || "")}</textarea></label>
      <label class="wide">复盘与认知偏差原文<textarea name="review" rows="4">${escapeHtml(item.review || "")}</textarea></label>
    </div>
    <p id="observationFormMessage" class="form-message" aria-live="polite"></p>
    <div class="decision-form-actions"><button class="decision-save" type="submit">保存修订</button>
    <button class="decision-delete" type="button" data-cancel-observation-edit="1">取消</button></div>
  </form>`;
}

function collectKvPairs(form, prefix) {
  const out = {};
  const keys = form.querySelectorAll(`input[name="${prefix}_key"]`);
  keys.forEach((keyInput) => {
    const key = keyInput.value.trim();
    const row = keyInput.closest(".obs-kv-row");
    const valueInput = row?.querySelector(`input[name="${prefix}_value"]`);
    const value = valueInput ? valueInput.value.trim() : "";
    if (key && value) out[key] = value;
  });
  const newKey = form.querySelector(`input[name="${prefix}_new_key"]`);
  const newValue = form.querySelector(`input[name="${prefix}_new_value"]`);
  if (newKey && newValue && newKey.value.trim() && newValue.value.trim()) out[newKey.value.trim()] = newValue.value.trim();
  return Object.keys(out).length ? out : null;
}

/* ===================== 5 日涨跌幅与品种状态(运行时计算) ===================== */
function computeReturn5d(symbol) {
  const dates = (state.data.dates || []).slice().sort();
  const curIdx = dates.indexOf(state.date);
  if (curIdx < 5) return null;
  const prev = state.data.snapshots[dates[curIdx - 5]];
  if (!prev) return null;
  const cur = (currentSnapshot().instruments || []).find((x) => x.symbol === symbol);
  const prevItem = (prev.instruments || []).find((x) => x.symbol === symbol);
  const curClose = cur?.quote?.close;
  const prevClose = prevItem?.quote?.close;
  if (curClose == null || prevClose == null || prevClose === 0) return null;
  return Math.round(((curClose - prevClose) / prevClose) * 10000) / 100;
}

function trendStateByReturn(r5) {
  if (r5 == null) return { cls: "flat", label: "—" };
  if (r5 >= 5) return { cls: "ext-up", label: "趋势极强" };
  if (r5 <= -5) return { cls: "ext-down", label: "趋势极弱" };
  if (r5 >= 3) return { cls: "up", label: "趋势偏强" };
  if (r5 <= -3) return { cls: "down", label: "趋势偏弱" };
  return { cls: "flat", label: "震荡" };
}

/* 关键事件标签多/空分类 */
function classifyEvent(text) {
  const t = String(text || "");
  if (/空|跌|减|利空|偏弱|下跌/.test(t)) return { tone: "down", flag: "空" };
  if (/多|涨|增|利多|偏强|上涨/.test(t)) return { tone: "up", flag: "多" };
  return { tone: "neutral", flag: "" };
}

const CTA_FACTOR_LABELS = {trend: "量价趋势", seat: "席位存量", position: "席位边际", carry: "基差与仓单", option: "期权偏度"};

/* ===================== 品种历史操作回看 ===================== */

const HISTORY_SOURCE_LABELS = {"交易日志Excel": "Excel 日志", "月度复盘md": "月度复盘", "工作台决策": "工作台"};
const HISTORY_EVENT_LABELS = {open: "开仓", add: "加仓", reduce: "减仓", close: "平仓", other: "操作"};

function historySourceBadge(source) {
  return HISTORY_SOURCE_LABELS[source] || source || "";
}

function historyInstrumentText(item) {
  const parts = [];
  if (item.instrumentType) parts.push(item.instrumentType);
  if (item.optionType) parts.push(item.optionType.toUpperCase());
  if (item.contract) parts.push(item.contract);
  else if (item.strike) parts.push(`行权价 ${item.strike}`);
  if (item.moneyness) parts.push(item.moneyness);
  if (item.direction) parts.push(item.direction === "空" ? "做空" : "做多");
  if (item.positionPct) parts.push(`仓位 ${item.positionPct}`);
  return parts.join(" · ");
}

function historyPnlText(item) {
  if (!item.executed) {
    if (item.strategyPnlText) return {text: `策略方收益：${item.strategyPnlText}`, cls: "neutral-text"};
    return {text: item.kind === "trade" ? "" : "仅观察（未执行）", cls: "neutral-text"};
  }
  if (item.myPnl != null) return {text: `${formatSigned(item.myPnl, 0)} 元`, cls: signClass(item.myPnl)};
  if (item.pnlText) return {text: item.pnlText, cls: "neutral-text"};
  if (item.batchFlag) return {text: "批次记录，盈亏未拆分到单品种", cls: "neutral-text"};
  return {text: "", cls: ""};
}

function historyEventChain(events) {
  if (!events || !events.length) return "";
  return `<div class="history-event-chain"><span class="history-chain-title">操作序列</span>${events.map((event) => `<span class="history-event history-event-${escapeHtml(event.type)}"><b>${escapeHtml(HISTORY_EVENT_LABELS[event.type] || event.action)}</b>${event.price != null ? `<strong>${escapeHtml(String(event.price))}</strong>` : ""}${event.note ? `<i>${escapeHtml(event.note)}</i>` : ""}</span>`).join('<span class="history-event-arrow">→</span>')}</div>`;
}

function historyRatingDots(ratings) {
  if (!ratings || !Object.keys(ratings).length) return "";
  const cls = (value) => value.includes("利多") || value.includes("偏强") ? "bull-text" : value.includes("利空") || value.includes("偏弱") ? "bear-text" : "neutral-text";
  const short = (key) => ({技术面: "技术", 基本面: "基本", 资金面: "资金", 政策面: "政策", 情绪面: "情绪", 认知偏差: "认知", 综合评价: "综合"}[key] || key);
  return `<div class="history-ratings">${Object.entries(ratings).map(([key, value]) => `<span><small>${short(key)}</small><b class="${cls(String(value))}">${escapeHtml(String(value))}</b></span>`).join("")}</div>`;
}

function historyAttributionRows(attribution) {
  if (!attribution || !Object.keys(attribution).length) return "";
  return `<div class="history-attribution"><span class="history-chain-title">执行归因</span>${Object.entries(attribution).map(([key, value]) => `<span class="history-attribution-item"><small>${escapeHtml(key)}</small><b class="${/^Y|是/.test(String(value)) ? "bear-text" : "neutral-text"}">${escapeHtml(String(value)) || "—"}</b></span>`).join("")}</div>`;
}

function historyNarrativeText(item) {
  if (item.kind !== "narrative") return "";
  return `<p class="history-narrative">${escapeHtml(item.text || "")}</p>`;
}

/* 工作台日志的入场触发 / 仓位 / 止损失效（Excel 与 md 记录没有这些字段，自动跳过） */
function historyPlanRows(item) {
  const rows = [];
  if (item.trigger) rows.push(["入场触发", item.trigger]);
  if (item.positionPct) rows.push(["仓位", item.positionPct]);
  if (item.stopLossTakeProfit) rows.push(["止损 / 失效", item.stopLossTakeProfit]);
  if (!rows.length) return "";
  return `<div class="history-plan">${rows.map(([label, value]) => `<span><small>${label}</small><b>${escapeHtml(value)}</b></span>`).join("")}</div>`;
}

function renderHistoryEntry(item) {
  const pnl = historyPnlText(item);
  const review = item.review || "";
  const noTrade = item.noTradeReason ? `<p class="history-no-trade">未交易原因：${escapeHtml(item.noTradeReason)}</p>` : "";
  return `<article class="history-entry ${item.executed ? "is-executed" : "is-observe"}">
    <header>
      <span class="history-date">${escapeHtml(item.date || "日期缺失")}${item.dateNote ? `<i title="${escapeHtml(item.dateNote)}">?</i>` : ""}</span>
      <span class="history-badge history-badge-${escapeHtml(item.kind)}">${item.kind === "trade" ? "交易" : item.kind === "narrative" ? "复盘" : "观察"}</span>
      <span class="history-badge-source">${escapeHtml(historySourceBadge(item.source))}</span>
      <span class="history-instrument">${escapeHtml(historyInstrumentText(item))}</span>
      ${item.strategySource ? `<span class="history-strategy-source">参考来源：${escapeHtml(item.strategySource)}</span>` : ""}
      <em class="history-exec-flag">${item.executed ? "已执行" : "未执行"}</em>
      <button class="history-edit-btn" type="button" data-edit-observation="${escapeHtml(item.id)}" title="修订这条复盘(补填盈亏/归因/认知偏差)">编辑</button>
    </header>
    ${historyPlanRows(item)}
    ${pnl.text ? `<div class="history-pnl ${pnl.cls}">${escapeHtml(pnl.text)}</div>` : ""}
    ${historyEventChain(item.events)}
    ${historyRatingDots(item.ratings)}
    ${historyAttributionRows(item.attribution)}
    ${historyNarrativeText(item)}
    ${noTrade}
    ${review ? `<details class="history-review"><summary>复盘与认知偏差原文</summary><p>${escapeHtml(review)}</p></details>` : ""}
  </article>`;
}

function renderHistoryView() {
  const history = state.history;
  if (!history) return;
  const observations = history.observations || [];
  const trades = history.trades || [];
  const months = history.months || [];

  const executedObs = observations.filter((item) => item.executed);
  const myPnlTotal = executedObs.reduce((sum, item) => sum + (item.myPnl || 0), 0) + trades.reduce((sum, item) => sum + (item.myPnl || 0), 0);
  const monthPnlTotal = months.reduce((sum, month) => sum + (month.pnl || 0), 0);

  $("#historySummary").innerHTML = [
    summaryCard("历史记录", observations.length + trades.length, `Excel ${observations.filter((item) => item.source === "交易日志Excel").length} 条 · 月度复盘 ${trades.length} 笔交易`),
    summaryCard("已执行", executedObs.length + trades.length, "含开仓、加仓、平仓的真实操作"),
    summaryCard("观察（未执行）", observations.length - executedObs.length, "参考他人策略或自身观察记录"),
    summaryCard("已执行盈亏合计", `${formatSigned(myPnlTotal, 0)} 元`, "仅统计本人实际执行记录", myPnlTotal > 0 ? "bull-text" : myPnlTotal < 0 ? "bear-text" : ""),
    summaryCard("月度复盘合计", `${formatSigned(monthPnlTotal, 0)} 元`, `${months.length} 个月（${escapeHtml(months.map((month) => month.label).join("/"))}）`, monthPnlTotal > 0 ? "bull-text" : monthPnlTotal < 0 ? "bear-text" : ""),
  ].join("") + (history.errors && history.errors.length ? `<div class="detail-source-notice">部分数据源导入失败：${escapeHtml(history.errors.join("；"))}</div>` : "");

  const groups = {};
  [...observations, ...trades].forEach((item) => {
    const key = item.symbol || item.variety || "未知";
    if (!groups[key]) groups[key] = {key, variety: item.variety || key, symbol: item.symbol || "", items: []};
    groups[key].items.push(item);
  });
  const sorted = Object.values(groups).sort((a, b) => b.items.length - a.items.length || a.variety.localeCompare(b.variety, "zh-CN"));
  if (!state.historyJournalSymbol || !groups[state.historyJournalSymbol]) state.historyJournalSymbol = sorted[0]?.key || null;

  $("#historySymbolList").innerHTML = sorted.map((group) => {
    const executedCount = group.items.filter((item) => item.executed).length;
    return `<button class="history-symbol-item ${group.key === state.historyJournalSymbol ? "is-active" : ""}" data-history-symbol="${escapeHtml(group.key)}"><span><strong>${escapeHtml(group.variety)}</strong><small>${escapeHtml(group.symbol || "无代码")} · ${group.items.length} 条记录</small></span><em>${executedCount}/${group.items.length}</em></button>`;
  }).join("") || `<div class="detail-empty">没有导入的历史记录。</div>`;

  const group = groups[state.historyJournalSymbol];
  if (!group) { $("#historyTimeline").innerHTML = `<div class="detail-empty">暂无历史数据。先运行 scripts/import_trading_log_excel.py 与 scripts/import_monthly_review_md.py 生成 data/imported/ 下的 JSON。</div>`; return; }
  const items = [...group.items].sort((a, b) => (b.date || "").localeCompare(a.date || ""));
  const executedPnl = items.filter((item) => item.executed).reduce((sum, item) => sum + (item.myPnl || 0), 0);
  $("#historyTimeline").innerHTML = `<div class="history-timeline-head"><h3>${escapeHtml(group.variety)} ${escapeHtml(group.symbol)}</h3><span>${items.length} 条记录 · ${items.filter((item) => item.executed).length} 次执行 · 已执行盈亏 <b class="${signClass(executedPnl)}">${formatSigned(executedPnl, 0)} 元</b></span></div>${items.map(renderHistoryEntry).join("")}`;
}

function renderMetal4d(row) {
  const framework = row.metal4d;
  if (!framework) return "";
  const statusClass = (status) => status === "确认" ? "bull-text" : status === "冲突" ? "bear-text" : "neutral-text";
  const signalClass = framework.callSilver ? "bullish" : framework.signal.startsWith("暂不") ? "bearish" : "";
  const relative = framework.relative20d == null ? "缺失" : `${formatSigned(framework.relative20d, 1)}%`;
  return `<section class="cta-metal4d"><div class="cta-metal4d-head"><div><small>GOLD–SILVER 4D</small><h4>金银四维框架</h4></div><span class="tag ${signalClass}">${escapeHtml(framework.signal)}</span></div><p>白银相对黄金20日超额 ${relative} · 数据时点 ${escapeHtml(framework.asOf)}</p><div class="cta-factor-list">${framework.dimensions.map((item) => `<article><div><strong>${escapeHtml(item.name)}</strong><span class="${statusClass(item.status)}">${escapeHtml(item.status)}</span></div><p>${escapeHtml(item.evidence)}</p></article>`).join("")}</div><div class="detail-source-notice">待满足：${framework.blockers.length ? escapeHtml(framework.blockers.join("、")) : "四维与白银资金结构均已确认"}。Call 提示只代表条件筛选，不替代波动率、期限与最大亏损检查。</div></section>`;
}

function renderCta() {
  const allRows = currentSnapshot().cta || [];
  const sectors = [...new Set(allRows.map((row) => row.sector))].sort();
  $("#ctaSectorFilter").innerHTML = `<option value="all">全部板块</option>${sectors.map((sector) => `<option value="${escapeHtml(sector)}" ${sector === state.ctaSector ? "selected" : ""}>${escapeHtml(sector)}</option>`).join("")}`;
  const query = state.ctaQuery.trim().toLowerCase();
  const rows = allRows.filter((row) => (!query || `${row.variety}${row.symbol}`.toLowerCase().includes(query)) && (state.ctaSector === "all" || row.sector === state.ctaSector) && (state.ctaDirection === "all" || row.signal === state.ctaDirection));
  const bull = rows.filter((row) => row.score >= 15).length;
  const bear = rows.filter((row) => row.score <= -15).length;
  $("#ctaSummary").innerHTML = [
    summaryCard("CTA 样本", rows.length, `全量 ${allRows.length} 个，含股指 ${allRows.filter((row) => row.sector === "股指").length} 个`),
    summaryCard("偏多", bull, "分数不低于 +15", "bull-text"),
    summaryCard("中性", rows.length - bull - bear, "-15 至 +15"),
    summaryCard("偏空", bear, "分数不高于 -15", "bear-text"),
  ].join("");
  $("#ctaRows").innerHTML = rows.map((row, index) => `<tr data-cta-symbol="${escapeHtml(row.symbol)}" class="${row.symbol === state.activeCtaSymbol ? "is-selected" : ""}"><td>${index + 1}</td><td><strong>${escapeHtml(row.variety)}</strong><small>${escapeHtml(row.symbol)}</small></td><td>${escapeHtml(row.sector)}</td><td class="cta-score ${signClass(row.score)}">${formatSigned(row.score)}</td><td>${row.coverage}%</td><td class="${signClass(row.score)}">${escapeHtml(row.signal)}</td></tr>`).join("") || `<tr><td colspan="6">没有匹配品种。</td></tr>`;
  const selected = rows.find((row) => row.symbol === state.activeCtaSymbol) || rows[0];
  state.activeCtaSymbol = selected?.symbol || null;
  $("#ctaDetail").innerHTML = selected ? `<div class="detail-kicker">CTA FACTOR BREAKDOWN</div><h3>${escapeHtml(selected.variety)} <small>${escapeHtml(selected.symbol)}</small></h3><div class="cta-detail-score ${signClass(selected.score)}">${formatSigned(selected.score)} <small>${escapeHtml(selected.signal)}</small></div><p>${escapeHtml(selected.sector)} · 可用因子覆盖 ${selected.coverage}% · 年化波动 ${selected.volatility ?? "—"}%</p><div class="cta-factor-list">${Object.entries(CTA_FACTOR_LABELS).map(([key, label]) => `<article><div><strong>${label}</strong><span class="${selected.factors[key] == null ? "neutral-text" : signClass(selected.factors[key])}">${selected.factors[key] == null ? "未覆盖" : formatSigned(selected.factors[key])}</span></div><p>${escapeHtml(selected.evidence[key])}</p></article>`).join("")}</div>${renderMetal4d(selected)}<div class="detail-source-notice">缺失因子不按中性计分，而是按可用权重重算。截图是二级证据；评分不是回测后的交易策略或买卖建议。</div>` : `<div class="detail-empty">该筛选条件没有 CTA 品种。</div>`;
}

function renderAll() {
  /* 初始化交易日历(顶栏日历弹层) */
  if (typeof window.initCalendar === "function") {
    const allDates = state.data.dates || [];
    window.initCalendar(allDates, state.date);
  }
  renderDateControls();
  renderSummary();
  renderFocus();
  renderTide();
  renderCorePanorama();
  renderNetFlowChanges();
  renderSeatFlow();
  renderBrokerHighlights();
  renderStockIndices();
  renderOverviewStatus();
  renderDetailWorkspace();
  renderInstrumentTable();
  renderHistory();
  renderStatus();
  renderDecisionView();
  renderHistoryView();
  renderCta();
}

function switchView(view) {
  state.view = view;
  $$(".nav-item").forEach((button) => button.classList.toggle("is-active", button.dataset.view === view));
  $$(".view").forEach((panel) => panel.classList.toggle("is-active", panel.id === `view-${view}`));
  if (view === "detail") renderDetailWorkspace();
  if (view === "history") renderHistory();
  if (view === "decisions") { renderDecisionView(); renderHistoryView(); }
  if (view === "cta") renderCta();
}

function setDate(date) {
  const previousDate = state.date;
  state.date = date;
  state.symbol = "all";
  state.sector = "all";
  state.detailSector = "all";
  state.detailQuery = "";
  state.decisionPage = 1;
  state.activeCtaSymbol = null;
  if (state.data.snapshots[date]) { renderAll(); return; }
  /* 该日快照可能还在后台补载队列里：按需拉取后再渲染，期间复用全屏装载提示 */
  const loadingEl = document.getElementById("loadingState");
  if (loadingEl) loadingEl.style.display = "grid";
  ensureSnapshot(date)
    .catch(() => {})
    .then(() => {
      if (loadingEl) loadingEl.style.display = "";
      if (state.date !== date) return;
      if (!state.data.snapshots[date]) { state.date = previousDate; } /* 拉取失败则留在原日期 */
      renderAll();
    });
}

function bindEvents() {
  document.addEventListener("click", (event) => {
    const railToggle = event.target.closest("#railToggle");
    if (railToggle) {
      state.railCollapsed = !state.railCollapsed;
      $("#app").classList.toggle("rail-collapsed", state.railCollapsed);
      railToggle.textContent = state.railCollapsed ? "›" : "‹";
      railToggle.setAttribute("aria-label", state.railCollapsed ? "展开侧边栏" : "收起侧边栏");
      railToggle.title = state.railCollapsed ? "展开侧边栏" : "收起侧边栏";
    }
    const nav = event.target.closest("[data-view]");
    if (nav) switchView(nav.dataset.view);
    const dateButton = event.target.closest("[data-date]");
    if (dateButton) setDate(dateButton.dataset.date);
    const row = event.target.closest("[data-symbol]");
    if (row) { state.activeSymbol = row.dataset.symbol; renderInstrumentTable(); }
    const ctaRow = event.target.closest("[data-cta-symbol]");
    if (ctaRow) { state.activeCtaSymbol = ctaRow.dataset.ctaSymbol; renderCta(); }
    const detailName = event.target.closest("[data-open-detail-symbol]");
    if (detailName) { state.activeSymbol = detailName.dataset.openDetailSymbol; switchView("detail"); window.scrollTo({top: 0, behavior: "smooth"}); }
    const focus = event.target.closest("[data-open-symbol]");
    if (focus) { state.activeSymbol = focus.dataset.openSymbol; switchView("detail"); window.scrollTo({top: 0, behavior: "smooth"}); }
    const detailAnchor = event.target.closest("[data-detail-anchor]");
    if (detailAnchor) {
      $$("[data-detail-anchor]").forEach((button) => button.classList.toggle("is-active", button === detailAnchor));
      document.getElementById(detailAnchor.dataset.detailAnchor)?.scrollIntoView({behavior: "smooth", block: "start"});
    }
    const direction = event.target.closest("[data-direction]");
    if (direction) {
      state.direction = direction.dataset.direction;
      $$("[data-direction]").forEach((button) => button.classList.toggle("is-active", button === direction));
      renderInstrumentTable();
    }
    const openDecision = event.target.closest("[data-open-decision]");
    if (openDecision) upsertDecision(openDecision.dataset.openDecision);
    const decisionPage = event.target.closest("[data-decision-page]");
    if (decisionPage) { state.decisionPage = numeric(decisionPage.dataset.decisionPage); renderDecisionView(); }
    const editDecision = event.target.closest("[data-edit-decision]");
    if (editDecision) { state.activeDecisionId = editDecision.dataset.editDecision; renderDecisionView(); }
    const createDecision = event.target.closest("[data-create-decision]");
    if (createDecision) { upsertDecision(createDecision.dataset.createDecision); switchView("decisions"); window.scrollTo({top: 0, behavior: "smooth"}); }
    const deleteDecision = event.target.closest("[data-delete-decision]");
    if (deleteDecision) { state.decisions = state.decisions.filter((entry) => entry.id !== deleteDecision.dataset.deleteDecision); state.activeDecisionId = null; saveDecisions(); renderDecisionView(); }
    const historySymbol = event.target.closest("[data-history-symbol]");
    if (historySymbol) { state.historyJournalSymbol = historySymbol.dataset.historySymbol; renderHistoryView(); }
    const editObs = event.target.closest("[data-edit-observation]");
    if (editObs) startObservationEdit(editObs.dataset.editObservation);
    if (event.target.closest("[data-cancel-observation-edit]")) { state.editingObservationId = null; renderDecisionView(); }
  });
  $("#decisionEditor").addEventListener("submit", (event) => {
    if (event.target.id !== "observationForm") return;
    event.preventDefault();
    const item = findObservation(state.editingObservationId);
    if (!item) return;
    const form = event.target;
    const values = Object.fromEntries(new FormData(form));
    const message = $("#observationFormMessage");
    const attribution = {};
    [["judgment", "判断错?"], ["timing", "时机错?"], ["position", "仓位错?"], ["tool", "工具错?"], ["execution", "执行错?"]].forEach(([key, label]) => {
      if (values[`attr_${key}`]) attribution[label] = values[`attr_${key}`];
    });
    const updated = {...item};
    updated.tradeStatus = values.tradeStatus;
    updated.executed = values.tradeStatus !== "no_trade";
    updated.direction = values.direction;
    updated.mainContradiction = values.mainContradiction.trim();
    updated.trigger = values.trigger.trim();
    updated.positionPct = values.positionPct.trim();
    updated.stopLossTakeProfit = values.stopLossTakeProfit.trim();
    updated.closeNote = values.closeNote.trim();
    updated.myPnl = values.myPnl === "" ? null : numeric(values.myPnl);
    updated.noTradeReason = values.noTradeReason.trim();
    updated.reviewNote = values.reviewNote.trim();
    updated.selfInquiry = values.selfInquiry.trim();
    updated.review = values.review.trim();
    updated.attribution = Object.keys(attribution).length ? attribution : null;
    updated.editedAt = new Date().toISOString();
    if (values.tradeStatus === "closed" && !values.closeNote.trim()) {
      message.textContent = "已平仓必须填写平仓记录。";
      return;
    }
    if (updated.executed && !updated.review.trim() && updated.myPnl == null) {
      message.textContent = "已执行记录至少补填盈亏或复盘内容之一。";
      return;
    }
    HistoryStore.putObservation(updated);
    state.editingObservationId = null;
    renderDecisionView();
    renderHistoryView();
    renderCloudSyncStatus();
    setTimeout(renderCloudSyncStatus, 2500);
  });
  $("#exportUserJournalBtn")?.addEventListener("click", exportUserJournal);
  $("#cloudSyncBtn")?.addEventListener("click", cloudSyncAction);
  renderCloudSyncStatus();
  window.addEventListener("fr:set-date", (event) => setDate(event.detail));
  $("#symbolFilter").addEventListener("change", (event) => { state.symbol = event.target.value; renderInstrumentTable(); });
  $("#searchInput").addEventListener("input", (event) => { state.query = event.target.value; renderInstrumentTable(); });
  $("#sectorFilter").addEventListener("change", (event) => { state.sector = event.target.value; renderInstrumentTable(); });
  $("#detailSymbolFilter").addEventListener("change", (event) => { if (event.target.value) { state.activeSymbol = event.target.value; renderDetailWorkspace(); } });
  $("#detailSearchInput").addEventListener("input", (event) => { state.detailQuery = event.target.value; renderDetailWorkspace(); });
  $("#detailSectorFilter").addEventListener("change", (event) => { state.detailSector = event.target.value; renderDetailWorkspace(); });
  $("#historyControls").addEventListener("change", (event) => { if (event.target.id === "historySymbolSelect") { state.historySymbol = event.target.value; renderHistory(); } });
  $("#decisionSectorFilter").addEventListener("change", (event) => { state.decisionSector = event.target.value; state.decisionSymbol = "all"; state.decisionPage = 1; renderDecisionView(); });
  $("#decisionSymbolFilter").addEventListener("change", (event) => { state.decisionSymbol = event.target.value; state.decisionPage = 1; renderDecisionView(); });
  $("#decisionSearchInput").addEventListener("input", (event) => { state.decisionQuery = event.target.value; state.decisionPage = 1; renderDecisionView(); });
  $("#ctaSearchInput").addEventListener("input", (event) => { state.ctaQuery = event.target.value; renderCta(); });
  $("#ctaSectorFilter").addEventListener("change", (event) => { state.ctaSector = event.target.value; state.activeCtaSymbol = null; renderCta(); });
  $("#ctaDirectionFilter").addEventListener("change", (event) => { state.ctaDirection = event.target.value; state.activeCtaSymbol = null; renderCta(); });
  $("#decisionEditor").addEventListener("submit", (event) => {
    if (event.target.id !== "decisionForm") return;
    event.preventDefault();
    const record = state.decisions.find((entry) => entry.id === state.activeDecisionId);
    if (!record) return;
    const values = Object.fromEntries(new FormData(event.target));
    const message = $("#decisionFormMessage");
    const attribution = {};
    [["judgment", "判断错？"], ["timing", "时机错？"], ["position", "仓位错？"], ["tool", "工具错？"], ["execution", "执行错？"]].forEach(([key, label]) => {
      if (values[`attr_${key}`]) attribution[label] = values[`attr_${key}`];
    });
    if (values.tradeStatus === "closed" && !values.closeNote.trim()) { message.textContent = "已平仓必须填写平仓记录。"; return; }
    if (values.tradeStatus === "closed" && !values.reviewNote.trim()) { message.textContent = "已平仓必须写最大错误与下一条规则。"; return; }
    Object.assign(record, values, {attribution, updatedAt: new Date().toISOString()});
    delete record.attr_judgment; delete record.attr_timing; delete record.attr_position; delete record.attr_tool; delete record.attr_execution;
    saveDecisions();
    syncDecisionToHistory(record);
    renderDecisionView();
    renderHistoryView();
    if (message) message.textContent = "";
  });
}

/* 快照懒加载层：启动只拉几 KB 的 meta + 最新日快照即出首屏（原整包 dashboard.json ~24MB）。
   其余历史快照在首屏渲染后由后台静默补齐（写入 state.data.snapshots，浏览器 HTTP 缓存兜底回访）。 */
function fetchSnapshot(date) {
  return fetch(`data/snapshots/${date}.json`).then((response) => {
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  });
}
const snapshotPending = new Map(); /* 日期 -> 进行中的请求，避免重复拉取 */
function ensureSnapshot(date) {
  if (!date || !state.data || state.data.snapshots[date]) return Promise.resolve(state.data?.snapshots[date] || null);
  if (!snapshotPending.has(date)) {
    const request = fetchSnapshot(date).then((snapshot) => {
      state.data.snapshots[date] = snapshot;
      snapshotPending.delete(date);
      return snapshot;
    }).catch((error) => {
      snapshotPending.delete(date);
      throw error;
    });
    snapshotPending.set(date, request);
  }
  return snapshotPending.get(date);
}
function preloadHistoricalSnapshots() {
  /* 并发补载（窗口 4）：最近 5 个交易日先行——序列图/5日涨跌最先可用，其余按新→旧全量补齐；
     单日失败跳过不打断（与原串行版一致） */
  const CONCURRENCY = 4;
  const drain = async (dates) => {
    let index = 0;
    const worker = async () => {
      while (index < dates.length) {
        const date = dates[index++];
        try { await ensureSnapshot(date); } catch (error) { /* 失败跳过 */ }
      }
    };
    await Promise.all(Array.from({length: Math.min(CONCURRENCY, dates.length)}, worker));
  };
  const missing = (state.data.dates || []).filter((date) => !state.data.snapshots[date]);
  return drain(missing.slice(0, 5)).then(() => drain(missing.slice(5)));
}
const dashboardLoad = fetch("data/dashboard-meta.json", {cache: "no-store"})
  .then((response) => { if (!response.ok) throw new Error(`HTTP ${response.status}`); return response.json(); })
  .then((meta) => fetchSnapshot(meta.latestDate).then((snapshot) => ({
    generatedAt: meta.generatedAt,
    dates: meta.dates,
    latestDate: meta.latestDate,
    snapshots: {[meta.latestDate]: snapshot},
  })))
  .catch(() => fetch("data/dashboard.json").then((response) => { if (!response.ok) throw new Error(`HTTP ${response.status}`); return response.json(); })); /* 旧数据无 meta 时回退整包 */

Promise.all([
  dashboardLoad,
  fetch("run-manifest.json", {cache: "no-store"}).then((response) => response.ok ? response.json() : null),
  typeof HistoryStore !== "undefined" ? HistoryStore.init().catch((error) => ({observations: [], trades: [], narratives: [], months: [], errors: [String(error.message || error)]})) : Promise.resolve(null),
])
  .then(([data, manifest, history]) => {
    state.data = data;
    state.manifest = manifest;
    state.decisions = loadDecisions();
    state.date = data.latestDate;
    state.history = history || {observations: [], trades: [], narratives: [], months: [], errors: []};
    state.activeSymbol = data.snapshots[data.latestDate].tripleResonance[0]?.symbol || data.snapshots[data.latestDate].instruments[0]?.symbol;
    bindEvents();
    renderAll();
    const viewParams = new URLSearchParams(window.location.search);
    const viewParam = viewParams.get("view");
    if (viewParam && ["overview", "detail", "instruments", "cta", "history", "decisions"].includes(viewParam)) switchView(viewParam);
    const journalParam = viewParams.get("historySymbol");
    if (journalParam) { state.historyJournalSymbol = journalParam.toUpperCase(); if (state.view === "decisions") renderHistoryView(); }
    /* 打开页面自动双向同步一次私有数据仓(有 Token 时):远端新记录并入、本地新写推上去 */
    if (JournalSync?.hasToken() && typeof HistoryStore !== "undefined") {
      renderCloudSyncStatus();
      HistoryStore.pushToCloud()
        .then(() => { renderHistoryView(); renderDecisionView(); renderCloudSyncStatus(); })
        .catch(() => { const el = document.getElementById("cloudSyncStatus"); if (el) el.textContent = "● 同步失败，点右侧按钮重试"; });
    }
    $("#app").dataset.ready = "true";
    /* 首屏已出：后台补齐其余历史快照（串行），补完后重渲染一次填充序列图/5日涨跌；
       decisions 视图含表单，避免重渲染清空输入，留给下次切换视图时自然取数 */
    preloadHistoricalSnapshots().then(() => { if (state.view !== "decisions") renderAll(); });
  })
  .catch((error) => {
    $("#loadingState").textContent = `数据装载失败：${error.message}。请通过本地 HTTP 服务打开。`;
  });

/* 「📤 导出我的复盘」按钮：把工作台新写的 observation（source=工作台日志）打包成 JSON 下载。
   用途：本地 IndexedDB 推不到 GitHub，你下载后发给 agent，agent 追加到
   data/imported/user_journal.json 并 push，下次刷新页面自动加载。 */
function exportUserJournal() {
  if (typeof HistoryStore === "undefined") return;
  const data = HistoryStore.exportUserJournal();
  const btn = document.getElementById("exportUserJournalBtn");
  const flash = (text) => { if (!btn) return; const original = btn.textContent; btn.textContent = text; btn.disabled = true; setTimeout(() => { btn.textContent = original; btn.disabled = false; }, 2000); };
  if (!data.count) { flash("暂无新复盘可导出"); return; }
  const blob = new Blob([JSON.stringify(data, null, 2)], {type: "application/json"});
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  const stamp = new Date().toISOString().slice(0, 10);
  a.href = url;
  a.download = `user_journal_${stamp}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  flash(`✓ 已导出 ${data.count} 条到下载文件夹`);
}

/* 「🔐 云端同步」：配置 Token / 立即同步。
   Token 为 GitHub fine-grained PAT（只授权 futures-journal-data 的 Contents 读写），
   存 localStorage，不进 git；与 digital-garden 的同步模型一致。
   首次配置后立即做一次全量推送，把本地历史复盘（Excel/md 导入 + 已写复盘）落到私有仓。 */
function cloudSyncAction() {
  if (typeof JournalSync === "undefined" || typeof HistoryStore === "undefined") return;
  if (!JournalSync.hasToken()) {
    const input = window.prompt("粘贴 GitHub fine-grained Token（仅授权 futures-journal-data 仓库 Contents 读写）。\nToken 只保存在本机浏览器，不会进入代码或公开仓库：");
    if (!input || !input.trim()) return;
    JournalSync.setToken(input.trim());
  }
  const btn = document.getElementById("cloudSyncBtn");
  const status = document.getElementById("cloudSyncStatus");
  if (btn) { btn.textContent = "⏳ 同步中…"; btn.disabled = true; }
  HistoryStore.pushToCloud()
    .then((result) => {
      renderCloudSyncStatus();
      if (btn) { btn.textContent = "🔐 云端同步"; btn.disabled = false; }
      if (result.local) {
        if (status) status.textContent = "（未配置 Token，仅本地）";
      } else {
        const count = (result.data.observations || []).length + (result.data.trades || []).length;
        if (status) status.textContent = `✓ 已同步 ${count} 条`;
        renderHistoryView();
      }
    })
    .catch((error) => {
      if (btn) { btn.textContent = "🔐 云端同步"; btn.disabled = false; }
      if (status) status.textContent = `✗ ${error.message}`;
      if (/Token 无效/.test(String(error.message))) JournalSync.setToken("");
    });
}

function renderCloudSyncStatus() {
  const status = document.getElementById("cloudSyncStatus");
  if (!status || typeof JournalSync === "undefined") return;
  if (!JournalSync.hasToken()) { status.textContent = "○ 未连接（仅本地）"; return; }
  const st = typeof HistoryStore !== "undefined" && HistoryStore.syncState ? HistoryStore.syncState() : null;
  if (st && st.unsynced > 0) status.textContent = `● 私有数据仓已连接 · ${st.unsynced} 条待同步（点右侧按钮重试）`;
  else if (st && st.lastPushAt) status.textContent = `● 已同步 ${st.lastPushAt}`;
  else status.textContent = "● 已连接私有数据仓";
}
