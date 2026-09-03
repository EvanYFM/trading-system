/* ============================================================
   journal-sync.js · 期货工作站个人数据同步层
   原则照搬 digital-garden 的 garden-data.js：
   本地优先（IndexedDB 永远可用），GitHub 私有仓库做跨设备同步。
   未设置 Token 时，一切退化为纯本地——不报错、不阻塞。

   数据仓库：EvanYFM/futures-journal-data（私有，仅本人 Token 可读写）
   该仓库存放全部个人复盘数据（journal.json），公开站点上不存在，
   匿名访问 404；Token 存 localStorage，不进 git、不进公开代码。
   ============================================================ */
var JournalSync = (function () {
  var OWNER = "EvanYFM";
  var REPO = "futures-journal-data";
  var TKEY = "fs_token";
  var JOURNAL_PATH = "journal.json";

  function token() { try { return localStorage.getItem(TKEY) || ""; } catch (e) { return ""; } }
  function setToken(t) { try { t ? localStorage.setItem(TKEY, t) : localStorage.removeItem(TKEY); } catch (e) {} }
  function hasToken() { return !!token(); }

  /* UTF-8 安全的 base64（garden-data.js 同款） */
  function b64e(s) { return btoa(unescape(encodeURIComponent(s))); }
  function b64d(s) { return decodeURIComponent(escape(atob(s.replace(/\n/g, "")))); }

  function api(method, path, body) {
    return fetch("https://api.github.com/repos/" + OWNER + "/" + REPO + "/contents/" + path, {
      method: method,
      headers: {
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + token(),
        "Content-Type": "application/json",
        "X-GitHub-Api-Version": "2022-11-28"
      },
      body: body ? JSON.stringify(body) : undefined
    }).then(function (r) {
      if (r.status === 404) return null;                 /* 文件尚不存在 */
      if (r.status === 401) throw new Error("Token 无效或已过期");
      if (!r.ok) throw new Error("GitHub " + r.status);
      return r.json();
    });
  }

  /* 拉取：返回 {data, sha} 或 null（404 / 无 Token） */
  function pull(path) {
    if (!hasToken()) return Promise.resolve(null);
    return api("GET", path).then(function (j) {
      return j ? {data: JSON.parse(b64d(j.content)), sha: j.sha} : null;
    });
  }

  /* 推送：无 sha=创建，有 sha=更新 */
  function push(path, obj, sha) {
    var body = {message: "sync " + path + " · " + new Date().toISOString().slice(0, 16),
      content: b64e(JSON.stringify(obj, null, 1))};
    if (sha) body.sha = sha;
    return api("PUT", path, body);
  }

  /* 同步：拉取 → merge(本地, 远端) → 推送；409 冲突自动重试一次 */
  function sync(path, localObj, merge) {
    if (!hasToken()) return Promise.resolve({data: localObj, local: true});
    function attempt(retry) {
      return pull(path).then(function (r) {
        var sha = r ? r.sha : null;
        var merged = merge(localObj, r ? r.data : null);
        return push(path, merged, sha).then(function () {
          return {data: merged, ok: true};
        });
      }).catch(function (e) {
        if (retry && /409/.test(e.message)) return attempt(false);
        throw e;
      });
    }
    return attempt(true);
  }

  /* 复盘合并：按 id，updated 较新者胜；远端独有条目并入本地视图 */
  function mergeJournal(local, remote) {
    var out = {};
    var r = remote || {observations: [], trades: [], narratives: [], months: []};
    (r.observations || []).forEach(function (o) { out[o.id] = o; });
    (r.trades || []).forEach(function (o) { out[o.id] = o; });
    (r.narratives || []).forEach(function (o) { out[o.id] = o; });
    (local.observations || []).forEach(function (o) {
      if (!out[o.id] || Number(o.updated || 0) >= Number((out[o.id] || {}).updated || 0)) out[o.id] = o;
    });
    (local.trades || []).forEach(function (o) {
      if (!out[o.id] || Number(o.updated || 0) >= Number((out[o.id] || {}).updated || 0)) out[o.id] = o;
    });
    (local.narratives || []).forEach(function (o) {
      if (!out[o.id] || Number(o.updated || 0) >= Number((out[o.id] || {}).updated || 0)) out[o.id] = o;
    });
    var list = Object.keys(out).map(function (k) { return out[k]; });
    return {
      observations: list.filter(function (o) { return o.kind === "observation" || o.kind === "narrative" || !o.kind; }),
      trades: list.filter(function (o) { return o.kind === "trade"; }),
      narratives: list.filter(function (o) { return o.kind === "narrative"; }),
      months: (local.months && local.months.length ? local.months : (r.months || [])),
      updatedAt: new Date().toISOString()
    };
  }

  /* 完整同步一次个人复盘数据：
     localPayload = {observations, trades, narratives, months}
     返回 {data, ok|local}，data 为合并后的远端最新全量 */
  function syncJournal(localPayload) {
    return sync(JOURNAL_PATH, localPayload, mergeJournal);
  }

  /* 只拉取远端（打开页面时合并展示用，不推送） */
  function pullJournal() {
    return pull(JOURNAL_PATH);
  }

  return {token: token, setToken: setToken, hasToken: hasToken,
    pullJournal: pullJournal, syncJournal: syncJournal, mergeJournal: mergeJournal};
})();
