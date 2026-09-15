import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent


class A11ySourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "index.html").read_text(encoding="utf-8")
        cls.css = (ROOT / "assets/statso.css").read_text(encoding="utf-8")
        cls.nav = (ROOT / "assets/statso-nav.js").read_text(encoding="utf-8")
        cls.guides = (ROOT / "assets/statso-guides.js").read_text(encoding="utf-8")

    # ---------- skip link ---------------------------------------------------

    def test_skip_link_is_a_button_before_the_header(self):
        body_start = self.html.index("<body>")
        header_start = self.html.index('<header class="site-header">')
        skip_pos = self.html.index('id="skip-link"')
        self.assertLess(body_start, skip_pos)
        self.assertLess(skip_pos, header_start)
        self.assertRegex(self.html, r'<button[^>]*id="skip-link"[^>]*>')
        self.assertNotIn('<a href="#main"', self.html)
        self.assertNotIn('<a href="#skip-link"', self.html)

    def test_skip_link_is_wired_to_focus_the_view(self):
        self.assertIn("initSkipLink", self.nav)
        self.assertIn("getElementById('skip-link')", self.nav)

    # ---------- route focus management --------------------------------------

    def test_route_focus_and_announcement(self):
        self.assertIn("function focusView", self.nav)
        self.assertIn("function currentHeading", self.nav)
        self.assertIn("tabindex", self.nav)
        self.assertIn(".focus(", self.nav)
        self.assertEqual(self.nav.count("root.scrollTo(0, 0)"), 1)
        self.assertEqual(self.guides.count("root.scrollTo(0, 0)"), 2)
        self.assertIn("Statso.nav = {route: route, init: init, toolRoutes: toolRoutes, focusView: focusView}", self.nav)

    def test_guides_call_into_nav_focus(self):
        self.assertEqual(self.guides.count("Statso.nav.focusView"), 4)  # guard + call, in both showGuide and showIndex
        self.assertIn("function showGuide(", self.guides)
        self.assertIn("function showIndex(fromRoute)", self.guides)
        self.assertNotIn("addEventListener('click', showIndex)", self.guides)
        self.assertIn("addEventListener('click', function () { showIndex(); })", self.guides)

    # ---------- accessible tools disclosure ----------------------------------

    def test_tools_trigger_starts_collapsed_and_wired(self):
        self.assertIn('id="tools-trigger"', self.html)
        self.assertIn('aria-expanded="false"', self.html)
        self.assertIn('aria-controls="tools-submenu"', self.html)
        submenu_tag = re.search(r'<ul class="nav-submenu"[^>]*>', self.html).group(0)
        self.assertLess(submenu_tag.index('class="nav-submenu"'), submenu_tag.index('id="tools-submenu"'))
        self.assertIn("aria-expanded", self.nav)
        self.assertIn("Escape", self.nav)
        # mouse-hover convenience must survive the accessibility layer
        self.assertIn(".nav-group:hover .nav-submenu", self.css)
        # focus-within was deliberately dropped in favor of a JS-tracked
        # data-open state, so aria-expanded can never lie about it (see
        # test_tab_focus_alone_opens_the_menu_and_keeps_it_escapable)
        self.assertNotIn(":focus-within", self.css)

    def test_tab_focus_alone_opens_the_menu_and_keeps_it_escapable(self):
        # Tabbing onto the trigger (no click) must itself set data-open, or a
        # keyboard user who never clicks can open the menu (via the old
        # :focus-within convenience) into a state Escape doesn't recognize.
        self.assertIn("trigger.addEventListener('focus', open)", self.nav)
        # Escape must be document-level: a click-opened menu doesn't
        # necessarily leave focus inside .nav-group (Safari doesn't focus
        # links on click), so a group-scoped listener could miss it there.
        escape_block = re.search(r"document\.addEventListener\('keydown'.*?\}\);", self.nav, re.DOTALL)
        self.assertIsNotNone(escape_block)
        self.assertIn("Escape", escape_block.group(0))
        self.assertIn("data-open", escape_block.group(0))

    def test_forced_closed_state_cannot_get_stuck(self):
        # data-closed overrides :hover too (same !important rule) — it must
        # be clearable by something other than focus leaving the group, or a
        # mouse-hover attempt right after an Escape would find the menu
        # permanently unresponsive.
        self.assertIn('.nav-group[data-closed="true"] .nav-submenu', self.css)
        self.assertIn("!important", self.css.split('[data-closed="true"] .nav-submenu {')[1].split('}')[0])
        self.assertIn("mouseenter", self.nav)
        self.assertIn("focusout", self.nav)

    def test_tools_menu_flag_cannot_leak_into_an_unrelated_navigation(self):
        # The flag must only be armed when the hash is actually about to
        # change (a same-hash click fires no hashchange, so nothing would
        # ever consume the flag, and a later, unrelated navigation could
        # wrongly find it still set and skip closing the menu).
        click_handler = re.search(r"trigger\.addEventListener\('click'.*?\n    \}\);", self.nav, re.DOTALL)
        self.assertIsNotNone(click_handler)
        self.assertIn("location.hash !== '#/tools'", click_handler.group(0))
        # a modifier/middle click opens a new tab without changing this
        # page's hash at all — must not arm the flag either
        self.assertIn("metaKey", click_handler.group(0))

    # ---------- table captions ------------------------------------------------

    def test_every_data_table_has_a_caption(self):
        for table_id in ("fx-table", "th-table", "fxh-table", "trh-table"):
            match = re.search(r'<table class="data-table" id="' + table_id + r'">(.*?)<thead', self.html, re.DOTALL)
            self.assertIsNotNone(match, f"{table_id} not found")
            self.assertIn("<caption", match.group(1))

    # ---------- reduced motion -------------------------------------------------

    def test_prefers_reduced_motion_disables_the_existing_transitions(self):
        match = re.search(r'@media \(prefers-reduced-motion: reduce\) \{(.*?)\}\s*\}', self.css, re.DOTALL)
        self.assertIsNotNone(match)
        block = match.group(1)
        self.assertIn(".toggle-caret", block)
        self.assertIn(".nav-submenu", block)

    # ---------- escaping --------------------------------------------------------

    def test_escape_html_round_trip(self):
        script = """
global.window = {};
require(%s);
const escapeHtml = window.Statso.core.escapeHtml;
process.stdout.write(JSON.stringify(escapeHtml('<a "x" \\'y\\' & b>')));
""" % json.dumps(str(ROOT / "assets/statso-core.js"))
        out = json.loads(subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True, encoding="utf-8"
        ).stdout)
        self.assertEqual(out, "&lt;a &quot;x&quot; &#39;y&#39; &amp; b&gt;")

    def test_consumers_call_escape_html(self):
        consumers = ["statso-fxtable.js", "statso-fxhistory.js", "statso-calculator.js", "statso-tools.js"]
        for name in consumers:
            text = (ROOT / "assets" / name).read_text(encoding="utf-8")
            self.assertIn("Statso.core.escapeHtml(", text, f"{name} does not call escapeHtml")
        self.assertNotIn("Statso.core.escapeHtml(", (ROOT / "assets/statso-rent.js").read_text(encoding="utf-8"))

    def test_core_loads_before_its_escaping_consumers(self):
        scripts = re.findall(r'<script src="assets/([a-z0-9-]+\.js)"', self.html)
        core_index = scripts.index("statso-core.js")
        for name in ("statso-fxtable.js", "statso-fxhistory.js", "statso-calculator.js", "statso-tools.js"):
            self.assertLess(core_index, scripts.index(name), f"statso-core.js must load before {name}")


if __name__ == "__main__": unittest.main()
