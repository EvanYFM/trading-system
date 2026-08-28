import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from build_cta_factor_demo import build_rows, option_factor


class OptionFactorTests(unittest.TestCase):
    def test_skew_percentile_sets_direction_without_penalizing_missing_rows(self):
        self.assertAlmostEqual(0.72, option_factor({"skew_percentile": "86", "implied_vol": "47.97", "realized_vol": "40.60", "skew": "2.89", "iv_percentile": "53"})[0])
        self.assertAlmostEqual(-0.96, option_factor({"skew_percentile": "2", "implied_vol": "40.49", "realized_vol": "34.25", "skew": "-0.65", "iv_percentile": "64"})[0])
        self.assertIsNone(option_factor(None)[0])

    def test_stock_index_uses_screenshot_trend_and_stays_in_its_own_sector(self):
        snapshots = [{
            "date": "20260824",
            "instruments": [],
            "stockIndices": [{
                "symbol": "IH",
                "variety": "上证50",
                "quote": {"close": 2851.0, "changePct": -0.38},
                "marketFlow": {"return10d": -2.90, "return20d": -2.46},
                "stockComponents": {"机构": 3e8, "外资": 1e8, "家人反向": -2e8},
                "flowComponents": {"机构": 2e7, "外资": -1e7, "家人反向": 3e7},
                "hasFuturesFlow": True,
            }],
        }]
        rows = build_rows(snapshots, {}, {
            "IH": {"skew_percentile": "14", "implied_vol": "14.93", "realized_vol": "12.19", "skew": "-0.29", "iv_percentile": "27"},
        })

        self.assertEqual("股指", rows[0]["sector"])
        self.assertEqual("10日 -2.9% / 20日 -2.5%（同花顺截图）", rows[0]["evidence"]["trend"])
        self.assertEqual(-72, rows[0]["factors"]["option"])

    def test_precious_metals_4d_requires_macro_relative_strength_and_silver_flow(self):
        def item(symbol, variety, return20d, change_pct, hands):
            return {
                "symbol": symbol,
                "variety": variety,
                "sector": "贵金属" if symbol in {"AU", "AG"} else "有色金属",
                "quote": {"close": 100, "changePct": change_pct},
                "marketFlow": {"return10d": return20d / 2, "return20d": return20d},
                "margin": {"perLot": 1},
                "groups": {"domestic": {"netPosition": hands, "hands": hands}},
                "resonance": {},
                "fundamentals": {},
            }

        snapshots = [{"date": "20260828", "instruments": [
            item("AU", "沪金", 10, 1.0, 50),
            item("AG", "沪银", 18, 1.5, 100),
            item("CU", "沪铜", 5, 0.5, 20),
        ], "stockIndices": []}]
        option_rows = {
            symbol: {"skew_percentile": "70", "implied_vol": "30", "realized_vol": "25", "skew": "1", "iv_percentile": "50"}
            for symbol in ("AU", "AG")
        }
        macro = {
            "asOf": "2026-08-28T17:00:00+08:00",
            "indicators": [{"id": "tips10", "value": 2.30, "previous": 2.40, "dataDate": "2026-08-27"}],
            "markets": [{"id": "dxy", "pctChange": -0.2}],
            "growth": [{"id": "ismMfg", "displayValue": "55.0"}],
        }

        rows = build_rows(snapshots, {}, option_rows, macro)
        framework = next(row for row in rows if row["symbol"] == "AG")["metal4d"]
        self.assertTrue(framework["callSilver"])
        self.assertEqual("可考虑 Call 白银", framework["signal"])
        self.assertEqual(8.0, framework["relative20d"])
        self.assertEqual(["确认"] * 4, [item["status"] for item in framework["dimensions"]])


if __name__ == "__main__":
    unittest.main()
