import re
import json
import subprocess
import struct
import html
from html.parser import HTMLParser
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent


APPROVED_REFRESH_TEXT = [
    ('מעבר ל-Power Query', 'Switch to Power Query'),
    ('שאיבת נתונים מ-statso לתוך Excel', 'Pulling statso data into Excel'),
    ('קודים לייצוא (Power Query)', 'Export code (Power Query)'),
    ('למה Power Query?',
     'Why Power Query?'),
    ('Power Query היא השיטה היחידה כאן שאפשר להגדיר בה רענון אוטומטי: הקובץ יכול להתרענן בכל פתיחה או כל כמה דקות, וריבית או מדד חדשים נכנסים לטבלה בלי להוריד שוב כלום. זה עובד כשההרשאות מאפשרות זאת — אקסל צריך חיבור לאינטרנט, וחיבורי נתונים חיצוניים לא יכולים להיות חסומים (למשל במדיניות ארגונית או בקובץ שנפתח בתצוגה מוגנת).',
     "Power Query is the only method here where you can set up automatic refresh: the file can refresh every time it opens or every few minutes, and a new rate or index reading enters the table without downloading anything again. This works when the permissions allow it — Excel needs an internet connection, and external data connections must not be blocked (for example by an organization's policy, or in a file opened in Protected View)."),
    ('רענון אוטומטי של הנתונים ב-Excel',
     'Automatic data refresh in Excel'),
    ('בהורדה ידנית הנתונים קפואים ברגע ההורדה ואינם מתעדכנים. ב-Power Query אפשר להגדיר שאקסל ישאב אותם מחדש לבד, בכל פתיחה של הקובץ או כל כמה דקות, אם ההרשאות מאפשרות זאת.',
     'A manual download freezes the data at the moment you download it, and it never updates. With Power Query you can set Excel to pull it again on its own, every time the file opens or every few minutes, if the permissions allow it.'),
    ('נוסחת WEBSERVICE אינה כוללת הגדרת רענון אוטומטי, ומתאימה רק לערך בודד. ב-Power Query אפשר לשאוב טבלה שלמה ולהגדיר שאקסל ירענן אותה לבד, בכל פתיחה של הקובץ או כל כמה דקות, אם ההרשאות מאפשרות זאת.',
     'The WEBSERVICE formula has no automatic-refresh setting and suits a single value only. With Power Query you can pull a whole table and set Excel to refresh it on its own, every time the file opens or every few minutes, if the permissions allow it.'),
    ('אחרי שאיבת הנתונים עם Power Query: כך מגדירים שהקובץ יתרענן בפתיחה או כל כמה דקות, וימשיך להוסיף ריבית ומדד חדשים.',
     'After pulling data with Power Query: how to set the file to refresh on opening or every few minutes and keep adding new rate and index readings.'),
    ('מדריך המשך',
     'Follow-up guide'),
    ('אחרי ששאבתם נתונים עם Power Query, אפשר להגדיר שהקובץ יתעדכן לבד וימשיך להוסיף ריבית ומדד חדשים.',
     'Once you have pulled data with Power Query, you can set the file to update itself and keep adding new rate and index readings.'),
    ('שלב 1: בוחרים תאריך סיום רחוק',
     'Step 1: Choose a far-off end date'),
    ('כדי שהטבלה תמשיך לגדול, בוחרים תאריך סיום רחוק, למשל 31.12.2099, ומעתיקים את הקוד. לא מסמנים ״להוסיף שורת ממוצע בסוף הטבלה״, כדי שהשורה האחרונה בטבלה תהיה תמיד הנתון האחרון.',
     'To keep the table growing, choose a far-off end date, for example 31.12.2099, and copy the code. Leave "Add an average row at the end of the table" unchecked, so the last row of the table is always the latest reading.'),
    ('אם כבר הדבקתם קוד בקובץ: בעורך Power Query פותחים ״עורך מתקדם״ (Advanced Editor) ומחליפים את תאריך הסיום בשורות הראשונות של הקוד, מתחת ל-let:',
     'If you already pasted code into the file: in the Power Query editor open "Advanced Editor" and replace the end date in the first lines of the code, below let:'),
    ('שלב 2: פותחים את מאפייני השאילתה',
     'Step 2: Open the query properties'),
    ('בלשונית ״נתונים״ (Data) לוחצים על ״שאילתות & חיבורים״ (Queries & Connections). חלונית נפתחת בצד הגיליון.',
     'In the "Data" tab, click "Queries & Connections". A pane opens beside the sheet.'),
    ('לוחצים לחיצה ימנית על שם השאילתה ובוחרים ״מאפיינים״ (Properties).',
     'Right-click the query name and choose "Properties".'),
    ('נפתח החלון ״מאפייני שאילתה״ (Query Properties). בלשונית ״שימוש״ (Usage), בקבוצה ״בקרת רענון״ (Refresh control), נמצאות האפשרויות של השלב הבא.',
     'The "Query Properties" window opens. In the "Usage" tab, in the "Refresh control" group, you will find the options for the next step.'),
    ('ב-Excel למק לא בדקנו את החלון הזה: ייתכן שחלק מהאפשרויות חסרות בו או נראות אחרת. אם אינן מופיעות אצלכם, ממשיכים לרענן ידנית באמצעות ״רענן את הכל״ (Refresh All).',
     'We have not tested this window in Excel for Mac: some options may be missing or look different. If they do not appear for you, keep refreshing manually with "Refresh All".'),
    ('שלב 3: בוחרים מתי להתרענן',
     'Step 3: Choose when to refresh'),
    ('בקבוצה ״בקרת רענון״ מסמנים את מה שמתאים לכם:',
     'In the "Refresh control" group, tick what suits you:'),
    ('״רענון נתונים בעת פתיחת הקובץ״ (Refresh data when opening the file): אקסל שואב נתונים חדשים בכל פעם שפותחים את הקובץ. זו הבחירה הנוחה לרוב המשתמשים.',
     '"Refresh data when opening the file": Excel pulls new data every time the file is opened. This is the convenient choice for most people.'),
    ('״רענן כל n דקות״ (Refresh every n minutes): אקסל שואב מחדש כל כמה דקות, אבל רק כל עוד הקובץ פתוח. מתאים לקובץ שנשאר פתוח כל היום. הנתונים באתר מתעדכנים פעם בלילה, ולכן אין צורך במרווח קצר; 60 דקות ומעלה מספיקים.',
     '"Refresh every n minutes": Excel pulls again every few minutes, but only while the file is open. It suits a file that stays open all day. The data on the site updates once a night, so a short interval is not needed; 60 minutes or more is enough.'),
    ('״הפיכת רענון רקע לזמין״ (Enable background refresh): מאפשר להמשיך לעבוד באקסל בזמן הרענון. אפשר להשאיר מסומן.',
     '"Enable background refresh": lets you keep working in Excel while it refreshes. You can leave it ticked.'),
    ('לוחצים ״אישור״ (OK) ושומרים את הקובץ.',
     'Click "OK" and save the file.'),
    ('שלב 4: מאשרים לאקסל להתחבר כשהקובץ נפתח',
     'Step 4: Let Excel connect when the file opens'),
    ('אקסל חוסם חיבורי נתונים חיצוניים בקבצים שאינו סומך עליהם, למשל קבצים שהורדו מהאינטרנט או נשלחו במייל, ובלי אישור הרענון בפתיחה לא יתבצע.',
     'Excel blocks external data connections in files it does not trust, for example files downloaded from the internet or received by email, and without your approval the refresh on opening will not happen.'),
    ('אם מופיע פס ״תצוגה מוגנת״ (Protected View), לוחצים ״אפשר עריכה״ (Enable Editing).',
     'If a "Protected View" bar appears, click "Enable Editing".'),
    ('אם מופיע פס אזהרה על חיבורי נתונים חיצוניים, לוחצים ״הפעל תוכן״ (Enable Content).',
     'If a warning bar about external data connections appears, click "Enable Content".'),
    ('אם הארגון שלכם חוסם חיבורי נתונים חיצוניים, ההגדרה לא תעבוד, ויש לפנות למנהל המערכת.',
     'If your organization blocks external data connections, the setting will not work, and you need to contact your system administrator.'),
    ('שלב 5: בודקים שהרענון עובד',
     'Step 5: Check that the refresh works'),
    ('סוגרים את הקובץ ופותחים אותו שוב (אם בחרתם רענון בפתיחה).',
     'Close the file and open it again (if you chose refresh on opening).'),
    ('ממתינים כמה שניות עד שהרענון מסתיים.',
     'Wait a few seconds for the refresh to finish.'),
    ('בודקים את השורה האחרונה בטבלה: בריבית זה השינוי האחרון בריבית, ובמדד זה החודש האחרון שפורסם.',
     'Check the last row of the table: for the interest rate it is the latest change in the rate, and for the index it is the latest month published.'),
    ('שלב 6: מה קורה כשמתווסף נתון חדש',
     'Step 6: What happens when a new reading is added'),
    ('כשהאתר מוסיף נתון חדש, הרענון הבא מוסיף אותו בסוף הטבלה, והטבלה מתארכת מעצמה. הנתונים באתר מתעדכנים כל לילה ב-02:00 שעון ישראל, אבל נתון חדש מגיע אליהם רק אחרי שהלמ״ס או בנק ישראל פרסמו אותו, ולכן אין טעם לרענן בתדירות גבוהה מפעם ביום.',
     'When the site adds a new reading, the next refresh adds it at the end of the table, and the table grows by itself. The data on the site updates every night at 02:00 Israel time, but a new reading reaches it only after the CBS or the Bank of Israel has published it, so there is no point refreshing more than once a day.'),
    ('נוסחאות שמפנות לטבלה לפי שם העמודה (Structured References), ותרשימים שמבוססים על הטבלה, כוללים את השורות החדשות אוטומטית. טווח תאים קבוע לא יכלול אותן.',
     'Formulas that refer to the table by column name (Structured References), and charts based on the table, include the new rows automatically. A fixed cell range will not include them.'),
    ('לא שמים נתונים או חישובים ישירות מתחת לטבלה: שם היא תמשיך להתארך.',
     'Do not put data or calculations directly below the table: it keeps growing there.'),
    ('אקסל מרענן רק כשהקובץ פתוח. אם הוא סגור, הנתונים החדשים ייכנסו בפעם הבאה שתפתחו אותו (אם בחרתם רענון בפתיחה).',
     'Excel refreshes only while the file is open. If it is closed, the new data enters the next time you open it (if you chose refresh on opening).'),
    ('אם משהו לא מתעדכן',
     'If something does not update'),
    ('הטבלה לא התארכה: בדקו שתאריך הסיום בקוד רחוק (שלב 1).',
     'The table did not grow: check that the end date in the code is far off (step 1).'),
    ('הרענון לא התחיל: ודאו שיש חיבור לאינטרנט ושאישרתם את הפסים בראש החוברת (שלב 4).',
     'The refresh did not start: make sure you have an internet connection and that you approved the bars at the top of the workbook (step 4).'),
    ('מופיעה הודעה על אישורים: בוחרים ״אנונימי״ (Anonymous), כמו בשלב החיבור במדריך הראשון.',
     'A message about credentials appears: choose "Anonymous", as in the connection step of the first guide.'),
    ('הנתון החדש עדיין לא הגיע: ייתכן שהוא טרם פורסם, או שהאתר טרם התעדכן בלילה. נסו שוב למחרת.',
     'The new reading has not arrived yet: it may not have been published yet, or the site may not have updated overnight yet. Try again the next day.'),
    ('בהורדה ידנית של CSV ובנוסחת WEBSERVICE אין הגדרה כזו. להגדרת הרענון האוטומטי:',
     'A manual CSV download and the WEBSERVICE formula have no such setting. To set up automatic refresh:'),
    ('זה המשך של המדריך',
     'This continues the guide'),
    ('. קודם שואבים את הנתונים עם Power Query כמתואר שם, ורק אחר כך מגדירים כאן רענון. ההגדרות כאן אינן חלות על הורדה ידנית של CSV או על נוסחת WEBSERVICE.',
     '. First pull the data with Power Query as described there, then set up refresh here. These settings do not apply to a manual CSV download or to the WEBSERVICE formula.'),
    ('בעמוד',
     'On the'),
    ('בוחרים תאריך סיום, והקוד שהעמוד מפיק מסנן את הנתונים עד התאריך הזה. ברירת המחדל היא היום, ולכן נתון חדש שהתאריך שלו (במדד: החודש שלו) מאוחר מתאריך הסיום לא ייכנס לטבלה, גם אחרי רענון.',
     'page you choose an end date, and the code the page produces filters the data up to that date. The default is today, so a new reading whose date (for the index: its month) is later than the end date does not enter the table, even after a refresh.'),
    ('בקוד של המדד: השורה',
     'In the index code: the line'),
    (', למשל',
     ', for example'),
    ('בקוד של הריבית ושל שערי החליפין: השורה',
     'In the interest-rate and exchange-rate code: the line'),
]


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

        plain = lambda s: re.sub(r'<span lang="en" dir="ltr">([^<]*)</span>', r'\1', s)
        mac = steps("he/mac")
        self.assertEqual(len(mac), 6)
        self.assertIn(new_text, plain(mac[0]))
        self.assertIn('ללשונית <span lang="en" dir="ltr">Data</span> / ״נתונים״', mac[0])
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
            if page == 'he/mac':
                paragraph = ('<p>בעורך <span lang="en" dir="ltr">Power Query</span> לוחצים על ״עורך מתקדם״ '
                             '<span lang="en" dir="ltr">(Advanced Editor)</span>, '
                             'מוחקים את כל מה שכתוב שם, מדביקים במקומו קוד מתוך '
                             '<a class="guide-pill" href="#/mcode">קודים לייצוא '
                             '<span lang="en" dir="ltr">(Power Query)</span></a>, ולוחצים אישור/הבא.</p>')
            example = '<p>הקוד שלהלן הוא דוגמה מוכנה לריבית בנק ישראל לטווח 2022-12-01 עד 2025-12-31.</p>'
            self.assertIn(paragraph + example + '<div class="code-block"><button class="copy-url guide-copy-pill" '
                          'type="button">העתקת הקוד</button><pre dir="ltr" role="region" tabindex="0" aria-label="קוד לדוגמה" data-i18n-skip><code lang="en">', third)
            self.assertIn('</code></pre></div><div class="guide-mcode-cta">', third)
            cta = re.search(r'<div class="guide-mcode-cta">(.*?)</div>', third, re.S).group(1)
            self.assertEqual(cta.count('<p>'), 1)
            self.assertNotIn('<a', cta)
            self.assertNotIn('<button', cta)
            self.assertNotIn('guide-mcode-button', third)

        self.assertIn('class="code-block"', mac[2])
        self.assertIn('<pre dir="ltr" role="region" tabindex="0" aria-label="קוד לדוגמה" data-i18n-skip>', mac[2])
        rendered_code = re.search(r'<pre[^>]*><code lang="en">(.*?)</code></pre>', mac[2], re.S).group(1)
        self.assertEqual(html.unescape(rendered_code), out['code'])
        self.assertEqual(out['he/mac'].count('href="#/mcode"'), 1)
        self.assertNotIn('<aside', out['he/mac'])
        self.assertIn('הקוד שלהלן הוא דוגמה מוכנה לריבית בנק ישראל לטווח 2022-12-01 עד 2025-12-31.', mac[2])
        for text in ('כל סדרה, טווח תאריכים והשוואה שהאתר מציע', 'להוסיף שורת ממוצע', 'קוד M מוכן להעתקה'):
            self.assertIn(text, plain(mac[2]))
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
        self.assertIn(win_text, plain(win[0]))
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
        self.assertNotIn('href="#/mcode"', out['manual'])
        for step in steps('manual'):
            self.assertEqual(len(figures(step)), 1)
            self.assertIn('class="step-art step-art-single"', step)
            self.assertNotIn('אקסל באנגלית', step)
        for shot in out["shots"] + out["winShots"]:
            with (ROOT / shot["src"]).open("rb") as handle:
                self.assertEqual(handle.read(8), b"\x89PNG\r\n\x1a\n")
                length = struct.unpack(">I", handle.read(4))[0]
                self.assertEqual(handle.read(4), b"IHDR")
                width, height = struct.unpack(">II", handle.read(length)[:8])
            self.assertEqual((width, height), (shot["width"], shot["height"]))

    def test_illustration_regions_have_unique_names_in_every_excel_guide(self):
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
require(%s);
const S = window.Statso, out = {pages: {}};
for (const site of ['he', 'en']) {
  S.i18n = {current: () => site, onChange() {}};
  for (const platform of ['mac', 'win']) {
    for (const method of ['power', 'manual', 'webservice']) {
      Object.assign(S.guides.state, {platform, method});
      S.guides.renderExcelGuide();
      out.pages[[site, platform, method].join('/')] = host.innerHTML;
    }
  }
}
const L = S.lang;
const t = s => { if (L.en[s]) { return L.en[s]; }
  for (const [pattern, replacement] of L.enPatterns) { if (pattern.test(s)) { return s.replace(pattern, replacement); } }
  return s; };
out.translations = ['אקסל בעברית — שלב 3', 'אקסל באנגלית — שלב 12',
  'אקסל בעברית — שלב 5, תמונה 2', 'אקסל באנגלית — שלב 5, תמונה 1'].map(t);
process.stdout.write(JSON.stringify(out));
""" % tuple(json.dumps(str(ROOT / "assets" / name)) for name in
            ("statso-core.js", "statso-guide-art.js", "statso-guides.js", "statso-mcode.js", "statso-lang-en.js"))
        out = json.loads(subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True, encoding="utf-8"
        ).stdout)
        for page, markup in out['pages'].items():
            with self.subTest(page=page):
                labels = re.findall(r'role="region" tabindex="0" aria-label="([^"]*)"', markup)
                self.assertEqual(len(labels), len(set(labels)))
                if page.endswith('/mac/webservice'):
                    self.assertEqual(labels, [])
                    self.assertIn('<div class="guide-notice" role="status"><h2>', markup)
                    self.assertNotIn('<aside', markup)
                    continue
                figures = re.findall(r'<figure>(.*?)</figure>', markup, re.S)
                self.assertGreater(len(figures), 1)
                for figure in figures:
                    caption = re.search(r'<figcaption>(.*?)</figcaption>', figure, re.S).group(1)
                    self.assertEqual(caption, 'אקסל באנגלית' if page.startswith('en/') else 'אקסל בעברית')
                    label = re.search(r'aria-label="([^"]*)"', figure).group(1)
                    self.assertRegex(label, '^' + re.escape(caption) + r' — שלב \d+(?:, תמונה \d+)?$')
        for label in ('אקסל בעברית — שלב 5, תמונה 1', 'אקסל בעברית — שלב 5, תמונה 2',
                      'אקסל בעברית — שלב 7'):
            self.assertIn('aria-label="' + label + '"', out['pages']['he/win/power'])
        self.assertIn('aria-label="אקסל בעברית — שלב 1"', out['pages']['he/mac/manual'])
        self.assertNotIn('אקסל באנגלית', out['pages']['he/mac/manual'])
        self.assertIn('aria-label="אקסל באנגלית — שלב 1"', out['pages']['en/win/power'])
        self.assertEqual(out['translations'], ['Excel in Hebrew — step 3', 'Excel in English — step 12',
            'Excel in Hebrew — step 5, picture 2', 'Excel in English — step 5, picture 1'])

    def test_hebrew_site_uses_the_single_column_in_every_guide(self):
        self.assertNotIn('realShotGuide', self.guides)
        render = self.guides.split('function renderSteps() {')[1].split('\n  }')[0]
        self.assertIn("const site = Statso.i18n ? Statso.i18n.current() : 'he';", render)
        self.assertIn("const artClass = site === 'en' ? 'step-art' : 'step-art step-art-single';", render)

    def test_each_site_language_shows_only_its_own_excel(self):
        script = """
global.window = {scrollTo() {}};
const els = {}, listeners = []; let site = 'he';
function element() { return {hidden: false, innerHTML: '', setAttribute() {}, addEventListener() {}}; }
const host = element(), stub = element();
global.document = {addEventListener() {}, getElementById: id => els[id] || (els[id] = element()),
  querySelector: s => s === '.guide-steps-host' ? host : stub, querySelectorAll: () => []};
window.Statso = {i18n: {current: () => site, onChange: fn => listeners.push(fn)}};
require(%s);
require(%s);
require(%s);
require(%s);
require(%s);
const S = window.Statso, out = {pages: {}, switches: {}};
for (site of ['he', 'en']) for (const platform of ['mac', 'win']) for (const method of ['power', 'manual', 'webservice']) {
  Object.assign(S.guides.state, {platform, method});
  S.guides.renderExcelGuide();
  out.pages[[site, platform, method].join('/')] = host.innerHTML;
}
for (const platform of ['mac', 'win']) for (const method of ['power', 'manual', 'webservice']) {
  site = 'he'; Object.assign(S.guides.state, {platform, method});
  S.guides.showGuide('excel', true); const opened = host.innerHTML;
  site = 'en'; listeners.forEach(fn => fn()); const english = host.innerHTML;
  site = 'he'; listeners.forEach(fn => fn()); const hebrew = host.innerHTML;
  out.switches[platform + '/' + method] = {opened, english, hebrew};
}
out.caption = S.lang.en['אקסל באנגלית'];
process.stdout.write(JSON.stringify(out));
""" % tuple(json.dumps(str(ROOT / "assets" / name)) for name in
            ("statso-core.js", "statso-guide-art.js", "statso-mcode.js", "statso-guides.js", "statso-lang-en.js"))
        out = json.loads(subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True, encoding="utf-8"
        ).stdout)
        hebrew_counts = {'mac/power': [1, 1, 0, 1, 1, 1], 'win/power': [1, 1, 1, 1, 2, 1, 1],
                         'mac/manual': [1, 1, 1, 1], 'win/manual': [1, 1, 1, 1],
                         'win/webservice': [1, 1, 1], 'mac/webservice': []}
        english_counts = dict(hebrew_counts, **{'win/power': [1, 1, 1, 0, 1, 1, 1]})
        for site, counts in (('he', hebrew_counts), ('en', english_counts)):
            for variant, expected in counts.items():
                page = out['pages'][site + '/' + variant]
                with self.subTest(site=site, variant=variant):
                    steps = re.findall(r'<li>(.*?)</li>', page, re.S)
                    self.assertEqual([len(re.findall(r'<figure>', step)) for step in steps], expected)
                    self.assertNotIn('אקסל בעברית' if site == 'en' else 'אקסל באנגלית', page)
                    if variant == 'mac/webservice':
                        self.assertIn('<div class="guide-notice" role="status">', page)
                        self.assertNotIn('<figure>', page)
                        continue
                    for number, step in enumerate(steps, 1):
                        figures = re.findall(r'<figure>(.*?)</figure>', step, re.S)
                        if not figures:
                            self.assertNotIn('step-art', step)
                            continue
                        boxes = re.findall(r'<div class="(step-art[^"]*)">', step)
                        self.assertEqual(boxes, ['step-art' if site == 'en' else 'step-art step-art-single'])
                        for picture, figure in enumerate(figures, 1):
                            caption = re.search(r'<figcaption>(.*?)</figcaption>', figure).group(1)
                            label = re.search(r'role="region" tabindex="0" aria-label="([^"]*)"', figure).group(1)
                            if site == 'en':
                                self.assertEqual(caption, 'אקסל באנגלית')
                                self.assertEqual(label, f'אקסל באנגלית — שלב {number}')
                                self.assertIn('class="art-scroll art-scroll-ltr"', figure)
                                self.assertIn('<svg class="guide-svg" ', figure)
                                self.assertNotIn('<img', figure)
                                continue
                            self.assertEqual(caption, 'אקסל בעברית')
                            self.assertEqual(label, f'אקסל בעברית — שלב {number}' +
                                             (f', תמונה {picture}' if len(figures) > 1 else ''))
                            self.assertIn('class="art-scroll art-scroll-rtl"', figure)
                            self.assertNotIn('<svg class="guide-svg" ', figure)
                            if variant.endswith('/power'):
                                self.assertEqual(figure.count('<img '), 1)
                                self.assertNotIn('guide-svg', figure)
                            else:
                                self.assertIn('<svg class="guide-svg rtl-art" ', figure)
                                self.assertIn(' direction="rtl"', figure)
                                self.assertNotIn('<img', figure)
        self.assertEqual(out['caption'], 'Excel in English')
        for variant, seen in out['switches'].items():
            with self.subTest(switch=variant):
                self.assertEqual(seen['opened'], out['pages']['he/' + variant])
                self.assertEqual(seen['english'], out['pages']['en/' + variant])
                self.assertEqual(seen['hebrew'], out['pages']['he/' + variant])

    def test_second_guide_and_id_dispatch(self):
        self.assertIn("id: 'cpi-terms'", self.guides)
        self.assertIn("guideId === 'cpi-terms'", self.guides)
        self.assertIn("href=\"#/guides/' + guide.id + '\"", self.guides)
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


class GuideTree(HTMLParser):
    def __init__(self, markup):
        super().__init__(convert_charrefs=True)
        self.root = {'tag': '', 'attrs': {}, 'children': []}
        self.stack = [self.root]
        self.chunks = []
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        node = {'tag': tag, 'attrs': dict(attrs), 'children': []}
        self.stack[-1]['children'].append(node)
        if tag not in ('img', 'input', 'br', 'hr', 'meta', 'link'):
            self.stack.append(node)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i]['tag'] == tag:
                del self.stack[i:]
                break

    def handle_data(self, text):
        self.stack[-1]['children'].append(text)
        self.chunks.append((text, self.stack[1:].copy()))

    def nodes(self, tag=None, class_=None, parent=None):
        found = []
        for child in (parent or self.root)['children']:
            if isinstance(child, dict):
                if (tag is None or child['tag'] == tag) and (class_ is None or
                        class_ in child['attrs'].get('class', '').split()):
                    found.append(child)
                found.extend(self.nodes(tag, class_, child))
        return found

    @staticmethod
    def text(node):
        return ''.join(child if isinstance(child, str) else GuideTree.text(child)
                       for child in node['children'])


class LivePullGuideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / 'assets/statso-guides.js').read_text()
        script = r'''
global.window = {scrollTo() {}};
const els = {}, callbacks = [], listeners = [], clicks = [], order = [], spoken = []; let site = 'he';
function element() { return {hidden: false, innerHTML: '', attrs: {},
  setAttribute(k, v) { this.attrs[k] = v; }, addEventListener() {}}; }
const host = element(), heading = element();
heading.focus = options => { heading.focusOptions = options; order.push('focus'); };
const button = {addEventListener(event, fn) { if (event === 'click') clicks.push(fn); }};
global.document = {addEventListener(event, fn) { callbacks.push(fn); },
  getElementById: id => els[id] || (els[id] = element()),
  querySelector: s => s === '.guide-steps-host' ? host :
    s === '.choose-power' && host.innerHTML.includes('class="choose-power"') ? button :
    s === '.guide-steps-host h2' ? heading : null,
  querySelectorAll: () => []};
window.Statso = {i18n: {current: () => site, onChange: fn => listeners.push(fn), apply: node => order.push(node === els['guide-detail'] ? 'apply' : 'apply-elsewhere')},
  exporter: {announce: text => { order.push('announce'); spoken.push(text); }}};
'''
        script += '\n'.join('require(' + json.dumps(str(ROOT / 'assets' / name)) + ');' for name in
                            ('statso-core.js', 'statso-guide-art.js', 'statso-mcode.js',
                             'statso-guides.js', 'statso-lang-en.js'))
        script += r'''
const S = window.Statso, G = S.guides, out = {pages: {}, live: {}, clicks: {}, dictionary: S.lang.en};
callbacks[callbacks.length - 1](); out.cards = els['guide-cards'].innerHTML; out.guides = G.guides;
for (site of ['he', 'en']) {
  for (const platform of ['mac', 'win']) for (const method of ['power', 'manual', 'webservice']) {
    Object.assign(G.state, {platform, method}); G.renderExcelGuide();
    out.pages[[site, platform, method].join('/')] = {content: els['guide-content'].innerHTML, host: host.innerHTML};
  }
  out.opened = G.showGuide('live-pull', true);
  out.label = els['guide-detail'].attrs['aria-labelledby'];
  out.live[site] = els['guide-content'].innerHTML;
}
for (const [platform, method] of [['mac','manual'], ['win','manual'], ['win','webservice'], ['mac','webservice']]) {
  Object.assign(G.state, {platform, method}); G.showGuide('excel', true);
  order.length = 0; spoken.length = 0; clicks[clicks.length - 1]();
  out.clicks[platform + '/' + method] = {method: G.state.method, host: host.innerHTML,
    attrs: {...heading.attrs}, focus: heading.focusOptions, order: order.slice(), spoken: spoken.slice()};
}
site = 'he'; G.showGuide('live-pull', true); out.switches = [els['guide-content'].innerHTML];
for (site of ['en', 'he']) { listeners.forEach(fn => fn()); out.switches.push(els['guide-content'].innerHTML); }
out.generated = {};
for (const series of ['cpi','construction','boi','fx']) {
  for (const currencies of (series === 'fx' ? [['usd'], ['usd','eur']] : [[]])) {
    out.generated[series + '/' + currencies.length] = S.mcode.generate({series, currencies,
      from: '2022-12-01', to: '2099-12-31', average: false});
  }
}
process.stdout.write(JSON.stringify(out));
'''
        cls.out = json.loads(subprocess.run(['node', '-e', script], check=True,
                                           capture_output=True, text=True).stdout)

    def assert_marked_latin(self, tree, exempt=('a',)):
        for text, ancestors in tree.chunks:
            if not re.search('[A-Za-z]', text) or any(n['tag'] in exempt for n in ancestors):
                continue
            self.assertTrue(any(n['tag'] == 'span' and n['attrs'].get('lang') == 'en' and
                                n['attrs'].get('dir') == 'ltr' for n in ancestors), text)

    def translated(self, node):
        def translate(text):
            stripped = text.strip()
            return text.replace(stripped, self.out['dictionary'].get(stripped, stripped)) if stripped else text
        return ''.join(translate(child) if isinstance(child, str) else self.translated(child)
                       for child in node['children'])

    def test_power_query_note_opens_the_excel_guide_in_every_view(self):
        for variant, page in self.out['pages'].items():
            with self.subTest(variant=variant):
                markup = page['content']
                self.assertEqual(markup.count('<div class="guide-note">'), 1)
                self.assertLess(markup.index('</header>'), markup.index('<div class="guide-note">'))
                self.assertLess(markup.index('<div class="guide-note">'), markup.index('<form class="guide-selectors">'))
                note = re.search(r'<div class="guide-note">.*?</div>', markup).group()
                # the note's title is a real heading under the page's one h1, at the level of the step headings
                tree = GuideTree(note)
                headings = [n for n in tree.nodes() if re.fullmatch(r'h[1-6]', n['tag'])]
                self.assertEqual([n['tag'] for n in headings], ['h2'])
                self.assertIs(tree.root['children'][0]['children'][0], headings[0])
                self.assertEqual(GuideTree.text(headings[0]), 'למה Power Query?')
                if variant.startswith('en/'):
                    self.assertEqual(self.translated(headings[0]), 'Why Power Query?')
                self.assertLess(markup.index('<div class="guide-note"><h2>'), markup.index('<form class="guide-selectors">'))
                self.assertEqual(len(GuideTree(markup).nodes('h1')), 1)
                self.assertNotIn('<strong>', note)
                self.assertEqual(note.count('href="#/guides/live-pull"'), 1)
                self.assertNotRegex(note, r'<aside\b')
                if variant.startswith('he/'):
                    self.assert_marked_latin(GuideTree(note))
                else:
                    self.assertNotIn('<span lang="en"', note)

    def test_manual_and_webservice_views_recommend_power_query(self):
        notice = '<div class="guide-notice" role="status"><h2>WEBSERVICE אינה זמינה ב-Excel for Mac</h2><p>אין צעדים להצגה עבור שילוב זה. אפשר לייבא את הנתונים באמצעות Power Query.</p><button type="button" class="choose-power">מעבר ל-Power Query</button></div>'
        for variant, page in self.out['pages'].items():
            with self.subTest(variant=variant):
                host = page['host']
                if variant.endswith('mac/webservice'):
                    self.assertEqual(host, notice)
                elif variant.endswith('/power'):
                    self.assertNotIn('choose-power', host)
                    self.assertNotIn('guide-note', host)
                else:
                    self.assertTrue(host.startswith('<div class="guide-note">'))
                    note, steps = host.split('</div>', 1)
                    self.assertTrue(steps.startswith('<ol class="guide-steps">'))
                    self.assertEqual(note.count('<p>'), 1)
                    self.assertEqual(note.count('<button type="button" class="choose-power">מעבר ל-Power Query</button>'), 1)
                    self.assertNotRegex(note, r'<h[1-6]\b')
                    # the Hebrew hint marks its English terms; the button keeps the plain label the other notice button has
                    if variant.startswith('he/'):
                        self.assert_marked_latin(GuideTree(note + '</div>'), exempt=('a', 'button'))
                    else:
                        self.assertNotIn('<span lang="en"', note)

    def test_switch_to_power_query_buttons_share_one_handler_and_move_focus(self):
        for variant, result in self.out['clicks'].items():
            with self.subTest(variant=variant):
                self.assertEqual(result['method'], 'power')
                self.assertEqual(len(GuideTree(result['host']).nodes('h2')), 6 if variant.startswith('mac/') else 7)
                self.assertNotIn('choose-power', result['host'])
                self.assertEqual(result['attrs'], {'tabindex': '-1'})
                self.assertEqual(result['focus'], {'preventScroll': True})
                # the rebuilt steps are translated before the heading takes focus, so a screen reader never reads Hebrew on the English site
                self.assertEqual(result['order'], ['apply', 'focus', 'announce'])
                self.assertEqual(result['spoken'], ['השלבים עודכנו לפי הבחירה'])
        handler = self.source.split('function attachChoosePower() {')[1].split('\n  }')[0]
        self.assertEqual(handler.count("addEventListener('click'"), 1)
        self.assertEqual(handler.count('announceSteps();'), 1)
        self.assertLess(handler.index('first.focus('), handler.index('announceSteps();'))
        render = self.source.split('function renderSteps() {')[1].split('\n  }')[0]
        self.assertEqual(render.count('attachChoosePower();'), 2)
        self.assertNotIn("querySelector('.choose-power').addEventListener", self.source)

    def test_live_pull_is_a_real_guide_card_and_route(self):
        guides = self.out['guides']
        self.assertEqual([g['id'] for g in guides], ['excel', 'cpi-terms', 'live-pull'])
        self.assertFalse(any(g.get('soon') for g in guides))
        card = re.search(r'<a class="guide-card" href="#/guides/live-pull">.*?</a>', self.out['cards']).group()
        self.assertIn('רענון אוטומטי של הנתונים ב-Excel', card)
        self.assertIn('אחרי שאיבת הנתונים עם Power Query: כך מגדירים שהקובץ יתרענן בפתיחה או כל כמה דקות, וימשיך להוסיף ריבית ומדד חדשים.', card)
        self.assertTrue(self.out['opened'])
        self.assertEqual(self.out['label'], 'live-pull-guide-title')

    def test_live_pull_guide_structure(self):
        for site, markup in self.out['live'].items():
            with self.subTest(site=site):
                tree = GuideTree(markup)
                self.assertEqual([n['attrs'] for n in tree.nodes('h1')], [{'id': 'live-pull-guide-title'}])
                lists = tree.nodes('ol', 'guide-steps')
                self.assertEqual(len(lists), 1)
                steps = lists[0]['children']
                self.assertEqual(len(steps), 6)
                for step in steps:
                    self.assertEqual(step['tag'], 'li')
                    self.assertEqual(len(step['children']), 1)
                    copy = step['children'][0]
                    self.assertEqual((copy['tag'], copy['attrs']), ('div', {'class': 'step-copy'}))
                    self.assertEqual(copy['children'][0]['tag'], 'h2')
                    self.assertEqual(len(tree.nodes('h2', parent=copy)), 1)
                prose = tree.nodes('div', 'prose-guide')[0]
                self.assertEqual(len(prose['children']), 1)
                section = prose['children'][0]
                self.assertEqual(section['tag'], 'section')
                self.assertEqual(section['children'][0]['tag'], 'h2')
                self.assertEqual(len(tree.nodes('h2', parent=section)), 1)
                self.assertEqual(len(tree.nodes('h2')), 7)
                self.assertNotRegex(markup, r'<h[3-6]\b|step-art|<figure|<img|<svg|role="region"|tabindex')
                self.assertEqual(markup.count('href="#/guides/excel"'), 1)
                self.assertEqual(markup.count('<a class="guide-pill" href="#/mcode">'), 1)
                self.assertLess(markup.index('class="guide-note"'), markup.index('class="guide-steps"'))

    def test_live_pull_content_matches_the_approved_text(self):
        rendered = self.out['cards'] + self.out['live']['he']
        rendered += ''.join(p['content'] + p['host'] for key, p in self.out['pages'].items() if key.startswith('he/'))
        plain = GuideTree.text(GuideTree(rendered).root)
        for he, en in APPROVED_REFRESH_TEXT:
            with self.subTest(fragment=he):
                self.assertEqual(self.out['dictionary'].get(he), en)
                self.assertIn(he, plain)
        note = GuideTree(self.out['pages']['en/mac/power']['content']).nodes('div', 'guide-note')[0]
        live = GuideTree(self.out['live']['en'])
        paragraphs = live.nodes('p')
        expected = [
            'A manual CSV download and the WEBSERVICE formula have no such setting. To set up automatic refresh: Automatic data refresh in Excel.',
            'This continues the guide Pulling statso data into Excel. First pull the data with Power Query as described there, then set up refresh here. These settings do not apply to a manual CSV download or to the WEBSERVICE formula.',
            'On the Export code (Power Query) page you choose an end date, and the code the page produces filters the data up to that date. The default is today, so a new reading whose date (for the index: its month) is later than the end date does not enter the table, even after a refresh.',
            'In the index code: the line ToMonth, for example ToMonth = "2099-12"',
            'In the interest-rate and exchange-rate code: the line To, for example To = #date(2099, 12, 31)',
        ]
        nodes = GuideTree('').nodes('p', parent=note)[-1:] + paragraphs[2:4]
        nodes += live.nodes('ul', 'guide-list')[0]['children']
        self.assertEqual([self.translated(node) for node in nodes], expected)

    def test_live_pull_hebrew_marks_latin_and_english_nodes_stay_whole(self):
        self.assert_marked_latin(GuideTree(self.out['live']['he']), ('a', 'code', 'h1'))
        english = self.out['live']['en']
        self.assertNotIn('<span', english)
        for text, _ in GuideTree(english).chunks:
            if re.search('[֐-׿]', text):
                self.assertIn(text.strip(), self.out['dictionary'])
                self.assertNotRegex(self.out['dictionary'][text.strip()], '[֐-׿]')

    def test_live_pull_example_lines_match_the_generated_code(self):
        codes = [GuideTree.text(n) for n in GuideTree(self.out['live']['he']).nodes('code')]
        self.assertEqual(codes, ['ToMonth', 'ToMonth = "2099-12"', 'To', 'To = #date(2099, 12, 31)'])
        self.assertEqual(set(self.out['generated']), {'cpi/0', 'construction/0', 'boi/0', 'fx/1', 'fx/2'})
        for series, code in self.out['generated'].items():
            line = codes[1] if series.startswith(('cpi/', 'construction/')) else codes[3]
            self.assertIn('\n    ' + line + ',', code)

    def test_open_live_pull_guide_follows_a_language_switch(self):
        self.assertEqual(self.out['switches'], [self.out['live'][site] for site in ('he', 'en', 'he')])

    def test_note_hint_and_list_css(self):
        css = (ROOT / 'assets/statso.css').read_text()
        self.assertIn('.guide-notice button, .guide-note button, .copy-url {', css)
        before, forced = css.split('@media (forced-colors: active)')
        self.assertIn('.guide-note button', forced)
        rule = re.search(r'\.guide-list \{([^}]+)\}', before).group(1)
        self.assertIn('padding-inline-start: 24px', rule)
        self.assertIn('overflow-wrap: anywhere', rule)
        note = re.search(r'\.guide-note, \.guide-notice \{([^}]+)\}', before).group(1)
        self.assertIn('overflow-wrap: anywhere', note)
        # drawn exactly as the bold paragraph it replaced: the paragraph's 1em margins, the body size, bold
        heading = re.search(r'(?m)^\.guide-note h2 \{([^}]+)\}', before).group(1)
        for declaration in ('margin: 1em 0', 'font-size: 1em', 'font-weight: 700', 'overflow-wrap: anywhere'):
            self.assertIn(declaration, heading)

if __name__ == "__main__":
    unittest.main()
