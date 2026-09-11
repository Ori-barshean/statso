import csv
import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent
MODULES = ['statso-core.js', 'statso-guide-art.js', 'statso-guides.js', 'statso-mcode.js']


def node(body, setup='global.document = {addEventListener() {}};', modules=MODULES):
    script = 'global.window = {};\n' + setup + '\n'
    script += '\n'.join('require(' + json.dumps(str(ROOT / 'assets' / name)) + ');' for name in modules)
    script += '\nconst S = window.Statso;\n' + body
    return json.loads(subprocess.run(['node', '-e', script], check=True, capture_output=True, text=True).stdout)


class McodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.samples = node('''
const out = {};
for (const series of ['boi', 'cpi', 'fx']) {
  for (const currencies of (series === 'fx' ? [['usd'], ['usd', 'eur'], S.mcode.CURRENCIES] : [[]])) {
    for (const average of [false, true]) {
      const selection = {series, currencies, from: '2022-12-01', to: '2025-12-31', average};
      out[[series, currencies.length, average].join('/')] = S.mcode.generate(selection);
    }
  }
}
process.stdout.write(JSON.stringify(out));
''')
        cls.source = (ROOT / 'assets/statso-mcode.js').read_text()

    def test_boi_carries_forward_change_before_start(self):
        code = self.samples['boi/0/false']
        for expected in ('#date(2022, 12, 1)', '#date(2025, 12, 31)', 'Encoding = 65001',
                         'data/boi_interest_rate.csv', '"boi_rate"',
                         'Table.SelectRows(Typed, each [date] < From)', 'Table.LastN(Earlier, 1)',
                         'Table.Combine({Carried, InRange})', 'Table.Sort(Combined, {{"date", Order.Ascending}})'):
            self.assertIn(expected, code)
        for token in ('chained_1951_09', 'NestedJoin'):
            self.assertNotIn(token, code)
        order = ['InRange =', 'Earlier =', 'Carried =', 'Combined =', 'Sorted =', 'Result =']
        self.assertEqual(sorted(order, key=code.index), order)
        with (ROOT / 'data/boi_interest_rate.csv').open(encoding='utf-8-sig') as handle:
            rows = list(csv.DictReader(handle))
        before = max((r for r in rows if r['date'] < '2022-12-01'), key=lambda r: r['date'])
        inside = sorted((r for r in rows if '2022-12-01' <= r['date'] <= '2025-12-31'), key=lambda r: r['date'])
        self.assertEqual([(r['date'], float(r['rate'])) for r in [before] + inside], [
            ('2022-11-24', 3.25), ('2023-01-05', 3.75), ('2023-02-23', 4.25),
            ('2023-04-07', 4.5), ('2023-05-25', 4.75), ('2024-01-04', 4.5), ('2025-11-27', 4.25)])

    def test_cpi_exports_only_chained_index(self):
        code = self.samples['cpi/0/false']
        for expected in ('Table.SelectColumns(Promoted, {"month", "chained_1951_09"})',
                         '"cpi_chained"', '"2022-12"', '"2025-12"', 'September 1951 average'):
            self.assertIn(expected, code)
        self.assertNotIn('"value"', code.split('\nlet\n')[1])
        self.assertNotIn('#date(', code)

    def test_single_currency(self):
        code = self.samples['fx/1/false']
        self.assertEqual(code.count('Web.Contents('), 1)
        self.assertIn('data/fx/usd_ils.csv', code)
        self.assertIn('"usd_ils"', code)
        self.assertNotIn('NestedJoin', code)

    def test_multi_currency_spine_and_literal_urls(self):
        for count in (2, 10):
            code = self.samples[f'fx/{count}/false']
            self.assertIn('Spine =', code)
            self.assertEqual(code.count('Table.NestedJoin('), count)
            self.assertEqual(code.count('Table.ExpandTableColumn('), count)
            self.assertEqual(code.count('JoinKind.LeftOuter'), count)
            urls = re.findall(r'Web.Contents\("([^"]+)"\)', code)
            self.assertEqual(len(set(urls)), count)
            self.assertNotIn('JoinKind.FullOuter', code)
            self.assertIn('"usd_ils"', code)
            self.assertIn('"eur_ils"', code)
            self.assertIn('WithUsd, {"date"}, Eur', code)

    def test_average_is_final_simple_mean_with_null_key(self):
        for name, code in self.samples.items():
            if name.endswith('false'):
                self.assertNotIn('Table.InsertRows(', code)
                continue
            self.assertIn('Result = Table.InsertRows(', code)
            self.assertIn('Table.RowCount(', code)
            self.assertIn('List.Average(List.RemoveNulls(', code)
            key = 'month' if name.startswith('cpi') else 'date'
            self.assertIn('{[' + key + ' = null, ', code)
            count = int(name.split('/')[1]) or 1
            self.assertEqual(code.count('List.Average('), count)
            self.assertTrue(code.endswith('\nin\n    Result'))

    def test_ascii_and_offline_safety(self):
        for code in self.samples.values():
            self.assertTrue(code.isascii())
        for code in [self.source] + list(self.samples.values()):
            for token in ('</script', '</style', '<!--', '-->', ' defer', ' async'):
                self.assertNotIn(token, code)
        self.assertNotIn('raw.githubusercontent.com', self.source)

    def test_guide_example_is_identical_in_both_load_orders(self):
        body = '''
process.stdout.write(JSON.stringify(['boi', 'cpi'].map(series => {
 const steps = S.guides.getSteps('mac', 'power', series);
 return {embedded: steps[2].code, generated: S.mcode.generate({series, currencies: [], from: '2022-12-01', to: '2025-12-31', average: false}), hasUrl: steps.some(s => s.url)};
})));
'''
        for modules in (MODULES, MODULES[:2] + [MODULES[3], MODULES[2]]):
            for row in node(body, modules=modules):
                self.assertEqual(row['embedded'], row['generated'])
                self.assertFalse(row['hasUrl'])

    def test_validation_clears_code_without_generating(self):
        out = node('''
const results = [];
S.mcode.generate = () => { throw new Error('unexpected public generator'); };
// Removing URLs also makes a call to the internal generator fail.
S.guides = null;
for (const choice of [
 {from: '', to: ''}, {from: '2022-12-01', to: ''},
 {from: '', to: '2025-12-31'}, {from: '2025-12-31', to: '2022-12-01'},
 {series: 'fx', from: '2022-12-01', to: '2025-12-31'}
]) {
 series.value = choice.series || 'boi';
 els['mc-from'].value = choice.from; els['mc-to'].value = choice.to;
 S.mcode.render();
 results.push([els['mc-error'].textContent, els['mc-code'].textContent, els['mc-copy'].disabled, els['mc-currencies-block'].hidden]);
}
process.stdout.write(JSON.stringify(results));
''', setup='''
const els = Object.fromEntries(['mc-from', 'mc-to', 'mc-average', 'mc-currencies-block', 'mc-error', 'mc-code', 'mc-copy'].map(id => [id, {textContent: 'stale', checked: false}]));
const series = {value: 'boi'};
global.document = {addEventListener() {}, getElementById(id) { return els[id]; }, querySelector() { return series; }, querySelectorAll() { return []; }};
''')
        self.assertEqual([row[0] for row in out], ['יש לבחור תאריך התחלה ותאריך סיום.'] * 3 + [
            'תאריך ההתחלה חייב להיות לפני תאריך הסיום.', 'יש לבחור מטבע אחד לפחות.'])
        self.assertTrue(all(row[1] == '' and row[2] for row in out))
        self.assertFalse(out[-1][3])

    def test_init_defaults_wires_inputs_and_copies_generated_code(self):
        out = node(''' 
const allInputs = Array.from({length: 16}, () => ({events: {}, addEventListener(event, fn) { this.events[event] = fn; }}));
document.querySelectorAll = selector => selector === '#mcode-view input' ? allInputs : [];
S.mcode.init();
els['mc-copy'].events.click();
Promise.resolve().then(() => process.stdout.write(JSON.stringify({
 from: els['mc-from'].value, to: els['mc-to'].value,
 expectedFrom: (new Date().getFullYear() - 3) + '-' + String(new Date().getMonth() + 1).padStart(2, '0') + '-01',
 expectedTo: new Date().getFullYear() + '-' + String(new Date().getMonth() + 1).padStart(2, '0') + '-' + String(new Date().getDate()).padStart(2, '0'),
 currencies: els['mc-currencies'].innerHTML, code: els['mc-code'].textContent,
 copied, wired: allInputs.every(i => i.events.input && i.events.change)
})));
''', setup='''
const els = {}, copied = [];
Object.defineProperty(global, 'navigator', {value: {clipboard: {writeText(text) { copied.push(text); return Promise.resolve(); }}}});
window.setTimeout = () => {};
global.document = {addEventListener() {},
 getElementById(id) { return els[id] || (els[id] = {checked: false, events: {}, addEventListener(event, fn) { this.events[event] = fn; }}); },
 querySelector() { return {value: 'boi'}; }};
''')
        self.assertEqual(out['from'], out['expectedFrom'])
        self.assertEqual(out['to'], out['expectedTo'])
        self.assertEqual(out['currencies'].count('type="checkbox"'), 10)
        self.assertEqual(out['copied'], [out['code']])
        self.assertTrue(out['wired'])

    def test_mcode_route_preserves_focus_and_dashboard_fallback(self):
        out = node('''
let renders = 0, resizes = 0;
S.mcode = {render() { renders++; }};
S.chart = {resize() { resizes++; }};
window.location = {hash: '#/'};
window.scrollTo = () => {};
window.requestAnimationFrame = fn => fn();
S.nav.route();
window.location.hash = '#/mcode'; S.nav.route();
const mcode = {visible: !els['mcode-view'].hidden, dashboardHidden: els['dashboard-view'].hidden,
 active: links.filter(l => l.attrs['aria-current']).map(l => l.href), renders, resizes, focuses};
window.location.hash = '#/unknown'; S.nav.route();
process.stdout.write(JSON.stringify({mcode, fallback: !els['dashboard-view'].hidden && els['mcode-view'].hidden}));
''', setup='''
const els = {}; let focuses = 0;
const heading = {hasAttribute() { return false; }, setAttribute() {}, focus() { focuses++; }};
const links = ['#/', '#/guides', '#/tools', '#/mcode'].map(href => ({href, attrs: {},
 getAttribute() { return href; }, setAttribute(k, v) { this.attrs[k] = v; }, removeAttribute(k) { delete this.attrs[k]; }}));
global.document = {addEventListener() {},
 getElementById(id) { if (id === 'tools-trigger') { return null; } return els[id] || (els[id] = {hidden: false, querySelectorAll() { return []; }}); },
 querySelector() { return {querySelector() { return heading; }}; }, querySelectorAll() { return links; }};
''', modules=['statso-nav.js'])
        self.assertEqual(out['mcode'], {'visible': True, 'dashboardHidden': True, 'active': ['#/mcode'],
                                       'renders': 1, 'resizes': 1, 'focuses': 1})
        self.assertTrue(out['fallback'])

    def test_placeholder_is_noninteractive(self):
        html = node('''
callbacks[0]();
process.stdout.write(JSON.stringify(els['guide-cards'].innerHTML));
''', setup='''
const callbacks = [], els = {};
global.document = {addEventListener(event, fn) { callbacks.push(fn); },
 getElementById(id) { return els[id] || (els[id] = {innerHTML: '', addEventListener() {}}); }, querySelectorAll() { return []; }};
''', modules=MODULES[:3])
        card = re.search(r'<div class="guide-card guide-card-soon".*?</div>', html).group()
        self.assertIn('aria-disabled="true"', card)
        self.assertNotIn('data-guide', card)
        self.assertNotIn('<button', card)


if __name__ == '__main__':
    unittest.main()
