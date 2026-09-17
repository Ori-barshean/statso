(function (root) {
  'use strict';
  const Statso = root.Statso = root.Statso || {};
  const S = function () { return Statso.xlsx.STYLE; };
  let cpi = null, indexMap = null, firstMonth = null, lastMonth = null;
  let construction = null, constructionMap = null;
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
  function clampMonth(month, first, last) {
    if (Statso.core.monthToOrdinal(month) < Statso.core.monthToOrdinal(first)) { return first; }
    if (Statso.core.monthToOrdinal(month) > Statso.core.monthToOrdinal(last)) { return last; }
    return month;
  }

  // ---------- tool 1: index linkage ----------------------------------------
  let indexResult = null;

  const INDEX_SERIES = {
    cpi: {key: 'cpi', label: 'מדד המחירים לצרכן', title: 'הצמדה למדד המחירים לצרכן', field: 'chained_1951_09',
      doc: function () { return cpi; }, map: function () { return indexMap; }},
    construction: {key: 'construction', label: 'מדד תשומות הבנייה למגורים', title: 'הצמדה למדד תשומות הבנייה למגורים',
      field: 'chained_1950_07', doc: function () { return construction; }, map: function () { return constructionMap; }}
  };

  function currentIndexSeries() {
    const node = document.querySelector('input[name="ti-series"]:checked');
    const series = INDEX_SERIES[node ? node.value : 'cpi'] || INDEX_SERIES.cpi;
    return series.doc() ? series : INDEX_SERIES.cpi;
  }

  // The chained series is expressed in the series' own base, so its raw numbers can
  // run to millions. Ratios come from it, but anything shown to a person is the
  // index as the CBS published it that month.
  function published(map, month) {
    const row = map ? map.get(month) : null;
    return row ? row.value : null;
  }

  function indexInputs() {
    return {amount: Number(el('ti-amount').value),
      baseMonth: el('ti-base-year').value + '-' + el('ti-base-month').value,
      targetMonth: el('ti-target-year').value + '-' + el('ti-target-month').value,
      mode: document.querySelector('input[name="ti-mode"]:checked').value,
      series: currentIndexSeries()};
  }

  function indexFail(message) {
    indexResult = null;
    el('ti-error').textContent = message;
    el('ti-result').hidden = true;
  }

  function computeIndex() {
    if (!cpi) { return; }
    const input = indexInputs();
    const series = input.series;
    const doc = series.doc(); const map = series.map();
    if (!doc || !map) { return; }
    if (!Number.isFinite(input.amount) || input.amount < 0) { indexFail('יש להזין סכום תקין שאינו שלילי.'); return; }
    const baseMonth = Statso.core.resolveIndexMonth(input.baseMonth, input.mode);
    const targetMonth = Statso.core.resolveIndexMonth(input.targetMonth, input.mode);
    const base = Statso.core.lookupChained(map, baseMonth, doc.first_month, doc.last_month, series.field);
    const target = Statso.core.lookupChained(map, targetMonth, doc.first_month, doc.last_month, series.field);
    const missing = !base.ok ? baseMonth : (!target.ok ? targetMonth : null);
    if (missing) {
      indexFail('המדד לחודש ' + Statso.core.formatMonthHe(missing) + ' אינו זמין. הטווח הוא '
        + Statso.core.formatMonthHe(doc.first_month) + '–' + Statso.core.formatMonthHe(doc.last_month) + '.');
      return;
    }
    const outcome = Statso.core.indexAmount(input.amount, base.value, target.value);
    indexResult = {input: input, series: series, baseMonth: baseMonth, targetMonth: targetMonth,
      baseValue: base.value, targetValue: target.value,
      indexed: outcome.indexed, difference: outcome.difference,
      ratio: target.value / base.value};
    el('ti-error').textContent = '';
    el('ti-result').hidden = false;
    el('ti-indexed').textContent = Statso.core.formatNumber(outcome.indexed, 2);
    el('ti-difference').textContent = Statso.core.formatNumber(outcome.difference, 2);
    el('ti-detail').textContent = series.label + ' · מדד ' + Statso.core.formatMonthHe(baseMonth) + ' = '
      + Statso.core.formatNumber(published(map, baseMonth), 1) + ' · מדד ' + Statso.core.formatMonthHe(targetMonth)
      + ' = ' + Statso.core.formatNumber(Statso.core.readingInBase(map, baseMonth, targetMonth, series.field), 1)
      + ' (באותו בסיס) · מקדם '
      + Statso.core.formatNumber(target.value / base.value, 4);
  }

  function indexRows() {
    const r = indexResult;
    const modeText = r.input.mode === 'known' ? 'מדד ידוע' : 'מדד בגין';
    return [['סוג המדד', r.series.label], ['בסיס החישוב', modeText],
      ['סכום מקורי (₪)', r.input.amount],
      ['חודש בסיס', Statso.core.formatMonthHe(r.input.baseMonth)],
      ['מדד הבסיס בפועל', Statso.core.formatMonthHe(r.baseMonth)],
      ['ערך מדד הבסיס', published(r.series.map(), r.baseMonth)],
      ['חודש יעד', Statso.core.formatMonthHe(r.input.targetMonth)],
      ['מדד היעד בפועל', Statso.core.formatMonthHe(r.targetMonth)],
      ['ערך מדד היעד (בבסיס מדד הבסיס)', Statso.core.readingInBase(r.series.map(), r.baseMonth, r.targetMonth, r.series.field)],
      ['מקדם הצמדה', r.ratio],
      ['סכום מוצמד (₪)', r.indexed],
      ['הפרש (₪)', r.difference]];
  }

  function exportIndex(kind) {
    if (!indexResult) { return; }
    const rows = indexRows();
    const title = indexResult.series.title;
    if (kind === 'xlsx') {
      const sheet = {name: 'הצמדה למדד', columns: [{width: 26}, {width: 20}],
        merges: ['A1:B1'], rows: [[{v: say(title), s: S().title}], []]};
      rows.forEach(function (row) {
        sheet.rows.push([{v: row[0], s: S().header},
          typeof row[1] === 'number' ? {v: row[1], s: S().money} : {v: row[1], s: S().boxed}]);
      });
      Statso.exporter.downloadWorkbook('statso-' + Statso.i18n.t(title) + '-' + Statso.exporter.stamp() + '.xlsx', [sheet]);
      return;
    }
    Statso.exporter.printDocument(title,
      Statso.exporter.documentHtml(title,
        Statso.core.formatMonthHe(indexResult.input.baseMonth) + ' → ' + Statso.core.formatMonthHe(indexResult.input.targetMonth),
        [Statso.exporter.tableHtml(['פריט', 'ערך'], rows)]));
  }

  function switchIndexSeries() {
    const series = currentIndexSeries();
    const doc = series.doc();
    if (!doc) { return; }
    const capture = function (yearId, monthId) { return el(yearId).value + '-' + el(monthId).value; };
    const currentBase = capture('ti-base-year', 'ti-base-month');
    const currentTarget = capture('ti-target-year', 'ti-target-month');
    fillMonthSelects([{year: 'ti-base-year', month: 'ti-base-month'},
      {year: 'ti-target-year', month: 'ti-target-month'}], doc.first_month, doc.last_month);
    const apply = function (yearId, monthId, month) {
      const clamped = clampMonth(month, doc.first_month, doc.last_month);
      el(yearId).value = clamped.slice(0, 4); el(monthId).value = clamped.slice(5);
    };
    apply('ti-base-year', 'ti-base-month', currentBase);
    apply('ti-target-year', 'ti-target-month', currentTarget);
    computeIndex();
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

  const HISTORY_SERIES = [
    {key: 'cpi', label: 'מדד המחירים לצרכן', field: 'chained_1951_09',
      baseNote: 'המדד המשורשר של מדד המחירים לצרכן מבוטא בבסיס 9/1951.',
      doc: function () { return cpi; }, map: function () { return indexMap; }},
    {key: 'construction', label: 'מדד תשומות הבנייה למגורים', field: 'chained_1950_07',
      baseNote: 'המדד המשורשר של מדד תשומות הבנייה למגורים מבוטא בבסיס 7/1950, והסדרה המפורסמת מתחילה ב-1/2000.',
      doc: function () { return construction; }, map: function () { return constructionMap; }}
  ];

  const HISTORY_METRICS = [
    {key: 'chained', label: 'מדד משורשר', decimals: 2, format: function (v) { return Statso.core.formatNumber(v, 2); }},
    {key: 'value', label: 'מדד מקורי', decimals: null, format: function (v) { return Statso.core.formatNumber(v, 1); }},
    {key: 'mom', label: 'שינוי חודשי %', decimals: 2, format: function (v) { return Statso.core.formatPercent(v); }},
    {key: 'yoy', label: 'שינוי שנתי %', decimals: 2, format: function (v) { return Statso.core.formatPercent(v); }}
  ];

  function selectedHistorySeries() {
    return HISTORY_SERIES.filter(function (s) { return s.doc() && el('th-' + s.key).checked; });
  }

  function historyRange() {
    return {from: el('th-start-year').value + '-' + el('th-start-month').value,
      to: el('th-end-year').value + '-' + el('th-end-month').value};
  }

  function monthSpine(from, to) {
    const months = [];
    let cursor = from;
    while (Statso.core.monthToOrdinal(cursor) <= Statso.core.monthToOrdinal(to)) {
      months.push(cursor);
      cursor = Statso.core.shiftMonth(cursor, 1);
    }
    return months;
  }

  function buildHistory() {
    if (!cpi) { return; }
    const range = historyRange();
    if (Statso.core.monthToOrdinal(range.from) > Statso.core.monthToOrdinal(range.to)) {
      el('th-error').textContent = 'חודש ההתחלה חייב להיות מוקדם מחודש הסיום.';
      el('th-head').innerHTML = ''; el('th-body').innerHTML = ''; el('th-note').textContent = ''; historyRows = []; return;
    }
    const series = selectedHistorySeries();
    if (!series.length) {
      el('th-error').textContent = 'יש לבחור סדרה אחת לפחות.';
      el('th-head').innerHTML = ''; el('th-body').innerHTML = ''; el('th-note').textContent = ''; historyRows = []; return;
    }
    el('th-error').textContent = '';
    historyRows = monthSpine(range.from, range.to).map(function (month) {
      const cells = {};
      series.forEach(function (s) {
        const map = s.map();
        const row = map ? map.get(month) : null;
        const mom = map ? Statso.core.monthOverMonth(map, month, s.field) : {ok: false, percent: null};
        const yoy = map ? Statso.core.yearOverYear(map, month, s.field) : {ok: false, percent: null};
        cells[s.key] = {chained: row ? row[s.field] : null, value: row ? row.value : null,
          mom: mom.ok ? mom.percent : null, yoy: yoy.ok ? yoy.percent : null};
      });
      return {month: month, cells: cells};
    });
    renderHistory();
  }

  function renderHistory() {
    const series = selectedHistorySeries();
    el('th-head').innerHTML = '<th scope="col">' + say('חודש') + '</th>' + series.map(function (s) {
      return HISTORY_METRICS.map(function (m) {
        return '<th scope="col">' + say(m.label) + ' — ' + say(s.label) + '</th>';
      }).join('');
    }).join('');
    el('th-body').innerHTML = historyRows.map(function (row) {
      return '<tr><th scope="row" dir="ltr">' + Statso.core.escapeHtml(Statso.core.formatMonthHe(row.month)) + '</th>'
        + series.map(function (s) {
          const cell = row.cells[s.key];
          return HISTORY_METRICS.map(function (m) {
            const v = cell[m.key];
            return '<td dir="ltr">' + (v === null ? '—' : m.format(v)) + '</td>';
          }).join('');
        }).join('') + '</tr>';
    }).join('');
    const base = historyRows.length + ' ' + say('חודשים בטווח שנבחר.');
    const notes = series.map(function (s) { return say(s.baseNote); }).join(' ');
    el('th-note').textContent = base + (notes ? ' ' + notes : '');
  }

  function historyHead() {
    const series = selectedHistorySeries();
    const head = [say('חודש')];
    series.forEach(function (s) {
      HISTORY_METRICS.forEach(function (m) { head.push(say(m.label) + ' — ' + say(s.label)); });
    });
    return head;
  }

  function historyMatrix() {
    const series = selectedHistorySeries();
    return historyRows.map(function (row) {
      const out = [Statso.core.formatMonthHe(row.month)];
      series.forEach(function (s) {
        const cell = row.cells[s.key];
        HISTORY_METRICS.forEach(function (m) {
          const v = cell[m.key];
          out.push(v === null ? '' : (m.decimals === null ? v : Number(v.toFixed(m.decimals))));
        });
      });
      return out;
    });
  }

  function exportHistory(kind) {
    if (!historyRows.length) { return; }
    const series = selectedHistorySeries();
    if (!series.length) { return; }
    const range = historyRange();
    const subtitle = Statso.core.formatMonthHe(range.from) + '–' + Statso.core.formatMonthHe(range.to);
    const title = series.map(function (s) { return say(s.label); }).join(' / ');
    const head = historyHead();
    if (kind === 'xlsx') {
      const columns = head.map(function (_, i) { return {width: i === 0 ? 12 : 15}; });
      const sheet = {name: 'מדד היסטורי', columns: columns,
        merges: ['A1:' + Statso.xlsx.columnName(head.length - 1) + '1'],
        rows: [[{v: title + ' — ' + subtitle, s: S().title}], [],
          head.map(function (text) { return {v: text, s: S().header}; })]};
      historyMatrix().forEach(function (row) {
        sheet.rows.push([{v: row[0], s: S().boxed}].concat(row.slice(1).map(function (v) {
          return v === '' ? '' : {v: v, s: S().money};
        })));
      });
      Statso.exporter.downloadWorkbook('statso-' + say('מדד היסטורי') + '-' + Statso.exporter.stamp() + '.xlsx', [sheet]);
      return;
    }
    Statso.exporter.printDocument(title + ' — ' + subtitle,
      Statso.exporter.documentHtml(title, subtitle,
        [Statso.exporter.tableHtml(head, historyMatrix())]));
  }

  function copyHistory() {
    if (!historyRows.length) { return; }
    const button = el('th-copy');
    Statso.exporter.copyText(Statso.exporter.toTsv([historyHead()].concat(historyMatrix())))
      .then(function () { Statso.exporter.flash(button, 'הועתק ✓'); })
      .catch(function () { Statso.exporter.flash(button, 'ההעתקה נכשלה'); });
  }

  // ---------- wiring --------------------------------------------------------
  function init(cpiDoc, map, constructionDoc) {
    cpi = cpiDoc; indexMap = map; firstMonth = cpiDoc.first_month; lastMonth = cpiDoc.last_month;
    construction = constructionDoc || null;
    constructionMap = construction ? Statso.core.buildIndexMap(construction.observations) : null;

    fillMonthSelects([{year: 'ti-base-year', month: 'ti-base-month'},
      {year: 'ti-target-year', month: 'ti-target-month'}], firstMonth, lastMonth);
    const lastYear = lastMonth.slice(0, 4); const lastMonthPart = lastMonth.slice(5);
    el('ti-base-year').value = String(Number(lastYear) - 1); el('ti-base-month').value = lastMonthPart;
    el('ti-target-year').value = lastYear; el('ti-target-month').value = lastMonthPart;

    const unionFirst = construction && Statso.core.monthToOrdinal(construction.first_month) < Statso.core.monthToOrdinal(firstMonth)
      ? construction.first_month : firstMonth;
    const unionLast = construction && Statso.core.monthToOrdinal(construction.last_month) > Statso.core.monthToOrdinal(lastMonth)
      ? construction.last_month : lastMonth;
    fillMonthSelects([{year: 'th-start-year', month: 'th-start-month'},
      {year: 'th-end-year', month: 'th-end-month'}], unionFirst, unionLast);
    el('th-start-year').value = String(Number(lastYear) - 2); el('th-start-month').value = '01';
    el('th-end-year').value = lastYear; el('th-end-month').value = lastMonthPart;

    if (!construction) {
      const radio = el('ti-series-construction'); if (radio) { radio.disabled = true; }
      const box = el('th-construction'); if (box) { box.disabled = true; box.checked = false; }
    }

    ['ti-amount', 'ti-base-year', 'ti-base-month', 'ti-target-year', 'ti-target-month'].forEach(function (id) {
      on(id, 'input', computeIndex);
    });
    document.querySelectorAll('input[name="ti-mode"]').forEach(function (radio) { radio.addEventListener('change', computeIndex); });
    document.querySelectorAll('input[name="ti-series"]').forEach(function (radio) { radio.addEventListener('change', switchIndexSeries); });
    on('ti-xlsx', 'click', function () { exportIndex('xlsx'); });
    on('ti-pdf', 'click', function () { exportIndex('pdf'); });

    ['th-start-year', 'th-start-month', 'th-end-year', 'th-end-month'].forEach(function (id) {
      on(id, 'change', buildHistory);
    });
    on('th-cpi', 'change', buildHistory);
    on('th-construction', 'change', buildHistory);
    on('th-copy', 'click', copyHistory);
    on('th-xlsx', 'click', function () { exportHistory('xlsx'); });
    on('th-pdf', 'click', function () { exportHistory('pdf'); });
    if (Statso.i18n) { Statso.i18n.onChange(function () { if (historyRows.length) { renderHistory(); } }); }

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

  function initBoi(boiDoc) {
    if (Statso.ratehistory) { Statso.ratehistory.init(boiDoc); }
  }

  Statso.tools = {init: init, initFx: initFx, initBoi: initBoi, computeIndex: computeIndex, computeFx: computeFx,
    buildHistory: buildHistory, historyMatrix: historyMatrix, historyHead: historyHead, exportIndex: exportIndex,
    exportFx: exportFx, exportHistory: exportHistory};
})(window);
