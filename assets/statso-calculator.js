(function (root) {
  'use strict';
  const Statso = root.Statso = root.Statso || {};
  let indexMap, firstMonth, lastMonth;
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
  function readInputs() {
    return {amount: Number(document.getElementById('calc-amount').value), baseMonth: document.getElementById('calc-base-year').value + '-' + document.getElementById('calc-base-month').value, targetMonth: document.getElementById('calc-target-year').value + '-' + document.getElementById('calc-target-month').value, mode: document.querySelector('input[name="calc-mode"]:checked').value};
  }
  function reject(month, reason) {
    const detail = reason === 'missing' ? 'אינו קיים בסדרה' : 'מחוץ לטווח הנתונים';
    document.getElementById('calc-error').textContent = 'המדד לחודש ' + Statso.core.formatMonthHe(month) + ' ' + detail + '. הטווח הזמין הוא ' + Statso.core.formatMonthHe(firstMonth) + '–' + Statso.core.formatMonthHe(lastMonth) + '.';
    document.getElementById('calc-result').hidden = true;
  }
  function recompute() {
    const input = readInputs();
    if (!Number.isFinite(input.amount) || input.amount < 0) { document.getElementById('calc-error').textContent = 'יש להזין סכום תקין שאינו שלילי.'; document.getElementById('calc-result').hidden = true; return; }
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
  function init(cpiDoc, map) {
    indexMap = map; firstMonth = cpiDoc.first_month; lastMonth = cpiDoc.last_month;
    populateMonthSelects(firstMonth, lastMonth);
    ['calc-amount', 'calc-base-year', 'calc-base-month', 'calc-target-year', 'calc-target-month'].forEach(function (id) { document.getElementById(id).addEventListener('input', recompute); });
    document.querySelectorAll('input[name="calc-mode"]').forEach(function (radio) { radio.addEventListener('change', recompute); });
    recompute();
  }
  Statso.calculator = {populateMonthSelects: populateMonthSelects, readInputs: readInputs, recompute: recompute, init: init};
})(window);
