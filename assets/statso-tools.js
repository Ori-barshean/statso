(function (root) {
  'use strict';
  const Statso = root.Statso = root.Statso || {};
  const S = function () { return Statso.xlsx.STYLE; };
  let cpi = null, indexMap = null, firstMonth = null, lastMonth = null;
  let fxSummary = null, fxDaily = null, fxPending = false;

  function el(id) { return document.getElementById(id); }
  function say(text) { return Statso.i18n ? Statso.i18n.t(text) : text; }
  function on(id, event, handler) { const node = el(id); if (node) { node.addEventListener(event, handler); } }
  function options(from, to, pad) {
    let out = '';
    for (let n = from; n <= to; n += 1) { const v = pad ? String(n).padStart(2, '0') : String(n); out += '<option value="' + v + '">' + v + '</option>'; }
    return out;
  }
  function fillMonthSelects(ids, first, last) {
    const fy = Number(first.slice(0, 4)); const ly = Number(last.slice(0, 4));
    const years = options(fy, ly, false); const months = options(1, 12, true);
    ids.forEach(function (pair) { el(pair.year).innerHTML = years; el(pair.month).innerHTML = months; });
  }

  // ---------- tool 1: index linkage ----------------------------------------
  let indexResult = null;

  // The chained series is expressed in the 9/1951 base, so its raw numbers run to
  // millions. Ratios come from it, but anything shown to a person is the index as
  // the CBS published it that month.
  function published(month) {
    const row = indexMap ? indexMap.get(month) : null;
    return row ? row.value : null;
  }

  function indexInputs() {
    return {amount: Number(el('ti-amount').value),
      baseMonth: el('ti-base-year').value + '-' + el('ti-base-month').value,
      targetMonth: el('ti-target-year').value + '-' + el('ti-target-month').value,
      mode: document.querySelector('input[name="ti-mode"]:checked').value};
  }

  function indexFail(message) {
    indexResult = null;
    el('ti-error').textContent = message;
    el('ti-result').hidden = true;
  }

  function computeIndex() {
    if (!indexMap) { return; }
    const input = indexInputs();
    if (!Number.isFinite(input.amount) || input.amount < 0) { indexFail('יש להזין סכום תקין שאינו שלילי.'); return; }
    const baseMonth = Statso.core.resolveIndexMonth(input.baseMonth, input.mode);
    const targetMonth = Statso.core.resolveIndexMonth(input.targetMonth, input.mode);
    const base = Statso.core.lookupChained(indexMap, baseMonth, firstMonth, lastMonth);
    const target = Statso.core.lookupChained(indexMap, targetMonth, firstMonth, lastMonth);
    const missing = !base.ok ? baseMonth : (!target.ok ? targetMonth : null);
    if (missing) {
      indexFail('המדד לחודש ' + Statso.core.formatMonthHe(missing) + ' אינו זמין. הטווח הוא '
        + Statso.core.formatMonthHe(firstMonth) + '–' + Statso.core.formatMonthHe(lastMonth) + '.');
      return;
    }
    const outcome = Statso.core.indexAmount(input.amount, base.value, target.value);
    indexResult = {input: input, baseMonth: baseMonth, targetMonth: targetMonth,
      baseValue: base.value, targetValue: target.value,
      indexed: outcome.indexed, difference: outcome.difference,
      ratio: target.value / base.value};
    el('ti-error').textContent = '';
    el('ti-result').hidden = false;
    el('ti-indexed').textContent = Statso.core.formatNumber(outcome.indexed, 2);
    el('ti-difference').textContent = Statso.core.formatNumber(outcome.difference, 2);
    el('ti-detail').textContent = 'מדד ' + Statso.core.formatMonthHe(baseMonth) + ' = '
      + Statso.core.formatNumber(published(baseMonth), 1) + ' · מדד ' + Statso.core.formatMonthHe(targetMonth)
      + ' = ' + Statso.core.formatNumber(Statso.core.readingInBase(indexMap, baseMonth, targetMonth), 1)
      + ' (באותו בסיס) · מקדם '
      + Statso.core.formatNumber(target.value / base.value, 4);
  }

  function indexRows() {
    const r = indexResult;
    const modeText = r.input.mode === 'known' ? 'מדד ידוע' : 'מדד בגין';
    return [['סוג המדד', 'מדד המחירים לצרכן'], ['בסיס החישוב', modeText],
      ['סכום מקורי (₪)', r.input.amount],
      ['חודש בסיס', Statso.core.formatMonthHe(r.input.baseMonth)],
      ['מדד הבסיס בפועל', Statso.core.formatMonthHe(r.baseMonth)],
      ['ערך מדד הבסיס', published(r.baseMonth)],
      ['חודש יעד', Statso.core.formatMonthHe(r.input.targetMonth)],
      ['מדד היעד בפועל', Statso.core.formatMonthHe(r.targetMonth)],
      ['ערך מדד היעד (בבסיס מדד הבסיס)', Statso.core.readingInBase(indexMap, r.baseMonth, r.targetMonth)],
      ['מקדם הצמדה', r.ratio],
      ['סכום מוצמד (₪)', r.indexed],
      ['הפרש (₪)', r.difference]];
  }

  function exportIndex(kind) {
    if (!indexResult) { return; }
    const rows = indexRows();
    if (kind === 'xlsx') {
      const sheet = {name: 'הצמדה למדד', columns: [{width: 26}, {width: 20}],
        merges: ['A1:B1'], rows: [[{v: 'הצמדה למדד המחירים לצרכן', s: S().title}], []]};
      rows.forEach(function (row) {
        sheet.rows.push([{v: row[0], s: S().header},
          typeof row[1] === 'number' ? {v: row[1], s: S().money} : {v: row[1], s: S().boxed}]);
      });
      Statso.exporter.downloadWorkbook('statso-' + Statso.i18n.t('הצמדה למדד') + '-' + Statso.exporter.stamp() + '.xlsx', [sheet]);
      return;
    }
    Statso.exporter.printDocument('הצמדה למדד המחירים לצרכן',
      Statso.exporter.documentHtml('הצמדה למדד המחירים לצרכן',
        Statso.core.formatMonthHe(indexResult.input.baseMonth) + ' → ' + Statso.core.formatMonthHe(indexResult.input.targetMonth),
        [Statso.exporter.tableHtml(['פריט', 'ערך'], rows)]));
  }

  // ---------- tool 2: currency ---------------------------------------------
  let fxResult = null;

  function fxKind() { return document.querySelector('input[name="tf-kind"]:checked').value; }

  function fxFail(message) {
    fxResult = null;
    el('tf-error').textContent = message;
    el('tf-result').hidden = true;
  }

  function quote(code, isoDate) {
    if (code === 'ILS') { return {ok: true, rate: 1, unit: 1, date: null}; }
    const entry = fxDaily.currencies[code];
    if (!entry) { return {ok: false, code: code, first: null}; }
    const found = Statso.core.lookupRateAt(entry.dates, entry.rates, isoDate);
    if (!found.ok) { return {ok: false, code: code, first: entry.dates[0]}; }
    return {ok: true, rate: found.rate, unit: entry.unit, date: found.date};
  }

  function quoteFail(quoted) {
    const name = Statso.core.CURRENCY_NAMES[quoted.code] || quoted.code;
    fxFail(quoted.first ? 'אין שער ל' + name + ' לפני ' + Statso.core.formatIsoDateHe(quoted.first) + '.'
      : 'אין נתוני שער עבור ' + name + '.');
  }

  function computeFx() {
    if (!fxSummary) { return; }
    const amount = Number(el('tf-amount').value);
    if (!Number.isFinite(amount) || amount < 0) { fxFail('יש להזין סכום תקין שאינו שלילי.'); return; }
    if (!fxDaily) { fxFail(fxPending ? 'טוען שערי חליפין…' : 'שערי החליפין אינם זמינים.'); return; }
    const link = fxKind() === 'link';
    const date = el('tf-date').value;
    if (!date) { fxFail('יש לבחור תאריך.'); return; }
    if (link) {
      const code = el('tf-currency').value;
      const targetDate = el('tf-date-target').value;
      if (!targetDate) { fxFail('יש לבחור תאריך יעד.'); return; }
      const base = quote(code, date); if (!base.ok) { quoteFail(base); return; }
      const target = quote(code, targetDate); if (!target.ok) { quoteFail(target); return; }
      const linked = amount * (target.rate / base.rate);
      fxResult = {kind: 'link', amount: amount, code: code, baseDate: base.date, targetDate: target.date,
        baseRate: base.rate, targetRate: target.rate, value: linked, difference: linked - amount,
        ratio: target.rate / base.rate, unit: '₪'};
      el('tf-result-label').textContent = 'סכום מוצמד';
      el('tf-unit').textContent = '₪';
      el('tf-value').textContent = Statso.core.formatNumber(linked, 2);
      el('tf-detail').textContent = 'שער ' + code + ' ב־' + Statso.core.formatIsoDateHe(base.date) + ' = '
        + Statso.core.formatRate(base.rate) + ' · ב־' + Statso.core.formatIsoDateHe(target.date) + ' = '
        + Statso.core.formatRate(target.rate) + ' · הפרש ' + Statso.core.formatNumber(linked - amount, 2) + ' ₪';
    } else {
      const from = quote(el('tf-from').value, date); if (!from.ok) { quoteFail(from); return; }
      const to = quote(el('tf-to').value, date); if (!to.ok) { quoteFail(to); return; }
      const outcome = Statso.core.convertAmount(amount, from, to);
      const used = [from.date, to.date].filter(Boolean).sort();
      fxResult = {kind: 'convert', amount: amount, from: el('tf-from').value, to: el('tf-to').value,
        date: used.length ? used[used.length - 1] : date, rate: outcome.rate, value: outcome.amount,
        unit: el('tf-to').value === 'ILS' ? '₪' : el('tf-to').value};
      el('tf-result-label').textContent = 'סכום ממומר';
      el('tf-unit').textContent = fxResult.unit;
      el('tf-value').textContent = Statso.core.formatNumber(outcome.amount, 2);
      el('tf-detail').textContent = 'שער ' + Statso.core.formatRate(outcome.rate)
        + (used.length ? ' · לפי השער שפורסם ל־' + Statso.core.formatIsoDateHe(used[used.length - 1]) : '');
    }
    el('tf-error').textContent = '';
    el('tf-result').hidden = false;
  }

  function fxRows() {
    const r = fxResult;
    if (r.kind === 'link') {
      return [['מטבע ההצמדה', (Statso.core.CURRENCY_NAMES[r.code] || r.code) + ' (' + r.code + ')'],
        ['סכום מקורי (₪)', r.amount],
        ['תאריך בסיס', Statso.core.formatIsoDateHe(r.baseDate)], ['שער בסיס', r.baseRate],
        ['תאריך יעד', Statso.core.formatIsoDateHe(r.targetDate)], ['שער יעד', r.targetRate],
        ['מקדם הצמדה', r.ratio], ['סכום מוצמד (₪)', r.value], ['הפרש (₪)', r.difference]];
    }
    return [['ממטבע', (Statso.core.CURRENCY_NAMES[r.from] || r.from) + ' (' + r.from + ')'],
      ['למטבע', (Statso.core.CURRENCY_NAMES[r.to] || r.to) + ' (' + r.to + ')'],
      ['סכום מקורי', r.amount], ['תאריך השער', Statso.core.formatIsoDateHe(r.date)],
      ['שער', r.rate], ['סכום ממומר (' + r.unit + ')', r.value]];
  }

  function exportFx(kind) {
    if (!fxResult) { return; }
    const rows = fxRows();
    const title = fxResult.kind === 'link' ? 'הצמדה למטבע' : 'המרת מטבע';
    if (kind === 'xlsx') {
      const sheet = {name: title, columns: [{width: 26}, {width: 22}], merges: ['A1:B1'],
        rows: [[{v: say(title) + ' — ' + say('שערים יציגים של בנק ישראל'), s: S().title}], []]};
      rows.forEach(function (row) {
        sheet.rows.push([{v: row[0], s: S().header},
          typeof row[1] === 'number' ? {v: row[1], s: S().money} : {v: row[1], s: S().boxed}]);
      });
      Statso.exporter.downloadWorkbook('statso-' + Statso.i18n.t(title) + '-' + Statso.exporter.stamp() + '.xlsx', [sheet]);
      return;
    }
    Statso.exporter.printDocument(title,
      Statso.exporter.documentHtml(title, 'שערים יציגים של בנק ישראל',
        [Statso.exporter.tableHtml(['פריט', 'ערך'], rows)]));
  }

  function showFxKind() {
    const link = fxKind() === 'link';
    document.querySelectorAll('.tf-convert-only').forEach(function (node) { node.hidden = link; });
    document.querySelectorAll('.tf-link-only').forEach(function (node) { node.hidden = !link; });
    el('tf-date-label').firstChild.textContent = link ? 'תאריך בסיס ' : 'תאריך השער ';
    ensureFx();
    computeFx();
  }

  function ensureFx() {
    if (fxDaily || fxPending) { return; }
    fxPending = true;
    Statso.data.loadFxDaily().then(function (doc) {
      fxDaily = doc; fxPending = false; computeFx();
    }).catch(function () { fxPending = false; fxFail('לא ניתן לטעון את שערי החליפין.'); });
  }

  // ---------- tool 3: historical table -------------------------------------
  let historyRows = [];

  function historyRange() {
    return {from: el('th-start-year').value + '-' + el('th-start-month').value,
      to: el('th-end-year').value + '-' + el('th-end-month').value};
  }

  function buildHistory() {
    if (!cpi) { return; }
    const range = historyRange();
    if (Statso.core.monthToOrdinal(range.from) > Statso.core.monthToOrdinal(range.to)) {
      el('th-error').textContent = 'חודש ההתחלה חייב להיות מוקדם מחודש הסיום.';
      el('th-body').innerHTML = ''; historyRows = []; return;
    }
    el('th-error').textContent = '';
    historyRows = cpi.observations.filter(function (row) {
      return Statso.core.monthToOrdinal(row.month) >= Statso.core.monthToOrdinal(range.from)
        && Statso.core.monthToOrdinal(row.month) <= Statso.core.monthToOrdinal(range.to);
    }).map(function (row) {
      const mom = Statso.core.monthOverMonth(indexMap, row.month);
      const yoy = Statso.core.yearOverYear(indexMap, row.month);
      return {month: row.month, chained: row.chained_1951_09, value: row.value,
        mom: mom.ok ? mom.percent : null, yoy: yoy.ok ? yoy.percent : null};
    });
    el('th-body').innerHTML = historyRows.map(function (row) {
      return '<tr><th scope="row" dir="ltr">' + Statso.core.escapeHtml(Statso.core.formatMonthHe(row.month)) + '</th>'
        + '<td dir="ltr">' + Statso.core.formatNumber(row.chained, 2) + '</td>'
        + '<td dir="ltr">' + Statso.core.formatNumber(row.value, 1) + '</td>'
        + '<td dir="ltr">' + (row.mom === null ? '—' : Statso.core.formatPercent(row.mom)) + '</td>'
        + '<td dir="ltr">' + (row.yoy === null ? '—' : Statso.core.formatPercent(row.yoy)) + '</td></tr>';
    }).join('');
    el('th-note').textContent = historyRows.length + ' חודשים בטווח שנבחר. המדד המשורשר מבוטא בבסיס 9/1951, '
      + 'והמדד המקורי הוא הערך כפי שפורסם בבסיס התקף באותו חודש.';
  }

  const HISTORY_HEAD = ['חודש', 'מדד משורשר', 'מדד מקורי', 'שינוי חודשי %', 'שינוי שנתי %'];

  function historyMatrix() {
    return historyRows.map(function (row) {
      return [Statso.core.formatMonthHe(row.month), Number(row.chained.toFixed(2)), row.value,
        row.mom === null ? '' : Number(row.mom.toFixed(2)), row.yoy === null ? '' : Number(row.yoy.toFixed(2))];
    });
  }

  function exportHistory(kind) {
    if (!historyRows.length) { return; }
    const range = historyRange();
    const subtitle = Statso.core.formatMonthHe(range.from) + '–' + Statso.core.formatMonthHe(range.to);
    if (kind === 'xlsx') {
      const sheet = {name: 'מדד היסטורי',
        columns: [{width: 12}, {width: 15}, {width: 14}, {width: 15}, {width: 15}],
        merges: ['A1:E1'],
        rows: [[{v: say('מדד המחירים לצרכן') + ' — ' + subtitle, s: S().title}], [],
          HISTORY_HEAD.map(function (text) { return {v: text, s: S().header}; })]};
      historyMatrix().forEach(function (row) {
        sheet.rows.push([{v: row[0], s: S().boxed}, {v: row[1], s: S().money}, {v: row[2], s: S().money},
          row[3] === '' ? '' : {v: row[3], s: S().money}, row[4] === '' ? '' : {v: row[4], s: S().money}]);
      });
      Statso.exporter.downloadWorkbook('statso-' + Statso.i18n.t('מדד היסטורי') + '-' + Statso.exporter.stamp() + '.xlsx', [sheet]);
      return;
    }
    Statso.exporter.printDocument('מדד המחירים לצרכן — ' + subtitle,
      Statso.exporter.documentHtml('מדד המחירים לצרכן', subtitle,
        [Statso.exporter.tableHtml(HISTORY_HEAD, historyMatrix())]));
  }

  function copyHistory() {
    if (!historyRows.length) { return; }
    const button = el('th-copy');
    Statso.exporter.copyText(Statso.exporter.toTsv([HISTORY_HEAD].concat(historyMatrix())))
      .then(function () { Statso.exporter.flash(button, 'הועתק ✓'); })
      .catch(function () { Statso.exporter.flash(button, 'ההעתקה נכשלה'); });
  }

  // ---------- wiring --------------------------------------------------------
  function init(cpiDoc, map) {
    cpi = cpiDoc; indexMap = map; firstMonth = cpiDoc.first_month; lastMonth = cpiDoc.last_month;
    fillMonthSelects([{year: 'ti-base-year', month: 'ti-base-month'},
      {year: 'ti-target-year', month: 'ti-target-month'},
      {year: 'th-start-year', month: 'th-start-month'},
      {year: 'th-end-year', month: 'th-end-month'}], firstMonth, lastMonth);
    const lastYear = lastMonth.slice(0, 4); const lastMonthPart = lastMonth.slice(5);
    el('ti-base-year').value = String(Number(lastYear) - 1); el('ti-base-month').value = lastMonthPart;
    el('ti-target-year').value = lastYear; el('ti-target-month').value = lastMonthPart;
    el('th-start-year').value = String(Number(lastYear) - 2); el('th-start-month').value = '01';
    el('th-end-year').value = lastYear; el('th-end-month').value = lastMonthPart;
    ['ti-amount', 'ti-base-year', 'ti-base-month', 'ti-target-year', 'ti-target-month'].forEach(function (id) {
      on(id, 'input', computeIndex);
    });
    document.querySelectorAll('input[name="ti-mode"]').forEach(function (radio) { radio.addEventListener('change', computeIndex); });
    on('ti-xlsx', 'click', function () { exportIndex('xlsx'); });
    on('ti-pdf', 'click', function () { exportIndex('pdf'); });
    ['th-start-year', 'th-start-month', 'th-end-year', 'th-end-month'].forEach(function (id) {
      on(id, 'change', buildHistory);
    });
    on('th-copy', 'click', copyHistory);
    on('th-xlsx', 'click', function () { exportHistory('xlsx'); });
    on('th-pdf', 'click', function () { exportHistory('pdf'); });
    computeIndex();
    buildHistory();
    if (Statso.rent) { Statso.rent.init(cpiDoc, map); }
  }

  function initFx(summary) {
    fxSummary = summary;
    const rows = summary.rates || [];
    const codes = ['ILS'].concat(rows.map(function (row) { return row.code; }));
    const html = codes.map(function (code) {
      return '<option value="' + Statso.core.escapeHtml(code) + '">' + Statso.core.escapeHtml(Statso.core.CURRENCY_NAMES[code] || code) + ' (' + Statso.core.escapeHtml(code) + ')</option>';
    }).join('');
    el('tf-from').innerHTML = html; el('tf-to').innerHTML = html;
    el('tf-from').value = 'ILS'; el('tf-to').value = 'USD';
    el('tf-currency').innerHTML = rows.map(function (row) {
      return '<option value="' + Statso.core.escapeHtml(row.code) + '">' + Statso.core.escapeHtml(Statso.core.CURRENCY_NAMES[row.code] || row.code) + ' (' + Statso.core.escapeHtml(row.code) + ')</option>';
    }).join('');
    el('tf-currency').value = 'USD';
    const latest = rows.map(function (row) { return row.latest.date; }).sort();
    const starts = rows.map(function (row) { return row.first_date; }).sort();
    const newest = latest[latest.length - 1];
    ['tf-date', 'tf-date-target'].forEach(function (id) {
      el(id).min = starts[0]; el(id).max = newest;
    });
    el('tf-date').value = newest; el('tf-date-target').value = newest;
    ['tf-amount', 'tf-from', 'tf-to', 'tf-currency', 'tf-date', 'tf-date-target'].forEach(function (id) {
      on(id, 'input', computeFx);
    });
    document.querySelectorAll('input[name="tf-kind"]').forEach(function (radio) {
      radio.addEventListener('change', showFxKind);
    });
    on('tf-xlsx', 'click', function () { exportFx('xlsx'); });
    on('tf-pdf', 'click', function () { exportFx('pdf'); });
    showFxKind();
    if (Statso.fxhistory) { Statso.fxhistory.init(summary); }
  }

  Statso.tools = {init: init, initFx: initFx, computeIndex: computeIndex, computeFx: computeFx,
    buildHistory: buildHistory, historyMatrix: historyMatrix, exportIndex: exportIndex,
    exportFx: exportFx, exportHistory: exportHistory, HISTORY_HEAD: HISTORY_HEAD};
})(window);
