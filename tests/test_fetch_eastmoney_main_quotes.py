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
                writer = csv.DictWriter(handle, fieldnames=["symbol", "status", "close", "source_date"])
                writer.writeheader()
                writer.writerow({"symbol": "AG", "status": "OK", "close": "14381", "source_date": "2026-07-30"})

            rows = [{"symbol": "AG", "status": "ERROR:RemoteDisconnected", "source_date": ""}]
            merged = quotes.merge_existing_ok_rows(path, rows)

            self.assertEqual(merged[0]["status"], "OK")
            self.assertEqual(merged[0]["close"], "14381")

    def test_main_list_quote_uses_report_date_and_visible_fields(self):
        row = quotes.quote_from_main_list(
            {
                "symbol": "AG",
                "contract": "AG2610",
                "main_list_close": 14420,
                "main_list_change_pct": 4.9,
            },
            "20260730",
        )

        self.assertEqual(row["status"], "OK")
        self.assertEqual(row["source_date"], "2026-07-30")
        self.assertEqual(row["close"], 14420)
        self.assertEqual(row["change_pct"], 4.9)


if __name__ == "__main__":
    unittest.main()
