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


if __name__ == "__main__":
    unittest.main()
