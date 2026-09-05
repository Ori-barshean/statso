import re
import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent


class GuidesSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "index.html").read_text(encoding="utf-8")
        cls.guides = (ROOT / "assets/statso-guides.js").read_text(encoding="utf-8")
        cls.art = (ROOT / "assets/statso-guide-art.js").read_text(encoding="utf-8")

    def test_routes_and_accessible_selectors(self):
        self.assertIn('href="#/"', self.html)
        self.assertIn('href="#/guides"', self.html)
        self.assertIn('aria-label="דף הבית"', self.html)
        self.assertIn("<fieldset><legend>", self.guides)
        self.assertIn('type="radio"', self.guides)

    def test_exact_dataset_urls(self):
        found = set(re.findall(r"https://raw\.githubusercontent\.com/Ori-barshean/statso/main/data/[a-z0-9_]+\.(?:csv|json)", self.guides))
        self.assertEqual(found, {
            "https://raw.githubusercontent.com/Ori-barshean/statso/main/data/boi_interest_rate.csv",
            "https://raw.githubusercontent.com/Ori-barshean/statso/main/data/boi_interest_rate.json",
            "https://raw.githubusercontent.com/Ori-barshean/statso/main/data/cpi.csv",
            "https://raw.githubusercontent.com/Ori-barshean/statso/main/data/cpi.json",
            "https://raw.githubusercontent.com/Ori-barshean/statso/main/data/boi_next_decision.json",
        })

    def test_mac_webservice_has_no_steps(self):
        self.assertIn("if (platform === 'mac') { return []; }", self.guides)
        self.assertIn("state.platform === 'mac' && state.method === 'webservice'", self.guides)
        self.assertIn("WEBSERVICE אינה זמינה ב-Excel for Mac", self.guides)

    def test_all_art_archetypes(self):
        for name in ("ribbon-data", "menu-getdata", "dialog-fromweb", "dialog-navigator",
                     "sheet-loaded", "ribbon-refresh", "browser-save", "dialog-open-file", "cell-formula"):
            self.assertIn(name, self.art)
        self.assertIn("source.img", self.guides)
        self.assertIn("rtl-art", self.art)

    def test_cell_formula_art_does_not_double_escape_quotes(self):
        script = """
global.window = {};
require(%s);
const svg = window.Statso.guideArt.render('cell-formula', {
  lang: 'en', platform: 'win', dataset: 'boi', step: 1,
  url: 'https://example.test/data.json'
});
process.stdout.write(svg);
""" % json.dumps(str(ROOT / "assets/statso-guide-art.js"))
        svg = subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True
        ).stdout
        self.assertNotIn("&amp;quot;", svg)
        self.assertIn('=WEBSERVICE(&quot;https://example.test/data.json&quot;)', svg)


if __name__ == "__main__":
    unittest.main()
