# Codex Handoff

## 2026-08-07 Trading Capability Consolidation

- 从“交易能力”旧对话中筛出尚未进入系统的执行内容，并入现有文档，不新增附件或扩大十问清单。
- `docs/trading-system.md` 新增“看对、做对、做好”三层能力；事件观点要求写出传导链和关键验证指标，仓位模块区分配置仓与交易仓，叙事模块加入注意力反身性。
- `docs/trading-decision-checklist.md` 与 `docs/trading-log-framework.md` 同步传导链、关键验证指标、仓位性质和三层错误归因；`README.md` 与 `AGENTS.md` 已同步入口和复盘口径。
- 周期嵌套、资金仓位、事实/共识/价格、拥挤与右侧确认此前已经覆盖，本次没有重复追加。

## 2026-07-23 Daily Position Audit

- `docs/trading-log-framework.md` 新增开盘前与收盘后的持仓每日审计，固定原始逻辑、兑现期限、证伪条件和最大风险，避免在亏损压力下改写交易理由。
- 期权持仓归因统一拆成方向、入场时机、隐波、时间价值和流动性；空仓测试不通过、只为回本持有、原逻辑失效、期限已过、计划外补仓和扩大风险列为一票否决。
- `docs/trading-decision-checklist.md`、`README.md` 与 `AGENTS.md` 已同步路由到该审计卡。
- 生成 `2880x1800` 黑底交易纪律壁纸，位于 `output/trading_discipline_wallpaper_20260723/`，该目录属于本地交付产物，不进入 Git。

## Git Collaboration Baseline

- 主项目使用 GitHub 私有仓库，默认分支为 `main`。
- 原始 `data/`、日报目录、`tmp/`、依赖、缓存、本地应用状态和敏感环境文件不进入主项目仓库；仅经验证的工作站静态产物与目标日期快照按每日 Handoff 明确暂存。
- `sites/research_dashboard/` 保留为 Sites 平台自己的独立部署仓库；主项目 GitHub 跟踪 `web/research_dashboard/`、构建脚本、报告逻辑和项目文档，不嵌套提交 Sites 的 `.git` 历史。
- 每次较大修改完成后：运行验证、检查 diff、只暂存本次改动、提交并推送 `origin/main`，向用户报告 commit hash。

## 2026-07-18 Broker Group Expansion

- 两份正式日报的统一样本扩展为内资 13 家、外资 3 家、家人 9 家。
- 新增内资：中信期货、光大期货、一德期货、瑞达期货、银河期货。
- 新增家人：广发期货、民生期货、平安期货、中泰期货。
- 三方方向与计算口径不变：内资、外资为正向，家人为反向，最终净结果为内资 + 外资 - 家人。
- 新增名称将以奇货可查抓取页的实际返回名称核验；若单席位当日空表，报告状态区应明确披露，不得按零持仓处理。

## 2026-07-13 Oil Chemical Sector Update

- Starting with the next trading-day report, natural rubber `RU`（天然橡胶）, PP `PP`, synthetic rubber `BR`（合成橡胶）, plastics `L`（塑料）, ethylene glycol `EG`（乙二醇）, and polyester staple fiber `PF`（短纤）move from other commodities into oil chemical.
- The already-generated 2026-07-13 reports are not regenerated; they retain the classification used at generation time.

## Current State

本项目当前维护一条每日交付主线：

- 每个中国期货交易日拉取席位、天气、社区情绪、趋势、主力行情和技术面数据，固化为 `output/research_dashboard/data/snapshots/YYYYMMDD.json`，校验后同步至线上数据层。
- `scripts/generate_institutional_seat_report.py` 与 `scripts/generate_margin_weighted_seat_report.py` 默认只承担数据生产和对账；日常工作流不生成日报 HTML，旧版 HTML 仅在手动诊断时显式设置 `WRITE_REPORT_HTML=1`。
- `scripts/generate_futures_report.py` 仅保留为基础函数来源和手动排查脚本。
- 趋势优先使用报告日有效的 API 快照；若用户提供当日截图，只转录截图可确认的温度、强度和阶段，不把截图行情当作收盘行情。

数据已更新至：2026-09-04。线上发布目标为公开仓 `EvanYFM/futures-workstation` 的 GitHub Pages；个人交易记录不进入公开仓，本地 HTTP 工作站和 Sites 均不属于每日发布链路。

## Stable Decisions

- 数据来源使用奇货可查席位持仓页与品种持仓结构页。
- 席位名称以网页实际可返回持仓表的名称为准；用户简称只作别名。
- 原“乾坤期货”已按现名“高盛期货”处理。
- 减空、加多视为偏多；减多、加空视为偏空。
- 内资和外资按正向指标解读；家人席位按反向指标解读。
- 看多/上涨/正向用红色；看空/下跌/负向用绿色。
- 不再输出单席位 40% 阈值观察。
- EC 集运欧线因网页无持仓数据，不纳入重点持仓观察。
- 强共振观察回看最近 5 个可用披露日，识别持续多/空、反转或方向切换。
- 不再单独生成外资专题日报；外资席位分析并入机构合并专题日报。
- 2026 年中国法定节假日或调休放假日不更新工作站；自动化在这些休市日跳过抓取、快照构建和通知。

## Broker Groups

- 内资：国泰君安、东证期货、永安期货、海通期货、浙商期货、中财期货、南华期货、申银万国、一德期货、瑞达期货、银河期货
- 外资：高盛期货、摩根大通、瑞银期货
- 家人：东方财富、徽商期货、方正中期、华安期货、中信建投、广发期货、民生期货、平安期货、中泰期货、光大期货、招商期货、中信期货（前台标记“亏损机构（特殊）”）

两份数据脚本统一使用内资 11 家、外资 3 家、家人 12 家样本；内资、外资为正向资金，家人为反向指标，三方净结果为内资 + 外资 - 家人。

## Focus Varieties

当前固定重点品种：

- 燃油、苯乙烯、碳酸锂、豆粕、鸡蛋、焦煤、铁矿石、沪金、沪银、欧线集运、生猪、棕榈油、天然橡胶主力合约

结构页抓取名称：

- 沪金 -> 沪金
- 沪银 -> 沪银
- 欧线集运 -> 集运欧线（奇货可查无可用席位持仓数据，不纳入席位合计或结构页结论）

重点品种持仓结构只展示净多前 5 与净空前 5 席位构成。品种结构页交叉验证只在后台写入 `data/variety_structure_checks.csv`，不在 report 中单独展示。

## Login Handling

奇货可查品种结构页通常需要登录态。

优先顺序：

1. 使用 Chrome 插件/浏览器缓存中的既有登录态。
2. 若 Chrome 状态不可用，再临时登录。
3. 临时登录只通过环境变量传递会话 Cookie；不得把账号、密码、Cookie 或令牌写入项目文件、报告或日志。

2026-06-22 已验证临时登录后结构页可读取；运行结束时临时 cookie jar 和验证码图片已删除。

## Report Generator Status

`scripts/generate_futures_report.py` 当前能力：

- 批量抓取 13 个观察席位的合约持仓 HTML 表格。
- 按品种汇总三组席位的多空持仓与日变化。
- 输出反向共振品种、三组最强偏多/偏空品种、家人反向解读。
- 输出重点品种主力合约资金方向。
- 输出强共振品种最近 5 个可用披露日观察。
- 仅对重点品种输出净多/净空前 5 席位结构分析；欧线集运仅保留关注标识，不输出席位结构结论。
- 支持 `REPORT_DATE` 指定输出日期目录。
- 支持 `REUSE_STRUCTURE_DATA=1` 复用同日已成功抓取的结构页数据，避免登录态过期后把成功数据覆盖成无权访问。
- 支持临时 `QHKCH_COOKIE` 环境变量注入登录态。

常用命令：

```powershell
$env:REPORT_DATE="YYYYMMDD"; python scripts/generate_futures_report.py
```

```powershell
$env:REPORT_DATE="YYYYMMDD"; python scripts/generate_institutional_seat_report.py
```

```powershell
$env:REPORT_DATE="YYYYMMDD"; $env:REUSE_STRUCTURE_DATA="1"; python scripts/generate_futures_report.py
```

## Latest Daily Report

2026-06-19 至 2026-06-21 端午节休市，不生成日报；自动化已同步 2026 年法定节假日跳过规则。

2026-06-24 日报：

- 输出：`output/futures_report_20260624/report.html`
- 披露日期：观察席位页面统一为 2026-06-24
- 抓取结果：2002 条合约席位记录
- 反向共振品种：29 个
- 强共振历史观察：20 条
- 结构页状态：8 个重点品种均为 OK；临时登录目录已删除。
- 运行环境：2026-06-24 已为当前 Codex 打包 Python 补齐 `matplotlib`、`seaborn`、`beautifulsoup4`，用于图表生成和 HTML 解析。

重点品种主力合约资金信号：

- 金：看空 -2160
- 银：看空 -1735
- 锡：看空 -2078
- 碳酸锂：看多 +1434
- 焦煤：看多 +2748
- 鸡蛋：看多 +6408
- 棕榈油：看空 -1096
- 橡胶：看多 +3723

## Historical Foreign Seat Report

2026-06-24 外资席位专题日报：

- 输出：`output/foreign_seat_report_20260624/report.html`
- 披露日期：外资与家人观察席位页面统一为 2026-06-24
- 外资席位：高盛期货 71 行，摩根大通 31 行，瑞银期货 30 行
- 家人席位：东方财富 38 行，徽商期货 95 行，方正中期 192 行，华安期货 38 行，中信建投 256 行
- 外资覆盖品种：46 个
- 外资总方向分数：+49799 手
- 外资加多合计：68754 手；外资加空合计：29762 手
- 外资与家人反向后同向共振：25 个品种

外资重点加多品种：

- 豆粕：加多 14798，净方向 +13560
- 菜粕：加多 10776，净方向 +26113
- 豆油：加多 10705，净方向 +9617
- PTA：加多 6588，净方向 +2672
- 豆一：加多 4263，净方向 +10390

外资重点加空品种：

- 螺纹钢：加空 10585，净方向 -10585
- 白糖：加空 5059，净方向 -5059
- 豆粕：加空 2645，净方向 +13560
- 苯乙烯：加空 1411，净方向 -1413
- 豆油：加空 1410，净方向 +9617

外资与家人反向共振靠前品种：

- PVC：外资 +7752，家人原始 -5113，反向后 +5113
- 菜粕：外资 +26113，家人原始 -4330，反向后 +4330
- 螺纹钢：外资 -10585，家人原始 +2158，反向后 -2158
- 苯乙烯：外资 -1413，家人原始 +5196，反向后 -5196
- 豆油：外资 +9617，家人原始 -1232，反向后 +1232

## Latest Institutional Seat Report

2026-06-24 机构席位合并专题日报：

- 输出：`output/institutional_seat_report_20260624/report.html`
- 披露日期：内资、外资、家人共 16 个观察席位页面统一为 2026-06-24
- 抓取结果：2480 条合约席位记录
- 内资样本：国泰君安 286 行，东证期货 279 行，永安期货 258 行，海通期货 197 行，浙商期货 231 行，中财期货 100 行，南华期货 189 行，申银万国 189 行
- 外资样本：高盛期货 71 行，摩根大通 31 行，瑞银期货 30 行
- 家人样本：东方财富 38 行，徽商期货 95 行，方正中期 192 行，华安期货 38 行，中信建投 256 行
- 内资方向分数：+66602；外资方向分数：+49799
- 内外资同向品种：20 个
- 内外资同向且家人反向后的三方强共振：14 个
- 三方偏多靠前：PVC、豆油、豆二、沥青、天然橡胶
- 三方偏空靠前：苯乙烯、纯碱、乙二醇、液化气、沪锌、沪铝、沪铜

新增脚本能力：

- `scripts/generate_institutional_seat_report.py` 直接读取奇货可查 broker/position，不依赖登录态。
- 生成 `contract_rows.csv`、`fetch_status.csv`、`domestic_variety_summary.csv`、`foreign_variety_summary.csv`、`family_variety_summary.csv`、`broker_variety_summary.csv`、`institutional_resonance.csv`。
- HTML 使用红多绿空、进度条、内外资象限地图、内资/外资席位分拆和抓取状态卡。
- 当前建议先与旧全席位日报并行 2-3 个交易日；若用户确认口径稳定，可用机构专题日报替代旧全席位日报。

## Main Trend Workbook Updates

主力趋势表格更新规则：

- `+` 表示多，`-` 表示空。
- 内资和外资同向时颜色加深。
- 只有一类机构方向，或家人/单机构信号时使用浅色。
- 多头方向用红色；空头方向用绿色。
- 周末列不写入。
- 后续更新必须按表头日期序列定位目标列，不能只依赖历史记忆里的列号；2026-07-02 实测当前桌面 workbook 中 2026-07-01 序列 46204 位于 FG 列。
- 每次更新并输出结果后，同时汇总最近 3 个交易日的强共振品种：内资、外资同向；内资、外资同向且家人反向后同向。同一品种连续 2 天及以上出现时，必须单独提醒用户。

近期更新：

- 6.4：EO 列，输出 `output/main_trend_update/`。
- 6.5：EP 列，输出 `output/main_trend_update_20260605/`。
- 6.8：EQ 列，输出 `output/main_trend_update_20260608/`。
- 6.9：ER 列，输出 `output/main_trend_update_20260609/`。
- 6.10：ES 列，输出 `output/main_trend_update_20260610/`。
- 6.11：ET 列，输出 `output/main_trend_update_20260611/`。
- 6.12：EU 列，输出 `output/main_trend_update_20260612/`。
- 6.15：桌面 workbook 实测在 EV 列，输出 `output/main_trend_update_20260615/`。
- 6.16：EW 列，输出 `output/main_trend_update_20260616/`。
- 6.17：EX 列，原地更新桌面 `主力趋势-6.16-已更新.xlsx`，不另存新版 workbook；验证输出在 `output/main_trend_update_20260617/`。
- 6.18：EY 列，原地更新桌面 `主力趋势-6.16-已更新.xlsx`，不另存新版 workbook；验证输出在 `output/main_trend_update_20260618/`。
- 6.22：FC 列，原地更新桌面 `主力趋势-6.16-已更新.xlsx`，不另存新版 workbook；验证输出在 `output/main_trend_update_20260622/`。
- 6.23：FD 列，原地更新桌面 `主力趋势-6.16-已更新.xlsx`，不另存新版 workbook；验证输出在 `output/main_trend_update_20260623/`。

最新 6.23 更新：

- 脚本：`scripts/update_main_trend_june23_in_place.mjs`
- 写入 24 个品种，无缺失行，无跳过项。
- 验证文件：`output/main_trend_update_20260623/written_cells.json`
- 预览图：`output/main_trend_update_20260623/fd_column_preview.png`
- 读回桌面文件确认 FD 列日期序列为 46196，代表 2026-06-23。

2026-06-30 主力趋势表补充更新：
- 根据用户补充的 6.24、6.25、6.26、6.29、6.30 交易蓝图，已原地更新桌面 `主力趋势-6.16-已更新.xlsx`。
- 写入列：6.24=FE、6.25=FF、6.26=FG、6.29=FJ、6.30=FK；6.27/FH 与 6.28/FI 为周末列，保持空白。
- 脚本：`scripts/update_main_trend_june24_30_in_place.mjs`；读回校验脚本：`scripts/verify_main_trend_june24_30.mjs`。
- 校验输出：`output/main_trend_update_20260624_20260630/written_cells.json`、`readback_checks.json`、`fe_fk_columns_preview.png`。
- 共写入 116 个品种日期单元格，无缺失行；6.30 沪铝因机构区同时出现小幅加多与加空、外资为加空，按合并偏空写入 `内资-`/`外资-`，该判断已记录在 `written_cells.json` 的 notes。

2026-07-02 主力趋势表 7.1 更新：
- 根据用户提供的 7.1 交易蓝图，已原地更新桌面 `主力趋势-6.16-已更新.xlsx`；按表头日期序列 46204 定位到 FG 列。
- 更新脚本：`scripts/update_main_trend_20260701_in_place.mjs`；读回校验脚本：`scripts/verify_main_trend_20260701.mjs`。
- 校验输出：`output/main_trend_update_20260701/written_cells.json`、`readback_checks.json`、`fg_column_preview.png`、`strong_resonance_last3days.json`。
- 写入 21 个品种，无缺失行；写入前已清空 FG 数据区并复制空白邻列格式，避免旧信号残留。
- 最近 3 个交易日按当前表头为 2026-06-29/FE、2026-06-30/FF、2026-07-01/FG；内外资同向重复品种：花生连续 3 天偏多、铝连续 2 天偏空；内外资同向且家人反向后三方同向仅 2026-07-01 玻璃偏空，暂无连续重复。

## Trading System Docs

- `docs/trading-philosophy.md`：上层交易哲学，沉淀市场客观性、风险观、最小阻力线、试探仓位和情绪纪律。
- `docs/trading-system.md`：交易系统 V2，已简化为五问模块、入场闸门、工具选择、仓位风控、退出规则和最小日志模板。
- `docs/trading-decision-checklist.md`：交易前检查清单，已简化为五问模块、入场条件、风险字段、禁止动作和 Codex 提醒口径。
- `docs/trading-log-framework.md`：由交易策略 Excel 提炼出的日志与复盘框架。
- `docs/yuque-integration.md`：语雀 CLI/MCP 连接方案。

2026-06-20 用户要求根据截图新增固定分析模块并简化交易系统；已将系统重构为五问模块：

- 基本面：主要矛盾是什么？
- 流动性：全球资金是宽松还是收紧？
- 仓位：市场已经站在哪边？
- 叙事：市场现在相信什么故事？
- 周期：当前处于哪个阶段？

当用户提出具体交易想法时，先检查五问模块是否明确，并继续检查交易周期、技术触发、逻辑证伪、最大可承受亏损、匹配仓位、止损点位和止盈计划。若未完成，应提示“未完成系统分析”。

2026-06-25 用户提供长期交易者投资感悟图片，要求内化到交易系统。已提炼并写入：

- `docs/trading-philosophy.md`：新增资金安全、杠杆风险、少交易、能力圈、安全边际、市场阶段等原则。
- `docs/trading-system.md`：在五问模块中加入能力圈、安全边际/风险收益比、杠杆、叙事追逐、牛熊/泡沫/低迷阶段判断。
- `docs/trading-decision-checklist.md`：新增“看不懂不开仓”“没有安全边际或风险收益比不开仓”“因别人赚钱或热门叙事不开仓”“不用杠杆掩盖判断不清”等禁止动作。
- `AGENTS.md`：交易决策提醒同步增加能力圈、安全边际、市场阶段和杠杆风险检查。

2026-06-25 用户提供行为金融提醒截图，要求内化并压缩检查清单。已更新：

- `docs/trading-philosophy.md`：新增反方论证、确认偏误、空仓测试、交易后行为复盘原则。
- `docs/trading-system.md`：入场闸门加入空仓测试、最强反方逻辑、过去 24 小时反向指标检查；日志模板加入空仓测试、最强反方逻辑、24 小时反向指标和行为复盘。
- `docs/trading-decision-checklist.md`：重构为三段式：交易前方向与反向证据、交易计划与风险、执行及复盘，并保留一票否决项。
- `AGENTS.md`：交易决策提醒新增空仓测试、最强反方逻辑、24 小时反向指标检查，防止确认偏误。

2026-07-05 用户提供主观自我提问截图，认为可作为市场情绪过热参考。已更新：

- `docs/trading-system.md`：在仓位模块新增“主观逆向情绪分”，用紧急感、近期趋势、身边共识、持有人扩散四问衡量主观拥挤度；分数越负越热，<= -4 禁止追第一买点/卖点。
- `docs/trading-decision-checklist.md`：交易前检查新增主观逆向情绪分；一票否决新增“主观逆向情绪分 <= -4 且没有第二类买卖点，不交易”。
- `docs/trading-philosophy.md`：情绪纪律新增“身边一致看好是接盘风险上升，身边一致恐慌也不能替代基本面和技术触发”的原则。
- `AGENTS.md`：交易系统提醒同步加入主观逆向情绪分检查，防止后续具体交易决策漏掉情绪过热过滤。

2026-07-05 用户提供“股市投资情绪周期”图片，认为可作为市场阶段参考。已更新：

- `docs/trading-system.md`：在周期模块新增潜伏期、醒悟期、狂热期、幻灭期四段情绪周期定位，并明确狂热期不追第一买点、幻灭期不盲目抄底。
- `docs/trading-decision-checklist.md`：将情绪周期位置并入五问模块，避免检查清单继续膨胀。
- `docs/trading-philosophy.md`：市场阶段新增“价格围绕价值偏离与回归”的情绪周期原则。
- `AGENTS.md`：交易系统提醒同步加入情绪周期检查。

2026-07-05 用户补充“当郁金香有了更多的故事”文章截图，强调市场共识和叙事可能短中期压过事实，交易者仍要客观跟随市场。已更新：

- `docs/trading-system.md`：在叙事模块新增“事实-共识-价格”共识检查，并在入场闸门要求逆共识交易必须等价格证明共识松动。
- `docs/trading-decision-checklist.md`：交易前检查新增共识检查，避免只凭事实判断过早逆市场。
- `docs/trading-philosophy.md`：最小阻力线章节新增事实、共识与价格原则，强调交易者不是裁判，不能因“知道真相”提前重仓。
- `AGENTS.md`：交易系统提醒同步将叙事扩展为叙事/共识，并加入逆共识过早风险检查。

2026-07-06 用户强调“大赚之后一定要出金，大亏之后一定要休息”，并提到 2026 年 6 月连续几次交易亏损合计近 10W，计划休息一段时间。已更新：

- `docs/trading-system.md`：在仓位与风险模块新增利润出金与亏损冷却规则，要求大赚后出金、单月大亏/连续 3 笔亏损/急于回本后停止新增实盘并完成亏损归因。
- `docs/trading-decision-checklist.md`：一票否决新增“单月大亏、连续 3 笔亏损或急于回本后，未完成冷却复盘，不交易”。
- `docs/trading-philosophy.md`：风险观和情绪纪律新增“大赚出金，大亏休息”，强调冷却期任务是恢复判断力而非追回亏损。
- `AGENTS.md`：交易系统提醒同步加入连续亏损或单月大亏时优先提醒冷却复盘。

2026-07-06 用户提供四篇技术分析入门 PDF，要求单独构建技术面分析框架。已更新：

- 新增 `docs/technical-analysis-framework.md`：将技术分析定位为执行层筛选器，整合大周期结构、中周期形态、小周期触发、入场止损止盈、一票否决和技术面日志模板。
- `docs/trading-system.md`：文首增加技术执行框架引用。
- 框架明确承接“宏观判断 -> 基本面验证 -> 资金行为 -> 技术形态执行”，强调技术形态不作为第一性开仓理由。
- 已纳入反转形态：头肩顶/底、双顶/双底、三重顶/底、楔形；持续形态：旗形、三角旗；波浪理论：5 浪推动、3 浪调整、三大铁律和交替原则。
- `AGENTS.md`：用户要求技术面分析时，优先使用 `docs/technical-analysis-framework.md`，按大周期结构 -> 中周期形态 -> 小周期触发输出。

## Verification Notes

已验证：

- 席位持仓页 HTML 中包含可解析的 `positionTable` 表格。
- 品种结构页未登录时会返回无权访问状态，脚本会记录状态而不是编造席位结构。
- 登录态可通过临时 `QHKCH_COOKIE` 读取结构页。
- `REPORT_DATE=20260624` 登录态重跑后生成的全席位 report 保持当前重点品种、前 5 结构页分析、红多绿空配色，8 个重点结构页均为 OK。
- `REPORT_DATE=20260624` 已生成外资专题 report，验证 8 个外资/家人席位均为 2026-06-24 披露日期，HTML 不含旧 40% 阈值或 EC 文案。
- `REPORT_DATE=20260624` 已生成机构专题 report，验证 16 个内资/外资/家人席位均为 2026-06-24 披露日期，HTML 不含旧 40% 阈值或 EC 文案；Playwright 浏览器二进制缺失，已退回 HTML/CSV 结构级 QA。
- 2026-06-25 曾更新 heartbeat 自动化 `automation` 为旧全席位、外资专题和机构专题并行；该历史口径已被 2026-06-30 与 2026-07-01 新规则取代：不再单独生成外资专题日报。
- 2026-06-17 自动化提示词已从过期的“黄金/白银/锡”同步为“沪金/沪银/沪锡”，避免金属结构页空表。

未完成或需注意：

- 浏览器视觉 QA 曾因 in-app browser 连接重置未完整跑完；当前主要依赖文件级、HTML 关键字和图表资产检查。
- 若奇货可查网页结构变化，应先验证抓取表格列，再更新分析逻辑。
- 若新增重点品种，需同步更新 `FOCUS_ITEMS`、README、AGENTS 与本交接文档。

## Margin Weighted Seat Report

2026-06-25 新增保证金金额口径席位日报：

- 脚本：`scripts/generate_margin_weighted_seat_report.py`
- 输出：`output/margin_weighted_seat_report_20260625/report.html`
- 数据目录：`output/margin_weighted_seat_report_20260625/data/`
- 席位底表：优先复用同日 `output/institutional_seat_report_YYYYMMDD/data/contract_rows.csv`；如需强制重抓，设置 `REFETCH_POSITIONS=1`。
- 保证金来源：东方财富期货保证金表 `https://qhweb.eastmoney.com/bzj/allexchange`，后台保留 `margin_reference.csv` 与 `margin_fetch_status.csv`。
- 6.25 覆盖率：席位明细 2496 行，涉及 71 个品种，保证金覆盖 71/71。
- 金额口径：加多金额 + 减空金额 - 减多金额 - 加空金额；同时输出机构合计多头边际/空头边际结构，用于识别“多增空减”“多减空增”“多空同增”“多空同减”。
- 6.25 金额口径结果：三方强共振 8 个，内外资同向 15 个；HTML 已通过关键字与 CSV 结构检查。

常用命令：

```powershell
$env:REPORT_DATE="YYYYMMDD"; python scripts/generate_margin_weighted_seat_report.py
```

## Latest 2026-06-26 Run

2026-06-26 已生成四份日报，所有 broker/position 抓取状态均为 2026-06-26：

- 全席位日报：`output/futures_report_20260626/report.html`；1984 行席位合约记录，反向共振 22 个，强共振 5 日历史观察 15 条。
- 外资专题日报：`output/foreign_seat_report_20260626/report.html`；外资覆盖 46 个品种，外资与家人反向共振 24 个。
- 机构合并专题日报：`output/institutional_seat_report_20260626/report.html`；2473 行席位合约记录，三方强共振 13 个，内外资同向 19 个。
- 保证金金额口径日报：`output/margin_weighted_seat_report_20260626/report.html`；复用机构专题底表 2473 行，保证金覆盖 71/71，三方强共振 13 个，内外资同向 19 个。
- 保证金来源：东方财富期货保证金表，`margin_fetch_status.csv` 显示更新时间为 06月26日 18:05:53。
- 重点品种结构页：`output/futures_report_20260626/data/variety_structure_checks.csv` 中 8 个重点品种均返回无权访问，报告不展示编造的结构页前五席位。

金额口径 6.26 靠前三方共振：

- 偏多：菜油、菜粕、沪铝等。
- 偏空：PP、液化气、中证1000股指、沪锌、苯乙烯等。

外资手数口径 6.26 摘要：

- 外资重点加多：豆粕、菜粕、PTA、豆油、菜油。
- 外资重点加空：螺纹钢、PVC、玻璃、苯乙烯、塑料。
- 外资与家人反向靠前共振：螺纹钢偏空，豆油/菜粕/菜油/豆粕偏多，PP 偏空。

## Latest 2026-06-30 Run

2026-06-30 已按新工作流生成三份日报，未生成外资专题日报：

- 全席位日报：`output/futures_report_20260630/report.html`；1999 行席位合约记录，反向共振 32 个，强共振 5 日历史观察 23 条。
- 机构合并专题日报：`output/institutional_seat_report_20260630/report.html`；2479 行席位合约记录，三方强共振 13 个，内外资同向 25 个。
- 保证金金额口径日报：`output/margin_weighted_seat_report_20260630/report.html`；复用机构专题底表 2479 行，保证金覆盖 70/70，三方强共振 13 个，内外资同向 25 个。
- 保证金表使用项目级周缓存，`margin_fetch_status.csv` 标记为 `CACHE_WEEKLY`，来源更新时间沿用 2026-06-29 17:06 左右的东方财富保证金表；本次未强制刷新。
- 校验确认：`output/foreign_seat_report_20260630/report.html` 不存在；全席位日报不含旧 40% 阈值文案；保证金日报包含“机构合计净金额排行”，且不含旧“内外资金额共振地图”。

## Next Steps

- 2026-06-29 根据用户要求更新日报工作流：后续不再单独生成外资专题日报 `output/foreign_seat_report_YYYYMMDD/report.html`，改由机构合并专题日报 `output/institutional_seat_report_YYYYMMDD/report.html` 统一介绍内资、外资和家人共振情况；旧全席位日报暂时继续并行，只有用户明确确认后再停用。已同步更新 heartbeat 自动化 `automation`、`README.md` 和 `AGENTS.md`，2026-06-29 不重新生成报告。
- 2026-06-29 执行规则更新：Windows PowerShell 下不要再使用 Bash 风格 heredoc（如 `python - <<'PY'`）；临时 Python 校验统一使用原生 `python -c "..."` 或项目已有脚本，避免 PowerShell 解析错误。
- 2026-06-29 根据用户浏览器批注优化保证金金额口径日报：`scripts/generate_margin_weighted_seat_report.py` 第 02 区块从内资/外资毛加多/加空金额改为“机构合计净偏多/净偏空金额”（内资+外资净方向金额），删除“内外资金额共振地图”；边际结构矩阵、机构与家人反向共振、内资/外资席位分拆均统一展示净金额变动；矩阵与共振表最后一列改为“内资+外资+家人原始方向”的三方净变动；品种名与代码相同时隐藏重复代码，避免 `PPPP`。
- 保证金表改为项目级 7 天缓存：默认复用 `data/margin_reference.csv` 与 `data/margin_fetch_status.csv`，只有设置 `FORCE_MARGIN_REFRESH=1` 才强制刷新东方财富保证金表；已用 `REPORT_DATE=20260629` 重跑 `output/margin_weighted_seat_report_20260629/report.html`，底表 2477 行、保证金覆盖 71/71、三方强共振 19、内外资同向 27；HTML/CSV 校验确认新净金额排行存在、旧毛加多/加空标题和共振地图消失、三方净变动和周缓存说明存在、`PPPP` 不再出现。

- 2026-06-26 根据用户浏览器批注优化 `scripts/generate_institutional_seat_report.py`：机构专题第 02 区块从“加多/加空毛动作排行”改为“净偏多/净偏空排行”，避免玉米等品种同时出现在加多和加空两侧；新增“内资毛动作与净方向背离拆解”表，标注苯乙烯这类加多动作较大但净方向偏空的品种，并同步展示外资方向、家人反向验证；统一品种代码显示，品种名与代码相同（如 PP）时隐藏重复代码，避免出现 `PPPP`。
- 已用 `REPORT_DATE=20260626` 重跑 `output/institutional_seat_report_20260626/report.html`，结果仍为 2473 行、三方强共振 13 个、内外资同向 19 个；HTML 校验确认新净方向标题存在、旧内资加多/加空排行标题消失、苯乙烯背离拆解存在、`PPPP` 不再出现。
- 每个交易日盘后重新生成日报并核对披露日期。
- 机构专题日报可每日同步生成 `output/institutional_seat_report_YYYYMMDD/report.html`；若用户确认可替代旧全席位日报，再停用旧全席位输出。
- 保证金金额口径日报可每日同步生成 `output/margin_weighted_seat_report_YYYYMMDD/report.html`，并核对保证金覆盖率与来源更新时间。
- 若结构页返回无权访问，优先尝试 Chrome 登录态，再临时登录。
- 对强共振品种继续观察最近 5 个可用披露日是否持续或反转。
- 主力趋势表格后续继续按交易蓝图图片更新对应日期列，周末列跳过。
- 后续技术面分析可把 OpenVLab K 线/期权页作为浏览器截图或人工输入源。

## 2026-07-03 Main Trend Workbook Update

根据用户提供的 2026-07-02 与 2026-07-03 交易蓝图，已原地更新桌面 `主力趋势-6.16-已更新.xlsx`：

- 2026-07-02 按表头日期序列 46205 定位到 FH 列；2026-07-03 按表头日期序列 46206 定位到 FI 列。
- 更新脚本：`scripts/update_main_trend_20260702_03_in_place.mjs`；读回校验脚本：`scripts/verify_main_trend_20260702_03.mjs`。
- 输出目录：`output/main_trend_update_20260702_03/`，包含 `written_cells.json`、`readback_checks.json`、`strong_resonance_last3days.json`、`fg_fi_columns_preview.png`。
- 共写入 46 个品种日期单元格，无缺失行；预览范围为 2026-07-01/FG、2026-07-02/FH、2026-07-03/FI。
- 7.3 合成橡胶家人区徽章与文字方向不完全一致；按文字“大幅加空合成橡胶”解读为家人原始偏空，反向后写入 `家人+`，并与内资同向偏多。

最近 3 个交易日强共振统计窗口为 2026-07-01/FG、2026-07-02/FH、2026-07-03/FI：

- 内资、外资同向共振合计 21 条；内资、外资同向且家人反向后同向的三方强共振合计 1 条。
- 连续 2 天及以上的内外资同向品种：螺纹钢连续 3 天偏空；铝连续 2 天偏空；花生连续 2 天偏多；锡连续 2 天偏多；棕榈油连续 2 天偏空。
- 三方强共振仅 2026-07-01 玻璃偏空出现，当前窗口暂无连续 2 天及以上的三方强共振品种。

## 2026-07-07 Main Trend Workbook Update

根据用户提供的 2026-07-06 与 2026-07-07 交易蓝图，已原地更新桌面 `主力趋势-已更新.xlsx`：

- 2026-07-06 按表头日期序列 46209 定位到 FL 列；2026-07-07 按表头日期序列 46210 定位到 FM 列。
- 更新脚本：`scripts/update_main_trend_20260706_07_in_place.mjs`；读回校验脚本：`scripts/verify_main_trend_20260706_07.mjs`。
- 输出目录：`output/main_trend_update_20260706_07/`，包含 `written_cells.json`、`readback_checks.json`、`strong_resonance_last3days.json`、`fj_fm_columns_preview.png`。
- 共写入 36 个品种日期单元格，无缺失行；强共振统计已跳过 2026-07-04 与 2026-07-05 周末空列，最近 3 个交易日窗口为 2026-07-03/FI、2026-07-06/FL、2026-07-07/FM。

最近 3 个交易日强共振：

- 内资、外资同向共振合计 15 条；内资、外资同向且家人反向后同向的三方强共振合计 3 条。
- 连续 2 天及以上的内外资同向品种：菜油连续 3 个交易日偏多；玻璃连续 2 个交易日偏空；豆油连续 2 个交易日偏多；锡连续 2 个交易日偏多。
- 连续 2 天及以上的三方强共振品种：玻璃连续 2 个交易日偏空。

## 2026-07-31 Main Trend Workbook Backfill

根据用户提供的 2026-07-10、07-13、07-14、07-17、07-20 至 07-24、07-28、07-30、07-31 交易蓝图，已原地更新桌面 `主力趋势-已更新.xlsx`：

- 写入列：07-10/FN、07-13/FQ、07-14/FR、07-17/FU、07-20/FX、07-21/FY、07-22/FZ、07-23/GA、07-24/GB、07-28/GF、07-30/GH、07-31/GI；同一内容的两张 07-24 图片只写入一次。
- 脚本：`scripts/update_main_trend_20260710_31_in_place.mjs`；读回校验：`scripts/verify_main_trend_20260710_31.mjs`。
- 输出目录：`output/main_trend_update_20260710_31/`，包含写入清单、回读校验、最近 3 个交易日强共振 JSON 与列区间预览图。
- 共写入 250 个品种日期单元格，无缺失行；截图中的“沪铜/沪铝/沪镍/黄金/白银”按表内既有行名映射为“铜/铝/镍/金/银”。

最近 3 个交易日窗口为 2026-07-28/GF、2026-07-30/GH、2026-07-31/GI：

- 内资、外资同向共振共 20 条；三方强共振共 4 条。
- 连续共振重点：螺纹钢、热卷连续 3 个交易日内外资同向偏空；豆一、豆油连续 2 个交易日内外资同向偏空。
- 三方强共振为 07-28 纯碱偏空，07-31 锡偏多、纯碱偏空、玻璃偏多；最近 3 个交易日内没有连续两天的三方强共振。

## 2026-08-10 Main Trend Workbook Update

根据用户提供的 2026-08-03、08-04、08-05、08-06、08-07、08-10 交易蓝图，已在桌面 `主力趋势-已更新.xlsx` 末尾延伸并更新 8 月日期列：

- 原表止于 07-31/GI；按既有格式新增 08-01/GJ 至 08-10/GS，周末 08-01、08-02、08-08、08-09 仅保留日期列且数据区为空。
- 写入交易日列：08-03/GL、08-04/GM、08-05/GN、08-06/GO、08-07/GP、08-10/GS。
- 脚本：`scripts/update_main_trend_20260803_10_in_place.mjs`；读回校验：`scripts/verify_main_trend_20260803_10.mjs`；输出目录：`output/main_trend_update_20260803_10/`。
- 共写入 124 个品种日期单元格，无缺失行；6 个代表性单元格回读通过，列区间预览通过。

最近 3 个交易日窗口为 2026-08-06/GO、2026-08-07/GP、2026-08-10/GS：

- 内外资同向共振：08-06 有金、铜、锌、塑料、PVC、玻璃、白糖偏多，以及镍、菜粕偏空；08-07 有铜、锌、苯乙烯、纯碱、白糖偏多；08-10 有碳酸锂、纯碱偏多，纸浆偏空。
- 三方强共振：08-06 玻璃偏多；08-07 与 08-10 纯碱偏多。
- 连续重点：纯碱连续 2 个可用交易日出现内外资与家人反向后三方同向偏多，须重点观察；铜、锌、白糖连续 2 个交易日内外资同向偏多。

## 2026-07-07 Report Workflow Sector Grouping Update

根据用户最新要求，日报工作流已改为只生成两份正式报告：

- 机构合并专题：`output/institutional_seat_report_YYYYMMDD/report.html`
- 保证金金额口径：`output/margin_weighted_seat_report_YYYYMMDD/report.html`

旧全席位日报 `output/futures_report_YYYYMMDD/report.html` 已从每日自动化正式输出中取消；`scripts/generate_futures_report.py` 仍保留为基础函数来源和手动排查脚本。

本次代码变更：

- `scripts/generate_futures_report.py` 新增商品板块映射与 `BASE.add_sector_columns()`，继续过滤股指 `IC/IF/IH/IM`、国债 `T/TF/TL/TS`，并补充过滤已知外盘连续品种。
- `scripts/generate_institutional_seat_report.py` 和 `scripts/generate_margin_weighted_seat_report.py` 的 02 至后续所有具体品种列表，改为先插入板块汇总，再列该板块下的品种净偏多/净偏空。
- 板块采用中国商品口径：贵金属、有色金属、家人品种、黑色钢矿、煤化工、油化工、油脂油料、谷物饲料、农副软商、建材航运、其他商品；其中玻璃 `FG`、纯碱 `SA`、氧化铝 `AO`、烧碱 `SH` 强制归入“家人品种”板块。
- 机构专题和保证金专题均保留净变化可视化条形刻度，并新增板块标题、板块汇总行和席位卡内板块分隔。

验证：

- `py_compile` 通过：`scripts/generate_futures_report.py`、`scripts/generate_institutional_seat_report.py`、`scripts/generate_margin_weighted_seat_report.py`。
- 使用 `output/institutional_seat_report_20260707/data/` 与 `output/margin_weighted_seat_report_20260707/data/` 离线构建 HTML 成功；机构专题出现 28 个板块汇总行，保证金专题出现 29 个板块汇总行，均包含“家人品种”。
- heartbeat 自动化 `automation` 已同步为两份正式日报，不再自动生成旧全席位日报。

## 2026-07-08 Sector Classification Refinement

根据用户反馈，机构合并专题和保证金金额口径日报的板块口径已进一步收敛：

- 黑色矿钢和煤化工合并为“黑色系”：焦煤 `JM`、煤炭 `ZC`、铁矿石 `I`、螺纹钢 `RB`、热卷 `HC`、锰硅 `SM`、硅铁 `SF`、尿素 `UR`、PVC `V`。
- 油化工包括：原油 `SC`、燃油 `FU`、低硫油 `LU`、沥青 `BU`、LPG `PG`、甲醇 `MA`、苯乙烯 `EB`、纯苯 `BZ`、PX `PX`、PTA `TA`、天然橡胶 `RU`、PP `PP`、合成橡胶 `BR`、塑料 `L`、乙二醇 `EG`、短纤 `PF`、瓶片 `PR`。
- 农产品拆为三类：谷物饲料 `M/RM/C/A/B`，油脂油料 `P/OI/PK/Y`，农副软商 `CF/SR/LH/AP/JD/CJ/NR`；淀粉 `CS` 因流动性偏低不参与统计。
- 玻璃 `FG`、纯碱 `SA`、氧化铝 `AO`、烧碱 `SH` 继续强制归入“家人品种”。
- 两份正式日报的板块标题改为展示板块内“净多 / 净空”品种列表，不再展示板块整体净多、净空金额或合计手数，避免板块内分化被合计值掩盖。

验证：

- `py_compile` 通过：`scripts/generate_futures_report.py`、`scripts/generate_institutional_seat_report.py`、`scripts/generate_margin_weighted_seat_report.py`。
- 使用 `output/institutional_seat_report_20260708/data/` 离线构建机构合并专题 HTML 成功，约 111494 字符，34 个板块汇总行，包含“黑色系”，不含旧“黑色钢矿/煤化工”板块名。
- 使用 `output/margin_weighted_seat_report_20260708/data/` 离线构建保证金金额口径 HTML 成功，约 117815 字符，28 个板块汇总行，包含“黑色系”，不含旧“黑色钢矿/煤化工”板块名。

## 2026-07-09 Section 02 Per-Sector Top 3 Update

根据用户反馈，02 排行模块不再先做全市场 Top N 再分板块，因为这会导致油化工等金额较小板块被全局排序截掉。

本次规则更新：

- 机构合并专题和保证金金额口径日报的 02 模块改为先按商品板块分组。
- 每个已出现的板块分别列出前三净多、前三净空品种。
- 若某板块没有净多或没有净空，仍保留该板块，并在对应侧显示“今天没有净多品种”或“今天没有净空品种”。
- 该逻辑只影响 02 排行模块；后续边际矩阵、共振表和席位分拆继续按原有限量排序和板块标题展示。

验证：

- `py_compile` 通过：`scripts/generate_institutional_seat_report.py`、`scripts/generate_margin_weighted_seat_report.py`。
- 使用 `output/institutional_seat_report_20260709/data/` 离线构建机构合并专题 HTML 成功，约 134526 字符，02 区域保留油化工板块，并出现 4 条空侧说明。
- 使用 `output/margin_weighted_seat_report_20260709/data/` 离线构建保证金金额口径 HTML 成功，约 129344 字符，02 区域保留油化工板块。

## 2026-07-09 Section 02 Three-Party Net Result Update

根据用户进一步反馈，02 排行模块改为直接展示三方共振后的净结果：

- 机构合并专题的 02 主数值改为 `combined_signal = 内资方向分数 + 外资方向分数 - 家人原始方向分数`。
- 保证金金额口径日报的 02 主数值改为 `combined_amount_signal = 内资金额分数 + 外资金额分数 - 家人原始金额分数`。
- 02 不再单独列内资净偏多/净偏空、外资净偏多/净偏空；只保留“三方共振净偏多”和“三方共振净偏空”两列。
- 每张卡片底部保留拆解：机构合计与家人反向，方便确认三方净结果由谁贡献。

验证：

- `py_compile` 通过：`scripts/generate_institutional_seat_report.py`、`scripts/generate_margin_weighted_seat_report.py`。
- 使用 `output/institutional_seat_report_20260709/data/` 离线构建机构合并专题 HTML 成功，包含“三方共振净方向排行”，不再包含“内资净偏多排行/外资净偏多排行”。
- 使用 `output/margin_weighted_seat_report_20260709/data/` 离线构建保证金金额口径 HTML 成功，包含“三方共振净金额排行”，不再使用“机构合计净偏多金额”作为 02 标题。

## 2026-07-10 Margin Report Trend Temperature Module

根据用户提供的趋势温度截图，保证金金额口径日报新增独立“趋势温度与资金共振”模块，放在 02 三方净金额排行之后：

- 趋势数据优先读取 `data/trend_temperature_YYYYMMDD.csv`，否则读取 `data/trend_temperature_latest.csv`。
- 当前已根据截图落地 `data/trend_temperature_latest.csv`，共 22 行；其中 21 个有效趋势温度、1 个 `平`。
- 模块只纳入 `温/热/沸/凉/寒/冻`，过滤 `平`；`温/凉`定义为左侧预警，`热/寒`定义为右侧确认，`沸/冻`定义为极端警戒。
- 资金关系使用三方净金额 `combined_amount_signal = 内资 + 外资 - 家人原始` 判断：趋势方向与三方净金额同向为“资金顺势”，反向为“资金逆势”，金额为 0 为“资金未验证”。
- 后台输出 `output/margin_weighted_seat_report_YYYYMMDD/data/trend_temperature_used.csv`，方便核对当次使用的趋势温度源。

验证：

- `py_compile` 通过：`scripts/generate_margin_weighted_seat_report.py`。
- 已用 `REPORT_DATE=20260709` 重跑 `output/margin_weighted_seat_report_20260709/report.html`；底表 2530 行，保证金覆盖 63/63，三方强共振 14 个，内外资同向 22 个。
- HTML 校验确认“趋势温度与资金共振”为 03 号模块，“期货资金潮汐”顺延为 04 号模块，“抓取与保证金状态”为 09 号模块。
- 趋势模块中 `SN/锡` 的 `平` 指标已过滤；CSV 无 `IC/IF/IH/IM/T/TF/TL/TS` 残留；HTML 不含“共振地图”“map-wrap”“map-section”。

## 2026-07-10 Trend Animal API Integration

- 新增 `scripts/fetch_trend_animal_snapshot.py`。它只从 `TREND_ANIMAL_API_KEY` 环境变量读取密钥，每次先调用官方接口说明、更新状态和字段计费，再通过 `searchTicker` 获取 8 个重点商品的 `tmId`，最后以最小字段集调用 `getTickerSnapshot`。
- 调用范围限定为金、银、锡、碳酸锂、焦煤、鸡蛋、棕榈油、橡胶；费用阈值默认 1 元，达到阈值时不请求快照。不会把密钥、含密钥 URL、账户余额或账单写入项目。
- 2026-07-10 的商品期货 API 数据日为 `2026-07-10`，更新时间 `17:59:00`；8/8 重点商品已解析，预估费用 `0.368` 元。输出 `data/trend_temperature_20260710.csv` 与不含密钥的 `data/trend_animal_fetch_status_20260710.json`。
- 保证金日报的 03 模块已改为明确区分 API 直接事实与资金判断，新增右侧状态/天数、阶段/温度变化、局部强度、日收益原值列；`平` 继续过滤。官方文档未定义 `return1d` 序列化单位，报告不再自行添加百分号。
- 2026-07-10 两份正式日报已生成：机构专题 2519 行、内外资同向 23 个、三方强共振 13 个；保证金覆盖 63/63。HTML 与 CSV 校验无股指/国债/外盘残留，无共振地图，无 API Key。

## Latest 2026-07-01 Workflow Update

2026-07-01 根据用户提供的 BW Research 风格参考图，更新日报视觉与工作流：
- 三份日报均取消共振地图/散点象限地图；源码中机构合并专题和保证金金额口径专题的旧地图函数也已移除，避免后续误调用。
- 全席位日报取消重点品种结构页结果验证展示，并短路结构页抓取；全席位日报只保留基础资金面、重点品种主力合约和数据读取状态。
- 机构合并专题新增“期货资金潮汐”模块；当前底表暂无行情涨跌字段，暂按“资金净流入/流出 × 总持仓增/减”判断资金潮汐，后续接入行情源后可升级为“资金流入/流出 × 上涨/下跌”四象限。
- 保证金金额口径日报新增“期货资金潮汐”模块，并将金额边际矩阵升级为同一行内可视化比较：内资、外资、家人原始、家人反向、机构合计均使用净金额和条形刻度辅助对比。
- 机构合并专题的核心品种全景使用同一行内条形刻度展示内资、外资、家人相对持仓变化，并保留多头/空头/总持仓边际。
- heartbeat 自动化 `automation` 已同步新口径：不再单独外资专题，不输出共振地图，全席位日报不再做结构页结果验证，机构/保证金日报承担主要视觉分析。

2026-07-01 已重新生成并验证：
- 机构合并专题：`output/institutional_seat_report_20260701/report.html`，2450 行席位合约记录，三方强共振 15 个，内外资同向 22 个。
- 保证金金额口径日报：`output/margin_weighted_seat_report_20260701/report.html`，复用机构底表 2450 行，保证金覆盖 70/70，三方强共振 15 个，内外资同向 22 个。
- 全席位日报：`output/futures_report_20260701/report.html`，1969 行席位合约记录，反向共振 28 个，强共振 5 日历史观察 19 条。
- HTML 校验确认：三份报告均不含“共振地图”“map-wrap”“map-section”；机构合并专题和保证金金额口径日报均包含“期货资金潮汐”；全席位日报不含“重点品种持仓结构”或“结构页前”。
- 运行依赖：当前 Codex bundled Python 已补 `beautifulsoup4`、`matplotlib`、`seaborn`；系统 Python 仍可能缺 `pandas`，运行日报优先使用 `C:\Users\29266\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`。


## 2026-07-01 商品过滤与期权波动率 Demo

- 三份席位资金日报已加入商品过滤：默认排除股指期货 `IC/IF/IH/IM` 与国债期货 `T/TF/TL/TS`，当前只观察商品期货/期权相关品种。
- 过滤逻辑集中在 `scripts/generate_futures_report.py` 的 `filter_commodity_rows()`，机构合并专题与保证金金额口径脚本复用该函数。
- 已重跑 2026-07-01 三份日报并校验 CSV：`output/futures_report_20260701/data/broker_contract_rows.csv`、`output/institutional_seat_report_20260701/data/contract_rows.csv`、`output/margin_weighted_seat_report_20260701/data/amount_contract_rows.csv` 均无 `IC/IF/IH/IM/T/TF/TL/TS` 残留。
- 新增期权波动率 demo 脚本 `scripts/generate_option_vol_report.py`，输出 `output/option_vol_report_20260701/report.html`，后台 CSV 为 `output/option_vol_report_20260701/data/option_watchlist_snapshot.csv` 与 `openvlab_fetch_status.csv`。
- OpenVLab 的 market、light、volatility analysis 页面可访问，但公开静态 HTML 主要是前端动态壳；本次 demo 只将用户截图中的沪银 2608 隐波/实波/偏度样例标注为截图样例，未把它伪装成实时接口数据。后续若能定位历史接口，再补 5 日实波、隐波、偏度变化。
## 2026-07-13 Focus Watchlist Update

- 重点品种已更新为：燃油 `FU`、苯乙烯 `EB`、碳酸锂 `LC`、豆粕 `M`、鸡蛋 `JD`、焦煤 `JM`、沪金 `AU`、沪银 `AG`、欧线集运 `EC`、生猪 `LH` 主力合约。
- `scripts/generate_futures_report.py` 的兼容重点清单与 `scripts/fetch_trend_animal_snapshot.py` 的趋势动物 API 快照清单已同步；趋势 API 后续会按新的 10 个品种估算费用并继续遵守默认 1 元上限。
- 欧线集运 `EC` 保留在重点关注清单中，但奇货可查无可用席位持仓数据：不得纳入席位资金合计或结构页结论，报告中应明确标记为数据不可用。
## 2026-07-13 Daily Report Run

- 已生成机构合并专题：`output/institutional_seat_report_20260713/report.html`，2439 条商品席位合约记录，内外资同向 17 个，三方强共振 11 个。
- 已生成保证金金额口径日报：`output/margin_weighted_seat_report_20260713/report.html`，保证金覆盖 63/63；两份报告的全部席位披露日期均为 `2026-07-13`，当时商品 CSV 无股指、国债或外盘残留，报告无共振地图且保留板块行。后续新增的独立股指 CSV 不改变商品过滤口径。
- 本次自动化环境未提供 `TREND_ANIMAL_API_KEY`，因此未调用趋势动物 API。保证金日报的趋势模块明确标记为沿用 `trend_temperature_latest.csv` 中的 `2026-07-10` 截图来源数据，不视为当日 API 事实。
- 生成保证金日报时一次性安装的 `tmp/bs4-runtime` 已移除；不要将该临时依赖目录提交或保留。

## 2026-07-13 Weather, Index And Panorama Update

- 新增 `scripts/fetch_qhk_weather_risk.py`，读取 AI 天眼公开天气看板与未来预警接口。机构专题新增“农产品天气风险预警”，分别列出天气事实、市场反馈证据和三方席位资金验证，不把天气风险直接等同于涨跌信号。
- 2026-07-13 共取得 15 条农业天气预警，其中当日 12 条、未来 3 条；机构专题输出 `data/agri_weather_risk.csv` 与抓取状态文件。
- 保证金日报新增独立“股指资金与趋势观察”。`IH/IF/IC/IM` 的席位金额来自机构抓取的未过滤底表，写入独立 `stock_index_amount_contract_rows.csv` 和 `stock_index_amount_resonance.csv`；不参与商品板块、商品共振或保证金覆盖率。
- `scripts/fetch_trend_animal_snapshot.py` 已加入上证 50、沪深 300、中证 500、中证 1000、科创 50、创业板 50 的指数搜索，并继续执行文档、更新日、字段费用和总费用闸门。2026-07-13 当前环境未提供 `TREND_ANIMAL_API_KEY`，所以股指趋势与日收益保持明确降级状态，没有伪造数据。
- 参考 BW Research 页面后，机构专题“核心品种全景”新增当前净持仓列，将机构/家人存量仓位与今日边际变化分开；未采用已被用户取消的地图模块。
- 保证金网页解析已由运行时 `BeautifulSoup` 依赖改为 Python 标准库 `HTMLParser`，避免系统环境缺包导致日报中断。
- 两份报告已按新模块重新生成，各复用 2518 条未过滤席位合约底表；商品 CSV 无股指残留，股指独立表仅含 `IH/IF/IC/IM` 四类。

## 2026-07-14 Daily Report Run

- 已生成 `output/institutional_seat_report_20260714/report.html` 与 `output/margin_weighted_seat_report_20260714/report.html`，两份报告复用 2543 条未过滤席位合约底表；全部席位披露日为 `2026-07-14`。
- 三方强共振 15 个，内外资同向 25 个；保证金覆盖 63/63，保证金表更新时间为 `07月14日 17:14:11`。
- AI 天眼天气数据日为 `2026-07-14`，农业预警 17 条，其中当日 13 条、未来 4 条；未来预警涉及红枣、鸡蛋、棉花和玉米。
- 股指独立表仅含 `IH/IF/IC/IM`，商品 CSV 无股指、国债残留；报告不含共振地图或敏感信息。
- 当前自动化环境未提供 `TREND_ANIMAL_API_KEY`，因此未发起趋势动物 API 请求；趋势与日收益字段保持明确降级状态。

## 2026-07-15 Trading System Documentation Consolidation

用户认为交易系统、清单和哲学内容重复，已将交易文档收敛为“一份主系统加四份按需附件”：

- `docs/trading-system.md`：唯一主文档，保留五问分析、开仓闸门、工具选择、仓位退出、情绪与冷却规则。
- `docs/trading-decision-checklist.md`：压缩为开仓前十问、一票否决和四项持仓复盘；硬纪律统一放在清单，不新增独立 `纪律.md`。
- `docs/trading-philosophy.md`：只保留长期市场观、能力圈、风险观和情绪原则。
- `docs/technical-analysis-framework.md`：压缩为大周期方向、中周期结构、小周期触发、入场退出和技术面七问。
- `docs/trading-log-framework.md`：只保留每日观察、单笔交易卡和复盘归因。
- `README.md`：更新五份文档的职责和日常使用顺序。
- `AGENTS.md`：将繁琐的主观逆向情绪分收敛为四项主观拥挤检查。

保留的关键约束包括：事实、共识与价格分离，资金数据标注披露日期，空仓测试，最强反方逻辑，24 小时反向信号，技术触发，证伪与止损止盈，匹配仓位，亏损不补仓，大赚出金和大亏冷却。
## 2026-07-15 Daily Report Run

- Generated `output/institutional_seat_report_20260715/report.html` and `output/margin_weighted_seat_report_20260715/report.html` from 2,471 commodity contract rows; all 16 broker disclosures were dated `2026-07-15`.
- Detected 12 three-party strong-resonance varieties and 17 domestic/foreign same-direction varieties. Margin coverage was 63/63 using the weekly cache updated `07月14日 17:14:11`.
- AI Tianyan weather data was dated `2026-07-15`: 17 agricultural alerts, including 13 current-day and 4 future alerts. The independent stock-index table contained only `IH/IF/IC/IM`.
- Validation passed: both HTML reports were non-empty and dated correctly; commodity CSVs contained no stock-index, government-bond, or overseas symbols; no resonance map remained; required sector sections were present; no sensitive key was written.
- `TREND_ANIMAL_API_KEY` was unavailable in the automation environment, so the Trend Animal API was not called and the strong-resonance summary correctly reports no current-day return data.

## 2026-07-15 Research Dashboard MVP

- 新增 `scripts/build_research_dashboard.py`，将机构专题与保证金日报的共同披露日整理为只读历史快照；首版共纳入 15 个交易日、最新 63 个商品品种。
- 新增 `web/research_dashboard/` 静态前端，并生成 `output/research_dashboard/index.html` 与 `data/dashboard.json`。
- MVP 页面包含总览、板块前三净多/净空、农业天气、独立股指、品种全景、三组资金拆解、日期切换、单品种历史路径和数据状态；不包含共振地图。
- 三方口径保持 `内资 + 外资 - 家人`；商品主体继续排除 `IC/IF/IH/IM/T/TF/TL/TS`，股指只在独立区块展示。
- 趋势来源日期与报告日不一致时标记“旧”或“非当日”，不把历史截图伪装成当日 API 事实。
- 浏览器验收通过：桌面端无页面横向溢出；日期切换、强共振卡进入品种详情、搜索过滤均可用；移动端 390px 宽度无页面级横向溢出；控制台无警告或错误。
- 历史曲线严格截断到当前所选快照日期，回看旧日期时不会引用未来披露日数据。
- 当前未改每日自动化。用户确认 MVP 方向后，再把 `scripts/build_research_dashboard.py` 接到两份日报成功生成之后。

## 2026-07-15 Research Dashboard First Feedback

- 板块方向速览中的品种字号提高 2px，桌面端实测计算字号为 13px。
- 强共振卡现可直接切换到对应品种详情；详情新增最新价格指数、`return1d` API 原值，以及按席位聚合全部合约后的净多/净空前五。样本不足五家时显示真实数量，不补齐虚构席位。
- `scripts/fetch_trend_animal_snapshot.py` 的最小快照字段增加 `priceIndex`。本次严格先检查官方文档、更新状态与字段计费，商品数据日为 `2026-07-15`，共解析 10/16 个目标，预计费用 0.460 元；其中 9 个为商品，欧线集运与部分股指未定位成功。
- 官方文档只将 `priceIndex` 定义为价格指数、`return1d` 定义为日收益率，未说明 `return1d` 的序列化单位；网页因此展示接口原值，不自行乘以 100 或添加百分号。
- 浏览器验收通过：点击豆粕强共振卡后进入 `豆粕 M` 详情；行情显示价格指数 3,126、`return1d +0.0049（API原值）`；净多席位为 5/5，净空席位按真实样本显示 3/5；页面无脚本错误且桌面端无横向溢出。

## 2026-07-16 Eastmoney Main-contract Closing Quotes

- 新增 `scripts/fetch_eastmoney_main_quotes.py`。脚本先读取东方财富期货主力清单，再按报告日从对应主力合约日线读取开高低收、涨跌幅、成交量和成交额，输出 `data/eastmoney_main_quotes_YYYYMMDD.csv` 与状态 JSON。
- 行情按报告日精确查询，避免夜盘开始后把实时夜盘价格误当成上一交易日收盘价。工作站详情不再使用趋势动物 `priceIndex` / `return1d` 作为商品行情；趋势动物继续只提供趋势温度、强度等趋势事实。
- `2026-07-15` 快照共发现 87 个非月均主力合约，82 个取得对应报告日日线；缺失为 `JR/PM/RI/WH/ZC`。工作站当前 63 个商品品种全部获得当日收盘行情。
- 浏览器验收通过：豆粕详情显示主力 `m2609`、收盘价 3,066、涨幅 +0.43%，行情日期为 `2026-07-15 · 东方财富`，趋势温度仍独立显示“热”；控制台无页面错误，桌面端无横向溢出。

## 2026-07-16 Daily Report Run

- 本机时区确认是 `China Standard Time (UTC+08:00)`；heartbeat 的 `09:02Z` 应换算为北京时间 `17:02`，不得把带 `Z` 的时间直接当作本地时间。
- 已生成 `output/institutional_seat_report_20260716/report.html` 与 `output/margin_weighted_seat_report_20260716/report.html`，复用 2,454 条商品席位合约记录；全部 16 个席位披露日均为 `2026-07-16`。
- 三方强共振 18 个，内外资同向 22 个，保证金覆盖 63/63；天气预警 17 条，其中当日 14 条、未来 3 条；独立股指表仅含 `IH/IF/IC/IM`。
- 趋势动物在付费请求前检查到商品数据仍为 `2026-07-15`，因此跳过快照调用，未把旧趋势作为 7 月 16 日事实。
- 东方财富报告日日线匹配 82/87 个主力合约，两份日报的强共振通知表改用该日线的 `change_pct`，不再用趋势动物 `return1d` 代替商品涨跌幅。
- 自动化 `automation` 仍按工作日北京时间 17:00 运行；提示词已增加 UTC 转北京时间规则、东方财富收盘行情抓取和强共振表的新涨跌幅来源。

## 2026-07-16 Trading Philosophy Model Discipline

- 用户提供“投资为什么不是科学”的文章截图，认可模型有限、理论可修正和个人框架需要实践校准的观点。
- `docs/trading-philosophy.md` 新增“模型与方法”：投资保持科学态度，但不把模型当作真理；假设必须可证伪，历史结果要接受样本外和真实交易检验。
- 明确他人框架只能借鉴，最终结论要由个人知识、经历和交易日志校准；系统只在复盘后修改，不在持仓压力下改写。
- 未把文章引申为反数据或凭感觉交易，也未改动交易系统与决策清单的执行规则。

## 2026-07-16 Research Dashboard Annotation Pass

- 板块规则修正：低硫油 `LU`、瓶片 `PR` 归入油化工；20号胶 `NR` 归入农副软商；淀粉 `CS` 因流动性偏低从日报和研究工作站统计中排除。
- 板块方向速览的每个品种改为可点击按钮，点击后进入该品种详情；净变动使用红多绿空进度条，并把金额放在进度条右侧。
- 品种详情表头按“涨跌幅、收盘价”排列，字号一致；上涨为红色、下跌为绿色。三组净持仓改为以零轴为中心的红绿进度条，并保留今日边际金额。
- 历史资金曲线新增纵轴、加粗零轴、上下金额刻度与首末日期；浏览器分别切换 20号胶和豆粕验证，刻度会随品种数据动态更新。
- 构建脚本为 `app.js` 和 `styles.css` 增加版本查询参数，避免本地服务复用旧缓存；最新快照为 `2026-07-16`，共 62 个商品品种，控制台无错误。

## 2026-07-16 Research Dashboard V2 Concept

- 第二阶段先产出隔离的品种详情概念稿 `output/research_dashboard_v2_mockup/index.html`，未修改现有 V1 工作站，也未接入每日自动化。
- 概念稿以焦煤为示例，把行情、趋势温度、三方资金、席位结构、基本面、研报分歧和历史事件组织成可追溯证据链；所有数字明确标注为设计示意，不作为当日事实。
- 新增 `docs/research-dashboard-v2-plan.md`，记录产品信息架构和静态托管、个人服务器、多用户产品三个部署阶段。
- 当前部署建议是不立即购买服务器：先用本地或 COS/OSS 静态托管评审产品；加入登录、服务端抓取、数据库或私有数据后再购 2 核 2 GB 轻量服务器。
- 浏览器验收通过：1440×1024 无横向溢出，品种观察列表可切换，详情导航可滚动到资金与席位区域；设计审阅图为 `design-review.png` 与 `design-review-first-screen.png`。

## 2026-07-16 Trend API Daily Call And V2 Bar Fix

- 趋势动物 API 改为每个报告日调用一次，不再因预计费用达到 1 元而跳过；调用后用 `getAccountBalance` 的 ledger 汇总报告日实际消费，只有超过 1 元才输出提醒，余额、账单明细和实际消费金额不落盘。
- 2026-07-16 实跑解析 10/16 个目标，其中重点商品 9 个、指数 1 个，预计本次费用 0.440 元，当日消费提醒未触发。焦煤 API 事实为温度“平”、局部强度 28.6、未进入右侧。
- V2 概念稿的存量净持仓条形已把色条与数值拆为独立列；1440px 与 1100px 验证均无重叠。概念稿同步展示东方财富焦煤收盘价 1,261.0、涨跌幅 -0.32%，并明确其余资金/基本面数字仍为示意。
- 自动化 `automation` 已同步每日趋势调用与超过 1 元提醒规则。
- 2026-07-16 趋势商品数据实际更新时间为 18:13，晚于资金日报 17:00 触发；当前仍保持用户指定的 17:00 日报时间，若需要保证趋势当日命中，后续应单独增加晚间趋势刷新而不是延迟资金日报。

## 2026-07-17 ZSXQ Equity Sentiment And Early Report Run

- 新增 `scripts/fetch_zsxq_equity_sentiment.py`，复用 `zsxq-cli` 安全登录态读取“趋势小程序”知识星球报告日内帖子、评论及 Nick 的当日发帖/回复。输出为 `data/zsxq_equity_sentiment_YYYYMMDD.csv` 与 `data/zsxq_equity_sentiment_summary_YYYYMMDD.json`；只保留脱敏文本摘要，不落盘账号、Cookie、token、签名媒体 URL 或完整原帖。
- 2026-07-17 取得 14 条同日样本，其中帖子 4、评论 10、Nick 样本 3。规则化得分为 -43，标签“风险偏好偏低”，置信度中；报告将社区事实、Nick 观点和分析判断分列，并明确该指标不等同于股指涨跌预测。
- 保证金日报股指板块已加入“A股社区情绪指标”；桌面端 1440px 与移动端 390px 浏览器验收通过，页面无横向溢出、控制台无错误。宽表格改为板块内横向滚动，报告模板使用内嵌空 favicon，避免本地服务产生无意义 404。
- 本次在北京时间上午提前生成 `output/institutional_seat_report_20260717/report.html` 与 `output/margin_weighted_seat_report_20260717/report.html`。席位最新披露日仍为 2026-07-16，共 2438 条商品合约记录；三方强共振 18 个，内外资同向 22 个，保证金覆盖 62/62。天气数据日为 2026-07-17，共 14 条当日预警、4 条未来预警。17:00 自动化仍会按正常流程重新生成。
- 趋势动物在付费快照前确认商品数据日仍为 2026-07-16，因此没有把旧趋势写成 2026-07-17 当日事实。
- 按官方实时字段计费与当前日报 62 个商品品种估算：只抓 `trendTemperatureCurr` 时，按行数折扣每日约 0.2144 元；首次逐品种 `searchTicker` 约增加 0.62 元，首日合计约 0.8344 元。若对 62 个品种抓取当前重点清单使用的 8 个趋势/收益字段，每日约 1.5008 元，首次含搜索约 2.1208 元。建议全量商品只抓当日趋势温度，重点品种继续抓丰富字段；当前无需用户每天提供温度截图。
- 自动化 `automation` 已加入知识星球情绪抓取、脱敏校验与股指板块展示要求；全量 62 品种温度抓取尚未启用，等待用户确认费用方案。

## 2026-07-17 Research Dashboard Long-Page Candidate

- 用户希望后续以网页和每日快照替代两份日报 HTML。当前先交付候选版，不停用机构专题与保证金日报自动化；两份日报仍作为结构化数据生产和对账层。
- `scripts/build_research_dashboard.py` 扩展快照模型，加入资金潮汐、趋势与资金共振、重点品种标记、三组席位贡献、股指趋势、知识星球 A 股情绪，并按报告日前最近可用文件回退行情和趋势，同时保留来源日期和非当日状态。
- `web/research_dashboard/index.html`、`app.js`、`styles.css` 重构为 9 段长图总览：三方强共振、资金潮汐、板块方向、趋势验证、核心品种、席位贡献、天气风险、股指与情绪、来源状态。全部品种深度、历史回看和数据状态保留为二级视图。
- 每次构建会写入 `output/research_dashboard/data/snapshots/YYYYMMDD.json`，再汇总最近 30 个快照到 `dashboard.json`。当前共固化 17 个交易日快照。
- 2026-07-17 快照包含 62 个商品、18 个三方强共振、4 个资金潮汐象限、4 条非平趋势验证、18 条天气风险、4 个股指和 14 条情绪样本。席位披露、东方财富行情和趋势快照均保留各自来源日期；行情和趋势最近可用日为 2026-07-16，未冒充 2026-07-17 当日事实。
- 浏览器验收：1440x900 无页面横向溢出、控制台无错误；390x844 无横向溢出，核心品种与趋势表在手机端改为纵向卡片。强共振、板块、核心品种均可点击进入详情；历史图包含金额纵轴、0 轴和日期标签。
- 后续迁移建议：用户确认网页覆盖后，再把报告脚本中的抓取/计算层抽为共享数据管线，并将每日自动化改为“抓取 -> 计算 CSV/JSON -> 写快照 -> 构建网页”；届时停用两份日报 HTML，而不是删除其计算逻辑。

## 2026-07-17 V2 Instrument Detail Integration

- 用户要求把 `output/research_dashboard_v2_mockup/index.html` 的交互概念加入当前研究工作站。主站新增“品种详情”一级视图和侧栏重点观察；强共振、板块、核心品种及重点观察点击后统一进入详情。
- 品种详情使用现有快照真实数据展示五段证据链、收盘价与三方资金历史图、三组存量净持仓与今日边际、净多/净空席位前五、趋势温度/右侧状态、农业天气事实和最近五个历史快照。
- 概念稿示意数字未迁入。库存、基差、仓单、利润、产量、消费和研报分歧尚无结构化来源时，页面明确显示数据缺口；天气事实与资金判断继续分列。
- 浏览器验收：1440x900 从强共振卡进入沪银详情、侧栏切换焦煤、子导航定位资金与席位、历史日期切换均通过；390x844 无页面横向溢出，控制台无错误。焦煤实际样本显示净多 5 家、净空 2 家，不补齐虚构席位。

## 2026-07-17 Silver Technical Trial And Private Deployment

- 新增 `scripts/fetch_eastmoney_technical_snapshot.py`，当前默认只分析沪银 `AG`。脚本读取当前主力合约日线，计算 MA5/10/20/60、5/20/60 日收益、RSI14、MACD、ATR14、布林带、20/60 日区间和量比；输出日快照 JSON 与历史 CSV。
- 东方财富连接中断时允许复用同报告日缓存历史，但必须用 `data/eastmoney_main_quotes_YYYYMMDD.csv` 的最终收盘行情校正最后一根 K 线。2026-07-17 沪银最终收盘 13,522、涨跌幅 -3.66%、RSI14 32.78、规则评分 -5/7，技术面判断为偏空。
- 工作站品种详情新增“技术面”子页，分开显示大周期方向、中周期结构、小周期触发、接口事实、规则判断和数据限制。当前主力合约历史不是复权连续合约；趋势温度旧值不作为当日技术确认。
- 本次没有可用的 Pandadata SDK 或凭据，因此未调用 `futures-deepview-analyst` 的 DeepView 数据；页面没有伪造该来源。
- 技术指标为本地确定性计算，日常抓取与渲染不消耗 LLM/API token。每品种新增约 1 至 2 KB 快照及一份短历史 CSV；扩大品种覆盖的主要成本是数据稳定性校验，而不是 token。
- 新增 `sites/research_dashboard/` 私有部署包装，将已验证的静态工作站同步到 `public/dashboard/`，不在云端重算资金逻辑。构建与两项服务端测试通过，版本已私有发布；浏览器显示登录保护页，需站点所有者登录后访问。

## 2026-07-19 Technical Three-Layer Upgrade

- 技术面三层改为“日线 MA5/20/60 + 15 分钟简化缠论 + 60 分钟简化缠论”，移除前台及新快照中的 MA10、收益率、RSI、MACD、ATR、布林带和区间高低字段。
- 新浪分钟 K 线的 `v`、`p` 分别作为成交量和持仓量；按报告日交易时段计算收盘持仓及日变化，用价格涨跌组合为增仓上涨、增仓下跌、减仓上涨、减仓下跌。增仓同向权重高于减仓同向，成交放大只调整量仓证据权重。
- 缠论口径为可复现的简化结构：处理 K 线包含关系，识别三根 K 线分型，相邻有效分型至少间隔 4 根处理后 K 线形成简化笔；最近高低点同升为偏多、同降为偏空，其余为中枢震荡。不据此声称严格背驰或一、二、三类买卖点。
- 支撑压力由现价上下最近的 MA5/20/60 和 15/60 分钟有效中枢边界共同筛选，并在页面标注来源。
- 修复周末或换月后运行时混用当前主力与报告日主力的问题：技术脚本优先读取 `eastmoney_main_quotes_YYYYMMDD.csv` 中的报告日合约；分钟数据截止报告日 20:00 前，排除下一交易日夜盘。
- 2026-07-17 沪银回归结果：报告日合约 `ag2608`，日线、15 分钟、60 分钟均偏空；成交量较前日增加 13.2%，持仓减少 9,263 手，为减仓下跌/多头撤退，综合偏空且强。分钟数据均截止 15:00。
- 验证：7 项单元测试、Python 编译、17 个工作站快照重建通过；Playwright 桌面与 390px 移动视口真实页面检查通过，控制台零错误。

## 2026-07-19 Detail Coverage And Filtering

- 工作站源码此前已更新，但用户浏览器仍停留在构建前的旧脚本实例；重新构建静态产物并重启本地服务后，新技术模块正常加载。后续验收以新会话和生成产物哈希为准，避免把浏览器旧缓存误判为源码未生效。
- 移除侧栏“重点观察”，保留历史快照；品种详情顶部新增品种/代码搜索和板块筛选，当前覆盖沪银 `AG`、焦煤 `JM`、燃料油 `FU`、生猪 `LH`、碳酸锂 `LC`、鸡蛋 `JD`。搜索支持“燃油”命中“燃料油”。
- 技术抓取从单一沪银扩展到上述 6 个品种。东方财富合约历史接口连接中断时，允许用新浪财经同一主力合约日线补足 MA5/20/60 历史，并用东方财富报告日主力行情校正最后一根收盘；每个品种独立降级，单一接口失败不再中断整批。
- 2026-07-17 六个品种均生成有效技术快照：沪银、焦煤、生猪三层偏空；燃料油日线震荡、15 分钟偏空、60 分钟偏多；碳酸锂日线偏空、15 分钟震荡、60 分钟偏空；鸡蛋日线震荡、15 分钟偏空、60 分钟偏多。页面仍把各层事实分开，不用综合标签覆盖分歧。
- 验证：9 项单元测试通过；实际页面搜索、板块筛选及沪银/焦煤/燃料油/生猪切换通过，旧 RSI/MACD 文案无残留；390x844 视口 `scrollWidth == clientWidth == 390`，控制台零错误。

## 2026-07-20 Beijing Time Standard

- 项目全部时间口径统一为北京时间 `Asia/Shanghai`，覆盖报告日、交易日、17:00 触发判断、数据来源日期、文件名、研究工作站快照和用户通知。
- 自动化收到 UTC `Z` 时间或其他时区输入时，必须先转换为北京时间再判断日期和休市状态；不得直接沿用 UTC 日期。
- `期货席位资金面日报` 自动化已同步该规则，原工作日 17:00 计划保持不变。

## 2026-07-20 Dashboard Data-Only Refresh

- 更正交易日判断：`2026-07-20` 为星期一。研究工作站已按北京时间生成并发布 7 月 20 日快照；此前按周日处理的判断无效。
- 两份数据脚本新增 `SKIP_REPORT_HTML=1`：继续抓取和生成工作站依赖的 CSV，但不构建或写入 `report.html`。默认未设置时行为不变，正式自动化仍生成两份日报。
- 7 月 20 日快照包含 63 个商品、19 个三方强共振、63 个当日行情匹配、6 个技术品种、4 个股指、19 条天气风险和 15 条社区情绪样本；席位披露日期为 2026-07-20。
- 趋势动物官方商品数据仍为 2026-07-17，因此 7 月 20 日付费快照被安全跳过，工作站趋势当日有效数为 0，不沿用旧趋势作为当日事实。
- 验证：两份 `report.html` 均未生成；保证金覆盖 63/63；商品列表无股指、国债、淀粉残留；站点包装构建及 2 项渲染测试通过，私有 Sites 版本已发布。

## 2026-07-23 Local Dashboard Delivery

- 用户将每日交付从两份日报 HTML 改为本地研究工作站静态网页。机构与保证金脚本继续设置 `SKIP_REPORT_HTML=1` 生成 CSV，日报 HTML 仅在用户明确要求时手动生成。
- 每日流程为：席位与天气数据、知识星球情绪、有效的趋势 API 或用户当日截图、东方财富主力行情、六个重点品种技术快照、研究工作站每日 JSON 快照与本地静态网页。
- Sites 暂不随每日数据更新；待用户统一确认页面结构后再部署。
- 2026-07-23 本地快照包含 63 个商品、14 个三方强共振、63 个当日行情、16 个截图趋势和 6 个技术品种；席位披露日为 2026-07-23。
- 当日截图趋势只转录明确可见的 16 个商品温度与强度，不使用截图行情替代东方财富收盘价，也不沿用截图未出现的前一日趋势。
- 本地服务地址为 `http://127.0.0.1:8788/`；快照接口返回 200，技术面 9 项单元测试通过。自动化提示词已同步为本地静态网页工作流，并保留原暂停状态。

## 2026-07-29 Five-Element Month Backtest

- 新增 `scripts/backtest_wuxing_month_seasonality.py`，使用新浪期货主力连续日线计算月末收益，并按固定地支月份五行映射检验品种属性同元素月份。
- 统计口径为点二列相关、5000 次置换检验和 Benjamini-Hochberg FDR；页面同时显示上涨、震荡、下跌概率，震荡阈值为月收益绝对值不超过 1%。
- 纳入 22 个属性歧义较低的金属、燃料/煤炭、橡胶木材、矿石建材和航运品种；农业与畜牧不强制贴五行标签。
- 2026-07-28 截止样本中没有品种同时通过样本数、`|r| >= 0.15` 与 `q <= 0.10` 门槛。工作站详情仍展示原始回测证据，但统一标记“未通过统计门槛”，不形成方向信号。
- 本地桌面与 375px 浏览器流程已验证：玻璃详情可进入“五行季节性”，7 月显示未月/土属性、概率与相关系数；无横向溢出、无控制台错误。

## 2026-07-30 Fundamental Source Matrix And Detail Filter

- 新增 `config/fundamental_sources.json`，为工作站 63 个商品逐一绑定供给、需求、现金成本和产业库存的首选来源、指标、频率、访问状态和入口；已授权数值、公开摘要、待授权和缺失状态不得混写。
- `scripts/fetch_research_dashboard_market_context.py` 的生意社期现基差与东方财富仓单映射扩展到全品种候选集。2026-07-28 快照实际覆盖 53 个基差、61 个仓单；基差缺 10 个、仓单当期无记录 2 个，均保留缺失而不填零。
- 品种详情顶部改为“品种下拉 + 可选搜索 + 板块筛选”，不再平铺全部品种按钮；63 个品种均可选择，板块与搜索条件会联动收窄下拉选项。
- 基本面证据板只把实际抓取的基差、仓单画成历史图；供给、需求、成本和产业库存尚无连续数值时，展示首选来源与授权状态，不从周报叙述反推数据。
- 新增 `docs/fundamental-data-source-audit.md` 和 4 项工作站基本面回归测试。18 项单元测试、JavaScript 语法检查、桌面与 375px 移动端真实页面检查均通过；页面无横向溢出，控制台无错误。

## 2026-07-30 Dashboard 20260729-30 Refresh

- “今日三方强共振”恢复保证金金额口径：三方净保证金金额为卡片主值、排序依据和进度条刻度，手数仅保留为辅助说明；分别展示前五净多与前五净空。
- `fetch_broker` 新增历史披露日期参数，机构脚本按 `REPORT_DATE` 请求奇货可查，并拒绝晚于报告日的披露。修复补历史快照时把最新持仓写入旧日期的问题。
- 2026-07-29 快照披露日为 2026-07-29，63 个商品、18 个三方强共振、保证金覆盖 63/63；2026-07-30 快照披露日为 2026-07-30，63 个商品、7 个三方强共振、保证金覆盖 63/63。
- 两日基本面自动数据均覆盖 53 个基差与 61 个仓单，63 个品种均保留基本面来源矩阵。东方财富主力日线均未匹配报告日精确 K 线，因此页面不显示旧行情；7 月 30 日趋势动物官方数据仅更新至 7 月 29 日，页面把趋势明确标记为非当日。

## 2026-07-30 Eastmoney Quote Recovery

- 定位到 7 月 28 日后行情缺失并非前端问题，而是东方财富历史 K 线接口在高并发下断开连接，旧脚本仍写出了全量错误状态。
- 当报告日等于北京时间当天时，行情脚本直接读取东方财富主力列表返回的主力合约价格与涨跌幅；历史报告日仍使用精确日期 K 线。网络请求改为低并发和退避重试，失败刷新不会覆盖同报告日已有的有效行。
- 2026-07-30 行情恢复为 87/87 个东方财富主力合约，工作站商品过滤后资金潮汐覆盖 63 个商品：资金流入上涨 19、流入下跌 20、流出上涨 8、流出下跌 16。
- 浏览器验证豆油详情与全景侧栏均显示收盘 8,407、涨跌幅 -0.18%；四个资金潮汐象限恢复品种明细，页面无横向溢出。

## 2026-08-10 Local Dashboard Refresh

- 技术详情收敛为日线与 60 分钟双周期，结合简化缠论、动量、EMA5/20/60、成交量和持仓量；趋势与技术在详情页同一行展示。六个技术品种均生成有效快照。
- 工作站支持读取已授权并落盘的 Mysteel 基本面事实 CSV；本次没有取得可验证的 Mysteel 数值文件，基本面仍只展示实际抓取的基差、仓单与来源缺口，不伪造授权数据。
- 2026-08-10 快照包含 64 个商品、20 个三方强共振、64 个当日行情、9 个当日趋势、53 个基差与 61 个仓单覆盖；席位披露日为 2026-08-10，保证金覆盖 64/64。
- 两份日报 HTML 均未生成，Sites 未部署。浏览器桌面与 390px 移动端验证通过，移动端无横向溢出。

## 2026-08-11 工作站决策闭环与席位重分组

- 研究工作站新增“决策与交易”页：对当日三方强共振信号人工选择接受、拒绝或观察，并用浏览器本地存储记录主要矛盾、触发、证伪、交易日志引用、未交易原因、退出结果及看对/做对/做好归因。
- 五日复盘日按工作站已固化交易日序列向后取第 5 个交易日；历史不足时明确显示待积累。
- 构建末尾新增 `output/research_dashboard/run-manifest.json`，记录北京时间构建标识、快照日期与最新来源文件，不包含账号或敏感信息。
- 席位分组调整：光大期货、招商期货、中信期货归入家人；中信期货前台显示“亏损机构（特殊）”。所有席位排名在名称后显示机构/外资/家人标签；今日方向位于净持仓右侧。
- 已按新分组重算 2026-08-10 两套 CSV 并重建静态工作站；强共振 13 个，保证金覆盖 64/64。
- 验证：`node --check web/research_dashboard/app.js`；9 项 dashboard 单测通过；真实浏览器完成信号确认、未交易原因校验、保存、删除及席位颜色检查，控制台无错误。

## 2026-08-11 当日工作站与决策筛选

- 重点品种新增铁矿石 `I`、棕榈油 `P`、天然橡胶 `RU`；趋势 API、兼容重点清单和工作站关注标记已同步。
- 决策页改为展示当日全品种，并提供板块与品种两级下拉筛选；人工决策编辑器新增当日净多/净空席位前五，净保证金额与涨跌幅并排。
- 席位快照保留加多、减多、加空、减空四类边际动作。席位排名统一显示主导动作：加多/减多为红色，加空/减空为绿色；旧快照缺少动作分拆时只显示中性的净变，不伪装成具体动作。
- 2026-08-11 快照包含 64 个商品、11 个三方强共振、64/64 保证金覆盖和 87/87 东方财富主力行情；六个技术品种均成功，趋势商品与指数目标解析 12/19，未解析项保留缺失状态。
- 两份日报 HTML 未生成，Sites 未部署。11 项单元测试通过；真实页面验证全品种决策筛选、铁矿石板块联动、席位前五与“加空绿/减多红”通过。

## 2026-08-11 行情占位符与席位边际口径修复

- 东方财富主力列表中的 `-` 不再视为有效行情；当日主力列表存在占位符时回退到报告日日线，工作站构建层也拒绝把占位符转换成零。
- 2026-08-11 工作站 64 个席位商品全部恢复收盘价与涨跌幅；东方财富全表仍有 5 个非工作站品种请求失败，保持缺失而不填零。
- 资金与席位矩阵明确分列存量净持仓、今日手数净变动与今日净金额。全量检查内资、外资、家人原始及家人反向的今日手数和净金额方向，未发现符号不一致。
- 席位边际动作统一按动作本身列示：加多/加空为正，减多/减空为负，并补充净多或净空扩大/收窄；净多、净空前五标题显示机构或家人哪一类存量手数占优。
- 验证：16 项单元测试与 JavaScript 语法检查通过；真实页面焦煤显示内资存量 `+90,696`、今日手数 `-17,322`、今日净金额 `-3.30 亿`，减多/减空均显示负号，桌面无横向溢出且控制台零错误。

## 2026-08-12 2026-08-11 行情与主力席位校准

- 修复当日东方财富主力列表夜盘实时值被误标为报告日收盘的问题。北京时间当日优先读取奇货可查商品概览的同日主连收盘与涨跌幅，历史日仍使用精确日线。
- 品种详情席位排名改用奇货可查当日主力合约全市场多空表，按席位合并多头、空头持仓与各自日变化，不再把样本席位全合约聚合结果冒充主力合约排名。
- 总览新增“关键商品事件”，展示奇货可查当日价格、持仓和成交额标签，过滤股指、国债与淀粉。
- 校验：工作站 64 个商品收盘价/涨跌幅与实时重读的奇货可查同日源零差异；焦煤为 `1,343.5 / +5.4967%`，净多前五 `15,803 / 11,096 / 10,805 / 6,333 / 5,991`，净空前五 `12,602 / 6,747 / 6,077 / 5,758 / 5,463`。16 项单元测试、真实页面流程与控制台检查通过。

## 2026-08-12 席位动作净额展示

- 净多、净空席位的多头与空头日变化先按 `多头变化 - 空头变化` 抵消，只显示一个净动作及净手数；动作标签取净方向中贡献最大的加多、减多、加空或减空。
- 纯碱页面实测：申银万国显示“减多 -1,071”，方正中期显示“减多 -2,901”，中信期货显示“减空 +24,011”；页面无双动作行，控制台无工作站错误。

## 2026-08-12 工作站审阅流程精简

- 品种全景右侧仅保留行情与资金摘要，移除重复的三组边际和席位前五；品种名称成为独立详情入口，点击同一行其他数据仍只切换当前品种。
- 历史回看把资金净变动与收盘价叠加展示并使用左右双轴；决策页默认每页展示当日前五净多与前五净空，其他品种通过分页查看。
- 品种详情移除五行月份回测；资金群体的边际动作按方向着色，减多或加空偏空为绿色，加多或减空偏多为红色。
- 验证：工作站相关单元测试、JavaScript 语法检查和真实浏览器流程通过；页面无横向溢出，控制台无错误。

## 2026-08-12 同花顺期货通行情校准

- 品种详情的收盘价、涨跌幅、资金流向和日增减仓支持读取同花顺期货通人工核验快照；仅按品种代码与当日主力合约精确匹配，禁止跨月份合约补位。
- 详情页头部以同花顺“资金流向”和“日增减仓”替代重复的三方资金摘要；席位与保证金板块继续保留三方资金研究口径。
- 2026-08-12 本地快照精确覆盖 10 个主力合约。焦煤 `JM2609` 校准为收盘 `1,337.5`、涨跌 `+2.06%`、资金流向 `-7.42 亿元`、日减仓 `36,972 手`，关键商品事件同步使用该行情事实。
- 验证：16 项单元测试与 JavaScript 语法检查通过；真实页面的焦煤详情和关键商品事件数值一致，页面无横向溢出，控制台无错误。

## 2026-08-12 曲合与新浪主力行情切换

- 工作站商品行情改为优先读取曲合期货同日主力数据，并用新浪财经同日精确合约日线与实时收盘校验；东方财富不再作为工作站当日收盘价和涨跌幅来源。
- 2026-08-12 共校验 64 个商品：52 个与新浪精确合约收盘一致，6 个标记为主力换月差异，6 个使用新浪同日精确合约补充；收盘价和涨跌幅缺失均为 0。
- 焦煤详情显示收盘 `1,337.5`、涨跌幅 `+2.06%`。行情抓取测试、16 项工作站测试与真实页面检查通过，控制台无错误。

## 2026-08-17 双日工作站更新与焦煤换月

- 新增 2026-08-14、2026-08-17 两个本地工作站快照；两日均覆盖 64 个商品，主力行情日期精确匹配且无缺失，未生成两份日报 HTML。
- 焦煤工作站主力统一切换为 `JM2701`。2026-08-14 收盘 `1,515.5`、涨跌 `+3.06%`；2026-08-17 收盘 `1,522.0`、涨跌 `+1.37%`。席位榜、日线和 60 分钟技术面均跟随 `JM2701`。
- 修复历史技术快照在东方财富返回空日线时不触发新浪回退的问题；8 月 14 日重点技术品种由 4/6 提升为 6/6。趋势动物在 8 月 17 日仍只更新至 8 月 14 日，因此未冒用旧温度。
- 验证：行情 64/64、保证金覆盖 64/64；8 月 14 日三方强共振 17 个，8 月 17 日 8 个。Playwright 验证日期切换、焦煤详情、双周期技术面、桌面/手机无横向溢出且控制台零错误。

## 2026-08-17 日报 HTML 退出日常工作流

- 用户确认后续只专注更新本地静态研究工作站；两份日报 HTML 不再属于日常任务或交付物。
- `generate_institutional_seat_report.py` 与 `generate_margin_weighted_seat_report.py` 默认只写结构化数据，只有显式设置 `WRITE_REPORT_HTML=1` 才会生成旧版 `report.html` 供手动诊断。
- 工作站构建链路、每日 JSON 快照、行情、席位、保证金与技术面数据生产保持不变。

## 2026-08-18 工作站更新

- 新增 2026-08-18 本地静态工作站快照：64/64 个商品行情日期精确匹配，保证金覆盖 64/64，三方强共振 10 个，趋势目标解析 12/19。
- 焦煤继续使用 `JM2701`，收盘 `1,546.5`、涨跌 `+1.61%`；六个重点品种技术快照均为有效状态。
- 修复曲合通用主力代码覆盖具体合约、导致技术快照请求失败的问题；通用代码只用于行情校正，不再覆盖含交割年月的技术合约。
- 未生成两份日报 HTML，未部署 Sites。11 项技术单测通过；真实页面验证日期、焦煤详情、收盘价、技术板及桌面无横向溢出通过。

## 2026-08-19 工作站更新

- 新增 2026-08-19 本地工作站快照。65/65 个品种行情与同花顺截图资金流、日增减仓匹配；焦煤继续使用 `JM2701`，收盘 `1,586.5`、涨跌 `+3.46%`、日增仓 `51,695` 手、资金流入 `14.36` 亿元。
- 恢复 `qhkch_main_position_rows_20260819.csv` 全量抓取，并改用席位源自身的精确主力合约过滤排名。除奇货可查当日把多空持仓均发布为 0 的粳米 `RR` 外，其余 64 个品种均生成前五净多与前五净空。
- 同花顺截图只有一个明确合约时，可覆盖曲合的通用主连代码；具体月份不一致仍只允许用户截图来源覆盖，避免普通自动源跨月串值。
- 29 项相关单元测试、JavaScript 语法检查和真实浏览器验收通过；日期、焦煤行情、资金流、日增仓、前五席位、横向溢出与控制台均正常。未生成日报 HTML，未部署 Sites。

## 2026-08-20 工作站更新

- 新增 2026-08-20 本地工作站快照：65/65 个商品行情日期精确匹配，保证金覆盖 65/65，三方强共振 13 个；未生成日报 HTML，未部署 Sites。
- 焦煤继续使用 `JM2701`，收盘 `1,591.5`、涨跌 `+1.34%`；六个重点品种技术快照均有效。趋势动物官方数据仍停在 2026-08-19，因此 2026-08-20 趋势字段明确降级，不沿用旧温度。
- 奇货可查全量主力席位共 1,704 行；除源站多空存量均为零的粳米 `RR` 外，其余 64 个品种均生成前五净多与前五净空。当天没有同花顺人工快照，资金流向和日增减仓保持缺失，不沿用 2026-08-19 数据。
- 29 项相关单元测试、JavaScript 语法检查和真实浏览器验收通过；页面日期、焦煤合约与收盘价、前五席位、横向溢出和控制台均正常。
## 2026-08-20 Left-Side Reversal Evidence Chain

- `docs/trading-system.md` 新增空头趋势下的左侧反转观察：利空不跌、趋势转盘整、拥挤度反转、资金开始转多、事件催化。
- 执行区分继续观察、左侧小仓试错和右侧确认加仓；事件催化不能替代价格与资金证据，并明确结构、资金、催化和时间失效条件。
- `docs/trading-decision-checklist.md` 将该证据链并入原“技术触发”一问，没有增加清单长度。

## 2026-08-20 工作站品种准入调整

- 自下一次工作站更新起，铝合金 `AD`、丙烯 `PL`、粳米 `RR`、棉纱 `CY`、双胶纸 `OP`、油菜籽 `RS` 固定排除；只有用户以后明确要求时才恢复。
- 多晶硅 `PS`、纸浆 `SP` 归入“家人品种”，工作站不再设置“其他商品”分类。
- 本次只修改准入和分类规则及回归测试，未重新抓取数据、生成快照或部署网页。

## 2026-08-21 工作站更新与补数循环修复

- 新增 2026-08-21 本地工作站快照：按准入规则保留 59 个商品，行情、同花顺资金流与日增减仓均为 59/59；奇货可查主力席位底表共 1,747 行、65 个源站品种，工作站内 59/59 均有前五净多与前五净空。未生成日报 HTML，未部署 Sites。
- 焦煤为 `JM2701`，收盘 `1,581.5`、涨跌 `-0.13%`、资金流出 `5.43` 亿元、日减仓 `20,711` 手；六个重点品种技术快照全部有效。
- 修复历史补数分支只在“报告日等于北京时间今天”时抓取奇货可查概览与主力席位的问题。现在先尝试读取源站仍保留的报告日精确截面，日期不匹配才回退精确日线；回归测试确认次日补前一交易日仍会写入席位 CSV。
- CTA Demo 接入 AU、AG、JM、LH、LC 的 OpenVLab 截图期权截面。偏度分位形成方向因子，IV 分位仅作拥挤风险证据；未提供期权截面的品种不扣分。贵金属不再参与板块最强/最弱标签。
- 原任务审计确认 3 小时内发生 57 次 `ContextLimit` 压缩，且没有文件变更事件；压缩后的历史与技能元数据仍再次超限，使模型在每次成功工具调用后重启同一盘点。写入—读取探针证明文件权限正常。项目规则新增：连续两次出现该模式即转入干净任务，以一页内状态继续并先完成最小写盘闭环。
- 验证：43 项 Python 单元测试、JavaScript 语法、快照结构断言及真实浏览器流程通过；工作站与 CTA 在 1440px/390px 均无横向溢出，筛选与详情交互正常，控制台零错误。

## 2026-08-24 工作站与 CTA 合并更新

- 新增 2026-08-24 本地工作站快照：59 个商品行情与保证金全部同日有效，奇货可查席位底表 4,245 行，三方强共振 18 个；6 个重点品种技术快照有效，基差与仓单已更新到报告日。
- 同花顺截图底表覆盖工作站 58/59 个商品及 `IH/IF/IC/IM`，保留 10/20/30 日涨幅、日增减仓和资金流；截图未出现的甲醇只使用同日自动行情，不补旧截图资金流。OpenVLab 截面覆盖 55 个商品和 4 个股指映射，截图统一标记为二级证据。
- CTA 评分写入每个工作站快照并新增主导航视图，共 63 个标的；`IH/IF/IC/IM` 归入独立“股指”板块，不参与商品共振。截图 10/20 日涨幅优先用于量价因子，缺失时才回退工作站历史；缺失因子按可用权重重算。
- 修正股指 CTA 席位存量金额：按各组多头持仓金额减空头持仓金额计算，不能读取不存在的净持仓金额列。45 项 Python 单元测试、JavaScript 语法和真实浏览器流程通过；CTA 股指筛选在 1440×900 与 390×844 均无页面级横向溢出，控制台零错误。

## 2026-08-25 至 2026-08-26 工作站更新

- 新增 2026-08-25、2026-08-26 两个本地工作站快照；两日均保留 59 个商品、行情 59/59 同日有效、保证金覆盖 59/59，CTA 均为 63 个标的并包含 `IH/IF/IC/IM` 四个股指。未生成旧日报 HTML，未部署 Sites。
- 8 月 25 日席位底表 4,512 行，三方强共振 12 个、内外资同向 13 个；源站商品概览已切到 8 月 26 日，因此当日全市场主力合约排名底表保持为空，不用 26 日数据回填。重点技术面仅沪银 1/6 有效，现货指数日线为空，均保留来源缺失。
- 8 月 26 日席位底表 4,332 行，三方强共振 7 个、内外资同向 15 个；奇货可查当日主力席位 1,710 行、64 个源站品种，六个现货指数行情有效。用户补充截图后，同花顺截面覆盖 59 个商品和 4 个股指，OpenVLab 期权截面覆盖 55 个商品和 4 个股指（缺 `HC/J/LU/SS`）；重点技术面仅鸡蛋 1/6 有效，其余接口返回 HTTP 错误后停止重复请求。
- 45 项 Python 单元测试、JavaScript 语法和真实 HTTP 页面验收通过；日期选择可切换 8 月 25/26 日，CTA 样本显示 63 个且含股指 4 个，1280px 与 390px 均无页面级横向溢出，控制台零错误。本地服务地址为 `http://127.0.0.1:8788/`。

## 2026-08-27 本地常驻与私有发布

- 确认本地页面隔日失效的原因是临时 `http.server` 进程退出，静态产物本身未过期；Windows 计划任务 `FuturesResearchDashboardLocal` 已设置为登录后启动并在失败后重启，继续提供 `http://127.0.0.1:8788/`。
- 研究工作站 Sites 版本 8 已私有发布到 `https://futures-research-workstation.myfpanda.chatgpt.site`，访问策略保持仅所有者，不公开、不共享。
- 交易日 17:00 自动化恢复：先发布可自动获取的当日基线；期货通与 OpenVLab Legend 截图缺失时明确标记待补充且不沿用旧值，用户补发对应交易日截图后再补录、重建并覆盖私有发布同日快照。
- 8 月 27 日快照已完成：席位底表 4,389 行，59 个商品、CTA 63 个标的（含 `IH/IF/IC/IM`），同花顺截图与 OpenVLab 截图均按当日证据落盘；45 项 Python 测试、JavaScript 语法、Sites 构建测试和本地 HTTP 200 验证通过。
- “决策与交易记录”按 A4 交易员日志简化为单页日复盘：默认只保留人工确认、交易状态、核心逻辑、入场触发、失效/止损、结果、问题主因、最大错误和下一次唯一规则；席位证据默认折叠，旧记录字段继续兼容但不再占用表单空间。桌面端与 375px 移动端保存、刷新读回均已验证。

## 2026-08-28 金银四维 CTA 门槛

- 沪金、沪银 CTA 详情新增金银四维框架：黄金动量与投机情绪、DXY 与黄金、工业 PMI 领先、实际利率。四维全部确认、白银 20 日相对黄金转强且白银席位边际与期权偏度同向时，才提示“可考虑 Call 白银”；任一维冲突则提示“暂不 Call 白银”，缺失数据保持“继续观察”。
- 2026-08-27 白银相对黄金 20 日超额为 `+6.3%`，但黄金投机/期权信号冲突、DXY 与黄金同跌、10Y TIPS 上行，仅工业 PMI 维度确认，因此当前为“暂不 Call 白银”。ETF、CFTC 与 DXY 5 日相关性暂无报告日精确结构化源，未伪造补入。
- 私有 Sites 版本 9 已发布，访问策略仍为仅所有者；46 项 Python 测试、Sites 构建测试、本地桌面端与 375px 页面验收、线上静态资源与数据读取均通过。

## 2026-08-28 工作站数据更新与私有发布

- 新增 2026-08-28 工作站快照：席位底表 4,347 行，59 个商品、CTA 63 个标的（含 `IH/IF/IC/IM`），同花顺行情 59/59 同日有效，三方强共振 14 个。
- OpenVLab 截图期权截面覆盖 58 个 CTA 标的；焦炭 `J`、热卷 `HC`、短纤 `PF`、不锈钢 `SS`、低硫燃油 `LU` 保持缺失并按可用权重重算，不沿用旧值、不按中性扣分。趋势动物官方商品数据仍停在 2026-08-27，8 月 28 日趋势字段明确标记缺失；重点技术面 5/6 有效。
- 金银四维框架显示白银相对黄金 20 日超额 `+8.2%`，仅“黄金动量 × 投机情绪”确认，DXY、工业 PMI 领先与实际利率三维缺少当日精确数据，因此保持“数据不足，继续观察”，不触发 Call 白银。
- 46 项 Python 测试、JavaScript 语法、Sites 构建测试、本地 HTTP 200、桌面端与 375px CTA 页面验收均通过；私有 Sites 版本 10 已发布，线上快照核验为 20260828、59 个商品、63 个 CTA，访问策略仍为仅所有者。

## 2026-08-31 工作站数据更新与私有发布

- 新增 2026-08-31 工作站快照：席位底表 4,315 行，59 个商品、CTA 63 个标的（含 `IH/IF/IC/IM`），同花顺截图底表 63/63 同日有效，保证金覆盖 59/59，三方强共振 9 个。
- OpenVLab 截图期权截面覆盖 58 个 CTA 标的；焦炭 `J`、热卷 `HC`、低硫燃油 `LU`、不锈钢 `SS`、中证500 `IC` 保持缺失并按可用权重重算，不沿用旧值、不按中性扣分。趋势动物解析 12/19 个查询，其中工作站同日趋势 11/59；重点技术面 6/6 有效。
- 金银四维框架显示白银相对黄金 20 日超额 `+6.1%`，但黄金动量与投机情绪冲突，DXY、工业 PMI 领先与实际利率缺少报告日精确数据，白银席位边际也未与期权偏度形成同向确认，因此保持“暂不 Call 白银”。
- 最近三个交易日中，`AL/BC/I/M/P/PK/PP/SF/TA` 各有两日进入三方强共振，暂无连续三日重复品种。
- 46 项 Python 测试、JavaScript 语法、Sites 构建测试、本地 HTTP 200、桌面端与 375×812 CTA/金银框架验收均通过；私有 Sites 版本 11 已发布，线上快照核验为 20260831、59 个商品、63 个 CTA，访问策略仍为仅所有者。

## 2026-08-31 发布节奏调整

- 自 2026-08-31 起，用户主动要求更新期货数据时只生成并验证本地 HTTP 工作站，不自动同步或发布 Sites。
- 原交易日自动任务已替换为每周六 12:00 的部署提醒；提醒本身不执行发布，只有用户明确确认后才把最新本地版本部署到仅所有者可访问的线上地址。

## 2026-09-01 当日席位证据完整性闸门

- 复核发现 2026-08-31 缺少全市场主力席位文件，构建器静默退回样本席位底表，导致 59 个商品中有 53 个同时缺少净多与净空前五，但旧流程仍完成构建。
- 自 2026-09-01 起，`build_research_dashboard.py` 只对目标报告日执行硬校验：必须存在同日全市场席位行，且每个商品同时具有净多与净空席位；任一缺失即在写入快照前失败并列出品种。历史缺口保持原样，不用后日席位伪造回填。
- 新增单元测试覆盖“源品种缺失、净多缺失、净空缺失”和完整通过路径。

## 2026-09-01 席位来源顺序

- 用户指定主力席位优先使用奇货可查的品种结构页；仅在同日同合约的净多或净空证据缺失时，才改查交易可查的持仓结构页。
- 交易可查当前未登录访问会提示“查看持仓结构请先登录”，未返回席位表；因此没有可读取登录态时不作为自动回退成功，质量闸门仍会失败并列出缺失品种，避免伪造或混用证据。

## 2026-09-01 远端同步前置规则

- 用户会在其他电脑修改同一工作站并推送 GitHub；此后每次数据或结构更新都必须先在干净工作树执行 `git fetch origin main`、`git pull --rebase origin main`，以最新 `origin/main` 为唯一修改基线。
- 工作树不干净时，Git 会拒绝 rebase；先单独提交并推送相关变更，临时文件保持未跟踪，不用 stash、覆盖或混入数据版本。

## 数据更新状态

- 已更新至：2026-09-04
