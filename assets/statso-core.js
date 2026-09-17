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

  const DEFAULT_CHAINED = 'chained_1951_09';
  function chainedOf(row, field) { return row[field || DEFAULT_CHAINED]; }

  function lookupChained(map, month, firstMonth, lastMonth, field) {
    if (monthToOrdinal(month) < monthToOrdinal(firstMonth) || monthToOrdinal(month) > monthToOrdinal(lastMonth)) {
      return {ok: false, value: null, reason: 'out_of_range'};
    }
    const row = map.get(month);
    return row ? {ok: true, value: chainedOf(row, field), reason: null} : {ok: false, value: null, reason: 'missing'};
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
  function readingInBase(map, baseMonth, month, field) {
    const base = map.get(baseMonth); const target = map.get(month);
    if (!base || !target) { return null; }
    return base.value * (chainedOf(target, field) / chainedOf(base, field));
  }

  function indexAmount(amount, baseChained, targetChained) {
    const indexed = amount * (targetChained / baseChained);
    return {indexed: indexed, difference: indexed - amount};
  }

  function changeOverMonths(map, lastMonth, back, field) {
    const current = map.get(lastMonth);
    const prior = map.get(shiftMonth(lastMonth, -back));
    return current && prior ? {ok: true, percent: (chainedOf(current, field) / chainedOf(prior, field) - 1) * 100} : {ok: false, percent: null};
  }

  function yearOverYear(map, lastMonth, field) { return changeOverMonths(map, lastMonth, 12, field); }
  function monthOverMonth(map, lastMonth, field) { return changeOverMonths(map, lastMonth, 1, field); }
  function primeRate(boiRate) { return boiRate + PRIME_SPREAD; }

  function latestObservation(cpiDoc, map) { return map.get(cpiDoc.last_month); }
  function formatNumber(x, digits) { return new Intl.NumberFormat('he-IL', {minimumFractionDigits: digits, maximumFractionDigits: digits}).format(x); }
  function formatPercent(x) { return formatNumber(x, 2) + '%'; }
  // Rates reach back to 1948, when a dollar cost 0.000025 lira. A fixed four
  // decimals would render those as 0.0000, so widen the window for small values.
  function formatRateSmart(x) {
    const size = Math.abs(x);
    let digits = 4;
    if (size > 0 && size < 1) { digits = Math.min(10, Math.max(4, 4 + Math.ceil(-Math.log10(size)))); }
    return new Intl.NumberFormat('he-IL', {minimumFractionDigits: 2, maximumFractionDigits: digits}).format(x);
  }

  function formatRate(x) { return new Intl.NumberFormat('he-IL', {minimumFractionDigits: 2, maximumFractionDigits: 4}).format(x); }
  function formatMonthHe(key) { const p = key.split('-'); return p[1] + '/' + p[0]; }
  function formatIsoDateHe(value) { const p = value.split('-'); return p[2] + '/' + p[1] + '/' + p[0]; }

  // Israeli statutory non-working days (Rosh Hashana, Yom Kippur, Sukkot I, Shmini Atzeret,
  // Pesach I, Pesach VII, Shavuot, Yom HaAtzmaut) through 2034, sourced from hebcal.com.
  // Extend this table as the range runs out; CBS does not publish the CPI on these dates.
  const CBS_PUBLICATION_HOLIDAYS = new Set([
    '2025-09-23', '2025-09-24', '2025-10-02', '2025-10-07', '2025-10-14',
    '2026-09-12', '2026-09-13', '2026-09-21', '2026-09-26', '2026-10-03',
    '2027-10-02', '2027-10-03', '2027-10-11', '2027-10-16', '2027-10-23',
    '2028-09-21', '2028-09-22', '2028-09-30', '2028-10-05', '2028-10-12',
    '2029-09-10', '2029-09-11', '2029-09-19', '2029-09-24', '2029-10-01',
    '2030-09-28', '2030-09-29', '2030-10-07', '2030-10-12', '2030-10-19',
    '2031-09-18', '2031-09-19', '2031-09-27', '2031-10-02', '2031-10-09',
    '2032-09-06', '2032-09-07', '2032-09-15', '2032-09-20', '2032-09-27',
    '2033-09-24', '2033-09-25', '2033-10-03', '2033-10-08', '2033-10-15',
    '2034-09-14', '2034-09-15', '2034-09-23', '2034-09-28', '2034-10-05',
    '2025-04-13', '2025-04-19', '2026-04-02', '2026-04-08', '2027-04-22', '2027-04-28',
    '2028-04-11', '2028-04-17', '2029-03-31', '2029-04-06', '2030-04-18', '2030-04-24',
    '2031-04-08', '2031-04-14', '2032-03-27', '2032-04-02', '2033-04-14', '2033-04-20',
    '2034-04-04', '2034-04-10',
    '2025-06-02', '2026-05-22', '2027-06-11', '2028-05-31', '2029-05-20',
    '2030-06-07', '2031-05-28', '2032-05-16', '2033-06-03', '2034-05-24',
    '2025-05-01', '2026-04-22', '2027-05-12', '2028-05-02', '2029-04-19',
    '2030-05-08', '2031-04-29', '2032-04-15', '2033-05-04', '2034-04-25'
  ]);
  // CBS publishes the CPI for a month around the 15th of the month after next; a date that
  // falls on a Friday, Saturday or statutory holiday is postponed to the next weekday.
  function nextCpiPublicationDate(lastMonth) {
    const publishMonth = shiftMonth(lastMonth, 2).split('-').map(Number);
    const date = new Date(Date.UTC(publishMonth[0], publishMonth[1] - 1, 15));
    function iso(d) { return d.toISOString().slice(0, 10); }
    while (true) {
      const weekday = date.getUTCDay();
      if (weekday !== 5 && weekday !== 6 && !CBS_PUBLICATION_HOLIDAYS.has(iso(date))) { break; }
      date.setUTCDate(date.getUTCDate() + 1);
    }
    return iso(date);
  }

  const ESCAPE_MAP = {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'};
  // Safe for HTML text content and for double-quoted HTML attribute values —
  // every call site that uses this only needs those two contexts.
  function escapeHtml(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (ch) { return ESCAPE_MAP[ch]; });
  }

  Statso.core = {monthToOrdinal: monthToOrdinal, ordinalToMonth: ordinalToMonth, shiftMonth: shiftMonth,
    buildIndexMap: buildIndexMap, resolveIndexMonth: resolveIndexMonth, lookupChained: lookupChained,
    indexAmount: indexAmount, readingInBase: readingInBase, lookupRateAt: lookupRateAt, convertAmount: convertAmount,
    yearOverYear: yearOverYear, monthOverMonth: monthOverMonth,
    primeRate: primeRate, PRIME_SPREAD: PRIME_SPREAD, formatRate: formatRate,
    formatRateSmart: formatRateSmart,
    CURRENCY_NAMES: CURRENCY_NAMES, latestObservation: latestObservation,
    formatNumber: formatNumber, formatPercent: formatPercent, formatMonthHe: formatMonthHe,
    formatIsoDateHe: formatIsoDateHe, nextCpiPublicationDate: nextCpiPublicationDate, escapeHtml: escapeHtml};
})(window);
