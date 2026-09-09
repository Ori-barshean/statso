(function (root) {
  'use strict';
  const Statso = root.Statso = root.Statso || {};
  const S = function () { return Statso.xlsx.STYLE; };
  let indexMap = null, firstMonth = null, lastMonth = null;
  let periods = [];
  let overrides = {};   // "periodIndex:month" -> amount actually received
  let paid = {};        // "periodIndex:month" -> true when the difference was settled
  let model = null;
  let rangeTouched = false;   // once the user picks an export range, stop widening it

  function el(id) { return document.getElementById(id); }
  function on(id, event, handler) { const node = el(id); if (node) { node.addEventListener(event, handler); } }
  function monthsBetween(start, end) {
    const out = [];
    for (let n = Statso.core.monthToOrdinal(start); n <= Statso.core.monthToOrdinal(end); n += 1) {
      out.push(Statso.core.ordinalToMonth(n));
    }
    return out;
  }
  function key(periodIndex, month) { return periodIndex + ':' + month; }

  // ---------- reading the form ---------------------------------------------
  function optionRowHtml(index, values) {
    return '<div class="rent-option" data-option="' + index + '">'
      + '<label>מחודש <input type="month" class="tr-opt-start" value="' + (values.start || '') + '"></label>'
      + '<label>עד חודש <input type="month" class="tr-opt-end" value="' + (values.end || '') + '"></label>'
      + '<label>דמי שכירות חודשיים (₪) <input type="number" min="0" step="any" class="tr-opt-rent" value="'
      + (values.rent || '') + '"></label>'
      + '<button type="button" class="btn-ghost tr-opt-remove" aria-label="הסרת תקופה">הסרה</button></div>';
  }

  function readOptions() {
    return Array.prototype.map.call(document.querySelectorAll('#tr-option-rows .rent-option'), function (row) {
      return {start: row.querySelector('.tr-opt-start').value,
        end: row.querySelector('.tr-opt-end').value,
        rent: Number(row.querySelector('.tr-opt-rent').value)};
    });
  }

  function readForm() {
    return {contractDate: el('tr-contract-date').value,
      landlord: el('tr-landlord').value.trim(), tenant: el('tr-tenant').value.trim(),
      baseStart: el('tr-base-start').value, baseEnd: el('tr-base-end').value,
      baseRent: Number(el('tr-base-rent').value),
      hasOptions: el('tr-has-options').checked,
      options: el('tr-has-options').checked ? readOptions() : [],
      customBase: el('tr-custom-base').checked,
      baseIndexMonth: el('tr-base-index-year').value + '-' + el('tr-base-index-month').value,
      floor: document.querySelector('input[name="tr-floor"]:checked').value};
  }

  function fail(message) {
    model = null;
    el('tr-error').textContent = message;
    el('tr-output').hidden = true;
  }

  // ---------- computation ---------------------------------------------------
  // `value` is the chained reading the ratio is built from; `published` is the
  // index as the CBS published it, which is what the contract and the tenant see.
  function indexFor(month, baseIndexMonth) {
    const resolved = Statso.core.resolveIndexMonth(month, 'known');
    const found = Statso.core.lookupChained(indexMap, resolved, firstMonth, lastMonth);
    return {month: resolved, ok: found.ok, value: found.ok ? found.value : null,
      published: found.ok ? Statso.core.readingInBase(indexMap, baseIndexMonth, resolved) : null};
  }

  function compute() {
    if (!indexMap) { return; }
    const form = readForm();
    if (!form.contractDate) { fail('יש לבחור את מועד הסכם השכירות.'); return; }
    if (!form.baseStart || !form.baseEnd) { fail('יש לבחור את חודשי תחילת וסיום השכירות.'); return; }
    if (Statso.core.monthToOrdinal(form.baseStart) > Statso.core.monthToOrdinal(form.baseEnd)) {
      fail('חודש סיום השכירות מוקדם מחודש ההתחלה.'); return;
    }
    if (!Number.isFinite(form.baseRent) || form.baseRent <= 0) { fail('יש להזין דמי שכירות חודשיים תקינים.'); return; }

    const baseIndexMonth = form.customBase ? form.baseIndexMonth
      : Statso.core.resolveIndexMonth(form.contractDate.slice(0, 7), 'known');
    const baseIndex = Statso.core.lookupChained(indexMap, baseIndexMonth, firstMonth, lastMonth);
    if (!baseIndex.ok) {
      fail('מדד הבסיס לחודש ' + Statso.core.formatMonthHe(baseIndexMonth) + ' אינו זמין בסדרה.'); return;
    }

    const list = [{label: 'תקופת השכירות הבסיסית', start: form.baseStart, end: form.baseEnd, rent: form.baseRent}];
    for (let i = 0; i < form.options.length; i += 1) {
      const option = form.options[i];
      if (!option.start || !option.end) { fail('יש להשלים את חודשי תקופת האופציה ' + (i + 1) + '.'); return; }
      if (Statso.core.monthToOrdinal(option.start) > Statso.core.monthToOrdinal(option.end)) {
        fail('בתקופת אופציה ' + (i + 1) + ' חודש הסיום מוקדם מחודש ההתחלה.'); return;
      }
      if (!Number.isFinite(option.rent) || option.rent <= 0) {
        fail('יש להזין דמי שכירות חודשיים בתקופת אופציה ' + (i + 1) + '.'); return;
      }
      list.push({label: 'תקופת אופציה ' + (i + 1), start: option.start, end: option.end, rent: option.rent});
    }

    periods = list.map(function (period, periodIndex) {
      const rows = monthsBetween(period.start, period.end).map(function (month) {
        const reference = indexFor(month, baseIndexMonth);
        const stored = overrides[key(periodIndex, month)];
        const actual = stored === undefined ? period.rent : stored;
        if (!reference.ok) {
          return {month: month, indexMonth: reference.month, available: false, nominal: period.rent,
            actual: actual, ratio: null, indexed: null, difference: null, payable: null,
            paid: Boolean(paid[key(periodIndex, month)])};
        }
        const rawRatio = reference.value / baseIndex.value;
        const ratio = form.floor === 'floor' ? Math.max(1, rawRatio) : rawRatio;
        const indexed = period.rent * ratio;
        const difference = indexed - actual;
        return {month: month, indexMonth: reference.month, available: true, nominal: period.rent,
          actual: actual, indexValue: reference.published, ratio: ratio, indexed: indexed,
          difference: difference, payable: Math.max(0, difference),
          paid: Boolean(paid[key(periodIndex, month)])};
      });
      return {index: periodIndex, label: period.label, start: period.start, end: period.end,
        rent: period.rent, rows: rows};
    });

    model = {form: form, baseIndexMonth: baseIndexMonth, baseIndexValue: baseIndex.value, periods: periods};
    el('tr-error').textContent = '';
    el('tr-output').hidden = false;
    const baseRow = indexMap.get(baseIndexMonth);
    el('tr-base-index-note').textContent = (form.customBase ? 'מדד בסיס מוסכם: ' : 'מדד ידוע במועד ההסכם: ')
      + Statso.core.formatMonthHe(baseIndexMonth) + ' = '
      + Statso.core.formatNumber(baseRow ? baseRow.value : baseIndex.value, 1);
    render();
  }

  // ---------- rendering -----------------------------------------------------
  function totalsOf(rows) {
    return rows.reduce(function (acc, row) {
      if (!row.available) { return acc; }
      acc.nominal += row.nominal; acc.actual += row.actual; acc.indexed += row.indexed;
      acc.difference += row.difference;
      if (!row.paid) { acc.payable += row.payable; }
      return acc;
    }, {nominal: 0, actual: 0, indexed: 0, difference: 0, payable: 0});
  }

  function rowHtml(periodIndex, row) {
    const id = key(periodIndex, row.month);
    if (!row.available) {
      return '<tr class="rent-row-pending"><th scope="row" dir="ltr">' + Statso.core.formatMonthHe(row.month) + '</th>'
        + '<td dir="ltr">' + Statso.core.formatNumber(row.nominal, 2) + '</td>'
        + '<td colspan="6">המדד לחודש ' + Statso.core.formatMonthHe(row.indexMonth) + ' טרם פורסם</td></tr>';
    }
    return '<tr><th scope="row" dir="ltr">' + Statso.core.formatMonthHe(row.month) + '</th>'
      + '<td dir="ltr">' + Statso.core.formatNumber(row.nominal, 2) + '</td>'
      + '<td dir="ltr">' + Statso.core.formatNumber(row.indexValue, 2) + '</td>'
      + '<td dir="ltr">' + Statso.core.formatNumber(row.ratio, 4) + '</td>'
      + '<td dir="ltr">' + Statso.core.formatNumber(row.indexed, 2) + '</td>'
      + '<td><input type="number" step="any" min="0" class="tr-actual" data-key="' + id
      + '" value="' + row.actual + '" aria-label="סכום ששולם בפועל"></td>'
      + '<td dir="ltr" class="' + (row.difference < 0 ? 'rent-negative' : '') + '">'
      + Statso.core.formatNumber(row.difference, 2) + '</td>'
      + '<td dir="ltr">' + Statso.core.formatNumber(row.payable, 2) + '</td>'
      + '<td><input type="checkbox" class="tr-paid" data-key="' + id + '"' + (row.paid ? ' checked' : '')
      + ' aria-label="ההפרש שולם"></td></tr>';
  }

  function periodHtml(period) {
    const totals = totalsOf(period.rows);
    return '<section class="rent-period"><header class="rent-period-head">'
      + '<h3>' + period.label + '</h3>'
      + '<span>' + Statso.core.formatMonthHe(period.start) + '–' + Statso.core.formatMonthHe(period.end)
      + ' · ' + Statso.core.formatNumber(period.rent, 2) + ' ₪ לחודש</span>'
      + '<label class="rent-mark-all"><input type="checkbox" class="tr-period-paid" data-period="' + period.index
      + '"> סימון כל התקופה כשולמה</label></header>'
      + '<div class="table-wrap"><table class="data-table rent-table"><thead><tr>'
      + ['חודש', 'נומינלי', 'מדד בבסיס ההסכם', 'מקדם', 'ממודד', 'שולם בפועל', 'הפרש', 'הפרש לתשלום', 'שולם']
        .map(function (text) { return '<th scope="col">' + text + '</th>'; }).join('')
      + '</tr></thead><tbody>' + period.rows.map(function (row) { return rowHtml(period.index, row); }).join('')
      + '</tbody><tfoot><tr><th scope="row">סה״כ</th>'
      + '<td dir="ltr">' + Statso.core.formatNumber(totals.nominal, 2) + '</td><td></td><td></td>'
      + '<td dir="ltr">' + Statso.core.formatNumber(totals.indexed, 2) + '</td>'
      + '<td dir="ltr">' + Statso.core.formatNumber(totals.actual, 2) + '</td>'
      + '<td dir="ltr">' + Statso.core.formatNumber(totals.difference, 2) + '</td>'
      + '<td dir="ltr">' + Statso.core.formatNumber(totals.payable, 2) + '</td><td></td></tr></tfoot></table></div>'
      + '</section>';
  }

  function render() {
    const all = periods.reduce(function (acc, period) { return acc.concat(period.rows); }, []);
    const totals = totalsOf(all);
    el('tr-summary').innerHTML = '<div class="rent-summary-grid">'
      + '<div><span>סה״כ נומינלי</span><strong dir="ltr">' + Statso.core.formatNumber(totals.nominal, 2) + ' ₪</strong></div>'
      + '<div><span>סה״כ ממודד</span><strong dir="ltr">' + Statso.core.formatNumber(totals.indexed, 2) + ' ₪</strong></div>'
      + '<div><span>סה״כ שולם בפועל</span><strong dir="ltr">' + Statso.core.formatNumber(totals.actual, 2) + ' ₪</strong></div>'
      + '<div class="rent-summary-highlight"><span>יתרת הפרשים לתשלום</span><strong dir="ltr">'
      + Statso.core.formatNumber(totals.payable, 2) + ' ₪</strong></div></div>';
    el('tr-periods').innerHTML = periods.map(periodHtml).join('');
    const select = el('tr-export-period');
    const current = select.value;
    select.innerHTML = '<option value="all">כל התקופות</option>' + periods.map(function (period) {
      return '<option value="' + period.index + '">' + period.label + '</option>';
    }).join('');
    select.value = Array.prototype.some.call(select.options, function (o) { return o.value === current; }) ? current : 'all';
    if (all.length && !rangeTouched) {
      el('tr-export-from').value = all[0].month;
      el('tr-export-to').value = all[all.length - 1].month;
    }
    bindRows();
  }

  function bindRows() {
    document.querySelectorAll('#tr-periods .tr-actual').forEach(function (input) {
      input.addEventListener('change', function () {
        const value = Number(input.value);
        if (Number.isFinite(value) && value >= 0) { overrides[input.dataset.key] = value; compute(); }
      });
    });
    document.querySelectorAll('#tr-periods .tr-paid').forEach(function (box) {
      box.addEventListener('change', function () {
        if (box.checked) { paid[box.dataset.key] = true; } else { delete paid[box.dataset.key]; }
        compute();
      });
    });
    document.querySelectorAll('#tr-periods .tr-period-paid').forEach(function (box) {
      box.addEventListener('change', function () {
        const period = periods[Number(box.dataset.period)];
        if (!period) { return; }
        period.rows.forEach(function (row) {
          if (box.checked) { paid[key(period.index, row.month)] = true; } else { delete paid[key(period.index, row.month)]; }
        });
        compute();
      });
    });
  }

  // ---------- export --------------------------------------------------------
  function exportSelection() {
    const scope = el('tr-export-period').value;
    const from = el('tr-export-from').value;
    const to = el('tr-export-to').value;
    const excludePaid = el('tr-exclude-paid').checked;
    const chosen = scope === 'all' ? periods : periods.filter(function (period) { return String(period.index) === scope; });
    return chosen.map(function (period) {
      const rows = period.rows.filter(function (row) {
        if (!row.available) { return false; }
        if (excludePaid && row.paid) { return false; }
        if (from && Statso.core.monthToOrdinal(row.month) < Statso.core.monthToOrdinal(from)) { return false; }
        if (to && Statso.core.monthToOrdinal(row.month) > Statso.core.monthToOrdinal(to)) { return false; }
        return true;
      });
      return {label: period.label, start: period.start, end: period.end, rent: period.rent, rows: rows};
    }).filter(function (period) { return period.rows.length; });
  }

  function contractRows() {
    const form = model.form;
    return [['מועד הסכם השכירות', Statso.core.formatIsoDateHe(form.contractDate)],
      ['שם המשכיר', form.landlord || '—'], ['שם השוכר', form.tenant || '—'],
      ['תקופת השכירות', Statso.core.formatMonthHe(form.baseStart) + '–' + Statso.core.formatMonthHe(form.baseEnd)],
      ['דמי שכירות חודשיים (₪)', form.baseRent],
      ['תקופות אופציה', form.options.length ? String(form.options.length) : 'אין'],
      ['מדד הבסיס', Statso.core.formatMonthHe(model.baseIndexMonth)
        + (form.customBase ? ' (מוסכם)' : ' (מדד ידוע במועד ההסכם)')],
      ['ערך מדד הבסיס', model.baseIndexPublished],
      ['אופן ההצמדה', form.floor === 'floor' ? 'רק הפרש לתשלום — ללא הפחתה בירידת מדד' : 'הצמדה מלאה לשני הכיוונים']];
  }

  const HEAD = ['חודש', 'נומינלי', 'מדד בבסיס ההסכם', 'מקדם', 'ממודד', 'שולם בפועל', 'הפרש', 'הפרש לתשלום'];

  function matrix(rows) {
    return rows.map(function (row) {
      return [Statso.core.formatMonthHe(row.month), row.nominal, row.indexValue,
        Number(row.ratio.toFixed(4)), row.indexed, row.actual, row.difference, row.payable];
    });
  }

  function exportRent(kind) {
    if (!model) { return; }
    const selection = exportSelection();
    if (!selection.length) { el('tr-error').textContent = 'אין חודשים בטווח שנבחר לייצוא.'; return; }
    el('tr-error').textContent = '';
    const grand = totalsOf(selection.reduce(function (acc, period) { return acc.concat(period.rows); }, []));
    const subtitle = (model.form.landlord || 'משכיר') + ' ← ' + (model.form.tenant || 'שוכר')
      + ' · מדד בסיס ' + Statso.core.formatMonthHe(model.baseIndexMonth);

    if (kind === 'xlsx') {
      const details = {name: 'פרטי ההסכם', columns: [{width: 28}, {width: 30}], merges: ['A1:B1'],
        rows: [[{v: 'הצמדת הסכם שכירות למדד', s: S().title}], []]};
      contractRows().forEach(function (row) {
        details.rows.push([{v: row[0], s: S().header},
          typeof row[1] === 'number' ? {v: row[1], s: S().money} : {v: row[1], s: S().boxed}]);
      });
      const sheet = {name: 'הפרשי הצמדה',
        columns: [{width: 12}, {width: 13}, {width: 14}, {width: 10}, {width: 13}, {width: 13}, {width: 13}, {width: 15}],
        merges: ['A1:H1'], rows: [[{v: 'הפרשי הצמדה — ' + subtitle, s: S().title}], []]};
      selection.forEach(function (period) {
        sheet.rows.push([{v: period.label + ' · ' + Statso.core.formatMonthHe(period.start) + '–'
          + Statso.core.formatMonthHe(period.end), s: S().title}]);
        sheet.rows.push(HEAD.map(function (text) { return {v: text, s: S().header}; }));
        matrix(period.rows).forEach(function (row) {
          sheet.rows.push([{v: row[0], s: S().boxed}].concat(row.slice(1).map(function (value) {
            return {v: value, s: S().money};
          })));
        });
        const totals = totalsOf(period.rows);
        sheet.rows.push([{v: 'סה״כ תקופה', s: S().header}, {v: totals.nominal, s: S().moneyBold},
          {v: '', s: S().header}, {v: '', s: S().header}, {v: totals.indexed, s: S().moneyBold},
          {v: totals.actual, s: S().moneyBold}, {v: totals.difference, s: S().moneyBold},
          {v: totals.payable, s: S().moneyBold}]);
        sheet.rows.push([]);
      });
      sheet.rows.push([{v: 'סה״כ לתשלום', s: S().header}, {v: '', s: S().header}, {v: '', s: S().header},
        {v: '', s: S().header}, {v: '', s: S().header}, {v: '', s: S().header}, {v: '', s: S().header},
        {v: grand.payable, s: S().moneyBold}]);
      Statso.exporter.downloadWorkbook('statso-' + Statso.i18n.t('הפרשי הצמדה') + '-' + Statso.exporter.stamp() + '.xlsx',
        [details, sheet]);
      return;
    }

    const blocks = ['<h2>פרטי ההסכם</h2>' + Statso.exporter.tableHtml(['פריט', 'ערך'], contractRows())];
    selection.forEach(function (period) {
      blocks.push('<h2>' + Statso.xlsx.escapeXml(period.label) + ' · '
        + Statso.core.formatMonthHe(period.start) + '–' + Statso.core.formatMonthHe(period.end) + '</h2>'
        + Statso.exporter.tableHtml(HEAD, matrix(period.rows)));
    });
    blocks.push('<p class="print-total">סך ההפרשים לתשלום: <strong dir="ltr">'
      + Statso.core.formatNumber(grand.payable, 2) + ' ₪</strong></p>');
    blocks.push('<p class="print-note">החישוב מבוסס על מדד המחירים לצרכן שמפרסמת הלשכה המרכזית לסטטיסטיקה. '
      + 'לכל חודש שכירות שימש המדד הידוע לאותו חודש, ביחס למדד הבסיס שנקבע בהסכם.</p>');
    Statso.exporter.printDocument('הפרשי הצמדה — הסכם שכירות',
      Statso.exporter.documentHtml('הצמדת הסכם שכירות למדד', subtitle, blocks));
  }

  // ---------- wiring --------------------------------------------------------
  function addOptionRow(values) {
    const host = el('tr-option-rows');
    const index = host.querySelectorAll('.rent-option').length;
    host.insertAdjacentHTML('beforeend', optionRowHtml(index, values || {}));
    const row = host.lastElementChild;
    row.querySelectorAll('input').forEach(function (input) { input.addEventListener('change', compute); });
    row.querySelector('.tr-opt-remove').addEventListener('click', function () { row.remove(); compute(); });
    compute();
  }

  function init(cpiDoc, map) {
    indexMap = map; firstMonth = cpiDoc.first_month; lastMonth = cpiDoc.last_month;
    const fy = Number(firstMonth.slice(0, 4)); const ly = Number(lastMonth.slice(0, 4));
    let years = '';
    for (let y = fy; y <= ly; y += 1) { years += '<option value="' + y + '">' + y + '</option>'; }
    let months = '';
    for (let m = 1; m <= 12; m += 1) { const v = String(m).padStart(2, '0'); months += '<option value="' + v + '">' + v + '</option>'; }
    el('tr-base-index-year').innerHTML = years; el('tr-base-index-month').innerHTML = months;
    el('tr-base-index-year').value = String(ly); el('tr-base-index-month').value = lastMonth.slice(5);

    const startOrdinal = Statso.core.monthToOrdinal(lastMonth) - 23;
    const start = Statso.core.ordinalToMonth(startOrdinal);
    el('tr-contract-date').value = start + '-01';
    el('tr-base-start').value = start;
    el('tr-base-end').value = Statso.core.ordinalToMonth(startOrdinal + 11);
    el('tr-contract-date').max = lastMonth + '-28';

    ['tr-contract-date', 'tr-landlord', 'tr-tenant', 'tr-base-start', 'tr-base-end', 'tr-base-rent',
      'tr-base-index-year', 'tr-base-index-month'].forEach(function (id) { on(id, 'change', compute); });
    on('tr-base-rent', 'input', compute);
    document.querySelectorAll('input[name="tr-floor"]').forEach(function (radio) { radio.addEventListener('change', compute); });
    on('tr-has-options', 'change', function () {
      el('tr-options').hidden = !el('tr-has-options').checked;
      if (el('tr-has-options').checked && !el('tr-option-rows').children.length) {
        const end = el('tr-base-end').value;
        const next = end ? Statso.core.ordinalToMonth(Statso.core.monthToOrdinal(end) + 1) : '';
        addOptionRow({start: next, end: next ? Statso.core.ordinalToMonth(Statso.core.monthToOrdinal(next) + 11) : '',
          rent: el('tr-base-rent').value});
      } else { compute(); }
    });
    on('tr-custom-base', 'change', function () {
      el('tr-custom-base-fields').hidden = !el('tr-custom-base').checked;
      compute();
    });
    on('tr-add-option', 'click', function () { addOptionRow({}); });
    ['tr-export-period', 'tr-export-from', 'tr-export-to', 'tr-exclude-paid'].forEach(function (id) {
      on(id, 'change', function () { el('tr-error').textContent = ''; });
    });
    ['tr-export-from', 'tr-export-to'].forEach(function (id) {
      on(id, 'change', function () { rangeTouched = true; });
    });
    on('tr-xlsx', 'click', function () { exportRent('xlsx'); });
    on('tr-pdf', 'click', function () { exportRent('pdf'); });
    compute();
  }

  Statso.rent = {init: init, compute: compute, exportRent: exportRent, exportSelection: exportSelection,
    monthsBetween: monthsBetween, totalsOf: totalsOf, HEAD: HEAD,
    state: function () { return model; }};
})(window);
