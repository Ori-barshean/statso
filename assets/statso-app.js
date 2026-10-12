(function (root) {
  'use strict';
  const Statso = root.Statso = root.Statso || {};
  // The cards and tables on the home page say what failed, but a visitor who arrives on a tool or a guide never sees
  // them, so every failed dataset is also named once in a notice above the page (see index.html #data-problem).
  const failedData = [];
  function noteFailure(name) { if (failedData.indexOf(name) < 0) { failedData.push(name); } }
  const GENERIC_ERROR = 'אירעה שגיאה בעיבוד הנתונים. אפשר לרענן את הדף ולנסות שוב.';
  function userMessage(error) {
    const text = error && typeof error.message === 'string' ? error.message.trim() : '';
    return /[֐-׿]/.test(text) ? text : GENERIC_ERROR;
  }
  function showDataProblems() {
    const wrap = document.getElementById('data-problem-wrap'); const box = document.getElementById('data-problem');
    if (!wrap || !box || !failedData.length) { return; }
    const lead = document.createElement('p');
    lead.textContent = 'חלק מהנתונים לא נטענו, ולכן ייתכן שחלק מהכלים לא יפעלו. אפשר לרענן את הדף ולנסות שוב.';
    const label = document.createElement('p');
    label.textContent = 'נתונים שלא נטענו:';
    const list = document.createElement('ul');
    failedData.forEach(function (name) { const item = document.createElement('li'); item.textContent = name; list.appendChild(item); });
    // The alert is shown empty first and filled on the next tick: a screen reader announces a change inside a
    // region it already knows, which is less reliable when the region appears together with its text.
    box.textContent = '';
    wrap.hidden = false;
    root.setTimeout(function () { box.appendChild(lead); box.appendChild(label); box.appendChild(list); }, 50);
  }
  function failCard(sectionId, errorId, message, valueIds) {
    valueIds.forEach(function (id) { document.getElementById(id).textContent = '—'; });
    document.getElementById(errorId).textContent = message;
    Statso.data.setState(document.getElementById(sectionId), 'error', message);
  }
  function failCpi(message) {
    noteFailure('מדד המחירים לצרכן');
    failCard('cpi-kpi', 'kpi-cpi-error', message, ['kpi-cpi-yoy', 'kpi-cpi-mom']);
    Statso.data.setState(document.getElementById('chart-section'), 'error', message);
    Statso.data.setState(document.getElementById('calculator-section'), 'error', message);
  }
  function shortMonthHe(key) { const p = key.split('-'); return p[1] + '/' + p[0].slice(2); }
  function alignKpiFootnotes() {
    const notes = document.querySelectorAll('.kpi-card .kpi-footnote');
    if (!notes.length) { return; }
    notes.forEach(function (el) { el.style.minHeight = ''; });
    let max = 0;
    notes.forEach(function (el) { max = Math.max(max, el.getBoundingClientRect().height); });
    notes.forEach(function (el) { el.style.minHeight = max + 'px'; });
  }
  function showCpi(doc, constructionDoc) {
    const map = Statso.core.buildIndexMap(doc.observations); const latest = Statso.core.latestObservation(doc, map);
    if (!latest) { throw new Error('המדד העדכני חסר'); }
    const yoy = Statso.core.yearOverYear(map, doc.last_month); const mom = Statso.core.monthOverMonth(map, doc.last_month);
    if (!yoy.ok || !mom.ok) { throw new Error('לא ניתן לחשב את השינוי במדד'); }
    document.getElementById('kpi-cpi-yoy').textContent = Statso.core.formatPercent(yoy.percent);
    document.getElementById('kpi-cpi-yoy-range').textContent = shortMonthHe(Statso.core.shiftMonth(doc.last_month, -12)) + '–' + shortMonthHe(doc.last_month);
    document.getElementById('kpi-cpi-mom').textContent = Statso.core.formatPercent(mom.percent);
    document.getElementById('kpi-cpi-mom-month').textContent = Statso.core.formatMonthHe(doc.last_month);
    document.getElementById('kpi-cpi-next').textContent = Statso.core.formatIsoDateHe(Statso.core.nextCpiPublicationDate(doc.last_month));
    Statso.data.setState(document.getElementById('cpi-kpi'), 'ready');
    Statso.data.setState(document.getElementById('calculator-section'), 'ready');
    Statso.calculator.init(doc, map);
    if (Statso.tools) { Statso.tools.init(doc, map, constructionDoc || null); }
    if (typeof root.Chart === 'function') { Statso.chart.init(doc.observations, constructionDoc ? constructionDoc.observations : null); Statso.data.setState(document.getElementById('chart-section'), 'ready'); }
    else { Statso.chart.showUnavailable(); }
  }
  function showBoi(doc) {
    if (typeof doc.current_rate !== 'number' || !isFinite(doc.current_rate)) { throw new Error('הריבית הנוכחית חסרה'); }
    document.getElementById('kpi-boi-rate').textContent = Statso.core.formatPercent(doc.current_rate);
    document.getElementById('kpi-boi-prime').textContent = Statso.core.formatPercent(Statso.core.primeRate(doc.current_rate));
    Statso.data.setState(document.getElementById('boi-kpi'), 'ready');
    if (Statso.tools) { Statso.tools.initBoi(doc); }
  }
  function failBoi(message) {
    noteFailure('ריבית בנק ישראל');
    failCard('boi-kpi', 'kpi-boi-error', message, ['kpi-boi-rate', 'kpi-boi-prime']);
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
    noteFailure('שערי חליפין');
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
      const cpi = results[0], boi = results[1], next = results[2], fx = results[3], construction = results[4];
      const constructionDoc = construction && construction.status === 'fulfilled' ? construction.value : null;
      if (cpi.status === 'fulfilled') { try { showCpi(cpi.value, constructionDoc); } catch (error) { failCpi(userMessage(error)); } } else { failCpi(userMessage(cpi.reason)); }
      if (boi.status === 'fulfilled') { try { showBoi(boi.value); } catch (error) { failBoi(userMessage(error)); } }
      else { failBoi(userMessage(boi.reason)); }
      if (next.status === 'fulfilled') { try { showNext(next.value); } catch (error) { showNextUnavailable(); } } else { showNextUnavailable(); }
      if (fx.status === 'fulfilled') { try { showFx(fx.value); } catch (error) { failFx(userMessage(error)); } } else { failFx(userMessage(fx.reason)); }
      // without it the construction series is left out of the chart and its options in the tools are disabled
      if (!constructionDoc) { noteFailure('מדד תשומות הבנייה למגורים'); }
      showDataProblems();
      alignKpiFootnotes();
      root.dispatchEvent(new CustomEvent('statso:app-ready'));
    });
  }
  document.addEventListener('DOMContentLoaded', init);
  if (Statso.i18n) { Statso.i18n.onChange(alignKpiFootnotes); }
  let kpiResizeTimer = null;
  root.addEventListener('resize', function () {
    clearTimeout(kpiResizeTimer);
    kpiResizeTimer = setTimeout(alignKpiFootnotes, 150);
  });
  Statso.app = {init: init, userMessage: userMessage};
})(window);
