(function (root) {
  'use strict';
  const Statso = root.Statso = root.Statso || {};
  const CHIP_HEIGHT = 17;
  let chartInstance = null;
  // Months whose CPI reading is worth calling out on the trend line.
  const EVENTS = [
    {month: '2008-09', label: 'משבר הסאב־פריים'},
    {month: '2020-03', label: 'קורונה'},
    {month: '2023-10', label: '7 באוקטובר'},
    {month: '2025-06', label: 'מלחמת איראן הראשונה'},
    {month: '2026-02', label: 'מלחמת איראן השנייה'}
  ];

  function eventIndex(rows, month) {
    for (let i = 0; i < rows.length; i += 1) { if (rows[i].month === month) { return i; } }
    return -1;
  }

  function chip(ctx, x, y, width, height) {
    if (typeof ctx.roundRect === 'function') { ctx.beginPath(); ctx.roundRect(x, y, width, height, 4); ctx.fill(); }
    else { ctx.fillRect(x, y, width, height); }
  }

  const eventPlugin = {
    id: 'statsoEvents',
    afterDatasetsDraw: function (chart) {
      const rows = chart.$statsoRows || [];
      const area = chart.chartArea;
      const scale = chart.scales.x;
      const yScale = chart.scales.y;
      const values = (chart.data.datasets[0] || {}).data || [];
      const middle = (area.top + area.bottom) / 2;
      const ctx = chart.ctx;
      let topLane = 0;
      let bottomLane = 0;
      EVENTS.forEach(function (event) {
        const index = eventIndex(rows, event.month);
        if (index < 0) { return; }
        const x = scale.getPixelForValue(index);
        if (!isFinite(x) || x < area.left || x > area.right) { return; }
        ctx.save();
        ctx.strokeStyle = '#e8590c';
        ctx.lineWidth = 1.5;
        ctx.setLineDash([5, 3]);
        ctx.beginPath(); ctx.moveTo(x, area.top); ctx.lineTo(x, area.bottom); ctx.stroke();
        ctx.setLineDash([]);
        ctx.font = '600 11px -apple-system, Segoe UI, Roboto, sans-serif';
        const label = Statso.i18n.t(event.label);
        const width = ctx.measureText(label).width + 12;
        // The line sits high here, so drop the chip to the floor of the plot, and the other way round.
        const valueY = yScale ? yScale.getPixelForValue(values[index]) : NaN;
        const placeAtBottom = isFinite(valueY) && valueY < middle;
        const top = placeAtBottom
          ? area.bottom - 4 - CHIP_HEIGHT - (bottomLane % 2) * 21
          : area.top + 4 + (topLane % 2) * 21;
        ctx.fillStyle = '#e8590c';
        chip(ctx, Math.min(Math.max(x - width / 2, area.left), area.right - width), top, width, CHIP_HEIGHT);
        ctx.fillStyle = '#ffffff';
        ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        ctx.fillText(label, Math.min(Math.max(x, area.left + width / 2), area.right - width / 2), top + 9);
        ctx.restore();
        if (placeAtBottom) { bottomLane += 1; } else { topLane += 1; }
      });
    }
  };

  let observations = [];
  let hasData = false;
  let opened = false;
  let started = false;

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
    return {type: 'line', plugins: [eventPlugin], data: {labels: rows.map(function (r) { return Statso.core.formatMonthHe(r.month); }), datasets: [{label: Statso.i18n.t('מדד משורשר'), data: rows.map(function (r) { return r.chained_1951_09; }), borderColor: '#2563eb', backgroundColor: 'rgba(37,99,235,.1)', borderWidth: 2, pointRadius: 0, tension: 0, fill: true}]}, options: {responsive: true, maintainAspectRatio: false, locale: 'he-IL', interaction: {intersect: false, mode: 'index'}, scales: {x: {type: 'category', ticks: {autoSkip: true, maxTicksLimit: 12}}, y: {type: 'linear', beginAtZero: false, ticks: {callback: function (v) { return Statso.core.formatNumber(v, 0); }}}}, plugins: {legend: {rtl: true}, tooltip: {rtl: true, textDirection: 'rtl'}}}};
  }

  function render(rows) {
    if (chartInstance) { chartInstance.destroy(); }
    chartInstance = new root.Chart(document.getElementById('cpi-chart').getContext('2d'), buildConfig(rows));
    chartInstance.$statsoRows = rows;
    chartInstance.update('none');
  }

  function onRangeChange() {
    const start = Number(document.getElementById('chart-start-year').value);
    const end = Number(document.getElementById('chart-end-year').value);
    const error = document.getElementById('chart-range-error');
    if (start > end) { error.textContent = 'שנת ההתחלה חייבת להיות מוקדמת משנת הסיום.'; return; }
    error.textContent = ''; render(sliceByYears(observations, start, end));
  }

  function start() {
    if (started || !hasData || !opened) { return; }
    started = true;
    const years = Array.from(new Set(observations.map(function (row) { return row.year; })));
    populateYearSelects(years);
    document.getElementById('chart-start-year').addEventListener('change', onRangeChange);
    document.getElementById('chart-end-year').addEventListener('change', onRangeChange);
    onRangeChange();
  }

  function init(rows) { observations = rows; hasData = true; start(); }
  function activate() { opened = true; start(); }

  function showUnavailable() { Statso.data.setState(document.getElementById('chart-section'), 'error', 'ספריית התרשים אינה זמינה. יתר הכלים ממשיכים לפעול.'); }
  function resize() { if (chartInstance) { chartInstance.resize(); } }
  Statso.i18n.onChange(function () {
    if (!chartInstance || !document.getElementById('chart-start-year') || !document.getElementById('chart-end-year') || !document.getElementById('chart-range-error') || !document.getElementById('cpi-chart')) { return; }
    onRangeChange();
  });
  Statso.chart = {EVENTS: EVENTS, eventIndex: eventIndex, populateYearSelects: populateYearSelects, sliceByYears: sliceByYears, buildConfig: buildConfig, render: render, onRangeChange: onRangeChange, init: init, activate: activate, showUnavailable: showUnavailable, resize: resize};
})(window);
