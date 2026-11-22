import json
import re
import subprocess
import unittest
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE_ERROR = 'חודש לא תקין בתקופת השכירות הבסיסית — יש להזין חודש ושנה, למשל 7/2025.'
EXPORT_ERROR = 'חודש לא תקין בטווח הייצוא — יש להזין חודש ושנה, למשל 7/2025.'
HINT = 'פורמט החודש: חודש ושנה, למשל 7/2025, 07/2025, 72025, 072025 או 2025-07'
VAT_ERROR = 'יש להזין שיעור מע״מ בין 0 ל־100.'
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
# Month fields use manual text entry, with visible format hints.
# Each section's region object is created only when the periods' markup is written,
# so object identity shows whether an edit rewrote the markup.
RENT_DOM = r'''
const elements = {}, optionRows = [], downloads = [];
let floorMode = 'floor';
function element(id = '') {
  const attrs = {}, listeners = {};
  return {id, value: '', type: 'text', hidden: !id.endsWith('-month-hint'), textContent: '', dataset: {},
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
el('tr-vat').value = '18';
for (const id of ['tr-base-start', 'tr-base-end', 'tr-export-from', 'tr-export-to']) {
  el(id).setAttribute('type', 'text');
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
        self.assertEqual(seen['valid']['value'], '9/2024')
        self.assertEqual(seen['valid']['attr'], 'text')
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

    def test_iso_month_normalizes_and_all_hints_stay_visible(self):
        seen = rent('''
el('tr-base-start').value = '2024-9'; S.rent.compute();
process.stdout.write(JSON.stringify({value: el('tr-base-start').value,
  start: S.rent.state().form.baseStart, invalid: el('tr-base-start').hasAttribute('aria-invalid'),
  hints: ['base', 'options', 'export'].map(group => el('tr-' + group + '-month-hint').hidden)}));
''')
        self.assertEqual(seen, {'value': '9/2024', 'start': '2024-09', 'invalid': False, 'hints': [False] * 3})

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
        self.assertEqual(seen['error'], 'חודש לא תקין בתקופת אופציה 1 — יש להזין חודש ושנה, למשל 7/2025.')
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
S.rent.compute(); corrected.rangePreserved = el('tr-export-from').value === '9/2024';
S.rent.exportRent('xlsx'); corrected.downloads = downloads.length;
process.stdout.write(JSON.stringify({invalid, stillInvalid, corrected}));
''')
        self.assertEqual(seen['invalid'], {'error': EXPORT_ERROR, 'hidden': False, 'downloads': 0, 'hint': False,
            'fields': [{'invalid': 'true', 'described': 'tr-export-month-hint tr-error'}] * 2})
        self.assertEqual(seen['stillInvalid'], EXPORT_ERROR)
        self.assertEqual(seen['corrected'], {'error': '', 'from': '9/2024', 'to': '10/2024', 'invalid': False,
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
        self.assertEqual(seen['value'], '6/2024')
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
                  'חודש לא תקין בתקופת אופציה 12 — יש להזין חודש ושנה, למשל 7/2025.']
        seen = node('''
const L = window.Statso.lang;
const t = s => { if (L.en[s]) { return L.en[s]; }
  for (const [pattern, replacement] of L.enPatterns) { if (pattern.test(s)) { return s.replace(pattern, replacement); } }
  return s; };
process.stdout.write(JSON.stringify(''' + json.dumps(values) + '.map(t)));', ('statso-lang-en.js',))
        self.assertEqual(seen, ['Start month', 'End month',
            'Month format: month and year, for example 7/2025, 07/2025, 72025, 072025 or 2025-07',
            'Invalid month in the base rental period — enter a month and year, for example 7/2025.',
            'Invalid month in the export range — enter a month and year, for example 7/2025.', 'All fields are required.',
            'Invalid month in option period 12 — enter a month and year, for example 7/2025.'])


RENT_CURRENT_DOC = json.dumps({
    'first_month': '2023-12', 'last_month': '2024-01',
    'observations': [dict(month=m, value=v, chained_1951_09=v) for m, v in (
        ('2023-12', 1000), ('2024-01', 1075))]})
RENT_HALF_CENT_DOC = json.dumps({
    'first_month': '2023-12', 'last_month': '2024-01',
    'observations': [dict(month=m, value=v, chained_1951_09=v) for m, v in (
        ('2023-12', 1000), ('2024-01', 1000))]})
RENT_CURRENT_SETUP = '''
el('tr-contract-date').value = '2024-01-15';
el('tr-base-start').value = '2024-01'; el('tr-base-end').value = '2024-03';
el('tr-base-rent').value = '10000'; S.rent.compute();
'''
RENT_EXPORT_MODULES = ''.join('require(' + json.dumps(str(ROOT / 'assets' / name)) + ');'
                              for name in ('statso-xlsx.js', 'statso-export.js'))


class RentCurrentFiguresTests(unittest.TestCase):
    def test_manual_month_parse_table_and_round_trips(self):
        valid = ['7/2025', '07/2025', '72025', '072025', '2025-07', '12025', '122025']
        invalid = ['13/2025', '7/25', '720255', '0/2025', '02025', '002025', '132025',
                   '202507', '7-2025', '2025/7', '50000']
        seen = node('''
const c = window.Statso.core;
process.stdout.write(JSON.stringify({parsed: ''' + json.dumps(valid + invalid) + '''.map(c.parseMonthInput),
  roundTrips: ['2025-07', '0001-05'].map(key => [c.formatMonthInput(key), c.parseMonthInput(c.formatMonthInput(key))])}));
''')
        self.assertEqual(seen['parsed'], ['2025-07'] * 5 + ['2025-01', '2025-12'] + [None] * len(invalid))
        self.assertEqual(seen['roundTrips'], [['7/2025', '2025-07'], ['5/0001', '0001-05']])

    def test_all_manual_forms_normalize_on_change_and_defaults_are_unpadded(self):
        seen = rent('''
const defaults = ['tr-base-start', 'tr-base-end', 'tr-export-from', 'tr-export-to'].map(id => el(id).value);
el('tr-base-end').value = '8/2025';
const forms = ['7/2025', '07/2025', '72025', '072025', '2025-07'].map(value => {
  el('tr-base-start').value = value; el('tr-base-start').change();
  return [el('tr-base-start').value, S.rent.state().form.baseStart];
});
process.stdout.write(JSON.stringify({defaults, forms, inputListeners: el('tr-base-start').listeners.input || []}));
''')
        self.assertTrue(all(re.fullmatch(r'[1-9]\d?/\d{4}', v) for v in seen['defaults']))
        self.assertEqual(seen['forms'], [['7/2025', '2025-07']] * 5)
        self.assertEqual(seen['inputListeners'], [])

    def test_added_option_markup_uses_manual_month_values(self):
        html = rent('''
process.stdout.write(JSON.stringify(S.rent.optionRowHtml(0, {start: '2025-07', end: '2026-06', rent: '5000'})));
''')
        fields = [n for n in Tree(html).nodes if n.attrs.get('class') in ('tr-opt-start', 'tr-opt-end')]
        self.assertEqual([n.attrs['value'] for n in fields], ['7/2025', '6/2026'])
        for field in fields:
            for attr, value in {'type': 'text', 'inputmode': 'numeric', 'dir': 'ltr', 'placeholder': 'M/YYYY',
                                'maxlength': '7', 'autocomplete': 'off', 'spellcheck': 'false'}.items():
                self.assertEqual(field.attrs[attr], value)

    def test_half_cent_payable_rounds_like_format_number_on_screen_xlsx_and_pdf(self):
        seen = rent_with(RENT_HALF_CENT_DOC, RENT_EXPORT_MODULES + r'''
el('tr-contract-date').value = '2024-01-15';
el('tr-base-start').value = '2024-01'; el('tr-base-end').value = '2024-03';
el('tr-base-rent').value = '1.005'; S.rent.compute();
el('tr-periods').listeners.change[0]({target: {classList: {contains: n => n === 'tr-actual'},
  value: '0', dataset: {key: '0:2024-01'}}});
let workbook, pdf;
S.exporter.downloadWorkbook = (name, sheets) => { workbook = sheets; };
S.exporter.printDocument = (title, html) => { pdf = html; };
S.rent.exportRent('xlsx'); S.rent.exportRent('pdf');
const current = S.rent.currentFigures(), row = current.rows[0];
const grand = workbook[1].rows.find(r => r.length && r[0].v === 'סה״כ לתשלום').slice(-1)[0].v;
const exported = workbook[0].rows.find(r => r.length && r[0].v === row.label);
const pdfTotal = Number(pdf.match(/<p class="print-total">.*?<strong[^>]*>([\d,.]+) ₪/)[1].replace(/,/g, ''));
process.stdout.write(JSON.stringify({current, html: el('tr-current').innerHTML, pdfTotal,
  grandFormatted: S.core.formatNumber(grand, 2),
  matches: S.core.formatNumber(grand, 2) === S.core.formatNumber(row.before, 2),
  exported: exported.slice(1).map(c => c.v)}));
''')
        row = seen['current']['rows'][0]
        self.assertEqual({k: row[k] for k in ('before', 'vat', 'total')},
                         {'before': 1.01, 'vat': 0.18, 'total': 1.19})
        self.assertIn('1.01', seen['html'])
        self.assertEqual(seen['pdfTotal'], row['before'])
        self.assertEqual(seen['grandFormatted'], '1.01')
        self.assertTrue(seen['matches'])
        self.assertEqual(seen['exported'], [1.01, 0.18, 1.19])
        self.assertEqual(seen['current']['rows'][1]['before'], 1.01)

    def test_half_cent_vat_rounds_like_format_number(self):
        seen = rent_with(RENT_HALF_CENT_DOC, '''
el('tr-contract-date').value = '2024-01-15';
el('tr-base-start').value = '2024-01'; el('tr-base-end').value = '2024-03';
el('tr-base-rent').value = '0.25'; el('tr-vat').value = '18'; S.rent.compute();
const row = S.rent.currentFigures().rows[1];
process.stdout.write(JSON.stringify({row, html: el('tr-current').innerHTML,
  matches: S.core.formatNumber(row.vat, 2) === S.core.formatNumber(0.25 * 18 / 100, 2)}));
''')
        self.assertEqual({k: seen['row'][k] for k in ('before', 'vat', 'total')},
                         {'before': 0.25, 'vat': 0.05, 'total': 0.3})
        self.assertTrue(seen['matches'])
        self.assertIn('0.05', seen['html'])
        self.assertIn('0.30', seen['html'])

    def test_overflowing_amounts_show_a_dash_instead_of_nan(self):
        seen = rent_with(RENT_HALF_CENT_DOC, '''
el('tr-contract-date').value = '2024-01-15';
el('tr-base-start').value = '2024-01'; el('tr-base-end').value = '2024-03';
el('tr-base-rent').value = '1e307'; el('tr-vat').value = '18'; S.rent.compute();
const row = S.rent.currentFigures().rows[1];
process.stdout.write(JSON.stringify({row, html: el('tr-current').innerHTML}));
''')
        self.assertIsNone(seen['row']['vat'])
        self.assertIsNone(seen['row']['total'])
        self.assertNotIn('NaN', seen['html'])
        self.assertIn('—', seen['html'])

    def test_vat_math_screen_and_zero_rate_keep_the_model_and_periods(self):
        seen = rent_with(RENT_CURRENT_DOC, RENT_CURRENT_SETUP + '''
const before = S.rent.currentFigures(), html = el('tr-current').innerHTML;
const model = S.rent.state(), writes = el('tr-periods').writes;
el('tr-vat').value = '0'; el('tr-vat').listeners.input[0]();
const zero = S.rent.currentFigures();
el('tr-vat').value = '100'; el('tr-vat').change();
const hundred = S.rent.currentFigures();
el('tr-vat').value = '17.5'; el('tr-vat').change();
process.stdout.write(JSON.stringify({before, html, zero, hundred, decimal: S.rent.currentFigures(),
  same: model === S.rent.state(), writes: el('tr-periods').writes - writes}));
''')
        self.assertEqual([list(row.values())[1:] for row in seen['before']['rows']], [[750, 135, 885], [10750, 1935, 12685]])
        for value in ('10,750.00', '1,935.00', '12,685.00'):
            self.assertIn(value, seen['html'])
        self.assertEqual([seen['zero']['rows'][1][k] for k in ('before', 'vat', 'total')], [10750, 0, 10750])
        self.assertEqual(seen['hundred']['rows'][1]['total'], 21500)
        self.assertEqual(seen['decimal']['rows'][1]['vat'], 1881.25)
        self.assertTrue(seen['same'])
        self.assertEqual(seen['writes'], 0)
        tree = Tree(seen['html'])
        self.assertEqual(sum(n.tag == 'th' and n.attrs.get('scope') == 'col' for n in tree.nodes), 4)
        self.assertEqual(sum(n.tag == 'th' and n.attrs.get('scope') == 'row' for n in tree.nodes), 2)

    def test_latest_published_month_ignores_period_order_and_filters_and_breaks_ties(self):
        seen = rent_with(RENT_CURRENT_DOC, RENT_CURRENT_SETUP + '''
const late = addOption('2/2024', '2/2024'); late.querySelector('.tr-opt-rent').value = '20000';
const early = addOption('1/2024', '1/2024'); early.querySelector('.tr-opt-rent').value = '30000';
S.rent.compute(); const outOfOrder = S.rent.currentFigures().rows[1];
const tie = addOption('2/2024', '2/2024'); tie.querySelector('.tr-opt-rent').value = '40000';
S.rent.compute(); const tied = S.rent.currentFigures().rows[1];
el('tr-export-period').value = '0'; el('tr-export-period').change();
el('tr-export-to').value = '1/2024'; el('tr-export-to').change();
const filtered = S.rent.currentFigures().rows[1];
el('tr-has-options').checked = false;
el('tr-base-start').value = '3/2024'; el('tr-base-end').value = '4/2024'; S.rent.compute();
process.stdout.write(JSON.stringify({outOfOrder, tied, filtered, unpublished: S.rent.currentFigures(), html: el('tr-current').innerHTML}));
''')
        self.assertEqual(seen['outOfOrder']['before'], 21500)
        self.assertEqual(seen['tied']['before'], 43000)
        self.assertEqual(seen['filtered'], seen['tied'])
        self.assertIsNone(seen['unpublished']['rows'][1]['before'])
        self.assertEqual(seen['unpublished']['rows'][0]['before'], 0)
        self.assertIn('—', seen['html'])

    def test_selected_payable_matches_xlsx_and_pdf_without_rebuilding_periods(self):
        seen = rent_with(RENT_CURRENT_DOC, RENT_CURRENT_SETUP + RENT_EXPORT_MODULES + '''
let workbook, pdf;
S.exporter.downloadWorkbook = (name, sheets) => { workbook = sheets; };
S.exporter.printDocument = (title, html) => { pdf = html; };
addOption('1/2024', '2/2024'); S.rent.compute();
el('tr-periods').listeners.change[0]({target: {classList: {contains: n => n === 'tr-paid'},
  checked: true, dataset: {key: '0:2024-02'}}});
const cases = [], writes = el('tr-periods').writes;
const before = el('tr-current').innerHTML;
for (const [scope, from, to, exclude] of [
  ['all', '1/2024', '2/2024', false], ['1', '1/2024', '2/2024', false],
  ['all', '2/2024', '2/2024', true], ['0', '1/2024', '2/2024', true]]) {
  el('tr-export-period').value = scope; el('tr-export-period').change();
  el('tr-export-from').value = from; el('tr-export-from').change();
  el('tr-export-to').value = to; el('tr-export-to').change();
  el('tr-exclude-paid').checked = exclude; el('tr-exclude-paid').change();
  S.rent.exportRent('xlsx'); S.rent.exportRent('pdf');
  cases.push({current: S.rent.currentFigures(), workbook, pdf});
}
const changed = before !== el('tr-current').innerHTML;
el('tr-export-from').value = 'bad'; el('tr-export-from').change();
const invalid = S.rent.currentFigures().rows[0];
el('tr-export-from').value = '3/2024'; el('tr-export-from').change();
process.stdout.write(JSON.stringify({cases, changed, writes: el('tr-periods').writes - writes,
  invalid, empty: S.rent.currentFigures().rows[0], html: el('tr-current').innerHTML}));
''')
        for case in seen['cases']:
            row = case['current']['rows'][0]
            grand = next(r[-1]['v'] for r in case['workbook'][1]['rows'] if r and r[0]['v'] == 'סה״כ לתשלום')
            self.assertAlmostEqual(row['before'], grand)
            pdf_total = re.search(r'<p class="print-total">.*?<strong[^>]*>([\d,.]+) ₪', case['pdf']).group(1)
            self.assertEqual(row['before'], float(pdf_total.replace(',', '')))
            exported = next(r for r in case['workbook'][0]['rows'] if r and r[0]['v'] == row['label'])
            self.assertEqual([c['v'] for c in exported[1:]], [row['before'], row['vat'], row['total']])
            self.assertEqual(case['current']['rows'][1]['before'], 5375)
        self.assertEqual([c['current']['rows'][0]['before'] for c in seen['cases']], [375] * 3 + [0])
        self.assertTrue(seen['changed'])
        self.assertEqual(seen['writes'], 0)
        self.assertIsNone(seen['invalid']['before'])
        self.assertEqual(seen['empty']['before'], 0)
        self.assertIn('0.00', seen['html'])

    def test_vat_errors_are_announced_and_flagged_without_hiding_output_or_exporting(self):
        seen = rent_with(RENT_CURRENT_DOC, RENT_CURRENT_SETUP + '''
const read = () => ({error: el('tr-error').textContent, hidden: el('tr-output').hidden,
  invalid: el('tr-vat').getAttribute('aria-invalid'), described: el('tr-vat').getAttribute('aria-describedby')});
const invalid = ['', '-1', '101', 'abc'].map(value => {
  el('tr-vat').value = value; el('tr-vat').listeners.input[0]();
  S.rent.exportRent('xlsx'); return read();
});
const blocked = downloads.length;
el('tr-export-to').value = 'bad'; el('tr-export-to').change();
S.rent.exportRent('xlsx'); const precedence = read();
el('tr-export-to').value = '2/2024'; el('tr-export-to').change(); const backToVat = read();
el('tr-vat').value = '18'; el('tr-vat').change(); const corrected = read();
S.rent.exportRent('xlsx');
process.stdout.write(JSON.stringify({invalid, blocked, precedence, backToVat, corrected, downloads: downloads.length}));
''')
        for case in seen['invalid'] + [seen['backToVat']]:
            self.assertEqual(case['error'], VAT_ERROR)
            self.assertFalse(case['hidden'])
            self.assertEqual(case['invalid'], 'true')
            self.assertIn('tr-error', case['described'].split())
        self.assertEqual(seen['blocked'], 0)
        self.assertEqual(seen['precedence']['error'], EXPORT_ERROR)
        self.assertFalse(seen['precedence']['hidden'])
        self.assertEqual(seen['corrected']['error'], '')
        self.assertIsNone(seen['corrected']['invalid'])
        self.assertNotIn('tr-error', seen['corrected']['described'] or '')
        self.assertEqual(seen['downloads'], 1)

    def test_details_current_and_periods_order_and_export_styles(self):
        seen = rent_with(RENT_CURRENT_DOC, RENT_CURRENT_SETUP + RENT_EXPORT_MODULES + '''
let workbook, pdf;
S.exporter.downloadWorkbook = (name, sheets) => { workbook = sheets; };
S.exporter.printDocument = (title, html) => { pdf = html; };
el('tr-landlord').value = '<b>משכיר & שם</b>'; el('tr-tenant').value = 'תקופות אופציה';
el('tr-vat').value = '17.5'; S.rent.compute();
S.rent.exportRent('xlsx'); S.rent.exportRent('pdf');
process.stdout.write(JSON.stringify({workbook, pdf, styles: S.xlsx.STYLE, details: el('tr-details').innerHTML}));
''')
        expected = ['מועד הסכם השכירות', 'שם המשכיר', 'שם השוכר', 'מדד הבסיס', 'ערך מדד הבסיס', 'אופן ההצמדה']
        details, periods = seen['workbook']
        self.assertEqual(details['columns'], [{'width': n} for n in (34, 30, 14, 18)])
        self.assertEqual([r[0]['v'] for r in details['rows'][2:8]], expected)
        self.assertEqual(details['rows'][8], [])
        self.assertEqual(details['rows'][9], [{'v': 'סכומים עדכניים (מע״מ 17.5%)', 's': seen['styles']['title']}])
        self.assertEqual(len(details['rows']), 13)
        header = details['rows'][10]
        self.assertEqual(len(header), 4)
        self.assertTrue(all(c['s'] == seen['styles']['header'] for c in header))
        for row in details['rows'][11:]:
            self.assertEqual(len(row), 4)
            self.assertEqual(row[0]['s'], seen['styles']['header'])
            self.assertTrue(all(c['s'] == seen['styles']['moneyBold'] for c in row[1:]))
        titles = [r[0]['v'] for r in periods['rows'][2:] if len(r) == 1]
        self.assertTrue(titles)
        self.assertTrue(all(t.endswith(' ₪ לחודש') for t in titles))
        pdf = Tree(seen['pdf'])
        headings = [n.text() for n in pdf.nodes if n.tag == 'h2']
        self.assertEqual(headings[:2], ['פרטי ההסכם', 'סכומים עדכניים (מע״מ 17.5%)'])
        self.assertTrue(headings[2].startswith('תקופת השכירות הבסיסית · 01/2024–03/2024'))
        self.assertTrue(headings[2].endswith('10,000.00 ₪ לחודש'))
        tables = [n for n in pdf.nodes if n.tag == 'table']
        detail_rows = [n for n in tables[0].descendants() if n.tag == 'tr'][1:]
        self.assertEqual([r.children[0].text() for r in detail_rows], expected)
        self.assertEqual(tables[1].parent.attrs, {'class': 'rent-current'})
        self.assertEqual(sum(n.tag == 'th' for n in tables[1].descendants()), 4)
        screen = Tree(seen['details'])
        self.assertEqual([n.text() for n in screen.nodes if n.tag == 'th' and n.attrs.get('scope') == 'row'], expected)
        names = [n for n in screen.nodes if 'data-i18n-skip' in n.attrs]
        self.assertEqual([n.text() for n in names], ['<b>משכיר & שם</b>', 'תקופות אופציה'])
        self.assertTrue(all(n.attrs['dir'] == 'auto' for n in names))
        self.assertFalse(any(n.tag == 'b' for n in screen.nodes))

    def test_exported_names_are_marked_raw_in_xlsx_and_pdf(self):
        names = ['תיאור', 'תקופות אופציה']  # both are exact dictionary keys
        seen = rent_with(RENT_CURRENT_DOC, RENT_CURRENT_SETUP + RENT_EXPORT_MODULES + '''
let workbook, pdf;
S.exporter.downloadWorkbook = (name, sheets) => { workbook = sheets; };
S.exporter.printDocument = (title, html) => { pdf = html; };
el('tr-landlord').value = ''' + json.dumps(names[0]) + '; el(\'tr-tenant\').value = ' + json.dumps(names[1]) + ''';
S.rent.compute();
S.rent.exportRent('xlsx'); S.rent.exportRent('pdf');
process.stdout.write(JSON.stringify({workbook, pdf, date: S.core.formatIsoDateHe('2024-01-15')}));
''')
        cells = {r[0]['v']: r[1] for r in seen['workbook'][0]['rows'] if len(r) == 2}
        for label, name in (('שם המשכיר', names[0]), ('שם השוכר', names[1])):
            self.assertIs(cells[label].get('raw'), True, label)
            self.assertEqual(cells[label]['v'], name)
        self.assertEqual(cells['מועד הסכם השכירות']['v'], seen['date'])
        self.assertNotIn('raw', cells['מועד הסכם השכירות'])
        for name in names:
            self.assertIn('<td dir="auto" data-i18n-skip>' + name + '</td>', seen['pdf'])
        self.assertIn('<td>מועד הסכם השכירות</td><td>' + seen['date'] + '</td>', seen['pdf'])

    def test_english_xlsx_keeps_typed_names_untranslated(self):
        names = ['תיאור', 'תקופות אופציה']  # exact keys: 'Description' / 'Option periods' in English
        seen = rent_with(RENT_CURRENT_DOC, RENT_CURRENT_SETUP + RENT_EXPORT_MODULES + '''
require(''' + json.dumps(str(ROOT / 'assets' / 'statso-lang-en.js')) + ''');
const L = window.Statso.lang, own = Object.prototype.hasOwnProperty;
S.i18n = {t: text => {
  const trimmed = String(text).trim();
  if (!trimmed) { return text; }
  if (own.call(L.en, trimmed)) { return String(text).replace(trimmed, L.en[trimmed]); }
  for (const [pattern, replacement] of L.enPatterns) {
    if (pattern.test(trimmed)) { return String(text).replace(trimmed, trimmed.replace(pattern, replacement)); }
  }
  return text;
}};
let workbook;
S.exporter.downloadWorkbook = (name, sheets) => { workbook = sheets; };
el('tr-landlord').value = ''' + json.dumps(names[0]) + '; el(\'tr-tenant\').value = ' + json.dumps(names[1]) + ''';
S.rent.compute(); S.rent.exportRent('xlsx');
const xml = Buffer.from(S.xlsx.build(workbook, {title: 'x'})).toString('utf8');
process.stdout.write(JSON.stringify({xml, label: S.i18n.t('שם המשכיר'), header: S.i18n.t('תיאור')}));
''')
        xml = seen['xml']

        def cell(text):
            return '<t xml:space="preserve">' + text + '</t>'
        self.assertNotEqual(seen['label'], 'שם המשכיר')  # English mode really is on
        self.assertEqual(seen['header'], 'Description')
        self.assertIn(cell(seen['label']), xml)  # the label is still translated
        for name in names:
            self.assertEqual(xml.count(cell(name)), 1, name)  # the typed name survives
        self.assertEqual(xml.count(cell('Description')), 1)  # only the real table header
        self.assertNotIn(cell('Option periods'), xml)

    def test_screen_details_cells_follow_the_raw_flag_not_the_row_position(self):
        seen = rent_with(RENT_CURRENT_DOC, RENT_CURRENT_SETUP + '''
el('tr-landlord').value = 'תיאור'; el('tr-tenant').value = ''; S.rent.compute();
process.stdout.write(JSON.stringify(el('tr-details').innerHTML));
''')
        rows = Tree(seen).nodes
        values = {r.children[0].text(): r.children[1] for r in rows
                  if r.tag == 'tr' and r.children[0].attrs.get('scope') == 'row'}
        self.assertEqual(len(values), 6)
        skipped = {label: 'data-i18n-skip' in cell.attrs for label, cell in values.items()}
        self.assertEqual([label for label, flag in skipped.items() if flag], ['שם המשכיר', 'שם השוכר'])
        self.assertEqual(values['שם השוכר'].text(), '—')
        self.assertEqual({k: v.attrs.get('dir') for k, v in values.items() if k not in ('שם המשכיר', 'שם השוכר')},
                         {'מועד הסכם השכירות': None, 'מדד הבסיס': None, 'ערך מדד הבסיס': 'ltr', 'אופן ההצמדה': None})
        source = (ROOT / 'assets' / 'statso-rent.js').read_text()
        body = re.search(r'function detailsHtml\(\) \{(.*?)\n  \}\n', source, re.S).group(1)
        self.assertNotIn('i === 1', body)
        self.assertNotIn('function (row, i)', body)

    def test_current_announcements_debounce_and_suppress_invalid_states(self):
        seen = rent_with(RENT_CURRENT_DOC, RENT_CURRENT_SETUP + '''
let pending = new Map(), serial = 0; const spoken = [], delays = [];
window.setTimeout = (fn, delay) => { delays.push(delay); pending.set(++serial, fn); return serial; };
window.clearTimeout = id => pending.delete(id);
S.exporter.announce = text => spoken.push(text);
const flush = () => { const jobs = [...pending.values()]; pending.clear(); jobs.forEach(fn => fn()); };
el('tr-vat').value = '0'; el('tr-vat').listeners.input[0](); el('tr-vat').change();
const queued = pending.size; flush();
el('tr-vat').value = ''; el('tr-vat').change(); flush();
el('tr-vat').value = '18'; el('tr-vat').change();
el('tr-base-start').value = 'bad'; el('tr-base-start').change(); flush();
el('tr-base-start').value = '1/2024'; S.rent.compute();
const afterCompute = pending.size;
el('tr-export-period').change(); flush();
process.stdout.write(JSON.stringify({queued, spoken, delays, afterCompute}));
''')
        self.assertEqual(seen['queued'], 1)
        self.assertEqual(seen['afterCompute'], 0)
        self.assertEqual(len(seen['spoken']), 2)
        self.assertIn('כולל מע״מ: 10,750.00 ₪', seen['spoken'][0])
        self.assertIn('כולל מע״מ: 12,685.00 ₪', seen['spoken'][1])
        self.assertTrue(all(delay == 800 for delay in seen['delays']))

    def test_current_figures_translation_keys_and_dynamic_titles(self):
        translations = {
            'סכומים עדכניים': 'Current figures', 'שיעור מע״מ (%)': 'VAT rate (%)', 'תיאור': 'Description',
            'סכום לפני מע״מ (₪)': 'Amount before VAT (₪)', 'מע״מ (₪)': 'VAT (₪)',
            'סכום כולל מע״מ (₪)': 'Amount incl. VAT (₪)',
            'סה״כ הפרשים לתשלום על ידי הלקוח': 'Total differences payable by the client',
            'סכום עדכני לשכירות חודשית': 'Current monthly rent amount', 'כולל מע״מ': 'incl. VAT',
            VAT_ERROR: 'Enter a VAT rate from 0 to 100.', 'מע״מ': 'VAT',
            'סכומים עדכניים (מע״מ 17.5%)': 'Current figures (VAT 17.5%)',
            'Base rental period · 01/2024–03/2024 · 10,000.00 ₪ לחודש':
                'Base rental period · 01/2024–03/2024 · 10,000.00 ₪ per month'}
        seen = node('''
const L = window.Statso.lang;
const t = text => {
  if (L.en[text]) { return L.en[text]; }
  for (const [pattern, replacement] of L.enPatterns) { if (pattern.test(text)) { return text.replace(pattern, replacement); } }
  return text;
};
process.stdout.write(JSON.stringify(''' + json.dumps(list(translations)) + '.map(t)));', ('statso-lang-en.js',))
        self.assertEqual(seen, list(translations.values()))


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
            self.assertNotIn('hidden', hint.attrs)
            self.assertEqual(hint.children, [HINT])
        self.assertEqual(self.tree.by_id('tr-error').attrs['role'], 'alert')

    def test_rent_current_and_details_regions_and_vat_form_placement(self):
        for name in ('details', 'current'):
            region = self.tree.by_id('tr-' + name)
            self.assertEqual(region.attrs['role'], 'region')
            self.assertEqual(region.attrs['tabindex'], '0')
            title = self.tree.by_id(region.attrs['aria-labelledby'])
            self.assertEqual(title.tag, 'h3')
            self.assertIn(title, region.parent.descendants())
        output = self.tree.by_id('tr-output').descendants()
        self.assertLess(output.index(self.tree.by_id('tr-details')), output.index(self.tree.by_id('tr-current')))
        self.assertLess(output.index(self.tree.by_id('tr-current')), output.index(self.tree.by_id('tr-periods')))
        vat = self.tree.by_id('tr-vat')
        for attr, value in {'type': 'number', 'value': '18', 'min': '0', 'max': '100',
                            'step': 'any', 'inputmode': 'decimal'}.items():
            self.assertEqual(vat.attrs[attr], value)
        form = next(n for n in self.tree.by_id('tool-rent-page').descendants()
                    if n.tag == 'form' and n.attrs.get('class') == 'rent-form')
        self.assertIn(vat, form.descendants())
        blocks = [n for n in form.children if isinstance(n, Element) and n.tag == 'fieldset']
        self.assertIn(vat, blocks[-1].descendants())
        self.assertEqual([n.text() for n in blocks[-2].children if isinstance(n, Element) and n.tag == 'legend'], ['אופן ההצמדה'])
        css = (ROOT / 'assets/statso.css').read_text()
        self.assertIn('.rent-current th, .rent-current td { font-weight: 700; }', css)
        self.assertIn('html[dir="rtl"] #tool-rent-page input[dir="ltr"] { text-align: end; }', css)


if __name__ == '__main__':
    unittest.main()
