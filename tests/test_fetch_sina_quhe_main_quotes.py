import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from fetch_sina_quhe_main_quotes import quhe_catalog, report_contract


class QuheCatalogTests(unittest.TestCase):
    def test_extracts_named_quote_code(self):
        html = '<dd><a title="焦煤">焦煤</a><em class="JO_165990_q63 q63_val">--</em></dd>'
        self.assertEqual(quhe_catalog(html), {"焦煤": "JO_165990"})

    def test_overrides_coking_coal_contract(self):
        self.assertEqual(report_contract("JM", "jm2609"), "JM2701")
        self.assertEqual(report_contract("AG", "ag2610"), "ag2610")


if __name__ == "__main__":
    unittest.main()
