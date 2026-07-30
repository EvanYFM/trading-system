import json
import pathlib
import unittest
from unittest import mock

from scripts import fetch_research_dashboard_market_context as market_context
from scripts import generate_futures_report as futures_report


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


if __name__ == "__main__":
    unittest.main()
