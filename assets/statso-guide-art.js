(function (root) {
  'use strict';
  const Statso = root.Statso = root.Statso || {};
  const words = {
    he: {excel: 'Excel', data: 'נתונים', getData: 'קבל נתונים', other: 'ממקורות אחרים', web: 'מהאינטרנט', refresh: 'רענן הכל', url: 'כתובת URL', ok: 'אישור', navigator: 'נווט', load: 'טען', file: 'קובץ', open: 'פתיחה', save: 'שמירה', formula: 'שורת הנוסחאות', preview: 'תצוגה מקדימה'},
    en: {excel: 'Excel', data: 'Data', getData: 'Get Data', other: 'From Other Sources', web: 'From Web', refresh: 'Refresh All', url: 'URL', ok: 'OK', navigator: 'Navigator', load: 'Load', file: 'File', open: 'Open', save: 'Save', formula: 'Formula bar', preview: 'Preview'}
  };
  function esc(value) { return String(value || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
  function text(x, y, value, cls) { return '<text x="' + x + '" y="' + y + '" class="' + (cls || '') + '">' + esc(value) + '</text>'; }
  function marker(x, y, n) { return '<circle cx="' + x + '" cy="' + y + '" r="13" class="marker"/>' + text(x, y + 5, n, 'marker-text'); }
  function chrome(w, platform) {
    if (platform === 'mac') { return '<circle cx="18" cy="15" r="4" fill="#ff605c"/><circle cx="31" cy="15" r="4" fill="#ffbd44"/><circle cx="44" cy="15" r="4" fill="#00ca4e"/>'; }
    return '<rect x="' + (w - 74) + '" y="5" width="22" height="18" rx="2" fill="#dbe6f1"/><path d="M' + (w - 45) + ' 10l10 10m0-10-10 10" stroke="#64748b"/>';
  }
  function grid(columns) {
    let out = '<rect x="24" y="118" width="552" height="180" fill="#fff" stroke="#cbd5e1"/>';
    for (let x = 24; x <= 576; x += 92) { out += '<path d="M' + x + ' 118v180" class="grid"/>'; }
    for (let y = 118; y <= 298; y += 30) { out += '<path d="M24 ' + y + 'h552" class="grid"/>'; }
    columns.slice(0, 6).forEach(function (c, i) { out += text(34 + i * 92, 138, c, 'tiny'); });
    return out;
  }
  function render(archetype, options) {
    const lang = options.lang === 'en' ? 'en' : 'he'; const rtl = lang === 'he'; const w = words[lang];
    const step = options.step || 1; const url = options.url || ''; const cols = options.dataset === 'cpi' ? ['month','year','month_num','value','base_desc','chained_1951_09'] : ['date','rate'];
    let body = '';
    if (archetype === 'timeline-publication') {
      body = text(300, 66, 'חודש X', 'timeline-title center') +
        '<path d="M70 176H530" class="timeline"/><path d="M70 168v16M300 160v32M530 160v32" class="timeline"/>' +
        text(70, 210, 'X-1', 'timeline-label center') + text(300, 210, 'X', 'timeline-label center') + text(530, 210, 'X+1', 'timeline-label center') +
        '<rect x="190" y="82" width="220" height="54" rx="10" class="known-callout"/>' + text(300, 105, 'במהלך חודש X', 'small center') + text(300, 124, 'מדד ידוע = מדד X-1', 'timeline-label center') +
        '<circle cx="470" cy="176" r="10" class="marker"/>' + text(470, 153, '15 בחודש X+1', 'small center') + text(470, 238, 'פרסום מדד בגין X', 'timeline-label center');
    } else if (archetype === 'ribbon-data' || archetype === 'ribbon-refresh') {
      body = '<rect x="18" y="56" width="564" height="70" rx="5" fill="#f1f5f9"/>' + text(rtl ? 530 : 42, 48, w.data, 'tab active') + text(rtl ? 485 : 42, 92, archetype === 'ribbon-refresh' ? w.refresh : w.getData, 'button-label') + '<rect x="' + (rtl ? 430 : 30) + '" y="66" width="140" height="42" rx="6" class="highlight"/>' + marker(rtl ? 422 : 178, 87, step) + grid(cols);
    } else if (archetype === 'menu-getdata') {
      const mx = rtl ? 302 : 28;
      body = '<rect x="18" y="53" width="564" height="54" fill="#f1f5f9"/>' + text(rtl ? 530 : 42, 84, w.getData, 'button-label') + '<rect x="' + mx + '" y="101" width="270" height="142" rx="7" fill="#fff" stroke="#94a3b8"/>' + text(mx + 18, 135, w.other, 'menu') + text(mx + 18, 187, w.web, 'menu') + '<rect x="' + (mx + 8) + '" y="155" width="254" height="48" rx="4" class="highlight"/>' + marker(rtl ? 286 : 314, 178, step);
    } else if (archetype === 'dialog-fromweb') {
      body = '<rect x="70" y="65" width="460" height="210" rx="9" fill="#fff" stroke="#94a3b8"/>' + text(rtl ? 480 : 95, 96, w.web, 'dialog-title') + text(rtl ? 480 : 95, 132, w.url, 'small') + '<rect x="95" y="145" width="410" height="43" rx="5" fill="#fff" stroke="#64748b"/>' + text(107, 171, url, 'url') + '<rect x="405" y="216" width="100" height="36" rx="5" class="primary"/>' + text(455, 240, w.ok, 'white center') + marker(390, 234, step);
    } else if (archetype === 'dialog-navigator') {
      body = '<rect x="48" y="50" width="504" height="255" rx="9" fill="#fff" stroke="#94a3b8"/>' + text(rtl ? 510 : 72, 82, w.navigator, 'dialog-title') + '<rect x="72" y="100" width="456" height="130" fill="#f8fafc" stroke="#cbd5e1"/>' + text(92, 125, w.preview, 'small') + grid(cols).replace(/x="24" y="118" width="552" height="180"/, 'x="90" y="138" width="410" height="70"') + '<rect x="428" y="250" width="100" height="34" rx="5" class="primary"/>' + text(478, 273, w.load, 'white center') + marker(414, 267, step);
    } else if (archetype === 'sheet-loaded') {
      body = text(rtl ? 555 : 28, 54, options.dataset === 'cpi' ? 'cpi.csv' : 'boi_interest_rate.csv', 'tab') + grid(cols) + '<rect x="23" y="117" width="553" height="61" rx="3" class="highlight"/>' + marker(563, 194, step);
    } else if (archetype === 'browser-save') {
      body = '<rect x="20" y="48" width="560" height="42" rx="8" fill="#eef2f7"/>' + text(45, 75, url, 'url') + '<rect x="34" y="112" width="532" height="150" fill="#fff" stroke="#cbd5e1"/>' + text(52, 140, cols.join(','), 'mono') + text(52, 165, options.dataset === 'cpi' ? '2026-08,2026,8,104.2,…' : '2026-09-03,3.25', 'mono') + '<rect x="440" y="274" width="112" height="34" rx="5" class="highlight"/>' + text(496, 297, w.save, 'center') + marker(425, 291, step);
    } else if (archetype === 'dialog-open-file') {
      body = '<rect x="65" y="57" width="470" height="235" rx="8" fill="#fff" stroke="#94a3b8"/>' + text(rtl ? 490 : 88, 88, w.file + ' ← ' + w.open, 'dialog-title') + '<rect x="92" y="112" width="416" height="52" rx="5" fill="#dbeafe" stroke="#2563eb"/>' + text(112, 144, options.dataset === 'cpi' ? 'cpi.csv' : 'boi_interest_rate.csv', 'mono') + '<rect x="408" y="230" width="100" height="36" rx="5" class="primary"/>' + text(458, 254, w.open, 'white center') + marker(393, 248, step);
    } else if (archetype === 'cell-formula') {
      body = text(rtl ? 550 : 28, 55, w.formula, 'tab') + '<rect x="24" y="72" width="552" height="38" fill="#fff" stroke="#64748b"/>' + text(36, 97, '=WEBSERVICE("' + url + '")', 'formula') + grid(cols) + '<rect x="23" y="117" width="93" height="31" class="highlight"/>' + marker(130, 134, step);
    }
    const bare = archetype === 'timeline-publication';
    const directionClass = rtl ? ' rtl-art' : '';
    return '<svg class="guide-svg' + directionClass + '" viewBox="0 0 600 330" role="img" aria-label="' + esc(archetype) + '"' + (rtl ? ' direction="rtl"' : '') + '><style>.window{fill:#fff;stroke:#b8c5d4}.title{fill:#176b45}.grid{stroke:#dbe3ec}.highlight{fill:#dbeafe;fill-opacity:.5;stroke:#f97316;stroke-width:3}.marker{fill:#f97316}.marker-text{fill:#fff;font:bold 14px Arial;text-anchor:middle}.primary{fill:#217346}.white{fill:#fff}.center{text-anchor:middle}.tab{font:bold 15px Arial}.active{fill:#176b45}.button-label,.menu,.dialog-title{font:bold 14px Arial}.small,.tiny{font:11px Arial}.url,.formula,.mono{font:10px monospace;direction:ltr;unicode-bidi:embed}.formula{font-size:9px}.timeline{stroke:#2563eb;stroke-width:4;stroke-linecap:round}.known-callout{fill:#dbeafe;stroke:#2563eb}.timeline-title{font:bold 20px Arial}.timeline-label{font:bold 14px Arial}text{fill:#25364a}</sty' + 'le><g><rect x="5" y="5" width="590" height="320" rx="10" class="window"/>' + (bare ? '' : '<rect x="5" y="5" width="590" height="28" rx="10" class="title"/>' + chrome(600, options.platform)) + body + '</g></svg>';
  }
  Statso.guideArt = {render: render, words: words};
})(window);
