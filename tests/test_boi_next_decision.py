import gzip
import json
import tempfile
import unittest
from pathlib import Path

from scripts import boi_next_decision, boi_rate, cpi, update_all
from scripts.common import ParseError, SourceError

FIXTURES = Path(__file__).parent / "fixtures"
LIVE = b'{"currentInterest":3.25,"nextInterestDate":"2026-10-21T00:00:00Z","lastPublishedDate":"2026-09-01T16:00:04.647Z"}'
KEYS = {"dataset", "source", "source_url", "content", "current_interest",
        "next_interest_date", "next_decision_date", "last_published_date"}


class BoiNextDecisionTests(unittest.TestCase):
    def test_parse_live_shape(self):
        record = boi_next_decision.build_record(LIVE)
        self.assertEqual(set(record), KEYS)
        self.assertEqual(record["current_interest"], 3.25)
        self.assertEqual(record["next_interest_date"], "2026-10-21T00:00:00Z")
        self.assertEqual(record["next_decision_date"], "2026-10-21")

    def test_next_date_unavailable_variants(self):
        for value in (None, "", "soon", "2026-13-45T00:00:00Z", 12345):
            payload = {"currentInterest": 3.25, "nextInterestDate": value}
            record = boi_next_decision.build_record(json.dumps(payload).encode())
            self.assertIsNone(record["next_decision_date"])
            self.assertNotIn(b"2026-10-21", boi_next_decision.to_json_bytes(record))
        record = boi_next_decision.build_record(b'{"currentInterest":3.25}')
        self.assertIsNone(record["next_decision_date"])
        self.assertIsNone(record["next_interest_date"])

    def test_non_json_raises(self):
        with self.assertRaises(ParseError):
            boi_next_decision.parse_payload(b"<html>404</html>")

    def test_no_timestamp_key(self):
        self.assertEqual(set(boi_next_decision.build_record(LIVE)), KEYS)

    def test_bytes_deterministic_and_encoding(self):
        record = boi_next_decision.build_record(LIVE)
        first = boi_next_decision.to_json_bytes(record)
        self.assertEqual(first, boi_next_decision.to_json_bytes(record))
        self.assertFalse(first.startswith(b"\xef\xbb\xbf"))
        self.assertTrue(first.endswith(b"\n")); self.assertFalse(first.endswith(b"\n\n"))
        self.assertIn("בנק ישראל".encode(), first)

    def fixture_fetch(self, fail_next=False):
        cpi_raw = gzip.open(FIXTURES / "cbs_cpi_snapshot_2026-09-05.json.gz", "rb").read()
        boi_raw = gzip.open(FIXTURES / "boi_snapshot_2026-09-05.csv.gz", "rb").read()
        def fetch(url):
            if url == boi_next_decision.BOI_NEXT_URL:
                if fail_next: raise SourceError("blocked")
                return LIVE
            if url == boi_rate.BOI_URL: return boi_raw
            if url == cpi.page_url(1): return cpi_raw
            raise AssertionError(url)
        return fetch

    def test_update_all_writes_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "data"
            self.assertEqual(len(update_all.update(fetch=self.fixture_fetch(), data_dir=target)), 5)
            self.assertEqual(update_all.update(fetch=self.fixture_fetch(), data_dir=target), [])

    def test_update_all_soft_fails_on_next_decision(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "data"; target.mkdir()
            stale = b"stale\n"; (target / "boi_next_decision.json").write_bytes(stale)
            changed = update_all.update(fetch=self.fixture_fetch(True), data_dir=target)
            self.assertEqual(len(changed), 4)
            self.assertEqual((target / "boi_next_decision.json").read_bytes(), stale)


if __name__ == "__main__": unittest.main()
