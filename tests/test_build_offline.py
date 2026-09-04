import base64
import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path

from scripts.build_offline import build, default_output_path, escape_json_for_html
from scripts.common import StatsoError

ROOT = Path(__file__).parent.parent


class BuildOfflineTests(unittest.TestCase):
    def setUp(self):
        self.html = (ROOT / "index.html").read_text(encoding="utf-8")

    def test_vendored_chartjs_matches_pinned_sri(self):
        payload = (ROOT / "assets/vendor/chart-4.5.1.umd.min.js").read_bytes()
        integrity = re.search(r'integrity="sha384-([^"]+)"', self.html).group(1)
        self.assertEqual(base64.b64encode(hashlib.sha384(payload).digest()).decode(), integrity)
        self.assertEqual(len(payload), 208522); self.assertNotIn(b"\r", payload)

    def test_markers_present_and_unique(self):
        self.assertEqual(self.html.count('data-inline="style"'), 1)
        self.assertEqual(self.html.count('data-inline="script"'), 7)
        self.assertEqual(self.html.count('data-inline="json"'), 3)
        self.assertEqual(set(re.findall(r'data-src="([^"]+)"', self.html)),
                         {"data/cpi.json", "data/boi_interest_rate.json", "data/boi_next_decision.json"})

    def test_cdn_tag_contract(self):
        self.assertIn("https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.5.1/chart.umd.min.js", self.html)
        self.assertIn('integrity="sha384-jb8JQMbMoBUzgWatfe6COACi2ljcDdZQ2OxczGA3bGNeWe+6DChMTBJemed7ZnvJ"', self.html)
        self.assertIn('crossorigin="anonymous"', self.html)

    def test_escape_json_for_html(self):
        source = '{"a":"</script><!-- --> \u2028 \u2029 & <b>"}'
        escaped = escape_json_for_html(source)
        for unsafe in ("<", ">", "\u2028", "\u2029"): self.assertNotIn(unsafe, escaped)
        self.assertIn("&", escaped); self.assertEqual(json.loads(escaped), json.loads(source))

    def test_artifact_structure(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "statso.html"; build(out=out); payload = out.read_bytes(); text = payload.decode()
            self.assertTrue(text.startswith("<!DOCTYPE html>")); self.assertIn('lang="he"', text); self.assertIn('dir="rtl"', text)
            self.assertIn("Chart.js v4.5.1", text)
            for absent in ("cdnjs.cloudflare.com", "integrity=", 'src="assets/', 'href="assets/', "http://"): self.assertNotIn(absent, text)
            self.assertFalse(payload.startswith(b"\xef\xbb\xbf")); self.assertNotIn(b"\r", payload)
            self.assertEqual(text.count("<script"), text.count("</script>"))

    def test_artifact_json_roundtrip(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "statso.html"; build(out=out); text = out.read_text(encoding="utf-8")
            for element, relative in (("data-cpi", "data/cpi.json"), ("data-boi", "data/boi_interest_rate.json"), ("data-next", "data/boi_next_decision.json")):
                content = re.search(r'<script[^>]*id="' + element + r'"[^>]*>(.*?)</script>', text, re.DOTALL).group(1)
                self.assertEqual(json.loads(content), json.loads((ROOT / relative).read_text(encoding="utf-8")))

    def test_artifact_deterministic(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "statso.html"; self.assertTrue(build(out=out)); first = out.read_bytes()
            self.assertFalse(build(out=out)); self.assertEqual(out.read_bytes(), first)

    def test_missing_marker_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "index.html"; out = Path(temp) / "out.html"
            source.write_text(re.sub(r'<script[^>]*chart\.umd\.min\.js[^>]*>\s*</script>', '', self.html), encoding="utf-8")
            with self.assertRaises(StatsoError): build(out=out, source=source)
            self.assertFalse(out.exists())

    def test_version_stamp(self):
        version = (ROOT / "VERSION").read_text().strip()
        self.assertRegex(version, r"^\d+\.\d+\.\d+$")
        self.assertRegex(self.html, r'id="app-version"[^>]*>\s*' + re.escape(version))
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "statso.html"; build(out=out); self.assertIn(version, out.read_text(encoding="utf-8"))

    def test_default_output_path(self):
        self.assertEqual(default_output_path(), Path.home() / "Desktop" / "statso-test.html")


if __name__ == "__main__": unittest.main()
