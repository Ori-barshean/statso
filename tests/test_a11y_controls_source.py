import json
import re
import subprocess
import unittest
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE_ERROR = 'חודש לא תקין בתקופת השכירות הבסיסית — יש להזין YYYY-MM או MM/YYYY.'
EXPORT_ERROR = 'חודש לא תקין בטווח הייצוא — יש להזין YYYY-MM או MM/YYYY.'
HINT = 'פורמט החודש: YYYY-MM או MM/YYYY (למשל 2024-09 או 09/2024)'
FLAG_EXPORT_TO = '''
const to = el('tr-export-to'); to.type = 'text'; to.value = 'bad'; to.change();
const state = () => ({error: el('tr-error').textContent, invalid: to.getAttribute('aria-invalid'),
  described: to.getAttribute('aria-describedby'), hidden: el('tr-output').hidden});
'''
FLAGGED = {'error': EXPORT_ERROR, 'invalid': 'true',
           'described': 'tr-export-month-hint tr-error', 'hidden': False}


def node(body, modules=('statso-core.js',)):
    script = 'global.window = {};\n' + '\n'.join(
        'require(' + json.dumps(str(ROOT / 'assets' / name)) + ');' for name in modules
    ) + '\n' + body
    result = subprocess.run(['node', '-e', script], cwd=ROOT, capture_output=True, text=True)
    if result.returncode:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


# Enough DOM to exercise the public rent API, including patching existing cells.
# Fields keep the month attribute independently of their reported input type.
# Each section's region object is created only when the periods' markup is written,
# so object identity shows whether an edit rewrote the markup.
RENT_DOM = r'''
const elements = {}, optionRows = [], downloads = [];
let floorMode = 'floor';
function element(id = '') {
  const attrs = {}, listeners = {};
  return {id, value: '', type: 'month', hidden: true, textContent: '', dataset: {},
    checked: false, options: [], children: [], listeners, writes: 0,
    classList: {names: new Set(), toggle(n, on) { if (on) { this.names.add(n); } else { this.names.delete(n); } },
      contains(n) { return this.names.has(n); }},
    setAttribute(k, v) { attrs[k] = String(v); },
    getAttribute(k) { return attrs[k] === undefined ? null : attrs[k]; },
    removeAttribute(k) { delete attrs[k]; }, hasAttribute(k) { return k in attrs; },
    addEventListener(k, fn) { (listeners[k] ||= []).push(fn); },
    change() { (listeners.change || []).forEach(fn => fn({target: this})); },
    get innerHTML() { return this.html || ''; },
    set innerHTML(html) {
      this.html = html; this.writes++; this.firstElementChild = html ? {} : null;
      if (id !== 'tr-periods') { return; }
      this.sections = [...html.matchAll(/<section class="rent-period">(.*?)<\/section>/gs)].map(match => {
        const cell = () => Object.assign(element(), {firstElementChild: element()});
        const rows = [...match[1].matchAll(/<tbody>(.*?)<\/tbody>/gs)][0][1];
        const bodyRows = [...rows.matchAll(/<tr\b[^>]*>(.*?)<\/tr>/gs)].map(row => ({
          children: [...row[1].matchAll(/<t[dh]\b[^>]*>(.*?)<\/t[dh]>/gs)].map(cell)
        }));
        const foot = {children: Array.from({length: 9}, cell)}, markall = element();
        const wrap = /<div class="table-wrap rent-scroll"/.test(match[1]) ? element() : null;
        return {querySelectorAll: selector => selector === 'tbody tr' ? bodyRows : [],
          querySelector: selector => selector === 'tfoot tr' ? foot : selector === '.rent-scroll' ? wrap : markall};
      });
    },
    querySelectorAll(selector) {
      if (id === 'tr-periods' && selector === '.rent-period') { return this.sections; }
      if (id === 'tr-option-rows' && selector === '.rent-option') { return optionRows; }
      return [];
    }
  };
}
const el = id => elements[id] ||= element(id);
function addOption(start, end, type = 'text') {
  const fields = {'.tr-opt-start': element(), '.tr-opt-end': element(), '.tr-opt-rent': element()};
  fields['.tr-opt-start'].value = start; fields['.tr-opt-end'].value = end;
  fields['.tr-opt-start'].type = fields['.tr-opt-end'].type = type;
  fields['.tr-opt-rent'].value = '5000';
  const row = {querySelector: selector => fields[selector]};
  optionRows.push(row); el('tr-has-options').checked = true;
  return row;
}
global.document = {getElementById: el,
  querySelector: selector => selector === 'input[name="tr-floor"]:checked' ? {value: floorMode} : null,
  querySelectorAll(selector) {
    if (selector === '#tr-option-rows .rent-option') { return optionRows; }
    if (selector === '#tr-option-rows .tr-opt-start, #tr-option-rows .tr-opt-end') {
      return optionRows.flatMap(row => [row.querySelector('.tr-opt-start'), row.querySelector('.tr-opt-end')]);
    }
    const flag = selector.match(/^\[data-error-flag="(.+)"\]$/);
    if (flag) {
      const all = Object.values(elements).concat(optionRows.flatMap(row => ['.tr-opt-start', '.tr-opt-end', '.tr-opt-rent'].map(k => row.querySelector(k))));
      return all.filter(field => field.getAttribute('data-error-flag') === flag[1]);
    }
    return [];
  }
};
const S = window.Statso;
S.xlsx = {STYLE: {}};
S.i18n = {t: text => text};
S.exporter = {stamp: () => 'test', downloadWorkbook(...args) { downloads.push(args); }};
const observations = Array.from({length: 36}, (_, i) => ({month: S.core.shiftMonth('2023-01', i),
  value: 100 + i, chained_1951_09: 100 + i}));
el('tr-base-rent').value = '5000';
for (const id of ['tr-base-start', 'tr-base-end', 'tr-export-from', 'tr-export-to']) {
  el(id).setAttribute('type', 'month');
}
'''


def rent(body):
    return node(RENT_DOM + '\nrequire(' + json.dumps(str(ROOT / 'assets/statso-rent.js')) + ''');
S.rent.init({first_month: '2023-01', last_month: '2025-12'}, S.core.buildIndexMap(observations));
''' + body)


def rent_with(doc_js, body):
    return node(RENT_DOM + '\nrequire(' + json.dumps(str(ROOT / 'assets/statso-rent.js')) + ');\n'
                + 'const DOC = ' + doc_js + ';\n'
                + 'S.rent.init(DOC, S.core.buildIndexMap(DOC.observations));\n' + body)


RENT_BALANCE_DOC = json.dumps({
    'first_month': '2023-12', 'last_month': '2024-03',
    'observations': [dict(month=m, value=v, chained_1951_09=c) for m, v, c in (
        ('2023-12', 105.8, 1000), ('2024-01', 104.7, 990),
        ('2024-02', 103.7, 980), ('2024-03', 106.9, 1010))]})
RENT_BALANCE_SETUP = '''
el('tr-contract-date').value = '2024-01-15';
el('tr-base-start').value = '2024-01'; el('tr-base-end').value = '2024-05';
el('tr-base-rent').value = '1000'; floorMode = 'full'; S.rent.compute();
const host = el('tr-periods');
const rows = () => S.rent.state().periods[0].rows;
const total = () => S.rent.totalsOf(rows());
const settle = (month, checked) => host.listeners.change[0]({target: {
  classList: {contains: n => n === 'tr-paid'}, checked, dataset: {key: '0:' + month}}});
'''


class RentBalanceTests(unittest.TestCase):
    def test_full_mode_nets_credits_and_renders_negative_cells(self):
        seen = rent_with(RENT_BALANCE_DOC, RENT_BALANCE_SETUP + '''
process.stdout.write(JSON.stringify({payables: rows().map(r => r.payable), total: total(),
  summary: el('tr-summary').innerHTML, html: host.innerHTML}));
''')
        self.assertEqual([None if v is None else round(v, 2) for v in seen['payables']],
                         [0, -10, -20, 10, None])
        self.assertAlmostEqual(seen['total']['payable'], -20)
        self.assertAlmostEqual(seen['total']['payable'], seen['total']['difference'])
        self.assertIn('class="rent-negative">-20.00', seen['summary'].replace('\u200e', ''))
        html = seen['html'].replace('\u200e', '')
        for month, amount in (('2024-02', '-10.00'), ('2024-03', '-20.00')):
            row = re.search(r'<tr><th[^>]*id="tr-p0-m' + month + r'".*?</tr>', html).group()
            cells = re.findall(r'<t[dh]\b([^>]*)>(.*?)</t[dh]>', row)
            self.assertIn('class="rent-negative"', cells[7][0])
            self.assertEqual(cells[7][1], amount)
        foot = re.search(r'<tfoot>(.*?)</tfoot>', html).group(1)
        self.assertIn('<td dir="ltr" class="rent-negative">-20.00</td>', foot)

    def test_settlements_and_mode_switch_patch_values_and_negative_classes(self):
        seen = rent_with(RENT_BALANCE_DOC, RENT_BALANCE_SETUP + '''
const writes = host.writes;
const snap = () => {
  const section = host.sections[0], foot = section.querySelector('tfoot tr').children;
  return {writes: host.writes - writes, text: foot[7].textContent,
    negative: foot[7].classList.contains('rent-negative'), total: total().payable,
    payables: rows().filter(r => r.available).map(r => r.payable),
    cells: section.querySelectorAll('tbody tr').slice(0, 4).map(r => r.children[7].classList.contains('rent-negative'))};
};
settle('2024-02', true); const feb = snap();
settle('2024-03', true); const mar = snap();
floorMode = 'floor'; S.rent.compute(); const floor = snap();
floorMode = 'full'; S.rent.compute(); const fullAgain = snap();
process.stdout.write(JSON.stringify({feb, mar, floor, fullAgain}));
''')
        for key, amount, negative in (('feb', -10, True), ('mar', 10, False), ('floor', 10, False)):
            item = seen[key]
            self.assertEqual(item['writes'], 0)
            self.assertEqual(item['text'].replace('\u200e', ''), f'{amount:.2f}')
            self.assertEqual(item['negative'], negative)
            self.assertAlmostEqual(item['total'], amount)
        self.assertEqual(seen['floor']['payables'], [0, 0, 0, 10])
        self.assertEqual(seen['floor']['cells'], [False] * 4)
        self.assertEqual(seen['fullAgain']['cells'], [False, True, True, False])
        self.assertEqual(seen['fullAgain']['writes'], 0)

    def test_exports_include_published_base_precise_ratios_and_net_credit(self):
        modules = ''.join('require(' + json.dumps(str(ROOT / 'assets' / n)) + ');'
                          for n in ('statso-xlsx.js', 'statso-export.js'))
        seen = rent_with(RENT_BALANCE_DOC, RENT_BALANCE_SETUP + modules + '''
let workbook, pdf;
S.exporter.downloadWorkbook = (name, sheets) => { workbook = sheets; };
S.exporter.printDocument = (title, html) => { pdf = html; };
settle('2024-02', true); settle('2024-03', true);
settle('2024-02', false); settle('2024-03', false);
S.rent.exportRent('xlsx'); S.rent.exportRent('pdf');
process.stdout.write(JSON.stringify({workbook, pdf, styles: S.xlsx.STYLE,
  note: el('tr-base-index-note').textContent, model: S.rent.state()}));
''')
        details, sheet = seen['workbook']
        base = next(row[1] for row in details['rows'] if row and row[0]['v'] == 'ערך מדד הבסיס')
        self.assertIsInstance(base['v'], (float, int))
        self.assertEqual(base, {'v': 105.8, 's': seen['styles']['money']})
        self.assertEqual(seen['model']['baseIndexPublished'], 105.8)
        self.assertEqual(seen['model']['baseIndexValue'], 1000)
        body = [row for row in sheet['rows'] if len(row) == 8 and re.fullmatch(r'\d\d/2024', row[0]['v'])]
        self.assertEqual(len(body), 4)
        self.assertEqual(body[1][3], {'v': 0.99, 's': seen['styles']['ratio']})
        for row in body:
            self.assertEqual(row[3]['s'], seen['styles']['ratio'])
            self.assertIsInstance(row[3]['v'], (int, float))
            self.assertEqual(row[2]['v'], round(row[2]['v'], 6))
        for label in ('סה״כ תקופה', 'סה״כ לתשלום'):
            cell = next(row[-1] for row in sheet['rows'] if row and row[0]['v'] == label)
            self.assertAlmostEqual(cell['v'], -20)
            self.assertEqual(cell['s'], seen['styles']['moneyBold'])
        pdf = seen['pdf'].replace('\u200e', '')
        self.assertIn('<td dir="ltr">105.80</td>', pdf)
        self.assertIn('<td dir="ltr">0.9900</td>', pdf)
        self.assertRegex(pdf, r'<p class="print-total">[^<]*<strong dir="ltr" class="rent-negative">-20.00 ₪</strong>')
        self.assertIn('105.8', seen['note'])

    def test_real_data_full_and_floor_balances(self):
        seen = rent_with("JSON.parse(require('fs').readFileSync('data/cpi.json', 'utf8'))", '''
el('tr-contract-date').value = '2024-10-01';
el('tr-base-start').value = '2024-10'; el('tr-base-end').value = '2025-09';
el('tr-base-rent').value = '5000';
const snap = () => ({totals: S.rent.totalsOf(S.rent.state().periods.flatMap(p => p.rows)),
  summary: el('tr-summary').innerHTML});
floorMode = 'full'; S.rent.compute(); const full = snap();
floorMode = 'floor'; S.rent.compute(); const floor = snap();
process.stdout.write(JSON.stringify({full, floor}));
''')
        self.assertEqual(round(seen['full']['totals']['payable'], 2), 649.44)
        self.assertEqual(round(seen['full']['totals']['difference'], 2), 649.44)
        self.assertIn('649.44', seen['full']['summary'])
        self.assertEqual(round(seen['floor']['totals']['payable'], 2), 658.65)

    def test_pdf_prints_the_unrounded_values_the_screen_shows(self):
        # Pre-rounding for the stored cell must not change what the PDF prints: with real CPI data a contract of
        # 2023-01-01 shows 111.19 for 09/2023 (111.195 reads as 111.1949999... on screen) and a contract of 1987-04-01
        # shows 1.4188 for 05/1989 (the toFixed(4) value, 1.4187, would print differently).
        modules = ''.join('require(' + json.dumps(str(ROOT / 'assets' / n)) + ');'
                          for n in ('statso-xlsx.js', 'statso-export.js'))
        seen = rent_with("JSON.parse(require('fs').readFileSync('data/cpi.json', 'utf8'))", modules + '''
let pdf;
const host = el('tr-periods');
S.exporter.downloadWorkbook = () => {};
S.exporter.printDocument = (title, html) => { pdf = html; };
const out = [];
for (const [contract, month] of [['2023-01-01', '2023-09'], ['1987-04-01', '1989-05']]) {
  el('tr-contract-date').value = contract; el('tr-base-start').value = month; el('tr-base-end').value = month;
  el('tr-base-rent').value = '5000'; S.rent.compute(); S.rent.exportRent('pdf');
  const tds = [...host.innerHTML.match(/<tbody><tr>(.*?)<\\/tr>/s)[1].matchAll(/<td[^>]*>(.*?)<\\/td>/g)].map(m => m[1]);
  out.push({contract, month, screen: [tds[1], tds[2]], pdf});
}
process.stdout.write(JSON.stringify(out));
''')
        for case in seen:
            rows = [re.findall(r'<td[^>]*>(.*?)</td>', row) for row in re.findall(r'<tr>(.*?)</tr>', case['pdf'])]
            row = next(cells for cells in rows if len(cells) == 8)
            self.assertEqual([row[2], row[3]], case['screen'], case['contract'])
        self.assertEqual(seen[0]['screen'][0], '111.19')
        self.assertEqual(seen[1]['screen'][1], '1.4188')

    def test_sub_agora_credit_is_zero_on_screen_pdf_and_excel(self):
        # a tenant who pays the indexed amount rounded to the agora leaves a credit below 0.005: the screen shows
        # 0.00 (settled), so the PDF must not print -0.00 and Excel must not store -0.0033
        modules = ''.join('require(' + json.dumps(str(ROOT / 'assets' / n)) + ');'
                          for n in ('statso-xlsx.js', 'statso-export.js'))
        seen = rent_with(RENT_BALANCE_DOC, RENT_BALANCE_SETUP + modules + '''
let workbook, pdf;
S.exporter.downloadWorkbook = (name, sheets) => { workbook = sheets; };
S.exporter.printDocument = (title, html) => { pdf = html; };
el('tr-base-end').value = '2024-01'; S.rent.compute();
host.listeners.change[0]({target: {classList: {contains: n => n === 'tr-actual'},
  value: '1000.0033', dataset: {key: '0:2024-01'}}});
S.rent.exportRent('xlsx'); S.rent.exportRent('pdf');
const row = host.sections[0].querySelectorAll('tbody tr')[0].children;
process.stdout.write(JSON.stringify({workbook, pdf, screen: row[7].textContent,
  negative: row[7].classList.contains('rent-negative')}));
''')
        self.assertEqual(seen['screen'], '0.00')
        self.assertFalse(seen['negative'])
        sheet = seen['workbook'][1]
        body = [row for row in sheet['rows'] if len(row) == 8 and re.fullmatch(r'\d\d/2024', row[0]['v'])]
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0][-1]['v'], 0)
        pdf_rows = [re.findall(r'<td[^>]*>(.*?)</td>', row) for row in re.findall(r'<tr>(.*?)</tr>', seen['pdf'])]
        pdf_row = next(cells for cells in pdf_rows if len(cells) == 8)
        self.assertEqual(pdf_row[-1].replace('\u200e', ''), '0.00')

    def test_float_noise_displays_as_zero_without_negative_styling(self):
        seen = rent_with(RENT_BALANCE_DOC, RENT_BALANCE_SETUP + '''
el('tr-base-end').value = '2024-01'; S.rent.compute();
host.listeners.change[0]({target: {classList: {contains: n => n === 'tr-actual'},
  value: '1000.000000001', dataset: {key: '0:2024-01'}}});
const foot = host.sections[0].querySelector('tfoot tr').children;
const row = host.sections[0].querySelectorAll('tbody tr')[0].children;
process.stdout.write(JSON.stringify({summary: el('tr-summary').innerHTML,
  row: row[7].textContent, foot: foot[7].textContent,
  negative: [row[7], foot[7]].map(c => c.classList.contains('rent-negative'))}));
''')
        self.assertEqual(seen['row'], '0.00')
        self.assertEqual(seen['foot'], '0.00')
        self.assertEqual(seen['negative'], [False, False])
        self.assertNotIn('rent-negative', seen['summary'])


class MonthInputTests(unittest.TestCase):
    def test_each_period_table_scrolls_in_its_own_region_named_by_the_period_heading(self):
        seen = rent('''
addOption('9/2024','10/2024'); addOption('1/2026','2/2026'); S.rent.compute();
process.stdout.write(JSON.stringify({html: el('tr-periods').innerHTML, labels: S.rent.state().periods.map(p => p.label)}));
''')
        html, labels = seen['html'], seen['labels']
        self.assertEqual(labels, ['תקופת השכירות הבסיסית', 'תקופת אופציה 1', 'תקופת אופציה 2'])
        tree = Tree(html)
        wraps = [n for n in tree.nodes if 'table-wrap' in n.attrs.get('class', '').split()]
        self.assertEqual(len(wraps), 3)
        headings = []
        for i, wrap in enumerate(wraps):
            self.assertEqual(wrap.tag, 'div')
            self.assertEqual(wrap.attrs['class'], 'table-wrap rent-scroll')
            self.assertEqual(wrap.attrs.get('tabindex'), '0')
            self.assertEqual(wrap.attrs.get('role'), 'region')
            self.assertNotIn('aria-label', wrap.attrs)
            ref = wrap.attrs.get('aria-labelledby')
            self.assertEqual(ref, f'tr-p{i}-title')
            heading = tree.by_id(ref)
            self.assertEqual(heading.tag, 'h3')
            self.assertEqual(heading.text(), labels[i])
            self.assertTrue(heading.text())
            headings.append(heading.text())
            self.assertEqual(wrap.parent.tag, 'section')
            self.assertIn('rent-period', wrap.parent.attrs.get('class', '').split())
            self.assertIn(heading, wrap.parent.descendants())
            self.assertEqual([child.tag for child in wrap.children if isinstance(child, Element)], ['table'])
        self.assertEqual(len(set(headings)), 3)
        self.assertEqual(len(re.findall(
            r'<div class="table-wrap rent-scroll" tabindex="0" role="region" aria-labelledby="tr-p\d+-title">', html)), 3)

    def test_editing_a_row_keeps_every_period_region_node(self):
        # Node identity in the stub means "host markup not rewritten"; real-node identity
        # and scroll retention are checked in a real browser.
        seen = rent('''
addOption('9/2024', '10/2024'); addOption('1/2026', '2/2026'); S.rent.compute();
const host = el('tr-periods'), regions = () => host.sections.map(s => s.querySelector('.rent-scroll'));
const before = regions(), writes = host.writes, month = S.rent.state().periods[1].rows[0].month;
const change = target => host.listeners.change[0]({target});
change({classList: {contains: n => n === 'tr-actual'}, value: '4000', dataset: {key: '1:' + month}});
change({classList: {contains: n => n === 'tr-paid'}, checked: true, dataset: {key: '1:' + month}});
const after = regions(), row = S.rent.state().periods[1].rows[0];
const patched = {count: before.length, present: before.every(Boolean), same: before.every((n, i) => n === after[i]),
  writes: host.writes - writes, actual: row.actual, paid: row.paid};
el('tr-base-end').value = '2024-11'; S.rent.compute();
process.stdout.write(JSON.stringify({patched, rebuilt: {same: regions()[0] === before[0], writes: host.writes - writes}}));
''')
        self.assertEqual(seen['patched'], {'count': 3, 'present': True, 'same': True,
                                          'writes': 0, 'actual': 4000, 'paid': True})
        self.assertEqual(seen['rebuilt'], {'same': False, 'writes': 1})

    def test_parse_month_input_rejects_year_zero(self):
        values = ['0000-05', '05/0000', '0000-5', '5/0000', '0001-05', '5/0001']
        seen = node('process.stdout.write(JSON.stringify(' + json.dumps(values)
                    + '.map(window.Statso.core.parseMonthInput)));')
        self.assertEqual(seen, [None] * 4 + ['0001-05'] * 2)

    def test_parse_month_input(self):
        values = ['2024-09', '2024-9', '09/2024', '9/2024', ' 2024-09 ', '',
                  '2024-13', '0/2024', 'sept 2024', '2024/09', '24-09', '2024-009']
        seen = node('process.stdout.write(JSON.stringify(' + json.dumps(values)
                    + '.map(window.Statso.core.parseMonthInput)));')
        self.assertEqual(seen, ['2024-09'] * 5 + [''] + [None] * 6)

    def test_text_month_normalizes_then_reports_and_clears_error(self):
        seen = rent('''
const field = el('tr-base-start'); field.type = 'text'; field.value = '09/2024';
S.rent.compute();
const read = () => ({value: field.value, attr: field.getAttribute('type'), error: el('tr-error').textContent,
  hidden: el('tr-output').hidden, hint: el('tr-base-month-hint').hidden,
  invalid: field.getAttribute('aria-invalid'), described: field.getAttribute('aria-describedby')});
const valid = read(); valid.rows = S.rent.state().periods[0].rows.length;
field.value = 'sept 2024'; S.rent.compute(); const invalid = read();
field.value = '2024-9'; S.rent.compute(); const corrected = read();
process.stdout.write(JSON.stringify({valid, invalid, corrected}));
''')
        self.assertEqual(seen['valid']['value'], '2024-09')
        self.assertEqual(seen['valid']['attr'], 'month')
        self.assertEqual(seen['valid']['rows'], 4)
        self.assertEqual(seen['valid']['error'], '')
        self.assertFalse(seen['valid']['hidden'])
        self.assertFalse(seen['valid']['hint'])
        self.assertEqual(seen['valid']['described'], 'tr-base-month-hint')
        self.assertEqual(seen['invalid']['error'], BASE_ERROR)
        self.assertTrue(seen['invalid']['hidden'])
        self.assertEqual(seen['invalid']['invalid'], 'true')
        self.assertEqual(seen['invalid']['described'], 'tr-base-month-hint tr-error')
        self.assertEqual(seen['corrected'], {k: v for k, v in seen['valid'].items() if k != 'rows'})

    def test_native_month_is_unchanged_and_hints_stay_hidden(self):
        seen = rent('''
el('tr-base-start').value = '2024-9'; S.rent.compute();
process.stdout.write(JSON.stringify({value: el('tr-base-start').value,
  start: S.rent.state().form.baseStart, invalid: el('tr-base-start').hasAttribute('aria-invalid'),
  hints: ['base', 'options', 'export'].map(group => el('tr-' + group + '-month-hint').hidden)}));
''')
        self.assertEqual(seen, {'value': '2024-9', 'start': '2024-9', 'invalid': False, 'hints': [True] * 3})

    def test_late_option_fields_are_normalized_and_validated(self):
        seen = rent('''
const row = addOption('9/2024', '10/2024'); S.rent.compute();
const valid = {start: S.rent.state().form.options[0].start, periods: S.rent.state().periods.length,
  hint: el('tr-options-month-hint').hidden,
  described: row.querySelector('.tr-opt-start').getAttribute('aria-describedby')};
row.querySelector('.tr-opt-end').value = 'sept 2024'; S.rent.compute();
process.stdout.write(JSON.stringify({valid, error: el('tr-error').textContent,
  invalid: row.querySelector('.tr-opt-end').getAttribute('aria-invalid'), hidden: el('tr-output').hidden}));
''')
        self.assertEqual(seen['valid'], {'start': '2024-09', 'periods': 2, 'hint': False,
                                         'described': 'tr-options-month-hint'})
        self.assertEqual(seen['error'], 'חודש לא תקין בתקופת אופציה 1 — יש להזין YYYY-MM או MM/YYYY.')
        self.assertEqual(seen['invalid'], 'true')
        self.assertTrue(seen['hidden'])

    def test_export_validates_both_fields_without_hiding_output_or_downloading(self):
        seen = rent('''
for (const id of ['tr-export-from', 'tr-export-to']) { el(id).type = 'text'; el(id).value = 'bad'; }
S.rent.exportRent('xlsx');
const invalid = {error: el('tr-error').textContent, hidden: el('tr-output').hidden, downloads: downloads.length,
  hint: el('tr-export-month-hint').hidden, fields: ['tr-export-from', 'tr-export-to'].map(id => ({
    invalid: el(id).getAttribute('aria-invalid'), described: el(id).getAttribute('aria-describedby')}))};
el('tr-export-from').value = '9/2024'; el('tr-export-to').change();
const stillInvalid = el('tr-error').textContent;
el('tr-export-to').value = '10/2024'; el('tr-export-to').change();
const corrected = {error: el('tr-error').textContent, from: el('tr-export-from').value, to: el('tr-export-to').value,
  invalid: el('tr-export-to').hasAttribute('aria-invalid'), described: el('tr-export-to').getAttribute('aria-describedby'),
  months: S.rent.exportSelection()[0].rows.map(row => row.month)};
S.rent.compute(); corrected.rangePreserved = el('tr-export-from').value === '2024-09';
S.rent.exportRent('xlsx'); corrected.downloads = downloads.length;
process.stdout.write(JSON.stringify({invalid, stillInvalid, corrected}));
''')
        self.assertEqual(seen['invalid'], {'error': EXPORT_ERROR, 'hidden': False, 'downloads': 0, 'hint': False,
            'fields': [{'invalid': 'true', 'described': 'tr-export-month-hint tr-error'}] * 2})
        self.assertEqual(seen['stillInvalid'], EXPORT_ERROR)
        self.assertEqual(seen['corrected'], {'error': '', 'from': '2024-09', 'to': '2024-10', 'invalid': False,
            'described': 'tr-export-month-hint', 'months': ['2024-09', '2024-10'], 'rangePreserved': True, 'downloads': 1})

    def test_a_month_the_text_fallback_rejects_stays_invalid_after_flagfields_withdraws_its_own(self):
        # found in review: a field the helper flagged earlier (export range empty) and the parse then rejects must keep
        # aria-invalid and its link to the message when the next message is written with no fields
        seen = rent("""
S.core.flagFields('tr-error', [el('tr-export-to')]);
const flagged = {invalid: el('tr-export-to').getAttribute('aria-invalid'), owned: el('tr-export-to').getAttribute('data-error-flag')};
const to = el('tr-export-to'); to.type = 'text'; to.value = 'bad'; to.change();
process.stdout.write(JSON.stringify({flagged, invalid: to.getAttribute('aria-invalid'), described: to.getAttribute('aria-describedby'),
  owned: to.getAttribute('data-error-flag'), error: el('tr-error').textContent}));
""")
        self.assertEqual(seen["flagged"], {"invalid": "true", "owned": "tr-error"})
        self.assertEqual(seen["invalid"], "true")
        self.assertIn("tr-error", seen["described"])
        self.assertIsNone(seen["owned"])
        self.assertEqual(seen["error"], EXPORT_ERROR)

    def test_export_error_survives_a_change_of_export_scope(self):
        seen = rent(FLAG_EXPORT_TO + '''
const flagged = state();
el('tr-export-period').change(); const period = state();
el('tr-exclude-paid').checked = false; el('tr-exclude-paid').change(); const paid = state();
process.stdout.write(JSON.stringify({flagged, period, paid}));
''')
        self.assertEqual(seen, {'flagged': FLAGGED, 'period': FLAGGED, 'paid': FLAGGED})

    def test_export_error_survives_a_successful_recompute(self):
        seen = rent(FLAG_EXPORT_TO + '''
let text = el('tr-error').textContent, writes = 0;
Object.defineProperty(el('tr-error'), 'textContent', {configurable: true,
  get() { return text; }, set(v) { writes++; text = v; }});
const month = S.rent.state().periods[0].rows[0].month;
el('tr-periods').listeners.change[0]({target: {classList: {contains: n => n === 'tr-actual'},
  value: '4000', dataset: {key: '0:' + month}}});
const edited = state(), editWrites = writes, overridden = S.rent.state().periods[0].rows[0].actual;
S.rent.compute(); const computed = state();
const base = el('tr-base-start'), original = base.value;
base.type = 'text'; base.value = 'bad'; S.rent.compute(); const baseError = el('tr-error').textContent;
base.value = original; S.rent.compute(); const restored = state();
process.stdout.write(JSON.stringify({edited, writes: editWrites, overridden, computed, baseError, restored}));
''')
        for key in ('edited', 'computed', 'restored'):
            self.assertEqual(seen[key], FLAGGED)
        self.assertEqual(seen['writes'], 0)
        self.assertEqual(seen['overridden'], 4000)
        self.assertEqual(seen['baseError'], BASE_ERROR)

    def test_fixing_the_export_field_clears_the_error_and_aria_invalid(self):
        seen = rent(FLAG_EXPORT_TO + '''
to.value = '6/2024'; to.change(); const fixed = state(), value = to.value;
el('tr-export-period').change(); const period = state().error;
S.rent.compute(); const computed = state().error;
process.stdout.write(JSON.stringify({fixed, value, period, computed}));
''')
        self.assertEqual(seen['fixed'], {'error': '', 'invalid': None,
                                         'described': 'tr-export-month-hint', 'hidden': False})
        self.assertEqual(seen['value'], '2024-06')
        self.assertEqual(seen['period'], '')
        self.assertEqual(seen['computed'], '')

    def test_rent_labels_are_unique_and_patch_keeps_existing_table(self):
        seen = rent('''
addOption('9/2024', '10/2024'); addOption('1/2026', '2/2026'); S.rent.compute();
const html = el('tr-periods').innerHTML, first = el('tr-periods').firstElementChild, writes = el('tr-periods').writes;
S.rent.compute();
process.stdout.write(JSON.stringify({html, same: first === el('tr-periods').firstElementChild,
  writes: el('tr-periods').writes - writes}));
''')
        self.assertTrue(seen['same'])
        self.assertEqual(seen['writes'], 0)
        tree = Tree(seen['html'])
        ids = Counter(n.attrs['id'] for n in tree.nodes if 'id' in n.attrs)
        controls = [n for n in tree.nodes if n.tag == 'input']
        self.assertGreater(len(controls), 3)
        for control in controls:
            refs = control.attrs['aria-labelledby'].split()
            cls = control.attrs['class']
            if cls == 'tr-period-paid':
                period = control.attrs['data-period']
                self.assertEqual(refs, [f'tr-p{period}-markall', f'tr-p{period}-title'])
            else:
                period, month = control.attrs['data-key'].split(':')
                col = 5 if cls == 'tr-actual' else 8
                self.assertEqual(refs, [f'tr-p{period}-c{col}', f'tr-p{period}-m{month}'])
                self.assertEqual(tree.by_id(refs[1]).text(), month[5:] + '/' + month[:4])
            for ref in refs:
                self.assertEqual(ids[ref], 1, ref)
        self.assertTrue(all(count == 1 for count in ids.values()))
        self.assertEqual(tree.by_id('tr-p2-m2026-02').attrs['scope'], 'row')
        self.assertNotIn('aria-label="סכום ששולם בפועל"', seen['html'])
        self.assertNotIn('aria-label="ההפרש שולם"', seen['html'])

    def test_new_messages_translate(self):
        values = ['חודש התחלה', 'חודש סיום', HINT, BASE_ERROR, EXPORT_ERROR, 'כל השדות חובה.',
                  'חודש לא תקין בתקופת אופציה 12 — יש להזין YYYY-MM או MM/YYYY.']
        seen = node('''
const L = window.Statso.lang;
const t = s => { if (L.en[s]) { return L.en[s]; }
  for (const [pattern, replacement] of L.enPatterns) { if (pattern.test(s)) { return s.replace(pattern, replacement); } }
  return s; };
process.stdout.write(JSON.stringify(''' + json.dumps(values) + '.map(t)));', ('statso-lang-en.js',))
        self.assertEqual(seen, ['Start month', 'End month',
            'Month format: YYYY-MM or MM/YYYY (for example 2024-09 or 09/2024)',
            'Invalid month in the base rental period — enter YYYY-MM or MM/YYYY.',
            'Invalid month in the export range — enter YYYY-MM or MM/YYYY.', 'All fields are required.',
            'Invalid month in option period 12 — enter YYYY-MM or MM/YYYY.'])


class Element:
    def __init__(self, tag, attrs=(), parent=None):
        self.tag, self.attrs, self.parent, self.children = tag, dict(attrs), parent, []

    def text(self):
        return ''.join(child if isinstance(child, str) else child.text() for child in self.children).strip()

    def descendants(self):
        return [node for child in self.children if isinstance(child, Element)
                for node in [child] + child.descendants()]


class Tree(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.root = Element('root')
        self.current = self.root
        self.feed(source)
        self.nodes = self.root.descendants()

    def handle_starttag(self, tag, attrs):
        node = Element(tag, attrs, self.current)
        self.current.children.append(node)
        if tag not in {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}:
            self.current = node

    def handle_endtag(self, tag):
        node = self.current
        while node.parent:
            if node.tag == tag:
                self.current = node.parent
                return
            node = node.parent

    def handle_data(self, data):
        self.current.children.append(data)

    def by_id(self, id):
        found = [n for n in self.nodes if n.attrs.get('id') == id]
        assert len(found) == 1, (id, len(found))
        return found[0]


class ControlsMarkupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = Tree((ROOT / 'index.html').read_text())

    def test_date_groups_have_context(self):
        for prefix in ('calc', 'ti'):
            for kind, text in [('base', 'חודש בסיס'), ('target', 'חודש יעד')]:
                title = self.tree.by_id(f'{prefix}-{kind}-title')
                group = title.parent
                self.assertEqual(title.text(), text)
                self.assertEqual(group.tag, 'div')
                self.assertIn('date-group', group.attrs['class'].split())
                self.assertEqual(group.attrs['role'], 'group')
                self.assertEqual(group.attrs['aria-labelledby'], title.attrs['id'])
                self.assertIs(next(c for c in group.children if isinstance(c, Element)), title)
                self.assertIn(self.tree.by_id(f'{prefix}-{kind}-year'), group.descendants())
                self.assertIn(self.tree.by_id(f'{prefix}-{kind}-month'), group.descendants())
        for kind, text, visible in [('start', 'חודש התחלה', 'מ־'), ('end', 'חודש סיום', 'עד')]:
            group = self.tree.by_id(f'th-{kind}-year').parent.parent
            self.assertEqual(group.attrs['class'], 'range-group')
            self.assertEqual(group.attrs['role'], 'group')
            self.assertEqual(group.attrs['aria-label'], text)
            self.assertIn(self.tree.by_id(f'th-{kind}-month'), group.descendants())
            self.assertEqual(next(c for c in group.children if isinstance(c, Element)).text(), visible)

    def test_kpi_headings_and_hidden_brand_marks(self):
        for prefix, text in [('cpi', 'מדד המחירים לצרכן'), ('boi', 'ריבית בנק ישראל'), ('fx', 'שערי חליפין נבחרים')]:
            article = self.tree.by_id(prefix + '-kpi')
            heading = self.tree.by_id(article.attrs['aria-labelledby'])
            self.assertEqual(heading.tag, 'h2')
            self.assertEqual(heading.text(), text)
            self.assertIn(heading, article.descendants())
        self.assertFalse(any(re.fullmatch(r'h[1-6]', n.tag) for n in self.tree.by_id('brand-kpi').descendants()))
        self.assertEqual(sum(n.tag == 'h1' for n in self.tree.by_id('dashboard-view').descendants()), 1)
        marks = [n for n in self.tree.nodes if n.attrs.get('class') == 'brand-mark']
        self.assertEqual(len(marks), 3)
        self.assertTrue(all(n.attrs.get('aria-hidden') == 'true' for n in marks))

    def test_method_links_distinguish_different_targets(self):
        blocks = [n for n in self.tree.by_id('method-page').descendants() if 'data-lang' in n.attrs]
        self.assertEqual({n.attrs['data-lang'] for n in blocks}, {'he', 'en'})
        for block in blocks:
            targets = {}
            for link in (n for n in block.descendants() if n.tag == 'a' and 'href' in n.attrs):
                targets.setdefault(link.text(), set()).add(link.attrs['href'])
            self.assertTrue(all(len(urls) == 1 for urls in targets.values()), targets)
            for series in ('120010', '200010'):
                self.assertIn('api.cbs.gov.il (' + series + ')', targets)

    def test_contact_note_is_first_and_describes_all_fields(self):
        form = self.tree.by_id('contact-form')
        first = next(c for c in form.children if isinstance(c, Element))
        self.assertEqual(first.attrs.get('id'), 'contact-required')
        self.assertEqual(first.text(), 'כל השדות חובה.')
        for name in ('name', 'email', 'message'):
            expected = ['contact-required', f'contact-{name}-error']
            if name == 'message':
                expected.append('contact-message-count')
            self.assertEqual(self.tree.by_id('contact-' + name).attrs['aria-describedby'].split(), expected)

    def test_month_hints_are_single_text_nodes_and_alert_exists(self):
        for name in ('base', 'options', 'export'):
            hint = self.tree.by_id('tr-' + name + '-month-hint')
            self.assertIn('hidden', hint.attrs)
            self.assertEqual(hint.children, [HINT])
        self.assertEqual(self.tree.by_id('tr-error').attrs['role'], 'alert')


if __name__ == '__main__':
    unittest.main()
