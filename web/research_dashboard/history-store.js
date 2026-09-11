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
    let userItems = [];
    /* 静态导入文件（Excel/md/user_journal）只存在于本地开发环境；公开站点上
       个人数据被排除出部署仓，404 是正常态，静默处理。个人数据的主存储是
       私有数据仓（futures-journal-data/journal.json），见下方云端拉取。 */
    try {
      const excel = await fetchJson("data/imported/trading_log_excel.json");
      excelItems = (excel.observations || []).map(normalizeExcelObservation);
    } catch (error) { if (!/HTTP 404/.test(String(error.message || ""))) errors.push(`Excel 导入：${error.message}`); }
    try {
      const md = await fetchJson("data/imported/monthly_review_md.json");
      months = md.months || [];
      mdTrades = (md.trades || []).map(normalizeMdTrade);
      mdNarratives = (md.narratives || []).map(normalizeMdNarrative);
    } catch (error) { if (!/HTTP 404/.test(String(error.message || ""))) errors.push(`月度复盘导入：${error.message}`); }
    try {
      const user = await fetchJson("data/imported/user_journal.json");
      userItems = (user.observations || []).map((item) => ({...item, source: "工作台日志"}));
    } catch (error) {
      if (!/HTTP 404/.test(String(error.message || ""))) errors.push(`用户复盘导入：${error.message}`);
    }

    /* 云端个人数据：有 Token 时拉取私有仓 journal.json（历史导入 + 各设备新写复盘），
       与本地合并；保存复盘时会自动推回私有仓（见 putObservation） */
    let remoteItems = [];
    let cloudMonths = [];
    if (typeof JournalSync !== "undefined" && JournalSync.hasToken()) {
      try {
        const remote = await JournalSync.pullJournal();
        if (remote && remote.data) {
          remoteItems = [...(remote.data.observations || []), ...(remote.data.trades || []), ...(remote.data.narratives || [])];
          if (!months.length) months = remote.data.months || [];
          cloudMonths = remote.data.months || [];
        }
      } catch (error) { errors.push(`云端复盘拉取：${error.message}`); }
    }

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
    /* 合并:同 id 按 updated 时间戳新者胜(与云端 mergeJournal 一致),杜绝旧数据覆盖新修订 */
    const merged = {};
    const putMerged = (item) => {
      if (!item || !item.id) return;
      const prev = merged[item.id];
      if (!prev || Number(item.updated || 0) >= Number(prev.updated || 0)) merged[item.id] = item;
    };
    [...excelItems, ...mdNarratives, ...mdTrades, ...userItems, ...remoteItems, ...legacy, ...migrateLocalStorageDecisions()].forEach(putMerged);

    cache = {
      observations: Object.values(merged).filter((item) => item.kind !== "trade"),
      trades: Object.values(merged).filter((item) => item.kind === "trade"),
      narratives: mdNarratives,
      months: months.length ? months : cloudMonths,
    };
    cache.errors = errors;
    return cache;
  }

  /* 全量个人数据负载（供云端首次同步 / 手动同步使用） */
  function localPayload() {
    return {observations: cache.observations, trades: cache.trades, narratives: cache.narratives, months: cache.months};
  }

  /* 推送本地个人数据到私有仓（pull -> merge -> push），返回合并后全量 */
  function pushToCloud() {
    if (typeof JournalSync === "undefined" || !JournalSync.hasToken()) {
      return Promise.resolve({local: true, data: localPayload()});
    }
    return JournalSync.syncJournal(localPayload()).then((result) => {
      unsynced = 0;
      lastPushAt = new Date().toLocaleTimeString("zh-CN", {hour: "2-digit", minute: "2-digit"});
      /* 远端可能有本地没有的记录（其他设备写的），并入缓存 */
      const remote = result.data || {};
      const incoming = [...(remote.observations || []), ...(remote.trades || [])];
      incoming.forEach((item) => {
        if (item && item.id && !cache.observations.some((o) => o.id === item.id) && !cache.trades.some((t) => t.id === item.id)) {
          if (item.kind === "trade") cache.trades.push(item); else cache.observations.push(item);
          if (db) putMany(STORES.observations, [item]).catch(() => {});
        }
      });
      if ((remote.months || []).length && !cache.months.length) cache.months = remote.months;
      return result;
    });
  }

  /* 云同步状态追踪:失败计数(供状态栏显示" N 条待同步")+ 最近成功推送时间 */
  let unsynced = 0;
  let lastPushAt = "";

  /* 工作台保存复盘时调用：写入 IndexedDB 并同步内存缓存，时间线即时可见；
     有 Token 时后台自动同步到私有数据仓；失败计入待同步数(状态栏可见),不再静默 */
  function putObservation(observation) {
    if (!observation || !observation.id) {
      console.warn("[HistoryStore] putObservation 忽略了缺 id 的记录（静默丢弃会掩盖数据丢失）", observation);
      return;
    }
    const stamped = {...observation, updated: Date.now()};
    cache.observations = cache.observations.filter((item) => item.id !== stamped.id);
    cache.observations.push(stamped);
    if (db) putMany(STORES.observations, [stamped]).catch((error) => {
      console.warn("[HistoryStore] IndexedDB 写入失败（重启后该记录可能丢失，建议导出备份）", error);
    });
    if (typeof JournalSync !== "undefined" && JournalSync.hasToken()) {
      unsynced += 1;
      JournalSync.syncJournal({observations: [stamped], trades: [], narratives: [], months: []})
        .then(() => { unsynced = Math.max(0, unsynced - 1); lastPushAt = new Date().toLocaleTimeString("zh-CN", {hour: "2-digit", minute: "2-digit"}); if (typeof renderCloudSyncStatus === "function") renderCloudSyncStatus(); })
        .catch(() => { if (typeof renderCloudSyncStatus === "function") renderCloudSyncStatus(); });
    }
  }

  /* 状态栏查询:待同步条数 + 最近成功推送时间 */
  function syncState() {
    return {unsynced: unsynced, lastPushAt: lastPushAt};
  }

  /* 导出：只包含本地工作台新写的 observation（source=工作台日志），
     不含静态 Excel/md 导入项，避免推送时重复。Agent 收到后追加到
     data/imported/user_journal.json，下次刷新页面自动展示 */
  function exportUserJournal() {
    const items = cache.observations.filter((item) => item.source === "工作台日志");
    return {
      exportedAt: new Date().toISOString(),
      generator: "trading-system research_dashboard",
      version: 1,
      count: items.length,
      observations: items,
    };
  }

  return {init, cache: () => cache, putObservation, exportUserJournal, pushToCloud, syncState, hasCloudToken: () => typeof JournalSync !== "undefined" && JournalSync.hasToken()};
})();
