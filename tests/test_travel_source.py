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

    def test_the_notes_carry_flight_education_and_currency(self):
        notes = self.s["lodging"]["notes"]
        self.assertTrue(any(note.startswith("! שימו לב") and "מחלקה ראשונה" in note for note in notes))
        self.assertTrue(any("חינוך ילדים" in note for note in notes))
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
}


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
  Object.assign({travelers: 1, rows: {perDiem: 1, car: 1}}, one)
];
const wanted = new Set(['lodging7', 'lodging90', 'lodgingAll', 'perDiem', 'car', 'gifts']);
for (const listed of [false, true]) for (const year of T.YEARS) for (const scenario of scenarios) {
  const i = inp(Object.assign({year, listed}, scenario));
  const model = T.calculate(i, quoteFor(i.depart));
  model.rows.filter(row => wanted.has(row.key) && row.cap !== null).forEach(row => items.push({year, listed, key: row.key, explain: row.explain,
    english: translate(row.explain), cap: row.cap, usd: model.rates[0].rate, L: model.nights, B: i.businessDays, N: i.travelers,
    K: i.partial ? i.lodgingDays : null}));
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
                    self.close(t * usd, cap, "dollars times the rate is the cap in shekels")
                    self.assertLessEqual(abs(ils - t * usd), 0.005 + 1e-9, "the shekel figure is the cap, shown to the agora")
                # the uplift is named when, and only when, it was applied (never on gifts; not in the sentences that apply no cap)
                if item["key"] != "gifts" and variant not in ("none",):
                    self.assertEqual(bool(up), item["listed"], "uplift mark")
                self.assertEqual(numbers(item["english"]), numbers(item["explain"]), "the same figures in English")
                self.assertIsNone(HEBREW.search(item["english"]))
        # coverage: every kind of sentence the tool can write was exercised
        for combination in (("lodging7", "night"), ("lodgingAll", "all"), ("lodging90", "above"), ("lodging90", "upto"),
                            ("perDiem", "full"), ("perDiem", "partial"), ("car", "day"), ("gifts", "person")):
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
  model.rows.forEach(item => { sentences.add(item.explain); explains.add(item.explain); sentences.add(item.label); });
  model.notes.forEach(note => sentences.add(note)); model.errors.forEach(error => sentences.add(error.message)); }
const nights = {depart: '2026-03-06', ret: '2026-03-25'}, long = {depart: '2026-01-01', ret: '2026-04-10'};
for (const listed of [false, true]) for (const year of [2018, 2024, 2025, 2026]) {
  [{rows: {lodging7: 4000, lodging90: 100, perDiem: 10, car: 10, gifts: 10, flight: 1, other: 1}},
   Object.assign({rows: {lodging90: 3900}}, nights), Object.assign({rows: {lodging90: 2340}}, nights),
   Object.assign({rows: {lodging90: 5200}}, nights), Object.assign({rows: {lodging90: 1950, lodging7: 1}}, nights),
   Object.assign({rows: {lodging7: 2000, lodging90: 20000, perDiem: 5}}, long),
   {travelers: 2, partial: true, lodgingDays: 3, rows: {lodging7: 1, perDiem: 1}},
   {businessDays: 3, partial: false, rows: {lodging7: 1}}, {depart: '2026-04-30', ret: '2026-04-30', rows: {flight: 1, insurance: [1, 'EUR'], phone: [1, 'JPY']}},
   {depart: '2026-12-31', ret: '2026-12-31', rows: {flight: 1}}, {rows: {insurance: [1, 'ILS']}}
  ].forEach(o => take(run(Object.assign({year, listed}, o))));
}
KEYS.forEach(key => take(run({rows: {[key]: -1}})));
KEYS.forEach(key => take(run({rows: {[key]: [1, 'XXX']}})));
[{businessDays: 0}, {businessDays: 9}, {partial: true, lodgingDays: 5}, {depart: '2026-03-06', ret: '2026-03-06', partial: true, lodgingDays: 1}, {partial: true, lodgingDays: 0}, {depart: '2026-03-10', ret: '2026-03-06'},
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
function counted(id, prop) {
  const e = mkEl(id); let held = '';
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
els['result-live'] = mkEl('result-live');
global.document = {title: 't', addEventListener() {}, getElementById(id) { return els[id] || (els[id] = mkEl(id)); },
  querySelectorAll(selector) { const m = /data-error-flag="([^"]+)"/.exec(selector);
    return m ? Object.values(els).filter(e => e.attrs['data-error-flag'] === m[1]) : []; }};
""" + module("statso-core.js") + module("statso-xlsx.js") + module("statso-export.js") + module("statso-docx.js") \
    + module("statso-lang-en.js") + TRANSLATE + r"""
const S = window.Statso;
const KEYS = %(keys)s;
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
  described: els['tt-business-days'].attrs['aria-describedby'] || ''});
%(steps)s
"""


def ui(lang, out, steps):
    return node(UI % {"lang": json.dumps(lang), "out": json.dumps(str(out)), "keys": json.dumps(KEYS),
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
        self.assertIn("! שימו לב", calc["body"])                # the first-class remark sits in the flight row itself
        self.assertIn("! שימו לב", calc["notes"])
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

    def test_the_eleven_expense_groups_are_named_and_their_fields_carry_the_group_name(self):
        groups = re.findall(r'<div class="travel-expense" role="group" aria-labelledby="(tt-[A-Za-z0-9]+-title)">', self.page)
        self.assertEqual(len(groups), 11)
        for key, title in zip(KEYS, groups):
            self.assertEqual(title, "tt-%s-title" % key)
            self.assertIn('id="tt-%s-amount" type="number" min="0" step="any" aria-labelledby="%s tt-%s-amount-label"' % (key, title, key),
                          self.page.replace(' aria-describedby="tt-flight-note"', ""))
            self.assertIn('<select id="tt-%s-currency" aria-labelledby="%s tt-%s-currency-label">' % (key, title, key), self.page)

    def test_the_flight_remark_is_visible_starts_with_an_exclamation_and_describes_the_field(self):
        note = re.search(r'<p class="travel-wide rent-hint" id="tt-flight-note">(.*?)</p>', self.page).group(1)
        self.assertTrue(note.startswith("! שימו לב"))
        self.assertIn('aria-describedby="tt-flight-note"', self.page)

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

    def test_the_currency_remark_and_the_education_remark_are_visible_under_the_form(self):
        self.assertIn("אם הנסיעה הייתה במטבע שאינו אחד מהמטבעות הנתמכים באתר, יש להזין את הסכומים בש״ח לאחר המרה.", self.page)
        self.assertIn("חינוך ילדים בנסיעה מעל 10 חודשים אינו מחושב", self.page)

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


if __name__ == "__main__":
    unittest.main()
