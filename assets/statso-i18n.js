(function (root) {
  'use strict';
  const Statso = root.Statso = root.Statso || {};
  const STORAGE_KEY = 'statso:lang';
  const ATTRIBUTES = ['placeholder', 'title', 'aria-label', 'alt'];
  const SKIP_TAGS = {SCRIPT: true, STYLE: true, TEXTAREA: true};

  const originalText = new WeakMap();   // text node -> Hebrew source
  const originalAttrs = new WeakMap();  // element -> {attribute: Hebrew source}
  const listeners = [];
  let lang = 'he';
  let observer = null;
  let writing = false;

  function dictionary() { return (Statso.lang && Statso.lang.en) || {}; }
  function patterns() { return (Statso.lang && Statso.lang.enPatterns) || []; }

  // Translate one Hebrew string. Falls back to the pattern rules, which cover
  // sentences the modules build by concatenation at run time.
  function t(text) {
    if (lang === 'he') { return text; }
    const trimmed = String(text).trim();
    if (!trimmed) { return text; }
    const exact = dictionary()[trimmed];
    if (exact !== undefined) { return String(text).replace(trimmed, exact); }
    const rules = patterns();
    for (let i = 0; i < rules.length; i += 1) {
      if (rules[i][0].test(trimmed)) {
        return String(text).replace(trimmed, trimmed.replace(rules[i][0], rules[i][1]));
      }
    }
    return text;
  }

  function hasHebrew(text) { return /[֐-׿]/.test(text); }

  function translateTextNode(node) {
    const source = originalText.has(node) ? originalText.get(node) : node.nodeValue;
    if (!hasHebrew(source)) { return; }
    if (!originalText.has(node)) { originalText.set(node, source); }
    const next = lang === 'he' ? source : t(source);
    if (node.nodeValue !== next) { node.nodeValue = next; }
  }

  function translateAttributes(element) {
    let stored = originalAttrs.get(element);
    ATTRIBUTES.forEach(function (name) {
      if (!element.hasAttribute(name)) { return; }
      const source = stored && stored[name] !== undefined ? stored[name] : element.getAttribute(name);
      if (!hasHebrew(source)) { return; }
      if (!stored) { stored = {}; originalAttrs.set(element, stored); }
      if (stored[name] === undefined) { stored[name] = source; }
      const next = lang === 'he' ? source : t(source);
      if (element.getAttribute(name) !== next) { element.setAttribute(name, next); }
    });
  }

  // Prose written as a whole (the information pages) ships as two parallel
  // blocks, because translating sentence fragments around inline <code> and
  // links cannot produce correct English word order.
  function applyLanguageBlocks(node) {
    const blocks = node.querySelectorAll ? node.querySelectorAll('[data-lang]') : [];
    blocks.forEach(function (block) { block.hidden = block.getAttribute('data-lang') !== lang; });
    if (node.nodeType === 1 && node.hasAttribute && node.hasAttribute('data-lang')) {
      node.hidden = node.getAttribute('data-lang') !== lang;
    }
  }

  function walk(node) {
    if (node.nodeType === 3) { translateTextNode(node); return; }
    if (node.nodeType !== 1 || SKIP_TAGS[node.tagName]) { return; }
    if (node.hasAttribute('data-i18n-skip')) { return; }
    if (node.hasAttribute('data-lang')) {
      node.hidden = node.getAttribute('data-lang') !== lang;
      if (node.hidden) { return; }
    }
    translateAttributes(node);
    for (let child = node.firstChild; child; child = child.nextSibling) { walk(child); }
  }

  function apply(target) {
    writing = true;
    try {
      const root_ = target || document.body;
      applyLanguageBlocks(root_);
      walk(root_);
    } finally { writing = false; }
  }

  function startObserver() {
    if (observer || typeof root.MutationObserver !== 'function') { return; }
    observer = new root.MutationObserver(function (records) {
      if (writing) { return; }
      writing = true;
      try {
        records.forEach(function (record) {
          if (record.type === 'characterData') { translateTextNode(record.target); return; }
          record.addedNodes.forEach(function (node) { walk(node); });
        });
      } finally { writing = false; }
    });
    observer.observe(document.body, {childList: true, subtree: true, characterData: true});
  }

  function readInitial() {
    let requested = null;
    try {
      const params = new URLSearchParams(root.location.search);
      const value = params.get('lang');
      if (value === 'en' || value === 'he') { requested = value; }
    } catch (error) { requested = null; }
    if (requested) { return requested; }
    try {
      const stored = root.localStorage.getItem(STORAGE_KEY);
      if (stored === 'en' || stored === 'he') { return stored; }
    } catch (error) { /* private mode */ }
    return 'he';
  }

  function writeUrl() {
    try {
      const url = new URL(root.location.href);
      if (lang === 'he') { url.searchParams.delete('lang'); } else { url.searchParams.set('lang', 'en'); }
      root.history.replaceState(null, '', url.toString());
    } catch (error) { /* file:// has no history entry to rewrite */ }
  }

  function paint() {
    const html = document.documentElement;
    html.setAttribute('lang', lang);
    html.setAttribute('dir', lang === 'he' ? 'rtl' : 'ltr');
    document.querySelectorAll('.lang-choice').forEach(function (choice) {
      const active = choice.getAttribute('data-lang-choice') === lang;
      if (active) { choice.setAttribute('aria-current', 'true'); } else { choice.removeAttribute('aria-current'); }
    });
    const title = document.querySelector('title');
    if (title) { translateTextNode(title.firstChild || title.appendChild(document.createTextNode(''))); }
    apply(document.body);
  }

  function set(next) {
    if (next !== 'he' && next !== 'en') { return; }
    if (next === lang) { return; }
    lang = next;
    try { root.localStorage.setItem(STORAGE_KEY, lang); } catch (error) { /* private mode */ }
    writeUrl();
    paint();
    listeners.forEach(function (fn) { try { fn(lang); } catch (error) { /* keep the rest */ } });
  }

  function onChange(fn) { listeners.push(fn); }
  function current() { return lang; }
  function locale() { return lang === 'he' ? 'he-IL' : 'en-GB'; }

  function closeMenu() {
    const menu = document.getElementById('lang-menu');
    const button = document.getElementById('lang-toggle');
    if (menu) { menu.hidden = true; }
    if (button) { button.setAttribute('aria-expanded', 'false'); }
  }

  function init() {
    lang = readInitial();
    const button = document.getElementById('lang-toggle');
    const menu = document.getElementById('lang-menu');
    if (button && menu) {
      button.addEventListener('click', function (event) {
        event.stopPropagation();
        const open = menu.hidden;
        menu.hidden = !open;
        button.setAttribute('aria-expanded', open ? 'true' : 'false');
      });
      menu.querySelectorAll('.lang-choice').forEach(function (choice) {
        choice.addEventListener('click', function () {
          set(choice.getAttribute('data-lang-choice'));
          closeMenu();
        });
      });
      document.addEventListener('click', function (event) {
        if (!menu.hidden && !document.getElementById('lang-picker').contains(event.target)) { closeMenu(); }
      });
      document.addEventListener('keydown', function (event) { if (event.key === 'Escape') { closeMenu(); } });
    }
    paint();
    startObserver();
  }

  document.addEventListener('DOMContentLoaded', init);
  Statso.i18n = {t: t, set: set, apply: apply, current: current, locale: locale, onChange: onChange,
    init: init, hasHebrew: hasHebrew, STORAGE_KEY: STORAGE_KEY};
})(window);
