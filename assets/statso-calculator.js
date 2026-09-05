(function (root) {
  'use strict';
  const Statso = root.Statso = root.Statso || {};
  let indexMap, firstMonth, lastMonth;
  let fxDaily = null;
  let fxPending = false;
  function options(from, to, pad) { let out = ''; for (let n = from; n <= to; n += 1) { const v = pad ? String(n).padStart(2, '0') : String(n); out += '<option value="' + v + '">' + v + '</option>'; } return out; }
  function populateMonthSelects(first, last) {
    const fy = Number(first.slice(0, 4)); const ly = Number(last.slice(0, 4));
    const yearOptions = options(fy, ly, false); const monthOptions = options(1, 12, true);
    document.getElementById('calc-base-year').innerHTML = yearOptions;
    document.getElementById('calc-target-year').innerHTML = yearOptions;
    document.getElementById('calc-base-month').innerHTML = monthOptions;
    document.getElementById('calc-target-month').innerHTML = monthOptions;
    document.getElementById('calc-base-year').value = String(Math.max(fy, ly - 1));
    document.getElementById('calc-base-month').value = last.slice(5);
    document.getElementById('calc-target-year').value = String(ly);
    document.getElementById('calc-target-month').value = last.slice(5);
  }
  function populateCurrencySelects(summary) {
    const rows = summary.rates || [];
    if (!rows.length) { throw new Error('רשימת המטבעות ריקה'); }
    const codes = ['ILS'].concat(rows.map(function (row) { return row.code; }));
    const html = codes.map(function (code) {
      return '<option value="' + code + '">' + (Statso.core.CURRENCY_NAMES[code] || code) + ' (' + code + ')</option>';
    }).join('');
    const from = document.getElementById('calc-fx-from'); const to = document.getElementById('calc-fx-to');
    from.innerHTML = html; to.innerHTML = html; from.value = 'ILS'; to.value = 'USD';
    const dates = rows.map(function (row) { return row.latest.date; }).sort();
    const starts = rows.map(function (row) { return row.first_date; }).sort();
    const dateInput = document.getElementById('calc-fx-date');
    dateInput.min = starts[0]; dateInput.max = dates[dates.length - 1]; dateInput.value = dates[dates.length - 1];
  }
  function currentKind() { return document.querySelector('input[name="calc-kind"]:checked').value; }
  function readInputs() {
    return {amount: Number(document.getElementById('calc-amount').value), baseMonth: document.getElementById('calc-base-year').value + '-' + document.getElementById('calc-base-month').value, targetMonth: document.getElementById('calc-target-year').value + '-' + document.getElementById('calc-target-month').value, mode: document.querySelector('input[name="calc-mode"]:checked').value};
  }
  function readFxInputs() {
    return {amount: Number(document.getElementById('calc-amount').value), from: document.getElementById('calc-fx-from').value, to: document.getElementById('calc-fx-to').value, date: document.getElementById('calc-fx-date').value};
  }
  function fail(resultId, message) {
    document.getElementById('calc-error').textContent = message;
    document.getElementById(resultId).hidden = true;
  }
  function reject(month, reason) {
    const detail = reason === 'missing' ? 'אינו קיים בסדרה' : 'מחוץ לטווח הנתונים';
    fail('calc-result', 'המדד לחודש ' + Statso.core.formatMonthHe(month) + ' ' + detail + '. הטווח הזמין הוא ' + Statso.core.formatMonthHe(firstMonth) + '–' + Statso.core.formatMonthHe(lastMonth) + '.');
  }
  function recomputeIndex() {
    const input = readInputs();
    if (!Number.isFinite(input.amount) || input.amount < 0) { fail('calc-result', 'יש להזין סכום תקין שאינו שלילי.'); return; }
    const baseResolved = Statso.core.resolveIndexMonth(input.baseMonth, input.mode);
    const targetResolved = Statso.core.resolveIndexMonth(input.targetMonth, input.mode);
    const base = Statso.core.lookupChained(indexMap, baseResolved, firstMonth, lastMonth);
    if (!base.ok) { reject(baseResolved, base.reason); return; }
    const target = Statso.core.lookupChained(indexMap, targetResolved, firstMonth, lastMonth);
    if (!target.ok) { reject(targetResolved, target.reason); return; }
    const result = Statso.core.indexAmount(input.amount, base.value, target.value);
    document.getElementById('calc-error').textContent = '';
    document.getElementById('calc-result').hidden = false;
    document.getElementById('calc-result-indexed').textContent = Statso.core.formatNumber(result.indexed, 2);
    document.getElementById('calc-result-difference').textContent = Statso.core.formatNumber(result.difference, 2);
  }
  function quote(code, isoDate) {
    if (code === 'ILS') { return {ok: true, rate: 1, unit: 1, date: null}; }
    const entry = fxDaily.currencies[code];
    if (!entry) { return {ok: false, code: code, first: null}; }
    const found = Statso.core.lookupRateAt(entry.dates, entry.rates, isoDate);
    if (!found.ok) { return {ok: false, code: code, first: entry.dates[0]}; }
    return {ok: true, rate: found.rate, unit: entry.unit, date: found.date};
  }
  function rejectQuote(quoted) {
    const name = Statso.core.CURRENCY_NAMES[quoted.code] || quoted.code;
    fail('calc-fx-result', quoted.first
      ? 'אין שער ל' + name + ' לפני ' + Statso.core.formatIsoDateHe(quoted.first) + '.'
      : 'אין נתוני שער עבור ' + name + '.');
  }
  function recomputeFx() {
    const input = readFxInputs();
    if (!Number.isFinite(input.amount) || input.amount < 0) { fail('calc-fx-result', 'יש להזין סכום תקין שאינו שלילי.'); return; }
    if (!input.date) { fail('calc-fx-result', 'יש לבחור תאריך.'); return; }
    if (!fxDaily) { fail('calc-fx-result', fxPending ? 'טוען שערי חליפין…' : 'שערי החליפין אינם זמינים.'); return; }
    const from = quote(input.from, input.date);
    if (!from.ok) { rejectQuote(from); return; }
    const to = quote(input.to, input.date);
    if (!to.ok) { rejectQuote(to); return; }
    const result = Statso.core.convertAmount(input.amount, from, to);
    const used = [from.date, to.date].filter(Boolean).sort();
    document.getElementById('calc-error').textContent = '';
    document.getElementById('calc-fx-result').hidden = false;
    document.getElementById('calc-fx-converted').textContent = Statso.core.formatNumber(result.amount, 2);
    document.getElementById('calc-fx-unit').textContent = input.to === 'ILS' ? '₪' : input.to;
    document.getElementById('calc-fx-rate').textContent = Statso.core.formatRate(result.rate);
    document.getElementById('calc-fx-used-date').textContent = used.length
      ? 'לפי השער שפורסם ל־' + Statso.core.formatIsoDateHe(used[used.length - 1]) : '';
  }
  function recompute() { if (currentKind() === 'fx') { recomputeFx(); } else { recomputeIndex(); } }
  function ensureFxData() {
    if (fxDaily || fxPending) { return; }
    fxPending = true;
    fail('calc-fx-result', 'טוען שערי חליפין…');
    Statso.data.loadFxDaily().then(function (doc) {
      fxDaily = doc; fxPending = false;
      if (currentKind() === 'fx') { recompute(); }
    }).catch(function () {
      fxPending = false;
      if (currentKind() === 'fx') { fail('calc-fx-result', 'לא ניתן לטעון את שערי החליפין.'); }
    });
  }
  function showKind(kind) {
    const fx = kind === 'fx';
    document.querySelectorAll('.calc-index-only').forEach(function (el) { el.hidden = fx; });
    document.querySelectorAll('.calc-fx-only').forEach(function (el) { el.hidden = !fx; });
    document.getElementById('calc-result').hidden = fx;
    document.getElementById('calc-fx-result').hidden = !fx;
    document.getElementById('calc-amount-label').textContent = fx ? 'סכום' : 'סכום בשקלים';
    document.getElementById('calc-error').textContent = '';
    if (fx) { ensureFxData(); }
    recompute();
  }
  function initFx(summary) {
    populateCurrencySelects(summary);
    ['calc-fx-from', 'calc-fx-to', 'calc-fx-date'].forEach(function (id) { document.getElementById(id).addEventListener('input', recompute); });
  }
  function init(cpiDoc, map) {
    indexMap = map; firstMonth = cpiDoc.first_month; lastMonth = cpiDoc.last_month;
    populateMonthSelects(firstMonth, lastMonth);
    ['calc-amount', 'calc-base-year', 'calc-base-month', 'calc-target-year', 'calc-target-month'].forEach(function (id) { document.getElementById(id).addEventListener('input', recompute); });
    document.querySelectorAll('input[name="calc-mode"]').forEach(function (radio) { radio.addEventListener('change', recompute); });
    document.querySelectorAll('input[name="calc-kind"]').forEach(function (radio) {
      radio.addEventListener('change', function () { showKind(currentKind()); });
    });
    showKind(currentKind());
  }
  Statso.calculator = {populateMonthSelects: populateMonthSelects, populateCurrencySelects: populateCurrencySelects,
    readInputs: readInputs, readFxInputs: readFxInputs, recompute: recompute, showKind: showKind,
    init: init, initFx: initFx};
})(window);
