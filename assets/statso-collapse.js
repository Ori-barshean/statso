(function (root) {
  'use strict';
  const Statso = root.Statso = root.Statso || {};
  const PREFIX = 'statso:collapsed:';

  function readStored(sectionId) {
    try {
      const raw = root.localStorage.getItem(PREFIX + sectionId);
      return raw === 'true' ? true : raw === 'false' ? false : null;
    } catch (error) { return null; }
  }

  function writeStored(sectionId, collapsed) {
    try { root.localStorage.setItem(PREFIX + sectionId, collapsed ? 'true' : 'false'); } catch (error) {}
  }

  function apply(section, button, collapsed) {
    section.dataset.collapsed = collapsed ? 'true' : 'false';
    button.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
  }

  function attach(sectionId, settings) {
    const section = document.getElementById(sectionId);
    const button = section ? section.querySelector('.section-toggle') : null;
    if (!section || !button) { return null; }
    const options = settings || {};
    const stored = readStored(sectionId);
    let collapsed = stored === null ? options.collapsed === true : stored;
    function announce() { if (!collapsed && typeof options.onOpen === 'function') { options.onOpen(); } }
    apply(section, button, collapsed);
    announce();
    button.addEventListener('click', function () {
      collapsed = !collapsed;
      apply(section, button, collapsed);
      writeStored(sectionId, collapsed);
      announce();
    });
    return {isCollapsed: function () { return collapsed; }};
  }

  Statso.collapse = {attach: attach, readStored: readStored, PREFIX: PREFIX};
})(window);
