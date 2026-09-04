import json
import unittest
from pathlib import Path

from tests.reference_calc import index_amount, resolve, shift_month

ROOT = Path(__file__).parent.parent


class IndexationReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cpi = json.loads((ROOT / "data/cpi.json").read_text(encoding="utf-8"))
        cls.boi = json.loads((ROOT / "data/boi_interest_rate.json").read_text(encoding="utf-8"))
        cls.index_map = {r["month"]: r["chained_1951_09"] for r in cls.cpi["observations"]}

    def test_month_arithmetic_and_resolution(self):
        self.assertEqual(shift_month("1952-01", -1), "1951-12")
        self.assertEqual(shift_month("2026-01", -1), "2025-12")
        self.assertEqual(shift_month("1951-09", -1), "1951-08")
        self.assertNotIn("1951-08", self.index_map)
        self.assertEqual(resolve("2026-07", "for"), "2026-07")
        self.assertEqual(resolve("2026-07", "known"), "2026-06")

    def test_indexation_for_mode(self):
        indexed, difference = index_amount(self.index_map, 1000, "2025-07", "2026-07", "for")
        expected = 1000 * 40691566.5993423 / 40072094.6054417
        self.assertEqual(indexed, expected)
        self.assertEqual(round(indexed, 2), 1015.46); self.assertEqual(round(difference, 2), 15.46)

    def test_indexation_known_mode(self):
        indexed, difference = index_amount(self.index_map, 1000, "2025-07", "2026-07", "known")
        self.assertEqual(round(indexed, 2), 1016.49); self.assertEqual(round(difference, 2), 16.49)

    def test_out_of_range(self):
        for month in ("2026-08", "1951-03"):
            self.assertNotIn(resolve(month, "for"), self.index_map)

    def test_headlines(self):
        yoy = (40691566.5993423 / 40072094.6054417 - 1) * 100
        self.assertEqual(yoy, 1.5458937198069123); self.assertEqual(round(yoy, 2), 1.55)
        latest = next(r for r in self.cpi["observations"] if r["month"] == self.cpi["last_month"])
        self.assertEqual(latest["value"], 105.1)
        self.assertEqual(self.boi["current_rate"], 3.25)
        self.assertEqual(self.boi["current_rate"], self.boi["changes"][-1]["rate"])


if __name__ == "__main__": unittest.main()
