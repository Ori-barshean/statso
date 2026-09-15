import re
import json
import subprocess
import struct
import html
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
                     "dialog-choose-source", "editor-advanced", "dialog-credentials",
                     "sheet-loaded", "ribbon-refresh", "browser-save", "dialog-open-file", "cell-formula"):
            self.assertIn(name, self.art)
        self.assertIn("rtl-art", self.art)

    def test_mac_power_steps_render_screenshots_and_code(self):
        script = """
global.window = {};
const host = {innerHTML: ''};
const stub = {setAttribute() {}, addEventListener() {}, innerHTML: ''};
global.document = {addEventListener() {}, getElementById() { return stub; },
  querySelector(s) { return s === '.guide-steps-host' ? host : stub; }, querySelectorAll() { return []; }};
require(%s);
require(%s);
require(%s);
require(%s);
const S = window.Statso, out = {variants: {}};
for (const site of ['he', 'en']) {
  S.i18n = {current: () => site, onChange() {}};
  for (const platform of ['mac', 'win']) {
    Object.assign(S.guides.state, {platform, method: 'power'});
    S.guides.renderExcelGuide();
    out[site + '/' + platform] = host.innerHTML;
    for (const method of ['power', 'manual', 'webservice']) {
      S.guides.state.method = method;
      S.guides.renderExcelGuide();
      out.variants[[site, platform, method].join('/')] = {header: stub.innerHTML, steps: host.innerHTML};
    }
  }
}
out.shots = S.guides.getSteps('mac', 'power').filter(s => s.shots).map(s => s.shots.he);
out.shot = S.guides.getSteps('mac', 'power')[0].shots.he;
out.win = S.guides.getSteps('win', 'power')[0];
out.winShots = S.guides.getSteps('win', 'power')
  .filter(s => s.shots)
  .flatMap(s => Array.isArray(s.shots.he) ? s.shots.he : [s.shots.he]);
out.code = S.mcode.generate({series: 'boi', currencies: [], from: '2022-12-01', to: '2025-12-31', average: false});
S.i18n = {current: () => 'he', onChange() {}};
Object.assign(S.guides.state, {platform: 'mac', method: 'manual'});
S.guides.renderExcelGuide();
out.manual = host.innerHTML;
process.stdout.write(JSON.stringify(out));
""" % tuple(json.dumps(str(ROOT / "assets" / name)) for name in
            ("statso-core.js", "statso-guide-art.js", "statso-guides.js", "statso-mcode.js"))
        out = json.loads(subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True, encoding="utf-8"
        ).stdout)
        new_text = 'פותחים חוברת עבודה חדשה, עוברים ללשונית Data / ״נתונים״ ולוחצים על ״יבא נתונים (Power Query)״.'
        alt = 'אקסל למק בעברית: לשונית נתונים והכפתור ״יבא נתונים (Power Query)״.'
        win_text = ('פותחים חוברת עבודה חדשה ועוברים ללשונית ״נתונים״ (Data). לוחצים על ״יבא נתונים״ (Get Data), '
                     'ואז על ״יבא נתונים (תצוגה מקדימה)״ (Get Data (Preview)).')

        def steps(key):
            return re.findall(r"<li>(.*?)</li>", out[key], re.S)

        def figures(step):
            return re.findall(r"<figure>.*?</figure>", step, re.S)

        mac = steps("he/mac")
        self.assertEqual(len(mac), 6)
        self.assertIn(new_text, mac[0])
        pair = figures(mac[0])
        self.assertEqual(len(pair), 1)
        shot = pair[0]
        for expected in ('<img src="assets/images/excel-mac-power-query-he.png"', f'alt="{alt}"',
                         'class="guide-shot-arrow"', 'viewBox="0 0 542 260"',
                         'points="386,212 366.2,229.4 359.9,208.7"'):
            self.assertIn(expected, shot)
        for absent in ("guide-svg", ' id="', "<marker"):
            self.assertNotIn(absent, shot)
        for step in (mac[0], mac[1], mac[3], mac[4], mac[5]):
            self.assertEqual(len(figures(step)), 1)
            self.assertIn('class="step-art step-art-single"', step)
            self.assertNotIn('אקסל באנגלית', step)
        for page in ('he/mac', 'en/mac'):
            third = steps(page)[2]
            self.assertEqual(figures(third), [])
            for absent in ('<img', 'guide-real-shot', 'step-art', '<svg'):
                self.assertNotIn(absent, third)
            paragraph = ('<p>בעורך Power Query לוחצים על ״עורך מתקדם״ (Advanced Editor), '
                         'מוחקים את כל מה שכתוב שם, מדביקים במקומו קוד מתוך '
                         '<a class="guide-pill" href="#/mcode">קודים לייצוא (Power Query)</a>'
                         ', ולוחצים אישור/הבא.</p>')
            example = '<p>הקוד שלהלן הוא דוגמה מוכנה לריבית בנק ישראל לטווח 2022-12-01 עד 2025-12-31.</p>'
            self.assertIn(paragraph + example + '<div class="code-block"><button class="copy-url guide-copy-pill" '
                          'type="button">העתקת הקוד</button><pre dir="ltr" data-i18n-skip><code>', third)
            self.assertIn('</code></pre></div><div class="guide-mcode-cta">', third)
            cta = re.search(r'<div class="guide-mcode-cta">(.*?)</div>', third, re.S).group(1)
            self.assertEqual(cta.count('<p>'), 1)
            self.assertNotIn('<a', cta)
            self.assertNotIn('<button', cta)
            self.assertNotIn('guide-mcode-button', third)

        self.assertIn('class="code-block"', mac[2])
        self.assertIn('<pre dir="ltr" data-i18n-skip>', mac[2])
        rendered_code = re.search(r'<pre[^>]*><code>(.*?)</code></pre>', mac[2], re.S).group(1)
        self.assertEqual(html.unescape(rendered_code), out['code'])
        self.assertEqual(out['he/mac'].count('href="#/mcode"'), 1)
        self.assertNotIn('<aside', out['he/mac'])
        self.assertIn('הקוד שלהלן הוא דוגמה מוכנה לריבית בנק ישראל לטווח 2022-12-01 עד 2025-12-31.', mac[2])
        for text in ('כל סדרה, טווח תאריכים והשוואה שהאתר מציע', 'להוסיף שורת ממוצע', 'קוד M מוכן להעתקה'):
            self.assertIn(text, mac[2])
        for name in ('Power Query', 'Choose data source', 'Blank Query', 'Advanced Editor',
                     'Configure connection', 'Anonymous', 'Close & Load', 'Refresh All'):
            self.assertIn('(' + name + ')', out['he/mac'])
        self.assertNotIn('Choose a data source', out['he/mac'])
        self.assertNotIn('״טקסט/CSV״ פותח קובץ מהמחשב', out['he/mac'])
        self.assertNotIn('OData דורש שירות OData', out['he/mac'])
        self.assertIn('assets/images/excel-mac-blank-query-he.png', mac[1])
        self.assertIn('assets/images/excel-mac-refresh-all-he.png', mac[5])
        self.assertNotIn("Get Data ← From Web", out["he/mac"])
        for index, shot in zip((0, 1, 3, 4, 5), out["shots"]):
            self.assertEqual(mac[index].count("<img "), 1)
            self.assertIn('src="' + shot["src"] + '"', mac[index])
            self.assertIn('alt="' + shot["alt"] + '"', mac[index])
            if index in (0, 1, 5):
                self.assertIn('guide-shot-arrow', mac[index])
                arrow = shot['arrow']
                distance = sum((a - b) ** 2 for a, b in zip(arrow['to'], arrow['c2'])) ** .5
                self.assertGreater(distance, arrow['head'])
            else:
                self.assertNotIn("arrow", shot)
                self.assertNotIn("guide-shot-arrow", mac[index])

        # the Windows Power Query guide (Hebrew) now uses real screenshots too,
        # laid out as 7 steps: single real photo per step, except step 4 (paste
        # code) which carries two arrows on one photo, and step 5 (credentials)
        # which shows two sequential real photos (the banner, then Anonymous/Connect).
        win = steps("he/win")
        self.assertEqual(len(win), 7)
        self.assertIn(win_text, win[0])
        for index in (0, 1, 2, 5, 6):
            figs = figures(win[index])
            self.assertEqual(len(figs), 1)
            self.assertIn('class="step-art step-art-single"', win[index])
            self.assertNotIn('אקסל באנגלית', win[index])
            self.assertIn('class="guide-shot-arrow"', figs[0])
            for absent in ('guide-svg', ' id="', '<marker'):
                self.assertNotIn(absent, figs[0])
        self.assertIn('assets/images/excel-win-get-data-he.png', win[0])
        self.assertIn('assets/images/excel-win-blank-query-he.png', win[1])
        self.assertIn('assets/images/excel-win-advanced-editor-he.png', win[2])
        self.assertIn('assets/images/excel-win-close-load-he.png', win[5])
        self.assertIn('assets/images/excel-win-refresh-all-he.png', win[6])
        # step 4: one photo, two arrow overlays (code box + Done button)
        paste = figures(win[3])
        self.assertEqual(len(paste), 1)
        self.assertIn('assets/images/excel-win-paste-code-he.png', win[3])
        self.assertEqual(win[3].count('<polygon'), 2)
        self.assertIn('class="code-block"', win[3])
        self.assertIn('href="#/mcode"', win[3])
        # step 5: two sequential real photos (banner, then Anonymous/Connect)
        creds = figures(win[4])
        self.assertEqual(len(creds), 2)
        self.assertIn('assets/images/excel-win-credentials-he.png', win[4])
        self.assertIn('assets/images/excel-win-credentials-anonymous-he.png', win[4])
        self.assertEqual(win[4].count('class="guide-shot-arrow"'), 2)
        self.assertEqual(figures(win[4])[1].count('<polygon'), 2)  # anonymous + connect

        # the English site never shows the Hebrew real screenshots
        for page in ("en/mac", "en/win"):
            self.assertNotIn("<img", out[page])
            self.assertNotIn("guide-real-shot", out[page])
        for page in ("en/mac", "en/win"):
            for index, step in enumerate(steps(page)):
                only = figures(step)
                if (page == 'en/mac' and index == 2) or (page == 'en/win' and index == 3):
                    self.assertEqual(only, [])
                    self.assertNotIn('step-art', step)
                    continue
                self.assertEqual(len(only), 1)
                self.assertIn('class="guide-svg', only[0])

        for variant, rendered in out['variants'].items():
            with self.subTest(variant=variant):
                self.assertEqual(rendered['header'].count('<fieldset>'), 2)
                self.assertEqual(set(re.findall(r'name="guide-([^"]+)"', rendered['header'])),
                                 {'platform', 'method'})
                self.assertNotIn('guide-dataset', rendered['header'])
                self.assertIn('בחרו את סביבת העבודה ושיטת הייבוא, והשלבים יתעדכנו מיד.', rendered['header'])
                urls = set(re.findall(r'https://raw\.githubusercontent\.com/Ori-barshean/statso/main/data/[^\s<"&]+',
                                      rendered['steps']))
                self.assertFalse(any('cpi.csv' in url or 'cpi.json' in url for url in urls))
                self.assertTrue(all(url.rsplit('/', 1)[1] in
                                    {'boi_interest_rate.csv', 'boi_interest_rate.json', 'boi_next_decision.json'}
                                    for url in urls))
                if '/manual' in variant or variant.endswith('win/power'):
                    self.assertTrue(any(url.endswith('boi_interest_rate.csv') for url in urls))
                if variant.endswith('win/webservice'):
                    self.assertTrue(any(url.endswith('boi_interest_rate.json') for url in urls))

        self.assertEqual(out["win"]["text"], win_text)
        self.assertEqual(out["win"]["art"], "ribbon-data")
        self.assertEqual(out["win"]["shots"]["he"]["src"], "assets/images/excel-win-get-data-he.png")
        self.assertEqual(len(out["shots"]), 5)
        self.assertNotIn('step-art-single', out['manual'])
        self.assertNotIn('href="#/mcode"', out['manual'])
        for step in steps('manual'):
            self.assertEqual(len(figures(step)), 2)
        for shot in out["shots"] + out["winShots"]:
            with (ROOT / shot["src"]).open("rb") as handle:
                self.assertEqual(handle.read(8), b"\x89PNG\r\n\x1a\n")
                length = struct.unpack(">I", handle.read(4))[0]
                self.assertEqual(handle.read(4), b"IHDR")
                width, height = struct.unpack(">II", handle.read(length)[:8])
            self.assertEqual((width, height), (shot["width"], shot["height"]))

    def test_single_hebrew_column_is_only_for_mac_or_win_power(self):
        predicate = self.guides.split('function realShotGuide() {')[1].split('\n  }')[0]
        self.assertIn("Statso.i18n ? Statso.i18n.current() : 'he'", predicate)
        self.assertIn(
            "return site === 'he' && state.method === 'power' && (state.platform === 'mac' || state.platform === 'win');",
            predicate)
        self.assertIn("if (realShotGuide()) { return artSlot(step, 'he', number); }", self.guides)

    def test_second_guide_and_id_dispatch(self):
        self.assertIn("id: 'cpi-terms'", self.guides)
        self.assertIn("guideId === 'cpi-terms'", self.guides)
        self.assertIn("eventOrId.currentTarget.dataset.guide", self.guides)
        self.assertIn("data-cpi-live-example", self.guides)
        self.assertIn("Statso.data.loadDataset(source)", self.guides)
        self.assertIn("לא ניתן להציג דוגמה מהנתונים כרגע", self.guides)

    def test_timeline_art_is_non_empty_and_not_double_escaped(self):
        script = """
global.window = {};
require(%s);
const svg = window.Statso.guideArt.render('timeline-publication', {lang: 'he', platform: 'win'});
process.stdout.write(svg);
""" % json.dumps(str(ROOT / "assets/statso-guide-art.js"))
        svg = subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True
        ).stdout
        self.assertIn("פרסום מדד בגין X", svg)
        self.assertIn("מדד ידוע = מדד X-1", svg)
        self.assertNotIn("&amp;quot;", svg)
        self.assertGreater(len(svg), 1000)

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
