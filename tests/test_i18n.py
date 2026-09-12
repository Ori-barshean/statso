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
        for text in ('בחר מקור נתונים', 'שאילתה ריקה', 'טקסט/CSV', 'עורך מתקדם', 'קבע תצורה של חיבור', 'אישורים לא חוקיים או חסרים', 'סגור וטען', 'שליפת נתונים חיה — בקרוב'):
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

    def test_guides_show_one_screenshot_in_english(self):
        guides = (ROOT / "assets/statso-guides.js").read_text(encoding="utf-8")
        self.assertIn("function artSlots(step, number)", guides)
        block = guides.split("function artSlots(step, number)")[1].split("function renderSteps()")[0]
        self.assertIn("if (site === 'en') { return artSlot(step, 'en', number); }", block)
        self.assertIn("artSlot(step, 'he', number) + artSlot(step, 'en', number)", block)
        # the step markup must go through the chooser, never call both directly
        steps = guides.split("function renderSteps()")[1]
        self.assertIn("artSlots(step, number)", steps)
        self.assertNotIn("artSlot(step, 'he'", steps)

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
