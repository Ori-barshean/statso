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

  // The tools submenu hangs from the end edge of its trigger, so near a window edge it ran out of the page: at 320px the
  // Hebrew menu crossed the right edge and the English one the left. Pure: the horizontal shift (px) that brings the menu's
  // [left, right] inside [start + margin, end - margin]; when the menu is wider than that room (CSS caps it, so by a pixel
  // or so at most) the left edge wins.
  const SUBMENU_MARGIN = 8;
  function submenuShift(left, right, start, end, margin) {
    if (![left, right, start, end, margin].every(Number.isFinite) || right <= left || end <= start) { return 0; }
    let shift = 0;
    // rounded away from the edge being cleared, so a fractional rect never leaves less than the margin
    if (right > end - margin) { shift = Math.floor(end - margin - right); }
    if (left + shift < start + margin) { shift = Math.ceil(start + margin - left); }
    return shift || 0;
  }
  // The page box is measured rather than assumed to start at 0: a scrollbar on the left (an RTL page in Firefox, or in a
  // frame in Chrome) moves it. The rect is valid while the menu is closed too (visibility: hidden still lays it out); it
  // already includes the shift last applied, which is taken off before measuring again.
  let submenuOffset = 0;
  function fitToolsMenu() {
    const menu = document.getElementById('tools-submenu');
    const html = document.documentElement;
    if (!menu || typeof menu.getBoundingClientRect !== 'function' || !menu.style || typeof menu.style.setProperty !== 'function') { return; }
    if (!html || typeof html.getBoundingClientRect !== 'function' || !(html.clientWidth > 0)) { return; }
    const start = html.getBoundingClientRect().left + (Number(root.scrollX) || 0);
    const rect = menu.getBoundingClientRect();
    const shift = submenuShift(rect.left - submenuOffset, rect.right - submenuOffset, start, start + html.clientWidth, SUBMENU_MARGIN);
    if (shift === submenuOffset) { return; }
    submenuOffset = shift;
    menu.style.setProperty('--submenu-shift', shift + 'px');
  }

  function knownGuide(id) {
    if (!Statso.guides) { return true; }   // module missing: guides view as before; the script notice explains
    return (Statso.guides.guides || []).some(function (guide) { return guide.id === id && !guide.soon; });
  }

  function route() {
    const hash = String(root.location.hash || '');
    const guideMatch = /^#\/guides\/([a-z0-9-]+)$/.exec(hash);
    const guides = hash === '#/guides' || Boolean(guideMatch && knownGuide(guideMatch[1]));
    const mcode = hash === '#/mcode';
    const toolPageId = toolRoutes[hash];
    const tools = hash === '#/tools' || Boolean(toolPageId);
    const home = hash === '' || hash === '#' || hash === '#/';
    const notFound = !home && !guides && !mcode && !tools && !infoRoutes[hash];
    const infoPageId = infoRoutes[hash] || (notFound ? 'notfound-page' : '');
    const info = Boolean(infoPageId);
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
    if (guides && Statso.guides) {
      if (!(guideMatch && Statso.guides.showGuide(guideMatch[1], true))) { Statso.guides.showIndex(true); }
    }
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
    let refocusing = false;
    function open() {
      if (refocusing) { return; }
      fitToolsMenu();
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
      if (event.key !== 'Escape') { return; }
      if (group.getAttribute('data-open') === 'true') {
        close();
        // :focus-within would otherwise reopen it the instant focus lands
        // back on the trigger; data-closed forces it shut until the user
        // does something that means they want it back — focus leaving the
        // group, or a fresh mouse-hover attempt.
        group.setAttribute('data-closed', 'true');
        refocusing = true;
        try { trigger.focus(); } finally { refocusing = false; }
      } else if (group.matches(':hover')) {
        // Opened by the pointer alone (CSS :hover): nothing to un-set and focus never went there, so only force it
        // shut (WCAG 1.4.13). The mouseenter listener clears this on the next fresh hover; focus opens it too.
        group.setAttribute('data-closed', 'true');
      }
    });
    group.addEventListener('focusout', function (event) {
      if (!group.contains(event.relatedTarget)) { close(); }
    });
    group.addEventListener('mouseenter', function () { group.removeAttribute('data-closed'); fitToolsMenu(); });
    document.addEventListener('click', function (event) {
      if (group.getAttribute('data-open') === 'true' && !group.contains(event.target)) { close(); }
    });
    // Re-placed whenever the menu or the room for it can change: a resized window, the other language (new labels,
    // the other direction), a new text size (ResizeObserver), and right before it opens (focus, click, hover).
    if (typeof root.addEventListener === 'function') { root.addEventListener('resize', fitToolsMenu); }
    if (Statso.i18n && typeof Statso.i18n.onChange === 'function') { Statso.i18n.onChange(fitToolsMenu); }
    const menu = document.getElementById('tools-submenu');
    if (typeof root.ResizeObserver === 'function') {
      const observer = new root.ResizeObserver(fitToolsMenu);
      [group, menu].forEach(function (node) { if (node && node.nodeType === 1) { observer.observe(node); } });
    }
    fitToolsMenu();
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
    // Three other tools share the rent form's class for their layout, so the class says nothing about which tool
    // the visitor is in: the page does. A change in the rent tool says its totals; a change in a historical-data tool
    // says how many rows the table now holds (the first sentence of the note under it).
    if (target.closest('#tool-rent-page .rent-form')) {
      const summary = document.getElementById('tr-summary');
      return summary ? [summary] : [];
    }
    const page = target.closest('#tool-history-page, #tool-rate-history-page, #tool-fx-history-page');
    if (page) {
      const note = document.getElementById(HISTORY_NOTES[page.id]);
      return note && note.textContent.trim() ? [note] : [];
    }
    return [];
  }

  const HISTORY_NOTES = {'tool-history-page': 'th-note', 'tool-rate-history-page': 'trh-note', 'tool-fx-history-page': 'fxh-note'};

  function isHistoryNote(block) {
    return Object.keys(HISTORY_NOTES).some(function (id) { return HISTORY_NOTES[id] === block.id; });
  }

  function spokenText(block) {
    if (isHistoryNote(block)) {
      const lead = root.Statso && root.Statso.i18n && root.Statso.i18n.t ? root.Statso.i18n.t('הטבלה עודכנה') : 'הטבלה עודכנה';
      const note = block.textContent.trim();
      const stop = note.indexOf('. ');
      return lead + ': ' + (stop < 0 ? note : note.slice(0, stop + 1));
    }
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
      const blocks = resultBlocks(target);
      const text = blocks.map(spokenText).filter(Boolean).join('. ');
      if (!text) { return; }
      if (live.textContent === text) {
        // A calculator whose answer did not change says nothing again. A table that was rewritten says so even when
        // it still has as many rows (another currency or series column was added or removed).
        if (!blocks.some(isHistoryNote)) { return; }
        live.textContent = '';
      }
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

  // A header taller than a quarter of the window (200% text in a narrow window: ~280px of 800) would cover that share of every
  // screen if it stuck, so .is-tall lets it scroll away with the page and --header-height drops to 0px, so scroll-padding-top
  // reserves nothing for it. Sticky and relative take the same room in the flow, so switching never changes the height measured
  // here. The window's height is the root's clientHeight (it leaves out a horizontal scrollbar, as clientWidth does in the
  // README's reflow checks), else innerHeight; with neither, or no classList, the header stays sticky exactly as before.
  const TALL_HEADER_SHARE = 0.25;
  function windowHeight(html) {
    if (typeof html.clientHeight === 'number' && html.clientHeight > 0) { return html.clientHeight; }
    return typeof root.innerHeight === 'number' && root.innerHeight > 0 ? root.innerHeight : 0;
  }
  function syncHeaderOffset() {
    const header = typeof document.querySelector === 'function' ? document.querySelector('.site-header') : null;
    const html = document.documentElement;
    if (!header || typeof header.getBoundingClientRect !== 'function' || !html || !html.style) { return; }
    const height = Math.ceil(header.getBoundingClientRect().height);
    if (!(height > 0)) { return; }
    const canMark = Boolean(header.classList) && typeof header.classList.toggle === 'function';
    const viewport = windowHeight(html);
    const tall = canMark && viewport > 0 && height > viewport * TALL_HEADER_SHARE;
    if (canMark) { header.classList.toggle('is-tall', tall); }
    html.style.setProperty('--header-height', (tall ? 0 : height) + 'px');
  }
  function initHeaderOffset() {
    syncHeaderOffset();
    const header = typeof document.querySelector === 'function' ? document.querySelector('.site-header') : null;
    if (typeof root.ResizeObserver === 'function' && header && header.nodeType === 1) {
      new root.ResizeObserver(syncHeaderOffset).observe(header);
    }
    if (typeof root.addEventListener === 'function') { root.addEventListener('resize', syncHeaderOffset); }
    // Both of the above run with rendering; Tab is the moment the browser decides how far to scroll, so
    // measure the header right before it as well (this also covers a page that was resized while hidden).
    if (typeof document.addEventListener === 'function') {
      document.addEventListener('keydown', function (event) { if (event.key === 'Tab') { syncHeaderOffset(); } }, true);
    }
  }

  function init() {
    root.addEventListener('hashchange', route);
    // The guides re-render their open view on this same event, so read the
    // heading once that has happened rather than whenever this listener runs.
    if (Statso.i18n && Statso.i18n.onChange) { Statso.i18n.onChange(function () { root.setTimeout(updateTitle, 0); }); }
    initToolsMenu();
    initSkipLink();
    initResultAnnouncements();
    initHeaderOffset();
    route();
  }
  document.addEventListener('DOMContentLoaded', init);
  Statso.nav = {route: route, init: init, toolRoutes: toolRoutes, focusView: focusView};
  Statso.nav.submenuShift = submenuShift;
})(window);
