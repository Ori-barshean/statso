(function (root) {
  'use strict';
  const Statso = root.Statso = root.Statso || {};
  const PRIME_SPREAD = 1.5;
  const CURRENCY_NAMES = {USD: 'דולר ארה״ב', EUR: 'אירו', GBP: 'ליש״ט', CHF: 'פרנק שווייצרי',
    JPY: 'ין יפני', CAD: 'דולר קנדי', AUD: 'דולר אוסטרלי', DKK: 'כתר דני',
    NOK: 'כתר נורווגי', SEK: 'כתר שוודי', ILS: 'שקל חדש'};

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

  function lookupRateAt(dates, rates, isoDate) {
    if (!dates.length || isoDate < dates[0]) { return {ok: false, rate: null, date: null}; }
    let low = 0; let high = dates.length - 1; let found = 0;
    while (low <= high) {
      const mid = (low + high) >> 1;
      if (dates[mid] <= isoDate) { found = mid; low = mid + 1; } else { high = mid - 1; }
    }
    return {ok: true, rate: rates[found], date: dates[found]};
  }

  function convertAmount(amount, from, to) {
    const rate = (from.rate / from.unit) / (to.rate / to.unit);
    return {amount: amount * rate, rate: rate};
  }

  // The CBS rebases the index every few years, so two published readings are only
  // comparable once both are expressed in the same base. coef=true gives us the
  // chained series precisely so this is a lookup: restate `month` in the base that
  // was in force at `baseMonth`, which is the number a contract actually cites.
  function readingInBase(map, baseMonth, month) {
    const base = map.get(baseMonth); const target = map.get(month);
    if (!base || !target) { return null; }
    return base.value * (target.chained_1951_09 / base.chained_1951_09);
  }

  function indexAmount(amount, baseChained, targetChained) {
    const indexed = amount * (targetChained / baseChained);
    return {indexed: indexed, difference: indexed - amount};
  }

  function changeOverMonths(map, lastMonth, back) {
    const current = map.get(lastMonth);
    const prior = map.get(shiftMonth(lastMonth, -back));
    return current && prior ? {ok: true, percent: (current.chained_1951_09 / prior.chained_1951_09 - 1) * 100} : {ok: false, percent: null};
  }

  function yearOverYear(map, lastMonth) { return changeOverMonths(map, lastMonth, 12); }
  function monthOverMonth(map, lastMonth) { return changeOverMonths(map, lastMonth, 1); }
  function primeRate(boiRate) { return boiRate + PRIME_SPREAD; }

  function latestObservation(cpiDoc, map) { return map.get(cpiDoc.last_month); }
  function formatNumber(x, digits) { return new Intl.NumberFormat('he-IL', {minimumFractionDigits: digits, maximumFractionDigits: digits}).format(x); }
  function formatPercent(x) { return formatNumber(x, 2) + '%'; }
  function formatRate(x) { return new Intl.NumberFormat('he-IL', {minimumFractionDigits: 2, maximumFractionDigits: 4}).format(x); }
  function formatMonthHe(key) { const p = key.split('-'); return p[1] + '/' + p[0]; }
  function formatIsoDateHe(value) { const p = value.split('-'); return p[2] + '/' + p[1] + '/' + p[0]; }

  Statso.core = {monthToOrdinal: monthToOrdinal, ordinalToMonth: ordinalToMonth, shiftMonth: shiftMonth,
    buildIndexMap: buildIndexMap, resolveIndexMonth: resolveIndexMonth, lookupChained: lookupChained,
    indexAmount: indexAmount, readingInBase: readingInBase, lookupRateAt: lookupRateAt, convertAmount: convertAmount,
    yearOverYear: yearOverYear, monthOverMonth: monthOverMonth,
    primeRate: primeRate, PRIME_SPREAD: PRIME_SPREAD, formatRate: formatRate,
    CURRENCY_NAMES: CURRENCY_NAMES, latestObservation: latestObservation,
    formatNumber: formatNumber, formatPercent: formatPercent, formatMonthHe: formatMonthHe,
    formatIsoDateHe: formatIsoDateHe};
})(window);
