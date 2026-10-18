import json
import re
import subprocess
import unittest
from pathlib import Path

from tests.test_i18n import dictionary_keys

ROOT = Path(__file__).parent.parent

TOOLS = [("index", "tool-index-page", "ti"), ("fx", "tool-fx-page", "tf"),
         ("history", "tool-history-page", "th"),
         ("rate-history", "tool-rate-history-page", "trh"),
         ("fx-history", "tool-fx-history-page", "fxh"), ("rent", "tool-rent-page", "tr")]


class ToolsSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "index.html").read_text(encoding="utf-8")
        cls.scripts = {p.name: p.read_text(encoding="utf-8") for p in (ROOT / "assets").glob("*.js")}

    def test_exports_name_their_workbooks_and_tables(self):
        tools = self.scripts['statso-tools.js']
        self.assertEqual(tools.count("tableHtml(['פריט', 'ערך'], rows, 'פרטי החישוב')"), 2)
        self.assertIn("tableHtml(head, historyMatrix(), title + ' — ' + subtitle)", tools)
        self.assertIn("[sheet], {title: say(title)}", tools)
        self.assertIn("[sheet], {title: say(title) + ' — ' + say('שערים יציגים של בנק ישראל')}", tools)
        self.assertIn("[sheet], {title: title + ' — ' + subtitle}", tools)
        self.assertIn("autoFilter: 'A3:' + Statso.xlsx.columnName(head.length - 1) + (3 + historyRows.length)", tools)
        for name, title, head in [('ratehistory', 'ריבית היסטורית', 'head(mode)'),
                                  ('fxhistory', 'שערי חליפין היסטוריים', 'head()')]:
            source = self.scripts['statso-' + name + '.js']
            self.assertIn("tableHtml(" + head + ", matrix(), t('" + title + "') + ' — ' + subtitle())", source)
            self.assertIn("[sheet], {title: t('" + title + "') + ' — ' + subtitle()}", source)
            self.assertIn("autoFilter: 'A3:' + Statso.xlsx.columnName(selected.length) + (3 + rows.length)", source)
        for name in ('tools', 'ratehistory', 'fxhistory'):
            source = self.scripts['statso-' + name + '.js']
            self.assertEqual(source.count('freezeRows: 3'), 1)
            self.assertEqual(source.count("autoFilter: 'A3:'"), 1)
        rent = self.scripts['statso-rent.js']
        self.assertIn("tableHtml(['פריט', 'ערך'], contractRows(), 'פרטי ההסכם')", rent)
        self.assertIn("tableHtml(HEAD, matrix(period.rows), say(period.label) + ' · ' + Statso.core.formatMonthHe(period.start) + '–' + Statso.core.formatMonthHe(period.end))", rent)
        self.assertIn("[details, sheet], {title: say('הצמדת הסכם שכירות למדד')}", rent)
        self.assertNotIn('freezeRows', rent)
        self.assertNotIn('autoFilter', rent)

    def test_every_tool_has_a_route_a_page_and_both_exports(self):
        nav = self.scripts["statso-nav.js"]
        for route, page, prefix in TOOLS:
            self.assertIn(f"'#/tools/{route}': '{page}'", nav)
            self.assertIn(f'id="{page}"', self.html)
            self.assertIn(f'id="{prefix}-xlsx"', self.html)
            self.assertIn(f'id="{prefix}-pdf"', self.html)

    def test_the_history_tool_can_copy_to_the_clipboard(self):
        self.assertIn('id="th-copy"', self.html)
        self.assertIn("copyText", self.scripts["statso-tools.js"])

    def test_printing_restores_the_page_once_and_only_once(self):
        text = self.scripts["statso-export.js"]
        self.assertIn("if (restored) { return; }", text)
        self.assertNotIn("setTimeout(restore", text)
        self.assertLess(text.index("root.print();"), text.index("restore();\n    return true;"))

    def test_fx_history_offers_currencies_a_range_and_a_resolution(self):
        for field in ('id="fxh-currencies"', 'id="fxh-from"', 'id="fxh-to"',
                      'id="fxh-resolution"', 'id="fxh-copy"', 'id="fxh-averages"'):
            self.assertIn(field, self.html)
        for value in ('value="daily"', 'value="weekly"', 'value="monthly"', 'value="yearly"'):
            self.assertIn(value, self.html)

    def test_fx_history_averages_the_period_and_never_truncates_the_export(self):
        text = self.scripts["statso-fxhistory.js"]
        self.assertIn("cell.sum / cell.count", text)
        self.assertIn("count ? total / count : null", text)
        self.assertIn("rows.slice(0, MAX_RENDERED_ROWS)", text)
        matrix = text.split("function matrix()")[1].split("function subtitle()")[0]
        self.assertNotIn("MAX_RENDERED_ROWS", matrix, "the export must cover the whole range")

    def test_old_rates_are_not_rounded_away(self):
        core = self.scripts["statso-core.js"]
        self.assertIn("function formatRateSmart(x)", core)
        self.assertIn("formatRateSmart: formatRateSmart", core)
        self.assertIn("Statso.core.formatRateSmart", self.scripts["statso-fxhistory.js"])

    def test_the_dashboard_calculator_is_still_there(self):
        for marker in ('id="calculator-section"', 'name="calc-kind"', 'id="calc-amount"'):
            self.assertIn(marker, self.html)

    def test_chart_marks_the_five_requested_events(self):
        text = self.scripts["statso-chart.js"]
        for month, label in (("2008-09", "סאב"), ("2020-03", "קורונה"), ("2023-10", "7 באוקטובר"),
                             ("2025-06", "הראשונה"), ("2026-02", "השנייה")):
            self.assertRegex(text, r"month: '" + month + r"', label: '[^']*" + label)
        self.assertIn("const EVENT_COLOR = '#c2410c'", text)
        self.assertEqual(text.count("EVENT_COLOR;"), 2)  # the dashed line and the chip fill share it

    def test_rent_tool_covers_every_field_the_brief_asked_for(self):
        for field in ('id="tr-contract-date"', 'id="tr-landlord"', 'id="tr-tenant"',
                      'id="tr-base-start"', 'id="tr-base-end"', 'id="tr-base-rent"',
                      'id="tr-has-options"', 'id="tr-add-option"', 'id="tr-custom-base"',
                      'name="tr-floor"', 'id="tr-export-period"', 'id="tr-exclude-paid"'):
            self.assertIn(field, self.html)

    def test_linkage_never_falls_below_nominal_when_the_floor_is_chosen(self):
        text = self.scripts["statso-rent.js"]
        self.assertIn("form.floor === 'floor' ? Math.max(1, rawRatio) : rawRatio", text)

    def test_readings_shown_to_people_share_one_base(self):
        core = self.scripts["statso-core.js"]
        self.assertIn("function readingInBase(map, baseMonth, month, field)", core)
        self.assertIn("readingInBase: readingInBase", core)
        self.assertIn("Statso.core.readingInBase", self.scripts["statso-rent.js"])
        self.assertIn("Statso.core.readingInBase", self.scripts["statso-tools.js"])

    def test_construction_inputs_index_is_selectable_in_both_tools(self):
        for marker in ('name="ti-series"', 'value="cpi" id="ti-series-cpi"',
                       'value="construction" id="ti-series-construction"',
                       'id="th-cpi"', 'id="th-construction"', 'id="th-head"',
                       'id="data-construction-inputs"'):
            self.assertIn(marker, self.html)
        tools = self.scripts["statso-tools.js"]
        for marker in ("chained_1950_07", "INDEX_SERIES", "HISTORY_SERIES"):
            self.assertIn(marker, tools)

    def test_the_offline_build_can_inline_every_new_module(self):
        forbidden = ("</script", "</style", "<!--", "-->")
        for name in ("statso-xlsx.js", "statso-export.js", "statso-tools.js", "statso-rent.js", "statso-mcode.js",
                     "statso-ratehistory.js"):
            self.assertIn(name, self.html, f"{name} is not loaded by the page")
            for token in forbidden:
                self.assertNotIn(token, self.scripts[name], f"{token!r} would fail the offline build")

    def test_fx_card_says_which_trading_day_the_rate_belongs_to(self):
        card = re.search(r'<article class="kpi-card[^"]*" id="fx-kpi".*?</article>', self.html, re.DOTALL).group(0)
        self.assertIn("מעודכן לסוף יום המסחר האחרון", card)


FXH_DOM = r"""
global.window = {};
const timers = [];
window.setTimeout = (fn, ms) => { timers.push({fn, ms, live: true}); return timers.length; };
window.clearTimeout = id => { if (timers[id - 1]) { timers[id - 1].live = false; } };
window.addEventListener = () => {}; window.scrollTo = () => {}; window.requestAnimationFrame = fn => fn();
window.location = {hash: '#/tools/fx-history'};
const docListeners = {}, made = {}, page = {id: 'tool-fx-history-page'};
let boxes = [], checkedQueries = 0;
function element(id) {
  if (id === 'tools-trigger') { return null; }
  if (made[id]) { return made[id]; }
  const attrs = {};
  return made[id] = {id, value: '', textContent: '', hidden: false, checked: false, listeners: {}, dispatched: [], _html: '',
    get innerHTML() { return this._html; },
    set innerHTML(html) {
      this._html = html;
      if (id === 'fxh-currencies') {
        boxes = Array.from(html.matchAll(/<input type="checkbox" value="([^"]+)"( checked)?>/g), m => {
          const box = element('box-' + m[1]); box.value = m[1]; box.checked = Boolean(m[2]); return box; });
      }
    },
    setAttribute(k, v) { attrs[k] = String(v); }, getAttribute(k) { return k in attrs ? attrs[k] : null; },
    removeAttribute(k) { delete attrs[k]; }, hasAttribute(k) { return k in attrs; }, querySelectorAll() { return []; },
    closest(selector) { return selector.includes('#tool-fx-history-page') ? page : null; },
    addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); },
    dispatchEvent(event) {
      this.dispatched.push({type: event.type, bubbles: event.bubbles});
      (this.listeners[event.type] || []).forEach(fn => fn({type: event.type, target: this}));
      if (event.bubbles && docListeners[event.type]) { docListeners[event.type]({type: event.type, target: this}); }
      return true;
    }};
}
global.document = {title: 't', getElementById: element, addEventListener(type, fn) { docListeners[type] = fn; },
  querySelector() { return null; },
  querySelectorAll(selector) {
    if (selector === '#fxh-currencies input') { return boxes; }
    if (selector === '#fxh-currencies input:checked') { checkedQueries += 1; return boxes.filter(box => box.checked); }
    const flag = /^\[data-error-flag="(.+)"\]$/.exec(selector);
    return flag ? Object.values(made).filter(n => n.getAttribute('data-error-flag') === flag[1]) : [];
  }};
"""
FXH_RUN = r"""
const S = window.Statso;
S.xlsx = {STYLE: {}};
const daily = {currencies: Object.fromEntries(['USD', 'EUR', 'GBP'].map((code, i) =>
  [code, {unit: 1, dates: ['2024-05-02', '2024-06-03'], rates: [3.5 + i, 3.6 + i]}]))};
let loads = 0;
S.data = {loadFxDaily: () => { loads += 1; return FAIL_FIRST && loads === 1 ? Promise.reject(new Error('x')) : Promise.resolve(daily); }};
S.nav.init();
S.fxhistory.init({rates: ['USD', 'EUR', 'GBP'].map(code => ({code, first_date: '2020-01-01', latest: {date: '2025-03-01'}}))});
const live = element('result-live');
const pause = () => timers.filter(t => t.live && t.ms < 1000).forEach(t => { t.live = false; t.fn(); });
const snap = () => ({checked: boxes.map(b => b.checked), builds: checkedQueries, loads,
  selected: S.fxhistory.state().selected.slice(), rows: S.fxhistory.state().rows.length,
  error: element('fxh-error').textContent, invalid: boxes.map(b => b.getAttribute('aria-invalid')),
  described: boxes.map(b => b.getAttribute('aria-describedby')), boxEvents: boxes.reduce((n, b) => n + b.dispatched.length, 0)});
const press = id => {
  checkedQueries = 0; live.textContent = '';
  element(id).listeners.click.forEach(fn => fn({type: 'click', target: element(id), currentTarget: element(id)}));
  const seen = snap(); pause(); seen.spoken = live.textContent; seen.sent = element(id).dispatched.splice(0); return seen;
};
const tick = () => new Promise(resolve => setTimeout(resolve, 0));
(async () => {
  await tick();
  const out = {initial: snap()};
  if (FAIL_FIRST) {
    out.all = press('fxh-select-all'); await tick(); out.loaded = snap();
  } else {
    const box = boxes[2];
    box.checked = true; checkedQueries = 0; box.dispatchEvent(new Event('change', {bubbles: true}));
    out.box = {builds: checkedQueries}; pause(); out.box.spoken = live.textContent;
    box.checked = false; box.dispatchEvent(new Event('change', {bubbles: true})); pause(); box.dispatched.length = 0;
    out.all = press('fxh-select-all'); out.allAgain = press('fxh-select-all');
    out.none = press('fxh-clear-all'); out.noneAgain = press('fxh-clear-all');
    await tick(); out.afterTick = snap();
    out.back = press('fxh-select-all');
  }
  process.stdout.write(JSON.stringify(out));
})();
"""


def run_fx_history(fail_first=False):
    script = FXH_DOM + "".join("require(" + json.dumps(str(ROOT / "assets" / n)) + ");"
                               for n in ("statso-core.js", "statso-fxhistory.js", "statso-nav.js")) \
        + "const FAIL_FIRST = " + json.dumps(fail_first) + ";" + FXH_RUN
    result = subprocess.run(["node", "-e", script], cwd=ROOT, capture_output=True, text=True)
    if result.returncode:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


class FxHistoryBulkSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "index.html").read_text(encoding="utf-8")
        cls.css = (ROOT / "assets/statso.css").read_text(encoding="utf-8")
        cls.normal = run_fx_history()
        cls.retry = run_fx_history(True)

    def test_buttons_are_only_in_the_fx_history_currencies_fieldset(self):
        page = re.search(r'<section\b[^>]*id="tool-fx-history-page".*?</section>', self.html, re.DOTALL).group(0)
        fieldset = re.search(r'<legend>מטבעות</legend>.*?</fieldset>', page, re.DOTALL).group(0)
        buttons = [f'<button type="button" class="btn-ghost" id="{id}">{label}</button>'
                   for id, label in (('fxh-select-all', 'בחירת כל המטבעות'),
                                     ('fxh-clear-all', 'ניקוי כל המטבעות'))]
        self.assertEqual(fieldset.count('<button'), 2)
        self.assertIn('<div class="fxh-bulk-actions">' + ''.join(buttons) + '</div>', fieldset)
        self.assertLess(fieldset.index('class="fxh-bulk-actions"'), fieldset.index('id="fxh-currencies"'))
        for id in ('fxh-select-all', 'fxh-clear-all'):
            self.assertEqual(self.html.count(f'id="{id}"'), 1)
        for button in re.findall(r'<button\b[^>]*>', fieldset):
            self.assertNotIn('aria-label', button)
        export_fieldset = re.search(r'<fieldset\b[^>]*id="mc-currencies-block".*?</fieldset>', self.html, re.DOTALL).group(0)
        self.assertNotIn('<button', export_fieldset)
        self.assertRegex(page, r'<p\b[^>]*id="fxh-error"[^>]*role="alert"')

    def test_both_labels_have_exact_english_translations(self):
        source = (ROOT / "assets/statso-lang-en.js").read_text(encoding="utf-8")
        keys = dictionary_keys()
        for he, en in (('בחירת כל המטבעות', 'Select all currencies'),
                       ('ניקוי כל המטבעות', 'Clear all currencies')):
            self.assertIn(he, keys)
            self.assertIn(f"'{he}': '{en}',", source)

    def test_actions_wrap_and_meet_the_minimum_target_size_before_forced_colors(self):
        for selector, declaration in ((r'\.fxh-bulk-actions', 'flex-wrap: wrap'),
                                      (r'\.fxh-bulk-actions \.btn-ghost', 'min-height: 24px')):
            rule = re.search(selector + r' \{([^}]*)\}', self.css)
            self.assertIsNotNone(rule)
            self.assertIn(declaration, rule.group(1))
            self.assertLess(rule.end(), self.css.index('@media (forced-colors: active)'))
        self.assertIn('.fxh-currencies, .tool-checkboxes { display: flex; flex-wrap: wrap; gap: 10px 20px; }', self.css)

    def test_select_all_recomputes_once_and_announces_like_a_checkbox(self):
        s = self.normal
        self.assertEqual(s['initial']['checked'], [True, True, False])
        self.assertEqual(s['box']['builds'], 1)
        self.assertEqual(s['box']['spoken'], 'הטבלה עודכנה: 2 שורות בטווח שנבחר.')
        for action in ('all', 'allAgain', 'back'):
            with self.subTest(action=action):
                state = s[action]
                self.assertEqual(state['checked'], [True] * 3)
                self.assertEqual(state['builds'], 1)
                self.assertEqual(state['selected'], ['USD', 'EUR', 'GBP'])
                self.assertEqual(state['error'], '')
                self.assertEqual(state['invalid'], [None] * 3)
                self.assertEqual(state['spoken'], s['box']['spoken'])

    def test_clear_all_uses_existing_validation_without_auto_selecting(self):
        s = self.normal
        for action in ('none', 'noneAgain'):
            with self.subTest(action=action):
                state = s[action]
                self.assertEqual(state['checked'], [False] * 3)
                self.assertEqual(state['builds'], 1)
                self.assertEqual(state['error'], 'יש לבחור מטבע אחד לפחות.')
                self.assertEqual(state['invalid'], ['true'] * 3)
                self.assertEqual(state['described'], ['fxh-error'] * 3)
                self.assertEqual(state['selected'], [])
                self.assertEqual(state['rows'], 0)
                self.assertEqual(state['spoken'], '')
        self.assertEqual(s['afterTick']['checked'], [False] * 3)

    def test_each_press_sends_one_bubbling_change_without_checkbox_events_or_reloading(self):
        for action in ('all', 'allAgain', 'none', 'noneAgain', 'back'):
            with self.subTest(action=action):
                state = self.normal[action]
                self.assertEqual(state['sent'], [{'type': 'change', 'bubbles': True}])
                self.assertEqual(state['boxEvents'], 0)
                self.assertEqual(state['loads'], 1)

    def test_select_all_retries_a_failed_initial_load(self):
        r = self.retry
        self.assertEqual(r['initial']['loads'], 1)
        self.assertEqual(r['all']['loads'], 2)
        self.assertEqual(r['loaded']['selected'], ['USD', 'EUR', 'GBP'])
        self.assertEqual(r['loaded']['builds'], 1)


def run_export_script(dom, modules, body):
    script = dom + '\n' + '\n'.join('require(' + json.dumps(str(ROOT / 'assets' / n)) + ');'
                                     for n in modules) + '\n' + body
    result = subprocess.run(['node', '-e', script], cwd=ROOT, capture_output=True, text=True)
    if result.returncode:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


EXPORT_MODULES = ('statso-core.js', 'statso-xlsx.js', 'statso-export.js')
TOOLS_DOM = FXH_DOM + r'''
const radios = {'ti-series': 'cpi', 'ti-mode': 'for', 'tf-kind': 'convert'};
document.querySelector = selector => {
  const match = /^input\[name="([^"]+)"\]:checked$/.exec(selector);
  return match ? {value: radios[match[1]]} : null;
};
element('ti-amount').value = '1000';
element('tf-date-label').firstChild = {textContent: ''};
'''
CAPTURE_EXPORTS = '''
const S = window.Statso;
S.i18n = {t: s => s, onChange() {}};
let workbook, pdf, copied;
S.exporter.downloadWorkbook = (name, sheets) => { workbook = sheets; };
S.exporter.printDocument = (title, html) => { pdf = html; };
S.exporter.copyText = text => { copied = text; return Promise.resolve(); };
S.exporter.flash = () => {};
const fire = (id, event = 'click') => element(id).dispatchEvent(new Event(event));
'''
INDEX_DOC = '''
const doc = {first_month: '2025-07', last_month: '2026-07', observations: [
  {month: '2025-07', value: 104.2, chained_1951_09: 1000},
  {month: '2026-07', value: 105.8, chained_1951_09: 1016.4347}]};
'''
I18N_BODY = '''
document.documentElement = {setAttribute() {}};
document.body = {nodeType: 1, tagName: 'BODY', hasAttribute: () => false,
  firstChild: null, querySelectorAll: () => []};
'''


def exported_pairs(sheet):
    return {row[0]['v']: row[1] for row in sheet['rows'] if len(row) == 2}


def pdf_pairs(html):
    return dict(re.findall(r'<tr><td>([^<]*)</td><td[^>]*>([^<]*)</td></tr>', html))


class ExportPrecisionTests(unittest.TestCase):
    def test_table_html_formats_typed_cells_and_preserves_plain_cells(self):
        html = run_export_script('global.window = {};', EXPORT_MODULES, '''
process.stdout.write(JSON.stringify(window.Statso.exporter.tableHtml([], [[
  {v: 1.0164347, f: 'ratio'}, {v: 3.103, f: 'rate'}, {v: 0.4658, f: 'rate'},
  {v: 0.000025, f: 'rateSmart'}, {v: 0.00006939, f: 'rateSmart'},
  5137.42, 'unchanged', null, 1.5, {v: 1.5}]])));
''')
        cells = re.findall(r'<td([^>]*)>(.*?)</td>', html)
        self.assertEqual([v for _, v in cells], ['1.0164', '3.103', '0.4658', '0.000025',
                                               '0.00006939', '5,137.42', 'unchanged', '', '1.50', '1.50'])
        self.assertEqual([a for a, _ in cells], [' dir="ltr"'] * 6 + ['', ''] + [' dir="ltr"'] * 2)

    def test_index_exports_precise_numeric_ratio_and_rebased_index(self):
        seen = run_export_script(TOOLS_DOM, EXPORT_MODULES + ('statso-tools.js',),
                                 CAPTURE_EXPORTS + INDEX_DOC + '''
const map = S.core.buildIndexMap(doc.observations);
S.tools.init(doc, map);
S.tools.exportIndex('xlsx'); S.tools.exportIndex('pdf');
const ratio = doc.observations[1].chained_1951_09 / doc.observations[0].chained_1951_09;
const raw = S.core.readingInBase(map, '2025-07', '2026-07');
process.stdout.write(JSON.stringify({workbook, pdf, ratio, rounded: Number(raw.toFixed(6)),
  expectedRatio: S.core.formatNumber(ratio, 4), styles: S.xlsx.STYLE}));
''')
        pairs = exported_pairs(seen['workbook'][0])
        self.assertEqual(pdf_pairs(seen['pdf'])['מקדם הצמדה'], seen['expectedRatio'])
        self.assertEqual(pairs['מקדם הצמדה'], {'v': seen['ratio'], 's': seen['styles']['ratio']})
        self.assertIsInstance(pairs['מקדם הצמדה']['v'], (int, float))
        self.assertEqual(pairs['ערך מדד היעד (בבסיס מדד הבסיס)'],
                         {'v': seen['rounded'], 's': seen['styles']['money']})
        self.assertNotEqual(seen['rounded'], 105.8)
        self.assertNotEqual(seen['rounded'], 1016.4347)

    def test_currency_convert_and_link_exports_keep_screen_precision(self):
        seen = run_export_script(TOOLS_DOM, EXPORT_MODULES + ('statso-tools.js',), CAPTURE_EXPORTS + '''
const daily = {currencies: {
  USD: {unit: 1, dates: ['2026-10-01', '2026-10-09'], rates: [3.103, 3.452]},
  DKK: {unit: 1, dates: ['2026-10-01', '2026-10-09'], rates: [0.4658, 0.5]}}};
S.data = {loadFxDaily: () => Promise.resolve(daily)};
S.tools.initFx({rates: ['USD', 'DKK'].map(code => ({code, first_date: '2026-10-01', latest: {date: '2026-10-09'}}))});
(async () => {
  await new Promise(resolve => setTimeout(resolve, 0));
  element('tf-amount').value = '1000'; element('tf-date').value = '2026-10-01';
  element('tf-from').value = 'DKK'; element('tf-to').value = 'ILS'; S.tools.computeFx();
  S.tools.exportFx('xlsx'); S.tools.exportFx('pdf'); const convert = {workbook, pdf};
  radios['tf-kind'] = 'link'; element('tf-currency').value = 'USD';
  element('tf-date-target').value = '2026-10-09'; S.tools.computeFx();
  S.tools.exportFx('xlsx'); S.tools.exportFx('pdf');
  process.stdout.write(JSON.stringify({convert, link: {workbook, pdf}, styles: S.xlsx.STYLE}));
})();
''')
        styles = seen['styles']
        self.assertEqual(pdf_pairs(seen['convert']['pdf'])['שער'], '0.4658')
        self.assertEqual(exported_pairs(seen['convert']['workbook'][0])['שער'],
                         {'v': 0.4658, 's': styles['rate']})
        pdf = pdf_pairs(seen['link']['pdf'])
        xlsx = exported_pairs(seen['link']['workbook'][0])
        for label, text, value, style in (('שער בסיס', '3.103', 3.103, 'rate'),
                                          ('שער יעד', '3.452', 3.452, 'rate'),
                                          ('מקדם הצמדה', '1.1125', 3.452 / 3.103, 'ratio')):
            self.assertEqual(pdf[label], text)
            self.assertEqual(xlsx[label], {'v': value, 's': styles[style]})
            self.assertIsInstance(xlsx[label]['v'], (int, float))
        self.assertEqual(xlsx['סכום מוצמד (₪)']['s'], styles['money'])

    def test_fx_history_rates_averages_and_clipboard_keep_small_digits(self):
        seen = run_export_script(FXH_DOM, EXPORT_MODULES + ('statso-fxhistory.js',), CAPTURE_EXPORTS + '''
const daily = {currencies: {
  USD: {unit: 1, dates: ['2026-10-01', '2026-10-09', '2026-10-12'], rates: [3.103, 3.6, 3.1026499999999997]},
  DKK: {unit: 1, dates: ['2026-10-01', '2026-10-09', '2026-10-12'], rates: [0.00006939, 0.4658, 0.4653]}}};
S.data = {loadFxDaily: () => Promise.resolve(daily)};
element('fxh-resolution').value = 'daily';
S.fxhistory.init({rates: ['USD', 'DKK'].map(code => ({code, first_date: '2026-10-01', latest: {date: '2026-10-12'}}))});
(async () => {
  await new Promise(resolve => setTimeout(resolve, 0));
  fire('fxh-xlsx'); fire('fxh-pdf'); fire('fxh-copy');
  const state = S.fxhistory.state();
  const raw = state.rows.map(r => r.values.map(v => v.rate));
  raw.push(state.averages.map(a => a.average));
  process.stdout.write(JSON.stringify({workbook, pdf, copied, styles: S.xlsx.STYLE,
    rounded: raw.map(row => row.map(v => Number(v.toFixed(10)))),
    formatted: raw.map(row => row.map(S.core.formatRateSmart))}));
})();
''')
        pdf_rows = re.findall(r'<tr>(.*?)</tr>', seen['pdf'])[1:]
        self.assertEqual(len(pdf_rows), 4)
        for row, expected in zip(pdf_rows, seen['formatted']):
            self.assertEqual(re.findall(r'<td[^>]*>(.*?)</td>', row)[1:], expected)
        # the PDF formats the unrounded rate: 3.1026499999999997 shows 3.1026 on screen, and its 10-decimal
        # rounding (3.10265) would print 3.1027
        self.assertEqual(re.findall(r'<td[^>]*>(.*?)</td>', pdf_rows[2])[1], '3.1026')
        rows = seen['workbook'][0]['rows'][3:]
        self.assertEqual(len(rows), 4)
        for i, (row, values) in enumerate(zip(rows, seen['rounded'])):
            self.assertEqual(row[0]['s'], seen['styles']['header' if i == 3 else 'boxed'])
            for cell, value in zip(row[1:], values):
                self.assertEqual(cell, {'v': value, 's': seen['styles']['rateBold' if i == 3 else 'rate']})
                self.assertIsInstance(cell['v'], (int, float))
        self.assertIn('0.00006939', seen['copied'])


class EnglishClipboardTests(unittest.TestCase):
    def test_fx_history_clipboard_translates_all_resolutions(self):
        seen = run_export_script(FXH_DOM + I18N_BODY,
                                 EXPORT_MODULES + ('statso-lang-en.js', 'statso-i18n.js', 'statso-fxhistory.js'), '''
const S = window.Statso;
let copied;
S.exporter.copyText = text => { copied = text; return Promise.resolve(); };
S.exporter.flash = () => {};
const daily = {currencies: Object.fromEntries(['USD', 'EUR', 'JPY'].map((code, i) => [code,
  {unit: code === 'JPY' ? 100 : 1, dates: ['2024-05-02', '2024-06-03', '2025-07-02'], rates: [3.1 + i, 3.5 + i, 3.6 + i]}]))};
S.data = {loadFxDaily: () => Promise.resolve(daily)};
element('fxh-resolution').value = 'daily';
S.fxhistory.init({rates: ['USD', 'EUR', 'JPY'].map(code => ({code, first_date: '2024-05-02', latest: {date: '2025-07-02'}}))});
(async () => {
  await new Promise(resolve => setTimeout(resolve, 0));
  boxes.forEach(b => { b.checked = true; }); S.fxhistory.build();
  element('fxh-copy').dispatchEvent(new Event('click')); const hebrew = copied;
  S.i18n.set('en'); const english = {};
  for (const resolution of ['daily', 'weekly', 'monthly', 'yearly']) {
    element('fxh-resolution').value = resolution;
    element('fxh-resolution').dispatchEvent(new Event('change'));
    element('fxh-copy').dispatchEvent(new Event('click')); english[resolution] = copied;
  }
  process.stdout.write(JSON.stringify({hebrew, english}));
})();
''')
        self.assertIn('דולר ארה״ב (USD)', seen['hebrew'].splitlines()[0])
        for resolution, tsv in seen['english'].items():
            with self.subTest(resolution=resolution):
                self.assertNotRegex(tsv, r'[֐-׿]')
                self.assertIn('US dollar (USD)', tsv)
                self.assertIn('Period average', tsv)
                self.assertIn('(EUR)', tsv)
                self.assertIn('(JPY)', tsv)
                self.assertGreater(len(tsv.splitlines()), 2)
        self.assertIn('Week of ', seen['english']['weekly'])

    def test_index_and_interest_history_clipboards_remain_english(self):
        seen = run_export_script(TOOLS_DOM + I18N_BODY,
                                 EXPORT_MODULES + ('statso-lang-en.js', 'statso-i18n.js',
                                                   'statso-tools.js', 'statso-ratehistory.js'), INDEX_DOC + '''
const S = window.Statso;
let copied;
S.exporter.copyText = text => { copied = text; return Promise.resolve(); };
S.exporter.flash = () => {};
element('th-cpi').checked = true;
S.tools.init(doc, S.core.buildIndexMap(doc.observations));
S.i18n.set('en'); element('th-copy').dispatchEvent(new Event('click'));
const out = {index: copied};
element('trh-boi').checked = element('trh-prime').checked = true;
element('trh-mode').value = 'points';
S.ratehistory.init({first_change_date: '2025-01-01', last_change_date: '2026-07-01',
  changes: [{date: '2025-01-01', rate: 4.5}, {date: '2026-07-01', rate: 3.25}]});
for (const mode of ['points', 'monthly']) {
  element('trh-mode').value = mode; element('trh-mode').dispatchEvent(new Event('change'));
  element('trh-copy').dispatchEvent(new Event('click')); out[mode] = copied;
}
process.stdout.write(JSON.stringify(out));
''')
        for tool, tsv in seen.items():
            with self.subTest(tool=tool):
                self.assertNotRegex(tsv, r'[֐-׿]')
                self.assertGreater(len(tsv.splitlines()), 2)
        self.assertIn('Consumer price index', seen['index'])
        for mode in ('points', 'monthly'):
            self.assertIn('Bank of Israel', seen[mode])
            self.assertIn('Prime', seen[mode])


if __name__ == "__main__":
    unittest.main()
