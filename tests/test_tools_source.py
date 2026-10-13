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


if __name__ == "__main__":
    unittest.main()
