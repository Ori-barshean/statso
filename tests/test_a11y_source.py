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

    # ---------- page titles --------------------------------------------------
    # A hash route never reloads the page, so without this every view of the
    # site kept the same tab title (WCAG 2.4.2, page titled).

    def test_document_title_follows_the_view_and_the_language(self):
        script = """
global.window = {};
let languageListener = null;
const els = {};
const heading = {textContent: '  about  ', hasAttribute() { return false; }, setAttribute() {}, focus() {}};
global.document = {title: 'site-title-he', addEventListener() {},
 getElementById(id) { if (id === 'tools-trigger') { return null; }
  return els[id] || (els[id] = {hidden: false, addEventListener() {}, querySelectorAll() { return []; }}); },
 querySelector() { return {querySelector() { return heading; }}; }, querySelectorAll() { return []; }};
window.location = {hash: '#/'};
window.addEventListener = () => {};
window.scrollTo = () => {};
window.requestAnimationFrame = fn => fn();
window.setTimeout = fn => fn();
window.Statso = {i18n: {t: text => 'shown:' + text, onChange(fn) { languageListener = fn; }}};
require(%s);
const S = window.Statso, seen = {};
S.nav.init();
seen.home = document.title;
window.location.hash = '#/about'; S.nav.route();
seen.about = document.title;
heading.textContent = 'renamed'; languageListener();
seen.afterLanguageChange = document.title;
window.location.hash = '#/'; S.nav.route();
seen.homeAgain = document.title;
process.stdout.write(JSON.stringify(seen));
""" % json.dumps(str(ROOT / "assets/statso-nav.js"))
        seen = json.loads(subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True, encoding="utf-8"
        ).stdout)
        self.assertEqual(seen["home"], "shown:site-title-he")
        self.assertEqual(seen["about"], "about \u2014 statso")
        self.assertEqual(seen["afterLanguageChange"], "renamed \u2014 statso")
        self.assertEqual(seen["homeAgain"], "shown:site-title-he")

    # ---------- spoken results and counters ------------------------------------
    # The calculators recompute silently as the visitor types, and the contact
    # form's character counter used to be a live region, which a screen reader
    # reads out on every single keystroke.

    def test_results_are_spoken_once_after_a_pause_and_never_with_the_disclaimer(self):
        script = """
global.window = {};
const timers = []; let listeners = {};
window.setTimeout = (fn, ms) => { timers.push({fn, ms, live: true}); return timers.length; };
window.clearTimeout = id => { if (timers[id - 1]) { timers[id - 1].live = false; } };
window.addEventListener = () => {};
window.scrollTo = () => {};
window.requestAnimationFrame = fn => fn();
window.location = {hash: '#/'};
const live = {textContent: ''};
const block = (hidden, parts) => ({hidden, querySelectorAll: () => parts.map(text => ({textContent: ' ' + text + ' '}))});
const blocks = [block(false, ['indexed', '1,234', 'NIS', 'difference', '234', 'NIS']), block(true, ['hidden', '9'])];
const scope = {querySelectorAll: () => blocks};
const field = {closest: selector => selector.includes('.calc-layout') ? scope : null};
const elsewhere = {closest: () => null};
global.document = {title: 't', addEventListener(type, fn) { listeners[type] = fn; },
 getElementById(id) { if (id === 'result-live') { return live; } if (id === 'tools-trigger') { return null; }
  return {hidden: false, addEventListener() {}, querySelectorAll() { return []; }}; },
 querySelector() { return null; }, querySelectorAll() { return []; }};
require(%s);
window.Statso.nav.init();
const seen = {};
const runLive = () => timers.filter(t => t.live).forEach(t => { t.live = false; t.fn(); });
listeners.input({target: elsewhere}); runLive(); seen.unrelated = live.textContent;
listeners.input({target: field}); listeners.input({target: field}); listeners.change({target: field});
seen.beforePause = live.textContent;
seen.scheduled = timers.filter(t => t.live).length;
runLive(); seen.afterPause = live.textContent;
timers.length = 0;
listeners.change({target: field}); runLive(); seen.repeatedChangeKeepsSameText = live.textContent;
process.stdout.write(JSON.stringify(seen));
""" % json.dumps(str(ROOT / "assets/statso-nav.js"))
        seen = json.loads(subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True, encoding="utf-8"
        ).stdout)
        self.assertEqual(seen["unrelated"], "")
        self.assertEqual(seen["beforePause"], "")
        self.assertEqual(seen["scheduled"], 1)  # three rapid events collapse into one announcement
        self.assertEqual(seen["afterPause"], "indexed 1,234 NIS difference 234 NIS")
        self.assertEqual(seen["repeatedChangeKeepsSameText"], "indexed 1,234 NIS difference 234 NIS")

    def test_copy_feedback_keeps_keyboard_focus_and_is_spoken(self):
        # flash() used to disable the button it was called from; disabling the
        # element that holds keyboard focus drops focus to <body>.
        script = """
global.window = {};
const timers = [];
window.setTimeout = fn => { timers.push(fn); return timers.length; };
window.clearTimeout = () => {};
const live = {textContent: ''};
global.document = {getElementById: id => id === 'result-live' ? live : null};
require(%s);
const attributes = {};
const button = {textContent: 'copy to excel', disabled: false,
 hasAttribute: name => name in attributes, setAttribute: (name, value) => { attributes[name] = value; },
 removeAttribute: name => { delete attributes[name]; }};
const seen = {};
const flash = window.Statso.exporter.flash;
flash(button, 'copied \u2713');
seen.label = button.textContent; seen.disabled = button.disabled; seen.spoken = live.textContent;
flash(button, 'again');                      // ignored while the first is showing
seen.secondPressIgnored = button.textContent === 'copied \u2713' && timers.length === 2;
timers.forEach(fn => fn());
seen.restored = button.textContent; seen.flashingCleared = !('data-flashing' in attributes); seen.cleared = live.textContent;
process.stdout.write(JSON.stringify(seen));
""" % json.dumps(str(ROOT / "assets/statso-export.js"))
        seen = json.loads(subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True, encoding="utf-8"
        ).stdout)
        self.assertEqual(seen["label"], "copied \u2713")
        self.assertFalse(seen["disabled"])
        self.assertEqual(seen["spoken"], "copied")
        self.assertTrue(seen["secondPressIgnored"])
        self.assertEqual(seen["restored"], "copy to excel")
        self.assertTrue(seen["flashingCleared"])
        self.assertEqual(seen["cleared"], "")

    def test_rent_periods_name_themselves_and_keep_keyboard_focus(self):
        rent = (ROOT / "assets/statso-rent.js").read_text(encoding="utf-8")
        language = (ROOT / "assets/statso-lang-en.js").read_text(encoding="utf-8")
        # each period is a named group, and its remove button is named from its
        # own visible text plus the period title (WCAG 2.5.3 label in name)
        self.assertIn('role="group" aria-labelledby="', rent)
        self.assertIn('class="rent-option-title sr-only"', rent)  # hidden: a visible title broke the row's grid
        self.assertIn("aria-labelledby=\"' + removeId + ' ' + titleId", rent)
        self.assertNotIn('aria-label="הסרת תקופה"', rent)
        self.assertIn("'תקופה':", language)
        # focus is never left on a node that no longer exists
        self.assertIn("el('tr-add-option').focus()", rent)
        self.assertIn("addOptionRow({}).querySelector('input').focus()", rent)
        self.assertIn("renumberOptionRows();", rent)

    def test_result_live_region_sits_outside_every_main_view(self):
        match = re.search(r'<div class="sr-only" id="result-live" role="status" aria-live="polite" aria-atomic="true"></div>', self.html)
        self.assertIsNotNone(match)
        self.assertGreater(match.start(), self.html.rindex("</main>"))
        self.assertIn("initResultAnnouncements();", self.nav)

    def test_message_counter_is_not_a_live_region_but_the_limit_is_spoken(self):
        counter = re.search(r'<span id="contact-message-count"[^>]*>', self.html).group(0)
        self.assertNotIn("aria-live", counter)
        self.assertNotIn("role=", counter)
        self.assertRegex(self.html, r'id="contact-message-limit" role="status" aria-live="polite"')
        contact = (ROOT / "assets/statso-contact.js").read_text(encoding="utf-8")
        language = (ROOT / "assets/statso-lang-en.js").read_text(encoding="utf-8")
        for message in re.findall(r"const LIMIT_(?:NEAR|REACHED) = '([^']+)'", contact):
            self.assertIn("'" + message + "':", language)
        self.assertEqual(len(re.findall(r"const LIMIT_(?:NEAR|REACHED) =", contact)), 2)

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

    # ---------- keyboard-scrollable regions -------------------------------------
    # axe-core flagged every horizontally-scrolling container (wide tables, guide
    # screenshots, sample-code blocks) as unreachable by keyboard: a div/pre that
    # scrolls but carries no tabindex is simply skipped by Tab, so a keyboard user
    # can never reach its hidden content at all.

    def test_every_table_wrap_is_a_focusable_labeled_region(self):
        wraps = re.findall(r'<div class="table-wrap"[^>]*>', self.html)
        self.assertEqual(len(wraps), 4)  # dashboard fx-table + 3 tool history tables
        for wrap in wraps:
            self.assertIn('tabindex="0"', wrap)
            self.assertIn('role="region"', wrap)
            self.assertIn('aria-label="', wrap)

    def test_guide_illustrations_and_code_blocks_are_focusable_regions(self):
        for name in ("codeBlock", "oneArtSlot"):
            self.assertIn(f"function {name}", self.guides)
        # No role="region" here on purpose: these repeat once per guide step
        # with the same generic label ("Excel in Hebrew", "Sample code"), and a
        # landmark role demands a *unique* accessible name per instance — axe's
        # landmark-unique caught exactly this when role="region" was first
        # tried. Plain tabindex + aria-label is enough to satisfy
        # scrollable-region-focusable without claiming landmark status.
        self.assertEqual(self.guides.count('tabindex="0" aria-label="'), 3)
        self.assertNotIn('tabindex="0" role="region"', self.guides)
        # the standalone Power Query export-code tab has its own static <pre>
        static_pre = re.search(r'<div class="code-block mcode-output"><pre dir="ltr"[^>]*>', self.html)
        self.assertIsNotNone(static_pre)
        self.assertIn('tabindex="0" aria-label="', static_pre.group(0))
        self.assertNotIn('role="region"', static_pre.group(0))

    # ---------- form fields, focus ring, target size ---------------------------
    # 1.4.11: the border is the only thing that marks a text field out from the
    # page, so it must clear 3:1 (the old #cbd5e1 sat near 1.5:1). 2.4.7 and
    # 2.5.8 are covered by one shared focus ring and a 24px minimum target.

    @staticmethod
    def _contrast(hex1, hex2):
        def luminance(hex_color):
            channels = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
            linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
            return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]
        l1, l2 = luminance(hex1), luminance(hex2)
        return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)

    def test_form_field_border_clears_non_text_contrast(self):
        border = re.search(r'--field-border:\s*(#[0-9a-fA-F]{6});', self.css).group(1)
        for background in ('#ffffff', '#f5f8fc'):
            self.assertGreaterEqual(self._contrast(border, background), 3.0, f"{border} on {background}")
        rule = re.search(r'\ninput, select, textarea \{([^}]*)\}', self.css).group(1)
        self.assertIn('var(--field-border)', rule)
        self.assertNotIn('outline', rule)

    def test_one_focus_visible_ring_covers_every_operable_control(self):
        match = re.search(r':is\(([^)]*\)?[^)]*)\):focus-visible \{([^}]*)\}', self.css)
        self.assertIsNotNone(match)
        selector, body = match.groups()
        for tag in ("a", "button", "input", "select", "textarea", "summary"):
            self.assertRegex(selector, r'(^|, )' + tag + r'(,|$)')
        self.assertIn('[tabindex]:not([tabindex="-1"])', selector)
        self.assertRegex(body, r'outline:\s*3px solid')
        self.assertGreaterEqual(self._contrast('#1d4ed8', '#ffffff'), 3.0)
        self.assertGreaterEqual(self._contrast('#1d4ed8', '#f5f8fc'), 3.0)

    def test_standalone_links_meet_the_minimum_target_size(self):
        for selector in (r'\.footer-links a', r'\.tool-back'):
            rule = re.search(selector + r' \{([^}]*)\}', self.css).group(1)
            self.assertIn('min-height: 24px', rule)

    def test_language_picker_names_each_language_in_that_language(self):
        self.assertRegex(self.html, r'<button[^>]*id="lang-toggle"[^>]* lang="en"')
        self.assertRegex(self.html, r'data-lang-choice="he" lang="he">עברית<')
        self.assertRegex(self.html, r'data-lang-choice="en" lang="en">English<')

    # ---------- reduced motion -------------------------------------------------

    def test_prefers_reduced_motion_disables_the_existing_transitions(self):
        match = re.search(r'@media \(prefers-reduced-motion: reduce\) \{(.*?)\}\s*\}', self.css, re.DOTALL)
        self.assertIsNotNone(match)
        block = match.group(1)
        self.assertIn(".toggle-caret", block)
        self.assertIn(".nav-submenu", block)

    def test_chart_skips_its_draw_in_animation_under_reduced_motion(self):
        chart = (ROOT / "assets/statso-chart.js").read_text(encoding="utf-8")
        self.assertIn("(prefers-reduced-motion: reduce)", chart)
        self.assertIn("config.options.animation = false", chart)

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

    # ---------- color contrast ---------------------------------------------------
    # axe-core found that --muted text, when the layout direction flips to ltr
    # (switching to English, or forcing dir="ltr"), drops to a 4.46:1 contrast
    # ratio against the page's --wash background — just under the 4.5:1 AA
    # minimum for normal text. #5f6b80 clears 4.5:1 against both --wash (#f5f8fc)
    # and white with real margin, in either direction, so the fix doesn't depend
    # on understanding exactly why the ratio moves with direction.

    def test_muted_text_color_clears_aa_contrast_with_margin(self):
        match = re.search(r'--muted:\s*(#[0-9a-fA-F]{6});', self.css)
        self.assertIsNotNone(match)
        muted = match.group(1)
        self.assertNotEqual(muted.lower(), '#64748b')

        def luminance(hex_color):
            channels = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
            linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
            return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

        def ratio(hex1, hex2):
            l1, l2 = luminance(hex1), luminance(hex2)
            lighter, darker = max(l1, l2), min(l1, l2)
            return (lighter + 0.05) / (darker + 0.05)

        for background in ('#f5f8fc', '#ffffff'):
            self.assertGreaterEqual(ratio(muted, background), 4.5,
                                     f"{muted} on {background} must clear WCAG AA (4.5:1) for normal text")

    def test_kpi_footnote_sub_no_longer_dims_with_opacity(self):
        match = re.search(r'\.kpi-footnote-sub \{([^}]*)\}', self.css)
        self.assertIsNotNone(match)
        self.assertNotIn('opacity', match.group(1))
        match = re.search(r'\.kpi-meta \+ \.kpi-meta \{([^}]*)\}', self.css)
        self.assertIsNotNone(match)
        self.assertNotIn('opacity', match.group(1))


if __name__ == "__main__": unittest.main()
