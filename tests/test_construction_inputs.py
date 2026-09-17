import gzip
import json
import os
import unittest
from unittest import mock
from pathlib import Path

from scripts import construction_inputs as ci
from scripts.common import ChainedBaseNotFound, ValidationError

FIXTURES = Path(__file__).parent / "fixtures"


class ConstructionInputsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with gzip.open(FIXTURES / "cbs_construction_snapshot_2026-09-16.json.gz", "rt", encoding="utf-8") as f:
            cls.payload = json.load(f)
        cls.rows = ci.extract_rows(cls.payload)
        cls.records = ci.build_records(cls.rows)

    def test_full_snapshot_invariants(self):
        self.assertEqual(len(self.records), 848)
        self.assertEqual(len({r["month"] for r in self.records}), 848)
        ci.validate(self.records, 848)
        first = self.records[0]
        self.assertEqual(first, {"month": "1956-01", "year": 1956, "month_num": 1,
            "value": 427.2, "base_desc": "1950 יולי", "chained_1950_07": 427.2})
        known = {r["month"]: r["chained_1950_07"] for r in self.records}
        self.assertEqual(known["1956-02"], 427.4)
        self.assertEqual(known["2000-01"], 44820240.6462416)
        self.assertEqual(known["2026-08"], 97714812.5562859)
        for record in self.records:
            self.assertIsInstance(record["value"], float)
            self.assertGreater(record["value"], 0)
            self.assertTrue(record["base_desc"])
            self.assertIsInstance(record["chained_1950_07"], float)
            self.assertGreater(record["chained_1950_07"], 0)

    def test_anchor_lookup_is_direct(self):
        latest = next(r for r in self.rows if r["year"] == 2026 and r["month"] == 8)
        anchor = next(p for p in latest["prevBase"] if p["baseDesc"] == ci.ANCHOR)
        result = ci.resolve_chained(latest)
        self.assertEqual(result, anchor["value"])
        self.assertNotEqual(result, latest["currBase"]["value"] * anchor["coeff"])
        anchor_rows = [r for r in self.rows if r["currBase"]["baseDesc"] == ci.ANCHOR]
        self.assertEqual(len(anchor_rows), 97)
        self.assertTrue(all(not r["prevBase"] for r in anchor_rows))
        self.assertTrue(all(ci.resolve_chained(r) == r["currBase"]["value"] for r in anchor_rows))

    def test_missing_and_normalized_anchor(self):
        row = json.loads((FIXTURES / "cbs_construction_missing_anchor.json").read_text())
        with self.assertRaises(ChainedBaseNotFound):
            ci.resolve_chained(row)
        row["prevBase"].append({"baseDesc": " 1950  יולי ", "value": 123})
        self.assertEqual(ci.resolve_chained(row), 123.0)

    def test_export_starts_at_2000_01(self):
        exported = ci.export_records(self.records)
        self.assertEqual(len(exported), 320)
        self.assertLess(len(exported), len(self.records))
        self.assertEqual(exported[0]["month"], "2000-01")
        self.assertTrue(all(r["month"] >= "2000-01" for r in exported))
        months = [r["month"] for r in exported]
        self.assertEqual(months, sorted(set(months)))
        ci.validate_export(exported)

    def test_full_history_validation_runs_before_the_export_filter(self):
        exported = ci.export_records(self.records)
        # The filtered export is intentionally shorter than the CBS-reported total for
        # the FULL history, so running the full-history validator against it must fail —
        # this proves validation happens before filtering, not after.
        with self.assertRaises(ValidationError):
            ci.validate(exported, len(self.records))

    def test_non_shrink(self):
        exported = ci.export_records(self.records)
        with self.assertRaisesRegex(ValidationError, "shrink"):
            ci.validate_export(exported, {"count": len(exported) + 1})
        with mock.patch.dict(os.environ, {"STATSO_ALLOW_SHRINK": "1"}):
            ci.validate_export(exported, {"count": len(exported) + 1})
        with self.assertRaises(ValidationError):
            ci.validate_export(exported[:-1], {"count": len(exported)})


if __name__ == "__main__":
    unittest.main()
