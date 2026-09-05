(function (root) {
  'use strict';
  const Statso = root.Statso = root.Statso || {};
  const infoRoutes = {
    '#/about': 'about-page',
    '#/method': 'method-page',
    '#/privacy': 'privacy-page',
    '#/contact': 'contact-page'
  };

  function route() {
    const hash = root.location.hash;
    const guides = hash === '#/guides';
    const infoPageId = infoRoutes[hash];
    const info = Boolean(infoPageId);
    const dashboardView = document.getElementById('dashboard-view');
    const guidesView = document.getElementById('guides-view');
    const infoView = document.getElementById('info-view');
    dashboardView.hidden = guides || info;
    guidesView.hidden = !guides;
    infoView.hidden = !info;
    infoView.querySelectorAll('.info-page').forEach(function (page) {
      page.hidden = page.id !== infoPageId;
    });
    if (guides && Statso.guides) { Statso.guides.showIndex(); }
    if (info) { root.scrollTo(0, 0); }
    document.querySelectorAll('.site-nav a').forEach(function (link) {
      const active = guides ? link.getAttribute('href') === '#/guides' : (!info && link.getAttribute('href') === '#/');
      if (active) { link.setAttribute('aria-current', 'page'); } else { link.removeAttribute('aria-current'); }
    });
    if (!guides && !info) {
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
