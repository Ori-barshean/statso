"""Regression checks for the 1.0.75 script failures and not-found views.

Runtime checks execute the shipped JavaScript with a small DOM, while source
checks keep the bilingual markup and accessibility statement promises in sync.
"""
import json
import re
import tempfile
import unittest
from pathlib import Path

from scripts.build_offline import build
from scripts.statement_fingerprint import fingerprint
from tests.test_a11y_round5_source import module, node
from tests.test_i18n import dictionary_keys

ROOT = Path(__file__).resolve().parent.parent
HTML = (ROOT / 'index.html').read_text(encoding='utf-8')
ASSETS = sorted((ROOT / 'assets').glob('statso-*.js'))
GUARD = re.search(r'<script id="script-guard">(.*?)</script>', HTML, re.S).group(1)
REQUIRED = re.findall(r"'([A-Za-z][A-Za-z0-9]*)'", re.search(r'var REQUIRED = \[(.*?)\]', GUARD, re.S).group(1))
EXEMPT = {'statso-visits.js'}
GENERIC = 'אירעה שגיאה בעיבוד הנתונים. אפשר לרענן את הדף ולנסות שוב.'
GUARD_TEXTS = [
    'חלק מהאתר לא נטען, ולכן ייתכן שחלק מהעמודים והכלים לא יפעלו. אפשר לרענן את הדף ולנסות שוב.',
    'Part of the site did not load, so some pages and tools may not work. You can refresh the page and try again.',
]
STATEMENT_DATE = '2026-10-13'
STATEMENT_FINGERPRINT = 'bdf2da3d5500fc1afbc1e7ddf92c8c95ae6353f6b3f19f604a0bef47a3469d57'


def statement_blocks():
    page = re.search(r'<article[^>]*id="accessibility-page".*?</article>', HTML, re.S).group(0)
    return dict(re.findall(r'<div class="prose-guide" data-lang="(he|en)"[^>]*>(.*?)</div>', page, re.S))


def offline_html():
    # An explicit temporary destination never invokes the Desktop build target.
    with tempfile.TemporaryDirectory() as temp:
        out = Path(temp) / 'statso.html'
        build(out=out)
        return out.read_text(encoding='utf-8')


class ScriptGuardTests(unittest.TestCase):
    def test_notice_is_empty_hidden_and_above_every_view(self):
        wrap = re.search(r'<section class="shell data-problem-wrap" id="script-problem-wrap"([^>]*)>\s*'
                         r'<div class="data-problem" id="script-problem" role="alert" data-i18n-skip></div>\s*</section>', HTML)
        self.assertIsNotNone(wrap)
        self.assertIn('hidden', wrap.group(1))
        self.assertIn('aria-label="תקלה בטעינת האתר"', wrap.group(1))
        self.assertIn('תקלה בטעינת האתר', dictionary_keys())
        self.assertGreater(wrap.start(), HTML.index('</header>'))
        self.assertLess(wrap.start(), HTML.index('id="data-problem-wrap"'))
        self.assertLess(wrap.start(), HTML.index('<main'))

    def test_guard_is_last_and_independent_of_modern_syntax_and_translation(self):
        start = HTML.index('<script id="script-guard">')
        for script in re.finditer(r'<script\b[^>]*\bsrc=', HTML):
            self.assertLess(script.start(), start)
        for forbidden in ('=>', 'const ', 'let ', '`', 'i18n.', '.t(', ' async', ' defer', '<!--', '-->'):
            self.assertNotIn(forbidden, GUARD)
        self.assertLess(start, HTML.index('<div id="print-root">'))

    def test_required_modules_cover_every_site_script_and_exemptions_are_explicit(self):
        included = set(re.findall(r'<script src="assets/(statso-[a-z0-9-]+\.js)"', HTML))
        self.assertEqual(included, {path.name for path in ASSETS})
        registered, exempt = set(), set()
        for path in ASSETS:
            names = re.findall(r'(?m)^\s*Statso\.([A-Za-z][A-Za-z0-9]*)\s*=\s*\{', path.read_text(encoding='utf-8'))
            registered.update(names)
            if not names:
                exempt.add(path.name)
        self.assertIn('i18n', REQUIRED)
        self.assertEqual(set(REQUIRED), registered)
        self.assertEqual(len(REQUIRED), len(registered))
        self.assertEqual(exempt, EXEMPT)

    def test_contact_script_registers_itself_and_is_checked_by_the_guard(self):
        self.assertIn('contact', REQUIRED)
        seen = node(r"""
global.window = {};
let domReady = null;
global.document = {addEventListener(type, fn) { domReady = {type, fn}; }};
require(%s);
process.stdout.write(JSON.stringify({registered: typeof window.Statso.contact.init, listener: domReady && domReady.type,
 sameFunction: domReady && domReady.fn === window.Statso.contact.init}));
""" % json.dumps(str(ROOT / 'assets' / 'statso-contact.js')))
        self.assertEqual(seen, {'registered': 'function', 'listener': 'DOMContentLoaded', 'sameFunction': True})
        # the visit counter stays outside the guard: privacy extensions may block it and visitors must not see a warning for that
        self.assertNotIn('visits', REQUIRED)

    @staticmethod
    def run_guard(missing):
        return node(r"""
const timers = [], wrap = {hidden: true}, box = {textContent: '', kids: [], appendChild(p) { this.kids.push(p); }};
global.window = {Statso: Object.fromEntries(%s.map(name => [name, {}])), setTimeout(fn) { timers.push(fn); }};
const missing = %s;
if (missing === '*') { delete window.Statso; } else if (missing) { delete window.Statso[missing]; }
global.document = {getElementById(id) { return id === 'script-problem-wrap' ? wrap : box; },
 createElement(tag) { return {tag, attrs: {}, textContent: '', setAttribute(k, v) { this.attrs[k] = v; }}; }};
""" % (json.dumps(REQUIRED), json.dumps(missing)) + GUARD + r"""
const before = {hidden: wrap.hidden, text: box.textContent, kids: box.kids.length, timers: timers.length};
timers.forEach(fn => fn());
process.stdout.write(JSON.stringify({before, hidden: wrap.hidden, kids: box.kids}));
""")

    def test_each_missing_module_and_missing_namespace_show_both_languages_after_a_tick(self):
        for missing in REQUIRED + ['*']:
            with self.subTest(missing=missing):
                seen = self.run_guard(missing)
                self.assertEqual(seen['before'], {'hidden': False, 'text': '', 'kids': 0, 'timers': 1})
                self.assertFalse(seen['hidden'])
                self.assertEqual(seen['kids'], [
                    {'tag': 'p', 'attrs': {'lang': lang, 'dir': direction, 'data-i18n-skip': ''}, 'textContent': text}
                    for lang, direction, text in zip(('he', 'en'), ('rtl', 'ltr'), GUARD_TEXTS)])

    def test_all_modules_present_leave_the_notice_hidden(self):
        seen = self.run_guard(None)
        self.assertEqual(seen['before'], {'hidden': True, 'text': '', 'kids': 0, 'timers': 0})
        self.assertTrue(seen['hidden'])
        self.assertEqual(seen['kids'], [])

    def test_offline_transform_preserves_the_guard(self):
        artifact = offline_html()
        self.assertIn('id="script-guard"', artifact)
        self.assertIn(re.search(r'var REQUIRED = \[.*?\];', GUARD, re.S).group(0), artifact)


class UserFacingErrorTests(unittest.TestCase):
    def test_exception_text_is_only_read_by_the_local_message_filter(self):
        count = 0
        for path in ASSETS:
            source = path.read_text(encoding='utf-8')
            helper = re.search(r'function userMessage\([^)]*\)\s*\{.*?\n  \}', source, re.S)
            self.assertNotIn('.reason.message', source, path.name)
            for match in re.finditer(r'(\w+)(?:\.reason)?\.message\b', source):
                if path.name == 'statso-contact.js' and match.group(0) == 'fields.message':
                    continue
                count += 1
                self.assertEqual(path.name, 'statso-app.js')
                self.assertIsNotNone(helper)
                self.assertTrue(helper.start() <= match.start() < helper.end())
            if helper:
                self.assertNotIn('Statso.core', helper.group(0))
                self.assertNotIn('Statso.i18n', helper.group(0))
        self.assertGreater(count, 0)
        self.assertIn(GENERIC, dictionary_keys())

    @staticmethod
    def run_app(results, missing=None):
        # Based on DataProblemNoticeTests.notice_after, recording both visible
        # card errors and setState messages, as well as the ready event.
        return node(r"""
const els = {}, states = [], events = [];
function made(id) { return {id, hidden: true, textContent: '', kids: [], dataset: {}, style: {},
 appendChild(c) { this.kids.push(c); }, setAttribute() {}, getBoundingClientRect() { return {height: 0}; },
 querySelector() { return null; }}; }
global.window = {addEventListener() {}, dispatchEvent(e) { events.push(e.type); }, setTimeout(fn) { fn(); }};
global.CustomEvent = function (type) { this.type = type; };
global.document = {addEventListener() {}, querySelectorAll() { return []; },
 getElementById(id) { return els[id] || (els[id] = made(id)); }, createElement: made};
const gone = {status: 'rejected', reason: new Error('response')};
const here = value => ({status: 'fulfilled', value});
const cpi = here({observations: [], last_month: '2026-09'}), boi = here({current_rate: 4.5});
const fx = here({rates: [{code: 'USD', latest: {rate: 3.3, date: '2026-10-01'}},
 {code: 'EUR', latest: {rate: 3.9, date: '2026-10-01'}}]});
const results = %s;
window.Statso = {data: {loadAll: () => Promise.resolve(results), loadVersion: () => Promise.reject(new Error('x')),
 setState(el, state, message) { states.push({id: el.id, state, message}); }},
 collapse: {attach() {}}, i18n: {onChange() {}}, chart: {init() {}, showUnavailable() {}, activate() {}},
 calculator: {init() {}, initFx() {}}, fxtable: {init() {}},
 core: {buildIndexMap: () => new Map(), latestObservation: () => ({}), yearOverYear: () => ({ok: true, percent: 1}),
 monthOverMonth: () => ({ok: true, percent: 1}), formatPercent: String, shiftMonth: m => m, formatMonthHe: m => m,
 formatIsoDateHe: d => d, nextCpiPublicationDate: () => '2026-10-15', primeRate: v => v + 1.5, formatRate: String}};
if (%s) { delete window.Statso[%s]; }
""" % (results, json.dumps(missing), json.dumps(missing)) + module('statso-app.js') + r"""
const direct = [null, {}, new TypeError('x'), new Error('  הודעה בעברית  ')].map(window.Statso.app.userMessage);
window.Statso.app.init();
setTimeout(() => {
 const errors = Object.fromEntries(['cpi', 'boi', 'fx'].map(id => [id, (els['kpi-' + id + '-error'] || {}).textContent || '']));
 process.stdout.write(JSON.stringify({errors, states, events, direct}));
}, 0);
""")

    def test_runtime_failures_are_safe_and_intentional_hebrew_messages_survive(self):
        cases = [
            ('[cpi, gone, gone, gone, gone]', 'core', 'cpi', GENERIC),
            ('[cpi, boi, gone, fx, gone]', 'fxtable', 'fx', GENERIC),
            ('[gone, boi, gone, fx, gone]', None, 'cpi', GENERIC),
            ("[{status: 'rejected', reason: new Error('לא ניתן לטעון את מדד המחירים לצרכן')}, boi, gone, fx, gone]",
             None, 'cpi', 'לא ניתן לטעון את מדד המחירים לצרכן'),
            ('[cpi, here({}), gone, fx, gone]', None, 'boi', 'הריבית הנוכחית חסרה'),
            ("[{status: 'rejected', reason: undefined}, boi, gone, fx, gone]", None, 'cpi', GENERIC),
        ]
        for results, missing, card, expected in cases:
            with self.subTest(results=results, missing=missing):
                seen = self.run_app(results, missing)
                self.assertEqual(seen['errors'][card], expected)
                affected = {'cpi': ['cpi-kpi', 'chart-section', 'calculator-section'],
                            'boi': ['boi-kpi'], 'fx': ['fx-kpi', 'fx-table-section']}[card]
                for id_ in affected:
                    self.assertIn({'id': id_, 'state': 'error', 'message': expected}, seen['states'])
                self.assertEqual(seen['events'], ['statso:app-ready'])
                self.assertEqual(seen['direct'], [GENERIC, GENERIC, GENERIC, 'הודעה בעברית'])


# The same DOM setup exercises route(), focusView(), updateTitle(), and init().
NAV_SETUP = r"""
const els = {}, focuses = [], siteTitle = 'statso — site';
let scrolls = 0, resizes = 0, languageChanged;
function heading(textContent) { return {textContent, attrs: {}, hasAttribute(k) { return k in this.attrs; },
 setAttribute(k, v) { this.attrs[k] = v; }, focus() { focuses.push(this.textContent); }}; }
const infoIds = ['about-page', 'method-page', 'terms-page', 'privacy-page', 'accessibility-page', 'contact-page', 'notfound-page'];
const toolIds = ['tool-index-page', 'tool-fx-page', 'tool-history-page', 'tool-rate-history-page', 'tool-fx-history-page', 'tool-rent-page'];
const viewIds = ['dashboard-view', 'tools-view', 'guides-view', 'mcode-view', 'info-view'];
for (const id of infoIds.concat(toolIds)) {
 els[id] = {id, hidden: true, heading: heading(id === 'notfound-page' ? 'הדף לא נמצא' : id)};
}
for (const id of viewIds) {
 els[id] = {id, hidden: true, heading: heading(id),
  querySelectorAll(selector) { return (selector === '.info-page' ? infoIds : selector === '.tool-page' ? toolIds : []).map(id => els[id]); },
  querySelector(selector) {
   if (selector === '.info-page:not([hidden]) h1' && id === 'info-view') {
    const page = infoIds.map(id => els[id]).find(p => !p.hidden); return page ? page.heading : null;
   }
   if (selector === '.tool-page:not([hidden]) h2' && id === 'tools-view') {
    const page = toolIds.map(id => els[id]).find(p => !p.hidden); return page ? page.heading : null;
   }
   return selector === 'h1' ? this.heading : null;
  }};
}
els['tools-index'] = {hidden: true};
const links = ['#/', '#/guides', '#/tools', '#/mcode'].map(href => ({href, attrs: {},
 getAttribute(k) { return k === 'href' ? href : this.attrs[k]; }, setAttribute(k, v) { this.attrs[k] = v; },
 removeAttribute(k) { delete this.attrs[k]; }}));
global.document = {title: siteTitle, addEventListener() {}, getElementById(id) { return els[id] || null; },
 querySelector(selector) { return selector === 'main:not([hidden])' ? viewIds.map(id => els[id]).find(v => !v.hidden) : null; },
 querySelectorAll(selector) { return selector === '.site-nav a' ? links : []; }};
global.window = {location: {hash: '#/'}, addEventListener() {}, scrollTo() { scrolls++; },
 requestAnimationFrame(fn) { fn(); }, setTimeout(fn) { fn(); },
 Statso: {guides: {guides: [{id: 'excel'}, {id: 'cpi-terms'}, {id: 'live-pull', soon: true}],
 showGuide() { return true; }, showIndex() {}}, mcode: {render() {}}, chart: {resize() { resizes++; }},
 i18n: {t: text => text, onChange(fn) { languageChanged = fn; }}}};
function go(hash) { window.location.hash = hash; window.Statso.nav.route(); }
function snapshot() { return {views: viewIds.filter(id => !els[id].hidden),
 info: infoIds.filter(id => !els[id].hidden), tools: toolIds.filter(id => !els[id].hidden),
 toolsIndex: !els['tools-index'].hidden, focus: focuses[focuses.length - 1], title: document.title,
 active: links.filter(l => l.attrs['aria-current'] === 'page').map(l => l.href), scrolls, resizes}; }
"""


def nav_run(body):
    return node(NAV_SETUP + module('statso-nav.js') + '\nwindow.Statso.nav.init();\n' + body)


class BrandLinkTests(unittest.TestCase):
    def test_brand_uses_the_same_hash_as_the_home_nav_without_a_special_listener(self):
        self.assertIn('<a class="brand" href="#/"', HTML)
        self.assertNotIn('href="index.html"', HTML)
        brand = re.search(r'<a class="brand" href="([^"]+)"', HTML).group(1)
        home = re.search(r'<a class="[^"]*\bnav-home\b[^"]*" href="([^"]+)"', HTML).group(1)
        self.assertEqual(brand, home)
        self.assertNotIn('.brand', (ROOT / 'assets/statso-nav.js').read_text(encoding='utf-8'))

    def test_home_route_restores_dashboard_focus_title_and_current_link(self):
        seen = nav_run("go('#/about'); go('#/'); process.stdout.write(JSON.stringify(snapshot()));")
        self.assertEqual(seen['views'], ['dashboard-view'])
        self.assertEqual(seen['focus'], 'dashboard-view')
        self.assertEqual(seen['active'], ['#/'])
        self.assertEqual(seen['title'], 'statso — site')
        self.assertEqual(seen['info'], [])


class NotFoundRouteTests(unittest.TestCase):
    def test_unknown_hashes_show_only_not_found_and_never_throw(self):
        hashes = ['#/nonexistent', '#/tools/xyz', '#/guides/xyz', '#/Guides', '#/tools/', '#/tools/index/extra',
                  '#/%E0%A4%A', '#/guides/live-pull', '#/guides/', '#/__proto__', '#/guides/constructor']
        seen = nav_run(r"""
const results = %s.map(hash => {
 go('#/about'); const before = {scrolls, resizes, focuses: focuses.length}; let error = null;
 try { go(hash); } catch (e) { error = String(e); }
 return {hash, before, after: snapshot(), focusCount: focuses.length, error};
});
process.stdout.write(JSON.stringify(results));
""" % json.dumps(hashes))
        for result in seen:
            with self.subTest(hash=result['hash']):
                self.assertIsNone(result['error'])
                after = result['after']
                self.assertEqual(after['views'], ['info-view'])
                self.assertEqual(after['info'], ['notfound-page'])
                self.assertEqual(after['tools'], [])
                self.assertEqual(after['focus'], 'הדף לא נמצא')
                self.assertEqual(after['title'], 'הדף לא נמצא — statso')
                self.assertEqual(after['active'], [])
                self.assertEqual(after['scrolls'], result['before']['scrolls'] + 1)
                self.assertEqual(after['resizes'], result['before']['resizes'])
                self.assertEqual(result['focusCount'], result['before']['focuses'] + 1)

    def test_every_valid_route_keeps_its_own_view_and_page(self):
        routes = [(hash_, 'dashboard-view', None) for hash_ in ('', '#', '#/')]
        routes += [('#/tools', 'tools-view', None), ('#/guides', 'guides-view', None),
                   ('#/guides/excel', 'guides-view', None), ('#/guides/cpi-terms', 'guides-view', None),
                   ('#/mcode', 'mcode-view', None)]
        routes += [('#/tools/' + slug, 'tools-view', 'tool-' + slug + '-page')
                   for slug in ('index', 'fx', 'history', 'rate-history', 'fx-history', 'rent')]
        routes += [('#/' + slug, 'info-view', slug + '-page')
                   for slug in ('about', 'method', 'terms', 'privacy', 'accessibility', 'contact')]
        seen = nav_run("const results = " + json.dumps(routes) + r""".map(([hash]) => {
 go('#/nonexistent'); go(hash); return snapshot();
}); process.stdout.write(JSON.stringify(results));
""")
        for (hash_, view, page), result in zip(routes, seen):
            with self.subTest(hash=hash_):
                self.assertEqual(result['views'], [view])
                self.assertEqual(result['info'], [page] if view == 'info-view' else [])
                self.assertEqual(result['tools'], [page] if view == 'tools-view' and page else [])
                if view == 'tools-view':
                    self.assertEqual(result['toolsIndex'], page is None)

    def test_not_found_title_follows_the_language(self):
        seen = nav_run(r"""
go('#/nonexistent'); els['notfound-page'].heading.textContent = 'Page not found'; languageChanged();
process.stdout.write(JSON.stringify(snapshot()));
""")
        self.assertEqual(seen['title'], 'Page not found — statso')

    def test_not_found_markup_has_one_named_heading_and_translated_destinations(self):
        page = re.search(r'<article[^>]*id="notfound-page".*?</article>', HTML, re.S).group(0)
        self.assertIn('hidden aria-labelledby="notfound-title"', page)
        self.assertEqual(len(re.findall(r'<h1\b', page)), 1)
        self.assertIn('<h1 id="notfound-title">הדף לא נמצא</h1>', page)
        self.assertIn('<h2>לאן אפשר להמשיך</h2>', page)
        self.assertEqual(re.findall(r'href="([^"]+)"', page), ['#/', '#/tools', '#/guides'])
        self.assertNotIn('data-lang', page)
        keys = dictionary_keys()
        for text in re.split(r'<[^>]+>', page):
            if re.search(r'[֐-׿]', text):
                self.assertIn(text.strip(), keys)


class StatementDateTests(unittest.TestCase):
    def test_visible_dates_match_each_other_and_the_machine_readable_date(self):
        months = {'he': 'ינואר פברואר מרץ אפריל מאי יוני יולי אוגוסט ספטמבר אוקטובר נובמבר דצמבר'.split(),
                  'en': 'January February March April May June July August September October November December'.split()}
        dates = []
        for lang, block in statement_blocks().items():
            values = re.findall(r'<time datetime="(\d{4})-(\d{2})-(\d{2})">(.*?)</time>', block)
            self.assertEqual(len(values), 1)
            y, m, d, visible = values[0]
            prefix = 'ב' if lang == 'he' else ''
            self.assertEqual(visible, f'{int(d)} {prefix}{months[lang][int(m)-1]} {y}')
            dates.append(f'{y}-{m}-{d}')
        self.assertEqual(len(dates), 2)
        self.assertEqual(dates[0], dates[1])

    def test_statement_text_changes_require_a_date_review(self):
        dates = [re.search(r'<time datetime="([^"]+)"', block).group(1) for block in statement_blocks().values()]
        self.assertEqual(dates, [STATEMENT_DATE, STATEMENT_DATE],
                         'The statement date changed but STATEMENT_DATE did not: after re-checking the statement, run '
                         'python3 -m scripts.update_statement_date --reviewed')
        self.assertEqual(fingerprint(HTML), STATEMENT_FINGERPRINT,
                         'The accessibility statement text changed: re-check that every sentence is supported by code, '
                         'tests or a check actually performed, then run python3 -m scripts.update_statement_date --reviewed '
                         '(it sets both <time> elements to the review date and updates STATEMENT_DATE and STATEMENT_FINGERPRINT).')

    def test_statement_discloses_conformance_limits_and_all_five_new_bullets(self):
        blocks = statement_blocks()
        phrases = {
            'he': ['אינו טוען להתאמה מלאה', 'ביקורת נגישות מקצועית חיצונית',
                   'כתובת בתוך האתר שאינה מובילה לעמוד קיים', 'כתובת שאינה קיימת בשרת של האתר',
                   'כשאחד מקובצי הסקריפט של האתר אינו נטען', 'ההודעה על חלק מהאתר שלא נטען מזהה רק',
                   'חסימת הטעינה של כל אחד מקובצי הסקריפט של האתר בתורו'],
            'en': ['does not claim full conformance', 'No external professional accessibility audit',
                   'An address inside the site that does not lead to an existing page',
                   "An address that does not exist on the site's server", "When one of the site's script files does not load",
                   'The notice about part of the site not loading detects only',
                   "Blocking each of the site's script files from loading in turn"],
        }
        for lang, texts in phrases.items():
            for text in texts[:2]:
                self.assertIn(text, blocks[lang])
            bullets = re.findall(r'<li>(.*?)</li>', blocks[lang], re.S)
            for text in texts[2:]:
                self.assertEqual(sum(text in bullet for bullet in bullets), 1)
        self.assertEqual(blocks['he'].count('<li>'), blocks['en'].count('<li>'))


class NotFoundPageFileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / '404.html').read_text(encoding='utf-8')
        cls.css = re.search(r'<style>(.*?)</style>', cls.html, re.S).group(1)

    def test_standalone_page_is_semantic_and_bilingual(self):
        self.assertTrue(self.html.startswith('<!DOCTYPE html>'))
        self.assertIn('<html lang="he" dir="rtl">', self.html)
        self.assertIn('<meta charset="utf-8">', self.html)
        self.assertIn('<meta name="viewport" content="width=device-width, initial-scale=1">', self.html)
        title = re.search(r'<title>(.*?)</title>', self.html).group(1)
        self.assertRegex(title, r'[֐-׿]')
        self.assertIn('Page not found', title)
        self.assertEqual(len(re.findall(r'<h1\b', self.html)), 1)
        self.assertIn('<main>', self.html)
        for lang, direction in (('he', 'rtl'), ('en', 'ltr')):
            block = re.search(r'<section lang="' + lang + '" dir="' + direction + r'">(.*?)</section>', self.html, re.S).group(1)
            self.assertIn('href="/statso/"', block)
            if lang == 'he':
                self.assertIn('<h1>', block)
            else:
                self.assertIn('<h2>Page not found</h2>', block)
                self.assertNotRegex(block, r'[֐-׿]')
        for forbidden in ('<script', 'src=', '<link', 'assets/', 'url('):
            self.assertNotIn(forbidden, self.html)
        self.assertEqual(re.findall(r'href="([^"]+)"', self.html), ['/statso/', '/statso/'])

    def test_focus_forced_colors_and_narrow_layout_are_supported(self):
        self.assertRegex(self.css, r'a:focus-visible\s*\{[^}]*outline:\s*3px solid')
        self.assertNotRegex(self.css, r'outline:\s*(?:none|0)\b')
        self.assertIn('@media (forced-colors: active)', self.css)
        self.assertIn('outline-color: Highlight', self.css)
        body = re.search(r'body\s*\{([^}]+)\}', self.css).group(1)
        self.assertIn('overflow-wrap: anywhere', body)
        self.assertNotRegex(self.css, r'\bwidth:\s*\d{3,}px')

    def test_text_and_link_colors_meet_normal_text_contrast(self):
        def luminance(color):
            channels = [int(color[i:i+2], 16) / 255 for i in (1, 3, 5)]
            linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in channels]
            return sum(v * weight for v, weight in zip(linear, (.2126, .7152, .0722)))

        body = re.search(r'body\s*\{([^}]+)\}', self.css).group(1)
        link = re.search(r'\ba\s*\{([^}]+)\}', self.css).group(1)
        background = re.search(r'background:\s*(#[0-9a-f]{6})', body).group(1)
        for rule in (body, link):
            color = re.search(r'\bcolor:\s*(#[0-9a-f]{6})', rule).group(1)
            light, dark = sorted((luminance(color), luminance(background)), reverse=True)
            self.assertGreaterEqual((light + .05) / (dark + .05), 4.5)

    def test_standalone_404_is_not_included_in_offline_artifact(self):
        self.assertNotIn('The address you opened does not exist on statso', offline_html())


if __name__ == '__main__':
    unittest.main()
