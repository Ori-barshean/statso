(function (root) {
  'use strict';
  const Statso = root.Statso = root.Statso || {};
  const infoRoutes = {
    '#/about': 'about-page',
    '#/method': 'method-page',
    '#/privacy': 'privacy-page',
    '#/contact': 'contact-page'
  };
  const toolRoutes = {
    '#/tools/index': 'tool-index-page',
    '#/tools/fx': 'tool-fx-page',
    '#/tools/history': 'tool-history-page',
    '#/tools/fx-history': 'tool-fx-history-page',
    '#/tools/rent': 'tool-rent-page'
  };

  function route() {
    const hash = root.location.hash;
    const guides = hash === '#/guides';
    const infoPageId = infoRoutes[hash];
    const info = Boolean(infoPageId);
    const toolPageId = toolRoutes[hash];
    const tools = hash === '#/tools' || Boolean(toolPageId);
    const dashboardView = document.getElementById('dashboard-view');
    const guidesView = document.getElementById('guides-view');
    const infoView = document.getElementById('info-view');
    const toolsView = document.getElementById('tools-view');
    dashboardView.hidden = guides || info || tools;
    guidesView.hidden = !guides;
    infoView.hidden = !info;
    if (toolsView) {
      toolsView.hidden = !tools;
      document.getElementById('tools-index').hidden = Boolean(toolPageId);
      toolsView.querySelectorAll('.tool-page').forEach(function (page) {
        page.hidden = page.id !== toolPageId;
      });
    }
    infoView.querySelectorAll('.info-page').forEach(function (page) {
      page.hidden = page.id !== infoPageId;
    });
    if (guides && Statso.guides) { Statso.guides.showIndex(); }
    if (info || tools) { root.scrollTo(0, 0); }
    document.querySelectorAll('.site-nav a').forEach(function (link) {
      const href = link.getAttribute('href');
      const active = guides ? href === '#/guides'
        : tools ? href === '#/tools'
        : (!info && href === '#/');
      if (active) { link.setAttribute('aria-current', 'page'); } else { link.removeAttribute('aria-current'); }
    });
    if (!guides && !info && !tools) {
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
  Statso.nav = {route: route, init: init, toolRoutes: toolRoutes};
})(window);
