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


def node(script):
    result = subprocess.run(["node", "-e", script], cwd=ROOT, capture_output=True, text=True)
    if result.returncode:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


def module(name):
    return "require(" + json.dumps(str(ROOT / "assets" / name)) + ");"


FIELD_DOM = r"""
global.window = {};
const fields = {};
function field(id, attrs = {}) {
  const f = {id, attrs: {...attrs}, setAttribute(k, v) { this.attrs[k] = String(v); },
    getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }, removeAttribute(k) { delete this.attrs[k]; }};
  fields[id] = f; return f;
}
global.document = {getElementById: id => fields[id] || null,
  querySelectorAll(selector) {
    const flag = selector.match(/^\[data-error-flag="(.+)"\]$/)[1];
    return Object.values(fields).filter(f => f.getAttribute('data-error-flag') === flag);
  }};
"""
GUIDE_DOM = r"""
global.window = {};
const host = {innerHTML: ''};
const stub = {setAttribute() {}, addEventListener() {}, innerHTML: ''};
global.document = {addEventListener() {}, getElementById() { return stub; },
  querySelector(s) { return s === '.guide-steps-host' ? host : stub; }, querySelectorAll() { return []; }};
"""


class FlaggedFieldTests(unittest.TestCase):
    def test_flagged_fields_say_they_are_invalid_and_point_at_the_message(self):
        seen = node(FIELD_DOM + module("statso-core.js") + r"""
field('a'); field('b', {'aria-describedby': 'hint'}); field('c');
const core = window.Statso.core;
const state = () => Object.fromEntries(Object.values(fields).map(f => [f.id, [f.getAttribute('aria-invalid'), f.getAttribute('aria-describedby'), f.getAttribute('data-error-flag')]]));
core.flagFields('err', ['a', 'b']);
const first = state();
core.flagFields('err', ['c', 'missing-id']);
const second = state();
core.flagFields('err', []);
process.stdout.write(JSON.stringify({first, second, third: state()}));
""")
        self.assertEqual(seen["first"]["a"], ["true", "err", "err"])
        self.assertEqual(seen["first"]["b"], ["true", "hint err", "err"])
        # a new call withdraws the earlier flags (and keeps the hint that was there before)
        self.assertEqual(seen["second"]["a"], [None, None, None])
        self.assertEqual(seen["second"]["b"], [None, "hint", None])
        self.assertEqual(seen["second"]["c"], ["true", "err", "err"])
        self.assertEqual(seen["third"]["c"], [None, None, None])

    def test_a_field_something_else_already_marked_invalid_is_left_alone(self):
        seen = node(FIELD_DOM + module("statso-core.js") + r"""
field('month', {'aria-invalid': 'true', 'aria-describedby': 'month-hint tr-error'});
const core = window.Statso.core;
core.flagFields('tr-error', ['month']);
const flagged = {...fields.month.attrs};
core.flagFields('tr-error', []);
process.stdout.write(JSON.stringify({flagged, after: fields.month.attrs}));
""")
        self.assertEqual(seen["flagged"], {"aria-invalid": "true", "aria-describedby": "month-hint tr-error"})
        self.assertEqual(seen["after"], {"aria-invalid": "true", "aria-describedby": "month-hint tr-error"})

    def test_elements_are_accepted_as_well_as_ids(self):
        seen = node(FIELD_DOM + module("statso-core.js") + r"""
const box = field('box');
window.Statso.core.flagFields('e', [box]);
process.stdout.write(JSON.stringify(box.attrs));
""")
        self.assertEqual(seen, {"aria-describedby": "e", "aria-invalid": "true", "data-error-flag": "e"})

    def test_every_tool_error_line_flags_the_fields_it_is_about(self):
        errors = re.findall(r'id="([a-z-]+-error)"[^>]*role="alert"', HTML)
        self.assertEqual(sorted(errors), sorted([
            "chart-range-error", "calc-error", "mc-error", "ti-error", "tf-error", "th-error",
            "trh-error", "fxh-error", "tr-error"]))
        sources = {path.name: path.read_text(encoding="utf-8") for path in (ROOT / "assets").glob("statso-*.js")}
        joined = "\n".join(sources.values())
        for error in errors:
            wired = re.search(r"(flagFields|showError)\(\s*'" + error + "'", joined)
            self.assertTrue(wired, error + " is announced but no field is marked invalid for it")
        # the shared helpers: the tools module passes the id through, so each id above reaches flagFields
        self.assertIn("Statso.core.flagFields(errorId, fields || [])", sources["statso-tools.js"])

    def test_alert_text_is_not_written_around_the_helpers(self):
        # a message written straight to the line would leave the previous message's fields flagged
        for name, ids in {"statso-calculator.js": ["calc-error"], "statso-tools.js": ["ti-error", "tf-error", "th-error"],
                          "statso-ratehistory.js": ["trh-error"], "statso-rent.js": ["tr-error"]}.items():
            source = (ROOT / "assets" / name).read_text(encoding="utf-8")
            for error in ids:
                direct = re.findall(r"(?:el|getElementById)\('" + error + r"'\)\)?\.textContent\s*=", source)
                # one direct write per module: the helper itself
                self.assertLessEqual(len(direct), 1, name + " writes " + error + " directly")


class GuideNameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rendered = node(GUIDE_DOM + "".join(module(n) for n in (
            "statso-core.js", "statso-guide-art.js", "statso-guides.js", "statso-mcode.js")) + r"""
const S = window.Statso, out = {};
for (const site of ['he', 'en']) {
  S.i18n = {current: () => site, onChange() {}};
  for (const platform of ['mac', 'win']) for (const method of ['power', 'manual', 'webservice']) {
    Object.assign(S.guides.state, {platform, method});
    S.guides.renderExcelGuide();
    out[[site, platform, method].join('/')] = host.innerHTML;
  }
}
out.cpi = S.guideArt.render('timeline-publication', {lang: 'he', platform: 'win'});
out.descriptions = S.guideArt.descriptions;
process.stdout.write(JSON.stringify(out));
""")

    def test_pictures_are_described_in_words_never_by_their_internal_id(self):
        id_like = re.compile(r"^[a-z]+(-[a-z]+)+$")
        labels = []
        for key, html in self.rendered.items():
            if key == "descriptions":
                continue
            labels += re.findall(r'<svg class="guide-svg[^>]*role="img" aria-label="([^"]*)"', html)
        self.assertTrue(labels)
        descriptions = set(self.rendered["descriptions"].values())
        for label in labels:
            self.assertFalse(id_like.match(label), label)
            self.assertIn(label.replace("&quot;", '"'), descriptions)
        self.assertNotIn("cell-formula", self.rendered["cpi"])
        self.assertIn(self.rendered["descriptions"]["timeline-publication"], self.rendered["cpi"])

    def test_every_drawn_archetype_has_a_description_with_an_english_version(self):
        art = (ROOT / "assets/statso-guide-art.js").read_text(encoding="utf-8")
        drawn = set(re.findall(r"archetype === '([a-z-]+)'", art))
        self.assertEqual(drawn, set(self.rendered["descriptions"]))
        keys = dictionary_keys()
        for text in self.rendered["descriptions"].values():
            self.assertIn(text, keys)
        self.assertIn("איור", keys)

    def test_copy_buttons_on_one_page_never_share_a_name(self):
        for key, html in self.rendered.items():
            if key in ("descriptions", "cpi"):
                continue
            names = []
            for attrs, text in re.findall(r'<button class="copy-url"([^>]*)>([^<]*)</button>', html):
                label = re.search(r' aria-label="([^"]*)"', attrs)
                name = label.group(1) if label else text
                if label:
                    self.assertTrue(name.startswith(text), name)  # label in name: the visible word comes first
                names.append((name, re.search(r'data-url="([^"]*)"', attrs).group(1) if "data-url" in attrs else None))
            # two buttons may share a name only when they copy the very same thing
            by_name = {}
            for name, url in names:
                by_name.setdefault(name, set()).add(url)
            for name, urls in by_name.items():
                self.assertEqual(len(urls), 1, key + ": '" + name + "' copies " + str(urls))

    def test_webservice_guide_tells_its_two_copy_buttons_apart(self):
        html = self.rendered["he/win/webservice"]
        labels = re.findall(r'<button class="copy-url"[^>]* aria-label="([^"]*)"', html)
        self.assertEqual(len(labels), len(set(labels)))
        self.assertGreaterEqual(len(labels), 2)
        keys = dictionary_keys()
        for label in labels:
            self.assertIn(label, keys)


class BackLinkTests(unittest.TestCase):
    def test_the_arrow_in_a_back_link_is_decoration_not_part_of_its_name(self):
        links = re.findall(r'<a class="(?:tool-back|info-back|guide-back)"[^>]*>(.*?)</a>', HTML)
        self.assertGreaterEqual(len(links), 13)
        for body in links:
            self.assertTrue(body.startswith('<span class="back-arrow" aria-hidden="true">←</span> '), body)
        # the glyph must not survive outside that span (it would be read as "left arrow")
        self.assertNotRegex(HTML, r'<a [^>]*>\s*←')
        keys = dictionary_keys()
        for text in ("לכל הכלים", "חזרה לעמוד הבית", "חזרה לכל המדריכים"):
            self.assertIn(text, keys)
        for old in ("← לכל הכלים", "← חזרה לעמוד הבית", "← חזרה לכל המדריכים"):
            self.assertNotIn(old, keys)


class TextSizeLayoutTests(unittest.TestCase):
    # Found with 200% text at 305-1024px: the header pushed the language switcher off the unreachable side of an RTL
    # page and the fourth home card left the screen. Each rule lets content move to a new row or word-break instead.
    def rule(self, selector):
        match = re.search(r"(?m)^" + re.escape(selector) + r" \{([^}]*)\}", CSS)
        self.assertTrue(match, selector)
        return match.group(1)

    def test_header_wraps_instead_of_overflowing(self):
        self.assertIn("flex-wrap: wrap", self.rule(".header-inner"))
        self.assertIn("flex-wrap: wrap", self.rule(".site-nav"))
        self.assertIn("flex-wrap: wrap", self.rule(".brand-group"))
        self.assertNotIn("nowrap", self.rule(".lang-button"))

    def test_nav_item_widths_grow_with_the_text(self):
        self.assertIn("width: 8rem", self.rule(".nav-item-stacked"))
        self.assertIn("width: 7rem", CSS)
        self.assertIn("width: 6.5rem", CSS)
        self.assertNotRegex(CSS, r"\.nav-item-stacked \{[^}]*width: \d+px")

    def test_home_cards_wrap_by_the_room_their_text_needs(self):
        self.assertIn("display: flex; flex-wrap: wrap", self.rule(".kpi-grid"))
        self.assertRegex(self.rule(".kpi-grid > .kpi-card"), r"flex: 1 1 max\(12\.5rem, calc\(25% - 11px\)\)")
        self.assertIn("min-width: 0", self.rule(".kpi-grid > .kpi-card"))
        self.assertIn("flex-wrap: wrap", self.rule(".kpi-pair"))
        self.assertIn("flex-basis: max(12.5rem, calc(50% - 8px))", re.search(r"@media \(max-width: 900px\) \{[^@]*\}", CSS).group(0))
        self.assertIn(".kpi-grid > .kpi-card { flex-basis: 100%; }", re.search(r"@media \(max-width: 600px\) \{.*", CSS).group(0))

    def test_long_words_and_links_break_instead_of_widening_the_page(self):
        self.assertIn("overflow-wrap: break-word", self.rule("h1, h2, h3, h4"))
        self.assertIn("overflow-wrap: anywhere", self.rule(".calc-result strong"))
        self.assertNotIn("nowrap", self.rule(".footer-links a"))
        self.assertNotIn(".fxh-currency { white-space: nowrap", CSS)
        self.assertIn("overflow-wrap: anywhere", self.rule(".prose-guide"))
        self.assertNotRegex(self.rule(".guide-pill"), "nowrap")


if __name__ == "__main__":
    unittest.main()
