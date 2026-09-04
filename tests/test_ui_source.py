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


if __name__ == "__main__": unittest.main()
