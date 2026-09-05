import codecs
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from scripts import fx_rates
from scripts.common import ParseError, ValidationError


HEADER = ("SERIES_CODE,FREQ,BASE_CURRENCY,COUNTER_CURRENCY,UNIT_MEASURE,DATA_TYPE,"
          "DATA_SOURCE,TIME_COLLECT,CONF_STATUS,PUB_WEBSITE,UNIT_MULT,COMMENTS,"
          "TIME_PERIOD,OBS_VALUE,RELEASE_STATUS\n")


def row(code, date_text, rate, *, unit_mult=None, counter="ILS", series_code=None,
        base=None):
    unit_mult = (2 if code == "JPY" else 0) if unit_mult is None else unit_mult
    return (f"{series_code or f'RER_{code}_ILS'},D,{base or code},{counter},ILS,AVG,BOI,"
            f",F,Y,{unit_mult},,{date_text},{rate},F\n")


def raw_series(dates=("2026-09-03", "2026-09-04"), revised=None):
    body = HEADER
    for code in fx_rates.CURRENCIES:
        for index, date_text in enumerate(dates):
            value = revised if revised is not None and code == "USD" and index == 0 else 1 + index / 10
            body += row(code, date_text, value)
    return body.encode()


def small_series(dates=("2026-09-03", "2026-09-04")):
    return fx_rates.parse_observations(raw_series(dates))


class FxRatesTests(unittest.TestCase):
    def test_parse_and_jpy_unit(self):
        series = small_series()
        self.assertEqual(list(series), list(fx_rates.CURRENCIES))
        self.assertEqual(series["USD"][0], {"date": "2026-09-03", "rate": 1.0})
        self.assertEqual(fx_rates.EXPECTED_UNITS["JPY"], 100)
        self.assertEqual(json.loads(fx_rates.to_json_bytes("JPY", series["JPY"]))["unit"], 100)
        self.assertEqual(json.loads(fx_rates.to_json_bytes("USD", series["USD"]))["unit"], 1)

    def test_merge_replaces_revision_and_preserves_old_history(self):
        stored = [{"date": "1948-05-15", "rate": 4.0},
                  {"date": "2026-09-03", "rate": 3.1}]
        fetched = [{"date": "2026-09-03", "rate": 3.2},
                   {"date": "2026-09-04", "rate": 3.0}]
        self.assertEqual(fx_rates.merge_series(stored, fetched), [
            {"date": "1948-05-15", "rate": 4.0},
            {"date": "2026-09-03", "rate": 3.2},
            {"date": "2026-09-04", "rate": 3.0}])

    def test_update_is_byte_idempotent(self):
        series = small_series()
        with tempfile.TemporaryDirectory() as temp, self.minimums(series):
            target = Path(temp)
            fetch_full = lambda url: raw_series()
            self.assertEqual(len(fx_rates.update(fetch=fetch_full, data_dir=target,
                                                 backfill=True)), 23)
            mtimes = {path: path.stat().st_mtime_ns for path in target.rglob("*") if path.is_file()}
            time.sleep(0.001)
            self.assertEqual(fx_rates.update(fetch=fetch_full, data_dir=target), [])
            self.assertEqual(mtimes, {path: path.stat().st_mtime_ns
                                      for path in target.rglob("*") if path.is_file()})
            self.assertTrue((target / "fx/usd_ils.csv").read_bytes().startswith(codecs.BOM_UTF8))
            self.assertFalse((target / "fx/usd_ils.json").read_bytes().startswith(codecs.BOM_UTF8))

    def test_incremental_requires_complete_readable_history(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValidationError, "--backfill"):
                fx_rates.prepare_update(fetch=lambda _: raw_series(), data_dir=Path(temp))
        series = small_series()
        with tempfile.TemporaryDirectory() as temp, self.minimums(series):
            target = Path(temp)
            fx_rates.update(fetch=lambda _: raw_series(), data_dir=target, backfill=True)
            (target / "fx/usd_ils.csv").write_bytes(b"broken")
            with self.assertRaisesRegex(ValidationError, "--backfill"):
                fx_rates.prepare_update(fetch=lambda _: raw_series(), data_dir=target)

    def test_bad_header_and_row_parsing(self):
        with self.assertRaises(ParseError):
            fx_rates.parse_observations(b"SERIES_CODE,TIME_PERIOD\n")
        for bad_row in (row("USD", "09/04/2026", 3), row("USD", "2026-09-04", "x")):
            with self.subTest(bad_row=bad_row):
                with self.assertRaises(ParseError):
                    fx_rates.parse_observations((HEADER + bad_row).encode())

    def test_source_identity_validation(self):
        cases = ((row("USD", "2026-09-04", 3, series_code="RER_XYZ_ILS"), "series"),
                 (row("USD", "2026-09-04", 3, counter="EUR"), "counter"),
                 (row("USD", "2026-09-04", 3, base="EUR"), "base"),
                 (row("USD", "2026-09-04", 3, unit_mult=2), "UNIT_MULT"),
                 (row("JPY", "2026-09-04", 3, unit_mult=0), "UNIT_MULT"))
        for bad_row, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValidationError, message):
                    fx_rates.parse_observations((HEADER + bad_row).encode())

    def test_validation_failures(self):
        series = small_series()
        with self.assertRaisesRegex(ValidationError, "currencies mismatch"):
            fx_rates.validate({k: v for k, v in series.items() if k != "SEK"},
                              require_minimum=False)
        for mutation, message in (
                (lambda s: s["USD"].append(dict(s["USD"][-1])), "strictly ascending"),
                (lambda s: s["USD"].__setitem__(0, {"date": "bad", "rate": 1}), "date"),
                (lambda s: s["USD"].__setitem__(0, {"date": "2026-09-03", "rate": 0}), "rate"),
                (lambda s: s["USD"].__setitem__(0, {"date": "2026-09-03", "rate": float("inf")}), "rate"),
                (lambda s: s["USD"].__setitem__(0, {"date": "2026-09-03"}), "shape")):
            changed = {code: [dict(item) for item in items] for code, items in series.items()}
            mutation(changed)
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValidationError, message):
                    fx_rates.validate(changed, require_minimum=False)
        with self.assertRaisesRegex(ValidationError, "below minimum"):
            fx_rates.validate(series)

    def test_missing_window_currency_and_non_shrink(self):
        series = small_series()
        empty_one = {code: list(items) for code, items in series.items()}
        empty_one["SEK"] = []
        with tempfile.TemporaryDirectory() as temp, self.minimums(series):
            target = Path(temp)
            fx_rates.update(fetch=lambda _: raw_series(), data_dir=target, backfill=True)
            missing_raw = (HEADER + "".join(row(code, "2026-09-04", 1)
                                             for code in fx_rates.CURRENCIES if code != "SEK")).encode()
            with self.assertRaisesRegex(ValidationError, "missing a currency"):
                fx_rates.prepare_update(fetch=lambda _: missing_raw, data_dir=target)
        with self.assertRaisesRegex(ValidationError, "shrink"):
            fx_rates.validate(series, {"USD": len(series["USD"]) + 1}, require_minimum=False)
        with mock.patch.dict(os.environ, {"STATSO_ALLOW_SHRINK": "1"}):
            fx_rates.validate(series, {"USD": len(series["USD"]) + 1}, require_minimum=False)

    def test_summary_year_end_and_average(self):
        observations = [{"date": "2024-01-02", "rate": 3.0}, {"date": "2024-12-30", "rate": 4.0},
                        {"date": "2025-06-01", "rate": 5.0}, {"date": "2025-12-31", "rate": 7.0},
                        {"date": "2026-09-04", "rate": 9.0}]
        series = {code: list(observations) for code in fx_rates.CURRENCIES}
        self.assertEqual(fx_rates.completed_years(series), [2025, 2024])
        stats_2024 = fx_rates.year_stats(observations, 2024)
        self.assertEqual(stats_2024["year_end"], {"date": "2024-12-30", "rate": 4.0})
        self.assertEqual(stats_2024["average"], 3.5)
        self.assertEqual(stats_2024["count"], 2)
        self.assertIsNone(fx_rates.year_stats(observations, 2019))
        summary = json.loads(fx_rates.summary_json_bytes(series))
        self.assertEqual(summary["years"], [2025, 2024])
        usd = summary["rates"][0]
        self.assertEqual(usd["code"], "USD")
        self.assertEqual(usd["latest"], {"date": "2026-09-04", "rate": 9.0})
        self.assertEqual(usd["first_date"], "2024-01-02")
        self.assertEqual([entry["year"] for entry in usd["years"]], [2025, 2024])
        self.assertEqual(usd["years"][0]["average"], 6.0)

    def test_daily_arrays_stay_aligned(self):
        series = small_series()
        daily = json.loads(fx_rates.daily_json_bytes(series))
        self.assertEqual(set(daily["currencies"]), set(fx_rates.CURRENCIES))
        for code in fx_rates.CURRENCIES:
            entry = daily["currencies"][code]
            self.assertEqual(len(entry["dates"]), len(entry["rates"]))
            self.assertEqual(entry["dates"], [item["date"] for item in series[code]])
            self.assertEqual(entry["rates"], [item["rate"] for item in series[code]])
            self.assertEqual(entry["unit"], fx_rates.EXPECTED_UNITS[code])
        self.assertNotIn(b"\n  ", fx_rates.daily_json_bytes(series))

    def test_recent_url(self):
        self.assertTrue(fx_rates.FULL_URL.endswith("RER_SEK_ILS..?format=csv"))
        self.assertEqual(fx_rates.recent_url(), fx_rates.FULL_URL + "&lastNObservations=10")
        for value in (0, -1, True, 1.5):
            with self.assertRaises(ValueError):
                fx_rates.recent_url(value)

    def test_published_snapshot_contract(self):
        data = Path(__file__).parent.parent / "data"
        series = {}
        for code in fx_rates.CURRENCIES:
            obj = json.loads((data / "fx" / f"{code.lower()}_ils.json").read_bytes())
            self.assertEqual(list(obj), ["dataset", "source", "source_url", "currency",
                "counter_currency", "unit", "count", "first_date", "last_date",
                "observations"])
            self.assertEqual(obj["currency"], code)
            self.assertEqual(obj["unit"], 100 if code == "JPY" else 1)
            self.assertEqual(obj["count"], fx_rates.MIN_COUNTS[code])
            self.assertEqual(obj["first_date"], fx_rates.FIRST_DATES[code])
            self.assertEqual((data / "fx" / f"{code.lower()}_ils.csv").read_bytes(),
                             fx_rates.to_csv_bytes(obj["observations"]))
            series[code] = obj["observations"]
        fx_rates.validate(series)
        latest = (data / "fx_latest.json").read_bytes()
        self.assertEqual(latest, fx_rates.latest_json_bytes(series))
        self.assertFalse(latest.startswith(codecs.BOM_UTF8))

    @staticmethod
    def minimums(series):
        first_dates = {code: items[0]["date"] for code, items in series.items()}
        minimums = {code: len(items) for code, items in series.items()}
        return mock.patch.multiple(fx_rates, FIRST_DATES=first_dates, MIN_COUNTS=minimums)


if __name__ == "__main__":
    unittest.main()
