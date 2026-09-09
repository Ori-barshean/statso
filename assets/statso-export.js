(function (root) {
  'use strict';
  const Statso = root.Statso = root.Statso || {};
  const XLSX_MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';

  function stamp() {
    const now = new Date();
    return now.getFullYear() + String(now.getMonth() + 1).padStart(2, '0') + String(now.getDate()).padStart(2, '0');
  }

  function downloadBytes(filename, bytes, mime) {
    const blob = new Blob([bytes], {type: mime || 'application/octet-stream'});
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url; link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    root.setTimeout(function () { URL.revokeObjectURL(url); }, 2000);
  }

  function downloadWorkbook(filename, sheets) {
    downloadBytes(filename, Statso.xlsx.build(sheets), XLSX_MIME);
  }

  function toTsv(rows) {
    return rows.map(function (row) {
      return row.map(function (cell) {
        const value = cell === null || cell === undefined ? '' : cell;
        return String(typeof value === 'object' ? value.v : value).replace(/[\t\r\n]/g, ' ');
      }).join('\t');
    }).join('\n');
  }

  function copyText(text) {
    if (root.navigator.clipboard && root.navigator.clipboard.writeText) {
      return root.navigator.clipboard.writeText(text).catch(function () { return legacyCopy(text); });
    }
    return legacyCopy(text);
  }

  function legacyCopy(text) {
    return new Promise(function (resolve, reject) {
      const area = document.createElement('textarea');
      area.value = text;
      area.setAttribute('readonly', 'readonly');
      area.style.position = 'fixed';
      area.style.insetInlineStart = '-9999px';
      document.body.appendChild(area);
      area.select();
      let ok = false;
      try { ok = document.execCommand('copy'); } catch (error) { ok = false; }
      document.body.removeChild(area);
      if (ok) { resolve(); } else { reject(new Error('copy failed')); }
    });
  }

  // Renders `html` into a dedicated print container and opens the browser's
  // print dialog, where the user picks "Save as PDF". Keeping it in-page (rather
  // than a popup) means Hebrew shaping is the browser's job and it works offline.
  function printDocument(title, html) {
    const container = document.getElementById('print-root');
    if (!container) { return false; }
    const previous = document.title;
    container.innerHTML = html;
    document.body.classList.add('is-printing');
    document.title = title;
    let restored = false;
    function restore() {
      if (restored) { return; }
      restored = true;
      document.body.classList.remove('is-printing');
      document.title = previous;
      root.removeEventListener('afterprint', restore);
    }
    root.addEventListener('afterprint', restore);
    root.print();
    restore();
    return true;
  }

  function tableHtml(head, rows) {
    let html = '<table><thead><tr>';
    head.forEach(function (cell) { html += '<th>' + Statso.xlsx.escapeXml(cell) + '</th>'; });
    html += '</tr></thead><tbody>';
    rows.forEach(function (row) {
      html += '<tr>';
      row.forEach(function (cell) {
        const value = cell === null || cell === undefined ? '' : (typeof cell === 'object' ? cell.v : cell);
        const numeric = typeof value === 'number';
        html += '<td' + (numeric ? ' dir="ltr"' : '') + '>'
          + Statso.xlsx.escapeXml(numeric ? Statso.core.formatNumber(value, 2) : value) + '</td>';
      });
      html += '</tr>';
    });
    return html + '</tbody></table>';
  }

  function documentHtml(title, subtitle, blocks) {
    let html = '<header class="print-head"><div class="print-brand">statso</div>'
      + '<h1>' + Statso.xlsx.escapeXml(title) + '</h1>';
    if (subtitle) { html += '<p class="print-subtitle">' + Statso.xlsx.escapeXml(subtitle) + '</p>'; }
    html += '</header>' + blocks.join('');
    return html + '<footer class="print-foot">הופק ב־' + Statso.core.formatIsoDateHe(new Date().toISOString().slice(0, 10))
      + ' · נתוני מקור: הלשכה המרכזית לסטטיסטיקה ובנק ישראל · statso</footer>';
  }

  function flash(button, message) {
    const previous = button.textContent;
    button.textContent = message;
    button.disabled = true;
    root.setTimeout(function () { button.textContent = previous; button.disabled = false; }, 1600);
  }

  Statso.exporter = {downloadBytes: downloadBytes, downloadWorkbook: downloadWorkbook, toTsv: toTsv,
    copyText: copyText, printDocument: printDocument, tableHtml: tableHtml, documentHtml: documentHtml,
    flash: flash, stamp: stamp, XLSX_MIME: XLSX_MIME};
})(window);
