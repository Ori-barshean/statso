import codecs
import csv
import gzip
import io
import json
import os
import re
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from scripts import boi_rate, cpi, update_all
from scripts.common import SourceError, ValidationError, fmt_number, write_atomic

FIXTURES = Path(__file__).parent / "fixtures"


class SerializationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with gzip.open(FIXTURES / "cbs_cpi_snapshot_2026-09-05.json.gz", "rt", encoding="utf-8") as f:
            payload = json.load(f)
        cls.cpi_records = cpi.build_records(cpi.extract_rows(payload))
        with gzip.open(FIXTURES / "boi_snapshot_2026-09-05.csv.gz", "rb") as f:
            observations = boi_rate.parse_observations(f.read())
        cls.changes = boi_rate.derive_change_points(observations)

    def test_encoding_and_numbers(self):
        json_bytes = cpi.to_json_bytes(self.cpi_records)
        self.assertTrue(json_bytes.startswith(b"{"))
        self.assertIn("1951 ספטמבר".encode(), json_bytes)
        json.loads(json_bytes)
        for payload in (cpi.to_csv_bytes(self.cpi_records), boi_rate.to_csv_bytes(self.changes)):
            self.assertTrue(payload.startswith(codecs.BOM_UTF8))
            self.assertNotIn(b"\r", payload)
            self.assertTrue(payload.endswith(b"\n"))
            self.assertFalse(payload.endswith(b"\n\n"))
            cells = csv.reader(io.StringIO(payload.decode("utf-8-sig")))
            self.assertFalse(any(re.search(r"[eE][+-]", cell) for row in cells for cell in row))
        self.assertEqual(fmt_number(40691566.5993423), "40691566.5993423")
        self.assertEqual(fmt_number(100.0), "100.0")
        self.assertEqual(fmt_number(1), "1.0")
        with self.assertRaises(ValidationError): fmt_number(1e17)

    def test_deterministic_and_roundtrip(self):
        self.assertEqual(cpi.to_json_bytes(self.cpi_records), cpi.to_json_bytes(self.cpi_records))
        self.assertEqual(cpi.to_csv_bytes(self.cpi_records), cpi.to_csv_bytes(self.cpi_records))
        cpi_obj = json.loads(cpi.to_json_bytes(self.cpi_records))
        self.assertEqual(cpi.to_json_bytes(cpi_obj["observations"]), cpi.to_json_bytes(self.cpi_records))
        boi_obj = json.loads(boi_rate.to_json_bytes(self.changes))
        self.assertEqual(boi_rate.to_json_bytes(boi_obj["changes"]), boi_rate.to_json_bytes(self.changes))

    def test_write_atomic(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "file"
            self.assertTrue(write_atomic(path, b"old"))
            before = path.stat().st_mtime_ns
            time.sleep(0.001)
            self.assertFalse(write_atomic(path, b"old"))
            self.assertEqual(path.stat().st_mtime_ns, before)
            with mock.patch("scripts.common.os.replace", side_effect=OSError("boom")):
                with self.assertRaises(OSError): write_atomic(path, b"new")
            self.assertEqual(path.read_bytes(), b"old")

    def test_orchestrator_source_failure_touches_nothing(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "data"
            def fail(_): raise SourceError("offline")
            with self.assertRaises(SourceError): update_all.update(fetch=fail, data_dir=target)
            self.assertFalse(target.exists())
