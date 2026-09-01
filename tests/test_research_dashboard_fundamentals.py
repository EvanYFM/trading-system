import ast
import json
import pathlib
import unittest
from unittest import mock

from scripts import fetch_research_dashboard_market_context as market_context
from scripts import generate_futures_report as futures_report
from scripts import build_research_dashboard as dashboard


ROOT = pathlib.Path(__file__).resolve().parents[1]


class ResearchDashboardFundamentalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads(
            (ROOT / "config" / "fundamental_sources.json").read_text(encoding="utf-8")
        )

    def test_every_dashboard_symbol_has_a_source_profile(self):
        self.assertEqual(
            set(market_context.INVENTORY_CODES),
            set(self.config["symbols"]),
        )

    def test_every_source_profile_declares_four_fundamental_layers(self):
        required = {"supply", "demand", "cost", "inventory"}
        for symbol, profile_name in self.config["symbols"].items():
            with self.subTest(symbol=symbol):
                profile = self.config["profiles"][profile_name]
                self.assertEqual(required, set(profile))
                for layer in required:
                    self.assertTrue(profile[layer]["source"])
                    self.assertTrue(profile[layer]["metric"])
                    self.assertTrue(profile[layer]["frequency"])
                    self.assertTrue(profile[layer]["access"])
                    self.assertTrue(profile[layer]["url"])

    def test_detail_page_uses_dropdown_instead_of_product_card_grid(self):
        html = (ROOT / "web" / "research_dashboard" / "index.html").read_text(
            encoding="utf-8"
        )
        self.assertIn('id="detailSymbolFilter"', html)
        self.assertIn('id="detailSearchInput"', html)
        self.assertIn('id="detailSectorFilter"', html)
        self.assertNotIn('id="detailFilterResults"', html)

    def test_quote_index_rejects_placeholder_prices(self):
        rows = [{
            "symbol": "JM",
            "status": "OK",
            "source_date": "2026-08-11",
            "close": "-",
            "change_pct": "-",
        }]
        self.assertEqual({}, dashboard.quote_index(rows, "20260811"))

    def test_ths_market_snapshot_requires_exact_main_contract(self):
        rows = [{
            "symbol": "JM", "contract": "jm2609", "status": "OK", "source_date": "2026-08-12",
            "close": "1337.5", "change_pct": "2.06", "capital_flow": "-742000000",
            "open_interest_change": "-36972",
        }, {
            "symbol": "JM", "contract": "jm2701", "status": "OK", "source_date": "2026-08-12",
            "close": "1476", "change_pct": "2.22", "capital_flow": "254000000",
            "open_interest_change": "10399",
        }]
        markets = dashboard.ths_market_index(rows, "20260812")
        exact = markets[("JM", dashboard.normalize_contract("jm2609"))]
        self.assertEqual(1337.5, exact["quote"]["close"])
        self.assertEqual(-742000000, exact["marketFlow"]["capitalFlow"])
        self.assertEqual(-36972, exact["marketFlow"]["openInterestChange"])
        self.assertEqual({}, dashboard.ths_market_index([{**rows[0], "source_date": "2026-08-11"}], "20260812"))

    def test_ths_market_snapshot_allows_unique_contract_for_generic_main_code(self):
        rows = [{
            "symbol": "JM", "contract": "jm2701", "status": "OK", "source_date": "2026-08-19",
            "close": "1586.5", "change_pct": "3.46", "capital_flow": "1436000000",
        }]
        markets = dashboard.ths_market_index(rows, "20260819")
        selected = dashboard.select_ths_market(markets, "JM", "jmm")
        self.assertEqual(1586.5, selected["quote"]["close"])
        self.assertIsNone(dashboard.select_ths_market(markets, "JM", "jm2609"))

    def test_user_screenshot_can_replace_stale_specific_contract(self):
        rows = [{
            "symbol": "AL", "contract": "al2610", "status": "OK", "source_date": "2026-08-19",
            "close": "23675", "change_pct": "-1.07", "source": "同花顺期货通截图",
        }]
        markets = dashboard.ths_market_index(rows, "20260819")
        selected = dashboard.select_ths_market(markets, "AL", "al2609")
        self.assertEqual("al2610", selected["quote"]["contract"])

    def test_stock_index_cta_stock_amount_uses_long_minus_short(self):
        rows = [{
            "symbol": "IH", "variety": "上证50", "signal_dir": "偏多",
            "domestic_long_pos_amount": "100", "domestic_short_pos_amount": "40",
            "foreign_long_pos_amount": "30", "foreign_short_pos_amount": "10",
            "family_long_pos_amount": "80", "family_short_pos_amount": "20",
            "domestic_amount_score": "5", "foreign_amount_score": "3", "family_amount_score": "-2",
        }]

        item = dashboard.build_stock_rows(rows, {}, {}, {})[0]

        self.assertEqual({"机构": 60, "外资": 20, "家人反向": -60}, item["stockComponents"])
        self.assertEqual({"机构": 5, "外资": 3, "家人反向": 2}, item["flowComponents"])

    def test_detail_header_uses_ths_market_flow_not_three_party_money(self):
        app = (ROOT / "web" / "research_dashboard" / "app.js").read_text(encoding="utf-8")
        self.assertIn("<small>资金流向</small>", app)
        self.assertIn('openInterestChange >= 0 ? "日增仓" : "日减仓"', app)

    def test_key_events_accept_exact_ths_market_override(self):
        build = (ROOT / "scripts" / "build_research_dashboard.py").read_text(encoding="utf-8")
        self.assertIn('"priceChangePct": quote.get("changePct", event.get("priceChangePct"))', build)
        self.assertIn('"openInterestChangePct": market_flow.get("openInterestChangePct"', build)

    def test_resonance_focus_uses_margin_amount_as_primary_metric(self):
        html = (ROOT / "web" / "research_dashboard" / "index.html").read_text(
            encoding="utf-8"
        )
        app = (ROOT / "web" / "research_dashboard" / "app.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("按三方净保证金金额列示前五多与前五空", html)
        self.assertIn(
            "numeric(b.amountSignal) - numeric(a.amountSignal)", app
        )
        self.assertIn(
            "numeric(a.amountSignal) - numeric(b.amountSignal)", app
        )
        self.assertIn(
            '${formatAmount(item.amountSignal)}</div>', app
        )
        self.assertIn(
            "三方手数 ${formatHands(item.handsSignal)} 手", app
        )

    def test_broker_fetch_passes_requested_disclosure_date(self):
        html = '<th colspan="6">2026-07-29 国泰君安 持仓列表</th>'
        with mock.patch.object(futures_report, "fetch_url", return_value=html):
            date, url, rows = futures_report.fetch_broker(
                "国泰君安", "2026-07-29"
            )
        self.assertEqual("2026-07-29", date)
        self.assertIn("date=2026-07-29", url)
        self.assertEqual([], rows)

    def test_basis_mapping_keeps_corn_and_bottle_flakes(self):
        self.assertEqual("C", market_context.BASIS_NAMES["玉米"])
        self.assertEqual("PR", market_context.BASIS_NAMES["瓶片"])

    def test_mysteel_facts_require_numeric_ok_rows_and_respect_report_date(self):
        rows = [
            {
                "symbol": "JM",
                "dimension": "inventory",
                "metric": "样本矿山精煤库存",
                "value": "195.84",
                "unit": "万吨",
                "source_date": "2026-08-07",
                "frequency": "周度",
                "status": "OK",
                "source": "Mysteel",
                "source_url": "https://www.mysteel.com/example",
            },
            {
                "symbol": "JM",
                "dimension": "cost",
                "metric": "现金成本",
                "value": "",
                "unit": "元/吨",
                "source_date": "2026-08-07",
                "frequency": "月度",
                "status": "NO_ACCESS",
                "source": "Mysteel",
                "source_url": "https://www.mysteel.com/example",
            },
            {
                "symbol": "JM",
                "dimension": "inventory",
                "metric": "样本矿山精煤库存",
                "value": "999",
                "unit": "万吨",
                "source_date": "2026-08-08",
                "frequency": "周度",
                "status": "OK",
                "source": "Mysteel",
                "source_url": "https://www.mysteel.com/example",
            },
        ]

        result = dashboard.fundamental_fact_index(rows, "20260807")

        self.assertEqual(1, len(result["JM"]))
        self.assertEqual(195.84, result["JM"][0]["value"])
        self.assertEqual("inventory", result["JM"][0]["dimension"])

    def test_special_brokers_are_family_and_labeled_for_display(self):
        for name in ("generate_institutional_seat_report.py", "generate_margin_weighted_seat_report.py"):
            tree = ast.parse((ROOT / "scripts" / name).read_text(encoding="utf-8"))
            values = {
                node.targets[0].id: ast.literal_eval(node.value)
                for node in tree.body
                if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id in {"DOMESTIC_BROKERS", "FAMILY_BROKERS"}
            }
            self.assertNotIn("中信期货", values["DOMESTIC_BROKERS"])
            self.assertNotIn("光大期货", values["DOMESTIC_BROKERS"])
            self.assertTrue({"大地期货", "宝城期货"} <= set(values["DOMESTIC_BROKERS"]))
            self.assertTrue({"中信期货", "光大期货", "招商期货"} <= set(values["FAMILY_BROKERS"]))
        self.assertEqual("亏损机构（特殊）", dashboard.broker_display_group("中信期货", "家人"))
        self.assertEqual("家人", dashboard.broker_display_group("光大期货", "家人"))

    def test_decision_workflow_and_manifest_are_wired(self):
        html = (ROOT / "web" / "research_dashboard" / "index.html").read_text(encoding="utf-8")
        app = (ROOT / "web" / "research_dashboard" / "app.js").read_text(encoding="utf-8")
        build = (ROOT / "scripts" / "build_research_dashboard.py").read_text(encoding="utf-8")
        self.assertIn('id="view-decisions"', html)
        self.assertIn("futuresResearchDecisions.v1", app)
        self.assertIn("数据 / 证据", app)
        self.assertIn('option("judgment","判断"', app)
        self.assertIn('option("execution","执行"', app)
        self.assertIn('TARGET_DIR / "run-manifest.json"', build)

    def test_decision_filters_watchlist_and_seat_actions_are_wired(self):
        html = (ROOT / "web" / "research_dashboard" / "index.html").read_text(encoding="utf-8")
        app = (ROOT / "web" / "research_dashboard" / "app.js").read_text(encoding="utf-8")
        self.assertTrue({"I", "P", "RU"} <= dashboard.WATCHLIST_SYMBOLS)
        self.assertIn('id="decisionSectorFilter"', html)
        self.assertIn('id="decisionSymbolFilter"', html)
        self.assertIn("const netChange = longChange - shortChange", app)
        self.assertIn('[["加多", Math.max(longChange, 0)], ["减空", Math.max(-shortChange, 0)]]', app)
        self.assertIn('[["减多", Math.max(-longChange, 0)], ["加空", Math.max(shortChange, 0)]]', app)
        self.assertIn("function rankingDominance(items)", app)
        self.assertIn("function seatChanges(entry)", app)

    def test_dashboard_review_changes_are_wired(self):
        app = (ROOT / "web" / "research_dashboard" / "app.js").read_text(encoding="utf-8")
        self.assertIn("function orderDecisionSignals(items)", app)
        self.assertIn("data-decision-page", app)
        self.assertIn("data-open-detail-symbol", app)
        self.assertIn("历史资金净变动与收盘价曲线", app)
        self.assertIn("series.map((entry) => entry.close)", app)
        self.assertIn("最大错误与下一条规则", app)
        self.assertIn("查看当日席位证据", app)
        self.assertNotIn('name="seeRight"', app)
        self.assertNotIn('name="doRight"', app)
        self.assertNotIn('name="doWell"', app)
        self.assertIn('seeRight: "pending"', app)
        self.assertIn("signClass(numeric(group.longChange) - numeric(group.shortChange))", app)
        self.assertNotIn("detail-wuxing", app)
        self.assertNotIn("三组存量与今日边际", app)
        self.assertNotIn("样本席位净持仓前五", app)

    def test_workstation_universe_excludes_retired_symbols_and_has_no_other_sector(self):
        self.assertTrue({"AD", "PL", "RR", "CY", "OP", "RS"} <= dashboard.EXCLUDED_SYMBOLS)
        self.assertEqual("家人品种", dashboard.SECTOR_OVERRIDES["PS"])
        self.assertEqual("家人品种", dashboard.SECTOR_OVERRIDES["SP"])
        self.assertNotIn("其他商品", dashboard.ANALYSIS_SECTORS)
        self.assertTrue({"PS", "SP"} <= futures_report.FAMILY_SECTOR_SYMBOLS)
        self.assertNotIn("其他商品", futures_report.SECTOR_ORDER)

    def test_broker_rankings_keep_action_components(self):
        rankings = dashboard.build_broker_rankings([{
            "symbol": "I", "contract": "i2609", "broker": "国泰君安", "group": "内资",
            "long_pos": "10", "long_chg": "-2", "short_pos": "30", "short_chg": "12", "net_pos": "-20", "flow_score": "-14",
            "add_long": "0", "reduce_long": "2", "add_short": "12", "reduce_short": "0",
        }, {
            "symbol": "I", "contract": "i2701", "broker": "国泰君安", "group": "内资",
            "long_pos": "100", "long_chg": "20", "short_pos": "0", "short_chg": "0", "net_pos": "100", "flow_score": "20",
            "add_long": "20", "reduce_long": "0", "add_short": "0", "reduce_short": "0",
        }], {"I": "i2609"})
        entry = rankings["I"]["netShort"][0]
        self.assertEqual(-20, entry["netPosition"])
        self.assertEqual(-2, entry["longChange"])
        self.assertEqual(12, entry["shortChange"])
        self.assertEqual(12, entry["addShort"])
        self.assertEqual(2, entry["reduceLong"])

    def test_seat_evidence_validation_requires_both_sides_for_every_symbol(self):
        snapshot = {"instruments": [{
            "symbol": "JM",
            "brokerRanking": {"netLong": [{"broker": "甲"}], "netShort": []},
        }, {
            "symbol": "I",
            "brokerRanking": {"netLong": [], "netShort": [{"broker": "乙"}]},
        }]}
        rows = [{"symbol": "JM", "contract": "jm2701", "broker": "甲"}]

        with self.assertRaises(RuntimeError) as error:
            dashboard.validate_seat_evidence(snapshot, rows, "20260831")
        self.assertIn("source rows missing: I", str(error.exception))
        self.assertIn("net-long seats missing: I", str(error.exception))
        self.assertIn("net-short seats missing: JM", str(error.exception))

        snapshot["instruments"][0]["brokerRanking"]["netShort"] = [{"broker": "丙"}]
        snapshot["instruments"][1]["brokerRanking"]["netLong"] = [{"broker": "丁"}]
        rows.append({"symbol": "I", "contract": "i2701", "broker": "丁"})
        dashboard.validate_seat_evidence(snapshot, rows, "20260831")


if __name__ == "__main__":
    unittest.main()
