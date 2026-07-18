import sys
import unittest
from datetime import datetime
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from fetch_eastmoney_technical_snapshot import (  # noqa: E402
    build_strokes,
    build_key_levels,
    classify_chan,
    classify_daily_ma,
    classify_position_price,
    combine_technical_bias,
    recent_central_zone,
    session_activity,
)


def point(index, kind, price):
    return {"index": index, "kind": kind, "price": price, "timestamp": datetime(2026, 7, 17, 9, index)}


class TechnicalSnapshotTests(unittest.TestCase):
    def test_daily_ma_states(self):
        self.assertEqual(classify_daily_ma(120, 115, 110, 100), "偏多")
        self.assertEqual(classify_daily_ma(80, 85, 90, 100), "偏空")
        self.assertEqual(classify_daily_ma(105, 100, 110, 90), "中枢震荡")

    def test_chan_direction_states(self):
        bullish = [point(1, "bottom", 90), point(5, "top", 100), point(9, "bottom", 95), point(13, "top", 110)]
        bearish = [point(1, "top", 110), point(5, "bottom", 100), point(9, "top", 105), point(13, "bottom", 90)]
        oscillating = [point(1, "bottom", 90), point(5, "top", 110), point(9, "bottom", 95), point(13, "top", 105)]
        self.assertEqual(classify_chan(bullish), "偏多")
        self.assertEqual(classify_chan(bearish), "偏空")
        self.assertEqual(classify_chan(oscillating), "中枢震荡")

    def test_strokes_and_central_zone(self):
        raw = [point(1, "bottom", 90), point(3, "top", 100), point(6, "top", 105), point(10, "bottom", 95), point(14, "top", 110)]
        strokes = build_strokes(raw)
        self.assertEqual([item["price"] for item in strokes], [90, 105, 95, 110])
        self.assertEqual(recent_central_zone(strokes), {"lower": 95.0, "upper": 105.0})

    def test_position_price_patterns(self):
        self.assertEqual(classify_position_price(1.2, 300), {"label": "增仓上涨", "impulse": "多头推动"})
        self.assertEqual(classify_position_price(-1.2, 300), {"label": "增仓下跌", "impulse": "空头推动"})
        self.assertEqual(classify_position_price(1.2, -300), {"label": "减仓上涨", "impulse": "空头回补"})
        self.assertEqual(classify_position_price(-1.2, -300), {"label": "减仓下跌", "impulse": "多头撤退"})

    def test_key_levels_use_ma_and_central_zones(self):
        levels = build_key_levels(
            100,
            {"MA5": 98, "MA20": 103, "MA60": 95},
            [{"period": 15, "centralZone": {"lower": 99, "upper": 102}}],
        )
        self.assertEqual(levels["supports"][0]["label"], "15分钟中枢下沿")
        self.assertEqual(levels["resistances"][0]["label"], "15分钟中枢上沿")

    def test_combined_bias_weights_open_interest_impulse(self):
        strong_short = combine_technical_bias("偏空", "偏空", "偏空", "空头推动", 1.3)
        covering_rally = combine_technical_bias("中枢震荡", "偏多", "中枢震荡", "空头回补", 0.7)
        self.assertEqual(strong_short["bias"], "偏空")
        self.assertEqual(strong_short["strength"], "强")
        self.assertEqual(covering_rally["bias"], "中枢震荡")

    def test_session_activity_includes_previous_night_and_excludes_next_night(self):
        bars = [
            {"timestamp": datetime(2026, 7, 16, 14, 45), "volume": 10, "openInterest": 100},
            {"timestamp": datetime(2026, 7, 16, 21, 0), "volume": 20, "openInterest": 102},
            {"timestamp": datetime(2026, 7, 17, 9, 0), "volume": 30, "openInterest": 105},
            {"timestamp": datetime(2026, 7, 17, 15, 0), "volume": 40, "openInterest": 108},
        ]
        activity = session_activity(bars, "20260717")
        self.assertEqual(activity["volume"], 90)
        self.assertEqual(activity["openInterestChange"], 8)


if __name__ == "__main__":
    unittest.main()
