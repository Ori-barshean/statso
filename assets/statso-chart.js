(function (root) {
  'use strict';
  const Statso = root.Statso = root.Statso || {};
  let chartInstance = null;
  let observations = [];

  function populateYearSelects(years) {
    const start = document.getElementById('chart-start-year');
    const end = document.getElementById('chart-end-year');
    const options = years.map(function (year) { return '<option value="' + year + '">' + year + '</option>'; }).join('');
    start.innerHTML = options; end.innerHTML = options;
    const max = Math.max.apply(null, years); const min = Math.min.apply(null, years);
    end.value = String(max); start.value = String(Math.max(min, max - 9));
  }

  function sliceByYears(rows, startYear, endYear) { return rows.filter(function (row) { return row.year >= startYear && row.year <= endYear; }); }

  function buildConfig(rows) {
    return {type: 'line', data: {labels: rows.map(function (r) { return Statso.core.formatMonthHe(r.month); }), datasets: [{label: 'מדד משורשר', data: rows.map(function (r) { return r.chained_1951_09; }), borderColor: '#2563eb', backgroundColor: 'rgba(37,99,235,.1)', borderWidth: 2, pointRadius: 0, tension: 0, fill: true}]}, options: {responsive: true, maintainAspectRatio: false, locale: 'he-IL', interaction: {intersect: false, mode: 'index'}, scales: {x: {type: 'category', ticks: {autoSkip: true, maxTicksLimit: 12}}, y: {type: 'linear', beginAtZero: false, ticks: {callback: function (v) { return Statso.core.formatNumber(v, 0); }}}}, plugins: {legend: {rtl: true}, tooltip: {rtl: true, textDirection: 'rtl'}}}};
  }

  function render(rows) {
    if (chartInstance) { chartInstance.destroy(); }
    chartInstance = new root.Chart(document.getElementById('cpi-chart').getContext('2d'), buildConfig(rows));
  }

  function onRangeChange() {
    const start = Number(document.getElementById('chart-start-year').value);
    const end = Number(document.getElementById('chart-end-year').value);
    const error = document.getElementById('chart-range-error');
    if (start > end) { error.textContent = 'שנת ההתחלה חייבת להיות מוקדמת משנת הסיום.'; return; }
    error.textContent = ''; render(sliceByYears(observations, start, end));
  }

  function init(rows) {
    observations = rows;
    const years = Array.from(new Set(rows.map(function (row) { return row.year; })));
    populateYearSelects(years);
    document.getElementById('chart-start-year').addEventListener('change', onRangeChange);
    document.getElementById('chart-end-year').addEventListener('change', onRangeChange);
    onRangeChange();
  }

  function showUnavailable() { Statso.data.setState(document.getElementById('chart-section'), 'error', 'ספריית התרשים אינה זמינה. יתר הכלים ממשיכים לפעול.'); }
  Statso.chart = {populateYearSelects: populateYearSelects, sliceByYears: sliceByYears, buildConfig: buildConfig, render: render, onRangeChange: onRangeChange, init: init, showUnavailable: showUnavailable};
})(window);
