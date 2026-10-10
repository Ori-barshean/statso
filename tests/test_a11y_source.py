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

    def test_chart_events_are_named_in_text_for_the_current_range(self):
        # The five event markers are drawn on the canvas only; a screen reader
        # needs them in the chart's description, limited to what is on screen.
        script = """
global.window = {};
const holder = {children: [{text: 'old'}], hidden: true, appendChild(node) { this.children.push(node); }, setAttribute() {},
 set textContent(value) { this.children = []; }};
global.document = {getElementById: id => id === 'chart-alt-events' ? holder : null,
 createTextNode: text => ({text}), createElement: () => ({attrs: {}, setAttribute(k, v) { this.attrs[k] = v; }, textContent: ''})};
window.Statso = {i18n: {onChange() {}, t: text => text}};
require(%s);
require(%s);
const S = window.Statso, seen = {};
const flat = () => holder.children.map(node => node.text !== undefined ? node.text : node.textContent).join('');
S.chart.describeEvents([{month: '2008-09'}, {month: '2010-01'}, {month: '2020-03'}]);
seen.some = flat(); seen.someHidden = holder.hidden;
S.chart.describeEvents([{month: '2012-01'}]);
seen.none = flat(); seen.noneHidden = holder.hidden;
S.chart.describeEvents(S.chart.EVENTS.map(event => ({month: event.month})));
seen.all = flat();
process.stdout.write(JSON.stringify(seen));
""" % (json.dumps(str(ROOT / "assets/statso-core.js")), json.dumps(str(ROOT / "assets/statso-chart.js")))
        seen = json.loads(subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True, encoding="utf-8"
        ).stdout)
        self.assertEqual(seen["some"], "אירועים המסומנים בתרשים: 09/2008 \u2014 משבר הסאב־פריים; 03/2020 \u2014 קורונה.")
        self.assertFalse(seen["someHidden"])
        self.assertEqual(seen["none"], "")
        self.assertTrue(seen["noneHidden"])
        self.assertEqual(seen["all"].count("\u2014"), 5)
        self.assertRegex(self.html, r'role="img" aria-describedby="chart-alt-text chart-alt-events chart-keys-help"')
        canvas = re.search(r'<canvas id="cpi-chart"[^>]*>', self.html).group(0)
        self.assertIn('tabindex="0"', canvas)
        self.assertRegex(self.html, r'<p class="sr-only" id="chart-alt-events" hidden></p>')
        language = (ROOT / "assets/statso-lang-en.js").read_text(encoding="utf-8")
        self.assertIn("'אירועים המסומנים בתרשים:':", language)

    def test_guide_copy_buttons_cannot_get_stuck_on_their_confirmation(self):
        copy = self.guides[self.guides.index("function copy(button)"):]
        copy = copy[:copy.index("\n  }\n")]
        self.assertIn("button.hasAttribute('data-flashing')", copy)
        self.assertIn("button.removeAttribute('data-flashing')", copy)

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

    def test_focused_controls_clear_the_sticky_header(self):
        rule = re.search(r'\nhtml \{([^}]*)\}', self.css).group(1)
        self.assertIn('scroll-padding-top: calc(var(--header-height, 72px) + 12px)', rule)
        script = """
global.window = {};
let height = 68.4, observerCallback, observed;
const props = {}, listeners = {}, els = {};
const header = {nodeType: 1, getBoundingClientRect: () => ({height})};
const heading = {textContent: 'about', hasAttribute() { return false; }, setAttribute() {}, focus() {}};
const docListeners = {};
global.document = {title: 'site', addEventListener(type, fn, capture) { docListeners[type] = {fn, capture}; },
 documentElement: {style: {setProperty(k, v) { props[k] = v; }}},
 getElementById(id) { if (id === 'tools-trigger') { return null; }
  return els[id] || (els[id] = {hidden: false, addEventListener() {}, querySelectorAll() { return []; }}); },
 querySelector(selector) { return selector === '.site-header' ? header : {querySelector: () => heading}; },
 querySelectorAll() { return []; }};
window.location = {hash: '#/'};
window.addEventListener = (type, fn) => { listeners[type] = fn; };
window.scrollTo = () => {};
window.requestAnimationFrame = fn => fn();
window.setTimeout = fn => fn();
window.Statso = {i18n: {t: s => s, onChange() {}}};
window.ResizeObserver = class { constructor(fn) { observerCallback = fn; } observe(el) { observed = el; } };
require(%s);
window.Statso.nav.init();
const seen = {initial: props['--header-height'], observedHeader: observed === header};
height = 131.2; observerCallback(); seen.resized = props['--header-height'];
height = 90.1; docListeners.keydown.fn({key: 'a'}); seen.otherKeyIgnored = props['--header-height'];
docListeners.keydown.fn({key: 'Tab'}); seen.measuredBeforeTab = props['--header-height'];
seen.tabCapture = docListeners.keydown.capture === true; seen.resizeAlways = typeof listeners.resize === 'function';
delete window.ResizeObserver; height = 68.4;
window.Statso.nav.init(); seen.fallbackInitial = props['--header-height'];
seen.resizeListener = typeof listeners.resize === 'function';
height = 131.2; listeners.resize(); seen.fallbackResized = props['--header-height'];
process.stdout.write(JSON.stringify(seen));
""" % json.dumps(str(ROOT / "assets/statso-nav.js"))
        seen = json.loads(subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True, encoding="utf-8"
        ).stdout)
        self.assertEqual(seen, {"initial": "69px", "observedHeader": True, "resized": "132px",
                                "otherKeyIgnored": "132px", "measuredBeforeTab": "91px", "tabCapture": True,
                                "resizeAlways": True,
                                "fallbackInitial": "69px", "resizeListener": True, "fallbackResized": "132px"})

    def test_disclosure_buttons_do_not_claim_a_popup(self):
        self.assertNotIn('aria-haspopup', self.html)
        for id_, controls in [('tools-trigger', 'tools-submenu'), ('lang-toggle', 'lang-menu')]:
            tag = re.search(r'<[^>]+id="' + id_ + r'"[^>]*>', self.html).group(0)
            self.assertIn('aria-expanded="false"', tag)
            self.assertIn('aria-controls="' + controls + '"', tag)

    def test_language_menu_hands_focus_back_to_its_toggle(self):
        script = """
global.window = {location: {search: '', href: 'https://x.test/'},
 history: {replaceState() {}}, localStorage: {getItem() { return null; }, setItem() {}}};
const listeners = {};
function element(attrs = {}) { return {attrs, handlers: {},
 addEventListener(type, fn) { this.handlers[type] = fn; },
 getAttribute(k) { return this.attrs[k]; }, setAttribute(k, v) { this.attrs[k] = v; },
 removeAttribute(k) { delete this.attrs[k]; }, focus() { document.activeElement = this; }}; }
const button = element(), menu = element(), outside = element();
const choices = ['he', 'en'].map(lang => element({'data-lang-choice': lang}));
menu.hidden = true; menu.querySelectorAll = () => choices;
const picker = {contains: el => [button, menu, ...choices].includes(el)};
const els = {'lang-toggle': button, 'lang-menu': menu, 'lang-picker': picker};
global.document = {activeElement: outside, getElementById: id => els[id],
 addEventListener(type, fn) { listeners[type] = fn; },
 querySelectorAll: () => choices, querySelector: () => null,
 documentElement: {setAttribute() {}},
 body: {nodeType: 1, tagName: 'BODY', hasAttribute: () => false, firstChild: null, querySelectorAll: () => []}};
require(%s);
const S = window.Statso; S.i18n.init();
const open = () => button.handlers.click({stopPropagation() {}});
const seen = {};
open(); choices[0].focus(); listeners.keydown({key: 'Escape'});
seen.inside = menu.hidden && document.activeElement === button && button.attrs['aria-expanded'] === 'false';
open(); outside.focus(); listeners.keydown({key: 'Escape'});
seen.outside = menu.hidden && document.activeElement === outside;
open(); choices[1].focus(); choices[1].handlers.click();
seen.choice = menu.hidden && document.activeElement === button;
seen.language = S.i18n.current();
process.stdout.write(JSON.stringify(seen));
""" % json.dumps(str(ROOT / "assets/statso-i18n.js"))
        seen = json.loads(subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True, encoding="utf-8"
        ).stdout)
        self.assertEqual(seen, {"inside": True, "outside": True, "choice": True, "language": "en"})

    def test_contact_submit_keeps_focus_while_sending_and_focuses_the_confirmation(self):
        script = """
(async function () {
const path = %s;
async function run(fail) {
 global.window = {location: {protocol: 'https:'}};
 let init, resolveFetch, rejectFetch, fetchCalls = 0, everDisabled = false;
 function element() { return {attrs: {}, handlers: {}, value: 'valid', validity: {typeMismatch: false},
  textContent: '', children: [],
  set disabled(value) { if (value) { everDisabled = true; } }, get disabled() { return false; },
  setAttribute(k, v) { this.attrs[k] = v; }, getAttribute(k) { return this.attrs[k]; },
  removeAttribute(k) { delete this.attrs[k]; }, addEventListener(type, fn) { this.handlers[type] = fn; },
  appendChild(el) { this.children.push(el); }, focus() { document.activeElement = this; }}; }
 const els = {};
 global.document = {activeElement: null, addEventListener(type, fn) { init = fn; },
  getElementById: id => els[id] || (els[id] = element()), createElement(tag) {
   if (tag !== 'p') { throw new Error('unexpected tag'); } return element(); }};
 global.FormData = class { set() {} };
 global.fetch = () => { fetchCalls++; return new Promise((resolve, reject) => { resolveFetch = resolve; rejectFetch = reject; }); };
 delete require.cache[require.resolve(path)]; require(path); init();
 const form = els['contact-form'], button = document.getElementById('contact-submit');
 button.focus();
 const event = {preventDefault() {}, currentTarget: form};
 form.handlers.submit(event);
 const result = {pending: button.attrs['aria-disabled'], label: button.textContent,
  focusedWhileSending: document.activeElement === button};
 form.handlers.submit(event); result.fetchCalls = fetchCalls;
 if (fail) { rejectFetch(new Error('network')); }
 else { resolveFetch({ok: true, json: () => ({success: true})}); }
 await new Promise(resolve => setImmediate(resolve));
 result.everDisabled = everDisabled;
 if (fail) {
  result.failure = els['contact-status'].textContent;
  result.disabledRemoved = !('aria-disabled' in button.attrs); result.restored = button.textContent;
 } else {
  const success = els['contact-form-area'].children[0];
  result.success = {className: success.className, role: success.attrs.role, tabindex: success.attrs.tabindex,
   focused: document.activeElement === success, text: success.textContent};
 }
 return result;
}
process.stdout.write(JSON.stringify({success: await run(false), failure: await run(true)}));
})().catch(error => { console.error(error); process.exit(1); });
""" % json.dumps(str(ROOT / "assets/statso-contact.js"))
        seen = json.loads(subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True, encoding="utf-8"
        ).stdout)
        for run in seen.values():
            self.assertEqual(run['pending'], 'true')
            self.assertEqual(run['label'], 'שולח…')
            self.assertTrue(run['focusedWhileSending'])
            self.assertFalse(run['everDisabled'])
            self.assertEqual(run['fetchCalls'], 1)
        self.assertEqual(seen['success']['success'], {
            'className': 'contact-success', 'role': 'status', 'tabindex': '-1', 'focused': True,
            'text': 'ההודעה נשלחה ותענה בהקדם האפשרי לתיבת המייל שציינת לחזרה.'})
        self.assertEqual(seen['failure']['failure'], 'לא ניתן היה לשלוח את ההודעה כרגע. התוכן נשמר בטופס ואפשר לנסות שוב.')
        self.assertTrue(seen['failure']['disabledRemoved'])
        self.assertEqual(seen['failure']['restored'], 'שלח')
        self.assertIn('.contact-submit[aria-disabled="true"]', self.css)
        self.assertNotIn('button.disabled', (ROOT / 'assets/statso-contact.js').read_text(encoding='utf-8'))

    def test_current_page_is_marked_without_color_in_forced_colors(self):
        block = re.search(r'@media \(forced-colors: active\) \{(.*?)\}\s*\}', self.css, re.DOTALL).group(1)
        self.assertIn('.nav-item[aria-current="page"]', block)
        self.assertIn('border-block-end: 3px solid CanvasText', block)

    def test_month_inputs_show_their_format(self):
        rent = (ROOT / 'assets/statso-rent.js').read_text(encoding='utf-8')
        for source, count in [(self.html, 4), (rent, 2)]:
            tags = re.findall(r'<input[^>]*type="month"[^>]*>', source)
            self.assertEqual(len(tags), count)
            for tag in tags:
                self.assertIn('placeholder="YYYY-MM"', tag)

    def test_chart_keyboard_helpers_are_pure(self):
        script = """
global.window = {Statso: {i18n: {onChange() {}, t: s => ({'קורונה': 'Covid'})[s] || s}}};
global.document = {getElementById: () => null};
require(%s); require(%s);
const {nextIndex, announcementText} = window.Statso.chart;
// Calling the helpers must never need a document or schedule a timer.
global.document = new Proxy({}, {get() { throw new Error('DOM access'); }});
window.setTimeout = () => { throw new Error('timer'); };
const cases = [[null, 'ArrowRight', 10], [null, 'ArrowLeft', 10], [null, 'Home', 10],
 [null, 'PageUp', 10], [5, 'ArrowRight', 10], [9, 'ArrowRight', 10], [0, 'ArrowLeft', 10],
 [20, 'PageUp', 30], [5, 'PageUp', 30], [20, 'PageDown', 30], [2, 'PageDown', 30],
 [5, 'End', 10], [5, 'Escape', 10], [null, 'ArrowRight', 0]];
const rows = [{month: '2020-03'}];
const cpi = {label: 'CPI', data: [101.3], visible: true};
const build = {label: 'Build', data: [2000], visible: true};
const text = series => announcementText(rows, series, 0);
process.stdout.write(JSON.stringify({indices: cases.map(c => nextIndex(...c)),
 unhandled: ['ArrowUp', 'a', 'toString'].map(key => nextIndex(5, key, 10) === undefined),
 both: text([cpi, build]), nullValue: text([cpi, {...build, data: [null]}]),
 hidden: text([cpi, {...build, visible: false}]),
 noParts: text([{...cpi, visible: false}, {...build, data: [Infinity]}]),
 undefinedValue: text([{...build, data: []}]), nanValue: text([{...build, data: [NaN]}]),
 missing: announcementText(rows, [cpi, build], 10)}));
""" % (json.dumps(str(ROOT / 'assets/statso-core.js')), json.dumps(str(ROOT / 'assets/statso-chart.js')))
        seen = json.loads(subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True, encoding="utf-8"
        ).stdout)
        self.assertEqual(seen['indices'], [9, 9, 0, 9, 6, 9, 0, 8, 0, 29, 14, 9, None, None])
        self.assertEqual(seen['unhandled'], [True, True, True])
        self.assertEqual(seen['both'], '03/2020: CPI 101.3; Build 2,000.0 — Covid')
        for key in ('nullValue', 'hidden'):
            self.assertEqual(seen[key], '03/2020: CPI 101.3 — Covid')
        for key in ('noParts', 'undefinedValue', 'nanValue'):
            self.assertEqual(seen[key], '03/2020 — Covid')
        self.assertEqual(seen['missing'], '')

    def test_chart_keys_tooltip_announcement_and_series_toggle(self):
        script = """
let languageListener;
global.window = {Statso: {i18n: {onChange(fn) { languageListener = fn; },
 t: s => ({'מדד המחירים לצרכן': 'CPI', 'מדד תשומות הבנייה למגורים': 'Build', 'קורונה': 'Covid'})[s] || s}}};
const timers = [];
window.setTimeout = (fn, ms) => { timers.push({fn, ms, live: true}); return timers.length; };
window.clearTimeout = id => { if (timers[id - 1]) { timers[id - 1].live = false; } };
const flush = () => timers.filter(t => t.live).forEach(t => { t.live = false; t.fn(); });
function element() { return {textContent: '', value: '', checked: true, label: {hidden: false}, handlers: {},
 addEventListener(type, fn) { this.handlers[type] = fn; }, closest() { return this.label; }, getContext() { return {}; }}; }
const els = {};
['cpi-chart', 'chart-start-year', 'chart-end-year', 'chart-range-error', 'chart-live',
 'chart-series-cpi', 'chart-series-construction'].forEach(id => { els[id] = element(); });
global.document = {getElementById: id => els[id] || null};
const charts = [];
window.Chart = class {
 constructor(ctx, config) {
  this.data = config.data; this.options = config.options;
  this.meta = this.data.datasets.map(d => ({hidden: null, data: d.data.map((v, i) => ({x: i, y: v}))}));
  this.active = []; this.updates = [];
  this.tooltip = {active: [], setActiveElements(active, position) { this.active = active; this.position = position; }};
  charts.push(this);
 }
 isDatasetVisible(i) { return !(this.meta[i].hidden === null ? this.data.datasets[i].hidden : this.meta[i].hidden); }
 setDatasetVisibility(i, visible) { this.meta[i].hidden = !visible; }
 getDatasetMeta(i) { return this.meta[i]; }
 setActiveElements(active) { this.active = active; }
 update(mode) { this.updates.push(mode); }
 destroy() { this.destroyed = true; }
};
require(%s); require(%s);
const S = window.Statso;
const rows = Array.from({length: 24}, (_, i) => ({year: 2019 + Math.floor(i / 12),
 month: String(2019 + Math.floor(i / 12)) + '-' + String(i %% 12 + 1).padStart(2, '0'), chained_1951_09: 100 + i}));
const construction = rows.slice(12).map((row, i) => ({...row, chained_1950_07: 2000 + i}));
S.chart.init(rows, construction);
const seen = {lazy: charts.length === 0};
S.chart.activate();
let chart = charts[0];
function key(name, modifiers = {}) {
 let prevented = false;
 els['cpi-chart'].handlers.keydown({key: name, ...modifiers, preventDefault() { prevented = true; }});
 return prevented;
}
seen.rightPrevented = key('ArrowRight'); seen.latest = chart.tooltip.active;
seen.anchor = chart.tooltip.position;
seen.activeMatches = JSON.stringify(chart.active) === JSON.stringify(chart.tooltip.active);
seen.delay = timers.filter(t => t.live).map(t => t.ms);
seen.beforePause = els['chart-live'].textContent;
flush(); seen.latestSpoken = els['chart-live'].textContent;
key('Home'); seen.earliest = chart.tooltip.active;
key('ArrowRight'); key('ArrowRight'); seen.pendingTimers = timers.filter(t => t.live).length;
flush(); seen.rapidSpoken = els['chart-live'].textContent;
seen.upPrevented = key('ArrowUp');
seen.modifiers = ['metaKey', 'altKey', 'ctrlKey', 'shiftKey'].map(modifier => key('ArrowLeft', {[modifier]: true}));
seen.escapePrevented = key('Escape'); seen.cleared = chart.tooltip.active;
seen.clearSpoken = els['chart-live'].textContent;
seen.emptyEscapePrevented = key('Escape');
key('End'); flush();
const input = els['chart-series-construction'];
input.checked = false; input.handlers.change();
seen.hidden = !chart.isDatasetVisible(1); seen.hiddenActive = chart.tooltip.active;
chart.options.plugins.legend.onClick({}, {datasetIndex: 1});
seen.legendRestored = chart.isDatasetVisible(1) && input.checked;
seen.legendActive = chart.tooltip.active;
input.checked = false; input.handlers.change();
const cpi = els['chart-series-cpi']; cpi.checked = false; cpi.handlers.change();
seen.allHiddenActive = chart.tooltip.active; seen.allHiddenAnchor = chart.tooltip.position;
cpi.checked = true; cpi.handlers.change();
key('ArrowLeft');
S.chart.onRangeChange(); chart = charts[charts.length - 1];
flush(); seen.range = {newChart: charts.length === 2 && charts[0].destroyed,
 hidden: chart.data.datasets[1].hidden, active: chart.tooltip.active, spoken: els['chart-live'].textContent};
languageListener(); chart = charts[charts.length - 1];
seen.languageKeepsHidden = chart.data.datasets[1].hidden && !input.checked;
els['chart-start-year'].value = '2019'; els['chart-end-year'].value = '2019'; S.chart.onRangeChange();
seen.onlyCpi = !cpi.label.hidden && input.label.hidden;
els['chart-end-year'].value = '2020'; S.chart.onRangeChange();
seen.bothControls = !cpi.label.hidden && !input.label.hidden && !input.checked;
process.stdout.write(JSON.stringify(seen));
""" % (json.dumps(str(ROOT / 'assets/statso-core.js')), json.dumps(str(ROOT / 'assets/statso-chart.js')))
        seen = json.loads(subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True, encoding="utf-8"
        ).stdout)
        both = [{'datasetIndex': 0, 'index': 23}, {'datasetIndex': 1, 'index': 23}]
        self.assertTrue(seen['lazy'])
        self.assertTrue(seen['rightPrevented'])
        self.assertEqual(seen['latest'], both)
        self.assertEqual(seen['anchor'], {'x': 23, 'y': 123})
        self.assertTrue(seen['activeMatches'])
        self.assertEqual(seen['delay'], [250])
        self.assertEqual(seen['beforePause'], '')
        self.assertEqual(seen['latestSpoken'], '12/2020: CPI 123.0; Build 2,011.0')
        self.assertEqual(seen['earliest'], [{'datasetIndex': 0, 'index': 0}])
        self.assertEqual(seen['pendingTimers'], 1)
        self.assertEqual(seen['rapidSpoken'], '03/2019: CPI 102.0')
        self.assertFalse(seen['upPrevented'])
        self.assertEqual(seen['modifiers'], [False] * 4)
        self.assertTrue(seen['escapePrevented'])
        self.assertEqual(seen['cleared'], [])
        self.assertEqual(seen['clearSpoken'], '')
        self.assertFalse(seen['emptyEscapePrevented'])
        self.assertTrue(seen['hidden'])
        self.assertEqual(seen['hiddenActive'], [{'datasetIndex': 0, 'index': 23}])
        self.assertTrue(seen['legendRestored'])
        self.assertEqual(seen['legendActive'], both)
        self.assertEqual(seen['allHiddenActive'], [])
        self.assertEqual(seen['allHiddenAnchor'], {'x': 0, 'y': 0})
        self.assertEqual(seen['range'], {'newChart': True, 'hidden': True, 'active': [], 'spoken': ''})
        self.assertTrue(seen['languageKeepsHidden'])
        self.assertTrue(seen['onlyCpi'])
        self.assertTrue(seen['bothControls'])

    def test_chart_announcements_stay_honest_when_the_series_or_language_change(self):
        # Found in review: a queued announcement survived hiding a series, the series names came from
        # the last built chart (stale after a language switch with an invalid range), and a boundary
        # key could not bring back a tooltip that the mouse leaving the canvas had removed.
        script = """
let language = 'he';
const labels = {he: {a: 'CPI-he', b: 'Build-he'}, en: {a: 'CPI-en', b: 'Build-en'}};
global.window = {Statso: {i18n: {onChange() {},
 t: s => ({'מדד המחירים לצרכן': labels[language].a, 'מדד תשומות הבנייה למגורים': labels[language].b})[s] || s}}};
const timers = [];
window.setTimeout = (fn, ms) => { timers.push({fn, ms, live: true}); return timers.length; };
window.clearTimeout = id => { if (timers[id - 1]) { timers[id - 1].live = false; } };
const flush = () => timers.filter(t => t.live).forEach(t => { t.live = false; t.fn(); });
function element() { return {textContent: '', value: '', checked: true, label: {hidden: false}, handlers: {},
 addEventListener(type, fn) { this.handlers[type] = fn; }, closest() { return this.label; }, getContext() { return {}; }}; }
const els = {};
['cpi-chart', 'chart-start-year', 'chart-end-year', 'chart-range-error', 'chart-live',
 'chart-series-cpi', 'chart-series-construction'].forEach(id => { els[id] = element(); });
global.document = {getElementById: id => els[id] || null};
const charts = [];
window.Chart = class {
 constructor(ctx, config) {
  this.data = config.data; this.options = config.options;
  this.meta = this.data.datasets.map(d => ({hidden: null, data: d.data.map((v, i) => ({x: i, y: v}))}));
  this.active = []; this.tooltip = {active: [], setActiveElements(active, position) { this.active = active; this.position = position; }};
  charts.push(this);
 }
 isDatasetVisible(i) { return !(this.meta[i].hidden === null ? this.data.datasets[i].hidden : this.meta[i].hidden); }
 setDatasetVisibility(i, visible) { this.meta[i].hidden = !visible; }
 getDatasetMeta(i) { return this.meta[i]; }
 setActiveElements(active) { this.active = active; }
 update() {}
 destroy() {}
};
require(%s); require(%s);
const S = window.Statso;
const rows = Array.from({length: 24}, (_, i) => ({year: 2019 + Math.floor(i / 12),
 month: String(2019 + Math.floor(i / 12)) + '-' + String(i %% 12 + 1).padStart(2, '0'), chained_1951_09: 100 + i}));
const construction = rows.slice(12).map((row, i) => ({...row, chained_1950_07: 2000 + i}));
S.chart.init(rows, construction); S.chart.activate();
const chart = charts[0], live = els['chart-live'], seen = {};
function key(name) { let prevented = false; els['cpi-chart'].handlers.keydown({key: name, preventDefault() { prevented = true; }}); return prevented; }
// 1) hiding a series cancels the announcement that is still queued for it
key('End');
const construct = els['chart-series-construction']; construct.checked = false; construct.handlers.change();
seen.pendingAfterHide = timers.filter(t => t.live).length; flush(); seen.spokenAfterHide = live.textContent;
construct.checked = true; construct.handlers.change();
// 2) the names follow the language of the key press, not the language the chart was built in
language = 'en'; key('ArrowLeft'); flush(); seen.english = live.textContent;
language = 'he'; key('ArrowLeft'); flush(); seen.hebrew = live.textContent;
// 3) a boundary key restores a tooltip removed by the mouse, without speaking again
key('End'); flush(); live.textContent = '';
chart.tooltip.setActiveElements([], {x: 0, y: 0}); chart.setActiveElements([]);
seen.boundaryPrevented = key('End');
seen.restored = chart.tooltip.active.length; seen.restoredQuiet = timers.filter(t => t.live).length === 0 && live.textContent === '';
process.stdout.write(JSON.stringify(seen));
""" % (json.dumps(str(ROOT / 'assets/statso-core.js')), json.dumps(str(ROOT / 'assets/statso-chart.js')))
        seen = json.loads(subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True, encoding="utf-8"
        ).stdout)
        self.assertEqual(seen['pendingAfterHide'], 0)
        self.assertEqual(seen['spokenAfterHide'], '')
        self.assertEqual(seen['english'], '11/2020: CPI-en 122.0; Build-en 2,010.0')
        self.assertEqual(seen['hebrew'], '10/2020: CPI-he 121.0; Build-he 2,009.0')
        self.assertTrue(seen['boundaryPrevented'])
        self.assertEqual(seen['restored'], 2)
        self.assertTrue(seen['restoredQuiet'])

    def test_skipped_content_still_gets_its_attributes_translated(self):
        # data-i18n-skip protects the content of code blocks from translation, but the aria-label on
        # the <pre> is read aloud, so it must follow the language (it used to stay Hebrew in English).
        script = """
const attrs = {'aria-label': 'קוד לדוגמה'};
const text = {nodeType: 3, nodeValue: 'קורונה', nextSibling: null};   // translatable, so a stray traversal would show
const pre = {nodeType: 1, tagName: 'PRE', firstChild: text, nextSibling: null,
 hasAttribute: name => name === 'data-i18n-skip' || name in attrs, getAttribute: name => attrs[name],
 setAttribute(name, value) { attrs[name] = value; }};
const body = {nodeType: 1, tagName: 'BODY', firstChild: pre, nextSibling: null, hasAttribute: () => false};
pre.parent = body;
global.window = {location: {search: '', href: 'https://x.test/'}, history: {replaceState() {}},
 localStorage: {getItem() { return null; }, setItem() {}}};
global.document = {body, addEventListener() {}, getElementById: () => null, querySelector: () => null,
 querySelectorAll: () => [], documentElement: {setAttribute() {}}};
require(%s); require(%s);
const S = window.Statso, seen = {};
S.i18n.init();
S.i18n.set('en'); seen.english = attrs['aria-label']; seen.contentUntouched = text.nodeValue;
S.i18n.set('he'); seen.hebrewAgain = attrs['aria-label'];
process.stdout.write(JSON.stringify(seen));
""" % (json.dumps(str(ROOT / "assets/statso-lang-en.js")), json.dumps(str(ROOT / "assets/statso-i18n.js")))
        seen = json.loads(subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True, encoding="utf-8"
        ).stdout)
        self.assertEqual(seen, {"english": "Sample code", "contentUntouched": "קורונה", "hebrewAgain": "קוד לדוגמה"})

    def test_missing_rate_messages_translate_the_currency_name_too(self):
        script = """
global.window = {};
require(%s);
const L = window.Statso.lang;
const t = s => { for (const rule of L.enPatterns) { if (rule[0].test(s)) { return s.replace(rule[0], rule[1]); } } return s; };
process.stdout.write(JSON.stringify([t('אין שער לדולר ארה״ב לפני 15/05/1948.'), t('אין נתוני שער עבור אירו.'),
 t('אין נתוני שער עבור XYZ.')]));
""" % json.dumps(str(ROOT / "assets/statso-lang-en.js"))
        seen = json.loads(subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True, encoding="utf-8"
        ).stdout)
        self.assertEqual(seen, ["No rate for US dollar before 15/05/1948.", "No rate data for Euro.", "No rate data for XYZ."])

    def test_chart_markup_and_strings(self):
        section = re.search(r'<section[^>]*id="chart-section".*?</section>', self.html, re.DOTALL).group(0)
        self.assertIn('<div class="sr-only" id="chart-live" role="status" aria-live="polite" aria-atomic="true"></div>', section)
        help_text = re.search(r'<p class="sr-only" id="chart-keys-help">([^<]+)</p>', section).group(1)
        language = (ROOT / 'assets/statso-lang-en.js').read_text(encoding='utf-8')
        self.assertIn("'" + help_text + "':", language)
        self.assertIn("'סדרות בתרשים':", language)
        fieldset = re.search(r'<fieldset class="chart-series">.*?</fieldset>', section).group(0)
        for id_ in ('chart-series-cpi', 'chart-series-construction'):
            self.assertIn('<input id="' + id_ + '" type="checkbox" checked>', fieldset)
        chart = (ROOT / 'assets/statso-chart.js').read_text(encoding='utf-8')
        for text in ('preventDefault', 'metaKey', 'setActiveElements', 'setDatasetVisibility',
                     'onClick: onLegendClick', 'nextIndex: nextIndex', 'announcementText: announcementText'):
            self.assertIn(text, chart)

    def test_accessibility_statement_lists_the_new_accommodations(self):
        page = re.search(r'<article[^>]*id="accessibility-page".*?</article>', self.html, re.DOTALL).group(0)
        he = re.search(r'data-lang="he">(.*?)</div>', page, re.DOTALL).group(1)
        en = re.search(r'data-lang="en" hidden>(.*?)</div>', page, re.DOTALL).group(1)
        self.assertIn('10/10/2026', he)
        self.assertIn('10 October 2026', en)
        for block in (he, en):
            self.assertIn('forced colors', block)
            self.assertIn('Page Up/Page Down', block)
            self.assertIn('Home/End', block)
            self.assertIn('NVDA/JAWS', block)
        self.assertIn('VoiceOver</span> לא בוצעה בשלב זה.', he)
        self.assertIn('VoiceOver</span> screen reader was not performed at this stage.', en)
        self.assertNotRegex(en, r'[֐-׿]')
        for old in ('09/10/2026', '9 October 2026', 'לא מתוך הגרף עצמו', 'not from the chart itself'):
            self.assertNotIn(old, page)

    def test_contact_hebrew_messages_have_english_entries(self):
        contact = (ROOT / 'assets/statso-contact.js').read_text(encoding='utf-8')
        language = (ROOT / 'assets/statso-lang-en.js').read_text(encoding='utf-8')
        # The email subject is service metadata, not a message shown in the UI.
        contact = re.sub(r"payload\.set\('subject', '[^']*'\);", '', contact)
        messages = [text for text in re.findall(r"'([^'\n]*)'", contact) if re.search(r'[֐-׿]', text)]
        self.assertEqual(len(set(messages)), 12)
        for message in messages:
            self.assertIn("'" + message + "':", language)

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
