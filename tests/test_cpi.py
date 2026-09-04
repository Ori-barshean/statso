import gzip
import json
import os
import unittest
from unittest import mock
from pathlib import Path

from scripts import cpi
from scripts.common import ChainedBaseNotFound, ValidationError

FIXTURES = Path(__file__).parent / "fixtures"


class CpiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with gzip.open(FIXTURES / "cbs_cpi_snapshot_2026-09-05.json.gz", "rt", encoding="utf-8") as f:
            cls.payload = json.load(f)
        cls.rows = cpi.extract_rows(cls.payload)
        cls.records = cpi.build_records(cls.rows)

    def test_full_snapshot_invariants(self):
        self.assertEqual(len(self.records), 899)
        self.assertEqual(len({r["month"] for r in self.records}), 899)
        cpi.validate(self.records, 899)
        first = self.records[0]
        self.assertEqual(first, {"month": "1951-09", "year": 1951, "month_num": 9,
            "value": 100.0, "base_desc": "1951 ספטמבר", "chained_1951_09": 100.0})
        known = {r["month"]: r["chained_1951_09"] for r in self.records}
        self.assertEqual(known["1951-10"], 103.0)
        self.assertEqual(known["1994-01"], 16033750.0800922)
        self.assertEqual(known["2026-07"], 40691566.5993423)
        for record in self.records:
            self.assertIsInstance(record["value"], float)
            self.assertGreater(record["value"], 0)
            self.assertTrue(record["base_desc"])
            self.assertIsInstance(record["chained_1951_09"], float)
            self.assertGreater(record["chained_1951_09"], 0)

    def test_anchor_lookup_is_direct(self):
        latest = next(r for r in self.rows if r["year"] == 2026 and r["month"] == 7)
        anchor = next(p for p in latest["prevBase"] if p["baseDesc"] == cpi.ANCHOR)
        result = cpi.resolve_chained(latest)
        self.assertEqual(result, anchor["value"])
        self.assertNotEqual(result, latest["currBase"]["value"] * anchor["coeff"])
        anchor_rows = [r for r in self.rows if r["currBase"]["baseDesc"] == cpi.ANCHOR]
        self.assertEqual(len(anchor_rows), 89)
        self.assertTrue(all(not r["prevBase"] for r in anchor_rows))
        self.assertTrue(all(cpi.resolve_chained(r) == r["currBase"]["value"] for r in anchor_rows))

    def test_missing_and_normalized_anchor(self):
        row = json.loads((FIXTURES / "cbs_cpi_missing_anchor.json").read_text())
        with self.assertRaises(ChainedBaseNotFound):
            cpi.resolve_chained(row)
        row["prevBase"].append({"baseDesc": " 1951  ספטמבר ", "value": 123})
        self.assertEqual(cpi.resolve_chained(row), 123.0)

    def test_non_shrink(self):
        # Must reach the shrink branch itself, not trip an earlier gate: pass the
        # full, otherwise-valid dataset and claim the published file held more.
        with self.assertRaisesRegex(ValidationError, "shrink"):
            cpi.validate(self.records, len(self.records), {"count": len(self.records) + 1})
        # And the documented escape hatch must actually disarm it.
        with mock.patch.dict(os.environ, {"STATSO_ALLOW_SHRINK": "1"}):
            cpi.validate(self.records, len(self.records), {"count": len(self.records) + 1})
        # A genuinely short dataset still fails, via the minimum-count gate.
        with self.assertRaises(ValidationError):
            cpi.validate(self.records[:-1], 898, {"count": 899})


if __name__ == "__main__":
    unittest.main()
