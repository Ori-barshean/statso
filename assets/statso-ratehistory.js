(function (root) {
  'use strict';
  const Statso = root.Statso = root.Statso || {};
  const S = function () { return Statso.xlsx.STYLE; };
  let doc = null;
  let rows = [];
  let selected = [];

  const SERIES = [
    {key: 'boi', label: 'ריבית בנק ישראל', value: function (rate) { return rate; }},
    {key: 'prime', label: 'ריבית פריים', value: function (rate) { return Statso.core.primeRate(rate); }}
  ];

  function el(id) { return document.getElementById(id); }
  function on(id, event, handler) { const node = el(id); if (node) { node.addEventListener(event, handler); } }
  function t(text) { return Statso.i18n ? Statso.i18n.t(text) : text; }
  function seriesByKey(key) { return SERIES.filter(function (s) { return s.key === key; })[0]; }

  // ---------- rate lookup ----------------------------------------------------
  function rateAt(isoDate) {
    const changes = doc.changes;
    let found = null;
    for (let i = 0; i < changes.length; i += 1) {
      if (changes[i].date > isoDate) { break; }
      found = changes[i];
    }
    return found ? found.rate : null;
  }

  function daysInMonth(monthKey) {
    const year = Number(monthKey.slice(0, 4)); const month = Number(monthKey.slice(5, 7));
    return new Date(Date.UTC(year, month, 0)).getUTCDate();
  }

  function monthlyRate(monthKey, seriesKey) {
    const days = daysInMonth(monthKey);
    let sum = 0; let count = 0; const distinct = new Set();
    for (let day = 1; day <= days; day += 1) {
      const iso = monthKey + '-' + String(day).padStart(2, '0');
      const boiRate = rateAt(iso);
      if (boiRate === null) { continue; }
      distinct.add(boiRate);
      sum += seriesByKey(seriesKey).value(boiRate);
      count += 1;
    }
    if (!count) { return {rate: null, changed: false}; }
    return {rate: sum / count, changed: distinct.size > 1};
  }

  // ---------- computation ---------------------------------------------------
  function selectedKeys() {
    return SERIES.filter(function (s) { return el('trh-' + s.key).checked; }).map(function (s) { return s.key; });
  }

  function fail(message) {
    rows = [];
    el('trh-error').textContent = message;
    el('trh-head').innerHTML = ''; el('trh-body').innerHTML = ''; el('trh-note').textContent = '';
  }

  function build() {
    if (!doc) { return; }
    selected = selectedKeys();
    const from = el('trh-from').value;
    const to = el('trh-to').value;
    const mode = el('trh-mode').value;
    if (!selected.length) { fail('יש לבחור סדרה אחת לפחות.'); return; }
    if (!from || !to) { fail('יש לבחור טווח תאריכים.'); return; }
    if (from > to) { fail('תאריך ההתחלה חייב להיות מוקדם מתאריך הסיום.'); return; }

    if (mode === 'points') {
      rows = doc.changes.filter(function (change) { return change.date >= from && change.date <= to; })
        .map(function (change) {
          return {label: Statso.core.formatIsoDateHe(change.date), changed: false,
            values: selected.map(function (key) { return seriesByKey(key).value(change.rate); })};
        });
      if (!rows.length) { fail('אין שינויי ריבית בטווח שנבחר.'); return; }
    } else {
      const fromMonth = from.slice(0, 7); const toMonth = to.slice(0, 7);
      const months = [];
      let cursor = fromMonth;
      while (cursor <= toMonth) {
        months.push(cursor);
        cursor = Statso.core.shiftMonth(cursor, 1);
      }
      rows = months.map(function (month) {
        const perSeries = selected.map(function (key) { return monthlyRate(month, key); });
        return {label: Statso.core.formatMonthHe(month), changed: perSeries.some(function (r) { return r.changed; }),
          values: perSeries.map(function (r) { return r.rate; })};
      }).filter(function (row) { return row.values.some(function (v) { return v !== null; }); });
      if (!rows.length) { fail('אין נתוני ריבית בטווח שנבחר.'); return; }
    }
    el('trh-error').textContent = '';
    render(mode);
  }

  function name(key) { return seriesByKey(key).label; }

  function render(mode) {
    el('trh-head').innerHTML = '<th scope="col">' + t(mode === 'points' ? 'תאריך שינוי' : 'חודש') + '</th>'
      + selected.map(function (key) { return '<th scope="col">' + t(name(key)) + '</th>'; }).join('');
    el('trh-body').innerHTML = rows.map(function (row) {
      return '<tr><th scope="row" dir="ltr">' + row.label + (row.changed ? ' <abbr title="' + t(CHANGED_MONTH_TITLE) + '">*</abbr>' : '') + '</th>'
        + row.values.map(function (value) {
          return '<td dir="ltr">' + (value === null ? '—' : Statso.core.formatPercent(value)) + '</td>';
        }).join('') + '</tr>';
    }).join('');
    const base = rows.length + ' ' + t(mode === 'points' ? 'שינויים בטווח שנבחר.' : 'חודשים בטווח שנבחר.');
    const primeNote = selected.indexOf('prime') !== -1 ? ' ' + t(PRIME_NOTE) : '';
    const monthlyNote = mode === 'monthly' ? ' ' + t(MONTHLY_NOTE) : '';
    el('trh-note').textContent = base + primeNote + monthlyNote;
  }

  const CHANGED_MONTH_TITLE = 'חודש שבו בוצע שינוי ריבית בפועל — הריבית המוצגת היא ממוצע משוקלל של הריבית שחלה בכל אחד מימי החודש.';
  const MONTHLY_NOTE = 'חודש המסומן ב-* הוא חודש שבו בוצע שינוי ריבית בפועל, והריבית המוצגת בו היא ממוצע משוקלל לפי מספר הימים שבהם חלה כל ריבית באותו חודש.';
  const PRIME_NOTE = 'ריבית הפריים מחושבת כריבית בנק ישראל בתוספת 1.5 נקודות אחוז.';

  // ---------- export ----------------------------------------------------------
  function head(mode) {
    return [t(mode === 'points' ? 'תאריך שינוי' : 'חודש')].concat(selected.map(function (key) { return t(name(key)); }));
  }

  function matrix() {
    return rows.map(function (row) {
      return [row.label + (row.changed ? ' *' : '')].concat(row.values.map(function (value) {
        return value === null ? '' : Number(value.toFixed(4));
      }));
    });
  }

  function subtitle() {
    return Statso.core.formatIsoDateHe(el('trh-from').value) + '–' + Statso.core.formatIsoDateHe(el('trh-to').value);
  }

  function exportNotes(mode) {
    const notes = [];
    if (selected.indexOf('prime') !== -1) { notes.push(t(PRIME_NOTE)); }
    if (mode === 'monthly') { notes.push(t(MONTHLY_NOTE)); }
    return notes;
  }

  function exportRateHistory(kind) {
    if (!rows.length) { return; }
    const mode = el('trh-mode').value;
    const notes = exportNotes(mode);
    const columns = [{width: 16}].concat(selected.map(function () { return {width: 15}; }));
    if (kind === 'xlsx') {
      const sheet = {name: 'ריבית היסטורית', columns: columns,
        merges: ['A1:' + Statso.xlsx.columnName(selected.length) + '1'],
        rows: [[{v: t('ריבית היסטורית') + ' — ' + subtitle(), s: S().title}], [],
          head(mode).map(function (text) { return {v: text, s: S().header}; })]};
      matrix().forEach(function (row) {
        sheet.rows.push([{v: row[0], s: S().boxed}]
          .concat(row.slice(1).map(function (value) { return value === '' ? '' : {v: value, s: S().money}; })));
      });
      if (notes.length) {
        sheet.rows.push([]);
        notes.forEach(function (note) { sheet.rows.push([{v: note, s: S().muted}]); });
      }
      Statso.exporter.downloadWorkbook('statso-' + t('ריבית היסטורית') + '-' + Statso.exporter.stamp() + '.xlsx', [sheet]);
      return;
    }
    const blocks = [Statso.exporter.tableHtml(head(mode), matrix())];
    notes.forEach(function (note) { blocks.push('<p class="print-note">' + Statso.xlsx.escapeXml(note) + '</p>'); });
    Statso.exporter.printDocument(t('ריבית היסטורית') + ' — ' + subtitle(),
      Statso.exporter.documentHtml('ריבית היסטורית', subtitle(), blocks));
  }

  function copyRateHistory() {
    if (!rows.length) { return; }
    const button = el('trh-copy');
    const mode = el('trh-mode').value;
    Statso.exporter.copyText(Statso.exporter.toTsv([head(mode)].concat(matrix())))
      .then(function () { Statso.exporter.flash(button, t('הועתק ✓')); })
      .catch(function () { Statso.exporter.flash(button, t('ההעתקה נכשלה')); });
  }

  // ---------- wiring ------------------------------------------------------------
  function init(boiDoc) {
    doc = boiDoc;
    el('trh-from').min = doc.first_change_date; el('trh-from').max = doc.last_change_date;
    el('trh-to').min = doc.first_change_date; el('trh-to').max = doc.last_change_date;
    el('trh-to').value = doc.last_change_date;
    const startYear = Number(doc.last_change_date.slice(0, 4)) - 2;
    el('trh-from').value = startYear + doc.last_change_date.slice(4);
    SERIES.forEach(function (s) { on('trh-' + s.key, 'change', build); });
    ['trh-from', 'trh-to', 'trh-mode'].forEach(function (id) { on(id, 'change', build); });
    on('trh-copy', 'click', copyRateHistory);
    on('trh-xlsx', 'click', function () { exportRateHistory('xlsx'); });
    on('trh-pdf', 'click', function () { exportRateHistory('pdf'); });
    if (Statso.i18n) { Statso.i18n.onChange(function () { if (rows.length) { render(el('trh-mode').value); } }); }
    build();
  }

  Statso.ratehistory = {init: init, build: build, rateAt: rateAt, monthlyRate: monthlyRate,
    matrix: matrix, head: head, PRIME_NOTE: PRIME_NOTE, MONTHLY_NOTE: MONTHLY_NOTE,
    state: function () { return {rows: rows, selected: selected}; }};
})(window);
