import csv
import hashlib
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
for (const series of ['boi', 'cpi', 'construction', 'fx']) {
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

    def test_construction_exports_only_chained_index(self):
        code = self.samples['construction/0/false']
        for expected in ('Table.SelectColumns(Promoted, {"month", "chained_1950_07"})',
                         '"construction_chained"', '"2022-12"', '"2025-12"',
                         'data/construction_inputs.csv', 'July 1950', 'January 2000'):
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
            key = 'month' if name.startswith(('cpi', 'construction')) else 'date'
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
const steps = S.guides.getSteps('mac', 'power');
process.stdout.write(JSON.stringify({embedded: steps[2].code,
 generated: S.mcode.generate({series: 'boi', currencies: [], from: '2022-12-01', to: '2025-12-31', average: false}),
 hasUrl: steps.some(s => s.url)}));
'''
        for modules in (MODULES, MODULES[:2] + [MODULES[3], MODULES[2]]):
            row = node(body, modules=modules)
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
 {series: ['fx'], from: '2022-12-01', to: '2025-12-31'},
 {series: [], from: '2022-12-01', to: '2025-12-31'},
 {series: ['boi', 'fx'], from: '2022-12-01', to: '2025-12-31'}
]) {
 ticked = (choice.series || ['boi']).map(value => ({value}));
 els['mc-from'].value = choice.from; els['mc-to'].value = choice.to;
 S.mcode.render();
 results.push([els['mc-error'].textContent, els['mc-code'].textContent, els['mc-copy'].disabled, els['mc-currencies-block'].hidden]);
}
process.stdout.write(JSON.stringify(results));
''', setup='''
const els = Object.fromEntries(['mc-from', 'mc-to', 'mc-average', 'mc-currencies-block', 'mc-error', 'mc-code', 'mc-copy'].map(id => {
  const attrs = {};
  return [id, {textContent: 'stale', checked: false, setAttribute(k, v) { attrs[k] = String(v); },
    getAttribute(k) { return k in attrs ? attrs[k] : null; }, removeAttribute(k) { delete attrs[k]; }}];
}));
let ticked = [{value: 'boi'}];
global.document = {addEventListener() {}, getElementById(id) { return els[id]; },
 querySelectorAll(selector) { return selector === 'input[name="mc-series"]:checked' ? ticked : []; }};
''')
        self.assertEqual([row[0] for row in out], ['יש לבחור תאריך התחלה ותאריך סיום.'] * 3 + [
            'תאריך ההתחלה חייב להיות לפני תאריך הסיום.', 'יש לבחור מטבע אחד לפחות.',
            'יש לבחור סדרה אחת לפחות.', 'יש לבחור מטבע אחד לפחות.'])
        self.assertTrue(all(row[1] == '' and row[2] for row in out))
        self.assertEqual([row[3] for row in out], [True, True, True, True, False, True, False])

    def test_init_defaults_wires_inputs_and_copies_generated_code(self):
        out = node(''' 
const allInputs = Array.from({length: 16}, () => ({events: {}, addEventListener(event, fn) { this.events[event] = fn; }}));
document.querySelectorAll = selector => selector === '#mcode-view input' ? allInputs :
 selector === 'input[name="mc-series"]:checked' ? [{value: 'boi'}] : [];
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

    def test_mcode_route_preserves_focus_and_unknown_hash_is_not_found(self):
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
process.stdout.write(JSON.stringify({mcode, fallback: els['dashboard-view'].hidden && els['mcode-view'].hidden && !els['info-view'].hidden}));
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
        seen = node('''
callbacks[0]();
const real = els['guide-cards'].innerHTML;
S.guides.guides.push({id: 'future-guide', soon: true, title: 'מדריך עתידי — בקרוב', description: 'בהכנה.'});
callbacks[0]();
process.stdout.write(JSON.stringify({real, stub: els['guide-cards'].innerHTML}));
''', setup='''
const callbacks = [], els = {};
global.document = {addEventListener(event, fn) { callbacks.push(fn); },
 getElementById(id) { return els[id] || (els[id] = {innerHTML: '', addEventListener() {}}); }, querySelectorAll() { return []; }};
''', modules=MODULES[:3])
        self.assertNotIn('guide-card-soon', seen['real'])
        self.assertIn('<a class="guide-card" href="#/guides/live-pull">', seen['real'])
        self.assertNotIn('href="#/guides/future-guide"', seen['stub'])
        card = re.search(r'<div class="guide-card guide-card-soon".*?</div>', seen['stub']).group()
        # plain content that says "soon" in words, not a control dressed as disabled (axe skips aria-disabled)
        self.assertNotIn('aria-disabled', card)
        self.assertNotIn('<a', card)
        self.assertNotIn('data-guide', card)
        self.assertNotIn('<button', card)


class CombinedMcodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # All generation and DOM checks share one Node run, separate from legacy samples.
        cls.out = node('''
const out = {single: {}, combined: {}, errors: [], rendered: []};
const base = {from: '2022-12-01', to: '2025-12-31', average: false};
const generate = selection => S.mcode.generate(Object.assign({}, base, selection));
for (const series of S.mcode.SERIES) {
  for (const currencies of (series === 'fx' ? [['usd'], ['usd', 'eur'], S.mcode.CURRENCIES] : [[]])) {
    for (const average of [false, true]) {
      for (const array of [false, true]) {
        out.single[[series, currencies.length, average, array].join('/')] =
          generate({series: array ? [series] : series, currencies, average});
      }
    }
  }
}
out.leftover = generate({series: ['cpi'], currencies: ['usd']});
for (let mask = 1; mask < 16; mask++) {
  const series = S.mcode.SERIES.filter((name, i) => mask & (1 << i));
  if (series.length < 2) continue;
  for (const currencies of (series.includes('fx') ? [['usd'], ['usd', 'eur'], S.mcode.CURRENCIES] : [[]])) {
    for (const average of [false, true]) {
      out.combined[[series.join('+'), currencies.length, average].join('/')] = generate({series, currencies, average});
    }
  }
}
out.early = generate({series: ['construction', 'fx'], currencies: ['usd'], from: '1995-01-01', to: '2001-12-31'});
out.reordered = generate({series: ['fx', 'construction', 'cpi', 'boi', 'fx', 'unknown'], currencies: ['eur', 'usd', 'eur', 'invalid'], average: true});
out.ordered = generate({series: S.mcode.SERIES, currencies: ['eur', 'usd'], average: true});
out.noFx = generate({series: ['construction', 'cpi'], currencies: ['usd']});
out.futureMonth = generate({series: ['cpi', 'fx'], currencies: ['usd'], to: '2099-12-31'});
out.futureDate = generate({series: ['boi', 'fx'], currencies: ['usd'], to: '2099-12-31'});
for (const selection of [{series: []}, {series: ['unknown']}, {series: ['boi', 'fx']},
                         {series: ['boi', 'fx'], currencies: []}, {series: ['boi', 'fx'], currencies: ['invalid']}]) {
  try { generate(selection); out.errors.push(null); } catch (error) { out.errors.push(error.message); }
}
const els = {};
document.getElementById = id => els[id] || (els[id] = {value: '', textContent: '', checked: false,
 setAttribute() {}, getAttribute() { return null; }, removeAttribute() {}});
document.getElementById('mc-from').value = base.from;
document.getElementById('mc-to').value = base.to;
for (const [series, currencies] of [[['boi', 'cpi'], []], [['boi', 'fx'], ['usd']]]) {
  document.querySelectorAll = selector => selector === 'input[name="mc-series"]:checked' ? series.map(value => ({value})) :
    selector === '#mc-currencies input:checked' ? currencies.map(value => ({value})) : [];
  S.mcode.render();
  out.rendered.push({selection: S.mcode.read(), code: els['mc-code'].textContent,
    error: els['mc-error'].textContent, hidden: els['mc-currencies-block'].hidden, disabled: els['mc-copy'].disabled});
}
out.currencies = S.mcode.CURRENCIES;
out.series = S.mcode.SERIES;
process.stdout.write(JSON.stringify(out));
''')
        cls.samples = cls.out['combined']
        cls.source = (ROOT / 'assets/statso-mcode.js').read_text()

    def code(self, series, count=0, average=False):
        return self.samples[f'{series}/{count}/{str(average).lower()}']

    @staticmethod
    def digest(code):
        return hashlib.sha256(code.encode()).hexdigest()

    @staticmethod
    def block(code, name):
        return re.search(r'^    ' + name + r' = .*?(?=^    \w+ = |^in$)', code, re.M | re.S).group().rstrip(',\n')

    def test_single_series_byte_identity(self):
        hashes = {
            'boi/0/false': '619dbf3dbd306a60e7309b25a89517be4bd0638793bef69ad302a9bb16166342',
            'boi/0/true': 'b04daa44a7d3e842e423ac557ad9becad4c6e45a901d51ec46a057f56f5db693',
            'cpi/0/false': '9eeceeffb291c520ff48a399cd4016775fb59a58f85ae72514e2308d22cf86ba',
            'cpi/0/true': '4837da03e9bb6728200d666a57dee0210989f843ac9e759e68171d452fc8919e',
            'construction/0/false': '3b52e9dc84439849dcb9ce330b8040e0546138d4aa9f6b6ce2cc8fe677e471e4',
            'construction/0/true': 'b725e227a0e2c7a84d1f832240d30fd57cb61c8ecd815696cf1447e1ae1aec9b',
            'fx/1/false': 'e89361467e4f23718c52b4bfe3cfbea877cd2eba21e3527f74091b11d7155da9',
            'fx/1/true': 'c9b77d7ab60f5e5b60d3419cb77f3ed4ed9f24b8c5ce599226f2a245a713aaf8',
            'fx/2/false': '89118f59724c0925f134c5b00f08bfc670f71537056926bf95fb0020ae1ca42e',
            'fx/2/true': '670abaf6c027b635a6c5b2c01e8c302038fcdd5486e591e064b7345b90656205',
            'fx/10/false': 'c41d20ce23d01b3eaf24ae317668c005bbd12b6ed34f714328b454dc6fcef58a',
            'fx/10/true': 'b5d571663c78e950ccccca8abb8157b03c15b7362adf09f3dca218dcd2d66523',
        }
        for name, expected in hashes.items():
            for array in ('false', 'true'):
                with self.subTest(name=name, array=array):
                    self.assertEqual(self.digest(self.out['single'][name + '/' + array]), expected)
        self.assertEqual(self.digest(self.out['leftover']), hashes['cpi/0/false'])

    def test_monthly_key_carry_forward_and_step_order(self):
        code = self.code('boi+cpi+fx', 2, True)
        self.assertEqual(self.digest(code), 'cf0c7f4b3ddbdcb0af006073e65044c46aefdeb85628c77f30edf43d8a1e5d99')
        self.assertNotIn('#date(', code)
        self.assertIn('FromMonth = "2022-12"', code)
        self.assertIn('ToMonth = "2025-12"', code)
        self.assertEqual(self.block(code, 'WithBoi'),
                         '    WithBoi = Table.AddColumn(Spine, "boi_rate", (row) => List.Last(Table.SelectRows(Boi, '
                         '(change) => change[month] <= row[month])[rate]), type number)')
        boi = self.block(code, 'Boi')
        self.assertNotIn('FromMonth', boi)
        self.assertNotIn('Table.SelectRows', boi)
        self.assertIn('Table.Buffer(Table.Sort(Monthly, {{"date", Order.Ascending}}))', boi)
        all_series = self.code('boi+cpi+construction+fx', 2, True)
        self.assertEqual(re.findall(r'^    (\w+) =', all_series, re.M), [
            'FromMonth', 'ToMonth', 'Boi', 'Cpi', 'Construction', 'Usd', 'Eur', 'Spine',
            'WithBoi', 'WithCpi', 'WithConstruction', 'WithUsd', 'WithEur', 'Sorted', 'Result'])

    def test_monthly_spine_unions_indexes_and_every_currency(self):
        code = self.code('boi+cpi+fx', 2)
        self.assertIn('List.Distinct(Cpi[month] & Usd[month] & Eur[month])', code)
        for count in (1, 2, 10):
            code = self.code('boi+cpi+fx', count)
            anchors = ['Cpi'] + [ccy.capitalize() for ccy in self.out['currencies'][:count]]
            self.assertIn('List.Distinct(' + ' & '.join(step + '[month]' for step in anchors) + ')', code)
            self.assertNotIn('Boi[month]', code)

    def test_monthly_currency_means_and_left_joins(self):
        for count in (1, 2, 10):
            code = self.code('boi+cpi+fx', count)
            self.assertEqual(code.count('Date.ToText([date], "yyyy-MM", "en-US")'), 1 + count)
            self.assertEqual(code.count('Table.Group('), count)
            self.assertEqual(code.count('Table.NestedJoin('), 1 + count)
            self.assertEqual(code.count('JoinKind.LeftOuter'), 1 + count)
            self.assertNotIn('FullOuter', code)
            for line in code.splitlines():
                if 'Table.NestedJoin(' in line:
                    self.assertEqual(line.count('{"month"}'), 2)
                    self.assertNotIn('{"date"}', line)
            for ccy in self.out['currencies'][:count]:
                self.assertIn('Table.Group(Filtered, {"month"}, {{"' + ccy + '_ils", '
                              'each List.Average(List.RemoveNulls([rate])), type number}})', code)

    def test_construction_and_fx_before_index_history(self):
        code = self.out['early']
        self.assertEqual(self.digest(code), '14be09624720289166568ae9270f219ef09c8d6fe2b0a60c2a40ac5bb24d2bac')
        self.assertIn('FromMonth = "1995-01"', code)
        self.assertIn('ToMonth = "2001-12"', code)
        self.assertIn('List.Distinct(Construction[month] & Usd[month])', code)
        usd = self.block(code, 'Usd')
        self.assertEqual(usd.count('Table.SelectRows('), 1)
        self.assertIn('Table.SelectRows(Monthly, each [month] >= FromMonth and [month] <= ToMonth)', usd)
        self.assertNotIn('2000', usd)

    def test_monthly_header_explains_partial_month_and_empty_cells(self):
        code = self.code('boi+cpi+fx', 1)
        header = code.split('\nlet\n')[0]
        self.assertIn('A month still in progress averages the\n// days published so far.', header)
        self.assertIn('A cell is empty\n// when its series has no value for that month.', header)
        self.assertIn('rate in force at the END of the month', header)
        self.assertIn('including the last change before the range start', header)
        usd = self.block(code, 'Usd')
        for token in ('Date.EndOfMonth', 'LocalNow'):
            self.assertNotIn(token, usd)

    def test_two_indexes_need_neither_boi_nor_fx(self):
        code = self.code('cpi+construction')
        self.assertEqual(self.digest(code), '426c0e0e6e749e2e774809da4abb3194d5416cdf67fd439e224fcc09a0cded84')
        self.assertIn('List.Distinct(Cpi[month] & Construction[month])', code)
        for token in ('Boi', 'Table.Group', 'fx/'):
            self.assertNotIn(token, code)
        for token in ('September 1951', 'July 1950', 'January 2000'):
            self.assertIn(token, code.split('\nlet\n')[0])

    def test_daily_reuses_existing_fx_blocks_and_spine(self):
        code = self.code('boi+fx', 2)
        self.assertEqual(self.digest(code), '09b789e32e8762b1127d01647d0d6a3c64d814deeceb2ab64fe6713e26476dd6')
        legacy = self.out['single']['fx/2/false/false']
        for step in ('Usd', 'Eur', 'Spine'):
            self.assertEqual(self.block(code, step), self.block(legacy, step))
        self.assertEqual(self.block(code, 'WithBoi'),
                         '    WithBoi = Table.AddColumn(Spine, "boi_rate", (row) => List.Last(Table.SelectRows(Boi, '
                         '(change) => change[date] <= row[date])[rate]), type number)')
        self.assertNotIn('Table.SelectRows', self.block(code, 'Boi'))
        self.assertIn('Table.Buffer(Table.Sort(Typed, {{"date", Order.Ascending}}))', self.block(code, 'Boi'))
        self.assertIn('NestedJoin(WithBoi, {"date"}, Usd', code)
        self.assertIn('Result = Table.Sort(WithEur, {{"date", Order.Ascending}})', code)
        for token in ('FromMonth', 'Table.Group', 'Date.ToText'):
            self.assertNotIn(token, code)

    def test_combined_average_row(self):
        self.assertEqual(self.digest(self.code('boi+fx', 1, True)),
                         '4ab6965ade1d0ed34b92828e695374a3da4ed7be899c1d0a17ee9e2003f62901')
        for name, code in self.samples.items():
            if name.endswith('/false'):
                self.assertNotIn('Table.InsertRows', code)
                self.assertNotIn('last row:', code)
                continue
            series, count, _ = name.split('/')
            key = 'month' if 'cpi' in series or 'construction' in series else 'date'
            columns = [column for s, column in [('boi', 'boi_rate'), ('cpi', 'cpi_chained'),
                                                ('construction', 'construction_chained')] if s in series]
            columns += [ccy + '_ils' for ccy in self.out['currencies'][:int(count)]]
            fields = [key + ' = null'] + [col + ' = List.Average(List.RemoveNulls(Sorted[' + col + ']))' for col in columns]
            self.assertIn('Result = Table.InsertRows(Sorted, Table.RowCount(Sorted), {[' + ', '.join(fields) + ']})', code)
            self.assertIn('// last row: simple arithmetic mean of the rows above; the key cell stays empty', code)

    def test_series_order_normalization_and_ignored_currencies(self):
        self.assertEqual(self.out['series'], ['boi', 'cpi', 'construction', 'fx'])
        self.assertEqual(self.out['reordered'], self.out['ordered'])
        self.assertEqual(self.out['noFx'], self.code('cpi+construction'))
        code = self.out['reordered']
        final = self.block(code, 'Result')
        columns = ['boi_rate', 'cpi_chained', 'construction_chained', 'eur_ils', 'usd_ils']
        self.assertEqual(sorted(columns, key=final.index), columns)

    def test_future_range_is_preserved(self):
        self.assertIn('\n    ToMonth = "2099-12",', self.out['futureMonth'])
        self.assertNotIn('To = #date', self.out['futureMonth'])
        self.assertIn('\n    To = #date(2099, 12, 31),', self.out['futureDate'])
        self.assertNotIn('ToMonth', self.out['futureDate'])

    def test_generated_code_structure_and_safety(self):
        for token in ('</script', '</style', '<!--', '-->', ' defer', ' async'):
            self.assertNotIn(token, self.source)
        self.assertNotIn('raw.githubusercontent.com', self.source)
        self.assertNotRegex(self.source, r'\(\?<[=!]')
        # M lambdas live in strings; JavaScript itself must not use arrows.
        js = re.sub(r'''"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|//[^\n]*''', '', self.source)
        self.assertNotIn('=>', js)
        for name, code in self.samples.items():
            with self.subTest(name=name):
                self.assertTrue(code.isascii())
                for token in ('</script', '</style', '<!--', '-->', ' defer', ' async'):
                    self.assertNotIn(token, code)
                self.assertTrue(code.endswith('\nin\n    Result'))
                # Strip M quoted strings and comments before inspecting syntax.
                bare = re.sub(r'"(?:""|[^"\n])*"|//[^\n]*', '', code)
                stack = []
                for char in bare:
                    if char in '([{':
                        stack.append(char)
                    elif char in ')]}':
                        self.assertTrue(stack)
                        self.assertEqual(stack.pop(), {')': '(', ']': '[', '}': '{'}[char])
                self.assertEqual(stack, [])
                self.assertEqual(len(re.findall(r'\blet\b', bare)), len(re.findall(r'\bin\b', bare)))
                steps = re.findall(r'^    (\w+) =', bare, re.M)
                self.assertEqual(len(steps), len(set(steps)))
                urls = re.findall(r'Web.Contents\("([^"]+)"\)', code)
                series, count, _ = name.split('/')
                expected = len([s for s in series.split('+') if s != 'fx']) + int(count)
                self.assertEqual(len(urls), expected)
                self.assertEqual(len(set(urls)), expected)

    def test_invalid_selections_throw(self):
        self.assertEqual(self.out['errors'], ['Choose at least one data series.'] * 2 +
                         ['Choose at least one supported currency.'] * 3)

    def test_render_reads_all_ticked_boxes(self):
        for row, series, currencies, hidden in zip(self.out['rendered'],
                                                  [['boi', 'cpi'], ['boi', 'fx']], [[], ['usd']], [True, False]):
            self.assertEqual(row['selection']['series'], series)
            self.assertEqual(row['selection']['currencies'], currencies)
            self.assertEqual(row['code'], self.code('+'.join(series), len(currencies)))
            self.assertEqual(row['error'], '')
            self.assertEqual(row['hidden'], hidden)
            self.assertFalse(row['disabled'])

    def test_form_uses_four_series_checkboxes(self):
        html = (ROOT / 'index.html').read_text()
        view = re.search(r'<main[^>]*id="mcode-view".*?</main>', html, re.S).group()
        fieldset = re.search(r'<fieldset><legend>סדרות</legend>(.*?)</fieldset>', view, re.S).group(1)
        inputs = re.findall(r'<input\b[^>]*>', fieldset)
        self.assertEqual(len(inputs), 4)
        for tag, series in zip(inputs, self.out['series']):
            self.assertIn('type="checkbox"', tag)
            self.assertIn('name="mc-series"', tag)
            self.assertIn('value="' + series + '"', tag)
            self.assertEqual(' checked' in tag, series == 'boi')
        self.assertIn('class="radio-options"', fieldset)
        self.assertNotIn('type="radio"', view)


if __name__ == '__main__':
    unittest.main()
