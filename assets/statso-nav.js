(function (root) {
  'use strict';
  const Statso = root.Statso = root.Statso || {};

  function route() {
    const guides = root.location.hash === '#/guides';
    const dashboardView = document.getElementById('dashboard-view');
    const guidesView = document.getElementById('guides-view');
    dashboardView.hidden = guides;
    guidesView.hidden = !guides;
    if (guides && Statso.guides) { Statso.guides.showIndex(); }
    document.querySelectorAll('.site-nav a').forEach(function (link) {
      const active = guides ? link.getAttribute('href') === '#/guides' : link.getAttribute('href') === '#/';
      if (active) { link.setAttribute('aria-current', 'page'); } else { link.removeAttribute('aria-current'); }
    });
    if (!guides) {
      root.requestAnimationFrame(function () {
        if (root.Statso.chart && root.Statso.chart.resize) { root.Statso.chart.resize(); }
      });
    }
  }

  function init() {
    root.addEventListener('hashchange', route);
    route();
  }
  document.addEventListener('DOMContentLoaded', init);
  Statso.nav = {route: route, init: init};
})(window);
