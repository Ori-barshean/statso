"""Foreign travel report (accounting and tax tools): the pure calculation, the form behaviour against a small mock DOM,
the Word and Excel files it writes, and the source rules (no storage, labelled fields, bilingual sentences).

The calculation tests use a fixed rate fixture, so each expected value is derived by hand from the caps table and
compared exactly (tolerance 1e-9), never as a rounded figure: rows are never rounded, only the totals are.
"""
import json
import re
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from decimal import ROUND_HALF_UP, Decimal
from html.parser import HTMLParser
from pathlib import Path

from tests.test_a11y_round5_source import module, node

ROOT = Path(__file__).resolve().parent.parent
HTML = (ROOT / "index.html").read_text(encoding="utf-8")
TRAVEL = (ROOT / "assets/statso-travel.js").read_text(encoding="utf-8")
DOCX = (ROOT / "assets/statso-docx.js").read_text(encoding="utf-8")
HEBREW = re.compile(r"[֐-׿]")
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
KEYS = ["flight", "insurance", "lodging7", "lodging90", "perDiem", "car", "transport", "phone", "gifts", "hosting", "other"]
ALL_KEYS = ["flight", "insurance", "lodging7", "lodging90", "lodgingAll", "perDiem", "car", "transport", "phone", "gifts", "hosting", "other", "education"]

CAPS = {
    2018: (278, 122, 208.5, 78, 130, 61, 15), 2019: (284, 125, 213, 80, 133, 62, 15),
    2020: (289, 127, 216.75, 81, 136, 64, 15), 2021: (293, 129, 220, 82, 137, 64, 15),
    2022: (313, 137, 235, 88, 147, 69, 15), 2023: (335, 147, 251, 94, 157, 69, 15),
    2024: (346, 152, 259.5, 97, 162, 76, 15), 2025: (355, 156, 266.25, 100, 167, 78, 15),
    2026: (365, 160, 273.75, 102, 171, 80, 15),
}
NOTE_YEARS = {2018, 2020, 2021, 2024, 2025}
COUNTRIES = ["אוסטריה", "אוסטרליה", "איטליה", "איסלנד", "אירלנד", "אנגולה", "בלגיה", "גרמניה", "דובאי", "דנמרק", "הולנד",
             "הונג קונג", "אנגליה/בריטניה", "טיוואן", "יוון", "יפן", "לוקסמבורג", "נורווגיה", "ספרד", "עומאן", "פינלנד",
             "צרפת", "קטאר", "קוריאה", "קמרון", "קנדה", "שבדיה", "שוויץ"]

FULL_HE = ("הכלי מסייע בחישוב משוער של הוצאות נסיעה לחו״ל לפי התקרות והכללים שבטפסי הדיווח לשנות המס, ואינו מהווה ייעוץ מס, "
           "חשבונאי או משפטי. בחלק מהשנים תקרה אחת או יותר נגזרה בחישוב ואינה מופיעה במפורש במקור, והדבר מסומן בדוח. לפני מילוי "
           "הדוח ואחריו, ובכל מקרה לפני הגשה או הכרה בהוצאה, יש להיוועץ ברואה חשבון או ביועץ מס מוסמך ולאמת מולו את הנתונים, "
           "התקרות ותוצאות החישוב. האחריות לנתונים שהוזנו ולשימוש בתוצאות היא של המשתמש.")
FULL_EN = ("This tool helps estimate foreign-travel expenses using the caps and rules in the reporting forms for each tax year. "
           "It is not tax, accounting or legal advice. In some years one or more caps were derived by calculation rather than "
           "stated explicitly in the source, and this is flagged in the report. Before and after completing the report, and in "
           "any case before filing or claiming an expense, consult a licensed accountant or tax adviser and verify the data, the "
           "caps and the calculation results with them. The user is responsible for the data entered and for how the results "
           "are used.")
SHORT_HE = "אינו ייעוץ מס. יש לאמת את הנתונים, התקרות והתוצאות מול רואה חשבון או יועץ מס מוסמך לפני המילוי ואחריו."
SHORT_EN = ("Not tax advice. Verify the data, caps and results with a licensed accountant or tax adviser before and after "
            "completing this report.")

TRANSLATE = r"""
const translate = text => { const t = String(text).trim(); const S = window.Statso; if (S.lang.en[t] !== undefined) { return S.lang.en[t]; }
  for (const rule of S.lang.enPatterns) { if (rule[0].test(t)) { return t.replace(rule[0], rule[1]); } } return null; };
"""

CALC = r"""
global.window = {}; global.document = {addEventListener() {}};
""" + module("statso-core.js") + module("statso-xlsx.js") + module("statso-lang-en.js") + module("statso-travel.js") + TRANSLATE + r"""
const S = window.Statso, T = S.travel;
const KEYS = %s;
const FX = {USD: {unit: 1, dates: ['2026-01-01', '2026-03-05'], rates: [3.6, 3.5]},
  EUR: {unit: 1, dates: ['2026-03-05'], rates: [4.0]}, JPY: {unit: 100, dates: ['2026-03-05'], rates: [2.4]}};
function quoteFor(depart) {
  return code => { const entry = FX[code]; if (!entry) { return {ok: false}; }
    const found = S.core.lookupRateAt(entry.dates, entry.rates, depart);
    return {ok: found.ok, rate: found.rate / entry.unit, unit: entry.unit, date: found.date}; };
}
function inp(o) {
  const rows = {}; KEYS.forEach(key => { rows[key] = {amount: 0, currency: 'USD'}; });
  Object.keys(o.rows || {}).forEach(key => { const v = o.rows[key]; rows[key] = Array.isArray(v) ? {amount: v[0], currency: v[1]} : {amount: v, currency: 'USD'}; });
  const base = Object.assign({year: 2026, listed: false, depart: '2026-03-06', ret: '2026-03-10', partial: false, lodgingDays: 1, travelers: 1}, o);
  if (base.businessDays === undefined) { base.businessDays = T.daysBetween(base.depart, base.ret); }
  base.rows = rows;
  return base;
}
function run(o) { const i = inp(o); return T.calculate(i, quoteFor(i.depart)); }
const out = {};
""" % json.dumps(KEYS)


def calc(script):
    return node(CALC + script)


def row(model, key):
    return next(item for item in model["rows"] if item["key"] == key)


def half_up(value):
    return float(Decimal(repr(round(value, 8))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


class TableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seen = calc("""
out.caps = T.CAPS; out.years = T.YEARS; out.countries = T.COUNTRIES;
out.days = [T.daysBetween('2026-03-06', '2026-03-10'), T.daysBetween('2026-01-01', '2026-04-10'), T.daysBetween('2026-03-06', '2026-03-06')];
process.stdout.write(JSON.stringify(out));
""")

    def test_caps_table_is_exactly_the_published_one(self):
        self.assertEqual(sorted(int(year) for year in self.seen["caps"]), list(CAPS))
        names = ["lodging7", "floor", "max", "perDiemLodging", "perDiemNoLodging", "car", "gift"]
        for year, values in CAPS.items():
            with self.subTest(year=year):
                entry = self.seen["caps"][str(year)]
                self.assertEqual([entry[name] for name in names], list(values))
                self.assertEqual(entry["note"] is not None, year in NOTE_YEARS)
                if year in NOTE_YEARS:
                    self.assertIn("בשנת %d " % year, entry["note"])

    def test_years_follow_the_table_and_the_countries_are_the_28_listed(self):
        self.assertEqual(self.seen["years"], list(range(2018, 2027)))
        self.assertEqual(self.seen["countries"], COUNTRIES)
        self.assertEqual(len(self.seen["countries"]), 28)
        self.assertEqual(len(set(self.seen["countries"])), 28)

    def test_days_include_both_ends(self):
        self.assertEqual(self.seen["days"], [5, 100, 1])

    def test_the_derived_year_notes_are_written_as_the_spec_says(self):
        notes = self.seen["caps"]
        self.assertIn("208.5", notes["2018"]["note"])
        self.assertIn("200 דולר", notes["2018"]["note"])
        self.assertIn("מטופס 2019", notes["2018"]["note"])
        self.assertIn("216.75", notes["2020"]["note"])
        self.assertIn("תבנית האקסל", notes["2021"]["note"])
        self.assertIn("259.5", notes["2024"]["note"])
        self.assertIn("346 דולר", notes["2024"]["note"])
        self.assertIn("443.75", notes["2025"]["note"])


class CalculationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = calc(r"""
const s = {};
// first 7 nights: 2026, two travellers, five nights
s.lodging = run({travelers: 2, rows: {lodging7: 4000}});
s.lodgingListed = run({travelers: 2, listed: true, rows: {lodging7: 4000}});
s.y2025 = run({year: 2025, rows: {lodging7: 1000}});
s.y2025Listed = run({year: 2025, listed: true, rows: {lodging7: 1000}});
s.y2024 = run({year: 2024, rows: {lodging7: 1000}});
s.shortStay = run({depart: '2026-03-06', ret: '2026-03-08', rows: {lodging7: 1000}});
// nights 8-90: twenty days = 13 nights in the range
const nights = {depart: '2026-03-06', ret: '2026-03-25'};
s.x300 = run(Object.assign({rows: {lodging90: 3900}}, nights));
s.x180 = run(Object.assign({rows: {lodging90: 2340}}, nights));
s.x400 = run(Object.assign({rows: {lodging90: 5200}}, nights));
s.x150 = run(Object.assign({rows: {lodging90: 1950}}, nights));
s.listed180 = run(Object.assign({listed: true, rows: {lodging90: 2340}}, nights));
s.listed500 = run(Object.assign({listed: true, rows: {lodging90: 6500}}, nights));
s.none90 = run(Object.assign({rows: {lodging90: 0}}, nights));
s.noRange = run({rows: {lodging90: 100}});
// more than 90 nights
const long = {depart: '2026-01-01', ret: '2026-04-10'};
s.over90 = run(Object.assign({rows: {lodging7: 2000, lodging90: 20000}}, long));
s.over90Listed = run(Object.assign({listed: true, rows: {lodging7: 2000, lodging90: 20000}}, long));
s.over90Mixed = run(Object.assign({depart: '2026-03-06', ret: '2026-06-15', rows: {lodging7: [100, 'EUR'], lodging90: [100, 'USD']}}));
s.over90One = run(Object.assign({depart: '2026-03-06', ret: '2026-06-15', rows: {lodging7: [100, 'EUR']}}));
s.over90Later = run(Object.assign({depart: '2026-03-06', ret: '2026-06-15', rows: {lodging90: [100, 'EUR']}}));
s.exactly90 = run({depart: '2026-03-06', ret: '2026-06-03', rows: {lodging7: 100, lodging90: 100}});
// per diem
s.pdWith = run({travelers: 2, rows: {lodging7: 1, perDiem: 1020}});
s.pdIls = run({travelers: 2, rows: {lodging7: 1, perDiem: [5000, 'ILS']}});
s.pdWithout = run({travelers: 2, rows: {perDiem: 1710}});
s.pdPartial = run({travelers: 2, partial: true, lodgingDays: 3, rows: {perDiem: 1296}});
s.pdPartialListed = run({travelers: 2, partial: true, listed: true, lodgingDays: 3, rows: {perDiem: 1620}});
s.pdTooMany = run({travelers: 2, partial: true, lodgingDays: 5, rows: {perDiem: 1}});
s.partialLodging = run({depart: '2026-03-06', ret: '2026-03-15', partial: true, lodgingDays: 4, rows: {lodging7: 1460, lodging90: 10, perDiem: 1434}});
s.partialOver = run({depart: '2026-03-06', ret: '2026-03-15', partial: true, lodgingDays: 4, rows: {lodging7: 3650}});
// car and gifts
s.car = run({travelers: 2, rows: {car: 1000}});
s.carListed = run({travelers: 2, listed: true, rows: {car: 1000}});
s.gifts = run({travelers: 3, rows: {gifts: 60}});
s.giftsListed = run({travelers: 3, listed: true, rows: {gifts: 60}});
// fully recognised rows and currencies
s.free = run({rows: {flight: [10000, 'JPY'], insurance: [100, 'EUR'], transport: 50, phone: 20, hosting: 30, other: 40}});
// years and dates
s.yearMismatch = run({year: 2025, rows: {lodging7: 1000}});
s.dayNote = run({businessDays: 3, rows: {lodging7: 1000}});
s.friday = run({rows: {flight: 100}});
s.travelersArray = run({travelers: [{name: 'א'}, {name: 'ב'}], rows: {lodging7: 4000}});
out.s = s;
process.stdout.write(JSON.stringify(s));
""")

    def near(self, actual, expected):
        self.assertAlmostEqual(actual, expected, delta=1e-9)

    def check(self, item, ils, cap, recognized, adjust):
        self.near(item["ils"], ils)
        self.near(item["cap"], cap)
        self.near(item["recognized"], recognized)
        self.near(item["adjust"], adjust)

    def test_every_row_and_the_totals_add_up(self):
        for name, model in self.s.items():
            if not model["ok"]:
                continue
            with self.subTest(case=name):
                for item in model["rows"]:
                    self.near(item["recognized"] + item["adjust"], item["ils"])
                for key, field in (("ils", "ils"), ("recognized", "recognized"), ("adjust", "adjust")):
                    self.assertEqual(model["totals"][key], half_up(sum(item[field] for item in model["rows"])))
                self.assertLessEqual(abs(model["totals"]["recognized"] + model["totals"]["adjust"] - model["totals"]["ils"]), 0.0101)

    def test_first_seven_nights(self):
        item = row(self.s["lodging"], "lodging7")
        self.check(item, 14000, 3650 * 3.5, 12775, 1225)
        self.assertEqual((item["amount"], item["currency"]), (4000, "USD"))
        self.near(self.s["lodging"]["rates"][0]["rate"], 3.5)
        self.check(row(self.s["lodgingListed"], "lodging7"), 14000, 4562.5 * 3.5, 14000, 0)
        self.near(row(self.s["lodgingListed"], "lodging7")["cap"], 15968.75)
        # the cap is per night of the form's year, however the dates fall
        self.near(row(self.s["y2025"], "lodging7")["cap"], 355 * 5 * 3.5)
        self.near(row(self.s["y2025Listed"], "lodging7")["cap"], 443.75 * 5 * 3.5)
        self.near(row(self.s["y2024"], "lodging7")["cap"], 346 * 5 * 3.5)
        self.near(row(self.s["shortStay"], "lodging7")["cap"], 365 * 3 * 3.5)

    def test_nights_eight_to_ninety_apply_the_75_percent_rule_between_floor_and_maximum(self):
        self.check(row(self.s["x300"], "lodging90"), 13650, 10237.5, 10237.5, 3412.5)
        self.check(row(self.s["x180"], "lodging90"), 8190, 7280, 7280, 910)       # 75% is below the floor: the floor
        item = row(self.s["x400"], "lodging90")                                   # 75% is above the maximum: the maximum
        self.check(item, 18200, 12455.625, 12455.625, 5744.375)
        self.check(row(self.s["x150"], "lodging90"), 6825, 6825, 6825, 0)         # at or below the floor: all of it
        # the uplifted floor and maximum (200 and 342.1875) for the listed countries
        self.check(row(self.s["listed180"], "lodging90"), 8190, 8190, 8190, 0)
        self.check(row(self.s["listed500"], "lodging90"), 22750, 15569.53125, 15569.53125, 22750 - 15569.53125)

    def test_a_row_is_shown_unrounded_and_only_the_total_is_rounded_half_up(self):
        model = self.s["x400"]
        self.near(row(model, "lodging90")["cap"], 12455.625)       # not 12455.63
        self.near(row(model, "lodging90")["recognized"], 12455.625)
        self.assertEqual(model["totals"]["recognized"], 12455.63)
        self.assertEqual(model["totals"]["adjust"], 5744.38)
        self.assertEqual(model["totals"]["ils"], 18200)
        self.assertEqual(self.s["listed500"]["totals"]["recognized"], 15569.53)

    def test_nights_eight_to_ninety_edge_cases(self):
        item = row(self.s["none90"], "lodging90")
        self.assertIsNone(item["cap"])                              # no amount: no cap
        self.assertEqual((item["ils"], item["recognized"], item["adjust"]), (0, 0, 0))
        item = row(self.s["noRange"], "lodging90")                  # five nights: none fall in the range
        self.near(item["cap"], 0)
        self.near(item["recognized"], 0)
        self.near(item["adjust"], 350)
        self.assertIn("אין לילות בטווח 8–90", item["explain"])

    def test_over_ninety_nights_use_the_floor_for_every_night_in_one_row(self):
        model = self.s["over90"]
        keys = [item["key"] for item in model["rows"]]
        self.assertIn("lodgingAll", keys)
        self.assertNotIn("lodging7", keys)
        self.assertNotIn("lodging90", keys)
        self.assertEqual(model["nights"], 100)
        self.check(row(model, "lodgingAll"), 79200, 57600, 57600, 21600)
        self.assertIn("מעל 90 לילות", row(model, "lodgingAll")["explain"])
        self.check(row(self.s["over90Listed"], "lodgingAll"), 79200, 160 * 1.25 * 100 * 3.6, 72000, 7200)   # 20,000 dollars at 3.6
        # exactly ninety nights is still the two-row rule
        self.assertEqual(self.s["exactly90"]["nights"], 90)
        self.assertIn("lodging90", [item["key"] for item in self.s["exactly90"]["rows"]])

    def test_over_ninety_nights_merge_the_two_amounts_without_inventing_a_currency(self):
        mixed = row(self.s["over90Mixed"], "lodgingAll")
        self.near(mixed["ils"], 100 * 4.0 + 100 * 3.5)
        self.assertEqual((mixed["currency"], mixed["amount"]), ("ILS", mixed["ils"]))
        one = row(self.s["over90One"], "lodgingAll")
        self.assertEqual((one["currency"], one["amount"]), ("EUR", 100))
        later = row(self.s["over90Later"], "lodgingAll")
        self.assertEqual((later["currency"], later["amount"]), ("EUR", 100))

    def test_per_diem_rates_with_and_without_lodging_and_in_partial_mode(self):
        self.check(row(self.s["pdWith"], "perDiem"), 3570, 3570, 3570, 0)
        self.check(row(self.s["pdIls"], "perDiem"), 5000, 3570, 3570, 1430)
        self.check(row(self.s["pdWithout"], "perDiem"), 5985, 5985, 5985, 0)
        self.near(row(self.s["pdPartial"], "perDiem")["cap"], 4536)
        self.near(row(self.s["pdPartialListed"], "perDiem")["cap"], 5670)

    def test_partial_per_diem_needs_fewer_lodging_days_than_business_days(self):
        model = self.s["pdTooMany"]
        self.assertFalse(model["ok"])
        self.assertEqual(model["errors"][0]["message"], "מספר ימי הלינה לא יעלה על 4")
        self.assertEqual(model["errors"][0]["fields"], ["tt-lodging-days"])

    def test_partial_mode_counts_lodging_nights_by_the_lodging_days_not_the_business_days(self):
        model = self.s["partialLodging"]
        self.assertEqual(model["nights"], 4)
        self.near(row(model, "lodging7")["cap"], 365 * 4 * 3.5)            # not 365 * 7 * 3.5
        self.near(row(model, "perDiem")["cap"], (4 * 102 + 6 * 171) * 3.5)
        item = row(model, "lodging90")
        self.near(item["cap"], 0)                                           # four nights: none in the 8-90 range
        self.near(item["adjust"], 10 * 3.5)
        self.near(row(self.s["partialOver"], "lodging7")["adjust"], (3650 - 1460) * 3.5)

    def test_car_is_capped_per_day_and_gifts_per_person_and_neither_gifts_nor_others_get_a_listed_uplift(self):
        self.check(row(self.s["car"], "car"), 3500, 2800, 2800, 700)
        self.check(row(self.s["carListed"], "car"), 3500, 3500, 3500, 0)
        self.check(row(self.s["gifts"], "gifts"), 210, 157.5, 157.5, 52.5)
        self.check(row(self.s["giftsListed"], "gifts"), 210, 157.5, 157.5, 52.5)

    def test_the_gift_cap_in_the_sentence_is_the_table_value_and_not_a_typed_15(self):
        seen = calc(r"""
const original = T.CAPS[2026].gift;
T.CAPS[2026].gift = 20;
let model;
try { model = run({travelers: 3, rows: {gifts: 100}}); } finally { T.CAPS[2026].gift = original; }
const item = model.rows.find(row => row.key === 'gifts');
process.stdout.write(JSON.stringify({item, english: translate(item.explain), restored: T.CAPS[2026].gift}));
""")
        item = seen["item"]
        self.assertIn("תקרה: 20 דולר לאדם · נוסעים: 3", item["explain"])
        self.assertNotIn("15", item["explain"])
        self.near(item["cap"], 20 * 3 * 3.5)
        self.near(item["adjust"], 100 * 3.5 - 20 * 3 * 3.5)
        self.assertIsNone(HEBREW.search(seen["english"]))
        self.assertIn("Cap: USD 20 per person · travellers: 3", seen["english"])
        self.assertEqual(seen["restored"], 15)

    def test_fully_recognised_rows_and_currency_conversion(self):
        model = self.s["free"]
        self.near(row(model, "flight")["ils"], 240)                         # JPY 10,000 at 2.4 per 100
        self.near(row(model, "insurance")["ils"], 400)
        for key, amount in (("flight", 240), ("insurance", 400), ("transport", 175), ("phone", 70), ("hosting", 105), ("other", 140)):
            with self.subTest(row=key):
                item = row(model, key)
                self.near(item["recognized"], amount)
                self.near(item["adjust"], 0)
                self.near(item["cap"], amount)

    def test_the_departure_date_chooses_the_rate_and_a_friday_uses_thursdays(self):
        rate = self.s["friday"]["rates"][0]
        self.assertEqual((rate["code"], rate["rate"], rate["date"]), ("USD", 3.5, "2026-03-05"))

    def test_a_different_year_for_the_dates_is_only_a_note(self):
        model = self.s["yearMismatch"]
        self.assertTrue(model["ok"])
        self.assertTrue(any(note.startswith("שימו לב: שנת תאריך היציאה או החזרה") for note in model["notes"]))
        self.assertTrue(any("בשנת 2025 תקרת 7" in note for note in model["notes"]))      # the derived-cap note of the year
        self.near(row(model, "lodging7")["cap"], 355 * 5 * 3.5)
        self.assertFalse(any(note.startswith("שימו לב: שנת") for note in self.s["lodging"]["notes"]))

    def test_year_notes_appear_only_in_the_years_that_derive_a_cap(self):
        notes = calc(r"""
const o = {};
for (const year of T.YEARS) {
  const i = inp({year, depart: year + '-03-06', ret: year + '-03-10'});
  o[year] = T.calculate(i, () => ({ok: true, rate: 3.5, unit: 1, date: i.depart})).notes;
}
process.stdout.write(JSON.stringify(o));
""")
        for year in CAPS:
            with self.subTest(year=year):
                has = any(note.startswith("בשנת %d " % year) for note in notes[str(year)])
                self.assertEqual(has, year in NOTE_YEARS)

    def test_business_days_below_the_total_are_named_in_words(self):
        notes = self.s["dayNote"]["notes"]
        self.assertIn("הימים העסקיים (3) פחותים מסך ימי הנסיעה (5).", notes)
        self.assertNotIn("הימים העסקיים (5) פחותים", " ".join(self.s["lodging"]["notes"]))

    def test_the_notes_carry_currency_but_no_flight_or_old_education_remark(self):
        notes = self.s["lodging"]["notes"]
        # the first-class sentence lives only in the round "!" button beside the flight title, not in the notes
        self.assertFalse(any("מחלקה ראשונה" in note for note in notes))
        self.assertFalse(any("שימו לב: במחלקה" in note or note.startswith("!") for note in notes))
        # a short trip has no children's education: neither the old "not calculated" remark nor the new rule
        self.assertFalse(any("חינוך ילדים" in note for note in notes))
        self.assertTrue(any("מטבע שאינו אחד מהמטבעות" in note for note in notes))

    def test_the_travellers_may_be_a_list_or_a_count(self):
        self.near(row(self.s["travelersArray"], "lodging7")["cap"], row(self.s["lodging"], "lodging7")["cap"])


class ValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = calc(r"""
const s = {};
s.businessZero = run({businessDays: 0});
s.businessTooMany = run({businessDays: 6});
s.businessFraction = run({businessDays: 2.5});
s.businessNaN = run({businessDays: NaN});
s.partialAll = run({partial: true, lodgingDays: 5});
s.partialZero = run({partial: true, lodgingDays: 0});
s.partialFraction = run({partial: true, lodgingDays: 1.5});
s.partialSingleDay = run({depart: '2026-03-06', ret: '2026-03-06', partial: true, lodgingDays: 1});
s.reversed = run({depart: '2026-03-10', ret: '2026-03-06'});
s.noDates = run({depart: '', ret: ''});
s.badDate = run({depart: '2026-02-30', ret: '2026-03-06'});
s.negative = run({rows: {car: -1}});
s.notANumber = run({rows: {phone: NaN}});
s.badCurrency = run({rows: {gifts: [5, 'XXX']}});
s.noTravellers = run({travelers: 0});
s.badYear = run({year: 2030});
s.beforeData = run({depart: '2025-12-31', ret: '2026-01-02'});
s.noRateForCurrency = run({rows: {insurance: [10, 'GBP']}});
s.week = run({depart: '2026-03-12', ret: '2026-03-12', rows: {flight: 1}});
s.weekPlusOne = run({depart: '2026-03-13', ret: '2026-03-13', rows: {flight: 1}});
s.future = run({year: 2026, depart: '2026-12-01', ret: '2026-12-05', rows: {lodging7: 1000}});
process.stdout.write(JSON.stringify(s));
""")

    def fields(self, name):
        return sorted({field for error in self.s[name]["errors"] for field in error["fields"]})

    def test_business_days_must_be_a_whole_number_within_the_trip(self):
        for name in ("businessZero", "businessTooMany", "businessFraction", "businessNaN"):
            with self.subTest(case=name):
                self.assertFalse(self.s[name]["ok"])
                self.assertEqual(self.fields(name), ["tt-business-days"])
                self.assertEqual(self.s[name]["errors"][0]["message"], "מספר הימים העסקיים חייב להיות שלם בטווח 1 עד 5.")

    def test_without_dates_only_the_dates_are_named(self):
        for name in ("noDates", "badDate"):
            with self.subTest(case=name):
                self.assertFalse(self.s[name]["ok"])
        self.assertEqual(self.fields("noDates"), ["tt-depart", "tt-return"])
        self.assertEqual(self.fields("badDate"), ["tt-depart"])
        for error in self.s["noDates"]["errors"]:
            self.assertNotIn("NaN", error["message"])

    def test_lodging_days_in_partial_mode(self):
        for name in ("partialAll", "partialSingleDay"):
            with self.subTest(case=name):
                self.assertEqual(self.fields(name), ["tt-lodging-days"])
        self.assertEqual(self.s["partialAll"]["errors"][0]["message"], "מספר ימי הלינה לא יעלה על 4")
        # one business day cannot be split: a sentence of its own, never "must not exceed 0"
        self.assertEqual(self.s["partialSingleDay"]["errors"][0]["message"],
                         "יש יום עסקי אחד בלבד, ולכן אי אפשר לחלק אותו לימים עם לינה ובלי לינה. "
                         "יש לבטל את הסימון בתיבה או להגדיל את מספר הימים העסקיים.")
        self.assertEqual(len(self.s["partialSingleDay"]["errors"]), 1)
        for name in ("partialZero", "partialFraction"):
            with self.subTest(case=name):
                self.assertEqual(self.fields(name), ["tt-lodging-days"])
                self.assertEqual(self.s[name]["errors"][0]["message"], "מספר ימי הלינה חייב להיות מספר שלם וחיובי.")

    def test_reversed_dates_flag_both_date_fields(self):
        self.assertFalse(self.s["reversed"]["ok"])
        self.assertEqual(self.fields("reversed"), ["tt-depart", "tt-return"])

    def test_a_negative_or_unreadable_amount_names_its_row_and_field(self):
        self.assertEqual(self.fields("negative"), ["tt-car-amount"])
        self.assertIn("השכרת רכב", self.s["negative"]["errors"][0]["message"])
        self.assertEqual(self.fields("notANumber"), ["tt-phone-amount"])
        self.assertIn("טלפון", self.s["notANumber"]["errors"][0]["message"])
        self.assertEqual(self.fields("badCurrency"), ["tt-gifts-currency"])

    def test_year_and_travellers_are_checked(self):
        self.assertEqual(self.fields("badYear"), ["tt-year"])
        self.assertEqual(self.fields("noTravellers"), ["tt-add-traveler"])

    def test_no_rate_at_all_is_an_error_on_the_departure_field(self):
        for name in ("beforeData", "noRateForCurrency"):
            with self.subTest(case=name):
                self.assertFalse(self.s[name]["ok"])
                self.assertEqual(self.fields(name), ["tt-depart"])
        self.assertIn("USD", self.s["beforeData"]["errors"][0]["message"])
        self.assertIn("GBP", self.s["noRateForCurrency"]["errors"][0]["message"])

    def test_an_old_rate_is_a_warning_and_the_latest_published_rate_is_used(self):
        self.assertTrue(self.s["week"]["ok"])
        self.assertFalse(any("אין שער בטווח 7 ימים" in note for note in self.s["week"]["notes"]))       # seven days is in range
        self.assertTrue(self.s["weekPlusOne"]["ok"])
        warnings = [note for note in self.s["weekPlusOne"]["notes"] if "אין שער בטווח 7 ימים" in note]
        self.assertEqual(len(warnings), 1)
        self.assertTrue(warnings[0].startswith("שימו לב:"))
        self.assertIn("05/03/2026", warnings[0])
        self.assertIn("USD", warnings[0])
        model = self.s["future"]
        self.assertTrue(model["ok"])
        self.assertEqual((model["rates"][0]["rate"], model["rates"][0]["date"]), (3.5, "2026-03-05"))
        self.assertAlmostEqual(row(model, "lodging7")["cap"], 365 * 5 * 3.5, delta=1e-9)
        self.assertTrue(any("05/03/2026" in note for note in model["notes"]))


NUM = r"([\d.]+)"
UPLIFT = r"( \(כולל תוספת 25%\))?"
ILS = r"([\d,]+\.\d\d)"
TAIL = r" = " + NUM + r" דולר · לפי שער " + NUM + r" = " + ILS + r" ₪\."
EDU_TAIL = r" = " + ILS + r" דולר · לפי שער " + NUM + r" = " + ILS + r" ₪\."
EXPLANATIONS = {
    "lodging7": [("night", re.compile(r"^תקרה: " + NUM + r" דולר ללילה" + UPLIFT + r" · לילות: (\d+) · נוסעים: (\d+)" + TAIL + "$"))],
    "lodgingAll": [("all", re.compile(r"^מעל 90 לילות: כל הלילות, מהלילה הראשון, לפי " + NUM + r" דולר ללילה" + UPLIFT
                                      + r" \(תקרת הסף ללילות 8–90 בשנת (\d+)\) · לילות: (\d+) · נוסעים: (\d+)" + TAIL + "$"))],
    "lodging90": [("above", re.compile(r"^ממוצע ללילה לנוסע " + NUM + r" דולר, מעל הסף של " + NUM + r" דולר" + UPLIFT
                                       + r": 75% הם " + NUM + r" דולר; בגבולות " + NUM + "–" + NUM + r" דולר מוכרים " + NUM
                                       + r" דולר ללילה · לילות: (\d+) · נוסעים: (\d+)" + TAIL + "$")),
                  ("upto", re.compile(r"^ממוצע ללילה לנוסע " + NUM + r" דולר, עד הסף של " + NUM + r" דולר" + UPLIFT + r" — מוכר במלואו\.$")),
                  ("none", re.compile(r"^אין לילות בטווח 8–90 \(סה״כ לילות: (\d+)\), ולכן אין הכרה בשורה זו\.$"))],
    "perDiem": [("full", re.compile(r"^ימים: (\d+) · " + NUM + r" דולר ליום \((עם|בלי) הוצאות לינה\)" + UPLIFT + r" · נוסעים: (\d+)" + TAIL + "$")),
                ("partial", re.compile(r"^ימים עם לינה: (\d+) · " + NUM + r" דולר; ימים בלי לינה: (\d+) · " + NUM + r" דולר" + UPLIFT
                                       + r" · נוסעים: (\d+)" + TAIL + "$"))],
    "car": [("day", re.compile(r"^תקרה: " + NUM + r" דולר ליום" + UPLIFT + r" · ימים: (\d+) · נוסעים: (\d+)" + TAIL + "$"))],
    "gifts": [("person", re.compile(r"^תקרה: " + NUM + r" דולר לאדם · נוסעים: (\d+)" + TAIL.replace(r" ₪\.", r" ₪ \(ללא תוספת 25%\)\.") + "$"))],
    # the months to four digits and the dollar total in the tool's number format (18,330.08): only the education sentence rounds
    "education": [("month", re.compile(r"^תקרה: " + NUM + r" דולר לילד לחודש · ילדים: (\d+) · חודשים: (\d+\.\d{4})"
                                       + r" \(ימי הנסיעה: (\d+) × 12 ÷ 365\)" + EDU_TAIL + "$"))],
}
EDUCATION_USD = {2018: (696, "cpi"), 2019: (711, "cpi"), 2020: (726, "cpi"), 2021: (734, "cpi"), 2022: (784, "cpi"),
                 2023: (840, "cpi"), 2024: (866, "cpi"), 2025: (890, "regulation"), 2026: (914, "cpa")}


def numbers(text):
    return sorted(token.rstrip(".,") for token in re.findall(r"\d[\d,.]*", text))


class ExplanationArithmeticTests(unittest.TestCase):
    """What an explanation says must be what it computed: every figure in the sentence is the one the cap used, in both
    languages, in every year, with and without the 25% uplift (the sentence once showed the base rate beside the uplift mark)."""

    @classmethod
    def setUpClass(cls):
        cls.seen = calc(r"""
const items = [];
const nights = {depart: '2026-03-06', ret: '2026-03-25'}, long = {depart: '2026-01-01', ret: '2026-04-10'}, one = {depart: '2026-03-06', ret: '2026-03-06'};
const scenarios = [
  {travelers: 2, rows: {lodging7: 4000, perDiem: 1, car: 1, gifts: 1}},
  {travelers: 2, rows: {perDiem: 1, car: 1}},
  {travelers: 3, partial: true, lodgingDays: 3, rows: {perDiem: 1}},
  ...[1950, 2340, 3900, 5200, 40000].map(amount => Object.assign({travelers: 1, rows: {lodging90: amount}}, nights)),
  Object.assign({travelers: 1, rows: {lodging7: 2000, lodging90: 20000}}, long),
  Object.assign({travelers: 1, rows: {perDiem: 1, car: 1}}, one),
  {travelers: 2, children: 3, depart: '2026-03-06', ret: '2027-01-04', rows: {education: 1}}
];
const wanted = new Set(['lodging7', 'lodging90', 'lodgingAll', 'perDiem', 'car', 'gifts', 'education']);
for (const listed of [false, true]) for (const year of T.YEARS) for (const scenario of scenarios) {
  const i = inp(Object.assign({year, listed}, scenario));
  const model = T.calculate(i, quoteFor(i.depart));
  model.rows.filter(row => wanted.has(row.key) && row.cap !== null).forEach(row => items.push({year, listed, key: row.key, explain: row.explain,
    english: translate(row.explain), cap: row.cap, usd: model.rates[0].rate, L: model.nights, B: i.businessDays, N: i.travelers,
    K: i.partial ? i.lodgingDays : null, C: i.children, D: model.totalDays}));
}
const exact = {};
for (const [name, o] of [['full', {travelers: 2, listed: true, rows: {perDiem: 1}}], ['partial', {travelers: 2, listed: true, partial: true, lodgingDays: 3, rows: {perDiem: 1}}],
    ['withLodging', {travelers: 2, listed: false, rows: {lodging7: 1, perDiem: 1}}]]) {
  const row = run(o).rows.find(item => item.key === 'perDiem');
  exact[name] = {explain: row.explain, english: translate(row.explain), cap: row.cap};
}
process.stdout.write(JSON.stringify({caps: T.CAPS, items, exact}));
""")

    def close(self, actual, expected, what=""):
        self.assertLessEqual(abs(actual - expected), 1e-9 * max(1, abs(expected)), what)

    def test_every_explained_row_matches_a_known_sentence_and_its_figures_are_the_ones_used(self):
        seen = {}
        for item in self.seen["items"]:
            caps = self.seen["caps"][str(item["year"])]
            m = 1.25 if item["listed"] else 1
            where = "%s %s listed=%s: %s" % (item["year"], item["key"], item["listed"], item["explain"])
            match = None
            for variant, pattern in EXPLANATIONS[item["key"]]:
                match = pattern.match(item["explain"])
                if match:
                    break
            self.assertIsNotNone(match, where)
            seen[(item["key"], variant)] = seen.get((item["key"], variant), 0) + 1
            groups = match.groups()
            n = float
            usd, cap, N = item["usd"], item["cap"], item["N"]
            rounded = False
            with self.subTest(where):
                if item["key"] == "lodging7":
                    c, up, nights, travellers, t, rate, ils = n(groups[0]), groups[1], int(groups[2]), int(groups[3]), n(groups[4]), n(groups[5]), n(groups[6].replace(",", ""))
                    self.close(c, caps["lodging7"] * m)
                    self.assertEqual((nights, travellers), (min(item["L"], 7), N))
                    self.close(c * nights * N, t)
                elif item["key"] == "lodgingAll":
                    c, up, year, nights, travellers, t, rate, ils = n(groups[0]), groups[1], int(groups[2]), int(groups[3]), int(groups[4]), n(groups[5]), n(groups[6]), n(groups[7].replace(",", ""))
                    self.close(c, caps["floor"] * m)
                    self.assertEqual((year, nights, travellers), (item["year"], item["L"], N))
                    self.close(c * nights * N, t)
                elif variant == "above":
                    x, f, up, p, low, high, a, nights, travellers, t, rate, ils = (n(groups[0]), n(groups[1]), groups[2], n(groups[3]), n(groups[4]), n(groups[5]),
                                                                                    n(groups[6]), int(groups[7]), int(groups[8]), n(groups[9]), n(groups[10]), n(groups[11].replace(",", "")))
                    self.close(f, caps["floor"] * m)
                    self.close(low, caps["floor"] * m)
                    self.close(high, caps["max"] * m)
                    self.close(p, 0.75 * x)
                    self.close(a, min(high, max(f, p)))
                    self.assertGreater(x, f)
                    self.assertEqual((nights, travellers), (min(item["L"], 90) - 7, N))
                    self.close(a * nights * N, t)
                elif variant == "upto":
                    x, f, up = n(groups[0]), n(groups[1]), groups[2]
                    self.close(f, caps["floor"] * m)
                    self.assertLessEqual(x, f * (1 + 1e-9))
                    t = rate = ils = None
                elif variant == "none":
                    self.assertEqual(int(groups[0]), item["L"])
                    t = rate = ils = up = None
                elif variant == "full":
                    days, r, with_, up, travellers, t, rate, ils = int(groups[0]), n(groups[1]), groups[2], groups[3], int(groups[4]), n(groups[5]), n(groups[6]), n(groups[7].replace(",", ""))
                    self.assertEqual((days, travellers), (item["B"], N))
                    self.close(r, caps["perDiemLodging" if with_ == "עם" else "perDiemNoLodging"] * m)
                    self.close(days * r * N, t)
                elif variant == "partial":
                    k, lo, h, hi, up, travellers, t, rate, ils = int(groups[0]), n(groups[1]), int(groups[2]), n(groups[3]), groups[4], int(groups[5]), n(groups[6]), n(groups[7]), n(groups[8].replace(",", ""))
                    self.assertEqual((k, h, travellers), (item["K"], item["B"] - item["K"], N))
                    self.close(lo, caps["perDiemLodging"] * m)
                    self.close(hi, caps["perDiemNoLodging"] * m)
                    self.close((k * lo + h * hi) * N, t)
                elif item["key"] == "education":
                    r, children, months, days, t, rate, ils = n(groups[0]), int(groups[1]), n(groups[2]), int(groups[3]), n(groups[4].replace(",", "")), n(groups[5]), n(groups[6].replace(",", ""))
                    self.close(r, EDUCATION_USD[item["year"]][0])
                    self.assertEqual((children, days), (item["C"], item["D"]))
                    # months to four digits, dollars to the cent: what is shown is rounded, the cap itself is not
                    self.assertLessEqual(abs(months - days * 12 / 365), 0.00005 + 1e-12)
                    self.assertLessEqual(abs(r * children * months - t), r * children * 0.00005 + 0.005 + 1e-9)
                    rounded = True
                    up = None
                elif item["key"] == "car":
                    c, up, days, travellers, t, rate, ils = n(groups[0]), groups[1], int(groups[2]), int(groups[3]), n(groups[4]), n(groups[5]), n(groups[6].replace(",", ""))
                    self.close(c, caps["car"] * m)
                    self.assertEqual((days, travellers), (item["B"], N))
                    self.close(c * days * N, t)
                else:
                    g, travellers, t, rate, ils = n(groups[0]), int(groups[1]), n(groups[2]), n(groups[3]), n(groups[4].replace(",", ""))
                    self.close(g, caps["gift"])                    # never the uplifted figure
                    self.assertEqual(travellers, N)
                    self.close(g * N, t)
                    up = None
                if t is not None:
                    self.close(rate, usd)
                    if rounded:
                        self.assertLessEqual(abs(t - cap / usd), 0.005 + 1e-9, "the dollar total is the cap in dollars, shown to the cent")
                        self.assertLessEqual(abs(ils - cap), 0.005 + 1e-9, "the shekel figure is the cap, shown to the agora")
                    else:
                        self.close(t * usd, cap, "dollars times the rate is the cap in shekels")
                        self.assertLessEqual(abs(ils - t * usd), 0.005 + 1e-9, "the shekel figure is the cap, shown to the agora")
                # the uplift is named when, and only when, it was applied (never on gifts; not in the sentences that apply no cap)
                if item["key"] not in ("gifts", "education") and variant not in ("none",):
                    self.assertEqual(bool(up), item["listed"], "uplift mark")
                self.assertEqual(numbers(item["english"]), numbers(item["explain"]), "the same figures in English")
                self.assertIsNone(HEBREW.search(item["english"]))
        # coverage: every kind of sentence the tool can write was exercised
        for combination in (("lodging7", "night"), ("lodgingAll", "all"), ("lodging90", "above"), ("lodging90", "upto"),
                            ("perDiem", "full"), ("perDiem", "partial"), ("car", "day"), ("gifts", "person"), ("education", "month")):
            self.assertGreater(seen.get(combination, 0), 0, combination)

    def test_the_per_diem_sentences_show_the_uplifted_rate_the_total_was_built_from(self):
        exact = self.seen["exact"]
        self.assertEqual(exact["full"]["explain"], "ימים: 5 · 213.75 דולר ליום (בלי הוצאות לינה) (כולל תוספת 25%) · נוסעים: 2 = 2137.5 דולר · לפי שער 3.5 = 7,481.25 ₪.")
        self.assertEqual(exact["full"]["english"], "Days: 5 · USD 213.75 per day (without lodging expenses) (including 25% uplift) · travellers: 2 = USD 2137.5 · at rate 3.5 = ILS 7,481.25.")
        self.assertEqual(exact["partial"]["explain"], "ימים עם לינה: 3 · 127.5 דולר; ימים בלי לינה: 2 · 213.75 דולר (כולל תוספת 25%) · נוסעים: 2 = 1620 דולר · לפי שער 3.5 = 5,670.00 ₪.")
        self.assertEqual(exact["partial"]["english"], "Days with lodging: 3 · USD 127.5; days without lodging: 2 · USD 213.75 (including 25% uplift) · travellers: 2 = USD 1620 · at rate 3.5 = ILS 5,670.00.")
        self.assertEqual(exact["withLodging"]["explain"], "ימים: 5 · 102 דולר ליום (עם הוצאות לינה) · נוסעים: 2 = 1020 דולר · לפי שער 3.5 = 3,570.00 ₪.")
        self.assertAlmostEqual(exact["full"]["cap"], 2137.5 * 3.5, delta=1e-9)       # the calculation itself is unchanged
        self.assertAlmostEqual(exact["partial"]["cap"], 1620 * 3.5, delta=1e-9)
        self.assertAlmostEqual(exact["withLodging"]["cap"], 1020 * 3.5, delta=1e-9)


class SentenceTranslationTests(unittest.TestCase):
    """Every complete sentence the calculation can build translates as a whole, with no Hebrew left."""

    def test_every_explanation_note_and_error_has_an_english_sentence(self):
        seen = calc(r"""
const sentences = new Set(), explains = new Set(); let models = 0;
function take(model) { models += 1;
  model.rows.forEach(item => { sentences.add(item.explain); explains.add(item.explain); sentences.add(item.label); if (item.note) { sentences.add(item.note); } });
  model.notes.forEach(note => sentences.add(note)); model.errors.forEach(error => sentences.add(error.message)); }
const nights = {depart: '2026-03-06', ret: '2026-03-25'}, long = {depart: '2026-01-01', ret: '2026-04-10'}, edu = {depart: '2026-03-06', ret: '2027-01-04'};
for (const listed of [false, true]) for (const year of [2018, 2024, 2025, 2026]) {
  [{rows: {lodging7: 4000, lodging90: 100, perDiem: 10, car: 10, gifts: 10, flight: 1, other: 1}},
   Object.assign({rows: {lodging90: 3900}}, nights), Object.assign({rows: {lodging90: 2340}}, nights),
   Object.assign({rows: {lodging90: 5200}}, nights), Object.assign({rows: {lodging90: 1950, lodging7: 1}}, nights),
   Object.assign({rows: {lodging7: 2000, lodging90: 20000, perDiem: 5}}, long),
   {travelers: 2, partial: true, lodgingDays: 3, rows: {lodging7: 1, perDiem: 1}},
   {businessDays: 3, partial: false, rows: {lodging7: 1}}, {depart: '2026-04-30', ret: '2026-04-30', rows: {flight: 1, insurance: [1, 'EUR'], phone: [1, 'JPY']}},
   {depart: '2026-12-31', ret: '2026-12-31', rows: {flight: 1}}, {rows: {insurance: [1, 'ILS']}},
   Object.assign({children: 2, rows: {education: 5, lodgingAll: 1, perDiem: 1}}, edu), Object.assign({children: 1, rows: {education: 5}}, edu)
  ].forEach(o => take(run(Object.assign({year, listed}, o))));
}
KEYS.forEach(key => take(run({rows: {[key]: -1}})));
KEYS.forEach(key => take(run({rows: {[key]: [1, 'XXX']}})));
[Object.assign({children: 1.5}, edu), Object.assign({children: -1}, edu), {businessDays: 0}, {businessDays: 9}, {partial: true, lodgingDays: 5}, {depart: '2026-03-06', ret: '2026-03-06', partial: true, lodgingDays: 1}, {partial: true, lodgingDays: 0}, {depart: '2026-03-10', ret: '2026-03-06'},
 {depart: '', ret: ''}, {travelers: 0}, {year: 2030}, {depart: '2025-12-31', ret: '2025-12-31'}, {rows: {insurance: [1, 'GBP']}}
].forEach(o => take(run(o)));
const bad = [...sentences].filter(text => /[֐-׿]/.test(text)).filter(text => { const english = translate(text); return english === null || /[֐-׿]/.test(english); });
// "1 nights" is wrong in both languages: a count never stands in front of a plural noun, it follows a label
const plural = [...explains].filter(text => /\d+ (לילות|ימים|נוסעים)/.test(text.replace(/^מעל 90 לילות:/, '')) || /\b\d+ (nights|days|travellers)\b/.test((translate(text) || '').replace(/^Over 90 nights:/, '')));
process.stdout.write(JSON.stringify({bad, plural, count: sentences.size, models}));
""")
        self.assertEqual(seen["bad"], [])
        self.assertGreater(seen["count"], 100)
        self.assertEqual(seen["plural"], [])

    def test_the_single_business_day_sentence_translates_to_the_agreed_english(self):
        seen = calc("""
const text = run({depart: '2026-03-06', ret: '2026-03-06', partial: true, lodgingDays: 1}).errors[0].message;
process.stdout.write(JSON.stringify(translate(text)));
""")
        self.assertEqual(seen, "There is only one business day, so it cannot be split into days with and without lodging. "
                               "Clear the checkbox or increase the number of business days.")

    def test_the_full_and_short_disclaimers_translate_to_the_agreed_english(self):
        seen = calc(r"""
const strings = %s;
process.stdout.write(JSON.stringify(strings.map(translate)));
""" % json.dumps([FULL_HE, SHORT_HE]))
        self.assertEqual(seen, [FULL_EN, SHORT_EN])


UI = r"""
const fs = require('fs'), os = require('os');
const LANG = %(lang)s, OUT = %(out)s;
global.window = {location: {hash: '#/accounting/travel'}, setTimeout() { return 0; }, clearTimeout() {}, Statso: {}};
const windowHandlers = {};
window.addEventListener = (type, fn) => { (windowHandlers[type] = windowHandlers[type] || []).push(fn); };
const state = {focus: null};
const store = {};
const els = new Proxy(store, {get: (target, id) => typeof id === 'string' ? (target[id] || (target[id] = mkEl(id))) : target[id]});
function mkEl(id) {
  return {id, value: '', checked: false, hidden: false, textContent: '', innerHTML: '', max: '', attrs: {}, handlers: {}, validity: {badInput: false},
    addEventListener(type, fn) { (this.handlers[type] = this.handlers[type] || []).push(fn); },
    getAttribute(name) { return name in this.attrs ? this.attrs[name] : null; },
    setAttribute(name, value) { this.attrs[name] = String(value); }, removeAttribute(name) { delete this.attrs[name]; },
    hasAttribute(name) { return name in this.attrs; }, focus() { state.focus = this.id; },
    click() { (this.handlers.click || []).forEach(fn => fn({target: this})); }, querySelectorAll() { return []; }};
}
// every write into a live region or an alert is counted: an unchanged message must not be written again
const writes = {};
function counted(id, prop, initial) {
  const e = mkEl(id); let held = initial || '';
  Object.defineProperty(e, prop, {get: () => held, set(v) { writes[id + '.' + prop] = (writes[id + '.' + prop] || 0) + 1; held = v; }});
  return e;
}
let serial = 0;
function travellers() {
  const host = mkEl('tt-travelers'); host.rows = [];
  host.querySelectorAll = () => host.rows.slice();
  Object.defineProperty(host, 'lastElementChild', {get: () => host.rows[host.rows.length - 1]});
  host.insertAdjacentHTML = (position, html) => {
    serial += 1;
    const row = {html, parts: {'.rent-option-title': mkEl(/id="(tt-person-title-\d+)"/.exec(html)[1]), '.tt-remove': mkEl(/id="(tt-person-remove-\d+)"/.exec(html)[1]),
      '.tt-name': mkEl('name-' + serial), '.tt-role': mkEl('role-' + serial)},
      querySelector(sel) { return this.parts[sel]; }, remove() { host.rows.splice(host.rows.indexOf(this), 1); }};
    host.rows.push(row);
  };
  return host;
}
els['tt-travelers'] = travellers();
['tt-rates', 'tt-error', 'tt-year-note', 'tt-days-note', 'tt-total-days'].forEach(id => {
  els[id] = counted(id, id === 'tt-rates' ? 'innerHTML' : 'textContent');
});
// the mode and status areas of the groups that come and go, and every live cap: none may be rewritten when nothing changed
els['tt-lodging-mode'] = counted('tt-lodging-mode', 'textContent'); els['tt-lodging-kept'] = counted('tt-lodging-kept', 'textContent');
els['tt-education-mode'] = counted('tt-education-mode', 'textContent', %(educationMode)s); els['tt-education-kept'] = counted('tt-education-kept', 'textContent');
['lodging7', 'lodging90', 'lodgingAll', 'perDiem', 'car', 'gifts', 'education'].forEach(key => { els['tt-' + key + '-cap'] = counted('tt-' + key + '-cap', 'innerHTML'); });
els['result-live'] = mkEl('result-live');
global.document = {title: 't', addEventListener() {}, getElementById(id) { return els[id] || (els[id] = mkEl(id)); },
  querySelectorAll(selector) { const m = /data-error-flag="([^"]+)"/.exec(selector);
    return m ? Object.values(els).filter(e => e.attrs['data-error-flag'] === m[1]) : []; }};
""" + module("statso-core.js") + module("statso-xlsx.js") + module("statso-export.js") + module("statso-docx.js") \
    + module("statso-lang-en.js") + TRANSLATE + r"""
const S = window.Statso;
const KEYS = %(keys)s, ALL = %(allkeys)s;
const FX = {USD: {unit: 1, dates: ['2026-01-01', '2026-03-05'], rates: [3.6, 3.5]},
  EUR: {unit: 1, dates: ['2026-03-05'], rates: [4.0]}, JPY: {unit: 100, dates: ['2026-03-05'], rates: [2.4]}};
const said = [];
S.i18n = LANG === 'en'
  ? {t: text => { said.push(text); const english = translate(text); return english === null ? text : english; }, current: () => 'en', locale: () => 'en-GB', apply() {}, onChange(fn) { S.i18n.listener = fn; }}
  : {t: text => text, current: () => 'he', locale: () => 'he-IL', apply() {}, onChange(fn) { S.i18n.listener = fn; }};
let loads = 0, reject = false;
S.data = {loadFxDaily() { loads += 1; return reject ? Promise.reject(new Error('x')) : Promise.resolve({currencies: FX}); }};
S.exporter.downloadWorkbook = (name, sheets, meta) => { fs.writeFileSync(OUT + '/' + LANG + '.xlsx', Buffer.from(S.xlsx.build(sheets, meta))); out.files.xlsx = name; };
S.exporter.downloadBytes = (name, bytes, mime) => { fs.writeFileSync(OUT + '/' + LANG + '.docx', Buffer.from(bytes)); out.files.docx = name; out.files.docxMime = mime; };
// what the real printDocument does before printing: the i18n engine translates every text node except the visitor's own
function emulateApply(html) {
  let skip = 0;
  return html.split(/(<[^>]+>)/).map(token => {
    if (token.startsWith('</')) { if (skip && /^<\/(td|span)>/.test(token)) { skip -= 1; } return token; }
    if (token.startsWith('<')) { if (/^<(td|span)\b[^>]*data-i18n-skip/.test(token)) { skip += 1; } return token; }
    if (skip || !/[\u0590-\u05ff]/.test(token)) { return token; }
    const plain = token.replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');
    const english = translate(plain);
    return english === null ? token : S.xlsx.escapeXml(english);
  }).join('');
}
S.exporter.printDocument = (title, html) => { out.pdf = {title, html, translated: LANG === 'en' ? emulateApply(html) : html}; return true; };
S.exporter.stamp = () => '20261120';
require(%(travel)s);
const T2 = S.travel;
const out = {files: {}};
const fire = (id, type) => (els['tt-form'].handlers[type || 'input'] || []).forEach(fn => fn({target: els[id]}));
const tick = () => new Promise(resolve => setTimeout(resolve, 0));
const host = els['tt-travelers'];
const snapshot = () => ({
  year: els['tt-year'].value, country: els['tt-country'].value, otherHidden: els['tt-country-other-wrap'].hidden,
  currencies: KEYS.map(key => els['tt-' + key + '-currency'].value), outputHidden: els['tt-output'].hidden,
  error: els['tt-error'].textContent, rates: els['tt-rates'].innerHTML, travellers: host.rows.length,
  removeHidden: host.rows.map(r => r.querySelector('.tt-remove').hidden), titles: host.rows.map(r => r.querySelector('.rent-option-title').textContent),
  count: els['tt-traveler-count'].textContent, live: els['result-live'].textContent, focus: state.focus,
  business: els['tt-business-days'].value, totalDays: els['tt-total-days'].textContent, yearNote: els['tt-year-note'].textContent,
  daysNote: els['tt-days-note'].textContent, lodgingDaysHidden: els['tt-lodging-days-wrap'].hidden, summary: els['tt-summary'].innerHTML,
  body: els['tt-body'].innerHTML, foot: els['tt-foot'].innerHTML, notes: els['tt-notes'].innerHTML,
  invalid: Object.values(els).filter(e => e.attrs['aria-invalid'] === 'true').map(e => e.id).sort(),
  described: els['tt-business-days'].attrs['aria-describedby'] || '',
  caps: Object.fromEntries(ALL.map(key => [key, els['tt-' + key + '-cap'].innerHTML])),
  groupsHidden: Object.fromEntries(['lodging7', 'lodging90', 'lodgingAll', 'education'].map(key => [key, els['tt-' + key + '-group'].hidden])),
  modes: {lodging: els['tt-lodging-mode'].textContent, lodgingKept: els['tt-lodging-kept'].textContent,
    education: els['tt-education-mode'].textContent, educationKept: els['tt-education-kept'].textContent}});
%(steps)s
"""


EDUCATION_MODE_HE = re.search(r'id="tt-education-mode" role="status">(.*?)</p>', HTML).group(1)


def ui(lang, out, steps):
    return node(UI % {"lang": json.dumps(lang), "out": json.dumps(str(out)), "keys": json.dumps(KEYS), "allkeys": json.dumps(ALL_KEYS),
                      "educationMode": json.dumps(EDUCATION_MODE_HE),
                      "travel": json.dumps(str(ROOT / "assets/statso-travel.js")), "steps": steps})


FLOW = r"""
(async () => {
  const o = {};
  window.location.hash = '#/';
  T2.init(); await tick();
  o.offRoute = {loads, rates: els['tt-rates'].innerHTML};
  window.location.hash = '#/accounting/travel';
  (windowHandlers.hashchange || []).forEach(fn => fn()); await tick();
  (windowHandlers.hashchange || []).forEach(fn => fn()); await tick();
  o.loads = loads;
  o.initial = snapshot();
  o.allCurrencies = ALL.map(key => els['tt-' + key + '-currency'].value);
  o.educationOptions = els['tt-education-currency'].innerHTML;
  o.yearOptions = els['tt-year'].innerHTML; o.countryOptions = els['tt-country'].innerHTML;
  o.currencyOptions = els['tt-flight-currency'].innerHTML;
  o.firstRow = host.rows[0].html;
  // dates alone: business days follow the total
  els['tt-depart'].value = '2026-03-06'; els['tt-return'].value = '2026-03-10'; fire('tt-return', 'change');
  o.dates = snapshot();
  // user text
  els['tt-company'].value = 'חברת "בדיקה" & <שותפים>'; els['tt-account'].value = 'כרטיס 7000'; els['tt-purpose'].value = 'כנס מקצועי';
  els['tt-country'].value = '21'; fire('tt-country', 'change');
  host.rows[0].querySelector('.tt-name').value = 'דנה כהן'; host.rows[0].querySelector('.tt-role').value = 'מנהלת כספים';
  els['tt-lodging7-amount'].value = '4000'; fire('tt-lodging7-amount');
  els['tt-flight-amount'].value = '1000'; els['tt-flight-currency'].value = 'EUR'; fire('tt-flight-amount');
  els['tt-other-amount'].value = '50'; els['tt-other-desc'].value = 'מתנות <ללקוחות>'; fire('tt-other-amount');
  o.calc = snapshot();
  // typing the same values again rewrites nothing that a screen reader would announce
  const before = JSON.stringify(writes);
  fire('tt-other-amount'); fire('tt-other-amount');
  o.stableWrites = JSON.stringify(writes) === before;
  // travellers
  els['tt-add-traveler'].click();
  o.added = snapshot();
  host.rows[1].querySelector('.tt-name').value = 'יוסי לוי';
  host.rows[0].querySelector('.tt-remove').click();
  o.removed = snapshot();
  o.survivor = host.rows[0].querySelector('.tt-name').value;
  host.rows[0].querySelector('.tt-remove').click();     // the only row's button is hidden: this is a no-op
  o.single = snapshot();
  els['tt-add-traveler'].click(); els['tt-add-traveler'].click();
  host.rows[2].querySelector('.tt-remove').click();
  o.removedLast = snapshot();
  // errors
  els['tt-business-days'].value = '9'; fire('tt-business-days');
  o.error = snapshot();
  els['tt-business-days'].value = '3'; fire('tt-business-days');
  o.fewerDays = snapshot();
  els['tt-partial'].checked = true; els['tt-lodging-days'].value = '2'; fire('tt-partial', 'change');
  o.partial = snapshot();
  els['tt-lodging-days'].value = '3'; fire('tt-lodging-days');
  o.partialError = snapshot();
  els['tt-partial'].checked = false; els['tt-business-days'].value = '5'; fire('tt-partial', 'change');
  els['tt-year'].value = '2025'; fire('tt-year', 'change');
  o.yearMismatch = snapshot();
  els['tt-year'].value = '2026'; fire('tt-year', 'change');
  els['tt-return'].value = '2026-03-30'; fire('tt-return', 'change');
  o.laterDates = snapshot();
  // a departure with no rate near it
  els['tt-depart'].value = '2026-06-01'; els['tt-return'].value = '2026-06-05'; fire('tt-return', 'change');
  o.stale = snapshot();
  els['tt-depart'].value = '2026-03-06'; els['tt-return'].value = '2026-03-10'; els['tt-business-days'].value = '5'; fire('tt-return', 'change');
  o.shortAgain = snapshot();
  // the currency chosen for a group is the currency its cap is shown in
  els['tt-lodging7-currency'].value = 'EUR'; fire('tt-lodging7-currency', 'change');
  o.eur = snapshot();
  els['tt-lodging7-currency'].value = 'USD'; fire('tt-lodging7-currency', 'change');
  // over 90 nights: the lodging is one row; what was typed in the two other rows is kept but is not in the sum
  els['tt-return'].value = '2026-06-15'; els['tt-business-days'].value = '102'; fire('tt-business-days');
  o.longStay = snapshot();
  els['tt-lodgingAll-amount'].value = '1000'; fire('tt-lodgingAll-amount');
  o.longStayAmount = snapshot();
  const beforeRetype = JSON.stringify(writes);
  fire('tt-lodgingAll-amount'); fire('tt-lodgingAll-amount');
  o.longStayStable = JSON.stringify(writes) === beforeRetype;
  // back to five days: the two rows count again, and the all-nights amount is kept aside
  els['tt-return'].value = '2026-03-10'; els['tt-business-days'].value = '5'; fire('tt-business-days');
  o.backToShort = snapshot();
  // a stay of over 10 months offers children's education: 305 days is in, 304 is out
  els['tt-return'].value = '2026-12-31'; els['tt-business-days'].value = '300'; fire('tt-business-days');
  o.education304 = snapshot();
  els['tt-return'].value = '2027-01-04'; els['tt-business-days'].value = '305'; fire('tt-business-days');
  o.education305 = snapshot();
  els['tt-children'].value = '2'; els['tt-education-amount'].value = '3000'; fire('tt-education-amount');
  o.educationRow = snapshot();
  els['tt-children'].value = '2.5'; fire('tt-children');
  o.childrenError = snapshot();
  els['tt-children'].value = '2'; fire('tt-children');
  const beforeEducation = JSON.stringify(writes);
  fire('tt-children'); fire('tt-children');
  o.educationStable = JSON.stringify(writes) === beforeEducation;
  els['tt-return'].value = '2026-03-10'; els['tt-business-days'].value = '5'; fire('tt-business-days');
  o.educationGone = snapshot();
  // exports: the visitor's own words, two travellers
  host.rows[0].querySelector('.tt-name').value = 'דנה כהן'; host.rows[0].querySelector('.tt-role').value = 'מנהלת כספים';
  host.rows[1].querySelector('.tt-name').value = 'יוסי לוי'; fire('tt-company');
  els['tt-xlsx'].click(); els['tt-pdf'].click(); els['tt-docx'].click();
  o.said = said;
  o.files = out.files; o.pdf = out.pdf;
  process.stdout.write(JSON.stringify(o));
})();
"""


class FormBehaviourTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.dir = Path(cls.temp.name)
        cls.he = ui("he", cls.dir, FLOW)
        cls.en = ui("en", cls.dir, FLOW)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_defaults_year_is_the_latest_in_the_table_destination_is_other_and_every_currency_is_the_dollar(self):
        initial = self.he["initial"]
        self.assertEqual(initial["year"], "2026")
        self.assertEqual(initial["country"], "other")
        self.assertEqual(initial["currencies"], ["USD"] * 11)
        self.assertFalse(initial["otherHidden"])
        self.assertTrue(initial["outputHidden"])               # nothing is shown, and no error, before the first change
        self.assertEqual(initial["error"], "")
        years = re.findall(r'value="(\d+)"', self.he["yearOptions"])
        self.assertEqual(years, [str(year) for year in range(2018, 2027)])
        self.assertNotIn('value=""', self.he["yearOptions"])
        self.assertEqual(self.he["countryOptions"].count("<option"), 29)
        self.assertTrue(self.he["countryOptions"].startswith('<option value="other">מדינה אחרת</option>'))
        self.assertEqual(self.he["currencyOptions"].count("<option"), 11)

    def test_the_rates_load_only_on_the_tool_route_and_once(self):
        self.assertEqual(self.he["offRoute"]["loads"], 0)
        self.assertIn("טוען שערי חליפין", self.he["offRoute"]["rates"])
        self.assertEqual(self.he["loads"], 1)
        self.assertEqual(self.he["initial"]["rates"], "")

    def test_the_first_traveller_row_is_named_numbered_and_cannot_be_removed(self):
        initial = self.he["initial"]
        self.assertEqual((initial["travellers"], initial["titles"], initial["removeHidden"]), (1, ["נוסע 1"], [True]))
        self.assertEqual(initial["count"], "מספר הנוסעים: 1.")
        row = self.he["firstRow"]
        self.assertIn('role="group" aria-labelledby="tt-person-title-1"', row)
        self.assertIn('aria-labelledby="tt-person-remove-1 tt-person-title-1"', row)
        self.assertIn('autocomplete="name"', row)

    def test_business_days_follow_the_total_until_edited_and_a_shorter_count_is_said_in_words(self):
        self.assertEqual(self.he["dates"]["business"], "5")
        self.assertEqual(self.he["dates"]["totalDays"], "סה״כ ימי הנסיעה: 5.")
        self.assertEqual(self.he["fewerDays"]["daysNote"], "הימים העסקיים (3) פחותים מסך ימי הנסיעה (5).")
        self.assertEqual(self.he["calc"]["daysNote"], "")

    def test_a_calculation_shows_the_summary_the_table_the_total_row_and_the_notes(self):
        calc = self.he["calc"]
        self.assertFalse(calc["outputHidden"])
        self.assertEqual(calc["error"], "")
        self.assertEqual(calc["body"].count("<tr>"), 11)
        self.assertEqual(calc["body"].count('<th scope="row">'), 11)
        self.assertEqual(calc["foot"].count("<tr>"), 1)
        self.assertIn("סה״כ", calc["foot"])
        self.assertEqual(calc["summary"].count("rent-summary-card"), 3)
        self.assertIn("סה״כ סכום שולם (בש״ח)", calc["summary"])
        self.assertIn("סה״כ הוצאה מוכרת", calc["summary"])
        self.assertIn("סה״כ סכום לתיאום", calc["summary"])
        self.assertNotIn("! שימו לב", calc["body"])             # the first-class sentence is only in the "!" button now
        self.assertNotIn("! שימו לב", calc["notes"])
        self.assertNotIn("חינוך ילדים", calc["notes"])           # a short trip: no education rule
        # France is a listed country (uplifted); the rate line names the date it comes from
        self.assertIn("שער יציג שפורסם ל־05/03/2026", calc["rates"])
        self.assertIn("(כולל תוספת 25%)", calc["body"])

    def test_text_the_visitor_typed_is_marked_so_that_it_is_never_translated(self):
        self.assertIn('<span dir="auto" data-i18n-skip>מתנות &lt;ללקוחות&gt;</span>', self.he["calc"]["body"])
        self.assertIn('<span dir="auto" data-i18n-skip>מתנות &lt;ללקוחות&gt;</span>', self.en["calc"]["body"])

    def test_unchanged_messages_are_not_written_again(self):
        self.assertTrue(self.he["stableWrites"])
        self.assertTrue(self.en["stableWrites"])

    def test_adding_and_removing_travellers_moves_focus_renumbers_and_announces(self):
        added = self.he["added"]
        self.assertEqual((added["travellers"], added["titles"], added["removeHidden"]), (2, ["נוסע 1", "נוסע 2"], [False, False]))
        self.assertEqual(added["focus"], "name-2")                 # the new row's name field
        self.assertEqual(added["live"], "נוסע 2 נוסף. מספר הנוסעים: 2.")
        self.assertEqual(added["count"], "מספר הנוסעים: 2.")
        removed = self.he["removed"]
        self.assertEqual((removed["travellers"], removed["titles"], removed["removeHidden"]), (1, ["נוסע 1"], [True]))
        self.assertEqual(removed["focus"], "name-2")              # the row that took the removed row's place
        self.assertEqual(removed["live"], "נוסע 1 הוסר. מספר הנוסעים: 1.")
        self.assertEqual(self.he["survivor"], "יוסי לוי")
        self.assertEqual(self.he["single"]["travellers"], 1)
        last = self.he["removedLast"]
        self.assertEqual((last["travellers"], last["titles"]), (2, ["נוסע 1", "נוסע 2"]))
        self.assertEqual(last["focus"], "name-3")                  # the last row was removed: focus goes to the one before it
        self.assertEqual(last["live"], "נוסע 3 הוסר. מספר הנוסעים: 2.")

    def test_all_thirteen_groups_get_the_currency_list_and_start_in_dollars(self):
        self.assertEqual(self.he["allCurrencies"], ["USD"] * 13)
        self.assertEqual(self.he["educationOptions"].count("<option"), 11)

    def test_every_cap_is_there_before_the_first_touch_with_its_rate_and_the_reason(self):
        caps = self.he["initial"]["caps"]
        for key in CAP_KEYS:
            with self.subTest(group=key):
                self.assertIn('<p class="travel-cap-value"><span>תקרה מותרת:</span> <span>', caps[key])
                self.assertIn("דולר", caps[key])
                self.assertIn("יש להזין תאריכים לחישוב התקרה.", caps[key])
        self.assertIn("365 דולר ללילה לנוסע", caps["lodging7"])
        self.assertEqual(caps["flight"], "")                                      # no cap: the markup already says so, in plain text
        self.assertEqual(self.en["initial"]["caps"]["lodging7"].count("USD 365 per night per traveller"), 1)

    def test_a_cap_is_a_label_the_figure_and_the_sentence_that_the_table_row_also_says(self):
        cap = self.he["calc"]["caps"]["lodging7"]
        self.assertRegex(cap, r'^<p class="travel-cap-value"><span>תקרה מותרת:</span> <strong dir="ltr">[\d,]+\.\d\d</strong> <span>USD</span></p>'
                              r'<p class="travel-cap-explain">תקרה: 456.25 דולר ללילה \(כולל תוספת 25%\) · לילות: 5 · נוסעים: 1 = ')
        explain = re.search(r'<p class="travel-cap-explain">(.*?)</p>', cap).group(1)
        table = re.search(r'<th scope="row">לינה — 7 הלילות הראשונים</th>.*?<td class="travel-explain">(.*?)</td>', self.he["calc"]["body"]).group(1)
        self.assertEqual(explain, table)
        self.assertNotIn("role=", cap)                                            # read with the field, never announced on its own

    def test_the_currency_of_a_group_is_the_currency_of_its_cap(self):
        eur = self.he["eur"]["caps"]["lodging7"]
        self.assertIn("<span>EUR</span>", eur)
        self.assertRegex(eur, r"המרה ל־EUR: [\d,]+\.\d\d ₪ ÷ 4 = [\d,]+\.\d\d EUR\.")
        self.assertIn("<span>USD</span>", self.he["shortAgain"]["caps"]["lodging7"])
        self.assertNotIn("EUR", self.he["shortAgain"]["caps"]["lodging7"])
        self.assertIn("Conversion to EUR: ILS", self.en["eur"]["caps"]["lodging7"])

    def test_over_ninety_nights_there_is_one_lodging_group_and_the_hidden_amounts_stay_out_of_the_sum(self):
        short, long, amount, back = (self.he[name] for name in ("shortAgain", "longStay", "longStayAmount", "backToShort"))
        self.assertEqual(short["groupsHidden"], {"lodging7": False, "lodging90": False, "lodgingAll": True, "education": True})
        self.assertEqual(long["groupsHidden"], {"lodging7": True, "lodging90": True, "lodgingAll": False, "education": True})
        self.assertEqual(long["modes"]["lodging"], "בשל נסיעה של מעל 90 לילות יש להזין את הלינה בשורה אחת.")
        self.assertIn("נשמרו, אך אינם נכללים בחישוב", long["modes"]["lodgingKept"])        # the 4000 typed in the first group
        rows = re.findall(r'<th scope="row">(.*?)</th>', long["body"])
        self.assertIn("לינה — כל הלילות (מעל 90 לילות)", rows)
        self.assertFalse(any(label.startswith("לינה — ") and "כל הלילות" not in label for label in rows))
        self.assertIn("4,175.00", long["foot"])                                         # the flight and the others only: the 4000 is not in
        self.assertIn("7,675.00", amount["foot"])                                       # 1000 dollars typed into the one group
        self.assertEqual(short["modes"]["lodging"], "")
        # back to five days the two groups count again and what was typed in the other one is kept, said, and out
        self.assertEqual(back["groupsHidden"], short["groupsHidden"])
        self.assertIn("נשמר, אך אינו נכלל בחישוב", back["modes"]["lodgingKept"])
        self.assertIn("18,175.00", back["foot"])
        self.assertIn("18,175.00", short["foot"])
        self.assertEqual(self.he["longStay"]["caps"]["lodgingAll"].count("מעל 90 לילות: כל הלילות"), 1)

    def test_children_education_is_offered_from_305_days_and_asks_for_the_number_of_children(self):
        below, above, row_ = self.he["education304"], self.he["education305"], self.he["educationRow"]
        self.assertTrue(below["groupsHidden"]["education"])
        self.assertIn("חינוך ילדים מחושב רק בנסיעה העולה על 10 חודשים", below["modes"]["education"])
        self.assertFalse(above["groupsHidden"]["education"])
        self.assertEqual(above["modes"]["education"], "")
        self.assertIn("ילדים: 0", above["caps"]["education"])                             # no children typed yet
        labels = re.findall(r'<th scope="row">(.*?)</th>', row_["body"])
        self.assertEqual(labels[-1], "חינוך ילדים")
        self.assertIn("ילדים: 2", row_["caps"]["education"])
        self.assertIn("<p>סכום החינוך לילד לחודש בשנת 2026 (914 דולר) נלקח מאתרי רואי חשבון ולא ממקור רשמי.</p>", row_["body"])
        self.assertIn("תקנה 2(2)(ז)", row_["notes"])
        bad = self.he["childrenError"]
        self.assertEqual(bad["error"], "מספר הילדים חייב להיות מספר שלם שאינו שלילי.")
        self.assertIn("tt-children", bad["invalid"])
        self.assertIn("התקרה תחושב לאחר תיקון השגיאה בטופס.", bad["caps"]["education"])
        gone = self.he["educationGone"]
        self.assertTrue(gone["groupsHidden"]["education"])
        self.assertNotIn("חינוך ילדים", re.findall(r'<th scope="row">(.*?)</th>', gone["body"]))
        self.assertIn("נשמר, אך אינו נכלל בחישוב", gone["modes"]["educationKept"])
        self.assertNotIn("תקנה 2(2)(ז)", gone["notes"])

    def test_typing_again_in_the_long_modes_rewrites_nothing_that_is_announced(self):
        self.assertTrue(self.he["longStayStable"])
        self.assertTrue(self.he["educationStable"])
        self.assertTrue(self.en["longStayStable"])
        self.assertTrue(self.en["educationStable"])

    def test_the_english_screen_has_no_hebrew_in_the_caps_or_the_mode_notes(self):
        for name in ("initial", "calc", "eur", "shortAgain", "longStay", "longStayAmount", "backToShort", "education304", "education305",
                     "educationRow", "childrenError", "educationGone"):
            snap = self.en[name]
            text = " ".join(list(snap["caps"].values()) + list(snap["modes"].values()) + [snap["body"], snap["notes"], snap["error"]])
            text = re.sub(r'<span dir="auto" data-i18n-skip>.*?</span>', "", text)
            with self.subTest(snapshot=name):
                self.assertIsNone(HEBREW.search(text), HEBREW.findall(text)[:5])
        self.assertIn("Because the trip is over 90 nights, enter the lodging in a single row.", self.en["longStay"]["modes"]["lodging"])
        self.assertIn("Children’s education is calculated only on a trip of over 10 months", self.en["education304"]["modes"]["education"])
        self.assertIn("accountants’ websites", self.en["educationRow"]["body"])
        self.assertIn("regulation 2(2)(g)", self.en["educationRow"]["notes"])

    def test_the_number_of_traveller_rows_is_the_number_of_travellers_in_the_calculation(self):
        one, two = self.he["calc"]["body"], self.he["added"]["body"]
        self.assertNotEqual(one, two)                              # per-person caps changed with the second row

    def test_a_wrong_business_day_count_is_an_alert_and_marks_the_field(self):
        error = self.he["error"]
        self.assertTrue(error["outputHidden"])
        self.assertEqual(error["error"], "מספר הימים העסקיים חייב להיות שלם בטווח 1 עד 5.")
        self.assertIn("tt-business-days", error["invalid"])
        self.assertIn("tt-error", error["described"])
        fixed = self.he["fewerDays"]
        self.assertEqual((fixed["error"], fixed["invalid"]), ("", []))
        self.assertFalse(fixed["outputHidden"])

    def test_partial_per_diem_shows_the_lodging_days_field_and_checks_its_range(self):
        self.assertFalse(self.he["partial"]["lodgingDaysHidden"])
        self.assertFalse(self.he["partial"]["outputHidden"])
        self.assertTrue(self.he["fewerDays"]["lodgingDaysHidden"])
        self.assertEqual(self.he["partialError"]["error"], "מספר ימי הלינה לא יעלה על 2")
        self.assertIn("tt-lodging-days", self.he["partialError"]["invalid"])

    def test_another_year_for_the_dates_is_a_visible_non_blocking_note(self):
        note = self.he["yearMismatch"]
        self.assertTrue(note["yearNote"].startswith("שימו לב:"))
        self.assertFalse(note["outputHidden"])
        self.assertEqual(note["error"], "")
        self.assertEqual(self.he["calc"]["yearNote"], "")

    def test_an_old_rate_is_warned_about_in_the_rates_area_with_its_date(self):
        stale = self.he["stale"]
        self.assertFalse(stale["outputHidden"])
        self.assertIn("שימו לב: אין שער בטווח 7 ימים", stale["rates"])
        self.assertIn("05/03/2026", stale["rates"])

    def test_every_sentence_the_form_says_translates(self):
        said = set(self.en["said"])
        self.assertGreater(len(said), 40)
        seen = node(TRANSLATE_SETUP + "const said = %s;\nprocess.stdout.write(JSON.stringify(said.filter(text => /[\\u0590-\\u05ff]/.test(text)).filter(text => { const english = translate(text); return english === null || /[\\u0590-\\u05ff]/.test(english); })));" % json.dumps(sorted(said)))
        self.assertEqual(seen, [])

    def test_the_english_screen_has_no_hebrew_except_what_the_visitor_typed(self):
        for name in ("calc", "added", "error", "stale", "yearMismatch", "partialError"):
            snap = self.en[name]
            text = " ".join(str(snap[key]) for key in ("error", "rates", "body", "foot", "summary", "notes", "yearNote", "daysNote",
                                                       "totalDays", "count", "live"))
            text = re.sub(r'<span dir="auto" data-i18n-skip>.*?</span>', "", text)
            with self.subTest(snapshot=name):
                self.assertIsNone(HEBREW.search(text), HEBREW.findall(text))
        self.assertEqual(self.en["added"]["live"], "Traveller 2 added. Number of travellers: 2.")
        self.assertEqual(self.en["removed"]["live"], "Traveller 1 removed. Number of travellers: 1.")
        self.assertEqual(self.en["added"]["titles"], ["Traveller 1", "Traveller 2"])
        self.assertTrue(self.en["yearMismatch"]["yearNote"].startswith("Please note:"))
        self.assertEqual(self.en["error"]["error"], "Business days must be an integer from 1 to 5.")


TRANSLATE_SETUP = "global.window = {}; global.document = {addEventListener() {}};\n" + module("statso-lang-en.js") + TRANSLATE


class ExportFileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.dir = Path(cls.temp.name)
        cls.results = {lang: ui(lang, cls.dir, FLOW) for lang in ("he", "en")}

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def docx(self, lang):
        archive = zipfile.ZipFile(self.dir / (lang + ".docx"))
        return archive, {name: archive.read(name).decode("utf-8") for name in archive.namelist()}

    def xlsx(self, lang):
        archive = zipfile.ZipFile(self.dir / (lang + ".xlsx"))
        return archive, {name: archive.read(name).decode("utf-8") for name in archive.namelist()}

    def test_file_names_follow_the_language_and_carry_the_date(self):
        self.assertEqual(self.results["he"]["files"]["xlsx"], "statso-דו״ח נסיעה לחו״ל-20261120.xlsx")
        self.assertEqual(self.results["he"]["files"]["docx"], "statso-דו״ח נסיעה לחו״ל-20261120.docx")
        self.assertEqual(self.results["en"]["files"]["xlsx"], "statso-Foreign Travel Report-20261120.xlsx")
        self.assertEqual(self.results["en"]["files"]["docx"], "statso-Foreign Travel Report-20261120.docx")
        self.assertEqual(self.results["en"]["files"]["docxMime"],
                         "application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    def test_the_workbook_has_two_sheets_values_only_a_frozen_header_and_the_disclaimer(self):
        for lang, names, disclaimer in (("he", ["פרטי הנסיעה", "חישוב ההוצאות"], FULL_HE), ("en", ["Trip details", "Expense calculation"], FULL_EN)):
            with self.subTest(lang=lang):
                archive, parts = self.xlsx(lang)
                self.assertIsNone(archive.testzip())
                sheets = sorted(name for name in parts if name.startswith("xl/worksheets/"))
                self.assertEqual(len(sheets), 2)
                for name in sheets:
                    self.assertNotIn("<f>", parts[name])
                    self.assertNotIn("mergeCell", parts[name])
                    self.assertIn('ySplit="3"', parts[name])
                    ET.fromstring(parts[name])
                workbook = parts["xl/workbook.xml"]
                for name in names:
                    self.assertIn(name, workbook)
                self.assertIn(disclaimer, parts["xl/worksheets/sheet2.xml"])
                self.assertIn("Foreign Travel Report" if lang == "en" else "דו״ח נסיעה לחו״ל", parts["docProps/core.xml"])
                self.assertIn(("en-GB" if lang == "en" else "he-IL"), parts["docProps/core.xml"])

    def test_row_two_of_the_details_sheet_is_the_short_disclaimer_in_the_sheets_language(self):
        for lang, short in (("he", SHORT_HE), ("en", SHORT_EN)):
            with self.subTest(lang=lang):
                _, parts = self.xlsx(lang)
                row = re.search(r'<row r="2">(.*?)</row>', parts["xl/worksheets/sheet1.xml"], re.S).group(1)
                self.assertIn(short, row)

    def test_the_workbook_keeps_the_visitors_own_words_in_both_languages(self):
        for lang in ("he", "en"):
            with self.subTest(lang=lang):
                _, parts = self.xlsx(lang)
                details = parts["xl/worksheets/sheet1.xml"]
                for text in ("חברת &quot;בדיקה&quot; &amp; &lt;שותפים&gt;", "כרטיס 7000", "כנס מקצועי", "דנה כהן", "מנהלת כספים"):
                    self.assertIn(text, details)
                for text in ("חברת", "מנהלת"):
                    self.assertNotIn("EN:" + text, details)

    def test_the_english_workbook_has_no_hebrew_beyond_the_visitors_words(self):
        _, parts = self.xlsx("en")
        user = ["חברת &quot;בדיקה&quot; &amp; &lt;שותפים&gt;", "כרטיס 7000", "כנס מקצועי", "דנה כהן", "מנהלת כספים", "מתנות &lt;ללקוחות&gt;", "יוסי לוי"]
        for name, text in parts.items():
            if not name.endswith(".xml") or name.startswith("_rels"):
                continue
            for phrase in user:
                text = text.replace(phrase, "")
            with self.subTest(part=name):
                self.assertIsNone(HEBREW.search(text), HEBREW.findall(text)[:5])

    def test_the_workbook_total_row_holds_the_rounded_sums(self):
        _, parts = self.xlsx("he")
        sheet = parts["xl/worksheets/sheet2.xml"]
        rows = {int(number): body for number, body in re.findall(r'<row r="(\d+)">(.*?)</row>', sheet, re.S)}
        total = [float(value) for value in re.findall(r"<v>([^<]+)</v>", rows[15])]
        self.assertEqual(total, [18175.0, 18175.0, 0.0])           # paid, recognised, to adjust: dollar lodging, euro flight and others

    def test_the_pdf_sheet_is_semantic_titled_and_carries_the_short_disclaimer_and_the_full_one(self):
        for lang, short, full in (("he", SHORT_HE, FULL_HE), ("en", SHORT_EN, FULL_EN)):
            with self.subTest(lang=lang):
                pdf = self.results[lang]["pdf"]
                self.assertEqual(pdf["title"], "דו״ח נסיעה לחו״ל")
                html = pdf["html"]
                self.assertEqual(html.count("<table>"), 4)
                self.assertEqual(html.count("<caption"), 4)
                self.assertGreaterEqual(html.count('<th scope="col">'), 8)
                self.assertIn(full, html)
                self.assertIn(short, html)
                self.assertIn("<h1>" + ("דו״ח נסיעה לחו״ל" if lang == "he" else "Foreign Travel Report") + "</h1>", html)
                self.assertNotIn("נתוני מקור: הלשכה המרכזית", html)
                self.assertIn('<td dir="auto" data-i18n-skip>', html)
                self.assertIn("&lt;שותפים&gt;", html)

    def test_the_pdf_footer_translates_as_a_whole(self):
        raw = self.results["en"]["pdf"]["html"]
        self.assertRegex(re.search(r"<footer class=\"print-foot\">(.*?)</footer>", raw).group(1), "^הופק ב־")
        footer = re.search(r"<footer class=\"print-foot\">(.*?)</footer>", self.results["en"]["pdf"]["translated"]).group(1)
        self.assertIsNone(HEBREW.search(footer), footer)
        self.assertTrue(footer.startswith("Produced "))
        self.assertIn(SHORT_EN, footer)

    def test_the_english_pdf_sheet_has_no_hebrew_beyond_the_visitors_words(self):
        html = self.results["en"]["pdf"]["translated"]
        html = re.sub(r'<td dir="auto" data-i18n-skip>.*?</td>', "", html)
        html = re.sub(r'<span dir="auto" data-i18n-skip>.*?</span>', "", html)
        self.assertIsNone(HEBREW.search(html), HEBREW.findall(html)[:5])

    def test_the_word_file_has_every_part_and_well_formed_xml(self):
        for lang in ("he", "en"):
            with self.subTest(lang=lang):
                archive, parts = self.docx(lang)
                self.assertIsNone(archive.testzip())
                self.assertEqual(set(parts), {"[Content_Types].xml", "_rels/.rels", "word/document.xml", "word/styles.xml",
                                              "word/footer1.xml", "word/_rels/document.xml.rels", "docProps/core.xml"})
                for name, text in parts.items():
                    ET.fromstring(text)

    def test_the_word_file_has_a_title_language_heading_styles_and_marked_table_headers(self):
        for lang, locale, title in (("he", "he-IL", "דו״ח נסיעה לחו״ל"), ("en", "en-GB", "Foreign Travel Report")):
            with self.subTest(lang=lang):
                _, parts = self.docx(lang)
                core = ET.fromstring(parts["docProps/core.xml"])
                self.assertEqual(core.find("{http://purl.org/dc/elements/1.1/}title").text, title)
                self.assertEqual(core.find("{http://purl.org/dc/elements/1.1/}language").text, locale)
                document = ET.fromstring(parts["word/document.xml"])
                styles = [p.find(W + "pPr").find(W + "pStyle").get(W + "val") for p in document.iter(W + "p")
                          if p.find(W + "pPr") is not None and p.find(W + "pPr").find(W + "pStyle") is not None]
                self.assertEqual(styles.count("Title"), 1)
                self.assertGreaterEqual(styles.count("Heading1"), 4)
                self.assertGreaterEqual(styles.count("Heading2"), 1)
                outline = {}
                for style in ET.fromstring(parts["word/styles.xml"]).iter(W + "style"):
                    level = style.find(W + "pPr").find(W + "outlineLvl") if style.find(W + "pPr") is not None else None
                    if level is not None:
                        outline[style.get(W + "styleId")] = level.get(W + "val")
                self.assertEqual(outline, {"Heading1": "0", "Heading2": "1"})
                tables = list(document.iter(W + "tbl"))
                self.assertEqual(len(tables), 4)
                for table in tables:
                    first = table.find(W + "tr")
                    self.assertIsNotNone(first.find(W + "trPr").find(W + "tblHeader"))
                    self.assertTrue(table.find(W + "tblPr").find(W + "tblCaption").get(W + "val"))
                    for cell in table.iter(W + "tc"):
                        self.assertIsNotNone(cell.find(W + "p"))
                    for later in table.findall(W + "tr")[1:]:
                        self.assertIsNone(later.find(W + "trPr"))
                for forbidden in ("gridSpan", "vMerge", "mergeCell"):
                    self.assertNotIn(forbidden, parts["word/document.xml"])

    def test_direction_marks_are_present_only_in_the_hebrew_word_file(self):
        for lang, expected in (("he", True), ("en", False)):
            with self.subTest(lang=lang):
                _, parts = self.docx(lang)
                for name in ("word/document.xml", "word/styles.xml", "word/footer1.xml"):
                    root = ET.fromstring(parts[name])
                    found = {tag: len(list(root.iter(W + tag))) for tag in ("bidi", "rtl", "bidiVisual")}
                    if expected:
                        self.assertGreater(found["bidi"], 0, name)
                    else:
                        self.assertEqual(found, {"bidi": 0, "rtl": 0, "bidiVisual": 0}, name)
                document = ET.fromstring(parts["word/document.xml"])
                self.assertEqual(len(list(document.iter(W + "bidiVisual"))) > 0, expected)
                lang_tag = next(document.iter(W + "lang"))
                self.assertEqual(lang_tag.get(W + "val"), "he-IL" if expected else "en-GB")
                self.assertEqual(lang_tag.get(W + "bidi"), "he-IL")

    def test_numbers_are_not_marked_right_to_left(self):
        _, parts = self.docx("he")
        document = ET.fromstring(parts["word/document.xml"])
        numeric = [p for p in document.iter(W + "p") if re.fullmatch(r"\d[\d,]*\.\d\d", "".join(t.text or "" for t in p.iter(W + "t")))]
        self.assertGreater(len(numeric), 10)
        for paragraph in numeric:
            self.assertIsNone(next(paragraph.iter(W + "rtl"), None))

    def test_the_word_file_carries_the_full_disclaimer_in_the_body_and_the_short_one_in_the_footer(self):
        for lang, short, full in (("he", SHORT_HE, FULL_HE), ("en", SHORT_EN, FULL_EN)):
            with self.subTest(lang=lang):
                _, parts = self.docx(lang)
                text = lambda name: "".join(t.text or "" for t in ET.fromstring(parts[name]).iter(W + "t"))
                self.assertIn(full, [("".join(t.text or "" for t in p.iter(W + "t"))) for p in ET.fromstring(parts["word/document.xml"]).iter(W + "p")])
                self.assertEqual(text("word/footer1.xml"), short)

    def test_the_word_file_keeps_the_visitors_own_words_and_the_english_one_has_no_other_hebrew(self):
        _, parts = self.docx("en")
        body = parts["word/document.xml"]
        user = ["חברת \"בדיקה\" & <שותפים>", "כרטיס 7000", "כנס מקצועי", "דנה כהן", "מנהלת כספים"]
        text = "".join(t.text or "" for t in ET.fromstring(body).iter(W + "t"))
        for phrase in user:
            self.assertIn(phrase, text)
        residue = body
        for phrase in ("חברת &quot;בדיקה&quot; &amp; &lt;שותפים&gt;", "חברת \"בדיקה\" &amp; &lt;שותפים&gt;", "כרטיס 7000", "כנס מקצועי", "דנה כהן",
                       "מנהלת כספים", "יוסי לוי", "מתנות &lt;ללקוחות&gt;"):
            residue = residue.replace(phrase, "")
        self.assertIsNone(HEBREW.search(re.sub(r"<[^>]+>", "", residue)), HEBREW.findall(re.sub(r"<[^>]+>", "", residue))[:5])
        for name in ("word/footer1.xml", "word/styles.xml", "docProps/core.xml"):
            self.assertIsNone(HEBREW.search(parts[name]), name)

    @unittest.skipUnless(Path("/usr/bin/textutil").exists(), "textutil is a macOS tool")
    def test_textutil_converts_the_word_files(self):
        for lang in ("he", "en"):
            with self.subTest(lang=lang):
                result = subprocess.run(["/usr/bin/textutil", "-convert", "txt", "-stdout", str(self.dir / (lang + ".docx"))],
                                        capture_output=True, text=True, encoding="utf-8")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("15,968.75", result.stdout)


DOCX_DRIVER = r"""
global.window = {};
require(%s); require(%s);
const S = window.Statso;
const bytes = S.docx.build(%s);
require('fs').writeFileSync(%s, Buffer.from(bytes));
"""


class DocxWriterTests(unittest.TestCase):
    def build(self, options):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "out.docx"
            script = DOCX_DRIVER % (json.dumps(str(ROOT / "assets/statso-xlsx.js")), json.dumps(str(ROOT / "assets/statso-docx.js")),
                                    json.dumps(options), json.dumps(str(path)))
            subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True, cwd=ROOT)
            with zipfile.ZipFile(path) as archive:
                return {name: archive.read(name).decode("utf-8") for name in archive.namelist()}

    def test_control_characters_that_xml_forbids_are_dropped_and_text_is_escaped(self):
        parts = self.build({"title": "t \x01 <x>", "language": "en-GB", "rtl": False, "footer": "f\x0b&", "created": 0,
                            "blocks": [{"type": "paragraph", "text": "a\x00b\x08c <&> \U0001F600"}]})
        for name, text in parts.items():
            ET.fromstring(text)
        document = ET.fromstring(parts["word/document.xml"])
        self.assertEqual("".join(t.text for t in document.iter(W + "t")), "abc <&> \U0001F600")

    def test_a_table_at_the_end_is_followed_by_a_paragraph(self):
        parts = self.build({"title": "t", "language": "en-GB", "rtl": False, "footer": "", "created": 0,
                            "blocks": [{"type": "table", "caption": "c", "head": ["a"], "rows": [[{"text": "1", "numeric": True}]]}]})
        body = ET.fromstring(parts["word/document.xml"]).find(W + "body")
        self.assertEqual([child.tag for child in body], [W + "tbl", W + "p", W + "sectPr"])

    def test_elements_follow_the_schema_order(self):
        parts = self.build({"title": "t", "language": "he-IL", "rtl": True, "footer": "f", "created": 0,
                            "blocks": [{"type": "title", "text": "t"}, {"type": "heading", "level": 2, "text": "h"},
                                       {"type": "table", "caption": "c", "head": ["a", "b"], "rows": [[{"text": "x"}, {"text": "1", "numeric": True}]]}]})
        order = {"pPr": ["pStyle", "keepNext", "bidi", "spacing", "jc", "outlineLvl"], "rPr": ["b", "bCs", "sz", "szCs", "rtl", "lang"],
                 "tblPr": ["tblStyle", "bidiVisual", "tblW", "tblLook", "tblCaption"], "sectPr": ["footerReference", "pgSz", "pgMar", "bidi"]}
        for name in ("word/document.xml", "word/styles.xml"):
            root = ET.fromstring(parts[name])
            for container, allowed in order.items():
                for node_ in root.iter(W + container):
                    tags = [child.tag.replace(W, "") for child in node_]
                    positions = [allowed.index(tag) for tag in tags if tag in allowed]
                    self.assertEqual(positions, sorted(positions), (name, container, tags))
        self.assertNotIn("<w:jc", parts["word/document.xml"])


class SourceTests(unittest.TestCase):
    def test_nothing_the_visitor_types_is_stored_in_the_browser(self):
        self.assertNotIn("localStorage", TRAVEL)
        self.assertNotIn("sessionStorage", TRAVEL)
        self.assertNotIn("document.cookie", TRAVEL)

    def test_every_alert_write_goes_through_flag_fields(self):
        self.assertIn("flagFields('tt-error'", TRAVEL)

    def test_the_two_new_scripts_are_registered_guarded_and_safe_to_inline(self):
        guard = re.search(r'<script id="script-guard">(.*?)</script>', HTML, re.S).group(1)
        required = re.findall(r"'([A-Za-z]+)'", re.search(r"var REQUIRED = \[(.*?)\]", guard, re.S).group(1))
        self.assertIn("travel", required)
        self.assertIn("docx", required)
        self.assertRegex(TRAVEL, r"(?m)^\s*Statso\.travel = \{")
        self.assertRegex(DOCX, r"(?m)^\s*Statso\.docx = \{")
        for name, source in (("travel", TRAVEL), ("docx", DOCX)):
            for forbidden in ("</script", "<!--", "-->", "merges", "mergeCell"):
                self.assertNotIn(forbidden, source, name)
        order = [HTML.index('src="assets/statso-%s.js"' % name) for name in ("export", "docx", "tools", "rent", "travel", "nav")]
        self.assertEqual(order, sorted(order))

    def test_the_source_disclaimers_equal_the_ones_on_the_page_and_in_the_dictionary(self):
        page = re.search(r'<p class="result-disclaimer travel-disclaimer">(.*?)</p>', HTML, re.S).group(1)
        self.assertEqual(page, FULL_HE)
        self.assertIn('const DISCLAIMER = "%s";' % FULL_HE, TRAVEL)
        self.assertIn('const SHORT = "%s";' % SHORT_HE, TRAVEL)
        language = (ROOT / "assets/statso-lang-en.js").read_text(encoding="utf-8")
        self.assertIn("'%s': '%s'" % (FULL_HE, FULL_EN), language)
        self.assertIn("'%s': '%s'" % (SHORT_HE, SHORT_EN), language)
        page = travel_page()
        self.assertEqual(page.count("result-disclaimer"), 1)
        # after the downloads and after the closing of the result block: the remark never hides with an empty result
        self.assertEqual(page[page.index('id="tt-docx"'):page.index("travel-disclaimer")].count("</div>"), 2)

    def test_the_site_has_one_disclaimer_for_the_tool_and_the_terms_only_name_it(self):
        self.assertEqual(HTML.count(FULL_HE), 1)
        terms = re.search(r'<article class="info-page" id="terms-page".*?</article>', HTML, re.S).group(0)
        self.assertEqual(terms.count("דו״ח נסיעה לחו״ל"), 1)
        self.assertEqual(terms.count("Foreign Travel Report"), 1)


class Collector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.labels = 0
        self.label_for = set()
        self.fields = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.add(attrs["id"])
        if tag == "label":
            self.labels += 1
            if "for" in attrs:
                self.label_for.add(attrs["for"])
        if tag in ("input", "select"):
            self.fields.append((tag, attrs, self.labels > 0))

    def handle_endtag(self, tag):
        if tag == "label":
            self.labels -= 1


def travel_page():
    return re.search(r'<section class="panel tool-page" id="tool-travel-page".*?</section>', HTML, re.S).group(0)


class MarkupTests(unittest.TestCase):
    def setUp(self):
        self.page = travel_page()
        self.collector = Collector()
        self.collector.feed(self.page)

    def test_every_field_has_a_name(self):
        self.assertGreater(len(self.collector.fields), 27)
        for tag, attrs, wrapped in self.collector.fields:
            with self.subTest(field=attrs.get("id")):
                named = wrapped or attrs.get("aria-label") or attrs.get("aria-labelledby") or attrs.get("id") in self.collector.label_for
                self.assertTrue(named)
                if attrs.get("aria-labelledby"):
                    for target in attrs["aria-labelledby"].split():
                        self.assertIn(target, self.collector.ids)
                for target in attrs.get("aria-describedby", "").split():
                    self.assertIn(target, self.collector.ids)

    def test_the_two_dates_are_a_named_group(self):
        group = re.search(r'<div role="group" aria-labelledby="(tt-dates-title)">(.*?)</div></div>', self.page, re.S)
        self.assertIsNotNone(group)
        self.assertIn('id="tt-dates-title"', self.page)
        self.assertIn('id="tt-depart"', group.group(2))
        self.assertIn('id="tt-return"', group.group(2))

    def test_the_thirteen_expense_groups_are_named_and_their_fields_carry_the_group_name(self):
        groups = re.findall(r'<div class="travel-expense" role="group" aria-labelledby="(tt-[A-Za-z0-9]+-title)"[^>]*>', self.page)
        self.assertEqual(len(groups), 13)
        # the eleven keys of the calculation in their order, the all-nights group after nights 8-90, education last
        order = ["flight", "insurance", "lodging7", "lodging90", "lodgingAll", "perDiem", "car", "transport", "phone", "gifts", "hosting", "other", "education"]
        self.assertEqual(ALL_KEYS, order)
        for key, title in zip(order, groups):
            self.assertEqual(title, "tt-%s-title" % key)
            self.assertIn('id="tt-%s-amount" type="number" min="0" step="any" aria-labelledby="%s tt-%s-amount-label" aria-describedby="tt-%s-cap"'
                          % (key, title, key, key), self.page)
            self.assertIn('<select id="tt-%s-currency" aria-labelledby="%s tt-%s-currency-label">' % (key, title, key), self.page)

    def test_every_expense_group_ends_with_its_cap_element_and_the_amount_points_at_it(self):
        # the cap element comes after the currency field in the document, so that the visual order (the end of the row)
        # is the reading order; the groups with no cap say so in plain text
        for key in ALL_KEYS:
            with self.subTest(group=key):
                self.assertEqual(self.page.count('id="tt-%s-cap"' % key), 1)
                self.assertGreater(self.page.index('id="tt-%s-cap"' % key), self.page.index('<select id="tt-%s-currency"' % key))
                self.assertEqual(self.page.count('aria-describedby="tt-%s-cap"' % key), 1)
        for key in ("flight", "insurance", "transport", "phone", "hosting", "other"):
            self.assertIn('<p class="travel-cap-free" id="tt-%s-cap">מוכר במלואו לפי קבלות, ללא תקרה.</p>' % key, self.page)
        for key in ("lodging7", "lodging90", "lodgingAll", "perDiem", "car", "gifts", "education"):
            self.assertIn('<div class="travel-cap" id="tt-%s-cap"></div>' % key, self.page)
        # no live region on a cap: the totals announcement stays the only voice, and the cap is read with the field
        for key in ALL_KEYS:
            self.assertNotRegex(self.page, r'id="tt-%s-cap"[^>]*(role=|aria-live)' % key)

    def test_groups_that_come_and_go_are_hidden_by_default_and_announce_their_mode_in_status_areas(self):
        for key in ("lodgingAll", "education"):
            self.assertRegex(self.page, r'aria-labelledby="tt-%s-title" id="tt-%s-group" hidden>' % (key, key))
        for key in ("lodging7", "lodging90"):
            self.assertRegex(self.page, r'aria-labelledby="tt-%s-title" id="tt-%s-group">' % (key, key))
        for area in ("tt-lodging-mode", "tt-lodging-kept", "tt-education-mode", "tt-education-kept"):
            self.assertRegex(self.page, r'<p class="rent-hint" id="%s" role="status">' % area)
        # the education threshold sentence is already in the markup, so that loading the page writes nothing into the area
        self.assertIn('id="tt-education-mode" role="status">חינוך ילדים מחושב רק בנסיעה העולה על 10 חודשים', self.page)
        self.assertRegex(self.page, r'id="tt-children" type="number" min="0" step="1" inputmode="numeric" aria-labelledby="tt-education-title tt-children-label"')

    def test_only_the_fieldsets_that_change_the_result_trigger_the_announcement(self):
        fieldsets = re.findall(r'<fieldset class="([^"]+)"><legend>(.*?)</legend>', self.page)
        calc = {legend for classes, legend in fieldsets if "travel-calc" in classes}
        self.assertEqual(calc, {"יעד ותאריכים", "נוסעים", "הוצאות"})
        self.assertIn('<label class="travel-calc">שנת מס', self.page)
        self.assertNotRegex(self.page, r'<label class="travel-calc">[^<]*<input id="tt-(company|account|purpose)"')
        self.assertIn('autocomplete="organization"', self.page)

    def test_the_result_table_has_a_caption_column_headers_and_a_named_scroll_region(self):
        self.assertIn('<div class="table-wrap" tabindex="0" role="region" aria-label="חישוב הוצאות הנסיעה">', self.page)
        self.assertIn('<caption class="sr-only">חישוב הוצאות הנסיעה</caption>', self.page)
        self.assertEqual(len(re.findall(r'<th scope="col">', self.page)), 8)

    def test_the_alert_the_status_areas_and_the_three_downloads(self):
        self.assertIn('<p class="inline-error" id="tt-error" role="alert"></p>', self.page)
        for area in ("tt-year-note", "tt-days-note", "tt-rates"):
            self.assertRegex(self.page, r'id="%s" role="status"|role="status" id="%s"' % (area, area))
        for button in ("tt-xlsx", "tt-pdf", "tt-docx"):
            self.assertIn('id="%s"' % button, self.page)
        self.assertIn("ייצוא ל־Word", self.page)

    def test_the_currency_remark_is_under_the_form_and_the_old_education_remark_is_gone(self):
        self.assertIn("אם הנסיעה הייתה במטבע שאינו אחד מהמטבעות הנתמכים באתר, יש להזין את הסכומים בש״ח לאחר המרה.", self.page)
        # children's education is calculated now: the "is not calculated" remark is nowhere, in the form or in the code
        self.assertNotIn("חינוך ילדים בנסיעה מעל 10 חודשים אינו מחושב", self.page)
        self.assertEqual(TRAVEL.count("חינוך ילדים בנסיעה מעל 10 חודשים אינו מחושב"), 0)
        self.assertNotIn("אינו מחושב", TRAVEL)
        # the method page says what the tool does now, in both languages, and still carries the first-class sentence
        self.assertEqual(HTML.count("חינוך ילדים בנסיעה מעל 10 חודשים אינו מחושב"), 0)
        self.assertIn("תקנה 2(2)(ז)", HTML)
        self.assertIn("regulation 2(2)(g)", HTML)

    def test_the_tool_page_is_inside_the_accounting_view_and_has_one_back_link(self):
        view = re.search(r'<main class="shell accounting-view" id="accounting-view" hidden>.*?</main>', HTML, re.S).group(0)
        self.assertIn('id="tool-travel-page"', view)
        self.assertEqual(view.count('href="#/accounting"'), 1)
        self.assertEqual(len(re.findall(r"<h1\b", view)), 1)


class AnnouncementTests(unittest.TestCase):
    """A change in a field that affects the result says the new totals once, after a pause; the report details do not."""

    def test_only_the_calculating_fieldsets_speak_and_only_while_a_result_is_shown(self):
        seen = node(r"""
global.window = {};
const timers = []; const listeners = {};
window.setTimeout = (fn, ms) => { timers.push({fn, ms, live: true}); return timers.length; };
window.clearTimeout = id => { if (timers[id - 1]) { timers[id - 1].live = false; } };
window.addEventListener = () => {}; window.scrollTo = () => {}; window.requestAnimationFrame = fn => fn();
window.location = {hash: '#/accounting/travel'};
const live = {textContent: ''};
const parts = ['Total paid (ILS)', '14,000.00', '\u20aa', 'Total deductible expense', '12,775.00', '\u20aa'];
const summary = {hidden: false, querySelectorAll: () => parts.map(text => ({textContent: ' ' + text + ' '}))};
const output = {hidden: false};
const calculating = {closest: selector => selector.includes('#tool-travel-page .travel-calc') ? {} : null};
const reportDetail = {closest: () => null};
const freeText = {closest: selector => selector.includes('#tool-travel-page .travel-calc') || selector.includes('.tt-name') ? {} : null};
global.document = {title: 't', addEventListener(type, fn) { listeners[type] = fn; },
 getElementById(id) { if (id === 'result-live') { return live; } if (id === 'tt-summary') { return summary; } if (id === 'tt-output') { return output; }
  if (id === 'tools-trigger' || id === 'accounting-trigger') { return null; }
  return {hidden: false, addEventListener() {}, querySelectorAll() { return []; }}; },
 querySelector() { return null; }, querySelectorAll() { return []; }};
require(%s);
window.Statso.nav.init();
const run = () => timers.filter(t => t.live).forEach(t => { t.live = false; t.fn(); });
const seen = {};
listeners.input({target: reportDetail}); run(); seen.detail = live.textContent;
listeners.input({target: calculating}); listeners.change({target: calculating}); seen.before = live.textContent; run(); seen.after = live.textContent;
live.textContent = ''; listeners.input({target: freeText}); listeners.change({target: freeText}); run(); seen.freeTextAlone = live.textContent;
live.textContent = ''; output.hidden = true;
listeners.input({target: calculating}); run(); seen.hidden = live.textContent;
process.stdout.write(JSON.stringify(seen));
""" % json.dumps(str(ROOT / "assets/statso-nav.js")))
        self.assertEqual(seen["detail"], "")
        self.assertEqual(seen["before"], "")
        self.assertEqual(seen["after"], "Total paid (ILS) 14,000.00 \u20aa Total deductible expense 12,775.00 \u20aa")
        self.assertEqual(seen["hidden"], "")
        self.assertEqual(seen["freeTextAlone"], "")      # typing a name, a role, a country name or a description says nothing


class StylesheetTests(unittest.TestCase):
    def test_the_expense_grid_and_the_explanation_column(self):
        css = (ROOT / "assets/statso.css").read_text(encoding="utf-8")
        self.assertIn(".travel-expense { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 12rem), 1fr));", css)
        self.assertIn(".travel-table td.travel-explain { white-space: normal; min-width: 18rem; }", css)
        self.assertIn('.rent-form select[aria-invalid="true"]', css)


# ---- children's education, the single lodging row over 90 nights, the live caps, the "!" button -----------------

HELPERS = r"""
const plus = (date, days) => new Date(Date.parse(date + 'T00:00:00Z') + days * 86400000).toISOString().slice(0, 10);
const START = '2026-03-06';
const trip = days => ({depart: START, ret: plus(START, days - 1)});     // both ends count: `days` days
const flat = () => ({ok: true, rate: 3.5, unit: 1, date: '2026-03-06'});
const live = (o, quote) => { const i = inp(o); return T.liveCaps(i, quote === undefined ? quoteFor(i.depart) : quote, o.options); };
"""
CAP_KEYS = ["lodging7", "lodging90", "lodgingAll", "perDiem", "car", "gifts", "education"]


class EducationTableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seen = calc(HELPERS + r"""
const o = {table: T.EDUCATION_USD, rates: {}, notes: {}, english: {}};
for (const year of [...T.YEARS, 2027, 2040]) { o.rates[year] = T.educationRate(year); }
// 2027 and later are not in the caps table, so the rule is reached by adding a year to it for a moment
T.CAPS[2027] = Object.assign({}, T.CAPS[2026]);
try {
  for (const year of [...T.YEARS, 2027]) {
    const model = T.calculate(inp(Object.assign({year, children: 1, rows: {education: 1}}, trip(305))), flat);
    const item = model.rows.find(row => row.key === 'education');
    o.notes[year] = item.note || '';
    o.english[year] = item.note ? translate(item.note) : '';
  }
} finally { delete T.CAPS[2027]; }
process.stdout.write(JSON.stringify(o));
""")

    def test_the_amounts_and_their_sources_are_locked_for_every_year(self):
        self.assertEqual(sorted(int(year) for year in self.seen["table"]), list(EDUCATION_USD))
        for year, (usd, source) in EDUCATION_USD.items():
            with self.subTest(year=year):
                self.assertEqual(self.seen["table"][str(year)], {"usd": usd, "source": source})
                self.assertEqual(self.seen["rates"][str(year)], {"usd": usd, "source": source})

    def test_a_year_after_the_last_takes_the_2026_amount_until_told_otherwise(self):
        for year in ("2027", "2040"):
            self.assertEqual(self.seen["rates"][year], {"usd": 914, "source": "later"})

    def test_the_source_note_names_what_is_not_official_and_2025_has_none(self):
        notes = self.seen["notes"]
        for year in range(2018, 2025):
            with self.subTest(year=year):
                self.assertIn("מדד המחירים לצרכן בארה״ב", notes[str(year)])
                self.assertIn("לא אומת ממקור רשמי", notes[str(year)])
                self.assertIn(str(EDUCATION_USD[year][0]), notes[str(year)])
        self.assertEqual(notes["2025"], "")
        self.assertIn("רואי חשבון", notes["2026"])
        self.assertIn("לא ממקור רשמי", notes["2026"])
        self.assertIn("914", notes["2026"])
        self.assertIn("סכום שנת 2026", notes["2027"])
        self.assertIn("914", notes["2027"])

    def test_every_source_note_translates_whole_and_keeps_its_figures(self):
        for year, english in self.seen["english"].items():
            note = self.seen["notes"][year]
            with self.subTest(year=year):
                if not note:
                    self.assertEqual(english, "")
                    continue
                self.assertIsNone(HEBREW.search(english), english)
                self.assertEqual(numbers(english), numbers(note))
        self.assertIn("US consumer price index", self.seen["english"]["2020"])
        self.assertIn("accountants’ websites", self.seen["english"]["2026"])
        self.assertIn("2026 amount", self.seen["english"]["2027"])


class EducationCalculationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = calc(HELPERS + r"""
const s = {};
s.d304 = run(Object.assign({children: 2, rows: {education: -1}}, trip(304)));      // not over 10 months: the group does not exist
s.d305 = run(Object.assign({children: 2, rows: {education: 1000}}, trip(305)));
s.byYear = {};
for (const year of T.YEARS) {
  const model = T.calculate(inp(Object.assign({year, children: 3, rows: {education: 5000}}, trip(305))), flat);
  s.byYear[year] = model.rows.find(row => row.key === 'education');
}
s.fraction = run(Object.assign({children: 2.5}, trip(305)));
s.negative = run(Object.assign({children: -1}, trip(305)));
s.nan = run(Object.assign({children: NaN}, trip(305)));
s.empty = run(Object.assign({children: ''}, trip(305)));
s.unset = run(trip(305));
s.shortBadChildren = run(Object.assign({children: -1}, trip(304)));
s.longTrip = run(Object.assign({children: 1, rows: {education: 7000}}, trip(365)));
s.listed = run(Object.assign({children: 2, listed: true, rows: {education: 1}}, trip(305)));
s.partialStay = run(Object.assign({children: 1, partial: true, lodgingDays: 10, rows: {education: 1}}, trip(305)));
s.badAmount = run(Object.assign({children: 1, rows: {education: -5}}, trip(305)));
// the months and the threshold come from the days of the trip: few business days change neither
s.fewBusiness = run(Object.assign({children: 1, businessDays: 200, rows: {education: 1}}, trip(365)));
s.fewBusinessLive = live(Object.assign({children: 1, businessDays: 200}, trip(365)));
s.fewBusinessIn = run(Object.assign({children: 1, businessDays: 10, rows: {education: 1}}, trip(305)));
const educationRow = model => model.rows.find(row => row.key === 'education');
s.english = {d305: translate(educationRow(s.d305).explain), longTrip: translate(educationRow(s.longTrip).explain)};
process.stdout.write(JSON.stringify(s));
""")

    def near(self, actual, expected):
        self.assertAlmostEqual(actual, expected, delta=1e-9)

    def test_ten_months_are_days_times_twelve_over_365_and_305_days_is_the_first_stay_that_counts(self):
        # 304 * 12 = 3648 < 3650 < 3660 = 305 * 12
        model = self.s["d304"]
        self.assertTrue(model["ok"])                                    # even with an invalid amount typed into the absent group
        self.assertNotIn("education", [item["key"] for item in model["rows"]])
        self.assertFalse(any("חינוך ילדים" in note for note in model["notes"]))
        self.assertIn("education", [item["key"] for item in self.s["d305"]["rows"]])
        self.assertEqual(len(self.s["d305"]["rows"]), 11)               # the eleven rows of a trip plus education, with the single lodging row
        self.assertEqual(self.s["d305"]["rows"][-1]["key"], "education")

    def test_the_cap_is_rate_times_children_times_prorated_months_in_dollars_converted_once(self):
        item = row(self.s["d305"], "education")
        cap = 914 * 2 * (305 * 12 / 365) * 3.5
        self.near(item["cap"], cap)
        self.near(item["usd"], 914 * 2 * (305 * 12 / 365))
        self.near(item["ils"], 3500)
        self.near(item["recognized"], min(3500, cap))
        self.assertEqual(item["label"], "חינוך ילדים")
        self.assertEqual((item["amount"], item["currency"]), (1000, "USD"))
        self.assertIn("ילדים: 2", item["explain"])
        self.assertIn("ימי הנסיעה: 305 × 12 ÷ 365", item["explain"])

    def test_every_year_uses_its_own_amount_and_the_cap_is_not_rounded(self):
        for year, (usd, _) in EDUCATION_USD.items():
            with self.subTest(year=year):
                item = self.s["byYear"][str(year)]
                self.near(item["cap"], usd * 3 * 305 * 12 / 365 * 3.5)
                self.assertNotEqual(item["cap"], round(item["cap"], 2))        # a row is shown unrounded; only totals round

    def test_no_uplift_applies_to_education_for_the_listed_countries(self):
        self.near(row(self.s["listed"], "education")["cap"], 914 * 2 * (305 * 12 / 365) * 3.5)
        self.assertNotIn("כולל תוספת 25%", row(self.s["listed"], "education")["explain"])

    def test_the_children_count_is_a_whole_number_and_empty_means_none(self):
        for name in ("fraction", "negative", "nan"):
            with self.subTest(case=name):
                self.assertFalse(self.s[name]["ok"])
                self.assertEqual([e["fields"] for e in self.s[name]["errors"]], [["tt-children"]])
                self.assertEqual(self.s[name]["errors"][0]["message"], "מספר הילדים חייב להיות מספר שלם שאינו שלילי.")
        for name in ("empty", "unset"):
            with self.subTest(case=name):
                self.assertTrue(self.s[name]["ok"])
                item = row(self.s[name], "education")
                self.near(item["cap"], 0)
                self.assertIn("ילדים: 0", item["explain"])
        self.assertTrue(self.s["shortBadChildren"]["ok"])               # no education on a short trip: the count is not checked
        self.assertEqual([e["fields"] for e in self.s["badAmount"]["errors"]], [["tt-education-amount"]])

    def test_the_notes_carry_the_rule_only_with_an_education_row_and_say_what_the_tool_limits(self):
        notes = self.s["d305"]["notes"]
        rule = [note for note in notes if "תקנה 2(2)(ז)" in note]
        self.assertEqual(len(rule), 1)
        for phrase in ("לתקנות מס הכנסה (ניכוי הוצאות מסויימות)", "שטרם מלאו להם 18 בשנת המס", "הנציב רשאי להתיר עודף", "הכלי מגביל לסכום שבתקנה"):
            self.assertIn(phrase, rule[0])
        self.assertFalse(any("תקנה 2(2)(ז)" in note for note in self.s["d304"]["notes"]))
        # the source remark of the year is in the row; the rule stays a single note
        self.assertIn("רואי חשבון", row(self.s["d305"], "education")["note"])
        self.assertNotIn("note", row(self.s["byYear"] and self.s["d304"], "flight"))

    def test_a_stay_of_a_year_is_twelve_months(self):
        item = row(self.s["longTrip"], "education")
        self.near(item["cap"], 914 * 1 * 12 * 3.5)
        self.assertEqual(item["explain"], "תקרה: 914 דולר לילד לחודש · ילדים: 1 · חודשים: 12.0000 (ימי הנסיעה: 365 × 12 ÷ 365) = 10,968.00 דולר · לפי שער 3.5 = 38,388.00 ₪.")
        self.assertEqual(self.s["english"]["longTrip"], "Cap: USD 914 per child per month · children: 1 · months: 12.0000 (trip days: 365 × 12 ÷ 365) = USD 10,968.00 · at rate 3.5 = ILS 38,388.00.")

    def test_the_education_sentence_shows_months_to_four_digits_and_dollars_to_the_cent_and_the_cap_stays_exact(self):
        item = row(self.s["d305"], "education")
        self.assertEqual(item["explain"], "תקרה: 914 דולר לילד לחודש · ילדים: 2 · חודשים: 10.0274 (ימי הנסיעה: 305 × 12 ÷ 365) = 18,330.08 דולר · לפי שער 3.5 = 64,155.29 ₪.")
        self.assertEqual(self.s["english"]["d305"], "Cap: USD 914 per child per month · children: 2 · months: 10.0274 (trip days: 305 × 12 ÷ 365) = USD 18,330.08 · at rate 3.5 = ILS 64,155.29.")
        self.assertNotIn("10.02739", item["explain"])
        self.assertNotIn("18330.08", item["explain"])
        # only what is shown is rounded: the row, the dollar total and the figures beside the field are the exact numbers
        self.near(item["cap"], 914 * 2 * 305 * 12 / 365 * 3.5)
        self.near(item["usd"], 914 * 2 * 305 * 12 / 365)
        self.assertNotEqual(item["usd"], round(item["usd"], 2))

    def test_months_and_the_ten_month_line_come_from_the_trip_days_and_not_from_the_business_days(self):
        item = row(self.s["fewBusiness"], "education")
        self.near(item["cap"], 914 * 12 * 3.5)                           # 365 days, not the 200 business days (which would be 6.58 months)
        self.assertIn("ימי הנסיעה: 365 × 12 ÷ 365", item["explain"])
        self.assertIn("חודשים: 12.0000", item["explain"])
        self.near(self.s["fewBusinessLive"]["education"]["ils"], 914 * 12 * 3.5)
        self.assertIn("education", [item["key"] for item in self.s["fewBusinessIn"]["rows"]])      # 305 days with 10 business days

    def test_education_has_its_own_total_and_enters_the_totals(self):
        model = self.s["d305"]
        self.assertEqual(model["totals"]["ils"], half_up(sum(item["ils"] for item in model["rows"])))
        self.assertEqual(model["totals"]["recognized"], half_up(sum(item["recognized"] for item in model["rows"])))


class LongStayInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = calc(HELPERS + r"""
const s = {};
const long = trip(102);
s.single = run(Object.assign({rows: {lodging7: -1, lodging90: -1, lodgingAll: 1000}}, long));   // the two hidden rows are not even checked
s.singleCurrency = run(Object.assign({rows: {lodging7: [5, 'GBP'], lodgingAll: [100, 'EUR']}}, long));   // a hidden row's currency is not read
s.shortIgnores = run({rows: {lodging7: 100, lodgingAll: -1}});
s.shortIgnoresValid = run({rows: {lodging7: 100, lodgingAll: 5000}});
s.partialLong = run(Object.assign({partial: true, lodgingDays: 95, businessDays: 100, rows: {lodgingAll: 100, perDiem: 1}}, trip(100)));
s.partialLongCompat = run(Object.assign({partial: true, lodgingDays: 95, businessDays: 100, rows: {lodging7: 100, perDiem: 1}}, trip(100)));
s.partialShortBusinessLong = run(Object.assign({partial: true, lodgingDays: 10, businessDays: 100, rows: {lodging7: 100}}, trip(100)));
s.hiddenNotCounted = run(Object.assign({rows: {lodging7: 1000, lodgingAll: 0, perDiem: 1}}, long));
s.allCounted = run(Object.assign({rows: {lodging7: 1000, lodgingAll: 500, perDiem: 1}}, long));
s.shortHiddenNotCounted = run({rows: {lodging7: 0, lodgingAll: 500, perDiem: 1}});
s.compat = run(Object.assign({rows: {lodging7: 2000, lodging90: 20000}}, long));
s.compatBad = run(Object.assign({rows: {lodging7: -1}}, long));
s.exactly90 = run(Object.assign({rows: {lodging7: 100, lodging90: 100, lodgingAll: 100}}, trip(90)));
s.facts = {};
for (const days of [5, 90, 91, 304, 305]) { s.facts[days] = (({longStay, education, months, totalDays, L}) => ({longStay, education, months, totalDays, L}))(T.tripFacts(inp(trip(days)))); }
process.stdout.write(JSON.stringify(s));
""")

    def keys(self, name):
        return [item["key"] for item in self.s[name]["rows"]]

    def test_the_all_nights_row_over_ninety_nights_replaces_the_two_lodging_rows_and_ignores_them(self):
        self.assertTrue(self.s["single"]["ok"])
        self.assertEqual(self.keys("single").count("lodgingAll"), 1)
        self.assertNotIn("lodging7", self.keys("single"))
        self.assertNotIn("lodging90", self.keys("single"))
        item = row(self.s["single"], "lodgingAll")
        self.assertAlmostEqual(item["cap"], 160 * 102 * 3.5, delta=1e-9)
        self.assertAlmostEqual(item["ils"], 3500, delta=1e-9)             # only the 1000 dollars typed in the one row
        self.assertEqual((item["amount"], item["currency"]), (1000, "USD"))
        self.assertTrue(self.s["singleCurrency"]["ok"])                    # a hidden row with a currency that has no rate is not read
        self.assertEqual(row(self.s["singleCurrency"], "lodgingAll")["currency"], "EUR")

    def test_up_to_ninety_nights_the_all_nights_row_is_ignored_even_when_invalid(self):
        for name in ("shortIgnores", "shortIgnoresValid"):
            with self.subTest(case=name):
                self.assertTrue(self.s[name]["ok"])
                self.assertNotIn("lodgingAll", self.keys(name))
                self.assertIn("lodging7", self.keys(name))
                self.assertIn("lodging90", self.keys(name))
        self.assertAlmostEqual(self.s["shortIgnoresValid"]["totals"]["ils"], 350, delta=1e-9)

    def test_a_partial_per_diem_with_more_than_ninety_lodging_days_is_a_long_stay(self):
        self.assertEqual(self.s["partialLong"]["nights"], 95)
        self.assertIn("lodgingAll", self.keys("partialLong"))
        self.assertIn("lodgingAll", self.keys("partialLongCompat"))
        self.assertNotIn("lodgingAll", self.keys("partialShortBusinessLong"))      # business days are over 90 but the nights are not

    def test_the_per_diem_rate_follows_only_the_lodging_rows_that_are_in_the_calculation(self):
        self.assertIn("בלי הוצאות לינה", row(self.s["hiddenNotCounted"], "perDiem")["explain"])
        self.assertIn("עם הוצאות לינה", row(self.s["allCounted"], "perDiem")["explain"])
        self.assertIn("בלי הוצאות לינה", row(self.s["shortHiddenNotCounted"], "perDiem")["explain"])

    def test_input_without_the_all_nights_row_keeps_the_old_merge_of_the_two_rows(self):
        self.assertIn("lodgingAll", self.keys("compat"))
        self.assertAlmostEqual(row(self.s["compat"], "lodgingAll")["ils"], 22000 * 3.5, delta=1e-9)
        self.assertFalse(self.s["compatBad"]["ok"])                         # the rows it does read are still checked
        self.assertEqual(self.s["compatBad"]["errors"][0]["fields"], ["tt-lodging7-amount"])
        self.assertNotIn("lodgingAll", self.keys("exactly90"))             # ninety nights is still the two-row rule

    def test_the_trip_facts_draw_the_lines_at_ninety_nights_and_ten_months(self):
        facts = self.s["facts"]
        self.assertEqual([facts[d]["longStay"] for d in ("5", "90", "91", "304", "305")], [False, False, True, True, True])
        self.assertEqual([facts[d]["education"] for d in ("5", "90", "91", "304", "305")], [False, False, False, False, True])
        self.assertAlmostEqual(facts["305"]["months"], 305 * 12 / 365, delta=1e-12)


LIVE = HELPERS + r"""
const all = ['lodging7', 'lodging90', 'lodgingAll', 'perDiem', 'car', 'gifts', 'education'];
"""


class LiveCapEqualityTests(unittest.TestCase):
    """The figure beside a field is the cap in the table, to the digit, and the sentence under it is the sentence of the table."""

    @classmethod
    def setUpClass(cls):
        cls.seen = calc(LIVE + r"""
const q = quoteFor(START);
const seen = {compared: 0, mismatches: [], states: {}, currencies: {}};
function note(tag, what, a, b) { seen.mismatches.push([tag, what, a, b]); }
for (const listed of [false, true]) for (const year of T.YEARS) for (const days of [5, 20, 102, 305]) for (const code of ['USD', 'ILS', 'EUR', 'JPY']) for (const a90 of [0, 50, 3000, 900000]) {
  const rows = {flight: [1, code]};
  const amounts = {lodging7: 1000, lodging90: a90, lodgingAll: 1000, perDiem: 500, car: 300, gifts: 100, education: 2000};
  for (const key of Object.keys(amounts)) { rows[key] = [amounts[key], code]; }
  const i = inp(Object.assign({year, listed, travelers: 2, children: 2, rows}, trip(days)));
  const model = T.calculate(i, q);
  const caps = T.liveCaps(i, q);
  const tag0 = [year, listed, days, code, a90].join('/');
  if (!model.ok) { note(tag0, 'calculation failed', model.errors[0].message); continue; }
  for (const row of model.rows) {
    const cap = caps[row.key];
    if (!cap || cap.state === 'free') { continue; }
    const tag = tag0 + '/' + row.key;
    seen.compared += 1;
    seen.states[cap.state] = (seen.states[cap.state] || 0) + 1;
    seen.currencies[cap.currency] = (seen.currencies[cap.currency] || 0) + 1;
    if (row.cap === null) {
      // nights 8-90 with no amount: the most it could be; with no night in that range at all, the sentence of the table for that
      if (cap.state === 'potential') { if (cap.ils !== row.potential) { note(tag, 'potential', cap.ils, row.potential); } }
      else if (!(cap.state === 'cap' && cap.ils === 0 && /^אין לילות בטווח/.test(cap.explain))) { note(tag, 'empty state', cap.state, cap.explain); }
      continue;
    }
    if (cap.ils !== row.cap) { note(tag, 'ils', cap.ils, row.cap); }
    if (cap.explain !== row.explain) { note(tag, 'explain', cap.explain, row.explain); }
    if (cap.state === 'full') { continue; }
    if (cap.currency !== code) { note(tag, 'currency', cap.currency, code); }
    const want = code === 'USD' ? row.usd : code === 'ILS' ? row.cap : row.cap / q(code).rate;
    if (cap.value !== want) { note(tag, 'value', cap.value, want); }
    if (code === 'USD' || code === 'ILS') { if (cap.conversion !== '') { note(tag, 'conversion', cap.conversion, ''); } }
    else if (!cap.conversion.startsWith('המרה ל־' + code + ': ')) { note(tag, 'conversion text', cap.conversion, code); }
  }
}
process.stdout.write(JSON.stringify(seen));
""")

    def test_the_live_cap_and_sentence_are_the_table_row_for_every_year_group_trip_and_currency(self):
        self.assertEqual(self.seen["mismatches"][:5], [])
        self.assertGreater(self.seen["compared"], 5000)

    def test_every_kind_of_live_state_was_exercised_in_every_currency(self):
        for state in ("cap", "potential", "full"):
            self.assertGreater(self.seen["states"].get(state, 0), 0, state)
        for code in ("USD", "ILS", "EUR", "JPY"):
            self.assertGreater(self.seen["currencies"].get(code, 0), 0, code)


class LiveCapDependencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = calc(LIVE + r"""
const s = {};
const noQuote = () => ({ok: false});
s.noDates = live({depart: '', ret: '', rows: {lodging7: 500}});
s.noDatesListed = live({depart: '', ret: '', listed: true});
s.noDatesBefore = live({depart: '', ret: ''}, null);
s.badPhone = {model: run({rows: {phone: -1, lodging7: 100}}), live: live({rows: {phone: -1, lodging7: 100}})};
s.badK = live({partial: true, lodgingDays: 99});
s.badKFilled = live({partial: true, lodgingDays: 0});
s.badB = live({businessDays: 99});
s.noTravellers = live({travelers: 0});
s.nights = live(Object.assign({rows: {lodging90: 0}}, trip(20)));
s.above = live(Object.assign({rows: {lodging90: 5200}}, trip(20)));
s.upto = live(Object.assign({rows: {lodging90: 1950}}, trip(20)));
s.model = run(Object.assign({rows: {lodging90: 5200}}, trip(20)));
s.none = live(Object.assign({rows: {lodging90: 100}}, trip(5)));
s.gbp = live({rows: {lodging7: [10, 'GBP']}});
s.gbp90 = live(Object.assign({rows: {lodging90: [10, 'GBP']}}, trip(20)));
s.loading = live({}, null);
s.failed = live({options: {failed: true}}, null);
s.noUsd = live({}, noQuote);
s.education = live(Object.assign({children: 2, rows: {education: 0}}, trip(305)));
s.educationNoChildren = live(trip(305));
s.educationShort = live(Object.assign({children: 2}, trip(304)));
s.badChildren = live(Object.assign({children: 1.5}, trip(305)));
s.long = live(Object.assign({rows: {lodgingAll: 0}}, trip(102)));
s.badYear = live({year: 2030});
// the per-diem rate asks the lodging rows that are in the calculation, in the live cap as in the table
const hiddenLodging = Object.assign({rows: {lodging7: 1000, lodgingAll: 0, perDiem: 1}}, trip(102));
s.hiddenLodging = {live: live(hiddenLodging), model: run(hiddenLodging)};
const shortHiddenAll = {rows: {lodgingAll: 500, perDiem: 1}};
s.shortHiddenAll = {live: live(shortHiddenAll), model: run(shortHiddenAll)};
const shownLodging = Object.assign({rows: {lodging7: 0, lodgingAll: 500, perDiem: 1}}, trip(102));
s.shownLodging = {live: live(shownLodging), model: run(shownLodging)};
process.stdout.write(JSON.stringify(s));
""")

    def test_before_any_date_only_the_rate_in_dollars_shows_with_the_reason(self):
        caps = self.s["noDates"]
        for key in CAP_KEYS:
            with self.subTest(group=key):
                self.assertEqual(caps[key]["state"], "rate")
                self.assertEqual(caps[key]["hint"], "יש להזין תאריכים לחישוב התקרה.")
                self.assertIsNone(caps[key]["value"])
        self.assertEqual(caps["lodging7"]["rateText"], "365 דולר ללילה לנוסע")
        self.assertEqual(caps["lodging90"]["rateText"], "סף 160 דולר, מקסימום 273.75 דולר ללילה לנוסע")
        self.assertEqual(caps["lodgingAll"]["rateText"], "160 דולר ללילה לנוסע")
        self.assertEqual(caps["perDiem"]["rateText"], "102 דולר ליום עם לינה, 171 דולר ליום בלי לינה, לנוסע")
        self.assertEqual(caps["car"]["rateText"], "80 דולר ליום לנוסע")
        self.assertEqual(caps["gifts"]["rateText"], "15 דולר לנוסע (ללא תוספת 25%)")
        self.assertEqual(caps["education"]["rateText"], "914 דולר לילד לחודש")
        self.assertEqual(self.s["noDatesListed"]["lodging7"]["rateText"], "456.25 דולר ללילה לנוסע (כולל תוספת 25%)")
        self.assertEqual(self.s["noDatesListed"]["gifts"]["rateText"], "15 דולר לנוסע (ללא תוספת 25%)")
        self.assertEqual(self.s["noDatesBefore"]["lodging7"]["hint"], "יש להזין תאריכים לחישוב התקרה.")     # the dates come before the rates
        for key in ("flight", "insurance", "transport", "phone", "hosting", "other"):
            self.assertEqual(self.s["noDates"][key]["state"], "free")

    def test_an_error_elsewhere_in_the_form_does_not_hide_a_cap_that_does_not_depend_on_it(self):
        self.assertFalse(self.s["badPhone"]["model"]["ok"])
        for key in ("lodging7", "lodging90", "perDiem", "car", "gifts"):
            self.assertEqual(self.s["badPhone"]["live"][key]["state"], "cap" if key != "lodging90" else "cap", key)
        self.assertEqual(self.s["badPhone"]["live"]["lodging7"]["hint"], "")

    def test_a_wrong_lodging_days_count_hides_only_the_caps_that_use_the_nights(self):
        for name in ("badK", "badKFilled"):
            caps = self.s[name]
            with self.subTest(case=name):
                for key in ("lodging7", "lodging90", "lodgingAll", "perDiem"):
                    self.assertEqual(caps[key]["state"], "rate", key)
                    self.assertEqual(caps[key]["hint"], "התקרה תחושב לאחר תיקון השגיאה בטופס.")
                    self.assertTrue(caps[key]["rateText"])
                self.assertEqual(caps["car"]["state"], "cap")
                self.assertEqual(caps["gifts"]["state"], "cap")
        caps = self.s["badB"]                                              # business days beyond the trip: nothing that counts days
        for key in ("lodging7", "perDiem", "car"):
            self.assertEqual(caps[key]["state"], "rate", key)
        self.assertEqual(caps["gifts"]["state"], "cap")
        self.assertEqual(self.s["noTravellers"]["gifts"]["state"], "rate")

    def test_nights_eight_to_ninety_show_the_most_it_could_be_until_an_amount_is_typed(self):
        empty = self.s["nights"]["lodging90"]
        self.assertEqual(empty["state"], "potential")
        self.assertEqual(empty["label"], "תקרה מותרת (מקסימום אפשרי):")
        self.assertTrue(empty["explain"].startswith("מקסימום אפשרי: 273.75 דולר ללילה · לילות: 13 · נוסעים: 1 = 3558.75 דולר"))
        self.assertEqual(empty["note"], "טווח ללילה לנוסע: 160–273.75 דולר. התקרה בפועל תלויה בסכום.")
        self.assertAlmostEqual(empty["ils"], 273.75 * 13 * 3.5, delta=1e-9)
        above = self.s["above"]["lodging90"]
        self.assertEqual(above["state"], "cap")
        self.assertAlmostEqual(above["ils"], row(self.s["model"], "lodging90")["cap"], delta=1e-9)     # over the threshold: the table's cap
        upto = self.s["upto"]["lodging90"]
        self.assertEqual((upto["state"], upto["label"]), ("full", "מוכר במלואו"))
        self.assertIn("עד הסף של 160 דולר", upto["explain"])                    # the sentence that names the threshold
        none = self.s["none"]["lodging90"]
        self.assertTrue(none["explain"].startswith("אין לילות בטווח 8–90"))

    def test_a_group_currency_without_a_rate_shows_shekels_and_says_so(self):
        cap = self.s["gbp"]["lodging7"]
        self.assertEqual((cap["currency"], cap["state"]), ("ILS", "cap"))
        self.assertAlmostEqual(cap["value"], cap["ils"], delta=1e-9)
        self.assertEqual(cap["hint"], "אין שער עבור GBP בתאריך היציאה או לפניו.")
        self.assertEqual(cap["conversion"], "")
        nights = self.s["gbp90"]["lodging90"]                                # an amount that cannot be converted counts as none yet
        self.assertEqual(nights["state"], "potential")
        self.assertEqual(nights["hint"], "אין שער עבור GBP בתאריך היציאה או לפניו.")

    def test_while_the_rates_load_fail_or_miss_the_dollar_the_cap_says_why(self):
        self.assertEqual(self.s["loading"]["lodging7"]["hint"], "טוען שערי חליפין…")
        self.assertEqual(self.s["failed"]["lodging7"]["hint"], "לא ניתן לטעון את שערי החליפין.")
        self.assertEqual(self.s["noUsd"]["lodging7"]["hint"], "אין שער עבור USD בתאריך היציאה או לפניו.")
        for name in ("loading", "failed", "noUsd"):
            self.assertEqual(self.s[name]["lodging7"]["state"], "rate")
            self.assertEqual(self.s[name]["lodging7"]["rateText"], "365 דולר ללילה לנוסע")

    def test_education_caps_exist_only_on_a_long_stay_and_need_a_valid_children_count(self):
        cap = self.s["education"]["education"]
        self.assertEqual(cap["state"], "cap")
        self.assertAlmostEqual(cap["ils"], 914 * 2 * (305 * 12 / 365) * 3.5, delta=1e-9)
        self.assertIn("ילדים: 2", cap["explain"])
        self.assertIn("רואי חשבון", cap["note"])
        none = self.s["educationNoChildren"]["education"]                      # no children yet: no cap, and the sentence says so
        self.assertEqual(none["state"], "cap")
        self.assertAlmostEqual(none["ils"], 0, delta=1e-9)
        self.assertIn("ילדים: 0", none["explain"])
        self.assertEqual(self.s["educationShort"]["education"]["state"], "rate")
        self.assertEqual(self.s["educationShort"]["education"]["hint"], "")
        self.assertEqual(self.s["badChildren"]["education"]["hint"], "התקרה תחושב לאחר תיקון השגיאה בטופס.")
        self.assertEqual(self.s["badChildren"]["lodgingAll"]["state"], "cap")

    def test_the_all_nights_cap_is_the_floor_for_every_night(self):
        cap = self.s["long"]["lodgingAll"]
        self.assertEqual(cap["state"], "cap")
        self.assertAlmostEqual(cap["ils"], 160 * 102 * 3.5, delta=1e-9)

    def test_the_live_per_diem_counts_only_the_lodging_groups_that_are_in_the_calculation(self):
        for name in ("hiddenLodging", "shortHiddenAll"):
            case = self.s[name]
            with self.subTest(case=name):
                self.assertTrue(case["model"]["ok"])
                self.assertEqual(case["live"]["perDiem"]["explain"], row(case["model"], "perDiem")["explain"])
                self.assertIn("בלי הוצאות לינה", case["live"]["perDiem"]["explain"])
        # and the other way round: a lodging amount in the visible group raises it to the with-lodging rate
        case = self.s["shownLodging"]
        self.assertEqual(case["live"]["perDiem"]["explain"], row(case["model"], "perDiem")["explain"])
        self.assertIn("עם הוצאות לינה", case["live"]["perDiem"]["explain"])

    def test_an_unknown_year_has_no_cap_and_no_rate_to_state(self):
        for key in CAP_KEYS:
            self.assertEqual(self.s["badYear"][key]["state"], "rate")
            self.assertEqual(self.s["badYear"][key]["rateText"], "")


class LiveSentenceArithmeticTests(unittest.TestCase):
    """The sentences that exist only beside the fields say what they computed, in both languages."""

    @classmethod
    def setUpClass(cls):
        cls.seen = calc(LIVE + r"""
const o = {items: [], rates: [], caps: T.CAPS};
for (const listed of [false, true]) for (const year of T.YEARS) {
  const base = {year, listed, travelers: 2, children: 2};
  const nights = live(Object.assign({rows: {lodging7: [10, 'EUR'], lodging90: [0, 'USD']}}, base, trip(20)));
  const edu = live(Object.assign({rows: {education: [10, 'JPY']}}, base, trip(305)));
  const tr = x => ({he: x, en: translate(x)});
  o.items.push({year, listed, eduExplain: tr(edu.education.explain), potential: tr(nights.lodging90.explain), range: tr(nights.lodging90.note), ilsPotential: nights.lodging90.ils,
    conversion: tr(nights.lodging7.conversion), ilsLodging: nights.lodging7.ils, valueLodging: nights.lodging7.value,
    eduConversion: tr(edu.education.conversion), ilsEdu: edu.education.ils, valueEdu: edu.education.value});
  const rates = live(base);
  all.concat([]).forEach(key => { if (rates[key].rateText) { o.rates.push({year, listed, key, he: rates[key].rateText, en: translate(rates[key].rateText)}); } });
}
process.stdout.write(JSON.stringify(o));
""")

    def close(self, a, b, what=""):
        self.assertLessEqual(abs(a - b), 1e-9 * max(1, abs(b)), what)

    def test_the_possible_maximum_sentence_is_max_times_nights_times_travellers_in_both_languages(self):
        pattern = re.compile(r"^מקסימום אפשרי: " + NUM + r" דולר ללילה" + UPLIFT + r" · לילות: (\d+) · נוסעים: (\d+)" + TAIL + "$")
        range_pattern = re.compile(r"^טווח ללילה לנוסע: " + NUM + "–" + NUM + r" דולר\. התקרה בפועל תלויה בסכום\.$")
        for item in self.seen["items"]:
            caps = self.seen["caps"][str(item["year"])]
            m = 1.25 if item["listed"] else 1
            with self.subTest(year=item["year"], listed=item["listed"]):
                match = pattern.match(item["potential"]["he"])
                self.assertIsNotNone(match, item["potential"]["he"])
                top, up, nights, travellers, t, rate, ils = float(match.group(1)), match.group(2), int(match.group(3)), int(match.group(4)), float(match.group(5)), float(match.group(6)), float(match.group(7).replace(",", ""))
                self.close(top, caps["max"] * m)
                self.assertEqual((nights, travellers, bool(up)), (13, 2, item["listed"]))
                self.close(top * nights * travellers, t)
                self.close(t * rate, item["ilsPotential"], "dollars times the rate is the possible maximum in shekels")
                self.assertLessEqual(abs(ils - t * rate), 0.005 + 1e-9)
                bounds = range_pattern.match(item["range"]["he"])
                self.assertIsNotNone(bounds, item["range"]["he"])
                self.close(float(bounds.group(1)), caps["floor"] * m)
                self.close(float(bounds.group(2)), caps["max"] * m)
                for pair in (item["potential"], item["range"]):
                    self.assertIsNone(HEBREW.search(pair["en"]), pair["en"])
                    self.assertEqual(numbers(pair["en"]), numbers(pair["he"]))
        sample = next(item for item in self.seen["items"] if (item["year"], item["listed"]) == (2026, False))
        self.assertTrue(sample["potential"]["en"].startswith("Maximum possible: USD 273.75 per night · nights: 13 · travellers: 2 = USD "))
        self.assertEqual(sample["range"]["en"], "Range per night per traveller: USD 160–273.75. The actual cap depends on the amount.")

    def test_the_live_education_sentence_is_the_rounded_one_of_the_table_in_both_languages(self):
        pattern = EXPLANATIONS["education"][0][1]
        for item in self.seen["items"]:
            text = item["eduExplain"]
            with self.subTest(year=item["year"], listed=item["listed"]):
                match = pattern.match(text["he"])
                self.assertIsNotNone(match, text["he"])
                rate, children, months, days, total = float(match.group(1)), int(match.group(2)), float(match.group(3)), int(match.group(4)), float(match.group(5).replace(",", ""))
                self.assertEqual((rate, children, days), (EDUCATION_USD[item["year"]][0], 2, 305))
                self.assertLessEqual(abs(months - 305 * 12 / 365), 0.00005 + 1e-12)
                self.assertLessEqual(abs(total - item["ilsEdu"] / 3.5), 0.005 + 1e-9)
                self.assertIsNone(HEBREW.search(text["en"]), text["en"])
                self.assertEqual(numbers(text["en"]), numbers(text["he"]))
                self.assertIn("months: %.4f (trip days: 305 × 12 ÷ 365)" % months, text["en"])
                self.assertNotIn("10.02739", text["he"])

    def test_the_conversion_sentence_divides_the_shekel_cap_by_the_rate_to_the_agora(self):
        pattern = re.compile(r"^המרה ל־([A-Z]{3}): " + ILS + r" ₪ ÷ " + NUM + " = " + ILS + r" ([A-Z]{3})\.$")
        for item in self.seen["items"]:
            for key, code, rate, ils_key, value_key in (("conversion", "EUR", 4.0, "ilsLodging", "valueLodging"), ("eduConversion", "JPY", 0.024, "ilsEdu", "valueEdu")):
                text = item[key]["he"]
                with self.subTest(year=item["year"], listed=item["listed"], code=code):
                    match = pattern.match(text)
                    self.assertIsNotNone(match, text)
                    self.assertEqual((match.group(1), match.group(5)), (code, code))
                    shekels, shown_rate, value = float(match.group(2).replace(",", "")), float(match.group(3)), float(match.group(4).replace(",", ""))
                    self.close(shown_rate, rate)
                    self.assertLessEqual(abs(shekels - item[ils_key]), 0.005 + 1e-9)
                    # the shekel figure in the sentence is shown to the agora, and dividing by a small rate widens that
                    self.assertLessEqual(abs(value - shekels / shown_rate), 0.005 / shown_rate + 0.005 + 1e-9)
                    self.assertLessEqual(abs(value - item[value_key]), 0.005 + 1e-9)
                    self.assertIsNone(HEBREW.search(item[key]["en"]), item[key]["en"])
                    self.assertEqual(numbers(item[key]["en"]), numbers(text))
        self.assertTrue(self.seen["items"][0]["conversion"]["en"].startswith("Conversion to EUR: ILS "))

    def test_the_rate_sentences_state_the_table_figures_and_translate_with_the_same_numbers(self):
        patterns = {
            "lodging7": (r"^" + NUM + r" דולר ללילה לנוסע" + UPLIFT + "$", lambda c, m: [c["lodging7"] * m]),
            "lodgingAll": (r"^" + NUM + r" דולר ללילה לנוסע" + UPLIFT + "$", lambda c, m: [c["floor"] * m]),
            "lodging90": (r"^סף " + NUM + r" דולר, מקסימום " + NUM + r" דולר ללילה לנוסע" + UPLIFT + "$", lambda c, m: [c["floor"] * m, c["max"] * m]),
            "perDiem": (r"^" + NUM + r" דולר ליום עם לינה, " + NUM + r" דולר ליום בלי לינה, לנוסע" + UPLIFT + "$", lambda c, m: [c["perDiemLodging"] * m, c["perDiemNoLodging"] * m]),
            "car": (r"^" + NUM + r" דולר ליום לנוסע" + UPLIFT + "$", lambda c, m: [c["car"] * m]),
            "gifts": (r"^" + NUM + r" דולר לנוסע \(ללא תוספת 25%\)$", lambda c, m: [c["gift"]]),
        }
        seen = set()
        for item in self.seen["rates"]:
            caps = self.seen["caps"][str(item["year"])]
            m = 1.25 if item["listed"] else 1
            with self.subTest(year=item["year"], listed=item["listed"], key=item["key"]):
                if item["key"] == "education":
                    match = re.match(r"^" + NUM + r" דולר לילד לחודש$", item["he"])
                    self.assertIsNotNone(match)
                    self.assertEqual(float(match.group(1)), EDUCATION_USD[item["year"]][0])
                else:
                    regex, expected = patterns[item["key"]]
                    match = re.match(regex, item["he"])
                    self.assertIsNotNone(match, item["he"])
                    figures = [float(group) for group in match.groups()[:len(expected(caps, m))]]
                    for shown, wanted in zip(figures, expected(caps, m)):
                        self.close(shown, wanted)
                    if item["key"] != "gifts":
                        self.assertEqual(bool(match.groups()[len(figures)]), item["listed"])
                seen.add(item["key"])
                self.assertIsNone(HEBREW.search(item["en"]), item["en"])
                self.assertEqual(numbers(item["en"]), numbers(item["he"]))
        self.assertEqual(seen, set(CAP_KEYS))
        self.assertEqual(sorted({item["en"] for item in self.seen["rates"] if item["key"] == "gifts"}), ["USD 15 per traveller (no 25% uplift)"])


FLIGHT_SENTENCE = "! שימו לב: במחלקה ראשונה מוכר רק עד מחיר מחלקת עסקים באותה טיסה; הכלי אינו מגביל זאת."


class InfoTipMarkupTests(unittest.TestCase):
    def setUp(self):
        self.page = travel_page()

    def test_the_exclamation_is_a_focusable_button_outside_the_title_with_its_own_accessible_name(self):
        self.assertIn('<h3 id="tt-flight-title">טיסה</h3>', self.page)                    # the title is just the title
        self.assertIn('<button type="button" class="info-tip-button" aria-label="הערה על מחלקה ראשונה" aria-describedby="tt-flight-note">'
                      '<span aria-hidden="true">!</span></button>', self.page)
        head = re.search(r'<div class="travel-head">(.*?)</div>', self.page, re.S).group(1)
        self.assertTrue(head.index("</h3>") < head.index("<button"))
        self.assertEqual(re.findall(r"<h3[^>]*>(.*?)</h3>", head), ["טיסה"])

    def test_the_sentence_is_a_tooltip_the_button_describes_and_it_is_nowhere_else_on_the_page(self):
        self.assertIn('<span class="info-tip-text" id="tt-flight-note" role="tooltip">' + FLIGHT_SENTENCE + "</span>", self.page)
        self.assertEqual(self.page.count(FLIGHT_SENTENCE), 1)
        self.assertEqual(self.page.count("tt-flight-note"), 2)                            # the id, and the one description that points at it
        self.assertIn('aria-describedby="tt-flight-cap"', self.page)                      # the amount field has the cap, not the sentence
        self.assertNotIn("! שימו לב", TRAVEL)
        self.assertIn("'%s'" % FLIGHT_SENTENCE, (ROOT / "assets/statso-lang-en.js").read_text(encoding="utf-8"))

    def test_the_method_pages_keep_the_documentary_sentence_in_both_languages(self):
        # the method page documents the first-class limit in prose, once per language; the button holds the form's sentence
        self.assertEqual(HTML.count("במחלקה ראשונה ההכרה מוגבלת למחיר מחלקת עסקים, אך הכלי אינו אוכף זאת."), 1)
        self.assertEqual(HTML.count("First-class fares are limited to the business-class fare, but the tool does not enforce this."), 1)


INFO_TIP = r"""
global.window = {}; const docHandlers = {};
global.document = {addEventListener(type, fn) { (docHandlers[type] = docHandlers[type] || []).push(fn); }, querySelectorAll: () => tips,
  activeElement: 'the-button'};
""" + module("statso-core.js") + r"""
const core = window.Statso.core;
function mkTip(name) {
  const attrs = {}, tip = {name, attrs, handlers: {}, hovered: false, focused: false};
  tip.getAttribute = n => n in attrs ? attrs[n] : null;
  tip.setAttribute = (n, v) => { attrs[n] = String(v); };
  tip.removeAttribute = n => { delete attrs[n]; };
  tip.addEventListener = (type, fn) => { (tip.handlers[type] = tip.handlers[type] || []).push(fn); };
  tip.button = {handlers: {}, addEventListener(type, fn) { (this.handlers[type] = this.handlers[type] || []).push(fn); }};
  tip.text = {tip};
  tip.contains = node => node === tip || node === tip.button || node === tip.text;
  tip.querySelector = sel => sel === '.info-tip-button' ? tip.button : sel === '.info-tip-text' ? tip.text : null;
  return tip;
}
const tips = [mkTip('a'), mkTip('b')];
const clear = tip => Object.keys(tip.attrs).forEach(name => { delete tip.attrs[name]; });
// what the stylesheet decides: shown on hover or focus or after a press, unless it was dismissed
window.getComputedStyle = node => { const t = node.tip; return {display: t.attrs['data-closed'] !== 'true' && (t.attrs['data-open'] === 'true' || t.hovered || t.focused) ? 'block' : 'none'}; };
const shown = tip => window.getComputedStyle(tip.text).display === 'block';
const call = (target, type, event) => (target.handlers[type] || []).forEach(fn => fn(event || {}));
const keydown = key => { const event = {key, defaultPrevented: false, preventDefault() { this.defaultPrevented = true; }}; (docHandlers.keydown || []).forEach(fn => fn(event)); return event; };
const scope = {querySelectorAll: () => tips};
core.initInfoTips(scope); core.initInfoTips(scope);
const out = {};
out.listeners = {keydown: docHandlers.keydown.length, click: docHandlers.click.length, buttonClicks: tips.map(t => t.button.handlers.click.length)};
const [a, b] = tips;
// a press opens, the next press closes (the stylesheet alone would keep it open while the pointer stays), and again opens
call(a.button, 'click'); out.first = {open: a.attrs['data-open'], closed: a.attrs['data-closed'] || null, shown: shown(a)};
call(a.button, 'click'); out.second = {open: a.attrs['data-open'] || null, closed: a.attrs['data-closed'] || null, shown: shown(a)};
call(a.button, 'click'); out.third = {open: a.attrs['data-open'], closed: a.attrs['data-closed'] || null, shown: shown(a)};
// Escape closes whatever is showing, leaves the focus where it is and does not cancel the key for anything else
b.focused = true; const before = document.activeElement;
const esc = keydown('Escape');
out.escape = {a: a.attrs['data-closed'] || null, aOpen: a.attrs['data-open'] || null, b: b.attrs['data-closed'] || null, shownB: shown(b), active: document.activeElement === before, prevented: esc.defaultPrevented};
keydown('Enter'); out.otherKey = {a: a.attrs['data-closed'] || null};
// hovering or focusing again opens it again
a.hovered = true; call(a, 'mouseenter'); out.hover = {closed: a.attrs['data-closed'] || null, shown: shown(a)};
b.focused = true; call(b, 'focusin'); out.focus = {closed: b.attrs['data-closed'] || null, shown: shown(b)};
// leaving the tip clears the state; moving inside it does not
a.attrs['data-open'] = 'true'; a.attrs['data-closed'] = 'true';
call(a, 'focusout', {relatedTarget: a.button}); out.inside = {open: a.attrs['data-open'] || null, closed: a.attrs['data-closed'] || null};
call(a, 'focusout', {relatedTarget: {}}); out.leave = {open: a.attrs['data-open'] || null, closed: a.attrs['data-closed'] || null};
// a tap outside closes a tip that a tap opened
a.attrs['data-open'] = 'true'; b.attrs['data-open'] = 'true';
(docHandlers.click || []).forEach(fn => fn({target: a.text}));
out.outside = {a: a.attrs['data-open'] || null, b: b.attrs['data-open'] || null};
// a tap: the pointer goes down before the focus arrives, and focus alone already shows the text, so the press must open and not close
clear(a); a.hovered = false; a.focused = false; call(a.button, 'pointerdown'); a.focused = true; call(a.button, 'click');
out.tap = {open: a.attrs['data-open'], closed: a.attrs['data-closed'] || null};
// the keyboard: no pointer, the focus is already there and shows the text, so Enter closes it
clear(a); a.hovered = false; a.focused = true; call(a.button, 'click');
out.keyboard = {open: a.attrs['data-open'] || null, closed: a.attrs['data-closed'] || null};
// a press that was cancelled (a scroll took over), then the keyboard: the text is shown by the focus, and Enter must close it
clear(a); a.hovered = false; a.focused = false; call(a.button, 'pointerdown'); call(a.button, 'pointercancel'); a.focused = true; call(a.button, 'click');
out.cancelled = {open: a.attrs['data-open'] || null, closed: a.attrs['data-closed'] || null};
// a press dragged off the button (no click), then a click that did not come from a pointer (detail 0: keyboard or assistive technology)
clear(a); a.hovered = false; a.focused = false; call(a.button, 'pointerdown'); a.focused = true; call(a.button, 'click', {detail: 0});
out.dragged = {open: a.attrs['data-open'] || null, closed: a.attrs['data-closed'] || null};
process.stdout.write(JSON.stringify(out));
"""


class InfoTipBehaviourTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seen = node(INFO_TIP)

    def test_one_document_listener_serves_every_tip_however_often_it_is_initialised(self):
        self.assertEqual(self.seen["listeners"], {"keydown": 1, "click": 1, "buttonClicks": [1, 1]})

    def test_a_press_opens_the_next_press_closes_and_a_third_opens_again(self):
        self.assertEqual(self.seen["first"], {"open": "true", "closed": None, "shown": True})
        self.assertEqual(self.seen["second"], {"open": None, "closed": "true", "shown": False})
        self.assertEqual(self.seen["third"], {"open": "true", "closed": None, "shown": True})

    def test_escape_closes_without_moving_the_focus_or_cancelling_the_key(self):
        self.assertEqual(self.seen["escape"], {"a": "true", "aOpen": None, "b": "true", "shownB": False, "active": True, "prevented": False})
        self.assertEqual(self.seen["otherKey"], {"a": "true"})            # another key leaves the state as Escape set it

    def test_a_new_hover_or_a_new_focus_opens_it_again(self):
        self.assertEqual(self.seen["hover"], {"closed": None, "shown": True})
        self.assertEqual(self.seen["focus"], {"closed": None, "shown": True})

    def test_leaving_clears_the_state_and_moving_inside_keeps_it(self):
        self.assertEqual(self.seen["inside"], {"open": "true", "closed": "true"})
        self.assertEqual(self.seen["leave"], {"open": None, "closed": None})
        self.assertEqual(self.seen["outside"], {"a": "true", "b": None})        # a click on the tip's own text keeps it, elsewhere closes

    def test_a_press_that_never_became_a_click_does_not_decide_a_later_keyboard_click(self):
        # both cases leave the focus showing the text, so the keyboard click closes it: neither stale value may open it
        self.assertEqual(self.seen["cancelled"], {"open": None, "closed": "true"})
        self.assertEqual(self.seen["dragged"], {"open": None, "closed": "true"})

    def test_a_tap_opens_even_though_the_focus_has_already_shown_the_text_and_the_keyboard_closes(self):
        self.assertEqual(self.seen["tap"], {"open": "true", "closed": None})
        self.assertEqual(self.seen["keyboard"], {"open": None, "closed": "true"})


EDUCATION_FLOW = r"""
(async () => {
  const o = {};
  window.location.hash = '#/accounting/travel';
  T2.init(); await tick();
  (windowHandlers.hashchange || []).forEach(fn => fn()); await tick();
  els['tt-depart'].value = '2026-03-06'; els['tt-return'].value = '2027-01-04'; fire('tt-return', 'change');
  els['tt-lodgingAll-amount'].value = '5000'; els['tt-children'].value = '2'; els['tt-education-amount'].value = '3000'; fire('tt-education-amount');
  o.calc = snapshot();
  els['tt-xlsx'].click(); els['tt-pdf'].click(); els['tt-docx'].click();
  o.files = out.files; o.pdf = out.pdf;
  process.stdout.write(JSON.stringify(o));
})();
"""


class EducationExportTests(unittest.TestCase):
    """The education row and its source remark are an ordinary row of the report in every file, in both languages."""

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.dir = Path(cls.temp.name)
        cls.results = {lang: ui(lang, cls.dir, EDUCATION_FLOW) for lang in ("he", "en")}
        cls.parts = {}
        for lang in ("he", "en"):
            for kind in ("xlsx", "docx"):
                archive = zipfile.ZipFile(cls.dir / ("%s.%s" % (lang, kind)))
                cls.parts[lang, kind] = "".join(archive.read(name).decode("utf-8") for name in archive.namelist() if name.endswith(".xml"))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_the_row_the_source_remark_and_the_rule_are_in_the_table_the_workbook_the_word_file_and_the_pdf(self):
        he = {"label": "חינוך ילדים", "remark": "נלקח מאתרי רואי חשבון ולא ממקור רשמי", "rule": "תקנה 2(2)(ז)", "limit": "הכלי מגביל לסכום שבתקנה"}
        en = {"label": "Children’s education", "remark": "was taken from accountants’ websites and not from an official source",
              "rule": "regulation 2(2)(g)", "limit": "the tool limits the cap to the amount in the regulation"}
        for lang, words in (("he", he), ("en", en)):
            result = self.results[lang]
            for where, text in (("table", result["calc"]["body"] + result["calc"]["notes"]), ("xlsx", self.parts[lang, "xlsx"]),
                                ("docx", self.parts[lang, "docx"]), ("pdf", result["pdf"]["translated"])):
                with self.subTest(lang=lang, file=where):
                    for key, phrase in words.items():
                        self.assertIn(phrase, text, key)

    def test_the_rounded_months_and_dollars_are_in_every_file_and_the_long_decimals_are_in_none(self):
        for lang in ("he", "en"):
            result = self.results[lang]
            for where, text in (("table", result["calc"]["body"]), ("xlsx", self.parts[lang, "xlsx"]), ("docx", self.parts[lang, "docx"]),
                                ("pdf", result["pdf"]["translated"])):
                with self.subTest(lang=lang, file=where):
                    self.assertIn("10.0274", text)
                    self.assertIn("18,330.08", text)
                    self.assertNotIn("10.02739", text)
                    self.assertNotIn("18330.08", text)
                    if lang == "en":
                        self.assertIn("months: 10.0274", text)
                        self.assertIn("USD 18,330.08", text)

    def test_the_english_files_have_no_hebrew(self):
        for text in (self.parts["en", "xlsx"], self.parts["en", "docx"], self.results["en"]["pdf"]["translated"]):
            self.assertIsNone(HEBREW.search(text), HEBREW.findall(text)[:5])

    def test_the_row_enters_the_totals_like_any_other_row(self):
        calc = self.results["he"]["calc"]
        self.assertEqual(re.findall(r'<th scope="row">(.*?)</th>', calc["body"])[-1], "חינוך ילדים")
        self.assertEqual(calc["body"].count("<tr>"), 11)                      # eleven rows on a long stay: one lodging row, and education
        self.assertIn("28,000.00", calc["foot"])                               # 5000 + 3000 dollars at 3.5
        self.assertIn("28,000.00", self.results["he"]["pdf"]["html"])


STICKY_FLOW = r"""
(async () => {
  const o = {};
  window.location.hash = '#/accounting/travel';
  T2.init(); await tick();
  (windowHandlers.hashchange || []).forEach(fn => fn()); await tick();
  els['tt-depart'].value = '2026-03-06'; els['tt-return'].value = '2026-03-25'; fire('tt-return', 'change');
  els['tt-lodging90-amount'].value = '500'; fire('tt-lodging90-amount');
  // 102 nights: only the later-nights amount was typed, and it is in a group that goes away
  els['tt-return'].value = '2026-06-15'; fire('tt-return', 'change');
  o.onlyLater = snapshot();
  // the business days are retyped to a value that is not valid: the groups stay as they were
  els['tt-business-days'].value = '200'; fire('tt-business-days');
  o.badDays = snapshot();
  // a stay of over 10 months
  els['tt-return'].value = '2027-01-04'; els['tt-business-days'].value = '305'; fire('tt-business-days');
  o.edu = snapshot();
  // the return date is cleared while the education group is there: it stays
  els['tt-return'].value = ''; fire('tt-return', 'change');
  o.noReturn = snapshot();
  process.stdout.write(JSON.stringify(o));
})();
"""


class ModeSwitchTests(unittest.TestCase):
    """The groups that come and go keep their state while a field is mid-edit, and say what was typed into a hidden one."""

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.seen = ui("he", Path(cls.temp.name), STICKY_FLOW)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_an_amount_typed_only_in_the_later_nights_group_is_kept_and_said_when_it_is_hidden(self):
        later = self.seen["onlyLater"]
        self.assertEqual(later["groupsHidden"], {"lodging7": True, "lodging90": True, "lodgingAll": False, "education": True})
        self.assertIn("נשמרו, אך אינם נכללים בחישוב", later["modes"]["lodgingKept"])

    def test_invalid_business_days_while_typing_do_not_flip_the_lodging_groups(self):
        bad, later = self.seen["badDays"], self.seen["onlyLater"]
        self.assertTrue(bad["error"])                                           # 200 business days in a trip of 102 days is an error
        self.assertEqual(bad["groupsHidden"], later["groupsHidden"])
        self.assertEqual(bad["modes"]["lodging"], "בשל נסיעה של מעל 90 לילות יש להזין את הלינה בשורה אחת.")

    def test_the_education_group_appears_over_ten_months_and_stays_while_the_dates_are_incomplete(self):
        self.assertFalse(self.seen["edu"]["groupsHidden"]["education"])
        gone = self.seen["noReturn"]
        self.assertTrue(gone["error"])
        self.assertFalse(gone["groupsHidden"]["education"])
        self.assertEqual(gone["modes"]["education"], "")


class StylesheetInfoTipTests(unittest.TestCase):
    css = (ROOT / "assets/statso.css").read_text(encoding="utf-8")

    def declarations(self, selector):
        match = re.search(r"(?m)^" + re.escape(selector) + r" \{([^{}]*)\}", self.css)
        self.assertIsNotNone(match, selector)
        return match.group(1)

    def test_the_button_is_a_round_target_of_at_least_24_pixels(self):
        rule = self.declarations(".info-tip-button")
        self.assertIn("inline-size: 24px", rule)
        self.assertIn("block-size: 24px", rule)
        self.assertIn("border-radius: 50%", rule)
        self.assertIn("border: 2px solid var(--navy)", rule)                     # a ring and a bold sign: not colour alone
        self.assertIn("font-weight: 800", rule)

    def test_hover_exists_only_for_a_fine_hovering_pointer(self):
        outside = re.sub(r"@media \(hover: hover\) and \(pointer: fine\) \{[^\n]*\}\n", "", self.css)
        self.assertNotIn(".info-tip:hover", outside)
        self.assertNotIn(".info-tip-button:hover", outside)
        self.assertIn("@media (hover: hover) and (pointer: fine) { .info-tip:hover .info-tip-text { display: block; } }", self.css)
        self.assertIn("@media (hover: hover) and (pointer: fine) { .info-tip-button:hover { background: var(--blue-tint-soft); } }", self.css)

    def test_focus_and_press_show_the_text_and_dismissal_wins_over_everything_outside_any_query(self):
        # the stylesheet may not use :focus-within anywhere (a11y source test): the button is the one focusable thing in a tip
        self.assertNotIn(":focus-within", self.css)
        self.assertRegex(self.css, r'(?m)^\.info-tip-button:focus \+ \.info-tip-text, \.info-tip\[data-open="true"\] \.info-tip-text \{ display: block; \}')
        self.assertRegex(self.css, r'(?m)^\.info-tip\[data-closed="true"\] \.info-tip-text \{ display: none !important; \}')
        self.assertLess(self.css.index(':focus + .info-tip-text'), self.css.index('[data-closed="true"] .info-tip-text'))

    def test_the_text_stays_inside_its_row_and_has_no_gap_the_pointer_could_fall_through(self):
        rule = self.declarations(".info-tip-text")
        self.assertIn("inset-inline: 0", rule)
        self.assertIn("top: 100%", rule)
        self.assertIn("overflow-wrap: anywhere", rule)
        self.assertNotIn("margin", rule)
        self.assertNotIn("box-shadow", rule)
        self.assertIn("align-self: stretch", self.declarations(".info-tip"))

    def test_the_live_cap_figure_is_red_and_the_sentence_under_it_is_the_muted_text_colour(self):
        self.assertIn("color: #b42318", self.declarations(".travel-cap-value"))
        self.assertIn("color: var(--muted)", self.declarations(".travel-cap-explain"))
        rule = self.declarations(".travel-cap, .travel-cap-free")
        self.assertIn("min-width: 0", rule)
        self.assertIn("overflow-wrap: anywhere", rule)


if __name__ == "__main__":
    unittest.main()
