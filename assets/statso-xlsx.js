(function (root) {
  'use strict';
  const Statso = root.Statso = root.Statso || {};

  // Styles the sheet builder can reference by name. Index order must match cellXfs below.
  const STYLE = {plain: 0, header: 1, title: 2, money: 3, moneyBold: 4, percent: 5, boxed: 6, muted: 7};

  const CRC_TABLE = (function () {
    const table = new Int32Array(256);
    for (let n = 0; n < 256; n += 1) {
      let c = n;
      for (let k = 0; k < 8; k += 1) { c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; }
      table[n] = c;
    }
    return table;
  })();

  function crc32(bytes) {
    let c = -1;
    for (let i = 0; i < bytes.length; i += 1) { c = CRC_TABLE[(c ^ bytes[i]) & 0xff] ^ (c >>> 8); }
    return (c ^ -1) >>> 0;
  }

  function utf8(text) { return new TextEncoder().encode(text); }

  function escapeXml(text) {
    return String(text).replace(/[&<>"']/g, function (ch) {
      return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;'}[ch];
    });
  }

  function columnName(index) {
    let name = '';
    let n = index + 1;
    while (n > 0) { const rest = (n - 1) % 26; name = String.fromCharCode(65 + rest) + name; n = Math.floor((n - 1) / 26); }
    return name;
  }

  // --- minimal ZIP (stored, no compression) -------------------------------
  function writer() {
    const chunks = [];
    let length = 0;
    return {
      push: function (bytes) { chunks.push(bytes); length += bytes.length; },
      u16: function (value) { this.push(new Uint8Array([value & 0xff, (value >>> 8) & 0xff])); },
      u32: function (value) {
        this.push(new Uint8Array([value & 0xff, (value >>> 8) & 0xff, (value >>> 16) & 0xff, (value >>> 24) & 0xff]));
      },
      get length() { return length; },
      merge: function () {
        const out = new Uint8Array(length);
        let at = 0;
        chunks.forEach(function (chunk) { out.set(chunk, at); at += chunk.length; });
        return out;
      }
    };
  }

  function zip(files) {
    const out = writer();
    const central = [];
    files.forEach(function (file) {
      const name = utf8(file.name);
      const data = file.data;
      const crc = crc32(data);
      const offset = out.length;
      out.u32(0x04034b50); out.u16(20); out.u16(0x0800); out.u16(0); out.u16(0); out.u16(0);
      out.u32(crc); out.u32(data.length); out.u32(data.length); out.u16(name.length); out.u16(0);
      out.push(name); out.push(data);
      central.push({name: name, crc: crc, size: data.length, offset: offset});
    });
    const directoryStart = out.length;
    central.forEach(function (entry) {
      out.u32(0x02014b50); out.u16(20); out.u16(20); out.u16(0x0800); out.u16(0); out.u16(0); out.u16(0);
      out.u32(entry.crc); out.u32(entry.size); out.u32(entry.size);
      out.u16(entry.name.length); out.u16(0); out.u16(0); out.u16(0); out.u16(0); out.u32(0);
      out.u32(entry.offset); out.push(entry.name);
    });
    const directorySize = out.length - directoryStart;
    out.u32(0x06054b50); out.u16(0); out.u16(0); out.u16(central.length); out.u16(central.length);
    out.u32(directorySize); out.u32(directoryStart); out.u16(0);
    return out.merge();
  }

  // --- sheet XML ----------------------------------------------------------
  // Cell values bypass the DOM, so they need the translator applied directly for
  // exports to follow the site language.
  function say(text) {
    return Statso.i18n ? Statso.i18n.t(text) : text;
  }

  function sheetName(sheet, i) { return say(sheet.name || ('גיליון' + (i + 1))).slice(0, 31); }
  function freezeOf(sheet) { return Number.isInteger(sheet.freezeRows) && sheet.freezeRows > 0 ? sheet.freezeRows : 0; }
  function filterOf(sheet) { return /^[A-Z]{1,3}[1-9]\d*:[A-Z]{1,3}[1-9]\d*$/.test(sheet.autoFilter) ? sheet.autoFilter : null; }
  function isoSeconds(v) {
    let date = new Date(v ?? Date.now());
    if (!Number.isFinite(date.getTime())) { date = new Date(); }
    return date.toISOString().replace(/\.\d{3}Z$/, 'Z');
  }

  function coreXml(options, firstSheet) {
    const stamp = isoSeconds(options.created);
    const language = options.language || (Statso.i18n && Statso.i18n.locale ? Statso.i18n.locale() : 'he-IL');
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
      + '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
      + '<dc:title>' + escapeXml(say(options.title || sheetName(firstSheet, 0))) + '</dc:title>'
      + '<dc:creator>statso</dc:creator><cp:lastModifiedBy>statso</cp:lastModifiedBy>'
      + '<dc:language>' + escapeXml(language) + '</dc:language>'
      + '<dcterms:created xsi:type="dcterms:W3CDTF">' + stamp + '</dcterms:created>'
      + '<dcterms:modified xsi:type="dcterms:W3CDTF">' + stamp + '</dcterms:modified></cp:coreProperties>';
  }

  function definedNamesXml(sheets) {
    const names = sheets.map(function (sheet, i) {
      const ref = filterOf(sheet);
      if (!ref) { return ''; }
      const range = "'" + sheetName(sheet, i).replace(/'/g, "''") + "'!" + ref.replace(/([A-Z]+)(\d+)/g, '$$$1$$$2');
      return '<definedName name="_xlnm._FilterDatabase" localSheetId="' + i + '" hidden="1">' + escapeXml(range) + '</definedName>';
    }).join('');
    return names ? '<definedNames>' + names + '</definedNames>' : '';
  }

  function cellXml(cell, reference) {
    if (cell === null || cell === undefined || cell === '') { return ''; }
    const value = typeof cell === 'object' ? cell.v : cell;
    const style = typeof cell === 'object' && cell.s ? ' s="' + cell.s + '"' : '';
    if (value === null || value === undefined || value === '') { return ''; }
    if (typeof value === 'number' && isFinite(value)) {
      return '<c r="' + reference + '"' + style + '><v>' + value + '</v></c>';
    }
    return '<c r="' + reference + '"' + style + ' t="inlineStr"><is><t xml:space="preserve">'
      + escapeXml(say(value)) + '</t></is></c>';
  }

  function sheetXml(sheet) {
    const rows = sheet.rows || [];
    const freeze = freezeOf(sheet);
    const filter = filterOf(sheet);
    let xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
      + '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
      + (freeze ? '<sheetViews><sheetView rightToLeft="1" workbookViewId="0"><pane ySplit="' + freeze
        + '" topLeftCell="A' + (freeze + 1) + '" activePane="bottomLeft" state="frozen"/>'
        + '<selection pane="bottomLeft" activeCell="A' + (freeze + 1) + '" sqref="A' + (freeze + 1) + '"/></sheetView></sheetViews>'
        : '<sheetViews><sheetView rightToLeft="1" workbookViewId="0"/></sheetViews>');
    if (sheet.columns && sheet.columns.length) {
      xml += '<cols>';
      sheet.columns.forEach(function (column, index) {
        xml += '<col min="' + (index + 1) + '" max="' + (index + 1) + '" width="'
          + (column.width || 14) + '" customWidth="1"/>';
      });
      xml += '</cols>';
    }
    xml += '<sheetData>';
    rows.forEach(function (row, rowIndex) {
      xml += '<row r="' + (rowIndex + 1) + '">';
      (row || []).forEach(function (cell, columnIndex) {
        xml += cellXml(cell, columnName(columnIndex) + (rowIndex + 1));
      });
      xml += '</row>';
    });
    xml += '</sheetData>';
    if (filter) { xml += '<autoFilter ref="' + filter + '"/>'; }
    return xml + '</worksheet>';
  }

  function stylesXml() {
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
      + '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
      + '<numFmts count="2"><numFmt numFmtId="164" formatCode="#,##0.00"/>'
      + '<numFmt numFmtId="165" formatCode="0.00%"/></numFmts>'
      + '<fonts count="4">'
      + '<font><sz val="11"/><name val="Arial"/></font>'
      + '<font><b/><sz val="11"/><name val="Arial"/></font>'
      + '<font><b/><sz val="15"/><name val="Arial"/></font>'
      + '<font><sz val="9"/><color rgb="FF6B7280"/><name val="Arial"/></font>'
      + '</fonts>'
      + '<fills count="3"><fill><patternFill patternType="none"/></fill>'
      + '<fill><patternFill patternType="gray125"/></fill>'
      + '<fill><patternFill patternType="solid"><fgColor rgb="FFE8F0FF"/>'
      + '<bgColor indexed="64"/></patternFill></fill></fills>'
      + '<borders count="2"><border><left/><right/><top/><bottom/><diagonal/></border>'
      + '<border><left/><right/><top/><bottom style="thin">'
      + '<color rgb="FFD7DEE8"/></bottom><diagonal/></border></borders>'
      + '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
      + '<cellXfs count="8">'
      + '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
      + '<xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"/>'
      + '<xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1"/>'
      + '<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
      + '<xf numFmtId="164" fontId="1" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyFont="1" applyBorder="1"/>'
      + '<xf numFmtId="165" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
      + '<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1"/>'
      + '<xf numFmtId="0" fontId="3" fillId="0" borderId="0" xfId="0" applyFont="1"/>'
      + '</cellXfs><cellStyles count="1">'
      + '<cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>' + '</' + 'styleSheet>';
  }

  function build(sheets, options) {
    options = options || {};
    const list = (sheets || []).filter(Boolean);
    if (!list.length) { throw new Error('חוברת העבודה ריקה'); }
    const files = [
      {name: 'docProps/core.xml', data: utf8(coreXml(options, list[0]))},
      {name: '[Content_Types].xml', data: utf8('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        + '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        + '<Default Extension="xml" ContentType="application/xml"/>'
        + '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        + list.map(function (sheet, index) {
          return '<Override PartName="/xl/worksheets/sheet' + (index + 1) + '.xml" '
            + 'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>';
        }).join('')
        + '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        + '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        + '</Types>')},
      {name: '_rels/.rels', data: utf8('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + '<Relationship Id="rId1" Target="xl/workbook.xml" '
        + 'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"/>'
        + '<Relationship Id="rId2" Target="docProps/core.xml" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties"/>'
        + '</Relationships>')},
      {name: 'xl/workbook.xml', data: utf8('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        + '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        + 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
        + list.map(function (sheet, index) {
          return '<sheet name="' + escapeXml(sheetName(sheet, index))
            + '" sheetId="' + (index + 1) + '" r:id="rId' + (index + 1) + '"/>';
        }).join('')
        + '</sheets>' + definedNamesXml(list) + '</workbook>')},
      {name: 'xl/_rels/workbook.xml.rels', data: utf8('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + list.map(function (sheet, index) {
          return '<Relationship Id="rId' + (index + 1) + '" Target="worksheets/sheet' + (index + 1) + '.xml" '
            + 'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/>';
        }).join('')
        + '<Relationship Id="rIdStyles" Target="styles.xml" '
        + 'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles"/>'
        + '</Relationships>')},
      {name: 'xl/styles.xml', data: utf8(stylesXml())}
    ];
    list.forEach(function (sheet, index) {
      files.push({name: 'xl/worksheets/sheet' + (index + 1) + '.xml', data: utf8(sheetXml(sheet))});
    });
    return zip(files);
  }

  Statso.xlsx = {build: build, STYLE: STYLE, columnName: columnName, escapeXml: escapeXml, crc32: crc32};
})(window);
