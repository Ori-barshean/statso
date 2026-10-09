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
    '#/tools/rate-history': 'tool-rate-history-page',
    '#/tools/fx-history': 'tool-fx-history-page',
    '#/tools/rent': 'tool-rent-page'
  };
  let firstRoute = true;
  let toolsMenuJustOpened = false;
  // Read while the script is evaluated, before the i18n engine paints, so this
  // is still the page's own Hebrew <title> whatever language was requested.
  const siteTitle = document.title;

  function currentHeading() {
    const view = document.querySelector('main:not([hidden])');
    if (!view) { return null; }
    return view.querySelector('.info-page:not([hidden]) h1')
      || view.querySelector('.tool-page:not([hidden]) h2')
      || view.querySelector('.guide-detail:not([hidden]) h1')
      || view.querySelector('h1');
  }

  // The tab title (and the history entry, and the screen reader's window
  // name) has to follow the view, since a hash route never reloads the page.
  // The dashboard keeps the site's own title; every other view is named after
  // its heading, which the i18n engine has already put in the shown language.
  function updateTitle() {
    const dashboard = document.getElementById('dashboard-view');
    const heading = dashboard && dashboard.hidden ? currentHeading() : null;
    const label = heading && heading.textContent ? heading.textContent.trim() : '';
    const i18n = Statso.i18n;
    document.title = label ? label + ' \u2014 statso' : (i18n && i18n.t ? i18n.t(siteTitle) : siteTitle);
  }

  // Moving focus to the new view's own heading is the announcement: screen
  // readers read a focused element's accessible name on their own, so a
  // parallel aria-live update of the same text would just repeat it.
  function focusView() {
    updateTitle();
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
    if (firstRoute) { firstRoute = false; updateTitle(); } else { focusView(); }
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

  // The calculators recompute as the visitor types or picks, so the answer
  // changes somewhere other than where the screen reader's cursor is. After a
  // pause in the changes, say what the visible result now reads — its labels
  // and figures, never the legal disclaimer underneath them. Errors already
  // speak for themselves through their own role="alert".
  function resultBlocks(target) {
    if (!target || !target.closest) { return []; }
    const scope = target.closest('.calc-layout, .tool-layout');
    if (scope) {
      return Array.from(scope.querySelectorAll('.calc-result')).filter(function (block) { return !block.hidden; });
    }
    if (target.closest('.rent-form')) {
      const summary = document.getElementById('tr-summary');
      return summary ? [summary] : [];
    }
    return [];
  }

  function spokenText(block) {
    return Array.from(block.querySelectorAll('span, strong, small')).map(function (part) {
      return part.textContent.trim();
    }).filter(Boolean).join(' ');
  }

  function initResultAnnouncements() {
    const live = document.getElementById('result-live');
    if (!live) { return; }
    let pending = null;
    let clearing = null;
    function speak(target) {
      const text = resultBlocks(target).map(spokenText).filter(Boolean).join('. ');
      if (!text || live.textContent === text) { return; }
      live.textContent = text;
      root.clearTimeout(clearing);
      clearing = root.setTimeout(function () { live.textContent = ''; }, 5000);
    }
    function schedule(event) {
      const target = event.target;
      if (!resultBlocks(target).length) { return; }
      root.clearTimeout(pending);
      pending = root.setTimeout(function () { speak(target); }, 800);
    }
    document.addEventListener('input', schedule);
    document.addEventListener('change', schedule);
  }

  function init() {
    root.addEventListener('hashchange', route);
    // The guides re-render their open view on this same event, so read the
    // heading once that has happened rather than whenever this listener runs.
    if (Statso.i18n && Statso.i18n.onChange) { Statso.i18n.onChange(function () { root.setTimeout(updateTitle, 0); }); }
    initToolsMenu();
    initSkipLink();
    initResultAnnouncements();
    route();
  }
  document.addEventListener('DOMContentLoaded', init);
  Statso.nav = {route: route, init: init, toolRoutes: toolRoutes, focusView: focusView};
})(window);
