(function (root) {
  'use strict';
  const Statso = root.Statso = root.Statso || {};

  function monthToOrdinal(key) {
    const parts = key.split('-').map(Number);
    return parts[0] * 12 + parts[1] - 1;
  }

  function ordinalToMonth(n) {
    const year = Math.floor(n / 12);
    const month = n - year * 12 + 1;
    return String(year).padStart(4, '0') + '-' + String(month).padStart(2, '0');
  }

  function shiftMonth(key, delta) { return ordinalToMonth(monthToOrdinal(key) + delta); }
  function buildIndexMap(observations) { return new Map(observations.map(function (row) { return [row.month, row]; })); }
  function resolveIndexMonth(contractMonth, mode) { return mode === 'known' ? shiftMonth(contractMonth, -1) : contractMonth; }

  function lookupChained(map, month, firstMonth, lastMonth) {
    if (monthToOrdinal(month) < monthToOrdinal(firstMonth) || monthToOrdinal(month) > monthToOrdinal(lastMonth)) {
      return {ok: false, value: null, reason: 'out_of_range'};
    }
    const row = map.get(month);
    return row ? {ok: true, value: row.chained_1951_09, reason: null} : {ok: false, value: null, reason: 'missing'};
  }

  function indexAmount(amount, baseChained, targetChained) {
    const indexed = amount * (targetChained / baseChained);
    return {indexed: indexed, difference: indexed - amount};
  }

  function yearOverYear(map, lastMonth) {
    const current = map.get(lastMonth);
    const prior = map.get(shiftMonth(lastMonth, -12));
    return current && prior ? {ok: true, percent: (current.chained_1951_09 / prior.chained_1951_09 - 1) * 100} : {ok: false, percent: null};
  }

  function latestObservation(cpiDoc, map) { return map.get(cpiDoc.last_month); }
  function formatNumber(x, digits) { return new Intl.NumberFormat('he-IL', {minimumFractionDigits: digits, maximumFractionDigits: digits}).format(x); }
  function formatPercent(x) { return formatNumber(x, 2) + '%'; }
  function formatMonthHe(key) { const p = key.split('-'); return p[1] + '/' + p[0]; }
  function formatIsoDateHe(value) { const p = value.split('-'); return p[2] + '/' + p[1] + '/' + p[0]; }

  Statso.core = {monthToOrdinal: monthToOrdinal, ordinalToMonth: ordinalToMonth, shiftMonth: shiftMonth,
    buildIndexMap: buildIndexMap, resolveIndexMonth: resolveIndexMonth, lookupChained: lookupChained,
    indexAmount: indexAmount, yearOverYear: yearOverYear, latestObservation: latestObservation,
    formatNumber: formatNumber, formatPercent: formatPercent, formatMonthHe: formatMonthHe,
    formatIsoDateHe: formatIsoDateHe};
})(window);
