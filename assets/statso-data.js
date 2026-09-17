(function (root) {
  'use strict';
  const Statso = root.Statso = root.Statso || {};

  function loadDataset(el) {
    const embedded = el.textContent.trim();
    if (embedded) {
      try { return Promise.resolve(JSON.parse(embedded)); }
      catch (error) { return Promise.reject(new Error('לא ניתן לטעון את ' + el.dataset.label)); }
    }
    return fetch(el.dataset.src, {cache: 'no-store'}).then(function (res) {
      if (!res.ok) { throw new Error('response'); }
      return res.json();
    }).catch(function () { throw new Error('לא ניתן לטעון את ' + el.dataset.label); });
  }

  function loadVersion() {
    const el = document.getElementById('version-source');
    if (!el) { return Promise.reject(new Error('version source missing')); }
    const embedded = el.textContent.trim();
    if (embedded) { return Promise.resolve(embedded); }
    return fetch(el.dataset.src, {cache: 'no-store'}).then(function (res) {
      if (!res.ok) { throw new Error('response'); }
      return res.text();
    }).then(function (text) { return text.trim(); });
  }

  function loadAll() {
    return Promise.allSettled([
      loadDataset(document.getElementById('data-cpi')),
      loadDataset(document.getElementById('data-boi')),
      loadDataset(document.getElementById('data-next')),
      loadDataset(document.getElementById('data-fx-summary')),
      loadDataset(document.getElementById('data-construction-inputs'))
    ]);
  }

  let dailyFxPromise = null;
  function loadFxDaily() {
    if (!dailyFxPromise) { dailyFxPromise = loadDataset(document.getElementById('data-fx-daily')); }
    return dailyFxPromise;
  }

  function setState(sectionEl, state, messageHe) {
    sectionEl.dataset.state = state;
    if (state === 'error') {
      const target = sectionEl.querySelector('.state-error');
      if (target) { target.textContent = messageHe || 'הנתונים אינם זמינים כרגע'; }
    }
  }

  Statso.data = {loadDataset: loadDataset, loadAll: loadAll, loadVersion: loadVersion, loadFxDaily: loadFxDaily, setState: setState};
})(window);
