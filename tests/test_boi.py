import gzip
import os
import unittest
from unittest import mock
from pathlib import Path

from scripts import boi_rate
from scripts.common import ParseError, ValidationError

FIXTURES = Path(__file__).parent / "fixtures"


class BoiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with gzip.open(FIXTURES / "boi_snapshot_2026-09-05.csv.gz", "rb") as f:
            cls.raw = f.read()
        cls.observations = boi_rate.parse_observations(cls.raw)
        cls.changes = boi_rate.derive_change_points(cls.observations)

    def test_full_snapshot(self):
        self.assertEqual(len(self.observations), 11909)
        self.assertEqual(len(self.changes), 159)
        self.assertEqual(self.changes[0], {"date": "1994-01-27", "rate": 10.5})
        self.assertEqual(self.changes[-1], {"date": "2026-09-03", "rate": 3.25})
        self.assertEqual(self.changes[-1]["rate"], self.observations[-1][1])
        self.assertNotIn("1994-01-28", {item["date"] for item in self.changes})
        self.assertEqual(min(d for d, _ in self.observations), "1994-01-27")
        self.assertEqual([c["date"] for c in self.changes], sorted({c["date"] for c in self.changes}))
        boi_rate.validate(self.changes, self.observations)

    def test_small_filter_and_empty(self):
        raw = (FIXTURES / "boi_small_changes.csv").read_bytes()
        observations = boi_rate.parse_observations(raw)
        self.assertEqual(boi_rate.derive_change_points(observations), [
            {"date": "1994-01-27", "rate": 1.0}, {"date": "1994-01-29", "rate": 2.0},
            {"date": "1994-02-01", "rate": 1.0}])
        self.assertEqual(boi_rate.parse_observations(b"\xef\xbb\xbf" + raw), observations)

    def test_bad_header(self):
        with self.assertRaises(ParseError):
            boi_rate.parse_observations(b"SERIES_CODE,TIME_PERIOD\nMNT_RIB_BOI_D,2020-01-01\n")

    def test_bad_first_date(self):
        observations = [("1994-02-01", 10.5)] * boi_rate.MIN_OBSERVATIONS
        with self.assertRaises(ValidationError):
            boi_rate.validate([{"date": "1994-02-01", "rate": 10.5}], observations)

    def test_non_shrink(self):
        # Reach the shrink branch itself rather than an earlier gate.
        with self.assertRaisesRegex(ValidationError, "shrink"):
            boi_rate.validate(self.changes, self.observations,
                              {"count": len(self.changes) + 1})
        with mock.patch.dict(os.environ, {"STATSO_ALLOW_SHRINK": "1"}):
            boi_rate.validate(self.changes, self.observations,
                              {"count": len(self.changes) + 1})
