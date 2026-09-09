import re
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent


class UiSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "index.html").read_text(encoding="utf-8")
        cls.scripts = {p.name: p.read_text(encoding="utf-8") for p in (ROOT / "assets").glob("*.js")}

    def test_all_javascript_ids_exist(self):
        html_ids = set(re.findall(r'\bid="([^"]+)"', self.html))
        used = set()
        for text in self.scripts.values():
            used.update(re.findall(r"getElementById\(['\"]([^'\"]+)", text))
            used.update(re.findall(r"querySelector(?:All)?\(['\"]#([^'\" .:\[]+)", text))
        self.assertEqual(used - html_ids, set())

    def test_chart_contract(self):
        text = self.scripts["statso-chart.js"]
        self.assertIn("type: 'linear'", text)
        for forbidden in ("logarithmic", "Math.log", "'time'"): self.assertNotIn(forbidden, text)

    def test_calculator_default(self):
        self.assertRegex(self.html, r'<input[^>]*type="radio"[^>]*name="calc-mode"[^>]*value="known"[^>]*checked')

    def test_offline_safety(self):
        texts = [self.html, (ROOT / "assets/statso.css").read_text(encoding="utf-8")] + list(self.scripts.values())
        for text in texts:
            for forbidden in ("fonts.googleapis.com", 'type="module"', " defer", " async"):
                self.assertNotIn(forbidden, text)
        self.assertIsNone(re.search(r'(?:src|href)="/', self.html))

    def test_data_first_ordering(self):
        text = self.scripts["statso-data.js"]
        self.assertLess(text.index("textContent"), text.index("fetch("))

    def test_info_routes_and_unknown_hash_fallback(self):
        text = self.scripts["statso-nav.js"]
        for route, page in (("about", "about-page"), ("method", "method-page"),
                            ("privacy", "privacy-page"), ("contact", "contact-page")):
            self.assertIn(f"'#/" + route + "': '" + page + "'", text)
        self.assertIn("const infoPageId = infoRoutes[hash]", text)
        self.assertIn("dashboardView.hidden = guides || info", text)
        self.assertNotIn("dataReady", text)

    def test_kpi_cards_right_to_left(self):
        cards = re.findall(r'<article class="kpi-card[^"]*" id="([^"]+)"', self.html)
        self.assertEqual(cards, ["cpi-kpi", "boi-kpi", "fx-kpi", "brand-kpi"])
        for value_id in ("kpi-cpi-yoy", "kpi-cpi-yoy-range", "kpi-cpi-mom", "kpi-cpi-mom-month",
                         "kpi-boi-rate", "kpi-boi-prime", "kpi-next-decision",
                         "kpi-fx-usd", "kpi-fx-eur", "kpi-fx-date"):
            self.assertIn(f'id="{value_id}"', self.html)
        self.assertNotIn('id="kpi-cpi-value"', self.html)
        self.assertNotIn('id="yoy-kpi"', self.html)
        self.assertNotIn('id="next-kpi"', self.html)

    def test_prime_rate_is_derived_from_the_boi_rate(self):
        text = self.scripts["statso-core.js"]
        self.assertIn("const PRIME_SPREAD = 1.5;", text)
        self.assertIn("function primeRate(boiRate) { return boiRate + PRIME_SPREAD; }", text)
        self.assertNotIn("4.75", self.html)

    def test_collapsible_sections(self):
        for section_id, collapsed in (("fx-table-section", "false"), ("chart-section", "true")):
            pattern = r'<section[^>]*id="' + section_id + r'"[^>]*data-collapsed="' + collapsed + r'"'
            self.assertRegex(self.html, pattern)
            block = re.search(r'<section[^>]*id="' + section_id + r'".*?</section>', self.html, re.DOTALL).group(0)
            self.assertIn('class="section-toggle"', block)
        text = self.scripts["statso-collapse.js"]
        self.assertIn("localStorage.getItem", text)
        self.assertIn("localStorage.setItem", text)
        self.assertEqual(text.count("catch"), 2)

    def test_chart_only_renders_once_opened(self):
        text = self.scripts["statso-chart.js"]
        self.assertIn("if (started || !hasData || !opened) { return; }", text)
        self.assertIn("function activate() { opened = true; start(); }", text)
        self.assertIn("onOpen: function () { Statso.chart.activate(); }", self.scripts["statso-app.js"])

    def test_calculator_offers_both_kinds(self):
        self.assertRegex(self.html, r'name="calc-kind"[^>]*value="index"[^>]*checked')
        self.assertRegex(self.html, r'name="calc-kind"[^>]*value="fx"')
        for element_id in ("calc-fx-from", "calc-fx-to", "calc-fx-date", "calc-fx-converted", "calc-fx-rate"):
            self.assertIn(f'id="{element_id}"', self.html)
        self.assertIn("loadFxDaily", self.scripts["statso-calculator.js"])

    def test_hidden_attribute_beats_layout_rules(self):
        css = (ROOT / "assets/statso.css").read_text(encoding="utf-8")
        self.assertIn("[hidden] { display: none !important; }", css)
        for selector in (".calc-form label", ".date-group", ".calc-form fieldset"):
            self.assertLess(css.index("[hidden] { display: none !important; }"), css.index(selector + " {"),
                            f"{selector} is declared before the [hidden] reset")

    def test_calculator_mode_switch_is_wired_without_fx_data(self):
        text = self.scripts["statso-calculator.js"]
        fx_body = text.split("function initFx(")[1].split("function init(")[0]
        init_body = text.split("function init(cpiDoc, map) {")[1]
        self.assertNotIn('input[name="calc-kind"]', fx_body)
        self.assertIn('input[name="calc-kind"]', init_body)
        self.assertIn("showKind(currentKind());", init_body)

    def test_top_nav_is_three_destinations_plus_the_tools_menu(self):
        nav = re.search(r'<nav class="site-nav".*?</nav>', self.html, re.DOTALL).group(0)
        self.assertEqual(nav.count('class="nav-item"'), 2)
        for href in ('href="#/"', 'href="#/guides"', 'href="#/tools"'):
            self.assertIn(href, nav)
        submenu = re.search(r'<ul class="nav-submenu".*?</ul>', nav, re.DOTALL).group(0)
        self.assertEqual(submenu.count("<a "), 5)
        for route in ("index", "fx", "history", "fx-history", "rent"):
            self.assertIn(f'href="#/tools/{route}"', submenu)


if __name__ == "__main__": unittest.main()
