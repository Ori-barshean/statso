"""Class-level accessibility checks.

The earlier rounds fixed the instances that an audit happened to find. These tests describe the *kind* of mistake
instead, and scan the whole stylesheet, the markup and the script templates for it, so that a new instance of the
same mistake fails here rather than waiting for the next audit.
"""
import json
import re
import subprocess
import unittest
from html.parser import HTMLParser
from pathlib import Path

from tests.test_i18n import dictionary_keys

ROOT = Path(__file__).resolve().parent.parent
HTML = (ROOT / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "assets/statso.css").read_text(encoding="utf-8")
ASSETS = sorted((ROOT / "assets").glob("statso-*.js"))

# arrows, geometric shapes, dingbats (check marks, crosses), misc symbols, bullets
SYMBOLS = "←-⇿⌀-⏿■-➿⬀-⯿•\u00d7"
SYMBOL = re.compile("[" + SYMBOLS + "]")


def node(script):
    result = subprocess.run(["node", "-e", script], cwd=ROOT, capture_output=True, text=True)
    if result.returncode:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


def module(name):
    return "require(" + json.dumps(str(ROOT / "assets" / name)) + ");"


def css_rules(css=CSS):
    text = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return [(m.group(1).strip(), m.group(2)) for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", text)]


def selector_parts(selector):
    return [part.strip() for part in selector.split(",") if part.strip()]


def media_block(css, header):
    start = css.index(header)
    depth, i = 0, css.index("{", start)
    begin = i
    while True:
        if css[i] == "{":
            depth += 1
        elif css[i] == "}":
            depth -= 1
            if not depth:
                return css[begin + 1:i]
        i += 1


class NameParser(HTMLParser):
    """Text of every link and button as a screen reader would build the name: aria-hidden subtrees left out."""

    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}

    def __init__(self):
        super().__init__()
        self.stack, self.active, self.done = [], [], []

    def handle_starttag(self, tag, attrs):
        if tag in self.VOID:
            return
        attrs = dict(attrs)
        hidden = attrs.get("aria-hidden") == "true" or bool(self.stack and self.stack[-1][1])
        self.stack.append((tag, hidden))
        if tag in ("a", "button") and not hidden:
            self.active.append([tag, attrs, ""])

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break
        if tag in ("a", "button") and self.active:
            self.done.append(self.active.pop())

    def handle_data(self, data):
        if self.active and self.stack and not self.stack[-1][1]:
            self.active[-1][2] += data


class DecorativeSymbolTests(unittest.TestCase):
    def test_no_link_or_button_in_the_markup_has_a_symbol_in_its_name(self):
        parser = NameParser()
        parser.feed(HTML)
        self.assertGreater(len(parser.done), 40)
        offenders = [(tag, " ".join(text.split())) for tag, attrs, text in parser.done
                     if SYMBOL.search(text) or re.match(r"[^\w\"'(\[]", " ".join(text.split()), re.U)]
        self.assertEqual(offenders, [])

    def test_tool_card_marks_are_hidden_from_screen_readers(self):
        marks = re.findall(r'<span class="tool-card-mark"([^>]*)>', HTML)
        self.assertEqual(len(marks), 6)
        for attrs in marks:
            self.assertIn('aria-hidden="true"', attrs)

    def test_symbols_written_into_script_templates_are_hidden_too(self):
        # the name of a link or button is its text with the aria-hidden parts left out, nested tags included
        hidden = re.compile(r"<(\w+)\b[^>]*aria-hidden=\"true\"[^>]*>.*?</\1>", re.S)
        offenders = []
        for path in ASSETS:
            if path.name in ("statso-lang-en.js", "statso-guide-art.js"):
                continue
            source = path.read_text(encoding="utf-8")
            for match in re.finditer(r"<(a|button)\b([^>]*)>(.*?)</\1>", source, re.S):
                inner = re.sub(r"<[^>]+>", "", hidden.sub("", match.group(3)))
                if SYMBOL.search(inner):
                    offenders.append(path.name + ": " + match.group(0)[:90])
            # a symbol, multiplier or arrow in any other small element must be hidden or be real content
            for match in re.finditer(r"<(span|b|i|strong|em|label|li|h[1-6]|th|td|summary)\b([^>]*)>([^<]*["
                                     + SYMBOLS + r"][^<]*)</\1>", source):
                if 'aria-hidden="true"' not in match.group(2) and "currency-code" not in match.group(2):
                    offenders.append(path.name + ": " + match.group(0)[:90])
        self.assertEqual(offenders, [])

    def test_generated_css_symbols_carry_an_empty_spoken_alternative(self):
        checked = 0
        for selector, body in css_rules():
            decls = [(text, alt) for _, text, alt, _ in re.findall(r"""content:\s*(["'])(.*?)\1(\s*/\s*(["'])\4)?""", body)]
            spoken_empty = {text for text, alt in decls if alt}
            for text, _ in decls:
                if text.strip() and not re.fullmatch(r"[\w\s]+", text, re.U):
                    checked += 1
                    self.assertIn(text, spoken_empty, selector + " writes a symbol that a screen reader would speak")
        self.assertGreaterEqual(checked, 1)   # the collapse caret

    def test_the_language_menu_tick_is_a_hidden_element_shown_only_for_the_current_language(self):
        choices = re.findall(r'<button type="button" class="lang-choice"[^>]*>(.*?)</button>', HTML)
        self.assertEqual(len(choices), 2)
        for inner in choices:
            self.assertIn('<span class="lang-tick" aria-hidden="true"> \u2713</span>', inner)
        self.assertIn(".lang-choice:not([aria-current=\"true\"]) .lang-tick { display: none; }", CSS)

    def test_the_copy_confirmation_keeps_its_tick_out_of_the_button_name(self):
        seen = node(r"""
global.window = {setTimeout() { return 1; }, clearTimeout() {}};
const live = {textContent: ''};
function element() {
  return {attrs: {}, kids: [], _text: '', setAttribute(k, v) { this.attrs[k] = v; }, hasAttribute(k) { return k in this.attrs; },
    removeAttribute(k) { delete this.attrs[k]; }, appendChild(c) { this.kids.push(c); },
    get textContent() { return this._text + this.kids.map(k => k.textContent).join(''); },
    set textContent(v) { this._text = v; this.kids = []; }};
}
global.document = {getElementById: () => live, createElement: element};
""" + module("statso-export.js") + r"""
const withTick = element(); withTick._text = 'copy';
window.Statso.exporter.flash(withTick, 'Copied ✓');
const plain = element(); plain._text = 'copy';
window.Statso.exporter.flash(plain, 'Copy failed');
process.stdout.write(JSON.stringify({
  name: withTick._text, kids: withTick.kids.map(k => [k.attrs['aria-hidden'], k.textContent]), live: live.textContent,
  plain: plain._text, plainKids: plain.kids.length}));
""")
        self.assertEqual(seen["name"], "Copied")
        self.assertEqual(seen["kids"], [["true", " ✓"]])
        self.assertEqual(seen["plain"], "Copy failed")
        self.assertEqual(seen["plainKids"], 0)


class ForcedColorsTests(unittest.TestCase):
    def test_buttons_that_are_only_a_fill_get_a_border_when_fills_are_not_drawn(self):
        forced = media_block(CSS, "@media (forced-colors: active)")
        covered = {part for selector, _ in css_rules(forced) for part in selector_parts(selector)
                   if "border" in dict(css_rules(forced)).get(selector, "")}
        fill_only = set()
        for selector, body in css_rules():
            if not re.search(r"(?<![-\w])border:\s*(0|none)\b", body):
                continue
            fill = re.search(r"(?<![-\w])background(?:-color)?:\s*([^;]+)", body)
            if fill and not re.match(r"(none|transparent|inherit)\b", fill.group(1).strip()):
                fill_only.update(selector_parts(selector))
        self.assertGreaterEqual(len(fill_only), 5)
        self.assertEqual(sorted(fill_only - covered), [])

    def test_the_forced_colors_block_is_the_end_of_the_file_so_it_wins(self):
        header = "@media (forced-colors: active)"
        start = CSS.index(header)
        end = CSS.index("{", start) + 1 + len(media_block(CSS, header)) + 1   # opening brace, block, closing brace
        self.assertEqual(CSS[end:].strip(), "", "a rule written after the forced-colors block would beat it")
        self.assertEqual(CSS.count(header), 1)


class ContrastAndScrollTests(unittest.TestCase):
    def test_content_is_never_dimmed_with_opacity(self):
        # opacity lowers the contrast of every word inside; only controls that are really off may use it
        for selector, body in css_rules():
            for value in re.findall(r"(?<![-\w])opacity:\s*([\d.]+)", body):
                if 0 < float(value) < 1:
                    self.assertRegex(selector, r":disabled|\[aria-disabled", selector + " dims content with opacity")

    def test_the_coming_soon_card_is_plain_content_with_a_visible_difference(self):
        rule = dict(css_rules())[".guide-card-soon"]
        self.assertNotIn("opacity", rule)
        self.assertIn("dashed", rule)
        source = (ROOT / "assets/statso-guides.js").read_text(encoding="utf-8")
        card = re.search(r"guide\.soon\) \{ return '(<div[^']*)'", source).group(1)
        self.assertNotIn("aria-disabled", card)

    def test_every_scroll_box_leaves_room_for_the_focus_ring(self):
        # a focused control that the browser scrolls into a box lands flush with its edge, where the ring is cut off
        padded, scrollers = set(), set()
        for selector, body in css_rules():
            for part in selector_parts(selector):
                key = re.sub(r"\[[^\]]*\]", "", part)
                if "scroll-padding" in body:
                    padded.add(key)
                if re.search(r"overflow(-x|-y)?:\s*(auto|scroll)", body):
                    scrollers.add(key)
        self.assertGreaterEqual(len(scrollers), 4)
        self.assertEqual(sorted(scrollers - padded), [])


class DataProblemNoticeTests(unittest.TestCase):
    def test_the_notice_sits_above_every_page_and_starts_empty_and_hidden(self):
        wrap = re.search(r'<section class="shell data-problem-wrap" id="data-problem-wrap"([^>]*)>\s*'
                         r'<div class="data-problem" id="data-problem" role="alert"></div>\s*</section>', HTML)
        self.assertIsNotNone(wrap)
        self.assertIn("hidden", wrap.group(1))
        self.assertIn('aria-label="תקלה בטעינת נתונים"', wrap.group(1))
        self.assertLess(wrap.start(), HTML.index("<main"))
        self.assertGreater(wrap.start(), HTML.index("</header>"))

    def test_strings_have_english_versions(self):
        keys = dictionary_keys()
        for text in ("חלק מהנתונים לא נטענו, ולכן ייתכן שחלק מהכלים לא יפעלו. אפשר לרענן את הדף ולנסות שוב.",
                     "נתונים שלא נטענו:", "תקלה בטעינת נתונים", "מדד המחירים לצרכן", "ריבית בנק ישראל", "שערי חליפין"):
            self.assertIn(text, keys)

    @staticmethod
    def notice_after(results, deferred=False):
        return node(r"""
const els = {};
function made(id) { return {id, hidden: true, textContent: '', kids: [], dataset: {}, style: {}, appendChild(c) { this.kids.push(c); },
  setAttribute() {}, getBoundingClientRect() { return {height: 0}; }, querySelector() { return null; }}; }
const timers = [];
global.window = {addEventListener() {}, dispatchEvent() {}, setTimeout: fn => { %s; return 1; }};
global.CustomEvent = function () {};
global.document = {addEventListener() {}, querySelectorAll() { return []; }, getElementById(id) { return els[id] || (els[id] = made(id)); },
  createElement(tag) { return made(tag); }};
const no = new Error('x');
const gone = {status: 'rejected', reason: no};
const here = value => ({status: 'fulfilled', value});
const fx = {rates: [{code: 'USD', latest: {rate: 3.3, date: '2026-10-01'}}, {code: 'EUR', latest: {rate: 3.9, date: '2026-10-01'}}]};
const results = %s;
window.Statso = {data: {loadAll: () => Promise.resolve(results), loadVersion: () => Promise.reject(no), setState() {}},
  collapse: {attach() {}}, i18n: {onChange() {}}, chart: {init() {}, showUnavailable() {}, activate() {}},
  calculator: {init() {}, initFx() {}}, fxtable: {init() {}},
  core: {buildIndexMap: () => new Map(), latestObservation: () => ({}), yearOverYear: () => ({ok: true, percent: 1}),
    monthOverMonth: () => ({ok: true, percent: 1}), formatPercent: v => String(v), shiftMonth: m => m, formatMonthHe: m => m,
    formatIsoDateHe: d => d, nextCpiPublicationDate: () => '2026-10-15', primeRate: v => v + 1.5, formatRate: v => String(v)}};
""" % ("fn()" if not deferred else "timers.push(fn)", results) + module("statso-app.js") + r"""
window.Statso.app.init();
setTimeout(() => {
  const wrap = els['data-problem-wrap'], box = els['data-problem'];
  const text = n => n.textContent + n.kids.map(text).join('|');
  const before = {hidden: wrap.hidden, parts: box.kids.length};
  timers.forEach(fn => fn());
  process.stdout.write(JSON.stringify({hidden: wrap.hidden, parts: box.kids.map(text), before}));
}, 30);
""")

    CPI = "here({observations: [], last_month: '2026-09'})"
    BOI = "here({current_rate: 4.5})"

    def test_a_failed_load_names_each_failed_dataset_once_in_the_notice(self):
        seen = self.notice_after("[gone, gone, gone, gone, gone]")
        self.assertFalse(seen["hidden"])
        self.assertEqual(seen["parts"], [
            "חלק מהנתונים לא נטענו, ולכן ייתכן שחלק מהכלים לא יפעלו. אפשר לרענן את הדף ולנסות שוב.",
            "נתונים שלא נטענו:",
            "|".join(["מדד המחירים לצרכן", "ריבית בנק ישראל", "שערי חליפין"])])

    def test_the_alert_is_shown_empty_first_and_filled_afterwards(self):
        seen = self.notice_after("[gone, gone, gone, gone, gone]", deferred=True)
        self.assertEqual(seen["before"], {"hidden": False, "parts": 0})
        self.assertEqual(len(seen["parts"]), 3)

    def test_only_the_dataset_that_failed_is_named(self):
        seen = self.notice_after("[%s, gone, gone, here(fx), gone]" % self.CPI)
        self.assertFalse(seen["hidden"])
        self.assertEqual(seen["parts"][2], "ריבית בנק ישראל")

    def test_nothing_is_shown_when_everything_loaded(self):
        seen = self.notice_after("[%s, %s, here({next_decision_date: '2026-11-24'}), here(fx), here({observations: []})]"
                                 % (self.CPI, self.BOI))
        self.assertTrue(seen["hidden"])
        self.assertEqual(seen["parts"], [])

    def test_the_optional_datasets_do_not_raise_the_notice(self):
        # the next-decision date and the construction inputs have their own, local messages
        seen = self.notice_after("[%s, %s, gone, here(fx), gone]" % (self.CPI, self.BOI))
        self.assertTrue(seen["hidden"])
        self.assertEqual(seen["parts"], [])


if __name__ == "__main__":
    unittest.main()
