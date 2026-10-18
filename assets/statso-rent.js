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
  function say(text) { return Statso.i18n ? Statso.i18n.t(text) : text; }
  function on(id, event, handler) { const node = el(id); if (node) { node.addEventListener(event, handler); } }
  function monthsBetween(start, end) {
    const out = [];
    for (let n = Statso.core.monthToOrdinal(start); n <= Statso.core.monthToOrdinal(end); n += 1) {
      out.push(Statso.core.ordinalToMonth(n));
    }
    return out;
  }
  function settled(x) { return Math.abs(x) < 0.005 ? 0 : x; }
  function negative(x) { return settled(x) < 0; }
  function round6(x) { return typeof x === 'number' && Number.isFinite(x) ? Number(x.toFixed(6)) : x; }

  function key(periodIndex, month) { return periodIndex + ':' + month; }

  function isTextMonth(input) { return input.type !== 'month'; }
  const MONTH_GROUPS = [
    {hint: 'tr-base-month-hint', fields: function () { return [el('tr-base-start'), el('tr-base-end')]; }},
    {hint: 'tr-options-month-hint', fields: function () {
      return document.querySelectorAll('#tr-option-rows .tr-opt-start, #tr-option-rows .tr-opt-end');
    }},
    {hint: 'tr-export-month-hint', fields: function () { return [el('tr-export-from'), el('tr-export-to')]; }}
  ];

  function describe(input) {
    input.setAttribute('aria-describedby', input.dataset.monthHint + (input.getAttribute('aria-invalid') === 'true' ? ' tr-error' : ''));
  }

  function syncMonthFields() {
    MONTH_GROUPS.forEach(function (group) {
      const fields = Array.from(group.fields());
      el(group.hint).hidden = !fields.some(isTextMonth);
      fields.forEach(function (input) {
        if (isTextMonth(input)) { input.dataset.monthHint = group.hint; describe(input); }
      });
    });
  }

  function monthOf(input) {
    if (!isTextMonth(input)) { return input.value; }
    const month = Statso.core.parseMonthInput(input.value);
    // Once the parse itself fails, this mechanism owns the flag, so flagFields never withdraws it.
    if (month === null) { input.setAttribute('aria-invalid', 'true'); input.removeAttribute('data-error-flag'); }
    else {
      input.removeAttribute('aria-invalid');
      if (month !== input.value) { input.value = month; }
    }
    if (input.dataset.monthHint) { describe(input); }
    return month;
  }

  // Every place that rewrites the error line checks the export range, so an invalid export month keeps its message
  // while the field stays aria-invalid and points at it. Both fields are read, so both get flagged.
  function exportRangeProblem() {
    const from = monthOf(el('tr-export-from'));
    const to = monthOf(el('tr-export-to'));
    return from === null || to === null ? 'חודש לא תקין בטווח הייצוא — יש להזין YYYY-MM או MM/YYYY.' : '';
  }

  // ---------- reading the form ---------------------------------------------
  // Every extra period names itself ("תקופה 1", "תקופה 2"…): without that, a
  // screen reader hears the same "מחודש / עד חודש / הסרה" once per row with no
  // way to tell which period a field belongs to. The title is the group's
  // name (visually hidden, so the row layout stays as it was), and the remove
  // button is named from its own text plus that title.
  let optionSerial = 0;
  function optionRowHtml(index, values) {
    optionSerial += 1;
    const titleId = 'tr-opt-title-' + optionSerial;
    const removeId = 'tr-opt-remove-' + optionSerial;
    return '<div class="rent-option" role="group" aria-labelledby="' + titleId + '" data-option="' + index + '">'
      + '<p class="rent-option-title sr-only" id="' + titleId + '">תקופה <span class="tr-opt-num">' + (index + 1) + '</span></p>'
      + '<label>מחודש <input type="month" placeholder="YYYY-MM" class="tr-opt-start" value="' + (values.start || '') + '"></label>'
      + '<label>עד חודש <input type="month" placeholder="YYYY-MM" class="tr-opt-end" value="' + (values.end || '') + '"></label>'
      + '<label>דמי שכירות חודשיים (₪) <input type="number" min="0" step="any" class="tr-opt-rent" value="'
      + (values.rent || '') + '"></label>'
      + '<button type="button" class="btn-ghost tr-opt-remove" id="' + removeId + '" aria-labelledby="' + removeId + ' ' + titleId
      + '">הסרה</button></div>';
  }

  function renumberOptionRows() {
    el('tr-option-rows').querySelectorAll('.rent-option').forEach(function (row, i) {
      row.querySelector('.tr-opt-num').textContent = String(i + 1);
    });
  }

  function readOptions() {
    return Array.prototype.map.call(document.querySelectorAll('#tr-option-rows .rent-option'), function (row) {
      return {start: monthOf(row.querySelector('.tr-opt-start')),
        end: monthOf(row.querySelector('.tr-opt-end')),
        rent: Number(row.querySelector('.tr-opt-rent').value)};
    });
  }

  function readForm() {
    return {contractDate: el('tr-contract-date').value,
      landlord: el('tr-landlord').value.trim(), tenant: el('tr-tenant').value.trim(),
      baseStart: monthOf(el('tr-base-start')), baseEnd: monthOf(el('tr-base-end')),
      baseRent: Number(el('tr-base-rent').value),
      hasOptions: el('tr-has-options').checked,
      options: el('tr-has-options').checked ? readOptions() : [],
      customBase: el('tr-custom-base').checked,
      baseIndexMonth: el('tr-base-index-year').value + '-' + el('tr-base-index-month').value,
      floor: document.querySelector('input[name="tr-floor"]:checked').value};
  }

  // The fields an error is about are marked invalid and point at the message, so they say so when focused. Fields the
  // month text fallback already marked invalid stay with that mechanism.
  function showError(message, fields) {
    setText(el('tr-error'), message);
    Statso.core.flagFields('tr-error', fields || []);
  }

  function fail(message, fields) {
    model = null;
    showError(message, fields);
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
    syncMonthFields();
    const form = readForm();
    const baseMonths = ['tr-base-start', 'tr-base-end'];
    if (!form.contractDate) { fail('יש לבחור את מועד הסכם השכירות.', ['tr-contract-date']); return; }
    if (form.baseStart === null || form.baseEnd === null) { fail('חודש לא תקין בתקופת השכירות הבסיסית — יש להזין YYYY-MM או MM/YYYY.', baseMonths); return; }
    if (!form.baseStart || !form.baseEnd) { fail('יש לבחור את חודשי תחילת וסיום השכירות.', baseMonths.filter(function (id) { return !el(id).value; })); return; }
    if (Statso.core.monthToOrdinal(form.baseStart) > Statso.core.monthToOrdinal(form.baseEnd)) {
      fail('חודש סיום השכירות מוקדם מחודש ההתחלה.', baseMonths); return;
    }
    if (!Number.isFinite(form.baseRent) || form.baseRent <= 0) { fail('יש להזין דמי שכירות חודשיים תקינים.', ['tr-base-rent']); return; }

    const baseIndexMonth = form.customBase ? form.baseIndexMonth
      : Statso.core.resolveIndexMonth(form.contractDate.slice(0, 7), 'known');
    const baseIndex = Statso.core.lookupChained(indexMap, baseIndexMonth, firstMonth, lastMonth);
    if (!baseIndex.ok) {
      fail('מדד הבסיס לחודש ' + Statso.core.formatMonthHe(baseIndexMonth) + ' אינו זמין בסדרה.',
        form.customBase ? ['tr-base-index-year', 'tr-base-index-month'] : ['tr-contract-date']); return;
    }

    const list = [{label: 'תקופת השכירות הבסיסית', start: form.baseStart, end: form.baseEnd, rent: form.baseRent}];
    for (let i = 0; i < form.options.length; i += 1) {
      const option = form.options[i];
      const row = document.querySelectorAll('#tr-option-rows .rent-option')[i];
      const optionMonths = [row.querySelector('.tr-opt-start'), row.querySelector('.tr-opt-end')];
      if (option.start === null || option.end === null) { fail('חודש לא תקין בתקופת אופציה ' + (i + 1) + ' — יש להזין YYYY-MM או MM/YYYY.', optionMonths); return; }
      if (!option.start || !option.end) { fail('יש להשלים את חודשי תקופת האופציה ' + (i + 1) + '.', optionMonths.filter(function (input) { return !input.value; })); return; }
      if (Statso.core.monthToOrdinal(option.start) > Statso.core.monthToOrdinal(option.end)) {
        fail('בתקופת אופציה ' + (i + 1) + ' חודש הסיום מוקדם מחודש ההתחלה.', optionMonths); return;
      }
      if (!Number.isFinite(option.rent) || option.rent <= 0) {
        fail('יש להזין דמי שכירות חודשיים בתקופת אופציה ' + (i + 1) + '.', [row.querySelector('.tr-opt-rent')]); return;
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
          difference: difference, payable: form.floor === 'floor' ? Math.max(0, difference) : difference,
          paid: Boolean(paid[key(periodIndex, month)])};
      });
      return {index: periodIndex, label: period.label, start: period.start, end: period.end,
        rent: period.rent, rows: rows};
    });

    const baseRow = indexMap.get(baseIndexMonth);
    const baseIndexPublished = baseRow ? baseRow.value : baseIndex.value;
    model = {form: form, baseIndexMonth: baseIndexMonth, baseIndexValue: baseIndex.value, baseIndexPublished: baseIndexPublished, periods: periods};
    el('tr-output').hidden = false;
    el('tr-base-index-note').textContent = (form.customBase ? 'מדד בסיס מוסכם: ' : 'מדד ידוע במועד ההסכם: ')
      + Statso.core.formatMonthHe(baseIndexMonth) + ' = '
      + Statso.core.formatNumber(baseIndexPublished, 1);
    render();
    // setText leaves an unchanged message alone, so a pending export error is not re-announced on every recompute
    // (the rent field recomputes on each keystroke).
    showError(exportRangeProblem());
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

  function rowText(row) {
    const n = Statso.core.formatNumber;
    return {nominal: n(row.nominal, 2), index: n(row.indexValue, 2), ratio: n(row.ratio, 4),
      indexed: n(row.indexed, 2), difference: n(row.difference, 2), payable: n(settled(row.payable), 2)};
  }

  function totalsText(totals) {
    const n = Statso.core.formatNumber;
    return {nominal: n(totals.nominal, 2), indexed: n(totals.indexed, 2), actual: n(totals.actual, 2),
      difference: n(totals.difference, 2), payable: n(settled(totals.payable), 2)};
  }

  // The period's "mark everything as paid" box mirrors its rows: ticked when every published month is settled.
  function allPaid(period) {
    const rows = period.rows.filter(function (row) { return row.available; });
    return rows.length > 0 && rows.every(function (row) { return row.paid; });
  }

  function somePaid(period) {
    return period.rows.some(function (row) { return row.available && row.paid; });
  }

  // Ticked when every published month is settled, "mixed" when only some are, so the box says what the rows say.
  function syncMarkAll(box, period) {
    box.checked = allPaid(period);
    box.indeterminate = !box.checked && somePaid(period);
  }

  function rowHtml(periodIndex, row) {
    const id = key(periodIndex, row.month);
    if (!row.available) {
      return '<tr class="rent-row-pending"><th scope="row" dir="ltr" id="tr-p' + periodIndex + '-m' + row.month + '">' + Statso.core.formatMonthHe(row.month) + '</th>'
        + '<td dir="ltr">' + Statso.core.formatNumber(row.nominal, 2) + '</td>'
        + '<td colspan="6">המדד לחודש ' + Statso.core.formatMonthHe(row.indexMonth) + ' טרם פורסם</td></tr>';
    }
    const text = rowText(row);
    return '<tr><th scope="row" dir="ltr" id="tr-p' + periodIndex + '-m' + row.month + '">' + Statso.core.formatMonthHe(row.month) + '</th>'
      + '<td dir="ltr">' + text.nominal + '</td>'
      + '<td dir="ltr">' + text.index + '</td>'
      + '<td dir="ltr">' + text.ratio + '</td>'
      + '<td dir="ltr">' + text.indexed + '</td>'
      + '<td><input type="number" step="any" min="0" class="tr-actual" data-key="' + id
      + '" value="' + row.actual + '" aria-labelledby="tr-p' + periodIndex + '-c5 tr-p' + periodIndex + '-m' + row.month + '"></td>'
      + '<td dir="ltr" class="' + (row.difference < 0 ? 'rent-negative' : '') + '">' + text.difference + '</td>'
      + '<td dir="ltr"' + (negative(row.payable) ? ' class="rent-negative"' : '') + '>' + text.payable + '</td>'
      + '<td><input type="checkbox" class="tr-paid" data-key="' + id + '"' + (row.paid ? ' checked' : '')
      + ' aria-labelledby="tr-p' + periodIndex + '-c8 tr-p' + periodIndex + '-m' + row.month + '"></td></tr>';
  }

  // Each table scrolls sideways inside its own keyboard stop: a region named by the period's visible heading
  // (README: a focusable scroll area is a region with a unique name). Editing a row writes into the existing cells
  // only, so this node, the focus on it and its scroll position survive the edit.
  function periodHtml(period) {
    const sums = totalsOf(period.rows);
    const totals = totalsText(sums);
    return '<section class="rent-period"><header class="rent-period-head">'
      + '<h3 id="tr-p' + period.index + '-title">' + period.label + '</h3>'
      + '<span>' + Statso.core.formatMonthHe(period.start) + '–' + Statso.core.formatMonthHe(period.end)
      + ' · ' + Statso.core.formatNumber(period.rent, 2) + ' ₪ לחודש</span>'
      + '<label class="rent-mark-all"><input type="checkbox" class="tr-period-paid" data-period="' + period.index
      + '" aria-labelledby="tr-p' + period.index + '-markall tr-p' + period.index + '-title"'
      + (allPaid(period) ? ' checked' : '') + '> <span id="tr-p' + period.index + '-markall">סימון כל התקופה כשולמה</span></label></header>'
      + '<div class="table-wrap rent-scroll" tabindex="0" role="region" aria-labelledby="tr-p' + period.index + '-title">'
      + '<table class="data-table rent-table"><caption class="sr-only">' + period.label
      + '</caption><thead><tr>'
      + ['חודש', 'נומינלי', 'מדד בבסיס ההסכם', 'מקדם', 'ממודד', 'שולם בפועל', 'הפרש', 'הפרש לתשלום', 'שולם']
        .map(function (text, column) { return '<th scope="col" id="tr-p' + period.index + '-c' + column + '">' + text + '</th>'; }).join('')
      + '</tr></thead><tbody>' + period.rows.map(function (row) { return rowHtml(period.index, row); }).join('')
      + '</tbody><tfoot><tr><th scope="row">סה״כ</th>'
      + '<td dir="ltr">' + totals.nominal + '</td><td></td><td></td>'
      + '<td dir="ltr">' + totals.indexed + '</td>'
      + '<td dir="ltr">' + totals.actual + '</td>'
      + '<td dir="ltr">' + totals.difference + '</td>'
      + '<td dir="ltr"' + (negative(sums.payable) ? ' class="rent-negative"' : '') + '>' + totals.payable + '</td><td></td></tr></tfoot></table></div>'
      + '</section>';
  }

  // The tables are rebuilt only when their shape changes (other dates, rents or months, which come from the form
  // above them). Editing "paid in practice" or ticking "paid" changes numbers only, so those are written into the
  // existing cells: replacing the table would drop keyboard focus to <body>, reset the scroll position and swallow
  // the click that follows an edit (its target would be gone between mouse-down and mouse-up).
  let renderedShape = null;

  function shapeOf(list) {
    return list.map(function (period) {
      return [period.index, period.label, period.start, period.end, period.rent].concat(period.rows.map(function (row) {
        return row.month + (row.available ? '+' : '-' + row.indexMonth);
      })).join('|');
    }).join('\n');
  }

  // An unchanged text is left alone. The page may already show the translation of a Hebrew message (the engine rewrites
  // the node after it is set), so the translated form counts as unchanged too, or the English UI would re-announce it.
  function setText(node, text) { if (node.textContent !== text && node.textContent !== say(text)) { node.textContent = text; } }

  function patchPeriods(host) {
    const sections = host.querySelectorAll('.rent-period');
    periods.forEach(function (period, i) {
      const section = sections[i];
      const bodyRows = section.querySelectorAll('tbody tr');
      period.rows.forEach(function (row, j) {
        if (!row.available) { return; }
        const text = rowText(row);
        const cells = bodyRows[j].children;
        setText(cells[1], text.nominal); setText(cells[2], text.index); setText(cells[3], text.ratio);
        setText(cells[4], text.indexed);
        const input = cells[5].firstElementChild;
        if (Number(input.value) !== row.actual) { input.value = String(row.actual); }
        cells[6].classList.toggle('rent-negative', row.difference < 0);
        setText(cells[6], text.difference); setText(cells[7], text.payable);
        cells[7].classList.toggle('rent-negative', negative(row.payable));
        cells[8].firstElementChild.checked = row.paid;
      });
      const foot = section.querySelector('tfoot tr').children;
      const sums = totalsOf(period.rows);
      const totals = totalsText(sums);
      setText(foot[1], totals.nominal); setText(foot[4], totals.indexed); setText(foot[5], totals.actual);
      setText(foot[6], totals.difference); setText(foot[7], totals.payable);
      foot[7].classList.toggle('rent-negative', negative(sums.payable));
      syncMarkAll(section.querySelector('.tr-period-paid'), period);
    });
  }

  function render() {
    const all = periods.reduce(function (acc, period) { return acc.concat(period.rows); }, []);
    const totals = totalsOf(all);
    el('tr-summary').innerHTML = '<div class="rent-summary-grid">'
      + '<div><span>סה״כ נומינלי</span><strong dir="ltr">' + Statso.core.formatNumber(totals.nominal, 2) + ' ₪</strong></div>'
      + '<div><span>סה״כ ממודד</span><strong dir="ltr">' + Statso.core.formatNumber(totals.indexed, 2) + ' ₪</strong></div>'
      + '<div><span>סה״כ שולם בפועל</span><strong dir="ltr">' + Statso.core.formatNumber(totals.actual, 2) + ' ₪</strong></div>'
      + '<div class="rent-summary-highlight"><span>יתרת הפרשים לתשלום</span><strong dir="ltr"' + (negative(totals.payable) ? ' class="rent-negative"' : '') + '>'
      + Statso.core.formatNumber(settled(totals.payable), 2) + ' ₪</strong></div></div>';
    const host = el('tr-periods');
    const shape = shapeOf(periods);
    if (renderedShape === shape && host.firstElementChild) {
      patchPeriods(host);
    } else {
      host.innerHTML = periods.map(periodHtml).join('');
      renderedShape = shape;
      Array.prototype.forEach.call(host.querySelectorAll('.tr-period-paid'), function (box) {
        const period = periods[Number(box.dataset.period)];
        if (period) { syncMarkAll(box, period); }
      });
    }
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
  }

  // One listener on the container (the tables inside it are replaced, the container is not).
  function onPeriodsChange(event) {
    const box = event.target;
    if (!box || !box.classList) { return; }
    if (box.classList.contains('tr-actual')) {
      const value = Number(box.value);
      if (Number.isFinite(value) && value >= 0) { overrides[box.dataset.key] = value; compute(); }
    } else if (box.classList.contains('tr-paid')) {
      if (box.checked) { paid[box.dataset.key] = true; } else { delete paid[box.dataset.key]; }
      compute();
    } else if (box.classList.contains('tr-period-paid')) {
      const period = periods[Number(box.dataset.period)];
      if (!period) { return; }
      period.rows.forEach(function (row) {
        if (box.checked) { paid[key(period.index, row.month)] = true; } else { delete paid[key(period.index, row.month)]; }
      });
      compute();
    }
  }

  // ---------- export --------------------------------------------------------
  function exportSelection() {
    const scope = el('tr-export-period').value;
    const from = monthOf(el('tr-export-from'));
    const to = monthOf(el('tr-export-to'));
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
      // v is the tidy stored value; p is the unrounded one the PDF formats, so it prints what the screen shows
      return [Statso.core.formatMonthHe(row.month), row.nominal, {v: round6(row.indexValue), f: 'money', p: row.indexValue},
        {v: Number(row.ratio.toFixed(4)), f: 'ratio', p: row.ratio}, row.indexed, row.actual, row.difference, settled(row.payable)];
    });
  }

  function exportRent(kind) {
    if (!model) { return; }
    syncMonthFields();
    const problem = exportRangeProblem();
    if (problem) { showError(problem); return; }
    const selection = exportSelection();
    if (!selection.length) { showError('אין חודשים בטווח שנבחר לייצוא.', ['tr-export-from', 'tr-export-to']); return; }
    showError('');
    const grand = totalsOf(selection.reduce(function (acc, period) { return acc.concat(period.rows); }, []));
    const subtitle = (model.form.landlord || say('משכיר')) + ' ← ' + (model.form.tenant || say('שוכר'))
      + ' · מדד בסיס ' + Statso.core.formatMonthHe(model.baseIndexMonth);

    if (kind === 'xlsx') {
      const details = {name: 'פרטי ההסכם', columns: [{width: 28}, {width: 30}],
        rows: [[{v: 'הצמדת הסכם שכירות למדד', s: S().title}], []]};
      contractRows().forEach(function (row) {
        details.rows.push([{v: row[0], s: S().header},
          typeof row[1] === 'number' ? {v: row[1], s: S().money} : {v: row[1], s: S().boxed}]);
      });
      const sheet = {name: 'הפרשי הצמדה',
        columns: [{width: 12}, {width: 13}, {width: 14}, {width: 10}, {width: 13}, {width: 13}, {width: 13}, {width: 15}],
        rows: [[{v: say('הפרשי הצמדה') + ' — ' + subtitle, s: S().title}], []]};
      selection.forEach(function (period) {
        sheet.rows.push([{v: say(period.label) + ' · ' + Statso.core.formatMonthHe(period.start) + '–'
          + Statso.core.formatMonthHe(period.end), s: S().title}]);
        sheet.rows.push(HEAD.map(function (text) { return {v: text, s: S().header}; }));
        matrix(period.rows).forEach(function (row) {
          sheet.rows.push([{v: row[0], s: S().boxed}].concat(row.slice(1).map(function (value) {
            return value !== null && typeof value === 'object' ? {v: value.v, s: value.f === 'ratio' ? S().ratio : S().money} : {v: value, s: S().money};
          })));
        });
        const totals = totalsOf(period.rows);
        sheet.rows.push([{v: 'סה״כ תקופה', s: S().header}, {v: totals.nominal, s: S().moneyBold},
          {v: '', s: S().header}, {v: '', s: S().header}, {v: totals.indexed, s: S().moneyBold},
          {v: totals.actual, s: S().moneyBold}, {v: totals.difference, s: S().moneyBold},
          {v: settled(totals.payable), s: S().moneyBold}]);
        sheet.rows.push([]);
      });
      sheet.rows.push([{v: 'סה״כ לתשלום', s: S().header}, {v: '', s: S().header}, {v: '', s: S().header},
        {v: '', s: S().header}, {v: '', s: S().header}, {v: '', s: S().header}, {v: '', s: S().header},
        {v: settled(grand.payable), s: S().moneyBold}]);
      Statso.exporter.downloadWorkbook('statso-' + Statso.i18n.t('הפרשי הצמדה') + '-' + Statso.exporter.stamp() + '.xlsx',
        [details, sheet], {title: say('הצמדת הסכם שכירות למדד')});
      return;
    }

    const blocks = ['<h2>פרטי ההסכם</h2>' + Statso.exporter.tableHtml(['פריט', 'ערך'], contractRows(), 'פרטי ההסכם')];
    selection.forEach(function (period) {
      blocks.push('<h2>' + Statso.xlsx.escapeXml(say(period.label)) + ' · '
        + Statso.core.formatMonthHe(period.start) + '–' + Statso.core.formatMonthHe(period.end) + '</h2>'
        + Statso.exporter.tableHtml(HEAD, matrix(period.rows), say(period.label) + ' · ' + Statso.core.formatMonthHe(period.start) + '–' + Statso.core.formatMonthHe(period.end)));
    });
    blocks.push('<p class="print-total">סך ההפרשים לתשלום: <strong dir="ltr"' + (negative(grand.payable) ? ' class="rent-negative"' : '') + '>'
      + Statso.core.formatNumber(settled(grand.payable), 2) + ' ₪</strong></p>');
    blocks.push('<p class="print-note">' + say('החישוב מבוסס על מדד המחירים לצרכן שמפרסמת הלשכה המרכזית לסטטיסטיקה.') + ' '
      + say('לכל חודש שכירות שימש המדד הידוע לאותו חודש, ביחס למדד הבסיס שנקבע בהסכם.') + '</p>');
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
    // Removing the row that holds keyboard focus would drop focus to <body>;
    // hand it to the button that adds a period instead.
    row.querySelector('.tr-opt-remove').addEventListener('click', function () {
      row.remove(); renumberOptionRows(); compute(); el('tr-add-option').focus();
    });
    compute();
    return row;
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
        const end = monthOf(el('tr-base-end')) || '';
        const next = end ? Statso.core.ordinalToMonth(Statso.core.monthToOrdinal(end) + 1) : '';
        addOptionRow({start: next, end: next ? Statso.core.ordinalToMonth(Statso.core.monthToOrdinal(next) + 11) : '',
          rent: el('tr-base-rent').value});
      } else { compute(); }
    });
    on('tr-custom-base', 'change', function () {
      el('tr-custom-base-fields').hidden = !el('tr-custom-base').checked;
      compute();
    });
    on('tr-periods', 'change', onPeriodsChange);
    on('tr-add-option', 'click', function () { addOptionRow({}).querySelector('input').focus(); });
    ['tr-export-period', 'tr-exclude-paid'].forEach(function (id) {
      on(id, 'change', function () { showError(exportRangeProblem()); });
    });
    ['tr-export-from', 'tr-export-to'].forEach(function (id) {
      on(id, 'change', function () {
        rangeTouched = true;
        syncMonthFields();
        showError(exportRangeProblem());
      });
    });
    on('tr-xlsx', 'click', function () { exportRent('xlsx'); });
    on('tr-pdf', 'click', function () { exportRent('pdf'); });
    compute();
  }

  Statso.rent = {init: init, compute: compute, exportRent: exportRent, exportSelection: exportSelection,
    monthsBetween: monthsBetween, totalsOf: totalsOf, HEAD: HEAD,
    state: function () { return model; }};
})(window);
