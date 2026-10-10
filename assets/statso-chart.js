(function (root) {
  'use strict';
  const Statso = root.Statso = root.Statso || {};
  const CHIP_HEIGHT = 17;
  const SLIDER_ID = 'chart-month';
  const NO_MONTH = 'לא נבחר חודש.';
  const SUMMARY = {intro: 'סיכום הנתונים בטווח שנבחר:', left: 'ציר שמאלי', right: 'ציר ימני', first: 'ערך ראשון', last: 'ערך אחרון', min: 'ערך נמוך ביותר', max: 'ערך גבוה ביותר', empty: 'אין נתונים בטווח שנבחר'};
  // White 11px labels on the chips need 4.5:1; the earlier orange (#e8590c) only reached 3.58:1. Canvas text is
  // invisible to axe, so the test suite computes this ratio itself.
  const EVENT_COLOR = '#c2410c';
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
        ctx.strokeStyle = EVENT_COLOR;
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
        ctx.fillStyle = EVENT_COLOR;
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
  const SERIES_INPUT_IDS = ['chart-series-cpi', 'chart-series-construction'];
  const seriesVisible = [true, true];
  let selectedIndex = null;
  let announceTimer = null;
  let hasData = false;
  let opened = false;
  let started = false;

  function nextIndex(current, key, length) {
    let step;
    switch (key) {
      case 'ArrowRight': step = 1; break;
      case 'ArrowLeft': step = -1; break;
      case 'PageDown': step = 12; break;
      case 'PageUp': step = -12; break;
      case 'Home': case 'End': step = 0; break;
      case 'Escape': return null;
      default: return undefined;
    }
    if (!(length > 0)) { return null; }
    const last = length - 1;
    if (key === 'Home') { return 0; }
    if (key === 'End' || current === null || current === undefined) { return last; }
    return Math.min(last, Math.max(0, Math.min(current, last) + step));
  }

  function announcementText(rows, series, index) {
    const row = rows[index];
    if (!row) { return ''; }
    const parts = [];
    series.forEach(function (one) {
      const value = one.data[index];
      if (!one.visible || value === null || value === undefined || !Number.isFinite(value)) { return; }
      parts.push(one.label + ' ' + Statso.core.formatNumber(value, 1));
    });
    let text = Statso.core.formatMonthHe(row.month);
    if (parts.length) { text += ': ' + parts.join('; '); }
    const event = EVENTS.find(function (one) { return one.month === row.month; });
    if (event) { text += ' — ' + Statso.i18n.t(event.label); }
    return text;
  }

  function sliderState(rows, series, index, neutralText) {
    const max = Math.max(rows.length - 1, 0);
    return {min: 0, max: max, value: index === null ? max : index,
      valuetext: index === null ? neutralText : announcementText(rows, series, index), disabled: !rows.length};
  }

  function sliderKeyIsInert(key, value, max) {
    switch (key) {
      case 'ArrowRight': case 'ArrowUp': case 'PageUp': case 'End': return value >= max;
      case 'ArrowLeft': case 'ArrowDown': case 'PageDown': case 'Home': return value <= 0;
      default: return false;
    }
  }

  function seriesExtremes(rows, data) {
    let result = null;
    rows.forEach(function (row, index) {
      const value = data[index];
      if (value === null || value === undefined || !Number.isFinite(value)) { return; }
      const point = {index: index, month: row.month, value: value};
      if (!result) { result = {first: point, last: point, min: point, max: point}; }
      result.last = point;
      if (value < result.min.value) { result.min = point; }
      if (value > result.max.value) { result.max = point; }
    });
    return result;
  }

  function summaryText(rows, series) {
    if (!rows.length || !series.length) { return ''; }
    const t = Statso.i18n.t;
    const axes = series.map(function (s) { return t(s.axis === 'right' ? SUMMARY.right : SUMMARY.left) + ' — ' + s.label; }).join('; ');
    const parts = series.map(function (s) {
      const extremes = seriesExtremes(rows, s.data);
      if (!extremes) { return s.label + ': ' + t(SUMMARY.empty) + '.'; }
      return s.label + ': ' + ['first', 'last', 'min', 'max'].map(function (key) {
        const p = extremes[key];
        return t(SUMMARY[key]) + ' ' + Statso.core.formatNumber(p.value, 1) + ' (' + Statso.core.formatMonthHe(p.month) + ')';
      }).join('; ') + '.';
    });
    return t(SUMMARY.intro) + ' ' + axes + '. ' + parts.join(' ');
  }

  // The series names are read in the language of the moment of the key press, not the one the chart
  // was last built in: with an invalid year range the chart is not rebuilt on a language switch.
  const SERIES_LABELS = ['מדד המחירים לצרכן', 'מדד תשומות הבנייה למגורים'];
  function seriesOf(chart) {
    return chart.data.datasets.map(function (d, i) {
      return {label: SERIES_LABELS[i] ? Statso.i18n.t(SERIES_LABELS[i]) : d.label, data: d.data, visible: chart.isDatasetVisible(i), axis: d.yAxisID === 'y1' ? 'right' : 'left'};
    });
  }

  function syncSlider() {
    const slider = document.getElementById(SLIDER_ID);
    if (!slider) { return; }
    const rows = chartInstance ? chartInstance.$statsoRows || [] : [];
    const state = sliderState(rows, chartInstance ? seriesOf(chartInstance) : [], selectedIndex, Statso.i18n.t(NO_MONTH));
    slider.min = String(state.min);
    slider.max = String(state.max);
    slider.value = String(state.value);
    slider.disabled = state.disabled;
    slider.setAttribute('aria-valuetext', state.valuetext);
    const wrapper = slider.closest && slider.closest('.chart-month');
    if (wrapper) { wrapper.hidden = state.disabled; }
  }

  function selectFromSlider() {
    const slider = document.getElementById(SLIDER_ID);
    const rows = chartInstance && chartInstance.$statsoRows;
    if (!slider || !rows || !rows.length) { return; }
    const index = Math.min(rows.length - 1, Math.max(0, Math.round(Number(slider.value))));
    root.clearTimeout(announceTimer);
    applySelection(index, false);
  }

  function onSliderKey(e) {
    if (e.altKey || e.ctrlKey || e.metaKey) { return; }
    const slider = document.getElementById(SLIDER_ID);
    if (!slider) { return; }
    if (e.key === 'Escape') {
      if (selectedIndex !== null) { e.preventDefault(); clearSelection(); }
    } else if (sliderKeyIsInert(e.key, Number(slider.value), Number(slider.max))) {
      e.preventDefault(); selectFromSlider();
    }
  }

  function onSliderClick() {
    if (selectedIndex === null) { selectFromSlider(); }
  }

  function describeData() {
    const holder = document.getElementById('chart-alt-summary');
    if (!holder) { return; }
    const rows = chartInstance ? chartInstance.$statsoRows || [] : [];
    const text = rows.length ? summaryText(rows, seriesOf(chartInstance)) : '';
    holder.textContent = text;
    holder.hidden = !text;
  }

  function activeAt(chart, index) {
    const active = [];
    chart.data.datasets.forEach(function (d, i) {
      const value = d.data[index];
      if (chart.isDatasetVisible(i) && value !== null && value !== undefined && Number.isFinite(value)) {
        active.push({datasetIndex: i, index: index});
      }
    });
    return active;
  }

  function scheduleAnnouncement(text) {
    root.clearTimeout(announceTimer);
    const live = document.getElementById('chart-live');
    if (!live) { return; }
    announceTimer = root.setTimeout(function () { live.textContent = text; }, 250);
  }

  function applySelection(index, announce) {
    selectedIndex = index;
    const chart = chartInstance;
    const active = activeAt(chart, index);
    const anchor = active.length ? chart.getDatasetMeta(active[0].datasetIndex).data[index] : null;
    chart.setActiveElements(active);
    chart.tooltip.setActiveElements(active, anchor ? {x: anchor.x, y: anchor.y} : {x: 0, y: 0});
    chart.update('none');
    syncSlider();
    if (announce) { scheduleAnnouncement(announcementText(chart.$statsoRows || [], seriesOf(chart), index)); }
  }

  function resetSelection() {
    selectedIndex = null;
    root.clearTimeout(announceTimer);
    const live = document.getElementById('chart-live');
    if (live) { live.textContent = ''; }
  }

  function clearSelection() {
    resetSelection();
    if (chartInstance) {
      chartInstance.setActiveElements([]);
      chartInstance.tooltip.setActiveElements([], {x: 0, y: 0});
      chartInstance.update('none');
    }
    syncSlider();
  }

  function onChartKey(event) {
    if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) { return; }
    const rows = chartInstance && chartInstance.$statsoRows;
    if (!rows) { return; }
    const next = nextIndex(selectedIndex, event.key, rows.length);
    if (next === undefined) { return; }
    if (event.key === 'Escape' && selectedIndex === null) { return; }
    event.preventDefault();
    // At an edge nothing moves and nothing is spoken again, but a tooltip that the mouse leaving the
    // canvas has just removed comes back.
    if (next === selectedIndex) { applySelection(next, false); return; }
    if (next === null) { clearSelection(); } else { applySelection(next, true); }
  }

  function setSeriesVisible(index, visible) {
    seriesVisible[index] = visible;
    const input = document.getElementById(SERIES_INPUT_IDS[index]);
    if (input) { input.checked = visible; }
    const chart = chartInstance;
    if (!chart || index >= chart.data.datasets.length) { syncSlider(); return; }
    chart.setDatasetVisibility(index, visible);
    root.clearTimeout(announceTimer);   // a queued announcement may still name the series that was just hidden
    if (selectedIndex === null) { chart.update(); }
    else { chart.update('none'); applySelection(selectedIndex, false); }
    syncSlider();
  }

  function onLegendClick(e, item) {
    setSeriesVisible(item.datasetIndex, !seriesVisible[item.datasetIndex]);
  }

  function syncSeriesControls(count) {
    SERIES_INPUT_IDS.forEach(function (id, i) {
      const input = document.getElementById(id);
      if (!input) { return; }
      input.checked = seriesVisible[i];
      input.closest('label').hidden = i >= count;
    });
  }

  function wireChartControls() {
    const slider = document.getElementById(SLIDER_ID);
    if (slider) {
      slider.addEventListener('input', selectFromSlider);
      slider.addEventListener('keydown', onSliderKey);
      slider.addEventListener('click', onSliderClick);
    }
    document.getElementById('cpi-chart').addEventListener('keydown', onChartKey);
    SERIES_INPUT_IDS.forEach(function (id, i) {
      const input = document.getElementById(id);
      if (input) { input.addEventListener('change', function () { setSeriesVisible(i, input.checked); }); }
    });
  }

  function populateYearSelects(years) {
    const start = document.getElementById('chart-start-year');
    const end = document.getElementById('chart-end-year');
    const options = years.map(function (year) { return '<option value="' + year + '">' + year + '</option>'; }).join('');
    start.innerHTML = options; end.innerHTML = options;
    const max = Math.max.apply(null, years); const min = Math.min.apply(null, years);
    end.value = String(max); start.value = String(Math.max(min, max - 9));
  }

  function sliceByYears(rows, startYear, endYear) { return rows.filter(function (row) { return row.year >= startYear && row.year <= endYear; }); }

  function buildConfig(cpiRows, constructionRows) {
    const hasConstruction = !!(constructionRows && constructionRows.length);
    const constructionByMonth = new Map((constructionRows || []).map(function (r) { return [r.month, r.chained_1950_07]; }));
    const datasets = [{label: Statso.i18n.t('מדד המחירים לצרכן'), data: cpiRows.map(function (r) { return r.chained_1951_09; }), borderColor: '#2563eb', backgroundColor: 'rgba(37,99,235,.1)', borderWidth: 2, pointRadius: 0, tension: 0, fill: true, yAxisID: 'y', hidden: !seriesVisible[0]}];
    if (hasConstruction) {
      datasets.push({label: Statso.i18n.t('מדד תשומות הבנייה למגורים'), data: cpiRows.map(function (r) { return constructionByMonth.has(r.month) ? constructionByMonth.get(r.month) : null; }), borderColor: '#16a34a', borderDash: [7, 4], backgroundColor: 'rgba(22,163,74,.1)', borderWidth: 2, pointRadius: 0, tension: 0, fill: false, spanGaps: false, yAxisID: 'y1', hidden: !seriesVisible[1]});
    }
    const config = {type: 'line', plugins: [eventPlugin], data: {labels: cpiRows.map(function (r) { return Statso.core.formatMonthHe(r.month); }), datasets: datasets}, options: {responsive: true, maintainAspectRatio: false, locale: 'he-IL', interaction: {intersect: false, mode: 'index'}, scales: {x: {type: 'category', ticks: {autoSkip: true, maxTicksLimit: 12}}, y: {type: 'linear', display: 'auto', position: 'left', beginAtZero: false, ticks: {callback: function (v) { return Statso.core.formatNumber(v, 0); }}}, y1: {type: 'linear', position: 'right', beginAtZero: false, display: hasConstruction ? 'auto' : false, grid: {drawOnChartArea: false}, ticks: {callback: function (v) { return Statso.core.formatNumber(v, 0); }}}}, plugins: {legend: {rtl: true, display: true, onClick: onLegendClick}, tooltip: {rtl: true, textDirection: 'rtl'}}}};
    // Chart.js draws the lines in over a second by default; a visitor who asked their OS for less motion gets the finished chart at once.
    if (root.matchMedia && root.matchMedia('(prefers-reduced-motion: reduce)').matches) { config.options.animation = false; }
    return config;
  }

  // The event markers exist only as canvas drawing, so a screen reader would
  // never learn they are there. Name the ones the current range actually shows,
  // from the same EVENTS list and the same test the drawing code uses.
  function describeEvents(rows) {
    const holder = document.getElementById('chart-alt-events');
    if (!holder) { return; }
    holder.textContent = '';
    const shown = EVENTS.filter(function (event) { return eventIndex(rows, event.month) >= 0; });
    holder.hidden = !shown.length;
    if (!shown.length) { return; }
    holder.appendChild(document.createTextNode('אירועים המסומנים בתרשים: '));
    shown.forEach(function (event, i) {
      if (i) { holder.appendChild(document.createTextNode('; ')); }
      const date = document.createElement('span');
      date.setAttribute('dir', 'ltr');
      date.textContent = Statso.core.formatMonthHe(event.month);
      holder.appendChild(date);
      holder.appendChild(document.createTextNode(' \u2014 '));
      holder.appendChild(document.createTextNode(event.label));
    });
    holder.appendChild(document.createTextNode('.'));
  }

  function render(cpiRows, constructionRows) {
    describeEvents(cpiRows);
    resetSelection();
    if (chartInstance) { chartInstance.destroy(); }
    const config = buildConfig(cpiRows, constructionRows);
    chartInstance = new root.Chart(document.getElementById('cpi-chart').getContext('2d'), config);
    chartInstance.$statsoRows = cpiRows;
    syncSeriesControls(config.data.datasets.length);
    describeData();
    syncSlider();
    chartInstance.update('none');
  }

  function onRangeChange() {
    const start = Number(document.getElementById('chart-start-year').value);
    const end = Number(document.getElementById('chart-end-year').value);
    const error = document.getElementById('chart-range-error');
    if (start > end) { error.textContent = 'שנת ההתחלה חייבת להיות מוקדמת משנת הסיום.'; return; }
    error.textContent = ''; render(sliceByYears(observations, start, end), sliceByYears(constructionObservations, start, end));
  }

  function start() {
    if (started || !hasData || !opened) { return; }
    started = true;
    const years = Array.from(new Set(observations.map(function (row) { return row.year; })));
    populateYearSelects(years);
    document.getElementById('chart-start-year').addEventListener('change', onRangeChange);
    document.getElementById('chart-end-year').addEventListener('change', onRangeChange);
    wireChartControls();
    onRangeChange();
  }

  let constructionObservations = [];
  function init(rows, constructionRows) { observations = rows; constructionObservations = constructionRows || []; hasData = true; start(); }
  function activate() { opened = true; start(); }

  function showUnavailable() { Statso.data.setState(document.getElementById('chart-section'), 'error', 'ספריית התרשים אינה זמינה. יתר הכלים ממשיכים לפעול.'); }
  function resize() { if (chartInstance) { chartInstance.resize(); } }
  Statso.i18n.onChange(function () {
    if (!chartInstance || !document.getElementById('chart-start-year') || !document.getElementById('chart-end-year') || !document.getElementById('chart-range-error') || !document.getElementById('cpi-chart')) { return; }
    onRangeChange();
    describeData();
    syncSlider();
  });
  Statso.chart = {EVENTS: EVENTS, eventIndex: eventIndex, populateYearSelects: populateYearSelects, sliceByYears: sliceByYears, buildConfig: buildConfig, describeEvents: describeEvents, render: render, onRangeChange: onRangeChange, init: init, activate: activate, showUnavailable: showUnavailable, resize: resize, nextIndex: nextIndex, announcementText: announcementText, sliderState: sliderState, sliderKeyIsInert: sliderKeyIsInert, seriesExtremes: seriesExtremes, summaryText: summaryText};
})(window);
