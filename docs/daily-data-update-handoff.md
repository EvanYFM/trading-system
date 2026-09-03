# 期货工作站每日数据更新 Handoff

面向接手本项目的 Agent。目标是生成一个可核验的本地交易日快照；缺失不伪造，截图未提供时不沿用旧日值。

## 交付边界

- 默认只更新本地 HTTP 工作站，不发布 Sites。
- 用户明确要求“先本地验收”时，不提交、不推送 GitHub。用户确认后才合并这几日数据与代码改动。
- 不修改或覆盖用户在“交易与决策”板块的内容；人工交易记录保存在浏览器本地存储，构建脚本不得清空。
- 所有日期按北京时间 `Asia/Shanghai`，`REPORT_DATE` 使用 `YYYYMMDD`。

## 1. 开始前

先检查 `git status --short`。

- 工作树干净：执行 `git fetch origin main`、`git pull --rebase origin main`。
- 已有待用户验收的本地改动：先比较 `origin/main` 与本地差异，不得覆盖、丢弃或为 rebase 临时混入用户修改；本轮继续仅本地更新，并在交付时明确未同步远端。
- 永远不提交 `data/`、`output/`、`tmp/`、登录态、Cookie、密钥或缓存。

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
$py="C:\Users\29266\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
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

## 6. 用户确认后再同步 GitHub

只有用户明确说“可以推送”后执行：

1. 再次获取 `origin/main`，先审查远端“交易与决策”改动。
2. 把本地数据链路改动重放到最新远端，不覆盖用户页面。
3. 重建目标日期并重跑席位硬复核、测试和 HTTP 验收。
4. 只暂存项目代码、测试和文档；`data/`、`output/`、`tmp/` 不进 Git。
5. 提交并推送 `origin/main`，报告 commit hash；Sites 仍需用户另行明确确认。

## 交付摘要模板

- 报告日：
- 本地地址：
- 商品 / CTA：59 / 63
- 席位证据：净多 295、净空 295、缺失品种 0
- 行情 / 保证金 / 技术：
- 同花顺 / OpenVLab 截图覆盖：
- 测试与 HTTP：
- GitHub / Sites：未提交、未推送、未发布（或写明用户已授权的结果）
