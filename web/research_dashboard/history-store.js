/* 历史复盘存储层：三层模型 + 静态导入 + localStorage 迁移
 *
 * 数据模型：
 *   observation — 一次判断/复盘（Excel 每品种行、md 叙述行、工作台决策记录）
 *   trade       — 一笔完整交易（md 表格行，含归因）
 *   tradeEvent  — 一次具体操作（开仓/加仓/减仓/平仓，如 1400开仓 -> 1450加仓）
 *
 * 数据来源与口径（2026-09-01 与用户确认）：
 *   1. data/imported/trading_log_excel.json — 仓位列空 = 仅观察他人策略，未执行；
 *      此类记录的 strategyPnlText 是策略方收益，绝不计入 myPnl。
 *   2. data/imported/monthly_review_md.json — 月度复盘表格与叙述。
 *   3. localStorage futuresResearchDecisions.v1 — 老决策记录，迁移为 observation，
 *      原始数据保留不删（符合 AGENTS.md「自动构建不得覆盖人工记录」）。
 */
const HistoryStore = (() => {
  const DB_NAME = "futuresTradingJournal";
  const DB_VERSION = 1;
  const STORES = {observations: "observations", trades: "trades", events: "tradeEvents", meta: "meta"};

  let db = null;
  let cache = {observations: [], trades: [], narratives: [], months: []};

  /* IndexedDB 在隐私模式、磁盘受限或被其他标签页阻塞时可能既不 resolve 也不 reject。
     不设超时会让 Promise.all 永久挂起、整个工作站停在装载中，因此这里强制超时降级，
     退化为只使用 fetch 到的内存数据，页面照常渲染。 */
  const DB_OPEN_TIMEOUT_MS = 3000;

  function withTimeout(promise, ms, message) {
    let timer = null;
    return Promise.race([
      promise.then((value) => { if (timer) clearTimeout(timer); return value; },
                   (error) => { if (timer) clearTimeout(timer); throw error; }),
      new Promise((_, reject) => { timer = setTimeout(() => reject(new Error(message)), ms); }),
    ]);
  }

  function openDb() {
    return new Promise((resolve, reject) => {
      if (!("indexedDB" in window)) return reject(new Error("IndexedDB 不可用"));
      const request = indexedDB.open(DB_NAME, DB_VERSION);
      const timer = setTimeout(() => reject(new Error("IndexedDB 打开超时")), DB_OPEN_TIMEOUT_MS);
      const settle = (fn, value) => { clearTimeout(timer); fn(value); };
      request.onupgradeneeded = () => {
        const database = request.result;
        if (!database.objectStoreNames.contains(STORES.observations)) database.createObjectStore(STORES.observations, {keyPath: "id"});
        if (!database.objectStoreNames.contains(STORES.trades)) database.createObjectStore(STORES.trades, {keyPath: "id"});
        if (!database.objectStoreNames.contains(STORES.events)) database.createObjectStore(STORES.events, {keyPath: "id"});
        if (!database.objectStoreNames.contains(STORES.meta)) database.createObjectStore(STORES.meta, {keyPath: "key"});
      };
      request.onsuccess = () => settle(resolve, request.result);
      request.onerror = () => settle(reject, request.error || new Error("IndexedDB 打开失败"));
      request.onblocked = () => settle(reject, new Error("IndexedDB 被其他标签页阻塞"));
    });
  }

  function putMany(storeName, items) {
    return new Promise((resolve, reject) => {
      if (!db || !items.length) return resolve();
      const tx = db.transaction(storeName, "readwrite");
      const store = tx.objectStore(storeName);
      items.forEach((item) => store.put(item));
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  }

  function getAll(storeName) {
    return new Promise((resolve, reject) => {
      if (!db) return resolve([]);
      const request = db.transaction(storeName, "readonly").objectStore(storeName).getAll();
      request.onsuccess = () => resolve(request.result || []);
      request.onerror = () => reject(request.error);
    });
  }

  function getMeta(key) {
    return new Promise((resolve) => {
      if (!db) return resolve(null);
      const request = db.transaction(STORES.meta, "readonly").objectStore(STORES.meta).get(key);
      request.onsuccess = () => resolve(request.result ? request.result.value : null);
      request.onerror = () => resolve(null);
    });
  }

  function setMeta(key, value) {
    return putMany(STORES.meta, [{key, value}]);
  }

  /* localStorage 老决策记录 -> observation。只做映射，原数据保留不删。 */
  function migrateLocalStorageDecisions() {
    let legacy = [];
    try { legacy = JSON.parse(localStorage.getItem("futuresResearchDecisions.v1") || "[]"); }
    catch { legacy = []; }
    if (!legacy.length) return [];
    return legacy.map((record) => ({
      id: `ws-${record.id}`,
      source: "工作台决策",
      kind: "observation",
      date: record.reportDate ? `${record.reportDate.slice(0, 4)}-${record.reportDate.slice(4, 6)}-${record.reportDate.slice(6, 8)}` : "",
      variety: record.variety || "",
      symbol: record.symbol || "",
      contract: null,
      strike: null,
      instrumentType: null,
      optionType: null,
      direction: null,
      strategySource: "自己",
      executed: record.tradeStatus !== "no_trade",
      myPnl: null,
      pnlRatio: null,
      strategyPnlText: "",
      choice: record.choice || "",
      tradeStatus: record.tradeStatus || "no_trade",
      review: [record.mainContradiction, record.exitResult, record.reviewNote].filter(Boolean).join("\n"),
      noTradeReason: record.noTradeReason || "",
      stopLossTakeProfit: "",
      ratings: {},
      raw: "",
    }));
  }

  function normalizeExcelObservation(item) {
    return {
      id: item.id, source: "交易日志Excel", kind: "observation",
      date: item.date || "", dateNote: item.dateNote || "",
      variety: item.variety, symbol: item.symbol,
      contract: item.contract || null, strike: item.strike || null,
      instrumentType: item.instrumentType, optionType: item.optionType,
      moneyness: item.moneyness || null, direction: item.direction,
      lots: item.lots, strategySource: item.strategySource,
      executed: item.executed,
      position: item.position, myPnl: item.myPnl, pnlRatio: item.pnlRatio,
      strategyPnlText: item.strategyPnlText || "",
      batchFlag: item.isBatchSplit || false,
      batchPosition: item.batchPosition || "", batchPnl: item.batchPnl || "",
      ratings: item.ratings || {},
      technical: item.technical || "", fundamental: item.fundamental || "",
      capital: item.capital || "", policy: item.policy || "", sentiment: item.sentiment || "",
      cognitiveBias: item.cognitiveBias || "",
      overall: item.overall || "",
      strategy: item.strategy || "", stopLossTakeProfit: item.stopLossTakeProfit || "",
      review: item.review || "",
      raw: "",
    };
  }

  function normalizeMdTrade(trade) {
    return {
      id: trade.id, source: "月度复盘md", kind: "trade",
      date: trade.month ? `${trade.month}-01` : "",
      month: trade.month || "",
      variety: trade.variety || "", symbol: trade.symbol || "",
      contract: trade.contract || null, strike: trade.strike || null,
      instrumentType: trade.instrumentType, optionType: trade.optionType,
      moneyness: trade.moneyness || null, direction: trade.direction,
      strategySource: "自己",
      executed: true,
      myPnl: trade.pnl, pnlText: trade.pnlText || "",
      attribution: trade.attribution || {},
      events: (trade.events || []).map((event, index) => ({
        id: `${trade.id}-e${index + 1}`, tradeId: trade.id,
        type: event.type, action: event.action,
        price: event.price, note: event.note,
      })),
      raw: trade.raw || "",
    };
  }

  function normalizeMdNarrative(item) {
    return {
      id: item.id, source: "月度复盘md", kind: "narrative",
      date: item.date || (item.month ? `${item.month}-01` : ""),
      month: item.month || "",
      variety: item.variety || "", symbol: item.symbol || "",
      myPnl: item.pnl, pnlText: item.pnlText || "",
      strategySource: "自己", executed: item.pnl != null,
      text: item.text || "",
      raw: "",
    };
  }

  async function fetchJson(path) {
    const response = await fetch(path, {cache: "no-store"});
    if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
    return response.json();
  }

  /* 静态导入源首次落库；已在 meta 标记的源跳过，避免重复导入 */
  async function importStaticSource(name, path, normalizer, listKey) {
    const mark = await getMeta(`import:${name}`);
    if (mark) return mark;
    const payload = await fetchJson(path);
    const items = (payload[listKey] || []).map(normalizer);
    await putMany(STORES.observations, items.filter((item) => item.kind === "observation" || item.kind === "narrative"));
    await putMany(STORES.trades, items.filter((item) => item.kind === "trade"));
    await putMany(STORES.events, items.flatMap((item) => item.events || []));
    await setMeta(`import:${name}`, {count: items.length, at: new Date().toISOString()});
    return {count: items.length, at: new Date().toISOString()};
  }

  async function init() {
    let months = [];
    const errors = [];
    try { db = await openDb(); }
    catch (error) { errors.push(`IndexedDB：${error.message}`); }

    let excelItems = [];
    let mdTrades = [];
    let mdNarratives = [];
    try {
      const excel = await fetchJson("data/imported/trading_log_excel.json");
      excelItems = (excel.observations || []).map(normalizeExcelObservation);
    } catch (error) { errors.push(`Excel 导入：${error.message}`); }
    try {
      const md = await fetchJson("data/imported/monthly_review_md.json");
      months = md.months || [];
      mdTrades = (md.trades || []).map(normalizeMdTrade);
      mdNarratives = (md.narratives || []).map(normalizeMdNarrative);
    } catch (error) { errors.push(`月度复盘导入：${error.message}`); }

    if (db) {
      try {
        await withTimeout(Promise.all([
          putMany(STORES.observations, [...excelItems, ...mdNarratives]),
          putMany(STORES.trades, mdTrades),
          putMany(STORES.events, mdTrades.flatMap((trade) => trade.events || [])),
          putMany(STORES.observations, migrateLocalStorageDecisions()),
          setMeta("lastImport", {at: new Date().toISOString(), excel: excelItems.length, trades: mdTrades.length, narratives: mdNarratives.length}),
        ]), 5000, "IndexedDB 写入超时");
      } catch (error) { errors.push(`IndexedDB 写入：${error.message}`); }
    }

    const legacy = db
      ? await withTimeout(getAll(STORES.observations), 4000, "IndexedDB 读取超时").catch(() => [])
      : [];
    const merged = {};
    [...excelItems, ...mdNarratives, ...mdTrades, ...legacy, ...migrateLocalStorageDecisions()].forEach((item) => {
      merged[item.id] = item;
    });

    cache = {
      observations: Object.values(merged).filter((item) => item.kind !== "trade"),
      trades: Object.values(merged).filter((item) => item.kind === "trade"),
      narratives: mdNarratives,
      months,
    };
    cache.errors = errors;
    return cache;
  }

  return {init, cache: () => cache};
})();
