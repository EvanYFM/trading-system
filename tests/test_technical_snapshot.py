import sys
import unittest
from datetime import datetime
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from fetch_eastmoney_technical_snapshot import (  # noqa: E402
    DEFAULT_SYMBOLS,
    build_strokes,
    build_key_levels,
    classify_chan,
    classify_ema_stack,
    classify_position_price,
    combine_timeframe_observation,
    ema,
    momentum_pct,
    parse_sina_daily_payload,
    recent_central_zone,
    session_activity,
)


def point(index, kind, price):
    return {"index": index, "kind": kind, "price": price, "timestamp": datetime(2026, 7, 17, 9, index)}


class TechnicalSnapshotTests(unittest.TestCase):
    def test_default_coverage_symbols(self):
        self.assertEqual(DEFAULT_SYMBOLS, ("AG", "JM", "FU", "LH", "LC", "JD"))

    def test_sina_daily_history_is_cut_off_and_calculates_change(self):
        payload = 'x=([{"d":"2026-07-16","o":"100","h":"105","l":"99","c":"102","v":"8"},{"d":"2026-07-17","o":"102","h":"106","l":"101","c":"104","v":"9"},{"d":"2026-07-20","o":"104","h":"108","l":"103","c":"107","v":"10"}]);'
        rows = parse_sina_daily_payload(payload, "20260717")
        self.assertEqual(len(rows), 2)
        self.assertAlmostEqual(rows[-1]["change_pct"], 1.960784, places=5)

    def test_ema_and_stack_states(self):
        self.assertAlmostEqual(ema([1, 2, 3, 4, 5], 3), 4.0625)
        self.assertEqual(classify_ema_stack(120, 115, 110, 100), "偏多")
        self.assertEqual(classify_ema_stack(80, 85, 90, 100), "偏空")
        self.assertEqual(classify_ema_stack(105, 100, 110, 90), "中枢震荡")

    def test_momentum_uses_lookback_return(self):
        self.assertAlmostEqual(momentum_pct([100, 101, 102, 103, 110], 4), 10.0)
        self.assertIsNone(momentum_pct([100, 101], 5))

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
            {"EMA5": 98, "EMA20": 103, "EMA60": 95},
            [{"label": "60分钟", "centralZone": {"lower": 99, "upper": 102}}],
        )
        self.assertEqual(levels["supports"][0]["label"], "60分钟中枢下沿")
        self.assertEqual(levels["resistances"][0]["label"], "60分钟中枢上沿")

    def test_timeframe_observation_combines_chan_ema_and_momentum(self):
        strong_short = combine_timeframe_observation("偏空", "偏空", -2.0, -4.0, "空头推动", 1.3)
        mixed = combine_timeframe_observation("偏多", "偏空", 1.0, -1.0, "空头回补", 0.7)
        self.assertEqual(strong_short["state"], "偏空")
        self.assertEqual(strong_short["strength"], "强")
        self.assertEqual(mixed["state"], "中枢震荡")

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
