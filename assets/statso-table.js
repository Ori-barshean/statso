(function (root) {
  'use strict';
  const Statso = root.Statso = root.Statso || {};
  let allRows = [];
  let timer = null;
  function normalize(s) { return String(s).normalize('NFC').trim().replace(/\s+/g, ' ').toLowerCase(); }
  function buildRows(observations) {
    return observations.slice().reverse().map(function (row) {
      const joined = row.month + ' ' + String(row.value) + ' ' + Statso.core.formatNumber(row.value, 1) + ' ' + row.base_desc + ' ' + String(row.chained_1951_09) + ' ' + Statso.core.formatNumber(row.chained_1951_09, 4);
      return {month: row.month, value: row.value, baseDesc: row.base_desc, chained: row.chained_1951_09, haystack: normalize(joined)};
    });
  }
  function filterRows(rows, query) { const q = normalize(query); return q ? rows.filter(function (row) { return row.haystack.indexOf(q) !== -1; }) : rows; }
  function escapeText(value) { return String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
  function render(rows) {
    document.getElementById('cpi-table-body').innerHTML = rows.map(function (row) {
      return '<tr><td class="numeric">' + Statso.core.formatMonthHe(row.month) + '</td><td class="numeric">' + Statso.core.formatNumber(row.value, 1) + '</td><td>' + escapeText(row.baseDesc) + '</td><td class="numeric">' + Statso.core.formatNumber(row.chained, 4) + '</td></tr>';
    }).join('');
    document.getElementById('cpi-table-count').textContent = Statso.core.formatNumber(rows.length, 0);
  }
  function attach() {
    document.getElementById('cpi-search').addEventListener('input', function (event) {
      root.clearTimeout(timer); timer = root.setTimeout(function () { render(filterRows(allRows, event.target.value)); }, 120);
    });
  }
  function init(observations) { allRows = buildRows(observations); render(allRows); attach(); }
  Statso.table = {normalize: normalize, buildRows: buildRows, filterRows: filterRows, render: render, attach: attach, init: init};
})(window);
