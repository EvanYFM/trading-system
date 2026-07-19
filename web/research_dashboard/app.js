const state = {
  data: null,
  date: null,
  view: "overview",
  query: "",
  sector: "all",
  direction: "all",
  detailQuery: "",
  detailSector: "all",
  activeSymbol: null,
  historySymbol: null,
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
const DETAIL_SYMBOLS = ["AG", "JM", "FU", "LH", "LC", "JD"];
const DETAIL_SEARCH_ALIASES = { FU: "燃油", AG: "白银", JM: "焦煤", LH: "生猪", LC: "碳酸锂", JD: "鸡蛋" };

function maxAbs(items, getter) {
  return Math.max(1, ...items.map((item) => Math.abs(numeric(getter(item)))));
}

function renderDateControls() {
  const options = state.data.dates.map((date) => `<option value="${date}" ${date === state.date ? "selected" : ""}>${formatDate(date)}</option>`).join("");
  $("#dateSelect").innerHTML = options;
  $("#dateList").innerHTML = state.data.dates.map((date) => `<button class="date-button ${date === state.date ? "is-active" : ""}" data-date="${date}">${formatDate(date)}</button>`).join("");
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
  const items = currentSnapshot().tripleResonance.slice(0, 8);
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
      <div class="focus-sub">三方手数 ${formatHands(item.handsSignal)} · ${escapeHtml(item.marginalStructure || "边际待判")}</div>
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

function renderTrendResonance() {
  const rows = (currentSnapshot().trendResonance || []).slice(0, 12);
  if (!rows.length) {
    $("#trendResonance").innerHTML = `<div class="detail-empty">该快照没有可用的非“平”趋势温度数据。</div>`;
    return;
  }
  const scale = maxAbs(rows, (item) => item.amount);
  $("#trendResonance").innerHTML = `<div class="trend-table-head"><span>品种</span><span>趋势事实</span><span>三方资金</span><span>关系</span><span>来源</span></div>${rows.map((item) => `<button class="trend-row" data-open-symbol="${escapeHtml(item.symbol)}">
    <span class="trend-name"><strong>${escapeHtml(item.variety)}</strong><small>${escapeHtml(item.symbol)} · ${escapeHtml(item.sector)}</small></span>
    <span>${trendChip({temperature:item.temperature, strength:item.strength, fresh:item.fresh})}<small class="trend-stage">${escapeHtml(item.stage || (item.rightSide ? "右侧" : "左侧"))}</small></span>
    <span class="trend-money"><span class="sector-meter"><span class="sector-meter-fill ${dirClass(item.amount)}" style="width:${Math.max(4, Math.abs(item.amount) / scale * 100)}%"></span></span><strong class="${signClass(item.amount)}">${formatAmount(item.amount)}</strong></span>
    <span><span class="tag ${item.relation === "资金顺势" ? dirClass(item.amount) : ""}">${escapeHtml(item.relation)}</span></span>
    <span class="source-date ${item.fresh ? "" : "is-stale"}">${escapeHtml(item.sourceDate || "未披露")}${item.fresh ? "" : " · 非当日"}</span>
  </button>`).join("")}`;
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
  const instruments = currentSnapshot().instruments;
  const preferred = instruments.filter((item) => item.watchlist);
  const additions = currentSnapshot().tripleResonance.filter((item) => !preferred.some((entry) => entry.symbol === item.symbol));
  return [...preferred, ...additions].slice(0, 14);
}

function renderCorePanorama() {
  const rows = coreItems();
  if (!rows.length) {
    $("#corePanorama").innerHTML = `<div class="detail-empty">该快照没有可用重点品种。</div>`;
    return;
  }
  $("#corePanorama").innerHTML = `<div class="panorama-head"><span>品种 / 行情</span><span>三方净变动</span><span>内资 / 外资 / 家人反向</span><span>趋势与信号</span></div>${rows.map((item) => {
    const quote = item.quote;
    return `<button class="panorama-row" data-open-symbol="${escapeHtml(item.symbol)}">
      <span class="panorama-name"><strong>${escapeHtml(item.variety)} ${escapeHtml(item.symbol)}</strong><small>${escapeHtml(item.sector)} · ${escapeHtml(quote?.contract || item.margin.contract || "主力待披露")}</small>${quote ? `<em>${numeric(quote.close).toLocaleString("zh-CN", {maximumFractionDigits:4})} <b class="${signClass(quote.changePct)}">${formatSigned(quote.changePct, 2)}%</b></em>` : `<em>行情暂无</em>`}</span>
      <span class="panorama-signal"><strong class="${signClass(item.amountSignal)}">${formatAmount(item.amountSignal)}</strong><small class="${signClass(item.handsSignal)}">${formatHands(item.handsSignal)} 手 · ${escapeHtml(item.marginalStructure || "边际待判")}</small></span>
      <span>${groupBars(item)}</span>
      <span class="panorama-tags">${trendChip(item.trend)}<span class="tag ${dirClass(item.amountSignal)}">${escapeHtml(item.resonance.label || item.direction)}</span></span>
    </button>`;
  }).join("")}`;
}

function brokerSide(items, side) {
  if (!items?.length) return `<p class="empty-side">今天没有净${side === "bullish" ? "多" : "空"}贡献</p>`;
  const scale = maxAbs(items, (item) => item.displayAmount);
  return items.map((item) => `<button class="broker-highlight-row" data-open-symbol="${escapeHtml(item.symbol)}">
    <span><strong>${escapeHtml(item.broker)}</strong><small>${escapeHtml(item.variety)} ${escapeHtml(item.symbol)}</small></span>
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
  $("#stockIndexList").innerHTML = rows.length ? rows.map((item) => `<div class="index-row"><div class="index-name"><strong>${escapeHtml(item.variety)}</strong><small>${escapeHtml(item.symbol)} · 独立专栏${item.trend ? ` · 趋势${escapeHtml(item.trend.temperature || "-")}${item.trend.fresh ? "" : "（旧）"}` : ""}</small></div><div class="index-value ${signClass(item.amountSignal)}">${formatAmount(item.amountSignal)}</div></div>`).join("") : `<div class="detail-empty">该快照没有独立股指数据。</div>`;
}

function renderEquitySentiment() {
  const item = currentSnapshot().equitySentiment || {};
  if (item.status !== "ok") {
    $("#equitySentiment").innerHTML = `<div class="detail-empty">该快照没有可用A股社区情绪数据。</div>`;
    return;
  }
  const tone = item.score > 0 ? "bullish" : item.score < 0 ? "bearish" : "";
  const evidence = (item.evidence || []).slice(0, 3).map((entry) => `<li>${escapeHtml(entry.excerpt)}</li>`).join("");
  $("#equitySentiment").innerHTML = `<div class="sentiment-head"><div><span>A股社区情绪</span><strong class="${signClass(item.score)}">${escapeHtml(item.label)}</strong></div><div class="sentiment-score ${tone}">${formatSigned(item.score, 0)}</div></div>
    <div class="sentiment-meta">${escapeHtml(item.dataDate)} · ${item.sampleCount} 条样本 · Nick ${item.nickCount} 条 · 置信度${escapeHtml(item.confidence)}</div>
    <p>${escapeHtml(item.communitySummary)}</p>
    <div class="sentiment-nick"><strong>Nick 当日观点</strong><span>${escapeHtml(item.nickSummary || "暂无")}</span></div>
    ${evidence ? `<details><summary>查看方向证据摘录</summary><ul>${evidence}</ul></details>` : ""}
    <small>${escapeHtml(item.methodology)}</small>`;
}

function renderOverviewStatus() {
  const snapshot = currentSnapshot();
  const summary = snapshot.summary;
  const latestDisclosure = snapshot.disclosureDates.at(-1) || "未披露";
  const sentiment = snapshot.equitySentiment || {};
  $("#overviewStatus").innerHTML = [
    ["席位披露", latestDisclosure, `${summary.instrumentCount} 个商品品种`],
    ["收盘行情", sourceFileDate(summary.quoteSourceFile), `${summary.quoteFreshCount}/${summary.instrumentCount} 与报告日同日 · 东方财富`],
    ["趋势快照", sourceFileDate(summary.trendSourceFile), `${summary.trendFreshCount}/${summary.instrumentCount} 与报告日同日 · 趋势动物`],
    ["保证金", `${(summary.marginCoverage * 100).toFixed(0)}% 覆盖`, summary.marginSourceUpdate || "更新时间未披露"],
    ["天气风险", `${snapshot.weather.length} 条`, snapshot.weather[0]?.date || "无数据"],
    ["A股情绪", sentiment.status === "ok" ? `${sentiment.sampleCount} 条样本` : "不可用", sentiment.dataDate || "无数据"],
  ].map(([label, value, note]) => `<article><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong><small>${escapeHtml(note)}</small></article>`).join("");
}

function filteredInstruments() {
  const query = state.query.trim().toLowerCase();
  return currentSnapshot().instruments.filter((item) => {
    const queryMatch = !query || item.variety.toLowerCase().includes(query) || item.symbol.toLowerCase().includes(query);
    const sectorMatch = state.sector === "all" || item.sector === state.sector;
    const directionMatch = state.direction === "all" || (state.direction === "bullish" ? item.amountSignal > 0 : item.amountSignal < 0);
    return queryMatch && sectorMatch && directionMatch;
  });
}

function renderSectorFilter() {
  const sectors = [...new Set(currentSnapshot().instruments.map((item) => item.sector))].sort();
  $("#sectorFilter").innerHTML = `<option value="all">全部板块</option>${sectors.map((sector) => `<option value="${escapeHtml(sector)}" ${state.sector === sector ? "selected" : ""}>${escapeHtml(sector)}</option>`).join("")}`;
}

function renderDetailFilter() {
  const covered = currentSnapshot().instruments.filter((item) => DETAIL_SYMBOLS.includes(item.symbol));
  const sectors = [...new Set(covered.map((item) => item.sector))].sort();
  $("#detailSearchInput").value = state.detailQuery;
  $("#detailSectorFilter").innerHTML = `<option value="all">全部板块</option>${sectors.map((sector) => `<option value="${escapeHtml(sector)}" ${state.detailSector === sector ? "selected" : ""}>${escapeHtml(sector)}</option>`).join("")}`;
  const query = state.detailQuery.trim().toLowerCase();
  const matches = covered.filter((item) => {
    const aliases = DETAIL_SEARCH_ALIASES[item.symbol] || "";
    const queryMatch = !query || item.variety.toLowerCase().includes(query) || item.symbol.toLowerCase().includes(query) || aliases.toLowerCase().includes(query);
    return queryMatch && (state.detailSector === "all" || item.sector === state.detailSector);
  });
  $("#detailFilterResults").innerHTML = matches.length ? matches.map((item) => `<button class="detail-filter-option ${item.symbol === state.activeSymbol ? "is-active" : ""}" data-open-symbol="${escapeHtml(item.symbol)}"><strong>${escapeHtml(item.variety)}</strong><small>${escapeHtml(item.symbol)} · ${escapeHtml(item.sector)}</small></button>`).join("") : `<span class="detail-filter-empty">当前筛选条件下没有已接入品种。</span>`;
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
  return items.length ? items.map((entry) => `<div class="seat-rank-row"><span class="seat-rank-name">${escapeHtml(entry.broker)}<small>${escapeHtml(entry.group)} · 今日方向 ${formatHands(entry.flowScore)}</small></span><strong class="${tone}">${formatHands(entry.netPosition)}</strong></div>`).join("") : `<div class="seat-rank-row"><span class="detail-empty">${emptyText}</span></div>`;
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

function chanSequence(points) {
  if (!Array.isArray(points) || points.length < 2) return "结构不足";
  return points.map((point) => technicalValue(point.price, 0)).join(" → ");
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
  const technicalSign = technical.bias === "偏多" ? 1 : technical.bias === "偏空" ? -1 : 0;
  const moneySign = Math.sign(numeric(item.amountSignal));
  if (!technicalSign) return "15/60分钟未形成同向突破，按中枢震荡处理";
  const direction = technicalSign > 0 ? "偏多" : "偏空";
  const moneyRead = !moneySign ? "三方资金中性" : moneySign === technicalSign ? `三方资金${direction}同向` : "三方资金反向";
  const trendSign = trend?.fresh && ["温", "热", "沸"].includes(trend.temperature) ? 1 : trend?.fresh && ["凉", "寒", "冻"].includes(trend.temperature) ? -1 : 0;
  const trendRead = !trendSign ? "趋势温度未确认" : trendSign === technicalSign ? "趋势温度同向" : "趋势温度反向";
  return `技术${direction}；${moneyRead}；${trendRead}`;
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
  const technical = item.technical?.status === "OK" ? item.technical : null;
  const groupRows = [["内资机构", item.groups.domestic], ["外资机构", item.groups.foreign], ["家人原始", item.groups.family]];
  const stockScale = maxAbs(groupRows, ([, group]) => group.netPosition);
  const longTotal = item.brokerRanking.netLong.reduce((sum, entry) => sum + numeric(entry.netPosition), 0);
  const shortTotal = Math.abs(item.brokerRanking.netShort.reduce((sum, entry) => sum + numeric(entry.netPosition), 0));
  const seatBias = longTotal > shortTotal ? "多方样本占优" : shortTotal > longTotal ? "空方样本占优" : "席位样本均衡";
  const relationship = detailRelationship(item);
  const technicalRead = technicalRelationship(technical, item, trend);
  const relevantWeather = currentSnapshot().weather.filter((entry) => entry.symbol === item.symbol).slice(0, 4);
  const trendState = trend ? `${trend.temperature || "-"} · ${trend.active ? (trend.stage || (trend.rightSide ? "右侧" : "左侧")) : "未进入趋势"}` : "暂无趋势数据";
  const researchState = `${item.amountSignal >= 0 ? "资金偏多" : "资金偏空"} · ${trend?.active ? relationship : "等待趋势确认"}`;
  const disclosure = currentSnapshot().disclosureDates.at(-1) || "未披露";
  const recentEvents = [...series].reverse().slice(0, 5);
  const weatherRead = relevantWeather.length ? `${relevantWeather[0].types}，${relevantWeather[0].reason}` : "该品种尚未接入库存、基差、利润或天气等基本面事实。";
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
    <nav class="detail-subnav" aria-label="品种详情导航"><button class="is-active" data-detail-anchor="detail-overview">总览</button><button data-detail-anchor="detail-positioning">资金与席位</button><button data-detail-anchor="detail-technical">技术面</button><button data-detail-anchor="detail-trend">趋势</button><button data-detail-anchor="detail-fundamental">基本面</button><button data-detail-anchor="detail-events">历史事件</button></nav>
    <section id="detail-overview" class="detail-dashboard-grid">
      <article class="detail-surface chart-surface"><div class="detail-section-head"><div><small>PRICE & FLOW</small><h3>价格与三方资金</h3></div><div class="detail-legend"><i></i>收盘价 <b></b>资金净变动</div></div><div class="combo-chart-wrap">${priceFlowChart(series, item.variety)}</div><div class="detail-chart-foot"><span>历史快照 <b>${series.length} 日</b></span><span>今日手数 <b class="${signClass(item.handsSignal)}">${formatHands(item.handsSignal)}</b></span><span>边际结构 <b>${escapeHtml(item.marginalStructure)}</b></span></div></article>
      <aside class="detail-surface executive-surface"><div class="detail-section-head"><div><small>EXECUTIVE READ</small><h3>今日研究读数</h3></div></div><dl><div><dt>接口事实</dt><dd>${trend ? `趋势温度“${escapeHtml(trend.temperature)}”，强度 ${formatSigned(trend.strength, 1)}，${trend.rightSide ? "处于右侧" : "未处于右侧"}。` : "趋势数据暂无。"} 三方资金 ${formatAmount(item.amountSignal)}。</dd></div><div><dt>策略判断</dt><dd>${escapeHtml(relationship)}；席位信号为“${escapeHtml(item.resonance.label || item.direction)}”。这是规则化解读，不是接口原文。</dd></div><div><dt>反向证据</dt><dd>${escapeHtml(weatherRead)}</dd></div></dl><button class="detail-action" data-view="history">查看完整历史路径</button></aside>
    </section>
    <section id="detail-positioning" class="detail-surface detail-wide-section"><div class="detail-section-head"><div><small>POSITIONING</small><h3>资金与席位结构</h3></div><p>存量净持仓与今日边际分列；家人按原始方向展示</p></div><div class="position-matrix"><div class="position-matrix-head"><span>资金群体</span><span>存量净持仓</span><span>今日净金额</span><span>边际动作</span></div>${groupRows.map(([label, group]) => `<div class="position-matrix-row"><b>${label}</b>${positionVisual(group.netPosition, stockScale)}<strong class="${signClass(group.amount)}">${formatAmount(group.amount)}</strong><span>${escapeHtml(flowAction(group))}</span></div>`).join("")}</div><div class="seat-rank-grid detail-ranks"><div class="seat-rank-list"><div class="seat-rank-title bull-text">净多席位 ${item.brokerRanking.netLong.length}/5</div>${rankRows(item.brokerRanking.netLong, "bull-text", "暂无净多席位")}</div><div class="seat-rank-list"><div class="seat-rank-title bear-text">净空席位 ${item.brokerRanking.netShort.length}/5</div>${rankRows(item.brokerRanking.netShort, "bear-text", "暂无净空席位")}</div></div></section>
    <section id="detail-technical" class="detail-surface detail-wide-section technical-section">
      <div class="detail-section-head"><div><small>TECHNICAL EXECUTION</small><h3>技术面三层验证</h3></div><span class="detail-stamp ${technical?.bias === "偏多" ? "bullish" : technical?.bias === "偏空" ? "bearish" : "neutral"}">${technical ? `结构判断 · ${escapeHtml(technical.bias)}` : "技术快照未接入"}</span></div>
      ${technical ? `<div class="technical-summary">
        <div><small>综合结论</small><strong class="${technicalStateClass(technical.bias)}">${escapeHtml(technical.bias)} · ${escapeHtml(technical.signalStrength || "-")}</strong></div>
        <div><small>量仓驱动</small><strong>${escapeHtml(technical.marketActivity?.label || "数据不足")} · ${escapeHtml(technical.marketActivity?.impulse || "无法确认")}</strong></div>
        <div><small>样本</small><strong>${technical.barCount} 日 · ${escapeHtml(technical.contract)}</strong></div>
      </div>
      <div class="technical-layer-grid">
        <article><span>01 · 日线均线</span><h4 class="${technicalStateClass(technical.dailyState)}">${escapeHtml(technical.dailyState)}</h4><dl><div><dt>收盘</dt><dd>${technicalValue(technical.close, 0)}</dd></div><div><dt>MA5</dt><dd>${technicalValue(technical.ma5, 0)}</dd></div><div><dt>MA20</dt><dd>${technicalValue(technical.ma20, 0)}</dd></div><div><dt>MA60</dt><dd>${technicalValue(technical.ma60, 0)}</dd></div></dl></article>
        <article><span>02 · 15分钟缠论</span><h4 class="${technicalStateClass(technical.chan15?.state)}">${escapeHtml(technical.chan15?.state || "无法确认")}</h4><dl><div><dt>最近高点</dt><dd>${chanSequence(technical.chan15?.recentTops)}</dd></div><div><dt>最近低点</dt><dd>${chanSequence(technical.chan15?.recentBottoms)}</dd></div><div><dt>最近中枢</dt><dd>${chanZone(technical.chan15)}</dd></div><div><dt>有效笔</dt><dd>${technicalValue(technical.chan15?.strokeCount, 0)}</dd></div></dl></article>
        <article><span>03 · 60分钟缠论</span><h4 class="${technicalStateClass(technical.chan60?.state)}">${escapeHtml(technical.chan60?.state || "无法确认")}</h4><dl><div><dt>最近高点</dt><dd>${chanSequence(technical.chan60?.recentTops)}</dd></div><div><dt>最近低点</dt><dd>${chanSequence(technical.chan60?.recentBottoms)}</dd></div><div><dt>最近中枢</dt><dd>${chanZone(technical.chan60)}</dd></div><div><dt>有效笔</dt><dd>${technicalValue(technical.chan60?.strokeCount, 0)}</dd></div></dl></article>
      </div>
      <div class="technical-readout">
        <div><b>成交与持仓事实</b><p>成交量 ${technicalValue(technical.marketActivity?.volume, 0)}，较前日 ${technicalValue((technical.marketActivity?.volumeRatio - 1) * 100, 1, "%")}；收盘持仓 ${technicalValue(technical.marketActivity?.openInterest, 0)}，日变动 ${technicalValue(technical.marketActivity?.openInterestChange, 0)}。${escapeHtml(technical.marketActivity?.label || "")}${escapeHtml(technical.marketActivity?.impulse ? `，${technical.marketActivity.impulse}` : "")}。</p></div>
        <div><b>支撑与压力</b><p>支撑：${levelText(technical.keyLevels?.supports, "暂无下方有效位置")}。压力：${levelText(technical.keyLevels?.resistances, "暂无上方有效位置")}。位置由 MA5/20/60 与最近有效中枢共同筛选。</p></div>
        <div><b>规则判断</b><p>${escapeHtml(technicalRead)}。增仓同向用于增强趋势置信度，减仓同向视为力度较弱；技术面不替代资金面与基本面。</p></div>
      </div>
      <div class="technical-limit"><b>数据限制</b><p>${escapeHtml(technical.limitations)}</p></div>
      <p class="detail-panel-note">来源：${escapeHtml(technical.source)}与${escapeHtml(technical.chan15?.source || "分钟数据未取得")}；数据日 ${escapeHtml(technical.sourceDate)}，分钟数据截至 ${escapeHtml(technical.chan15?.endTime || "无法确认")}。本模块按市场成交数据生成，不构成投资建议。</p>` : `<div class="data-gap"><strong>当前技术面覆盖沪银、焦煤、燃油、生猪、碳酸锂和鸡蛋</strong><p>该品种尚未生成技术快照，不使用其他品种或旧日数据填充。</p></div>`}
    </section>
    <section class="detail-split">
      <article id="detail-trend" class="detail-surface"><div class="detail-section-head"><div><small>TREND REGIME</small><h3>趋势与周期</h3></div><span class="detail-stamp">API事实</span></div><div class="temperature-scale">${tempOrder.map((name) => `<span class="${trend?.temperature === name ? "is-active" : ""}">${name}</span>`).join("")}</div><div class="trend-fact-row"><span>趋势强度</span><strong>${trend ? formatSigned(trend.strength, 1) : "暂无"}</strong></div><div class="trend-fact-row"><span>右侧状态</span><strong>${trend ? (trend.rightSide ? "是" : "否") : "暂无"}</strong></div><div class="trend-fact-row"><span>进入天数</span><strong>${trend?.daysSinceEntry == null ? "暂无" : `${trend.daysSinceEntry} 天`}</strong></div><p class="detail-panel-note">趋势动物直接事实与本页资金判断分列。温度为“平”或数据非当日时，不把它写成右侧趋势确认。</p></article>
      <article id="detail-fundamental" class="detail-surface"><div class="detail-section-head"><div><small>FUNDAMENTALS</small><h3>基本面证据板</h3></div><span class="detail-stamp neutral">外部事实</span></div>${relevantWeather.length ? `<div class="fundamental-grid">${relevantWeather.map((entry) => `<div><small>${escapeHtml(entry.window)} · ${escapeHtml(entry.date)}</small><strong>${escapeHtml(entry.types)}</strong><span>${escapeHtml(entry.origins)}</span></div>`).join("")}</div><p class="detail-panel-note">天气预警只作为外部事实，不直接推导涨跌。</p>` : `<div class="data-gap"><strong>当前没有该品种的基本面结构化数据</strong><p>库存、基差、仓单、利润、产量和消费尚未接入。保留此入口，避免用席位资金代替基本面结论。</p></div>`}</article>
    </section>
    <section id="detail-events" class="detail-surface detail-wide-section"><div class="detail-section-head"><div><small>EVENT PATH</small><h3>历史事件与数据缺口</h3></div><p>快照事实可追溯；研报观点库尚未接入</p></div><div class="event-layout"><div class="research-gap"><strong>研报分歧</strong><span>待接入</span><p>正式接入前不展示概念稿中的看多/震荡/看空数量。</p></div><div class="event-timeline">${recentEvents.map((entry) => `<div><time>${formatDate(entry.date)}</time><b class="${signClass(entry.amount)}">${formatAmount(entry.amount)}</b><p>${escapeHtml(entry.structure)} · ${formatHands(entry.hands)} 手${entry.close == null ? "" : ` · 收盘 ${formatPrice(entry.close)}`}</p></div>`).join("")}</div></div></section>`;
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
    <div class="detail-section"><h4>样本席位净持仓前五</h4><div class="seat-rank-grid"><div class="seat-rank-list"><div class="seat-rank-title bull-text">净多席位 ${item.brokerRanking.netLong.length}/5</div>${rankRows(item.brokerRanking.netLong, "bull-text", "暂无净多席位")}</div><div class="seat-rank-list"><div class="seat-rank-title bear-text">净空席位 ${item.brokerRanking.netShort.length}/5</div>${rankRows(item.brokerRanking.netShort, "bear-text", "暂无净空席位")}</div></div></div>
    <div class="detail-section"><h4>资金信号历史路径</h4><div class="spark-wrap">${sparkline(series.map((entry) => entry.amount), dirClass(item.amountSignal))}</div></div>
    <div class="detail-section"><h4>行情与趋势事实</h4><div class="status-line"><span>收盘行情</span><strong>${item.quote ? `${escapeHtml(item.quote.sourceDate)} · 东方财富` : "暂无"}${item.quote && !item.quote.fresh ? "（非当日）" : ""}</strong></div><div class="status-line"><span>趋势温度</span><strong>${item.trend ? `${escapeHtml(item.trend.temperature)} · ${escapeHtml(item.trend.stage)}` : "暂无"}</strong></div><div class="status-line"><span>趋势日期</span><strong>${item.trend ? escapeHtml(item.trend.sourceDate) : "暂无"}${item.trend && !item.trend.fresh ? "（非当日）" : ""}</strong></div></div>`;
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
    <section class="status-block"><h3>行情、趋势与天气</h3><div class="status-list"><div class="status-line"><span>当日收盘行情</span><strong>${summary.quoteFreshCount || 0} / ${summary.instrumentCount}</strong></div><div class="status-line"><span>当日趋势品种</span><strong>${summary.trendFreshCount} / ${summary.instrumentCount}</strong></div><div class="status-line"><span>天气预警</span><strong>${snapshot.weather.length} 条</strong></div><div class="status-line"><span>股指独立观察</span><strong>${snapshot.stockIndices.length} 个</strong></div></div></section>`;
}

function renderAll() {
  renderDateControls();
  renderSummary();
  renderFocus();
  renderTide();
  renderSectors();
  renderTrendResonance();
  renderCorePanorama();
  renderBrokerHighlights();
  renderWeather();
  renderStockIndices();
  renderEquitySentiment();
  renderOverviewStatus();
  renderDetailWorkspace();
  renderInstrumentTable();
  renderHistory();
  renderStatus();
}

function switchView(view) {
  state.view = view;
  $$(".nav-item").forEach((button) => button.classList.toggle("is-active", button.dataset.view === view));
  $$(".view").forEach((panel) => panel.classList.toggle("is-active", panel.id === `view-${view}`));
  if (view === "detail") renderDetailWorkspace();
  if (view === "history") renderHistory();
}

function setDate(date) {
  state.date = date;
  state.sector = "all";
  state.detailSector = "all";
  state.detailQuery = "";
  renderAll();
}

function bindEvents() {
  document.addEventListener("click", (event) => {
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
  });
  $("#dateSelect").addEventListener("change", (event) => setDate(event.target.value));
  $("#searchInput").addEventListener("input", (event) => { state.query = event.target.value; renderInstrumentTable(); });
  $("#sectorFilter").addEventListener("change", (event) => { state.sector = event.target.value; renderInstrumentTable(); });
  $("#detailSearchInput").addEventListener("input", (event) => { state.detailQuery = event.target.value; renderDetailFilter(); });
  $("#detailSectorFilter").addEventListener("change", (event) => { state.detailSector = event.target.value; renderDetailFilter(); });
  $("#historyControls").addEventListener("change", (event) => { if (event.target.id === "historySymbolSelect") { state.historySymbol = event.target.value; renderHistory(); } });
}

fetch("data/dashboard.json", {cache: "no-store"})
  .then((response) => {
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  })
  .then((data) => {
    state.data = data;
    state.date = data.latestDate;
    state.activeSymbol = data.snapshots[data.latestDate].tripleResonance[0]?.symbol || data.snapshots[data.latestDate].instruments[0]?.symbol;
    bindEvents();
    renderAll();
    $("#app").dataset.ready = "true";
  })
  .catch((error) => {
    $("#loadingState").textContent = `数据装载失败：${error.message}。请通过本地 HTTP 服务打开。`;
  });
