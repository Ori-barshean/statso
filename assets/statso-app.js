(function (root) {
  'use strict';
  const Statso = root.Statso = root.Statso || {};
  function failCard(sectionId, errorId, message, valueIds) {
    valueIds.forEach(function (id) { document.getElementById(id).textContent = '—'; });
    document.getElementById(errorId).textContent = message;
    Statso.data.setState(document.getElementById(sectionId), 'error', message);
  }
  function failCpi(message) {
    failCard('cpi-kpi', 'kpi-cpi-error', message, ['kpi-cpi-yoy', 'kpi-cpi-mom']);
    Statso.data.setState(document.getElementById('chart-section'), 'error', message);
    Statso.data.setState(document.getElementById('calculator-section'), 'error', message);
  }
  function showCpi(doc) {
    const map = Statso.core.buildIndexMap(doc.observations); const latest = Statso.core.latestObservation(doc, map);
    if (!latest) { throw new Error('המדד העדכני חסר'); }
    const yoy = Statso.core.yearOverYear(map, doc.last_month); const mom = Statso.core.monthOverMonth(map, doc.last_month);
    if (!yoy.ok || !mom.ok) { throw new Error('לא ניתן לחשב את השינוי במדד'); }
    document.getElementById('kpi-cpi-yoy').textContent = Statso.core.formatPercent(yoy.percent);
    document.getElementById('kpi-cpi-yoy-range').textContent = Statso.core.formatMonthHe(Statso.core.shiftMonth(doc.last_month, -12)) + '–' + Statso.core.formatMonthHe(doc.last_month);
    document.getElementById('kpi-cpi-mom').textContent = Statso.core.formatPercent(mom.percent);
    document.getElementById('kpi-cpi-mom-month').textContent = Statso.core.formatMonthHe(doc.last_month);
    Statso.data.setState(document.getElementById('cpi-kpi'), 'ready');
    Statso.data.setState(document.getElementById('calculator-section'), 'ready');
    Statso.calculator.init(doc, map);
    if (Statso.tools) { Statso.tools.init(doc, map); }
    if (typeof root.Chart === 'function') { Statso.chart.init(doc.observations); Statso.data.setState(document.getElementById('chart-section'), 'ready'); }
    else { Statso.chart.showUnavailable(); }
  }
  function showBoi(doc) {
    if (typeof doc.current_rate !== 'number' || !isFinite(doc.current_rate)) { throw new Error('הריבית הנוכחית חסרה'); }
    document.getElementById('kpi-boi-rate').textContent = Statso.core.formatPercent(doc.current_rate);
    document.getElementById('kpi-boi-prime').textContent = Statso.core.formatPercent(Statso.core.primeRate(doc.current_rate));
    Statso.data.setState(document.getElementById('boi-kpi'), 'ready');
    if (Statso.tools) { Statso.tools.initBoi(doc); }
  }
  function showNext(doc) {
    if (!doc.next_decision_date) { throw new Error('מועד ההחלטה הבאה אינו זמין'); }
    document.getElementById('kpi-next-decision').textContent = Statso.core.formatIsoDateHe(doc.next_decision_date);
  }
  function showNextUnavailable() { document.getElementById('kpi-next-decision').textContent = 'אינה ידועה'; }
  function showFx(doc) {
    const rates = new Map((doc.rates || []).map(function (row) { return [row.code, row]; }));
    const usd = rates.get('USD'); const eur = rates.get('EUR');
    if (!usd || !eur) { throw new Error('שערי החליפין אינם זמינים'); }
    document.getElementById('kpi-fx-usd').textContent = Statso.core.formatRate(usd.latest.rate);
    document.getElementById('kpi-fx-eur').textContent = Statso.core.formatRate(eur.latest.rate);
    document.getElementById('kpi-fx-date').textContent = Statso.core.formatIsoDateHe(usd.latest.date);
    Statso.data.setState(document.getElementById('fx-kpi'), 'ready');
    Statso.fxtable.init(doc);
    Statso.calculator.initFx(doc);
    if (Statso.tools) { Statso.tools.initFx(doc); }
  }
  function failFx(message) {
    failCard('fx-kpi', 'kpi-fx-error', message, ['kpi-fx-usd', 'kpi-fx-eur']);
    Statso.data.setState(document.getElementById('fx-table-section'), 'error', message);
  }
  function showVersion() {
    Statso.data.loadVersion().then(function (version) {
      if (!/^\d+\.\d+\.\d+$/.test(version)) { return; }
      document.getElementById('app-version').textContent = version;
      document.getElementById('app-version-line').hidden = false;
    }).catch(function () {});
  }
  function init() {
    showVersion();
    Statso.collapse.attach('fx-table-section', {collapsed: false});
    Statso.collapse.attach('chart-section', {collapsed: true, onOpen: function () { Statso.chart.activate(); }});
    Statso.data.loadAll().then(function (results) {
      const cpi = results[0], boi = results[1], next = results[2], fx = results[3];
      if (cpi.status === 'fulfilled') { try { showCpi(cpi.value); } catch (error) { failCpi(error.message); } } else { failCpi(cpi.reason.message); }
      if (boi.status === 'fulfilled') { try { showBoi(boi.value); } catch (error) { failCard('boi-kpi', 'kpi-boi-error', error.message, ['kpi-boi-rate', 'kpi-boi-prime']); } }
      else { failCard('boi-kpi', 'kpi-boi-error', boi.reason.message, ['kpi-boi-rate', 'kpi-boi-prime']); }
      if (next.status === 'fulfilled') { try { showNext(next.value); } catch (error) { showNextUnavailable(); } } else { showNextUnavailable(); }
      if (fx.status === 'fulfilled') { try { showFx(fx.value); } catch (error) { failFx(error.message); } } else { failFx(fx.reason.message); }
      root.dispatchEvent(new CustomEvent('statso:app-ready'));
    });
  }
  document.addEventListener('DOMContentLoaded', init);
  Statso.app = {init: init};
})(window);
