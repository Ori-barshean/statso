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

    def test_event_chips_dodge_the_line_instead_of_reserving_a_band(self):
        text = self.scripts["statso-chart.js"]
        for gone in ("EVENT_BAND_HEIGHT", "layout:", "padding:"):
            self.assertNotIn(gone, text)
        self.assertIn("const CHIP_HEIGHT = 17;", text)
        self.assertIn("const middle = (area.top + area.bottom) / 2;", text)
        self.assertIn("chart.scales.y", text)
        self.assertIn("const placeAtBottom = isFinite(valueY) && valueY < middle;", text)
        self.assertIn("area.bottom - 4 - CHIP_HEIGHT - (bottomLane % 2) * 21", text)
        self.assertIn("area.top + 4 + (topLane % 2) * 21", text)
        self.assertIn("if (placeAtBottom) { bottomLane += 1; } else { topLane += 1; }", text)

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
                            ("terms", "terms-page"), ("privacy", "privacy-page"),
                            ("accessibility", "accessibility-page"), ("contact", "contact-page")):
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

    def test_top_nav_is_four_destinations_plus_the_tools_menu(self):
        nav = re.search(r'<nav class="site-nav".*?</nav>', self.html, re.DOTALL).group(0)
        self.assertEqual(len(re.findall(r'class="nav-item(?: [^"]+)?"', nav)), 4)
        self.assertNotIn('<br', nav)
        self.assertGreater(nav.index('href="#/mcode"'), nav.index('</ul>'))
        for href in ('href="#/"', 'href="#/guides"', 'href="#/tools"', 'href="#/mcode"'):
            self.assertIn(href, nav)
        submenu = re.search(r'<ul class="nav-submenu".*?</ul>', nav, re.DOTALL).group(0)
        self.assertEqual(submenu.count("<a "), 6)
        for route in ("index", "fx", "history", "rate-history", "fx-history", "rent"):
            self.assertIn(f'href="#/tools/{route}"', submenu)
        # the new tool must sit right after "history" and before "fx-history",
        # in both the dropdown menu and the tools-tab card grid
        self.assertLess(submenu.index('href="#/tools/history"'), submenu.index('href="#/tools/rate-history"'))
        self.assertLess(submenu.index('href="#/tools/rate-history"'), submenu.index('href="#/tools/fx-history"'))
        cards = re.search(r'<div class="tool-cards"[^>]*>.*?</div>', self.html, re.DOTALL).group(0)
        self.assertLess(cards.index('href="#/tools/history"'), cards.index('href="#/tools/rate-history"'))
        self.assertLess(cards.index('href="#/tools/rate-history"'), cards.index('href="#/tools/fx-history"'))

    def test_mcode_ids_and_module_order(self):
        for name in ("mcode-view", "mc-currencies-block", "mc-currencies", "mc-from", "mc-to", "mc-average", "mc-error", "mc-code", "mc-copy"):
            self.assertEqual(self.html.count(f'id="{name}"'), 1)
        self.assertLess(self.html.index('src="assets/statso-mcode.js"'), self.html.index('src="assets/statso-guides.js"'))
        self.assertRegex(self.html, r'<main[^>]*id="mcode-view"[\s\S]*?<h1>')

    def test_footer_links_disclaimer_and_copyright(self):
        footer = re.search(r'<footer>.*?</footer>', self.html, re.DOTALL).group(0)
        routes_in_order = re.findall(r'href="(#/[a-z-]+)"', footer)
        self.assertEqual(routes_in_order,
                          ["#/about", "#/method", "#/terms", "#/privacy", "#/accessibility", "#/contact"])
        self.assertIn("statso הוא אתר אישי וחובבני, שאינו מופעל מטעם הלשכה המרכזית לסטטיסטיקה, "
                      "בנק ישראל או גוף ממשלתי אחר.", footer)
        self.assertIn("© 2026 מפעיל האתר. נתוני המקור שייכים לגופים המפרסמים.", footer)

    def test_contact_form_accessibility_additions(self):
        self.assertIn('autocomplete="name"', self.html)
        self.assertIn('autocomplete="email"', self.html)
        contact = re.search(r'<article class="info-page" id="contact-page".*?</article>', self.html, re.DOTALL).group(0)
        self.assertIn('name="botcheck"', contact)
        self.assertNotIn('type="checkbox" name="privacy-consent"', contact)
        self.assertIn('href="#/privacy"', contact)
        text = self.scripts["statso-contact.js"]
        self.assertIn("payload.set('subject'", text)
        self.assertIn("setAttribute('role', 'status')", text)
        self.assertIn("WEB3FORMS_ACCESS_KEY", text)

    def test_method_page_stale_counts_and_broken_link_fixed(self):
        method = re.search(r'<article class="info-page" id="method-page".*?</article>', self.html, re.DOTALL).group(0)
        self.assertNotIn("Developers-Portal.aspx", method)
        self.assertIn("%D7%9E%D7%9E%D7%A9%D7%A7-API.aspx", method)
        self.assertNotIn(">899<", method)
        self.assertNotIn(">159<", method)
        self.assertIn(">22</span> בסיסים", method)
        self.assertIn(">22</span> different bases", method)

    def test_privacy_page_no_longer_claims_no_browser_storage(self):
        privacy = re.search(r'<article class="info-page" id="privacy-page".*?</article>', self.html, re.DOTALL).group(0)
        self.assertNotIn("אינו שומר דבר בדפדפן שלך", privacy)
        self.assertNotIn("stores nothing in your browser", privacy)
        for marker in ("Web3Forms", "web3forms.com/privacy", "localStorage", "45 יום", "45 days"):
            self.assertIn(marker, privacy)


if __name__ == "__main__": unittest.main()
