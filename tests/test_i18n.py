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
        self.assertEqual(html.count('data-lang="he"'), 3)


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

    def test_the_toggle_is_in_the_nav_and_excluded_from_translation(self):
        nav = re.search(r'<nav class="site-nav".*?</nav>', self.html, re.DOTALL).group(0)
        self.assertIn('id="lang-toggle"', nav)
        self.assertIn("data-i18n-skip", nav)
        self.assertIn("node.hasAttribute('data-i18n-skip')", self.engine)

    def test_exports_follow_the_language(self):
        xlsx = (ROOT / "assets/statso-xlsx.js").read_text(encoding="utf-8")
        self.assertIn("Statso.i18n ? Statso.i18n.t(text) : text", xlsx)
        self.assertIn("escapeXml(say(value))", xlsx)
        export = (ROOT / "assets/statso-export.js").read_text(encoding="utf-8")
        self.assertLess(export.index("Statso.i18n.apply(container)"), export.index("root.print();"))

    def test_the_header_stays_reachable_on_every_page(self):
        css = (ROOT / "assets/statso.css").read_text(encoding="utf-8")
        header = re.search(r"\.site-header \{[^}]*\}", css).group(0)
        self.assertIn("position: sticky", header)
        self.assertIn("inset-block-start: 0", header)


if __name__ == "__main__":
    unittest.main()
