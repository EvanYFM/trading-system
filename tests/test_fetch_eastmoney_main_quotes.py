import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import fetch_eastmoney_main_quotes as quotes


class EastmoneyQuoteFetchTests(unittest.TestCase):
    def test_get_json_retries_transient_disconnect(self):
        response = unittest.mock.MagicMock()
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        response.read.return_value = b'{"data": {"klines": []}}'

        with (
            patch.object(quotes, "urlopen", side_effect=[quotes.http.client.RemoteDisconnected(), response]),
            patch.object(quotes.time, "sleep"),
            patch.object(quotes.random, "uniform", return_value=0),
        ):
            self.assertEqual(quotes.get_json("https://example.test", {}), {"data": {"klines": []}})

    def test_merge_existing_ok_row_replaces_failed_refresh(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "quotes.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["symbol", "status", "close", "change_pct", "source_date"])
                writer.writeheader()
                writer.writerow({"symbol": "AG", "status": "OK", "close": "14381", "change_pct": "4.8", "source_date": "2026-07-30"})

            rows = [{"symbol": "AG", "status": "ERROR:RemoteDisconnected", "source_date": ""}]
            merged = quotes.merge_existing_ok_rows(path, rows)

            self.assertEqual(merged[0]["status"], "OK")
            self.assertEqual(merged[0]["close"], "14381")

    def test_qhkch_report_date_quote_is_not_replaced_by_night_session_realtime(self):
        page = '''
        <div id="variety-key-events"><tr><td>焦煤</td><td><span>价涨仓增</span></td><td>+5.50%</td><td>+5.90%</td><td>948.21亿</td><td>煤炭</td></tr></div>
        <div id="variety-sector-temperature"></div>
        <script>let varietyMarketRows = [{"variety":"焦煤","symbol":"jm","close_price":1343.5,"previous_close_price":1273.5,"price_change_rate":5.4967,"open_interest_change_rate":5.8958,"turnover":94820910300,"data_date":"2026-08-11","data_complete":true}];</script>
        '''
        market, events = quotes.parse_qhkch_overview(page, "20260811")
        row = quotes.quote_from_qhkch({"symbol": "JM", "contract": "jm2609"}, market["JM"])

        self.assertEqual(1343.5, row["close"])
        self.assertEqual(5.4967, row["change_pct"])
        self.assertEqual("2026-08-11", row["source_date"])
        self.assertEqual("JM", events[0]["symbol"])

    def test_qhkch_position_page_combines_long_and_short_tables(self):
        page = '''
        <option value="jm2609" selected>焦煤2609</option>
        <tr id="variety_position_buy_tr_0"><td class="sort-broker"><a href="?broker=%E5%9B%BD%E6%B3%B0%E5%90%9B%E5%AE%89&x=1">国泰君安</a></td><td class="sort-buy">43,877</td><td class="sort-buy_chge">+2,385</td><td class="sort-net_position">多 15,803</td></tr>
        <tr id="variety_position_ss_tr_0"><td class="sort-broker"><a href="?broker=%E5%9B%BD%E6%B3%B0%E5%90%9B%E5%AE%89&x=1">国泰君安</a></td><td class="sort-ss">28,074</td><td class="sort-ss_chge">-96</td><td class="sort-net_position">多 15,803</td></tr>
        '''
        row = quotes.parse_qhkch_position_page(page, "JM")[0]

        self.assertEqual("jm2609", row["contract"])
        self.assertEqual(15803, row["net_pos"])
        self.assertEqual(2385, row["long_chg"])
        self.assertEqual(-96, row["short_chg"])

    def test_previous_day_still_uses_exact_qhkch_snapshot(self):
        page = '''
        <div id="variety-key-events"></div><div id="variety-sector-temperature"></div>
        <script>let varietyMarketRows = [{"variety":"焦煤","symbol":"jm","close_price":1581.5,"previous_close_price":1583.5,"price_change_rate":-0.13,"data_date":"2026-08-21","data_complete":true,"url":"/jm"}];</script>
        '''
        position = {"symbol": "JM", "contract": "jm2701", "broker": "国泰君安"}
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch.dict(quotes.os.environ, {"REPORT_DATE": "20260821"}),
                patch.object(quotes, "ROOT", Path(directory)),
                patch.object(quotes, "fetch_main_contracts", return_value=[{"symbol": "JM", "variety": "焦煤", "contract": "jm2701", "market": 114}]),
                patch.object(quotes, "get_text", return_value=page),
                patch.object(quotes, "fetch_qhkch_position_rows", return_value=[position]),
                patch.object(quotes, "fetch_daily_quote") as daily_quote,
            ):
                quotes.main()

                daily_quote.assert_not_called()
                with (Path(directory) / "data" / "qhkch_main_position_rows_20260821.csv").open("r", encoding="utf-8-sig", newline="") as handle:
                    self.assertEqual("jm2701", next(csv.DictReader(handle))["contract"])


if __name__ == "__main__":
    unittest.main()
