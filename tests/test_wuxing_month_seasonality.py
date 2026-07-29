import unittest

from scripts.backtest_wuxing_month_seasonality import (
    MONTH_CALENDAR,
    benjamini_hochberg,
    monthly_returns,
    pearson_binary,
    probability_summary,
)


class WuxingMonthSeasonalityTests(unittest.TestCase):
    def test_earthly_branch_month_elements(self):
        self.assertEqual(MONTH_CALENDAR[1], ("丑", "土"))
        self.assertEqual(MONTH_CALENDAR[8], ("申", "金"))
        self.assertEqual(MONTH_CALENDAR[12], ("子", "水"))

    def test_monthly_returns_use_last_close_in_each_month(self):
        rows = [
            {"d": "2025-01-02", "c": "100"},
            {"d": "2025-01-31", "c": "110"},
            {"d": "2025-02-28", "c": "121"},
            {"d": "2025-03-31", "c": "108.9"},
        ]
        result = monthly_returns(rows, "2025-03-31")
        self.assertEqual(len(result), 2)
        self.assertAlmostEqual(result[0]["return"], 0.10)
        self.assertAlmostEqual(result[1]["return"], -0.10)

    def test_binary_correlation_detects_direction(self):
        correlation = pearson_binary([1, 1, 0, 0], [0.10, 0.08, -0.02, -0.04])
        self.assertGreater(correlation, 0.9)

    def test_probability_summary_respects_flat_band(self):
        summary = probability_summary([0.02, -0.03, 0.005, -0.005])
        self.assertEqual(summary["sampleCount"], 4)
        self.assertEqual(summary["upProbability"], 0.25)
        self.assertEqual(summary["downProbability"], 0.25)
        self.assertEqual(summary["flatProbability"], 0.50)

    def test_benjamini_hochberg_is_monotone(self):
        adjusted = benjamini_hochberg({"A": 0.01, "B": 0.04, "C": 0.20})
        self.assertAlmostEqual(adjusted["A"], 0.03)
        self.assertAlmostEqual(adjusted["B"], 0.06)
        self.assertAlmostEqual(adjusted["C"], 0.20)


if __name__ == "__main__":
    unittest.main()
