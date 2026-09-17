import codecs
import csv
import json
import unittest
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


class PublishedDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not DATA.exists() or not any(DATA.iterdir()):
            raise unittest.SkipTest("data directory has not been generated")

    def test_contract(self):
        names = ("cpi.json", "cpi.csv", "construction_inputs.json", "construction_inputs.csv",
                  "boi_interest_rate.json", "boi_interest_rate.csv")
        for name in names: self.assertTrue((DATA / name).is_file() and (DATA / name).stat().st_size)
        cpi_obj = json.loads((DATA / "cpi.json").read_bytes())
        ci_obj = json.loads((DATA / "construction_inputs.json").read_bytes())
        boi_obj = json.loads((DATA / "boi_interest_rate.json").read_bytes())
        self.assertFalse((DATA / "cpi.json").read_bytes().startswith(codecs.BOM_UTF8))
        self.assertFalse((DATA / "construction_inputs.json").read_bytes().startswith(codecs.BOM_UTF8))
        self.assertFalse((DATA / "boi_interest_rate.json").read_bytes().startswith(codecs.BOM_UTF8))
        csv_rows = {}
        for stem in ("cpi", "construction_inputs", "boi_interest_rate"):
            raw = (DATA / f"{stem}.csv").read_bytes()
            self.assertTrue(raw.startswith(codecs.BOM_UTF8)); self.assertNotIn(b"\r", raw)
            self.assertTrue(raw.endswith(b"\n")); self.assertFalse(raw.endswith(b"\n\n"))
            with (DATA / f"{stem}.csv").open(encoding="utf-8-sig", newline="") as f:
                csv_rows[stem] = list(csv.DictReader(f))
        self.assertEqual(cpi_obj["count"], len(cpi_obj["observations"]))
        self.assertEqual(cpi_obj["count"], len(csv_rows["cpi"])); self.assertGreaterEqual(cpi_obj["count"], 899)
        months = [r["month"] for r in cpi_obj["observations"]]
        self.assertEqual(months, sorted(set(months)))
        self.assertEqual(cpi_obj["observations"][0]["month"], "1951-09")
        self.assertEqual(cpi_obj["observations"][0]["chained_1951_09"], 100.0)

        self.assertEqual(ci_obj["count"], len(ci_obj["observations"]))
        self.assertEqual(ci_obj["count"], len(csv_rows["construction_inputs"]))
        self.assertGreaterEqual(ci_obj["count"], 320)
        self.assertEqual(ci_obj["series_id"], "200010")
        self.assertEqual(ci_obj["chained_base"], "1950 יולי")
        self.assertEqual(ci_obj["chained_base_value"], 100.0)
        self.assertEqual(ci_obj["first_month"], "2000-01")
        ci_months = [r["month"] for r in ci_obj["observations"]]
        self.assertEqual(ci_months, sorted(set(ci_months)))
        self.assertTrue(all(m >= "2000-01" for m in ci_months))
        self.assertEqual(ci_obj["observations"][0]["month"], "2000-01")
        # No rebasing to the export cutoff: the first published observation must NOT read 100.
        self.assertNotEqual(ci_obj["observations"][0]["chained_1950_07"], 100.0)

        self.assertEqual(boi_obj["count"], len(boi_obj["changes"]))
        self.assertEqual(boi_obj["count"], len(csv_rows["boi_interest_rate"])); self.assertGreaterEqual(boi_obj["count"], 159)
        dates = [r["date"] for r in boi_obj["changes"]]
        self.assertEqual(dates, sorted(set(dates)))
        self.assertEqual(boi_obj["changes"][0], {"date": "1994-01-27", "rate": 10.5})
        self.assertEqual(boi_obj["current_rate"], boi_obj["changes"][-1]["rate"])
