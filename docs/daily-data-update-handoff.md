# 期货工作站每日数据更新 Handoff

面向接手本项目的 Agent。目标是生成并校验交易日快照，再把公开安全的静态产物发布到 GitHub Pages；缺失不伪造，截图未提供时不沿用旧日值。

## 交付边界

- 数据与快照校验通过后，直接同步私有开发仓 `EvanYFM/trading-system` 和公开部署仓 `EvanYFM/futures-workstation`，再在线验证 GitHub Pages；不启动本地 HTTP 工作站，不再发布 Sites。
- 不修改或覆盖用户在“交易与决策”板块的内容。个人复盘、交易记录、浏览器存储导出和 `data/imported/user_journal.json` 只能进入私有数据仓，不得进入公开部署仓。
- 所有日期按北京时间 `Asia/Shanghai`，`REPORT_DATE` 使用 `YYYYMMDD`。

## 1. 开始前

先检查 `git status --short`。

- 工作树干净：执行 `git fetch origin main`、`git pull --rebase origin main`。
- 已有本地改动：先比较 `origin/main` 与本地差异，不得覆盖、丢弃或为 rebase 临时混入用户修改。
- 原始 `data/`、日报目录、`tmp/`、登录态、Cookie、密钥或缓存不提交。私有开发仓只明确提交代码、文档以及工作站需要跟踪的目标快照；公开部署仓只接收下文列出的静态文件。

## 2. 当日输入

必须有报告日和以下数据源：

1. 奇货可查：机构席位、主力合约净多/净空席位。
2. AKShare：主力合约收盘、涨跌、5/10/20/30 日与月涨幅、成交量、持仓和日增减仓；同花顺截图仅补资金流等 AKShare 缺失字段。
3. OpenVLab Legend 截图（用户提供时）：隐波、实波、偏度、隐波百分位、偏度百分位。
4. 自动公开源：保证金、曲合/新浪行情、基差、仓单、六个重点品种技术面。
5. 趋势动物与知识星球仅在安全登录态或密钥可用时更新；不可用就标记缺失，不继承旧日。

截图底表沿用最近文件的表头：

- `data/ths_main_quotes_YYYYMMDD.csv`
- `data/openvlab_option_factors_YYYYMMDD.csv`

只转录截图中可确认的行和字段，`source_date` 必须等于报告日。OCR 结果必须抽样回看原图，尤其复核负号、合约、资金流和百分位。

## 3. 固定执行顺序

在项目根目录运行：

```powershell
$py=(Get-Command python -ErrorAction Stop).Source
$env:PYTHONUTF8="1"
$env:REPORT_DATE="YYYYMMDD"

& $py scripts\generate_institutional_seat_report.py
& $py scripts\generate_margin_weighted_seat_report.py
& $py scripts\fetch_akshare_main_quotes.py
& $py scripts\fetch_eastmoney_main_quotes.py
& $py scripts\fetch_sina_quhe_main_quotes.py
& $py scripts\fetch_research_dashboard_market_context.py
& $py scripts\fetch_eastmoney_technical_snapshot.py
& $py scripts\fetch_seat_flow.py
& $py scripts\build_research_dashboard.py
```

顺序不能颠倒：保证金层依赖机构底表；行情与技术面需要报告日主力合约；最后构建快照。

`fetch_eastmoney_main_quotes.py` 会直接请求奇货可查品种持仓页。补历史日时必须在请求中保留 `date=YYYY-MM-DD`，不能因概览已滚动到下一交易日而跳过席位。

## 4. 席位硬复核

构建成功不代表可以跳过复核。检查：

- 文件：`data/qhkch_main_position_rows_YYYYMMDD.csv`
- 日期：全部为报告日。
- 合约：每个品种必须匹配报告日精确主力合约。
- 覆盖：工作站 59 个商品全部存在。
- 数量：每个商品 `netLong` 恰好 5 条、`netShort` 恰好 5 条；总计应为 295 + 295。

任一品种缺一侧、少于五条、日期或合约不一致，停止交付并列出品种。优先重试奇货可查；只有同日同合约证据不完整时才查交易可查，且不得混用两个日期或两个合约。

## 5. 快照验收

目标文件：

- `output/research_dashboard/data/snapshots/YYYYMMDD.json`
- `output/research_dashboard/data/dashboard.json`
- `output/research_dashboard/run-manifest.json`

最低验收：

- `date == REPORT_DATE`
- `instruments == 59`
- `cta == 63`，其中含 `IH/IF/IC/IM`
- 保证金覆盖 59/59，主力行情 59/59
- 六个重点技术面逐项报告成功或明确缺失
- 所有 59 个商品净多/净空各 5 条
- 截图数据只来自报告日；未覆盖品种按可用因子重算，不继承前日

运行测试：

```powershell
& $py -m unittest discover -s tests -p "test_*.py"
node --check web\research_dashboard\app.js
```

若测试失败，先判断是本次数据链路失败，还是远端“交易与决策”改版后测试断言未同步；不得为让测试变绿而回滚用户页面。

## 6. 同步 GitHub 与 Pages

1. 在私有开发仓再次执行 `git fetch origin main`、`git pull --rebase origin main`，先审查远端“交易与决策”改动。
2. 把本地数据链路改动重放到最新远端，不覆盖用户页面；重建目标日期并重跑席位硬复核、快照校验和测试。
3. 私有开发仓只暂存本次代码、测试、文档，以及 `dashboard.json`、`data/dashboard-meta.json`（最新日期列表，首页启动靠它选日期，漏了页面会停在旧日期）、`run-manifest.json` 和目标 `snapshots/YYYYMMDD.json`；提交并推送 `origin/main`。
4. 获取公开仓 `EvanYFM/futures-workstation` 的最新 `main`。只同步 `index.html`、`app.js`、`styles-v2.css`、`history-store.js`、`journal-sync.js`、`favicon.svg`、`404.html`、`robots.txt`、`run-manifest.json`、`data/dashboard-meta.json`、`data/dashboard.json` 和 `data/snapshots/`；同步本 Handoff 到公开仓 `docs/`。
5. 发布前检查公开仓不含 `data/imported/`、`user_journal.json`、交易记录、Token、Cookie、密钥、账户状态和本机路径。不得整目录复制 `output/research_dashboard/data/`。
6. 提交并推送公开仓 `main`，等待 GitHub Pages 状态为 `built`，再读取线上 `data/dashboard.json` 与目标快照，确认最新日期、59 个商品、63 个 CTA、净多 295 和净空 295。
7. 报告私有仓与公开仓两个 commit hash、Pages 地址和线上验收结果。Sites 不再属于每日发布链路。

## 交接状态

数据已更新至：2026-09-10

后续每日只修改这一日期，不追加逐日过程记录；异常、缺失或发布失败才单独说明。

## 2026-09-11 前端统一与总览页改造（WorkBuddy 执行记录）

- **v1 退役**：`web/research_dashboard/styles.css`（v1 样式）删除；v2 garden SPA（`index.html` + `styles-v2.css` + `app.js` + `history-store.js` + `journal-sync.js` + `favicon.svg`/`404.html`/`robots.txt`/`assets/hero.svg`）成为唯一前端版本，私有仓 `web/research_dashboard/` 与公开部署仓根目录文件完全一致（以部署仓为准拷回）。
- **build 资产拷贝更新**：`build_research_dashboard.py` 输出资产改为 v2 清单；`data/imported/` 不再拷入产物（个人数据不进公开链路，与第 6 节一致）。
- **总览页**：删除「关键商品事件」「板块方向速览」；新增「四 净持仓分布变化」（全商品当日资金净流入/流出前五，剔除股指国债）与「五 席位大资金动向」（外资=高盛/瑞银/摩根大通，内资=国泰君安/东证/永安/中财/东吴；各席位前五流多/流空组内并集，可超五个；品种净变化 = Σ(long_chg) − Σ(short_chg)）。
- **新数据管线**：每日在第 3 节 `build` 之前运行 `scripts/fetch_seat_flow.py`（抓 8 席位持仓变化 → `data/seat_flow_rows_YYYYMMDD.json`），`build_research_dashboard.py` 的 `build_seat_flow()` 写入 `snapshot.seatFlow`；文件缺失时 `seatFlow=null`，前端显示缺失提示，不回填旧日值。
- **快照历史**：20260910 快照已回填 `seatFlow`（外资 12 条、内资 17 条）并发布；更早日期无 seatFlow 属正常，前端按缺失处理。
- **前端真身归属**：自此私有仓 `web/research_dashboard/` 是唯一源码，公开仓是发布产物；每日改前端一律改私有仓 `web/` → build → 按第 4 节清单同步公开仓，禁止直接在公开仓改页面（那次 v2 重构造成的分叉已在本日合并消除）。
- 对应提交：私有仓 `b64e132`（净流/席位板块管线）、本次前端统一提交；公开仓 `0c6e9d1`、本次同步提交。

## 2026-09-11 数据链路接管验证（WorkBuddy）

以 `REPORT_DATE=20260910` 从零重跑全链路（8 抓取脚本 + build），与线上现网快照逐项对比：

**通过项**：快照结构 100% 一致（59 instruments / 63 cta 含 4 股指 / 顶层字段）；收盘价 55/59 一致；**手数信号 handsSignal 59/59 完全一致**；三方席位组结构一致；seatFlow 8/8 席位正常；保证金覆盖 59/59；AKShare/新浪曲合行情 59/59；技术面 6/6。

**差异三类（均不构成数据链路问题）**：
1. `marketFlow.capitalFlow` 新跑为 None（53/59）：资金流来自**同花顺截图转录**（`data/ths_main_quotes_YYYYMMDD.csv`），重跑历史日期没有当日截图，按"缺失不伪造"规则留空。线上现网是 9/10 当天转录的，更完整——**不要用历史回跑覆盖现网**。
2. `amountSignal`/`groups.amount` 约 ±1% 差异：保证金金额 = 手数 × 当日保证金价格，历史回跑会用最新价格回算，属时效性偏差；**报告日当天跑则无此偏差**。
3. 收盘价 4/59 差异（如 AO）：回跑抓到的 K 线含夜盘/复权口径差，当天跑以当日收盘为准。

**测试**：48 个单测中 46 通过；2 个失败（`test_dashboard_review_changes_are_wired`、`test_decision_workflow_and_manifest_are_wired`）断言的是 v1 决策工作流字段（`seeRight: "pending"` 等），v2 决策编辑器已重构，**断言待同步 v2**——属页面断言滞后，非数据链路问题，不得为此回滚页面。

**接管结论**：链路可由 WorkBuddy 每日接管，前提是**报告日当天执行**；同花顺资金流截图仍需用户当天提供转录（唯一无法自动化的输入）。

## 2026-09-11 17:10 第一次正式接管发布（9/11 快照已上线）

- 验收全绿：59 instruments / 63 cta / 保证金 59/59 / 行情 fresh 59/59 / 资金流 53 品种 / seatFlow 外资 15 内资 19；资金流前五与用户截图逐项吻合（沪镍 3.24亿、液化气 3.07亿、氧化铝 2.40亿）。
- 截图转录流程：同花顺 4 张 → （原始字符串 + 单位换算）→ AKShare 对账修正 5 处（AL/I/NR/LC 收盘、BU 持仓 10 倍错位）→ 重生成 CSV。
- ⚠️ **事故记录与铁律**：本地 build 只产出当日快照（历史快照源文件不落地），直接把本地  推公开仓会把 30 天历史清成 2 天（本次已从公开仓 git HEAD~1 恢复）。**今后发布 dashboard.json 前必须核对快照日期数 ≥ 现网 dates 数；本地只有新日期时，用  恢复全量后注入新快照再提交。**
- 东财技术面接口当日 0/6 异常，按缺失处理；OpenVLab 截图分辨率不足未转录，期权因子标缺失。
- 提交：私有仓 、公开仓 （发布）+ （历史恢复修复）。
