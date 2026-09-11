(function (root) {
  'use strict';
  const Statso = root.Statso = root.Statso || {};
  const infoRoutes = {
    '#/about': 'about-page',
    '#/method': 'method-page',
    '#/terms': 'terms-page',
    '#/privacy': 'privacy-page',
    '#/accessibility': 'accessibility-page',
    '#/contact': 'contact-page'
  };
  const toolRoutes = {
    '#/tools/index': 'tool-index-page',
    '#/tools/fx': 'tool-fx-page',
    '#/tools/history': 'tool-history-page',
    '#/tools/fx-history': 'tool-fx-history-page',
    '#/tools/rent': 'tool-rent-page'
  };
  let firstRoute = true;
  let toolsMenuJustOpened = false;

  function currentHeading() {
    const view = document.querySelector('main:not([hidden])');
    if (!view) { return null; }
    return view.querySelector('.info-page:not([hidden]) h1')
      || view.querySelector('.tool-page:not([hidden]) h2')
      || view.querySelector('.guide-detail:not([hidden]) h1')
      || view.querySelector('h1');
  }

  // Moving focus to the new view's own heading is the announcement: screen
  // readers read a focused element's accessible name on their own, so a
  // parallel aria-live update of the same text would just repeat it.
  function focusView() {
    const heading = currentHeading();
    if (!heading) { return; }
    if (!heading.hasAttribute('tabindex')) { heading.setAttribute('tabindex', '-1'); }
    heading.focus({preventScroll: true});
  }

  function closeToolsMenu() {
    const trigger = document.getElementById('tools-trigger');
    const group = trigger && trigger.closest('.nav-group');
    if (!group) { return; }
    group.removeAttribute('data-open');
    trigger.setAttribute('aria-expanded', 'false');
  }

  function route() {
    const hash = root.location.hash;
    const guides = hash === '#/guides';
    const mcode = hash === '#/mcode';
    const infoPageId = infoRoutes[hash];
    const info = Boolean(infoPageId);
    const toolPageId = toolRoutes[hash];
    const tools = hash === '#/tools' || Boolean(toolPageId);
    const dashboardView = document.getElementById('dashboard-view');
    const guidesView = document.getElementById('guides-view');
    const infoView = document.getElementById('info-view');
    const toolsView = document.getElementById('tools-view');
    dashboardView.hidden = guides || info || tools || mcode;
    document.getElementById('mcode-view').hidden = !mcode;
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
    if (guides && Statso.guides) { Statso.guides.showIndex(true); }
    if (mcode && Statso.mcode) { Statso.mcode.render(); }
    if (info || tools || mcode) { root.scrollTo(0, 0); }
    document.querySelectorAll('.site-nav a').forEach(function (link) {
      const href = link.getAttribute('href');
      const active = guides ? href === '#/guides'
        : tools ? href === '#/tools'
        : mcode ? href === '#/mcode'
        : (!info && href === '#/');
      if (active) { link.setAttribute('aria-current', 'page'); } else { link.removeAttribute('aria-current'); }
    });
    if (!guides && !info && !tools && !mcode) {
      root.requestAnimationFrame(function () {
        if (root.Statso.chart && root.Statso.chart.resize) { root.Statso.chart.resize(); }
      });
    }
    if (toolsMenuJustOpened) { toolsMenuJustOpened = false; } else { closeToolsMenu(); }
    if (firstRoute) { firstRoute = false; } else { focusView(); }
  }

  // Two independent ways to reveal the submenu: plain CSS :hover for a mouse
  // (no JS, no aria-expanded claim to keep honest), and this JS-tracked
  // data-open for anything involving focus — Tab landing on the trigger,
  // click, Enter, Space — which does keep aria-expanded truthful, since
  // real focus already gets a screen reader all the way onto the trigger.
  function initToolsMenu() {
    const trigger = document.getElementById('tools-trigger');
    const group = trigger && trigger.closest('.nav-group');
    if (!trigger || !group) { return; }
    function open() {
      group.removeAttribute('data-closed');
      group.setAttribute('data-open', 'true');
      trigger.setAttribute('aria-expanded', 'true');
    }
    function close() { closeToolsMenu(); group.removeAttribute('data-closed'); }
    trigger.addEventListener('focus', open);
    trigger.addEventListener('click', function (event) {
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) { return; }
      // Only a real navigation (a hash that's about to change) reaches
      // route(); a same-hash click never fires hashchange, so never leave
      // this set for some later, unrelated navigation to misread.
      if (root.location.hash !== '#/tools') { toolsMenuJustOpened = true; }
      open();
    });
    trigger.addEventListener('keydown', function (event) {
      if (event.key === ' ' || event.key === 'Spacebar') { event.preventDefault(); trigger.click(); }
    });
    // Document-level, not group-level: a click-opened menu doesn't
    // necessarily leave focus inside the group (Safari never focuses a
    // link on click), so a listener scoped to the group could miss Escape
    // entirely there.
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && group.getAttribute('data-open') === 'true') {
        close();
        // :focus-within would otherwise reopen it the instant focus lands
        // back on the trigger; data-closed forces it shut until the user
        // does something that means they want it back — focus leaving the
        // group, or a fresh mouse-hover attempt.
        group.setAttribute('data-closed', 'true');
        trigger.focus();
      }
    });
    group.addEventListener('focusout', function (event) {
      if (!group.contains(event.relatedTarget)) { close(); }
    });
    group.addEventListener('mouseenter', function () { group.removeAttribute('data-closed'); });
    document.addEventListener('click', function (event) {
      if (group.getAttribute('data-open') === 'true' && !group.contains(event.target)) { close(); }
    });
  }

  function initSkipLink() {
    const link = document.getElementById('skip-link');
    if (!link) { return; }
    link.addEventListener('click', function () { focusView(); });
  }

  function init() {
    root.addEventListener('hashchange', route);
    initToolsMenu();
    initSkipLink();
    route();
  }
  document.addEventListener('DOMContentLoaded', init);
  Statso.nav = {route: route, init: init, toolRoutes: toolRoutes, focusView: focusView};
})(window);
