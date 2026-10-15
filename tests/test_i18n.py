import re
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent
HEBREW = re.compile(r"[֐-׿]")


def dictionary_keys():
    """Every Hebrew key the English dictionary defines."""
    text = (ROOT / "assets/statso-lang-en.js").read_text(encoding="utf-8")
    body = text.split("const enPatterns")[0]
    keys = set()
    for match in re.finditer(r"'((?:[^'\\]|\\.)*)':", body):
        keys.add(match.group(1).replace("\\'", "'"))
    return keys


def page_strings():
    """Hebrew text nodes and attributes the page ships, minus the he-only blocks."""
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    html = re.sub(r'<script\b.*?</script>', '', html, flags=re.DOTALL)
    html = re.sub(r'<div class="lang-picker".*?</div>\s*</div>', '', html, flags=re.DOTALL)
    # the information pages carry a full English sibling instead of per-string keys
    html = re.sub(r'<div class="prose-guide" data-lang="he">.*?</div>\s*(?=<div class="prose-guide" data-lang="en")',
                  '', html, flags=re.DOTALL)
    texts = set()
    for chunk in re.split(r'<[^>]+>', html):
        cleaned = chunk.replace("&quot;", '"').replace("&amp;", "&").strip()
        if cleaned and HEBREW.search(cleaned):
            texts.add(cleaned)
    for match in re.finditer(r'\b(?:placeholder|aria-label|title|alt)="([^"]*)"', html):
        value = match.group(1).strip()
        if HEBREW.search(value):
            texts.add(value)
    return texts


class DictionaryCoverageTests(unittest.TestCase):
    def test_every_hebrew_string_in_the_page_has_an_english_entry(self):
        missing = sorted(page_strings() - dictionary_keys())
        self.assertEqual(missing, [], f"no English for: {missing}")

    def test_information_pages_ship_both_languages(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertEqual(html.count('data-lang="he"'), html.count('data-lang="en"'))
        self.assertEqual(html.count('data-lang="he"'), 5)

    def test_mac_power_step_and_image_alt_have_english_entries(self):
        keys = dictionary_keys()
        self.assertIn('פותחים חוברת עבודה חדשה, עוברים ללשונית Data / ״נתונים״ ולוחצים על ״יבא נתונים (Power Query)״.', keys)
        self.assertIn('אקסל למק בעברית: לשונית נתונים והכפתור ״יבא נתונים (Power Query)״.', keys)

    def test_new_mac_steps_alts_labels_and_errors_have_translations(self):
        keys = dictionary_keys()
        for name in ("statso-guides.js", "statso-mcode.js"):
            source = (ROOT / "assets" / name).read_text()
            if name == "statso-guides.js":
                source = source.split("if (method === 'power')")[1].split("if (method === 'manual')")[0]
                texts = re.findall(r"(?:text|textAfterLink|alt): '([^']+)'", source)
            else:
                texts = re.findall(r"error = '([^']+)'", source)
            for text in texts:
                self.assertIn(text, keys)
        for text in ('בחר מקור נתונים', 'שאילתה ריקה', 'טקסט/CSV', 'עורך מתקדם', 'קבע תצורה של חיבור', 'אישורים לא חוקיים או חסרים', 'סגור וטען', 'רענון אוטומטי של הנתונים ב-Excel'):
            self.assertIn(text, keys)
        self.assertFalse(any('בוחרים Data ← Get Data ← From Web' in key or '״From Web״ קיים' in key for key in keys))

    def test_mac_code_cta_literals_have_translations(self):
        source = (ROOT / 'assets/statso-guides.js').read_text()
        keys = dictionary_keys()
        subtitle = re.search(r'<h1 id="excel-guide-title">.*?</h1><p>(.*?)</p>', source).group(1)
        self.assertIn(subtitle, keys)
        self.assertIn('העתקת הקוד', keys)
        self.assertIn('קודים לייצוא (Power Query)', keys)
        cta = source.split('function mcodeCta() {')[1].split('\n  }')[0]
        example = source.split('function mcodeExample() {')[1].split('\n  }')[0]
        literals = [text for text in re.findall(r"'([^']+)'", cta + example) if HEBREW.search(text)]
        self.assertEqual(len(literals), 2)
        for text in literals:
            self.assertIn(text, keys)

    def test_guides_render_without_hebrew_in_english(self):
        import json
        import subprocess
        script = r'''
global.window = {scrollTo() {}};
const els = {}, callbacks = [];
function element() { return {nodeType: 9, hidden: false, innerHTML: '', setAttribute() {}, addEventListener() {}}; }
const host = element();
global.document = {documentElement: {setAttribute() {}}, body: {nodeType: 9},
  addEventListener(event, fn) { callbacks.push(fn); },
  getElementById: id => els[id] || (els[id] = element()),
  querySelector: selector => selector === '.guide-steps-host' ? host : null,
  querySelectorAll: () => []};
'''
        script += '\n'.join('require(' + json.dumps(str(ROOT / 'assets' / name)) + ');' for name in
                            ('statso-lang-en.js', 'statso-i18n.js', 'statso-core.js',
                             'statso-guide-art.js', 'statso-mcode.js', 'statso-guides.js'))
        script += r'''
const S = window.Statso;
S.i18n.set('en');
callbacks[callbacks.length - 1]();
const pages = {cards: els['guide-cards'].innerHTML};
for (const platform of ['mac', 'win']) for (const method of ['power', 'manual', 'webservice']) {
  Object.assign(S.guides.state, {platform, method}); S.guides.renderExcelGuide();
  pages[platform + '/' + method] = els['guide-content'].innerHTML + host.innerHTML;
}
S.guides.showGuide('live-pull', true); pages.live = els['guide-content'].innerHTML;
const entities = {amp: '&', quot: '"', apos: "'", lt: '<', gt: '>', nbsp: '\u00a0'};
function decode(text) {
  return text.replace(/&(#x[0-9a-f]+|#\d+|amp|quot|apos|lt|gt|nbsp);/gi, (all, value) =>
    value[0] === '#' ? String.fromCodePoint(value[1].toLowerCase() === 'x' ?
      parseInt(value.slice(2), 16) : parseInt(value.slice(1), 10)) : entities[value]);
}
const chunks = {};
for (const [name, markup] of Object.entries(pages)) {
  const text = markup.split(/<[^>]+>/);
  const attrs = Array.from(markup.matchAll(/\b(?:aria-label|alt|title|placeholder)="([^"]*)"/g), m => m[1]);
  chunks[name] = text.concat(attrs).map(decode).filter(s => /[֐-׿]/.test(s)).map(s => [s, S.i18n.t(s)]);
}
const title = /<h1 id="live-pull-guide-title">([^<]+)<\/h1>/.exec(pages.live)[1];
process.stdout.write(JSON.stringify({chunks, title: S.i18n.t(decode(title))}));
'''
        out = json.loads(subprocess.run(['node', '-e', script], check=True,
                                        capture_output=True, text=True).stdout)
        self.assertEqual(len(out['chunks']), 8)
        for page, chunks in out['chunks'].items():
            self.assertTrue(chunks, page)
            for source, translated in chunks:
                with self.subTest(page=page, source=source):
                    self.assertNotRegex(translated, HEBREW)
        self.assertEqual(out['title'], 'Automatic data refresh in Excel')


class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = (ROOT / "assets/statso-i18n.js").read_text(encoding="utf-8")
        cls.html = (ROOT / "index.html").read_text(encoding="utf-8")

    def test_language_is_remembered_and_shareable(self):
        self.assertIn("localStorage.setItem(STORAGE_KEY", self.engine)
        self.assertIn("params.get('lang')", self.engine)
        self.assertIn("url.searchParams.set('lang', 'en')", self.engine)

    def test_switching_flips_direction(self):
        self.assertIn("html.setAttribute('dir', lang === 'he' ? 'rtl' : 'ltr')", self.engine)

    def test_dynamic_content_is_covered_by_an_observer(self):
        self.assertIn("MutationObserver", self.engine)
        self.assertIn("characterData: true", self.engine)

    def test_the_language_picker_sits_beside_the_brand(self):
        group = re.search(r'<div class="brand-group">.*?</div>\s*</div>', self.html, re.DOTALL).group(0)
        self.assertIn('id="lang-picker"', group)
        self.assertIn("data-i18n-skip", group)
        self.assertIn('class="brand"', group)
        self.assertLess(group.index('class="brand"'), group.index("lang-picker"),
                        "brand first, so in RTL statso sits on the right and the picker to its left")
        for choice in ('data-lang-choice="he"', 'data-lang-choice="en"'):
            self.assertIn(choice, group)
        self.assertIn(">Switch Language<", group)
        self.assertIn("node.hasAttribute('data-i18n-skip')", self.engine)

    def test_the_picker_opens_a_menu_and_closes_again(self):
        self.assertIn("aria-expanded", self.engine)
        self.assertIn("function closeMenu()", self.engine)
        self.assertIn("event.key === 'Escape'", self.engine)

    def test_exports_follow_the_language(self):
        xlsx = (ROOT / "assets/statso-xlsx.js").read_text(encoding="utf-8")
        self.assertIn("Statso.i18n ? Statso.i18n.t(text) : text", xlsx)
        self.assertIn("escapeXml(say(value))", xlsx)
        export = (ROOT / "assets/statso-export.js").read_text(encoding="utf-8")
        self.assertLess(export.index("Statso.i18n.apply(container)"), export.index("root.print();"))

    def test_guides_show_only_the_site_language_excel(self):
        guides = (ROOT / "assets/statso-guides.js").read_text(encoding="utf-8")
        self.assertIn("function artSlots(step, number)", guides)
        block = guides.split("function artSlots(step, number)")[1].split("function renderSteps()")[0]
        self.assertIn("if (site === 'en') { return artSlot(step, 'en', number); }", block)
        self.assertIn("return artSlot(step, 'he', number);", block)
        # neither site draws the other language's Excel: no he+en pair, no per-guide exception
        self.assertNotIn("artSlot(step, 'he', number) + artSlot(step, 'en', number)", guides)
        self.assertNotIn("realShotGuide", guides)
        # the step markup must go through the chooser, never call either language directly
        steps = guides.split("function renderSteps()")[1]
        self.assertIn("artSlots(step, number)", steps)
        self.assertNotIn("artSlot(step, 'he'", steps)
        self.assertNotIn("artSlot(step, 'en'", steps)

    def test_an_open_guide_is_rebuilt_when_the_language_changes(self):
        guides = (ROOT / "assets/statso-guides.js").read_text(encoding="utf-8")
        self.assertIn("currentGuide = guideId", guides)
        self.assertIn("Statso.i18n.onChange", guides)
        self.assertIn("renderGuide(currentGuide)", guides)

    def test_the_header_stays_reachable_on_every_page(self):
        css = (ROOT / "assets/statso.css").read_text(encoding="utf-8")
        header = re.search(r"\.site-header \{[^}]*\}", css).group(0)
        self.assertIn("position: sticky", header)
        self.assertIn("inset-block-start: 0", header)


if __name__ == "__main__":
    unittest.main()
