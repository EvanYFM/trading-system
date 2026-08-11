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
const DETAIL_SEARCH_ALIASES = { FU: "燃油", AG: "白银", JM: "焦煤", LH: "生猪", LC: "碳酸锂", JD: "鸡蛋" };
const CORE_GROUPS = [
  ["贵金属", ["AU", "AG"]],
  ["有色金属", ["SN", "LC"]],
  ["能源化工", ["FU"]],
  ["黑色系", ["JM"]],
  ["家人品种", ["FG", "SA", "AO", "SH"]],
  ["农产品", ["M", "JD", "LH"]],
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

function flowRelationClass(entry) {
  const position = Math.sign(numeric(entry.netPosition));
  const flow = Math.sign(numeric(entry.flowScore));
  return !position || !flow ? "neutral-text" : position === flow ? "seat-flow-aligned" : "seat-flow-opposite";
}

function maxAbs(items, getter) {
  return Math.max(1, ...items.map((item) => Math.abs(numeric(getter(item)))));
}

function renderDateControls() {
  const options = state.data.dates.map((date) => `<option value="${date}" ${date === state.date ? "selected" : ""}>${formatDate(date)}</option>`).join("");
  $("#dateSelect").innerHTML = options;
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

function sectorSide(items, side) {
  if (!items.length) return `<div class="empty-side">今天没有净${side === "bullish" ? "多" : "空"}品种</div>`;
  const scale = maxAbs(items, (item) => item.value);
  return items.map((item) => `<button class="sector-item" data-open-symbol="${escapeHtml(item.symbol)}" aria-label="查看${escapeHtml(item.variety)}详情">
    <span class="sector-item-name">${escapeHtml(item.variety)} <small>${escapeHtml(item.symbol)}</small></span>
    <span class="sector-meter"><span class="sector-meter-fill ${dirClass(item.value)}" style="width:${Math.max(5, Math.abs(item.value) / scale * 100)}%"></span></span>
    <strong class="${signClass(item.value)}">${formatAmount(item.value)}</strong>
  </button>`).join("");
}

function renderSectors() {
  $("#sectorGrid").innerHTML = currentSnapshot().sectorSummary.map((sector) => `<article class="sector-block">
    <div class="sector-title"><strong>${escapeHtml(sector.sector)}</strong><span class="sector-count">${sector.bullishCount} 多 · ${sector.bearishCount} 空</span></div>
    <div class="sector-sides">
      <div class="sector-side"><div class="side-title bull-text">净多前三</div>${sectorSide(sector.bullish, "bullish")}</div>
      <div class="sector-side"><div class="side-title bear-text">净空前三</div>${sectorSide(sector.bearish, "bearish")}</div>
    </div>
  </article>`).join("");
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
  $("#corePanorama").innerHTML = `<div class="panorama-head"><span>板块</span><span>品种 / 行情</span><span>三方净变动</span><span>内资 / 外资 / 家人反向</span><span>趋势与信号</span></div>${groups.map((group) => `<section class="panorama-group"><header>${escapeHtml(group.sector)}</header><div class="panorama-group-rows">${group.items.map((item) => {
    const quote = item.quote;
    return `<button class="panorama-row" data-open-symbol="${escapeHtml(item.symbol)}">
      <span class="panorama-name"><strong>${escapeHtml(item.variety)} ${escapeHtml(item.symbol)}</strong><small>${escapeHtml(item.sector)} · ${escapeHtml(quote?.contract || item.margin.contract || "主力待披露")}</small>${quote ? `<em>${numeric(quote.close).toLocaleString("zh-CN", {maximumFractionDigits:4})} <b class="${signClass(quote.changePct)}">${formatSigned(quote.changePct, 2)}%</b></em>` : `<em>行情暂无</em>`}</span>
      <span class="panorama-signal"><strong class="${signClass(item.amountSignal)}">${formatAmount(item.amountSignal)}</strong><small class="${signClass(item.handsSignal)}">${formatHands(item.handsSignal)} 手 · ${escapeHtml(item.marginalStructure || "边际待判")}</small></span>
      <span>${groupBars(item)}</span>
      <span class="panorama-tags">${trendChip(item.trend)}<span class="tag ${dirClass(item.amountSignal)}">${escapeHtml(item.resonance.label || item.direction)}</span></span>
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
    ["收盘行情", sourceFileDate(summary.quoteSourceFile), `${summary.quoteFreshCount}/${summary.instrumentCount} 与报告日同日 · 东方财富`],
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

function percentage(value, digits = 1) {
  return `${(numeric(value) * 100).toFixed(digits)}%`;
}

function wuxingSeasonalityPanel(item) {
  const data = item.wuxingSeasonality;
  if (!data || data.status !== "OK") return "";
  const current = data.currentMonth || {};
  const resonance = data.resonance || {};
  const qualified = Boolean(data.qualified);
  const stateClass = data.judgement === "历史正向共振" ? "bullish" : data.judgement === "历史负向共振" ? "bearish" : "neutral";
  const probabilityRows = [
    ["上涨", resonance.upProbability, "bullish"],
    ["震荡", resonance.flatProbability, "neutral"],
    ["下跌", resonance.downProbability, "bearish"],
  ];
  return `<section id="detail-wuxing" class="detail-surface detail-wide-section wuxing-section">
    <div class="detail-section-head"><div><small>SEASONALITY BACKTEST</small><h3>五行月份回测</h3></div><span class="detail-stamp ${stateClass}">${qualified ? escapeHtml(data.judgement) : "未通过统计门槛"}</span></div>
    <div class="wuxing-summary">
      <article><small>品种属性</small><strong>${escapeHtml(data.attributeElement)}</strong><p>先验分类标签</p></article>
      <article><small>当前月份</small><strong>${current.month || "-"}月 · ${escapeHtml(current.branch || "-")}月 · ${escapeHtml(current.element || "-")}</strong><p>${current.resonates ? "与品种属性同元素" : "本月不是同元素月"}</p></article>
      <article><small>点二列相关</small><strong>${numeric(data.correlation).toFixed(3)}</strong><p>FDR q=${numeric(data.fdrQValue).toFixed(3)}</p></article>
      <article><small>收益效应差</small><strong class="${signClass(data.effect)}">${percentage(data.effect, 2)}</strong><p>同元素月均值减其他月份</p></article>
      <article><small>样本</small><strong>${resonance.sampleCount || 0} / ${data.totalMonths || 0}</strong><p>同元素月 / 全部月度</p></article>
    </div>
    <div class="wuxing-probability">
      <div class="wuxing-probability-bars">${probabilityRows.map(([label, value, className]) => `<div><span>${label}</span><i><b class="${className}" style="width:${Math.max(0, Math.min(100, numeric(value) * 100))}%"></b></i><strong>${percentage(value)}</strong></div>`).join("")}</div>
      <div class="wuxing-month-strip">${(data.monthCalendar || []).map((entry) => `<span class="${entry.element === data.attributeElement ? "is-resonant" : ""} ${entry.month === current.month ? "is-current" : ""}"><b>${entry.month}月</b><em>${escapeHtml(entry.branch)}·${escapeHtml(entry.element)}</em></span>`).join("")}</div>
    </div>
    <p class="wuxing-readout">${qualified && current.resonates ? `本月处于同元素月；历史样本上涨 ${percentage(resonance.upProbability)}、震荡 ${percentage(resonance.flatProbability)}、下跌 ${percentage(resonance.downProbability)}。` : current.resonates ? "本月属性相同，但历史相关性未通过门槛，不形成方向信号。" : "本月不是该品种的同元素月；历史统计仅作研究背景。"}</p>
    <p class="detail-panel-note">来源：${escapeHtml(data.source)}，样本截至 ${escapeHtml(data.dataEndDate || "无数据")}。月收益按月末主力连续收盘计算；上涨/下跌阈值为 ±1%。五行属性是待检验分类，不是因果机制，也不构成投资建议。</p>
  </section>`;
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
  $("#instrumentRows").innerHTML = rows.map((item) => `<tr class="${item.symbol === state.activeSymbol ? "is-active" : ""}" data-symbol="${escapeHtml(item.symbol)}">
    <td><div class="instrument-name"><strong>${escapeHtml(item.variety)}</strong><small>${escapeHtml(item.symbol)} · ${escapeHtml(item.sector)}</small></div></td>
    <td class="num ${signClass(item.handsSignal)}">${formatHands(item.handsSignal)}</td>
    <td class="num ${signClass(item.amountSignal)}">${formatAmount(item.amountSignal)}</td>
    <td>${groupBars(item)}</td>
    <td class="trend-cell">${trendChip(item.trend)}</td>
    <td><span class="tag ${dirClass(item.amountSignal)}">${escapeHtml(item.resonance.label || item.direction)}</span></td>
  </tr>`).join("") || `<tr><td colspan="6" class="detail-empty">当前筛选条件下没有品种。</td></tr>`;
  renderDetail();
}

function seriesFor(symbol) {
  return state.data.dates.filter((date) => date <= state.date).reverse().map((date) => {
    const item = state.data.snapshots[date].instruments.find((entry) => entry.symbol === symbol);
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

function sparkline(values, tone = "bullish", large = false, dates = []) {
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
  return `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="历史净变化曲线，纵轴为资金净变动金额">${grid}<line class="spark-y-axis" x1="${padding.left}" x2="${padding.left}" y1="${padding.top}" y2="${height - padding.bottom}"></line><polyline class="spark-line ${tone}" points="${points}"></polyline><text class="spark-label" x="${padding.left}" y="${height - 7}">${firstDate}</text><text class="spark-label" x="${width - padding.right}" y="${height - 7}" text-anchor="end">${lastDate}</text></svg>`;
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
  return items.length ? items.map((entry) => `<div class="seat-rank-row"><span class="seat-rank-name">${escapeHtml(entry.broker)}（${escapeHtml(brokerGroupLabel(entry))}）</span><strong class="${tone}">${formatHands(entry.netPosition)}</strong><span class="seat-flow ${flowRelationClass(entry)}">今日 ${formatHands(entry.flowScore)}</span></div>`).join("") : `<div class="seat-rank-row"><span class="detail-empty">${emptyText}</span></div>`;
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
  const trend = item.trend;
  const wuxingPanel = wuxingSeasonalityPanel(item);
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
  $("#detailWorkspace").innerHTML = `<header class="instrument-detail-hero">
      <div class="instrument-detail-title"><span class="instrument-sector-mark"></span><div><p>${escapeHtml(item.sector)} · ${escapeHtml(item.margin.exchange || "交易所未披露")}</p><h2>${escapeHtml(item.variety)} <em>${escapeHtml(item.symbol)}</em></h2></div><span class="contract-pill">主力 ${escapeHtml(quote?.contract || item.margin.contract || "未披露")}</span></div>
      <div class="instrument-detail-quote"><div><small>涨跌幅</small><strong class="${quote?.changePct == null ? "" : signClass(quote.changePct)}">${quote?.changePct == null ? "暂无" : `${formatSigned(quote.changePct, 2)}%`}</strong></div><div><small>收盘价</small><strong>${formatPrice(quote?.close)}</strong></div><div><small>三方资金</small><strong class="${signClass(item.amountSignal)}">${formatAmount(item.amountSignal)}</strong></div></div>
    </header>
    <div class="detail-source-notice"><strong>真实快照</strong> 席位披露 ${escapeHtml(disclosure)}；行情 ${escapeHtml(quote?.sourceDate || "无数据")}；趋势 ${escapeHtml(trend?.sourceDate || "无数据")}。来源日期不同则分开标记，不视为同日事实。</div>
    <section class="evidence-rail" aria-label="证据链摘要">
      <article><span>01</span><small>行情结构</small><strong class="${quote?.changePct == null ? "" : signClass(quote.changePct)}">${quote?.changePct == null ? "暂无行情" : quote.changePct > 0 ? "当日上涨" : quote.changePct < 0 ? "当日下跌" : "当日持平"}</strong><p>${quote ? `${formatPrice(quote.low)}–${formatPrice(quote.high)} · 东方财富` : "未取得主力行情"}</p></article>
      <article><span>02</span><small>趋势温度</small><strong>${escapeHtml(trendState)}</strong><p>${trend ? `强度 ${formatSigned(trend.strength, 1)}${trend.fresh ? "" : " · 非当日"}` : "趋势动物未匹配"}</p></article>
      <article><span>03</span><small>三方资金</small><strong class="${signClass(item.amountSignal)}">${formatAmount(item.amountSignal)}</strong><p>${formatHands(item.handsSignal)} 手 · ${escapeHtml(item.marginalStructure)}</p></article>
      <article><span>04</span><small>席位结构</small><strong>${escapeHtml(seatBias)}</strong><p>净多 ${item.brokerRanking.netLong.length}/5 · 净空 ${item.brokerRanking.netShort.length}/5</p></article>
      <article class="decision"><span>结论</span><small>研究状态</small><strong>${escapeHtml(researchState)}</strong><p>${escapeHtml(item.resonance.label || item.direction)}</p></article>
    </section>
    <nav class="detail-subnav" aria-label="品种详情导航"><button class="is-active" data-detail-anchor="detail-overview">总览</button><button data-detail-anchor="detail-positioning">资金与席位</button><button data-detail-anchor="detail-technical">技术面</button><button data-detail-anchor="detail-trend">趋势</button>${wuxingPanel ? `<button data-detail-anchor="detail-wuxing">五行季节性</button>` : ""}<button data-detail-anchor="detail-fundamental">基本面</button><button data-detail-anchor="detail-events">历史事件</button></nav>
    <section id="detail-overview" class="detail-dashboard-grid">
      <article class="detail-surface chart-surface"><div class="detail-section-head"><div><small>PRICE & FLOW</small><h3>价格与三方资金</h3></div><div class="detail-legend"><i></i>收盘价 <b></b>资金净变动</div></div><div class="combo-chart-wrap">${priceFlowChart(series, item.variety)}</div><div class="detail-chart-foot"><span>历史快照 <b>${series.length} 日</b></span><span>今日手数 <b class="${signClass(item.handsSignal)}">${formatHands(item.handsSignal)}</b></span><span>边际结构 <b>${escapeHtml(item.marginalStructure)}</b></span></div></article>
      <aside class="detail-surface executive-surface"><div class="detail-section-head"><div><small>EXECUTIVE READ</small><h3>今日研究读数</h3></div></div><dl><div><dt>接口事实</dt><dd>${trend ? `趋势温度“${escapeHtml(trend.temperature)}”，强度 ${formatSigned(trend.strength, 1)}，${trend.rightSide ? "处于右侧" : "未处于右侧"}。` : "趋势数据暂无。"} 三方资金 ${formatAmount(item.amountSignal)}。</dd></div><div><dt>策略判断</dt><dd>${escapeHtml(relationship)}；席位信号为“${escapeHtml(item.resonance.label || item.direction)}”。这是规则化解读，不是接口原文。</dd></div><div><dt>基本面验证</dt><dd>${escapeHtml(fundamentalRead)}</dd></div></dl><button class="detail-action" data-create-decision="${escapeHtml(item.symbol)}">转入人工决策</button><button class="detail-action secondary" data-view="history">查看完整历史路径</button></aside>
    </section>
    <section id="detail-positioning" class="detail-surface detail-wide-section"><div class="detail-section-head"><div><small>POSITIONING</small><h3>资金与席位结构</h3></div><p>存量净持仓与今日边际分列；家人按原始方向展示</p></div><div class="position-matrix"><div class="position-matrix-head"><span>资金群体</span><span>存量净持仓</span><span>今日净金额</span><span>边际动作</span></div>${groupRows.map(([label, group]) => `<div class="position-matrix-row"><b>${label}</b>${positionVisual(group.netPosition, stockScale)}<strong class="${signClass(group.amount)}">${formatAmount(group.amount)}</strong><span>${escapeHtml(flowAction(group))}</span></div>`).join("")}</div><div class="seat-rank-grid detail-ranks"><div class="seat-rank-list"><div class="seat-rank-title bull-text">净多席位 ${item.brokerRanking.netLong.length}/5</div>${rankRows(item.brokerRanking.netLong, "bull-text", "暂无净多席位")}</div><div class="seat-rank-list"><div class="seat-rank-title bear-text">净空席位 ${item.brokerRanking.netShort.length}/5</div>${rankRows(item.brokerRanking.netShort, "bear-text", "暂无净空席位")}</div></div></section>
    <section class="detail-split">
      <article id="detail-trend" class="detail-surface"><div class="detail-section-head"><div><small>TREND REGIME</small><h3>趋势与周期</h3></div><span class="detail-stamp">API事实</span></div><div class="temperature-scale">${tempOrder.map((name) => `<span class="${trend?.temperature === name ? "is-active" : ""}">${name}</span>`).join("")}</div><div class="trend-fact-row"><span>趋势强度</span><strong>${trend ? formatSigned(trend.strength, 1) : "暂无"}</strong></div><div class="trend-fact-row"><span>右侧状态</span><strong>${trend ? (trend.rightSide ? "是" : "否") : "暂无"}</strong></div><div class="trend-fact-row"><span>进入天数</span><strong>${trend?.daysSinceEntry == null ? "暂无" : `${trend.daysSinceEntry} 天`}</strong></div><p class="detail-panel-note">趋势动物直接事实与本页资金判断分列。温度为“平”或数据非当日时，不把它写成右侧趋势确认。</p></article>
      <article id="detail-technical" class="detail-surface technical-section compact-technical"><div class="detail-section-head"><div><small>TECHNICAL EXECUTION</small><h3>双周期技术验证</h3></div><span class="detail-stamp ${technical?.bias === "偏多" ? "bullish" : technical?.bias === "偏空" ? "bearish" : "neutral"}">${technical ? escapeHtml(technical.bias) : "未接入"}</span></div>
        ${technical ? `<div class="technical-period-grid">${timeframeEvidence("日线观察", technical.dailyChan, technical.dailyObservation)}${timeframeEvidence("60分钟观察", technical.chan60, technical.hourObservation)}</div><div class="technical-compact-read"><p><b>量仓：</b>${escapeHtml(technical.marketActivity?.label || "数据不足")} · ${escapeHtml(technical.marketActivity?.impulse || "无法确认")}；成交较前日 ${technical.marketActivity?.volumeRatio == null ? "暂无" : technicalValue((technical.marketActivity.volumeRatio - 1) * 100, 1, "%")}。</p><p><b>位置：</b>支撑 ${levelText(technical.keyLevels?.supports, "暂无")}；压力 ${levelText(technical.keyLevels?.resistances, "暂无")}。</p><p><b>双周期：</b>${escapeHtml(technicalRead)}。</p></div><p class="detail-panel-note">EMA顺序为 5 / 20 / 60；数据日 ${escapeHtml(technical.sourceDate)}，60分钟截至 ${escapeHtml(technical.chan60?.endTime || "无法确认")}。技术观察不替代资金面与基本面。</p>` : `<div class="data-gap"><strong>当前技术面覆盖沪银、焦煤、燃油、生猪、碳酸锂和鸡蛋</strong><p>该品种尚未生成技术快照，不使用其他品种或旧日数据填充。</p></div>`}</article>
    </section>
    <article id="detail-fundamental" class="detail-surface detail-wide-section fundamental-surface"><div class="detail-section-head"><div><small>FUNDAMENTALS</small><h3>基本面证据板</h3></div><span class="detail-stamp neutral">事实与缺口分列</span></div>${fundamentalEvidence(item)}<p class="detail-panel-note">基差口径为现货价减主力期货价；仓单使用东方财富期货库存数据。供需、现金成本与产业库存未接入前不作推断。</p></article>
    ${wuxingPanel}
    <section id="detail-events" class="detail-surface detail-wide-section"><div class="detail-section-head"><div><small>EVENT PATH</small><h3>历史事件</h3></div><p>快照事实按披露日追溯</p></div><div class="event-timeline">${recentEvents.map((entry) => `<div><time>${formatDate(entry.date)}</time><b class="${signClass(entry.amount)}">${formatAmount(entry.amount)}</b><p>${escapeHtml(entry.structure)} · ${formatHands(entry.hands)} 手${entry.close == null ? "" : ` · 收盘 ${formatPrice(entry.close)}`}</p></div>`).join("")}</div></section>`;
}

function renderDetail() {
  const item = currentSnapshot().instruments.find((entry) => entry.symbol === state.activeSymbol);
  if (!item) {
    $("#detailPanel").innerHTML = `<div class="detail-empty">从左侧选择一个品种，查看三组资金拆解与历史路径。</div>`;
    return;
  }
  const series = seriesFor(item.symbol);
  const groupRows = [
    ["内资", item.groups.domestic], ["外资", item.groups.foreign], ["家人原始", item.groups.family], ["家人反向", item.groups.familyReverse]
  ];
  const closePrice = item.quote?.close;
  const dayReturn = item.quote?.changePct;
  const stockScale = maxAbs(groupRows, ([, group]) => group.netPosition);
  $("#detailPanel").innerHTML = `<div class="detail-header"><div><h3>${escapeHtml(item.variety)} <small>${escapeHtml(item.symbol)}</small></h3><p>${escapeHtml(item.sector)} · ${escapeHtml(item.quote?.contract || item.margin.contract || "主力合约未披露")} · ${escapeHtml(item.margin.exchange || "")}</p></div><div class="detail-side"><div class="detail-market"><div class="detail-quote"><small>涨跌幅</small><strong class="${dayReturn == null ? "" : signClass(dayReturn)}">${dayReturn == null ? "暂无" : `${formatSigned(dayReturn, 2)}%`}</strong></div><div class="detail-quote"><small>收盘价</small><strong>${closePrice == null ? "暂无" : numeric(closePrice).toLocaleString("zh-CN", {maximumFractionDigits: 4})}</strong></div></div><div class="detail-direction ${signClass(item.amountSignal)}">${escapeHtml(item.direction)}</div></div></div>
    <div class="detail-metrics">
      <div class="detail-metric"><span>三方手数净变动</span><strong class="${signClass(item.handsSignal)}">${formatHands(item.handsSignal)}</strong></div>
      <div class="detail-metric"><span>三方资金净变动</span><strong class="${signClass(item.amountSignal)}">${formatAmount(item.amountSignal)}</strong></div>
      <div class="detail-metric"><span>总持仓边际</span><strong>${formatHands(item.totalPositionChange)}</strong></div>
      <div class="detail-metric"><span>一手保证金</span><strong>${numeric(item.margin.perLot).toLocaleString("zh-CN", {maximumFractionDigits:0})}</strong></div>
    </div>
    <div class="detail-section"><h4>三组存量与今日边际</h4><div class="stock-delta-head"><span></span><span>净持仓</span><span>今日边际</span></div>${groupRows.map(([label, group]) => `<div class="stock-delta"><span>${label}</span>${positionVisual(group.netPosition, stockScale)}<strong class="${signClass(group.amount)}">${formatAmount(group.amount)}</strong></div>`).join("")}</div>
    <div class="detail-section"><h4>样本席位净持仓前五</h4><div class="seat-rank-grid"><div class="seat-rank-list"><div class="seat-rank-title bull-text">净多席位 ${item.brokerRanking.netLong.length}/5</div>${rankRows(item.brokerRanking.netLong, "bull-text", "暂无净多席位")}</div><div class="seat-rank-list"><div class="seat-rank-title bear-text">净空席位 ${item.brokerRanking.netShort.length}/5</div>${rankRows(item.brokerRanking.netShort, "bear-text", "暂无净空席位")}</div></div></div>`;
}

function renderHistory() {
  const symbols = currentSnapshot().instruments.map((item) => ({symbol: item.symbol, variety: item.variety}));
  if (!state.historySymbol || !symbols.some((item) => item.symbol === state.historySymbol)) state.historySymbol = state.activeSymbol || symbols[0]?.symbol;
  $("#historyControls").innerHTML = `<label>观察品种 <select id="historySymbolSelect">${symbols.map((item) => `<option value="${escapeHtml(item.symbol)}" ${item.symbol === state.historySymbol ? "selected" : ""}>${escapeHtml(item.variety)} ${escapeHtml(item.symbol)}</option>`).join("")}</select></label>`;
  const series = seriesFor(state.historySymbol);
  const current = currentSnapshot().instruments.find((item) => item.symbol === state.historySymbol);
  $("#historyPanel").innerHTML = `<section class="history-chart"><h3>${escapeHtml(current?.variety || state.historySymbol)} · 三方资金净变动</h3><div class="large-spark">${sparkline(series.map((entry) => entry.amount), dirClass(series.at(-1)?.amount || 0), true, series.map((entry) => entry.date))}</div></section>
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

function reviewDueDate(reportDate) {
  const dates = [...state.data.dates].sort();
  const index = dates.indexOf(reportDate);
  return index >= 0 ? dates[index + 5] || "" : "";
}

function decisionChoiceLabel(choice) {
  return ({accept: "接受", reject: "拒绝", observe: "观察"})[choice] || "待确认";
}

function upsertDecision(symbol, choice) {
  const item = currentSnapshot().instruments.find((entry) => entry.symbol === symbol);
  if (!item) return;
  const id = `${state.date}-${symbol}`;
  let record = state.decisions.find((entry) => entry.id === id);
  if (!record) {
    record = {
      id, reportDate: state.date, symbol, variety: item.variety, choice,
      runId: state.manifest?.runId || state.date, createdAt: new Date().toISOString(),
      amountSignal: item.amountSignal, handsSignal: item.handsSignal,
      close: item.quote?.close ?? null, changePct: item.quote?.changePct ?? null,
      trend: item.trend?.temperature || "", mainContradiction: "", trigger: "", invalidation: "",
      tradeStatus: "no_trade", tradeLogRef: "", noTradeReason: "", exitResult: "",
      problemType: "pending", seeRight: "pending", doRight: "pending", doWell: "pending", reviewNote: "",
    };
    state.decisions.push(record);
  } else {
    record.choice = choice;
  }
  state.activeDecisionId = id;
  saveDecisions();
  renderDecisionView();
}

function renderDecisionView() {
  const triples = [...currentSnapshot().tripleResonance];
  const signals = [
    ...triples.filter((item) => numeric(item.amountSignal) > 0).sort((a, b) => numeric(b.amountSignal) - numeric(a.amountSignal)).slice(0, 5),
    ...triples.filter((item) => numeric(item.amountSignal) < 0).sort((a, b) => numeric(a.amountSignal) - numeric(b.amountSignal)).slice(0, 5),
  ];
  $("#decisionSignals").innerHTML = signals.length ? signals.map((item) => {
    const record = state.decisions.find((entry) => entry.id === `${state.date}-${item.symbol}`);
    return `<article class="decision-signal ${dirClass(item.amountSignal)}"><div><strong>${escapeHtml(item.variety)} ${escapeHtml(item.symbol)}</strong><small>${formatAmount(item.amountSignal)} · ${formatHands(item.handsSignal)} 手</small></div><div class="decision-choices">${[["accept","接受"],["reject","拒绝"],["observe","观察"]].map(([value, label]) => `<button class="${record?.choice === value ? "is-active" : ""}" data-decision-choice="${value}" data-decision-symbol="${escapeHtml(item.symbol)}">${label}</button>`).join("")}</div></article>`;
  }).join("") : `<div class="detail-empty">该日没有三方强共振信号。</div>`;

  const records = [...state.decisions].sort((a, b) => b.reportDate.localeCompare(a.reportDate) || a.symbol.localeCompare(b.symbol));
  $("#decisionList").innerHTML = records.length ? records.map((record) => `<button class="decision-list-item ${record.id === state.activeDecisionId ? "is-active" : ""}" data-edit-decision="${escapeHtml(record.id)}"><span><strong>${escapeHtml(record.variety)} ${escapeHtml(record.symbol)}</strong><small>${formatDate(record.reportDate)} · ${decisionChoiceLabel(record.choice)}</small></span><em>${record.tradeStatus === "closed" ? "已退出" : record.tradeStatus === "open" ? "持仓中" : "未交易"}</em></button>`).join("") : `<div class="detail-empty">尚无人工确认记录。</div>`;

  const record = state.decisions.find((entry) => entry.id === state.activeDecisionId);
  if (!record) {
    $("#decisionEditor").innerHTML = `<div class="detail-empty">先对一个工作站信号选择“接受 / 拒绝 / 观察”。</div>`;
    return;
  }
  const due = reviewDueDate(record.reportDate);
  const option = (value, label, current) => `<option value="${value}" ${current === value ? "selected" : ""}>${label}</option>`;
  $("#decisionEditor").innerHTML = `<form id="decisionForm"><header><div><small>${formatDate(record.reportDate)} · ${escapeHtml(record.runId)}</small><h3>${escapeHtml(record.variety)} ${escapeHtml(record.symbol)}</h3></div><strong class="${signClass(record.amountSignal)}">${formatAmount(record.amountSignal)}</strong></header>
    <div class="decision-facts"><span>手数 ${formatHands(record.handsSignal)}</span><span>收盘 ${formatPrice(record.close)}</span><span>涨跌 ${record.changePct == null ? "暂无" : `${formatSigned(record.changePct, 2)}%`}</span><span>趋势 ${escapeHtml(record.trend || "暂无")}</span></div>
    <div class="decision-form-grid">
      <label>人工确认<select name="choice">${option("accept","接受",record.choice)}${option("reject","拒绝",record.choice)}${option("observe","观察",record.choice)}</select></label>
      <label>交易状态<select name="tradeStatus">${option("no_trade","未交易",record.tradeStatus)}${option("open","持仓中",record.tradeStatus)}${option("closed","已退出",record.tradeStatus)}</select></label>
      <label class="wide">主要矛盾<textarea name="mainContradiction" rows="2">${escapeHtml(record.mainContradiction)}</textarea></label>
      <label>技术/价格触发<input name="trigger" value="${escapeHtml(record.trigger)}"></label>
      <label>证伪/失效条件<input name="invalidation" value="${escapeHtml(record.invalidation)}"></label>
      <label>交易日志编号或链接<input name="tradeLogRef" value="${escapeHtml(record.tradeLogRef)}" placeholder="手工日志中的编号、文件路径或链接"></label>
      <label>未交易原因<input name="noTradeReason" value="${escapeHtml(record.noTradeReason)}"></label>
      <label class="wide">退出结果<textarea name="exitResult" rows="2">${escapeHtml(record.exitResult)}</textarea></label>
      <label>问题归因<select name="problemType">${option("pending","待复盘",record.problemType)}${option("data","数据问题",record.problemType)}${option("judgment","判断问题",record.problemType)}${option("execution","执行问题",record.problemType)}${option("no_issue","无明显问题",record.problemType)}</select></label>
      <label>看对<select name="seeRight">${option("pending","待评",record.seeRight)}${option("yes","是",record.seeRight)}${option("no","否",record.seeRight)}</select></label>
      <label>做对<select name="doRight">${option("pending","待评",record.doRight)}${option("yes","是",record.doRight)}${option("no","否",record.doRight)}</select></label>
      <label>做好<select name="doWell">${option("pending","待评",record.doWell)}${option("yes","是",record.doWell)}${option("no","否",record.doWell)}</select></label>
      <label class="wide">五日复盘<textarea name="reviewNote" rows="3">${escapeHtml(record.reviewNote)}</textarea></label>
    </div><p class="decision-due">五个交易日后复盘：${due ? formatDate(due) : "历史快照尚未积累到复盘日"}</p><p id="decisionFormMessage" class="form-message" aria-live="polite"></p><div class="decision-form-actions"><button class="decision-save" type="submit">保存决策记录</button><button class="decision-delete" type="button" data-delete-decision="${escapeHtml(record.id)}">删除</button></div></form>`;
}

function renderAll() {
  renderDateControls();
  renderSummary();
  renderFocus();
  renderTide();
  renderSectors();
  renderCorePanorama();
  renderBrokerHighlights();
  renderStockIndices();
  renderOverviewStatus();
  renderDetailWorkspace();
  renderInstrumentTable();
  renderHistory();
  renderStatus();
  renderDecisionView();
}

function switchView(view) {
  state.view = view;
  $$(".nav-item").forEach((button) => button.classList.toggle("is-active", button.dataset.view === view));
  $$(".view").forEach((panel) => panel.classList.toggle("is-active", panel.id === `view-${view}`));
  if (view === "detail") renderDetailWorkspace();
  if (view === "history") renderHistory();
  if (view === "decisions") renderDecisionView();
}

function setDate(date) {
  state.date = date;
  state.symbol = "all";
  state.sector = "all";
  state.detailSector = "all";
  state.detailQuery = "";
  renderAll();
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
    const choice = event.target.closest("[data-decision-choice]");
    if (choice) upsertDecision(choice.dataset.decisionSymbol, choice.dataset.decisionChoice);
    const editDecision = event.target.closest("[data-edit-decision]");
    if (editDecision) { state.activeDecisionId = editDecision.dataset.editDecision; renderDecisionView(); }
    const createDecision = event.target.closest("[data-create-decision]");
    if (createDecision) { upsertDecision(createDecision.dataset.createDecision, "observe"); switchView("decisions"); window.scrollTo({top: 0, behavior: "smooth"}); }
    const deleteDecision = event.target.closest("[data-delete-decision]");
    if (deleteDecision) { state.decisions = state.decisions.filter((entry) => entry.id !== deleteDecision.dataset.deleteDecision); state.activeDecisionId = null; saveDecisions(); renderDecisionView(); }
  });
  $("#dateSelect").addEventListener("change", (event) => setDate(event.target.value));
  $("#symbolFilter").addEventListener("change", (event) => { state.symbol = event.target.value; renderInstrumentTable(); });
  $("#searchInput").addEventListener("input", (event) => { state.query = event.target.value; renderInstrumentTable(); });
  $("#sectorFilter").addEventListener("change", (event) => { state.sector = event.target.value; renderInstrumentTable(); });
  $("#detailSymbolFilter").addEventListener("change", (event) => { if (event.target.value) { state.activeSymbol = event.target.value; renderDetailWorkspace(); } });
  $("#detailSearchInput").addEventListener("input", (event) => { state.detailQuery = event.target.value; renderDetailWorkspace(); });
  $("#detailSectorFilter").addEventListener("change", (event) => { state.detailSector = event.target.value; renderDetailWorkspace(); });
  $("#historyControls").addEventListener("change", (event) => { if (event.target.id === "historySymbolSelect") { state.historySymbol = event.target.value; renderHistory(); } });
  $("#decisionEditor").addEventListener("submit", (event) => {
    if (event.target.id !== "decisionForm") return;
    event.preventDefault();
    const record = state.decisions.find((entry) => entry.id === state.activeDecisionId);
    if (!record) return;
    const values = Object.fromEntries(new FormData(event.target));
    const message = $("#decisionFormMessage");
    if (values.tradeStatus === "no_trade" && !values.noTradeReason.trim()) { message.textContent = "未交易必须记录原因。"; return; }
    if (["open", "closed"].includes(values.tradeStatus) && !values.tradeLogRef.trim()) { message.textContent = "产生交易后必须关联交易日志。"; return; }
    if (values.tradeStatus === "closed" && !values.exitResult.trim()) { message.textContent = "已退出交易必须填写退出结果。"; return; }
    Object.assign(record, values, {updatedAt: new Date().toISOString()});
    saveDecisions();
    renderDecisionView();
  });
}

Promise.all([
  fetch("data/dashboard.json", {cache: "no-store"}).then((response) => { if (!response.ok) throw new Error(`HTTP ${response.status}`); return response.json(); }),
  fetch("run-manifest.json", {cache: "no-store"}).then((response) => response.ok ? response.json() : null),
])
  .then(([data, manifest]) => {
    state.data = data;
    state.manifest = manifest;
    state.decisions = loadDecisions();
    state.date = data.latestDate;
    state.activeSymbol = data.snapshots[data.latestDate].tripleResonance[0]?.symbol || data.snapshots[data.latestDate].instruments[0]?.symbol;
    bindEvents();
    renderAll();
    $("#app").dataset.ready = "true";
  })
  .catch((error) => {
    $("#loadingState").textContent = `数据装载失败：${error.message}。请通过本地 HTTP 服务打开。`;
  });
