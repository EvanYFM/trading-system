import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from build_cta_factor_demo import option_factor


class OptionFactorTests(unittest.TestCase):
    def test_skew_percentile_sets_direction_without_penalizing_missing_rows(self):
        self.assertAlmostEqual(0.72, option_factor({"skew_percentile": "86", "implied_vol": "47.97", "realized_vol": "40.60", "skew": "2.89", "iv_percentile": "53"})[0])
        self.assertAlmostEqual(-0.96, option_factor({"skew_percentile": "2", "implied_vol": "40.49", "realized_vol": "34.25", "skew": "-0.65", "iv_percentile": "64"})[0])
        self.assertIsNone(option_factor(None)[0])


if __name__ == "__main__":
    unittest.main()
