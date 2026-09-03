# 期货工作站每日数据更新 Handoff

面向接手本项目的 Agent。目标是生成一个可核验的本地交易日快照，并在验收后把公开安全的静态产物发布到 GitHub Pages；缺失不伪造，截图未提供时不沿用旧日值。

## 交付边界

- 默认先更新并验收本地 HTTP 工作站，再同步私有开发仓 `EvanYFM/trading-system` 和公开部署仓 `EvanYFM/futures-workstation`；不再发布 Sites。
- 用户明确要求“先本地验收”或“仅本地”时，不提交、不推送 GitHub；用户确认后再继续双仓同步。
- 不修改或覆盖用户在“交易与决策”板块的内容。个人复盘、交易记录、浏览器存储导出和 `data/imported/user_journal.json` 只能进入私有数据仓，不得进入公开部署仓。
- 所有日期按北京时间 `Asia/Shanghai`，`REPORT_DATE` 使用 `YYYYMMDD`。

## 1. 开始前

先检查 `git status --short`。

- 工作树干净：执行 `git fetch origin main`、`git pull --rebase origin main`。
- 已有待用户验收的本地改动：先比较 `origin/main` 与本地差异，不得覆盖、丢弃或为 rebase 临时混入用户修改；本轮继续仅本地更新，并在交付时明确未同步远端。
- 原始 `data/`、日报目录、`tmp/`、登录态、Cookie、密钥或缓存不提交。私有开发仓只明确提交代码、文档以及工作站需要跟踪的目标快照；公开部署仓只接收下文列出的静态文件。

## 2. 当日输入

必须有报告日和以下数据源：

1. 奇货可查：机构席位、主力合约行情、主力合约净多/净空席位。
2. 同花顺期货通截图（用户提供时）：收盘、涨跌、10/20/30 日涨幅、持仓、日增减仓、资金流。
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
& $py scripts\fetch_eastmoney_main_quotes.py
& $py scripts\fetch_sina_quhe_main_quotes.py
& $py scripts\fetch_research_dashboard_market_context.py
& $py scripts\fetch_eastmoney_technical_snapshot.py
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

## 5. 快照与页面验收

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

启动本地服务：

```powershell
& $py -m http.server 8788 --bind 127.0.0.1 --directory output\research_dashboard
```

若当前环境的线程式 `http.server` 出现 `Empty reply from server`，改用标准库单进程服务：

```powershell
python -c "import functools,http.server; H=http.server.SimpleHTTPRequestHandler; H.log_message=lambda *args:None; http.server.HTTPServer(('127.0.0.1',8792),functools.partial(H,directory=r'output\research_dashboard')).serve_forever()"
```

最后用 HTTP 读取 `/data/snapshots/YYYYMMDD.json`，确认状态 200、日期、59 个商品和 63 个 CTA 标的；再让用户打开页面验收。

## 6. 本地验收后同步 GitHub 与 Pages

用户没有要求“仅本地”时，本地验收通过后执行；若用户要求先看页面，则等待用户确认：

1. 在私有开发仓再次执行 `git fetch origin main`、`git pull --rebase origin main`，先审查远端“交易与决策”改动。
2. 把本地数据链路改动重放到最新远端，不覆盖用户页面；重建目标日期并重跑席位硬复核、测试和 HTTP 验收。
3. 私有开发仓只暂存本次代码、测试、文档，以及 `dashboard.json`、`run-manifest.json` 和目标 `snapshots/YYYYMMDD.json`；提交并推送 `origin/main`。
4. 获取公开仓 `EvanYFM/futures-workstation` 的最新 `main`。只同步 `index.html`、`app.js`、`styles.css`、`history-store.js`、`journal-sync.js`、`run-manifest.json`、`data/dashboard.json` 和 `data/snapshots/`；同步本 Handoff 到公开仓 `docs/`。
5. 发布前检查公开仓不含 `data/imported/`、`user_journal.json`、交易记录、Token、Cookie、密钥、账户状态和本机路径。不得整目录复制 `output/research_dashboard/data/`。
6. 提交并推送公开仓 `main`，等待 GitHub Pages 状态为 `built`，再读取线上 `data/dashboard.json` 与目标快照，确认最新日期、59 个商品、63 个 CTA、净多 295 和净空 295。
7. 报告私有仓与公开仓两个 commit hash、Pages 地址和线上验收结果。Sites 不再属于每日发布链路。

## 交付摘要模板

- 报告日：
- 本地地址：
- 商品 / CTA：59 / 63
- 席位证据：净多 295、净空 295、缺失品种 0
- 行情 / 保证金 / 技术：
- 同花顺 / OpenVLab 截图覆盖：
- 测试与 HTTP：
- 私有开发仓：commit / push 状态
- 公开部署仓与 Pages：commit / 最新日期 / HTTP 验收
- Sites：不发布
