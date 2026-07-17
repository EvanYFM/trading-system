# 趋势动物 API 接入

## 作用范围

`scripts/fetch_trend_animal_snapshot.py` 为保证金金额口径日报补充 10 个重点商品的趋势快照：燃油、苯乙烯、碳酸锂、豆粕、鸡蛋、焦煤、沪金、沪银、欧线集运、生猪；同时按需定位上证 50、沪深 300、中证 500、中证 1000、科创 50、创业板 50 指数。它不会替代奇货可查席位数据，也不会自动生成交易指令。

## 安全与调用流程

1. 仅从当前进程的 `TREND_ANIMAL_API_KEY` 读取密钥；不得写入仓库、HTML、日志或状态文件。
2. 每次运行先调用 `getApiDocIntro`、`getChangeLog`、`getUpdateStatus`、`getSnapshotColumnBilling`。
3. 仅当“商品期货”的 `asOfDate` 等于 `REPORT_DATE` 时，才抓取重点商品；指数在 `searchTicker` 定位后还要检查对应资产的数据日，只有数据日等于 `REPORT_DATE` 才进入快照。
4. 根据实时字段计费计算预估费用，但费用不再阻断每日快照。调用后通过 `getAccountBalance?viewLevel=ledger` 汇总报告日实际消费；默认 `TREND_ANIMAL_DAILY_COST_ALERT=1.00`，仅在当日实际消费超过该值时输出提醒。余额、账单明细与实际消费金额不写入项目文件或 HTML。
5. 快照字段为趋势温度、温度前值、右侧状态、右侧天数、当前趋势阶段、局部趋势强度及变化、日收益原值；字段清单和价格不在脚本中写死，以每次 `getSnapshotColumnBilling` 返回为准。

运行：

```powershell
$env:TREND_ANIMAL_API_KEY="<secure-session-key>"
$env:REPORT_DATE="YYYYMMDD"
python scripts/fetch_trend_animal_snapshot.py
python scripts/generate_margin_weighted_seat_report.py
```

## 数据流与产物

- `data/trend_temperature_YYYYMMDD.csv`：趋势动物 API 的当日直接事实。
- `data/trend_animal_fetch_status_YYYYMMDD.json`：数据日期、请求字段、预估费用、解析数量与未匹配品种；不包含密钥、请求 URL 或余额。
- `output/margin_weighted_seat_report_YYYYMMDD/data/trend_temperature_used.csv`：保证金报告实际使用的趋势文件副本。

CSV 中以 `report_scope` 区分重点商品与股指。保证金报告的“趋势温度与资金共振”模块将商品 API 事实与三方净金额并列；独立股指模块将指数趋势温度、日收益原值与 `IH/IF/IC/IM` 三方净金额并列。科创 50、创业板 50 没有席位持仓时只展示趋势事实，不伪造资金流。温度与右侧状态是接口事实；“资金顺势/逆势/未验证”是按用户规则作出的分析判断。

## 解释边界

`温/凉`作为左侧预警、`热/寒`作为右侧确认、`沸/冻`作为极端警戒，是用户采用的趋势温度规则。趋势动物官方文档未提供温度算法、趋势阶段枚举，或 `return1d` 的序列化单位，因此报告对这些未定义单位的字段保留 API 原值，不自行换算。

趋势动物 API 提供的趋势指标仅用于趋势交易研究与纪律执行参考，不构成投资建议或收益承诺。
