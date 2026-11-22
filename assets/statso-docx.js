(function (root) {
  'use strict';
  const Statso = root.Statso = root.Statso || {};
  const MIME = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
  const W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main';
  const R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships';
  const XML = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>';

  // Only XML 1.0 characters, including supplementary Unicode characters.
  function escape(text) {
    return Statso.xlsx.escapeXml(Array.from(String(text == null ? '' : text)).filter(function (ch) {
      const n = ch.codePointAt(0);
      return n === 9 || n === 10 || n === 13 || (n >= 32 && n <= 0xd7ff)
        || (n >= 0xe000 && n <= 0xfffd) || (n >= 0x10000 && n <= 0x10ffff);
    }).join(''));
  }

  function build(options) {
    const rtl = Boolean(options.rtl);
    const language = options.language || (rtl ? 'he-IL' : 'en-GB');
    const lang = '<w:lang w:val="' + escape(language) + '" w:bidi="he-IL"/>';
    // No explicit alignment: Word reads left/right in a bidi paragraph as start/end, so the paragraph direction decides.
    function paragraph(text, style, numeric, bold) {
      return '<w:p><w:pPr>' + (style ? '<w:pStyle w:val="' + style + '"/>' : '')
        + (style && style !== 'Normal' ? '<w:keepNext/>' : '') + (rtl ? '<w:bidi/>' : '')
        + '<w:spacing w:after="100"/></w:pPr>'
        + '<w:r><w:rPr>' + (bold ? '<w:b/><w:bCs/>' : '')
        + (rtl && !numeric ? '<w:rtl/>' : '') + lang + '</w:rPr><w:t xml:space="preserve">'
        + escape(text) + '</w:t></w:r></w:p>';
    }
    function table(block) {
      const count = block.head.length;
      const widths = block.widths && block.widths.length === count ? block.widths : Array(count).fill(1);
      const sum = widths.reduce(function (a, b) { return a + b; }, 0);
      const twips = widths.map(function (w) { return Math.round(9638 * w / sum); });
      let xml = '<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/>' + (rtl ? '<w:bidiVisual/>' : '')
        + '<w:tblW w:w="5000" w:type="pct"/><w:tblLook w:val="04A0" w:firstRow="1" w:lastRow="0" w:firstColumn="0" w:lastColumn="0" w:noHBand="0" w:noVBand="1"/>'
        + '<w:tblCaption w:val="' + escape(block.caption || '') + '"/></w:tblPr><w:tblGrid>'
        + twips.map(function (w) { return '<w:gridCol w:w="' + w + '"/>'; }).join('') + '</w:tblGrid>';
      [block.head].concat(block.rows || []).forEach(function (row, index) {
        xml += '<w:tr>' + (index === 0 ? '<w:trPr><w:tblHeader/></w:trPr>' : '');
        for (let i = 0; i < count; i += 1) {
          const cell = row[i] == null ? '' : row[i];
          const obj = typeof cell === 'object' ? cell : {text: cell, numeric: typeof cell === 'number'};
          xml += '<w:tc><w:tcPr><w:tcW w:w="' + twips[i] + '" w:type="dxa"/></w:tcPr>'
            + paragraph(obj.text, 'Normal', obj.numeric, index === 0) + '</w:tc>';
        }
        xml += '</w:tr>';
      });
      return xml + '</w:tbl>';
    }
    const blocks = options.blocks || [];
    let body = blocks.map(function (block) {
      return block.type === 'table' ? table(block) : paragraph(block.text,
        block.type === 'title' ? 'Title' : block.type === 'heading' ? (block.level === 2 ? 'Heading2' : 'Heading1') : 'Normal');
    }).join('');
    // Word requires a paragraph after a table that ends the body
    if (blocks.length && blocks[blocks.length - 1].type === 'table') { body += paragraph('', 'Normal'); }
    const documentXml = XML + '<w:document xmlns:w="' + W + '" xmlns:r="' + R + '"><w:body>' + body
      + '<w:sectPr><w:footerReference w:type="default" r:id="rIdFooter"/><w:pgSz w:w="11906" w:h="16838"/>'
      + '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134" w:header="567" w:footer="567" w:gutter="0"/>'
      + (rtl ? '<w:bidi/>' : '') + '</w:sectPr></w:body></w:document>';
    let styles = XML + '<w:styles xmlns:w="' + W + '"><w:docDefaults><w:rPrDefault><w:rPr>'
      + '<w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/><w:sz w:val="20"/><w:szCs w:val="20"/>' + lang
      + '</w:rPr></w:rPrDefault><w:pPrDefault><w:pPr>' + (rtl ? '<w:bidi/>' : '') + '</w:pPr></w:pPrDefault></w:docDefaults>';
    ['Normal', 'Title', 'Heading1', 'Heading2'].forEach(function (name, i) {
      styles += '<w:style w:type="paragraph" w:styleId="' + name + '"' + (i === 0 ? ' w:default="1"' : '') + '><w:name w:val="' + name + '"/>'
        + (i ? '<w:basedOn w:val="Normal"/><w:next w:val="Normal"/>' : '') + '<w:qFormat/>'
        + '<w:pPr>' + (i ? '<w:keepNext/>' : '') + (rtl ? '<w:bidi/>' : '')
        + (i >= 2 ? '<w:outlineLvl w:val="' + (i - 2) + '"/>' : '') + '</w:pPr><w:rPr>'
        + (i ? '<w:b/><w:bCs/><w:sz w:val="' + (i === 1 ? 32 : 24) + '"/><w:szCs w:val="' + (i === 1 ? 32 : 24) + '"/>' : '')
        + (rtl ? '<w:rtl/>' : '') + lang + '</w:rPr></w:style>';
    });
    styles += '<w:style w:type="table" w:styleId="TableGrid"><w:name w:val="Table Grid"/><w:tblPr><w:tblBorders>'
      + ['top', 'left', 'bottom', 'right', 'insideH', 'insideV'].map(function (side) {
        return '<w:' + side + ' w:val="single" w:sz="4" w:color="64748B"/>';
      }).join('') + '</w:tblBorders></w:tblPr></w:style></w:styles>';
    const stamp = new Date(options.created == null ? Date.now() : options.created).toISOString();
    const core = XML + '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
      + '<dc:title>' + escape(options.title) + '</dc:title><dc:language>' + escape(language) + '</dc:language><dc:creator>statso</dc:creator>'
      + '<dcterms:created xsi:type="dcterms:W3CDTF">' + stamp + '</dcterms:created></cp:coreProperties>';
    const relStart = XML + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">';
    const parts = {
      '[Content_Types].xml': XML + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
        + [['word/document.xml', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml'],
          ['word/styles.xml', 'application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml'],
          ['word/footer1.xml', 'application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml'],
          ['docProps/core.xml', 'application/vnd.openxmlformats-package.core-properties+xml']].map(function (pair) {
          return '<Override PartName="/' + pair[0] + '" ContentType="' + pair[1] + '"/>';
        }).join('') + '</Types>',
      '_rels/.rels': relStart + '<Relationship Id="rIdDocument" Type="' + R + '/officeDocument" Target="word/document.xml"/><Relationship Id="rIdCore" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/></Relationships>',
      'word/document.xml': documentXml,
      'word/styles.xml': styles,
      'word/footer1.xml': XML + '<w:ftr xmlns:w="' + W + '">' + paragraph(options.footer || '', 'Normal') + '</w:ftr>',
      'word/_rels/document.xml.rels': relStart + '<Relationship Id="rIdStyles" Type="' + R + '/styles" Target="styles.xml"/><Relationship Id="rIdFooter" Type="' + R + '/footer" Target="footer1.xml"/></Relationships>',
      'docProps/core.xml': core
    };
    return Statso.xlsx.zip(Object.keys(parts).map(function (name) { return {name: name, data: Statso.xlsx.utf8(parts[name])}; }));
  }
  Statso.docx = {build: build, MIME: MIME};
})(window);
