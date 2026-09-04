(function (root) {
  'use strict';
  const Statso = root.Statso = root.Statso || {};
  function failKpi(sectionId, valueId, errorId, message) {
    document.getElementById(valueId).textContent = '—';
    document.getElementById(errorId).textContent = message;
    Statso.data.setState(document.getElementById(sectionId), 'error', message);
  }
  function showCpi(doc) {
    const map = Statso.core.buildIndexMap(doc.observations); const latest = Statso.core.latestObservation(doc, map); const yoy = Statso.core.yearOverYear(map, doc.last_month);
    if (!latest) { throw new Error('המדד העדכני חסר'); }
    document.getElementById('kpi-cpi-value').textContent = Statso.core.formatNumber(latest.value, 1);
    document.getElementById('kpi-cpi-month').textContent = Statso.core.formatMonthHe(latest.month);
    Statso.data.setState(document.getElementById('cpi-kpi'), 'ready');
    if (yoy.ok) { document.getElementById('kpi-yoy').textContent = Statso.core.formatPercent(yoy.percent); Statso.data.setState(document.getElementById('yoy-kpi'), 'ready'); }
    else { failKpi('yoy-kpi', 'kpi-yoy', 'kpi-yoy-error', 'לא ניתן לחשב שינוי שנתי'); }
    ['table-section', 'calculator-section'].forEach(function (id) { Statso.data.setState(document.getElementById(id), 'ready'); });
    Statso.table.init(doc.observations); Statso.calculator.init(doc, map);
    if (typeof root.Chart === 'function') { Statso.chart.init(doc.observations); Statso.data.setState(document.getElementById('chart-section'), 'ready'); }
    else { Statso.chart.showUnavailable(); }
  }
  function showBoi(doc) {
    if (typeof doc.current_rate !== 'number' || !isFinite(doc.current_rate)) { throw new Error('הריבית הנוכחית חסרה'); }
    document.getElementById('kpi-boi-rate').textContent = Statso.core.formatPercent(doc.current_rate);
    Statso.data.setState(document.getElementById('boi-kpi'), 'ready');
  }
  function showNext(doc) {
    if (!doc.next_decision_date) { throw new Error('מועד ההחלטה הבאה אינו זמין'); }
    document.getElementById('kpi-next-decision').textContent = Statso.core.formatIsoDateHe(doc.next_decision_date); Statso.data.setState(document.getElementById('next-kpi'), 'ready');
  }
  function init() {
    Statso.data.loadAll().then(function (results) {
      if (results[0].status === 'fulfilled') { try { showCpi(results[0].value); } catch (error) { failKpi('cpi-kpi', 'kpi-cpi-value', 'kpi-cpi-error', error.message); failKpi('yoy-kpi', 'kpi-yoy', 'kpi-yoy-error', error.message); Statso.data.setState(document.getElementById('chart-section'), 'error', error.message); Statso.data.setState(document.getElementById('table-section'), 'error', error.message); Statso.data.setState(document.getElementById('calculator-section'), 'error', error.message); } }
      else { const msg = results[0].reason.message; failKpi('cpi-kpi', 'kpi-cpi-value', 'kpi-cpi-error', msg); failKpi('yoy-kpi', 'kpi-yoy', 'kpi-yoy-error', msg); Statso.data.setState(document.getElementById('chart-section'), 'error', msg); Statso.data.setState(document.getElementById('table-section'), 'error', msg); Statso.data.setState(document.getElementById('calculator-section'), 'error', msg); }
      if (results[1].status === 'fulfilled') { try { showBoi(results[1].value); } catch (error) { failKpi('boi-kpi', 'kpi-boi-rate', 'kpi-boi-error', error.message); } } else { failKpi('boi-kpi', 'kpi-boi-rate', 'kpi-boi-error', results[1].reason.message); }
      if (results[2].status === 'fulfilled') { try { showNext(results[2].value); } catch (error) { failKpi('next-kpi', 'kpi-next-decision', 'kpi-next-error', error.message); } } else { failKpi('next-kpi', 'kpi-next-decision', 'kpi-next-error', results[2].reason.message); }
    });
  }
  document.addEventListener('DOMContentLoaded', init);
  Statso.app = {init: init};
})(window);
