import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def node(setup, modules, body):
    script = 'global.window = {};\n' + setup + '\n'
    script += '\n'.join('require(' + json.dumps(str(ROOT / 'assets' / name)) + ');'
                        for name in modules)
    result = subprocess.run(['node', '-e', script + '\n' + body], cwd=ROOT,
                            capture_output=True, text=True, encoding='utf-8')
    if result.returncode:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


class A11yPagesSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / 'index.html').read_text(encoding='utf-8')

    def blocks(self, page):
        article = re.search(r'<article[^>]*id="' + page + r'-page".*?</article>',
                            self.html, re.DOTALL).group()
        blocks = re.findall(r'<div class="prose-guide" data-lang="(he|en)"[^>]*>'
                            r'(.*?)</div>', article, re.DOTALL)
        self.assertEqual([lang for lang, _ in blocks], ['he', 'en'])
        return dict(blocks)

    def test_guide_routes_return_to_index_and_unknown_ids_are_not_found(self):
        seen = node('''
const els = {}, calls = []; let focuses = 0, headingText = 'Guides';
const heading = {get textContent() { return headingText; },
 hasAttribute() { return false; }, setAttribute() {}, focus() { focuses++; }};
const links = ['#/', '#/guides', '#/tools', '#/mcode'].map(href => ({href, attrs: {},
 getAttribute() { return href; }, setAttribute(k, v) { this.attrs[k] = v; },
 removeAttribute(k) { delete this.attrs[k]; }}));
global.document = {title: 'statso', addEventListener() {},
 getElementById(id) { if (id === 'tools-trigger') { return null; }
  return els[id] || (els[id] = {hidden: false, querySelectorAll() { return []; }}); },
 querySelector() { return {querySelector() { return heading; }}; },
 querySelectorAll() { return links; }};
window.location = {hash: '#/guides'};
window.scrollTo = () => {};
window.requestAnimationFrame = fn => fn();
window.Statso = {guides: {
 guides: [{id: 'excel'}, {id: 'cpi-terms'}, {id: 'live-pull'}, {id: 'future-guide', soon: true}],
 showIndex(fromRoute) { calls.push(['index', fromRoute]); headingText = 'Guides'; },
 showGuide(id, fromRoute) { calls.push(['guide', id, fromRoute]);
  if (id !== 'excel') { return false; } headingText = 'Excel'; return true; }
}};
''', ['statso-nav.js'], '''
const views = [];
for (const hash of ['#/guides', '#/guides/excel', '#/guides', '#/guides/nope', '#/guides/future-guide']) {
 window.location.hash = hash; window.Statso.nav.route();
 views.push({dashboardHidden: els['dashboard-view'].hidden, guidesHidden: els['guides-view'].hidden,
  infoHidden: els['info-view'].hidden,
  active: links.filter(l => l.attrs['aria-current']).map(l => l.href), focuses, title: document.title});
}
delete window.Statso.guides;
window.location.hash = '#/guides/excel'; window.Statso.nav.route();
const missingModule = els['dashboard-view'].hidden && !els['guides-view'].hidden && els['info-view'].hidden;
window.location.hash = '#/unknown'; window.Statso.nav.route();
process.stdout.write(JSON.stringify({calls, views, missingModule,
 fallback: els['dashboard-view'].hidden && els['guides-view'].hidden && !els['info-view'].hidden}));
''')
        self.assertEqual(seen['calls'], [['index', True], ['guide', 'excel', True], ['index', True]])
        for i, view in enumerate(seen['views']):
            self.assertTrue(view['dashboardHidden'])
            self.assertEqual(view['guidesHidden'], i >= 3)
            self.assertEqual(view['infoHidden'], i < 3)
            self.assertEqual(view['active'], ['#/guides'] if i < 3 else [])
            self.assertEqual(view['focuses'], i)
            if i < 3:
                self.assertEqual(view['title'], ('Excel' if i == 1 else 'Guides') + ' — statso')
        self.assertTrue(seen['missingModule'])
        self.assertTrue(seen['fallback'])

    def test_guide_links_and_id_validation(self):
        seen = node('''
const callbacks = [], els = {}; let scrolls = 0, focuses = 0;
function element() { return {hidden: false, innerHTML: '', setAttribute() {}, addEventListener() {}}; }
global.document = {addEventListener(event, fn) { callbacks.push(fn); },
 getElementById(id) { return els[id] || (els[id] = element()); },
 querySelector(selector) { return selector === '.guide-steps-host' ?
  (els.steps || (els.steps = element())) : null; }, querySelectorAll() { return []; }};
window.scrollTo = () => { scrolls++; };
''', ['statso-core.js', 'statso-guide-art.js', 'statso-guides.js'], '''
const G = window.Statso.guides;
G.guides.push({id: 'future-guide', soon: true, title: 'מדריך עתידי — בקרוב', description: 'בהכנה.'});
window.Statso.nav = {focusView() { focuses++; }};
callbacks[0]();
document.getElementById('guides-index').hidden = false;
document.getElementById('guide-detail').hidden = true;
const before = JSON.stringify(els);
const invalid = [G.showGuide('nope', true), G.showGuide('future-guide', true)];
const unchanged = before === JSON.stringify(els), invalidScrolls = scrolls;
const opened = G.showGuide('excel', true);
const detail = {indexHidden: els['guides-index'].hidden, hidden: els['guide-detail'].hidden,
 content: els['guide-content'].innerHTML, scrolls, focuses};
G.showIndex(true);
const returned = {indexHidden: els['guides-index'].hidden, hidden: els['guide-detail'].hidden, focuses};
G.showGuide('cpi-terms');
const live = G.showGuide('live-pull', true), liveContent = els['guide-content'].innerHTML;
process.stdout.write(JSON.stringify({cards: els['guide-cards'].innerHTML,
 invalid, unchanged, invalidScrolls, opened, detail, returned, focuses, live, liveContent}));
''')
        for guide in ('excel', 'cpi-terms', 'live-pull'):
            self.assertIn('<a class="guide-card" href="#/guides/' + guide + '">', seen['cards'])
        self.assertNotIn('href="#/guides/future-guide"', seen['cards'])
        self.assertTrue(seen['live'])
        self.assertIn('id="live-pull-guide-title"', seen['liveContent'])
        self.assertEqual(seen['invalid'], [False, False])
        self.assertTrue(seen['unchanged'])
        self.assertEqual(seen['invalidScrolls'], 0)
        self.assertTrue(seen['opened'])
        self.assertTrue(seen['detail']['indexHidden'])
        self.assertFalse(seen['detail']['hidden'])
        self.assertIn('id="excel-guide-title"', seen['detail']['content'])
        self.assertEqual(seen['detail']['scrolls'], 1)
        self.assertEqual(seen['detail']['focuses'], 0)
        self.assertEqual(seen['returned'], {'indexHidden': False, 'hidden': True, 'focuses': 0})
        self.assertEqual(seen['focuses'], 1)

    def test_open_guide_is_translated_before_focus_and_title(self):
        seen = node('''
const callbacks = [], els = {}; let scrolls = 0, focuses = 0;
function element() { return {hidden: false, innerHTML: '', setAttribute() {}, addEventListener() {}}; }
global.document = {addEventListener(event, fn) { callbacks.push(fn); },
 getElementById(id) { return els[id] || (els[id] = element()); },
 querySelector(selector) { return selector === '.guide-steps-host' ?
  (els.steps || (els.steps = element())) : null; }, querySelectorAll() { return []; }};
window.scrollTo = () => { scrolls++; };
''', ['statso-core.js', 'statso-guide-art.js', 'statso-guides.js'], '''
const G = window.Statso.guides, calls = [];
G.guides.push({id: 'future-guide', soon: true});
window.Statso.i18n = {current: () => 'en', onChange() {}, apply(target) {
  calls.push(['apply', target === els['guide-detail'], !target.hidden,
    els['guide-content'].innerHTML.indexOf('-guide-title"') > 0]); }};
window.Statso.nav = {focusView() { calls.push(['focus']); }};
G.showGuide('excel'); G.showGuide('cpi-terms', true); G.showGuide('live-pull'); G.showGuide('future-guide');
process.stdout.write(JSON.stringify(calls));
''')
        self.assertEqual(seen, [['apply', True, True, True], ['focus'], ['apply', True, True, True],
                                ['apply', True, True, True], ['focus']])

    def test_information_pages_have_parallel_semantic_structure(self):
        for page in ('about', 'privacy', 'terms', 'accessibility'):
            with self.subTest(page=page):
                blocks = self.blocks(page)
                counts = [{tag: len(re.findall('<' + tag + r'\b', block))
                           for tag in ('h2', 'h3', 'ul', 'li')} for block in blocks.values()]
                self.assertEqual(counts[0], counts[1])
                self.assertGreaterEqual(counts[0]['h2'], 2)
                for block in blocks.values():
                    self.assertNotRegex(block, r'<(?:h1|div)\b')
                    sections = re.findall(r'<section>(.*?)</section>', block, re.DOTALL)
                    self.assertEqual(len(sections), counts[0]['h2'])
                    for section in sections:
                        self.assertRegex(section, r'^\s*<h2>')
                self.assertNotRegex(blocks['en'], r'[\u0590-\u05ff]')

    def test_statement_has_five_sections_and_five_accommodation_groups(self):
        for lang, block in self.blocks('accessibility').items():
            with self.subTest(lang=lang):
                self.assertEqual(block.count('<h2>'), 5)
                self.assertEqual(block.count('<h3>'), 5)
                self.assertEqual(len(re.findall(r'</h3>\s*<ul class="info-list">', block)), 5)
                for paragraph in re.findall(r'<p>(.*?)</p>', block, re.DOTALL):
                    self.assertLessEqual(len(paragraph), 700)
                self.assertGreaterEqual(block.count('<li>'), 40)

    def test_statement_has_the_same_number_of_list_items_in_both_languages(self):
        blocks = self.blocks('accessibility')
        self.assertEqual(blocks['he'].count('<li>'), blocks['en'].count('<li>'))

    def test_privacy_preferences_are_two_list_items(self):
        for block in self.blocks('privacy').values():
            lists = re.findall(r'<ul class="info-list">(.*?)</ul>', block, re.DOTALL)
            self.assertEqual(len(lists), 1)
            self.assertEqual(lists[0].count('<li>'), 2)


if __name__ == '__main__':
    unittest.main()
