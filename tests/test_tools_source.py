import re
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent

TOOLS = [("index", "tool-index-page", "ti"), ("fx", "tool-fx-page", "tf"),
         ("history", "tool-history-page", "th"),
         ("fx-history", "tool-fx-history-page", "fxh"), ("rent", "tool-rent-page", "tr")]


class ToolsSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "index.html").read_text(encoding="utf-8")
        cls.scripts = {p.name: p.read_text(encoding="utf-8") for p in (ROOT / "assets").glob("*.js")}

    def test_every_tool_has_a_route_a_page_and_both_exports(self):
        nav = self.scripts["statso-nav.js"]
        for route, page, prefix in TOOLS:
            self.assertIn(f"'#/tools/{route}': '{page}'", nav)
            self.assertIn(f'id="{page}"', self.html)
            self.assertIn(f'id="{prefix}-xlsx"', self.html)
            self.assertIn(f'id="{prefix}-pdf"', self.html)

    def test_the_history_tool_can_copy_to_the_clipboard(self):
        self.assertIn('id="th-copy"', self.html)
        self.assertIn("copyText", self.scripts["statso-tools.js"])

    def test_printing_restores_the_page_once_and_only_once(self):
        text = self.scripts["statso-export.js"]
        self.assertIn("if (restored) { return; }", text)
        self.assertNotIn("setTimeout(restore", text)
        self.assertLess(text.index("root.print();"), text.index("restore();\n    return true;"))

    def test_fx_history_offers_currencies_a_range_and_a_resolution(self):
        for field in ('id="fxh-currencies"', 'id="fxh-from"', 'id="fxh-to"',
                      'id="fxh-resolution"', 'id="fxh-copy"', 'id="fxh-averages"'):
            self.assertIn(field, self.html)
        for value in ('value="daily"', 'value="weekly"', 'value="monthly"', 'value="yearly"'):
            self.assertIn(value, self.html)

    def test_fx_history_averages_the_period_and_never_truncates_the_export(self):
        text = self.scripts["statso-fxhistory.js"]
        self.assertIn("cell.sum / cell.count", text)
        self.assertIn("count ? total / count : null", text)
        self.assertIn("rows.slice(0, MAX_RENDERED_ROWS)", text)
        matrix = text.split("function matrix()")[1].split("function subtitle()")[0]
        self.assertNotIn("MAX_RENDERED_ROWS", matrix, "the export must cover the whole range")

    def test_old_rates_are_not_rounded_away(self):
        core = self.scripts["statso-core.js"]
        self.assertIn("function formatRateSmart(x)", core)
        self.assertIn("formatRateSmart: formatRateSmart", core)
        self.assertIn("Statso.core.formatRateSmart", self.scripts["statso-fxhistory.js"])

    def test_the_dashboard_calculator_is_still_there(self):
        for marker in ('id="calculator-section"', 'name="calc-kind"', 'id="calc-amount"'):
            self.assertIn(marker, self.html)

    def test_chart_marks_the_five_requested_events(self):
        text = self.scripts["statso-chart.js"]
        for month, label in (("2008-09", "סאב"), ("2020-03", "קורונה"), ("2023-10", "7 באוקטובר"),
                             ("2025-06", "הראשונה"), ("2026-02", "השנייה")):
            self.assertRegex(text, r"month: '" + month + r"', label: '[^']*" + label)
        self.assertIn("#e8590c", text)

    def test_rent_tool_covers_every_field_the_brief_asked_for(self):
        for field in ('id="tr-contract-date"', 'id="tr-landlord"', 'id="tr-tenant"',
                      'id="tr-base-start"', 'id="tr-base-end"', 'id="tr-base-rent"',
                      'id="tr-has-options"', 'id="tr-add-option"', 'id="tr-custom-base"',
                      'name="tr-floor"', 'id="tr-export-period"', 'id="tr-exclude-paid"'):
            self.assertIn(field, self.html)

    def test_linkage_never_falls_below_nominal_when_the_floor_is_chosen(self):
        text = self.scripts["statso-rent.js"]
        self.assertIn("form.floor === 'floor' ? Math.max(1, rawRatio) : rawRatio", text)

    def test_readings_shown_to_people_share_one_base(self):
        core = self.scripts["statso-core.js"]
        self.assertIn("function readingInBase(map, baseMonth, month)", core)
        self.assertIn("readingInBase: readingInBase", core)
        self.assertIn("Statso.core.readingInBase", self.scripts["statso-rent.js"])
        self.assertIn("Statso.core.readingInBase", self.scripts["statso-tools.js"])

    def test_the_offline_build_can_inline_every_new_module(self):
        forbidden = ("</script", "</style", "<!--", "-->")
        for name in ("statso-xlsx.js", "statso-export.js", "statso-tools.js", "statso-rent.js"):
            self.assertIn(name, self.html, f"{name} is not loaded by the page")
            for token in forbidden:
                self.assertNotIn(token, self.scripts[name], f"{token!r} would fail the offline build")

    def test_fx_card_says_which_trading_day_the_rate_belongs_to(self):
        card = re.search(r'<article class="kpi-card[^"]*" id="fx-kpi".*?</article>', self.html, re.DOTALL).group(0)
        self.assertIn("מעודכן לסוף יום המסחר האחרון", card)


if __name__ == "__main__":
    unittest.main()
