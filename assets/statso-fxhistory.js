(function (root) {
  'use strict';
  const Statso = root.Statso = root.Statso || {};
  const S = function () { return Statso.xlsx.STYLE; };
  const MAX_RENDERED_ROWS = 2000;   // the table stays usable; exports still carry everything
  let summary = null;
  let daily = null;
  let pending = false;
  let rows = [];
  let selected = [];
  let averages = [];

  function el(id) { return document.getElementById(id); }
  function on(id, event, handler) { const node = el(id); if (node) { node.addEventListener(event, handler); } }
  function t(text) { return Statso.i18n ? Statso.i18n.t(text) : text; }

  // ---------- period keys ---------------------------------------------------
  function weekStart(iso) {
    const date = new Date(iso + 'T00:00:00Z');
    date.setUTCDate(date.getUTCDate() - date.getUTCDay());   // Sunday, the Israeli week start
    return date.toISOString().slice(0, 10);
  }

  function periodKey(iso, resolution) {
    if (resolution === 'yearly') { return iso.slice(0, 4); }
    if (resolution === 'monthly') { return iso.slice(0, 7); }
    if (resolution === 'weekly') { return weekStart(iso); }
    return iso;
  }

  function periodLabel(key, resolution) {
    if (resolution === 'yearly') { return key; }
    if (resolution === 'monthly') { return Statso.core.formatMonthHe(key); }
    if (resolution === 'weekly') { return 'שבוע של ' + Statso.core.formatIsoDateHe(key); }
    return Statso.core.formatIsoDateHe(key);
  }

  // ---------- computation ---------------------------------------------------
  function selectedCodes() {
    return Array.prototype.map.call(document.querySelectorAll('#fxh-currencies input:checked'),
      function (box) { return box.value; });
  }

  // The fields an error is about are marked invalid and point at the message, so they say so when focused.
  function showError(message, fields) {
    el('fxh-error').textContent = message;
    Statso.core.flagFields('fxh-error', fields || []);
  }

  function fail(message, fields) {
    rows = []; averages = [];
    showError(message, fields);
    el('fxh-head').innerHTML = ''; el('fxh-body').innerHTML = '';
    el('fxh-averages').innerHTML = ''; el('fxh-note').textContent = '';
  }

  function build() {
    if (!daily) { return; }
    selected = selectedCodes();
    const from = el('fxh-from').value;
    const to = el('fxh-to').value;
    const resolution = el('fxh-resolution').value;
    const range = ['fxh-from', 'fxh-to'];
    if (!selected.length) { fail('יש לבחור מטבע אחד לפחות.', Array.prototype.slice.call(document.querySelectorAll('#fxh-currencies input'))); return; }
    if (!from || !to) { fail('יש לבחור טווח תאריכים.', range.filter(function (id) { return !el(id).value; })); return; }
    if (from > to) { fail('תאריך ההתחלה חייב להיות מוקדם מתאריך הסיום.', range); return; }

    // period key -> code -> {sum, count}
    const buckets = new Map();
    averages = selected.map(function (code) {
      const entry = daily.currencies[code];
      let total = 0, count = 0;
      if (entry) {
        for (let i = 0; i < entry.dates.length; i += 1) {
          const date = entry.dates[i];
          if (date < from || date > to) { continue; }
          const rate = entry.rates[i];
          total += rate; count += 1;
          const key = periodKey(date, resolution);
          let bucket = buckets.get(key);
          if (!bucket) { bucket = {}; buckets.set(key, bucket); }
          const cell = bucket[code] || (bucket[code] = {sum: 0, count: 0});
          cell.sum += rate; cell.count += 1;
        }
      }
      return {code: code, average: count ? total / count : null, count: count};
    });

    rows = Array.from(buckets.keys()).sort().map(function (key) {
      const bucket = buckets.get(key);
      return {key: key, label: periodLabel(key, resolution),
        values: selected.map(function (code) {
          const cell = bucket[code];
          return cell ? {rate: cell.sum / cell.count, count: cell.count} : null;
        })};
    });

    if (!rows.length) { fail('אין שערים שפורסמו בטווח שנבחר.', range); return; }
    showError('');
    render(resolution);
  }

  function name(code) { return Statso.core.CURRENCY_NAMES[code] || code; }

  function render(resolution) {
    el('fxh-head').innerHTML = '<th scope="col">' + t('תקופה') + '</th>'
      + selected.map(function (code) {
        const entry = daily.currencies[code];
        const unit = entry && entry.unit !== 1 ? ' ×' + entry.unit : '';
        return '<th scope="col">' + Statso.core.escapeHtml(name(code)) + ' <span class="currency-code">' + Statso.core.escapeHtml(code + unit) + '</span></th>';
      }).join('');
    const shown = rows.slice(0, MAX_RENDERED_ROWS);
    el('fxh-body').innerHTML = shown.map(function (row) {
      return '<tr><th scope="row" dir="ltr">' + Statso.core.escapeHtml(row.label) + '</th>'
        + row.values.map(function (value) {
          return '<td dir="ltr">' + (value ? Statso.core.formatRateSmart(value.rate) : '—') + '</td>';
        }).join('') + '</tr>';
    }).join('');
    el('fxh-averages').innerHTML = '<div class="rent-summary-grid">' + averages.map(function (item) {
      return '<div><span>ממוצע לתקופה · <span>' + Statso.core.escapeHtml(name(item.code)) + '</span></span><strong dir="ltr">'
        + (item.average === null ? '—' : Statso.core.formatRateSmart(item.average)) + '</strong></div>';
    }).join('') + '</div>';
    const note = resolution === 'daily'
      ? 'כל שער שפורסם בטווח. הסדרות אינן רציפות — אין פרסום בסופי שבוע ובחלק מהחגים.'
      : 'כל שורה היא ממוצע השערים שפורסמו באותה תקופה.';
    el('fxh-note').textContent = rows.length + ' שורות בטווח שנבחר. ' + note
      + (rows.length > MAX_RENDERED_ROWS
        ? ' מוצגות ' + MAX_RENDERED_ROWS + ' השורות הראשונות; הייצוא וההעתקה כוללים את כל הטווח.' : '');
  }

  // ---------- export --------------------------------------------------------
  function head() {
    return [t('תקופה')].concat(selected.map(function (code) { return t(name(code) + ' (' + code + ')'); }));
  }

  // v is the tidy stored value; p is the unrounded rate, so the PDF shows exactly what the screen shows (no double rounding)
  function rateCell(rate) { return {v: Number(rate.toFixed(10)), f: 'rateSmart', p: rate}; }

  function matrix() {
    const body = rows.map(function (row) {
      return [t(row.label)].concat(row.values.map(function (value) {
        return value ? rateCell(value.rate) : '';
      }));
    });
    body.push([t('ממוצע לתקופה')].concat(averages.map(function (item) {
      return item.average === null ? '' : rateCell(item.average);
    })));
    return body;
  }

  function subtitle() {
    return Statso.core.formatIsoDateHe(el('fxh-from').value) + '–'
      + Statso.core.formatIsoDateHe(el('fxh-to').value);
  }

  function exportRates(kind) {
    if (!rows.length) { return; }
    const columns = [{width: 16}].concat(selected.map(function () { return {width: 15}; }));
    if (kind === 'xlsx') {
      const sheet = {name: 'שערי חליפין', columns: columns,
        freezeRows: 3, autoFilter: 'A3:' + Statso.xlsx.columnName(selected.length) + (3 + rows.length),
        rows: [[{v: t('שערי חליפין היסטוריים') + ' — ' + subtitle(), s: S().title}], [],
          head().map(function (text) { return {v: text, s: S().header}; })]};
      const body = matrix();
      body.forEach(function (row, index) {
        const last = index === body.length - 1;
        sheet.rows.push([{v: row[0], s: last ? S().header : S().boxed}]
          .concat(row.slice(1).map(function (cell) { return cell === '' ? '' : {v: cell.v, s: last ? S().rateBold : S().rate}; })));
      });
      Statso.exporter.downloadWorkbook('statso-' + t('שערי חליפין') + '-' + Statso.exporter.stamp() + '.xlsx', [sheet], {title: t('שערי חליפין היסטוריים') + ' — ' + subtitle()});
      return;
    }
    Statso.exporter.printDocument(t('שערי חליפין היסטוריים') + ' — ' + subtitle(),
      Statso.exporter.documentHtml('שערי חליפין היסטוריים', subtitle(),
        [Statso.exporter.tableHtml(head(), matrix(), t('שערי חליפין היסטוריים') + ' — ' + subtitle())]));
  }

  function copyRates() {
    if (!rows.length) { return; }
    const button = el('fxh-copy');
    Statso.exporter.copyText(Statso.exporter.toTsv([head()].concat(matrix())))
      .then(function () { Statso.exporter.flash(button, t('הועתק ✓')); })
      .catch(function () { Statso.exporter.flash(button, t('ההעתקה נכשלה')); });
  }

  // ---------- wiring --------------------------------------------------------
  function ensureData() {
    if (daily || pending) { return; }
    pending = true;
    el('fxh-error').textContent = 'טוען שערי חליפין…';
    Statso.data.loadFxDaily().then(function (doc) {
      daily = doc; pending = false; el('fxh-error').textContent = ''; build();
    }).catch(function () {
      pending = false; fail('לא ניתן לטעון את שערי החליפין.');
    });
  }

  // Both buttons set every box and then recompute once: assigning .checked fires no 'change', so the boxes' own
  // listeners stay quiet. A click fires no 'change' either, and that is what statso-nav.js listens to before it says
  // the table was updated, so the button sends one bubbling 'change' itself, after the table is built.
  function setAllCurrencies(checked, button) {
    document.querySelectorAll('#fxh-currencies input').forEach(function (box) { box.checked = checked; });
    ensureData(); build();
    button.dispatchEvent(new Event('change', {bubbles: true}));
  }

  function init(fxSummary) {
    summary = fxSummary;
    const rates = summary.rates || [];
    el('fxh-currencies').innerHTML = rates.map(function (row, index) {
      const checked = index < 2 ? ' checked' : '';
      return '<label class="fxh-currency"><input type="checkbox" value="' + Statso.core.escapeHtml(row.code) + '"' + checked + '> '
        + Statso.core.escapeHtml(name(row.code)) + ' <span class="currency-code">' + Statso.core.escapeHtml(row.code) + '</span></label>';
    }).join('');
    const latest = rates.map(function (row) { return row.latest.date; }).sort();
    const starts = rates.map(function (row) { return row.first_date; }).sort();
    const newest = latest[latest.length - 1];
    const from = el('fxh-from'); const to = el('fxh-to');
    from.min = starts[0]; from.max = newest; to.min = starts[0]; to.max = newest;
    to.value = newest;
    from.value = (Number(newest.slice(0, 4)) - 2) + newest.slice(4);
    document.querySelectorAll('#fxh-currencies input').forEach(function (box) {
      box.addEventListener('change', function () { ensureData(); build(); });
    });
    on('fxh-select-all', 'click', function () { setAllCurrencies(true, el('fxh-select-all')); });
    on('fxh-clear-all', 'click', function () { setAllCurrencies(false, el('fxh-clear-all')); });
    ['fxh-from', 'fxh-to', 'fxh-resolution'].forEach(function (id) {
      on(id, 'change', function () { ensureData(); build(); });
    });
    on('fxh-copy', 'click', copyRates);
    on('fxh-xlsx', 'click', function () { exportRates('xlsx'); });
    on('fxh-pdf', 'click', function () { exportRates('pdf'); });
    if (Statso.i18n) { Statso.i18n.onChange(function () { if (rows.length) { build(); } }); }
    ensureData();
  }

  Statso.fxhistory = {init: init, build: build, periodKey: periodKey, periodLabel: periodLabel,
    weekStart: weekStart, matrix: matrix, head: head, MAX_RENDERED_ROWS: MAX_RENDERED_ROWS,
    state: function () { return {rows: rows, averages: averages, selected: selected}; }};
})(window);
