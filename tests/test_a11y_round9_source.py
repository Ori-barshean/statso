"""Runtime and markup checks for hover dismissal and language of parts."""
import json
import re
import unittest
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

from tests.test_a11y_round5_source import module, node
from tests.test_a11y_round8_source import NAV_SETUP

ROOT = Path(__file__).resolve().parent.parent
MENU_SETUP = r"""
const docListeners = {}, focusLog = []; let active = null;
function el(name) { return {name, attrs: {}, listeners: {},
  getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }, setAttribute(k, v) { this.attrs[k] = String(v); },
  removeAttribute(k) { delete this.attrs[k]; }, addEventListener(t, fn) { (this.listeners[t] = this.listeners[t] || []).push(fn); },
  fire(t, e) { (this.listeners[t] || []).forEach(fn => fn(e || {})); }}; }
const group = el('group'), trigger = el('trigger'), link = el('link');
group.hovered = false; group.matches = sel => sel === ':hover' ? group.hovered : false;
group.contains = node => node === group || node === trigger || node === link;
trigger.closest = sel => sel === '.nav-group' ? group : null; trigger.attrs['aria-expanded'] = 'false';
trigger.focus = () => { focusLog.push('trigger'); if (active !== trigger) { active = trigger; trigger.fire('focus'); } };
els['tools-trigger'] = trigger;
document.addEventListener = (t, fn) => { (docListeners[t] = docListeners[t] || []).push(fn); };
function key(k) { const e = {key: k, prevented: false, preventDefault() { this.prevented = true; }}; (docListeners.keydown || []).forEach(fn => fn(e)); return e; }
function menu() { return {open: group.getAttribute('data-open'), closed: group.getAttribute('data-closed'), expanded: trigger.getAttribute('aria-expanded'), focusCalls: focusLog.length}; }
"""


def nav_run(body):
    return node(NAV_SETUP + MENU_SETUP + module('statso-nav.js') + '\nwindow.Statso.nav.init();\n' + body)


class NavEscapeTests(unittest.TestCase):
    def test_hover_escape_closes_without_focus_or_prevent_default_and_fresh_hover_resets(self):
        seen = nav_run("""
group.hovered = true; const prevented = key('Escape').prevented, closed = menu();
group.fire('mouseenter'); process.stdout.write(JSON.stringify({prevented, closed, fresh: menu()}));
""")
        self.assertFalse(seen['prevented'])
        self.assertEqual(seen['closed'], dict(open=None, closed='true', expanded='false', focusCalls=0))
        self.assertEqual(seen['fresh'], dict(open=None, closed=None, expanded='false', focusCalls=0))

    def test_unopened_escape_and_hover_non_escape_do_nothing(self):
        for setup, key in [('', 'Escape'), ('group.hovered = true;', 'Enter')]:
            with self.subTest(setup=setup, key=key):
                seen = nav_run(setup + 'const event = key(' + json.dumps(key) + ');'
                               + 'process.stdout.write(JSON.stringify({state: menu(), prevented: event.prevented}));')
                self.assertEqual(seen['state'], dict(open=None, closed=None, expanded='false', focusCalls=0))
                self.assertFalse(seen['prevented'])

    def test_keyboard_and_hover_plus_keyboard_escape_close(self):
        for hovered in (False, True):
            with self.subTest(hovered=hovered):
                seen = nav_run('group.hovered = ' + json.dumps(hovered) + """;
active = trigger; trigger.fire('focus'); const before = menu(), prevented = key('Escape').prevented;
process.stdout.write(JSON.stringify({before, after: menu(), prevented, onTrigger: active === trigger}));
""")
                self.assertEqual(seen['before'], dict(open='true', closed=None, expanded='true', focusCalls=0))
                self.assertEqual(seen['after'], dict(open=None, closed='true', expanded='false', focusCalls=1))
                self.assertTrue(seen['onTrigger'])
                self.assertFalse(seen['prevented'])

    def test_refocusing_after_submenu_or_safari_click_does_not_reopen(self):
        for setup in ("active = trigger; trigger.fire('focus'); active = link;",
                      "trigger.fire('click', {button: 0});"):
            with self.subTest(setup=setup):
                seen = nav_run(setup + """
const before = menu(), prevented = key('Escape').prevented;
const after = menu(), onTrigger = active === trigger;
active = null; trigger.focus();
process.stdout.write(JSON.stringify({before, after, onTrigger, prevented, freshFocus: menu()}));
""")
                self.assertEqual(seen['before']['open'], 'true')
                self.assertEqual(seen['after'], dict(open=None, closed='true', expanded='false', focusCalls=1))
                self.assertTrue(seen['onTrigger'])
                self.assertFalse(seen['prevented'])
                self.assertEqual(seen['freshFocus'], dict(open='true', closed=None, expanded='true', focusCalls=2))

    def test_refocusing_flag_is_reset_when_focus_throws(self):
        seen = nav_run("""
trigger.fire('focus');
trigger.focus = () => { throw new Error('focus failed'); };
let threw = false;
try { key('Escape'); } catch (e) { threw = true; }
const closed = menu();
trigger.focus = () => { focusLog.push('trigger'); active = trigger; trigger.fire('focus'); };
active = null; trigger.focus();
process.stdout.write(JSON.stringify({threw, closed, reopened: menu()}));
""")
        self.assertTrue(seen['threw'])
        self.assertIsNone(seen['closed']['open'])
        self.assertEqual(seen['reopened']['open'], 'true')


GUIDE_SETUP = r"""
global.window = {scrollTo() {}}; const els = {}, listeners = []; let site = 'he';
function element() { return {hidden: false, innerHTML: '', setAttribute() {}, addEventListener() {}}; }
const host = element(), stub = element();
global.document = {addEventListener() {}, getElementById: id => els[id] || (els[id] = element()),
  querySelector: s => s === '.guide-steps-host' ? host : stub, querySelectorAll: () => []};
window.Statso = {i18n: {current: () => site, onChange: fn => listeners.push(fn)}};
const translate = text => { const t = text.trim(); const S = window.Statso; if (S.lang.en[t] !== undefined) { return S.lang.en[t]; }
  for (const rule of S.lang.enPatterns) { if (rule[0].test(t)) { return t.replace(rule[0], rule[1]); } } return null; };
"""
SPAN = re.compile(r'<span lang="en" dir="ltr">([^<]*)</span>')
HEBREW = r'[\u0590-\u05ff]'
LATIN = r'[A-Za-z]'


def guide_run(body):
    return node(GUIDE_SETUP + ''.join(module(name) for name in (
        'statso-core.js', 'statso-guide-art.js', 'statso-mcode.js', 'statso-guides.js', 'statso-lang-en.js')) + body)


def paragraphs(markup):
    return re.findall(r'<p>(.*?)</p>', markup, re.S)


def guide_steps(markup):
    return re.findall(r'<li>(.*?)</li>', markup, re.S)


class GuideLanguageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seen = guide_run(r"""
const renders = {}, translations = [];
for (site of ['he', 'en']) for (const platform of ['mac', 'win']) for (const method of ['power', 'manual', 'webservice']) {
  Object.assign(window.Statso.guides.state, {platform, method}); window.Statso.guides.renderExcelGuide();
  renders[[site, platform, method].join('/')] = host.innerHTML;
  if (site === 'en') for (const p of host.innerHTML.matchAll(/<p>(.*?)<\/p>/gs)) {
    for (const chunk of p[1].split(/<[^>]+>/)) if (/[\u0590-\u05ff]/.test(chunk)) {
      translations.push({text: chunk, translated: translate(chunk)});
    }
  }
}
process.stdout.write(JSON.stringify({renders, translations}));
""")

    def test_every_hebrew_step_marks_all_latin_preserves_text_and_payloads(self):
        for platform in ('mac', 'win'):
            for method in ('power', 'manual', 'webservice'):
                with self.subTest(platform=platform, method=method):
                    he = self.seen['renders'][f'he/{platform}/{method}']
                    en = self.seen['renders'][f'en/{platform}/{method}']
                    count = {'power': 6 if platform == 'mac' else 7, 'manual': 4,
                             'webservice': 0 if platform == 'mac' else 3}[method]
                    self.assertEqual(len(guide_steps(he)), count)
                    self.assertEqual(len(guide_steps(en)), count)
                    he_paras = [p for step in guide_steps(he) for p in paragraphs(step)]
                    en_paras = [p for step in guide_steps(en) for p in paragraphs(step)]
                    self.assertEqual([SPAN.sub(r'\1', p) for p in he_paras], en_paras)
                    for p in he_paras:
                        for run in SPAN.findall(p):
                            self.assertNotRegex(run, HEBREW)
                        prose = re.sub(r'<code\b[^>]*>.*?</code>', '', p, flags=re.S)
                        prose = re.sub(r'<[^>]+>', '', SPAN.sub('', prose))
                        self.assertNotRegex(unescape(prose), LATIN)
                    for p in paragraphs(en):
                        self.assertNotIn('<span lang="en"', p)
                    self.assertEqual(re.findall(r'data-url="([^"]*)"', he), re.findall(r'data-url="([^"]*)"', en))
                    self.assertEqual(he.count('class="copy-url'), en.count('class="copy-url'))
                    self.assertEqual(re.findall(r'<code lang="en">(.*?)</code>', he, re.S),
                                     re.findall(r'<code lang="en">(.*?)</code>', en, re.S))

    def test_english_paragraph_text_chunks_still_translate_as_whole_nodes(self):
        self.assertGreater(len(self.seen['translations']), 20)
        for item in self.seen['translations']:
            with self.subTest(text=item['text']):
                self.assertIsNotNone(item['translated'])
                self.assertNotRegex(item['translated'], HEBREW)

    def test_worked_table_maximal_runs_in_every_step(self):
        expected = {
            'mac/power': [['Data', '(Power Query)'], ['(Choose data source)', '(Blank Query)'],
                          ['Power Query', '(Advanced Editor)', '(Power Query)', '(Power Query)', 'M'],
                          ['(Configure connection)', '(Anonymous)'], ['(Close & Load)'], ['Data', '(Refresh All)']],
            'win/power': [['(Data)', '(Get Data)', '(Get Data (Preview))'],
                          ['(Power Query)', '(Get Data (Power Query))', '(Blank Query)'], ['(Advanced Editor)'],
                          ['(Power Query)', '(Done)', '(Power Query)', 'M'],
                          ['(Edit Credentials)', '(Anonymous)', '(Connect)'], ['(Close & Load)'], ['(Data)', '(Refresh All)']],
            'mac/manual': [['CSV'], ['.csv', 'Cmd+S'], ['File ← Open'], ['UTF-8', 'BOM']],
            'win/manual': [['CSV'], ['.csv', 'Ctrl+S'], ['File ← Open'], ['UTF-8', 'BOM']],
            'win/webservice': [['WEBSERVICE', 'JSON'], [], ['Power Query']],
            'mac/webservice': [],
        }
        for variant, runs in expected.items():
            with self.subTest(variant=variant):
                steps = guide_steps(self.seen['renders']['he/' + variant])
                self.assertEqual([SPAN.findall(''.join(paragraphs(step))) for step in steps], runs)
        checks = {
            'mac/power': [(0, 'ללשונית <span lang="en" dir="ltr">Data</span> / ״נתונים״'),
                          (1, '״בחר מקור נתונים״ <span lang="en" dir="ltr">(Choose data source)</span> בוחרים ״שאילתה ריקה״ <span lang="en" dir="ltr">(Blank Query)</span>.'),
                          (2, '</a>, ולוחצים אישור/הבא.')],
            'win/power': [(0, '״נתונים״ <span lang="en" dir="ltr">(Data)</span>. לוחצים על ״יבא נתונים״ <span lang="en" dir="ltr">(Get Data)</span>, ואז על ״יבא נתונים (תצוגה מקדימה)״ <span lang="en" dir="ltr">(Get Data (Preview))</span>.'),
                          (1, '״יבא נתונים <span lang="en" dir="ltr">(Power Query)</span>״ <span lang="en" dir="ltr">(Get Data (Power Query))</span>'),
                          (3, '<a class="guide-pill" href="#/mcode">קודים לייצוא <span lang="en" dir="ltr">(Power Query)</span></a>. לאחר ההדבקה לוחצים על ״סיום״ <span lang="en" dir="ltr">(Done)</span>.'),
                          (4, '(״ציין כיצד להתחבר.״)')],
        }
        for platform, key, ending in [('mac', 'Cmd+S', 'במק.'), ('win', 'Ctrl+S', 'בווינדוס.')]:
            checks[platform + '/manual'] = [
                (1, 'כקובץ \u200e<span lang="en" dir="ltr">.csv</span> באמצעות <span lang="en" dir="ltr">' + key + '</span> ' + ending),
                (2, '<span lang="en" dir="ltr">File ← Open</span> / ״קובץ ← פתיחה״')]
        for variant, phrases in checks.items():
            steps = guide_steps(self.seen['renders']['he/' + variant])
            for index, phrase in phrases:
                with self.subTest(variant=variant, step=index + 1):
                    self.assertIn(phrase, steps[index])

    def test_language_round_trip_preserves_method_and_exact_render(self):
        seen = guide_run(r"""
const results = [];
for (const platform of ['mac', 'win']) for (const method of ['power', 'manual', 'webservice']) {
  site = 'he'; Object.assign(window.Statso.guides.state, {platform, method});
  window.Statso.guides.showGuide('excel', true); const first = host.innerHTML;
  site = 'en'; listeners.forEach(fn => fn()); const english = host.innerHTML, enMethod = window.Statso.guides.state.method;
  window.Statso.guides.renderExcelGuide(); const direct = host.innerHTML;
  site = 'he'; listeners.forEach(fn => fn());
  results.push({method, enMethod, heMethod: window.Statso.guides.state.method,
    sameHebrew: first === host.innerHTML, sameEnglish: english === direct});
}
process.stdout.write(JSON.stringify(results));
""")
        for result in seen:
            self.assertTrue(result['sameHebrew'])
            self.assertTrue(result['sameEnglish'])
            self.assertEqual(result['enMethod'], result['method'])
            self.assertEqual(result['heMethod'], result['method'])


class LanguageParser(HTMLParser):
    """Track nearest data-lang ancestors and retain ancestry for text checks."""
    VOID = set('area base br col embed hr img input link meta param source track wbr'.split())

    def __init__(self):
        super().__init__()
        self.stack, self.nodes, self.chunks, self.blocks = [], [], [], []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        region = attrs.get('data-lang', self.stack[-1]['region'] if self.stack else None)
        item = dict(tag=tag, attrs=attrs, region=region, text='', ancestors=self.stack[:])
        self.nodes.append(item)
        if 'data-lang' in attrs:
            self.blocks.append(item)
        if tag not in self.VOID:
            self.stack.append(item)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i]['tag'] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        self.chunks.append((data, self.stack[:]))
        for item in self.stack:
            item['text'] += data


class MarkupLanguageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = LanguageParser()
        cls.parser.feed((ROOT / 'index.html').read_text(encoding='utf-8'))

    def test_ltr_spans_follow_their_nearest_language_block(self):
        for language in ('he', 'en'):
            self.assertEqual(sum(b['region'] == language for b in self.parser.blocks), 5)
        marked = 0
        for item in self.parser.nodes:
            if item['tag'] != 'span' or item['attrs'].get('dir') != 'ltr':
                continue
            with self.subTest(region=item['region'], text=item['text']):
                if item['region'] == 'he':
                    if re.search(LATIN, item['text']) and not re.search(HEBREW, item['text']):
                        self.assertEqual(item['attrs'].get('lang'), 'en')
                        marked += 1
                    else:
                        self.assertNotIn('lang', item['attrs'])
                elif item['region'] == 'en':
                    self.assertNotIn('lang', item['attrs'])
        self.assertGreaterEqual(marked, 70)

    def test_hebrew_blocks_have_no_unmarked_latin_except_documented_exclusions(self):
        for text, ancestors in self.parser.chunks:
            if not ancestors or ancestors[-1]['region'] != 'he':
                continue
            if any(n['attrs'].get('lang') == 'en' or n['tag'] in ('a', 'code', 'time')
                   or (n['tag'] == 'span' and n['attrs'].get('dir') == 'ltr' and re.search(HEBREW, n['text']))
                   for n in ancestors):
                continue
            self.assertNotRegex(re.sub(r'\bstatso\b', '', text), LATIN, text)

    def test_statement_has_three_matching_new_bullets(self):
        phrases = {
            'he': ['כשהוא פתוח רק מפני שהעכבר נח עליו',
                   'מונחים וביטויים באנגלית בתוך הטקסט העברי',
                   'בתיאורי צילומי המסך במדריכים ובשמות הנגישים של רכיבים'],
            'en': ['when it is open only because the mouse rests on it',
                   'English terms and phrases inside the Hebrew text',
                   'The descriptions of the screenshots in the guides and the accessible names of components'],
        }
        bullets = {}
        for lang, texts in phrases.items():
            bullets[lang] = [n for n in self.parser.nodes if n['tag'] == 'li' and n['region'] == lang
                             and any(a['attrs'].get('id') == 'accessibility-page' for a in n['ancestors'])]
            for text in texts:
                self.assertEqual(sum(text in n['text'] for n in bullets[lang]), 1)
        self.assertEqual(len(bullets['he']), len(bullets['en']))
