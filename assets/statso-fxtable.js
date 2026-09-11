(function (root) {
  'use strict';
  const Statso = root.Statso = root.Statso || {};

  function sharedYearEndDate(rates, position) {
    const dates = rates.map(function (row) {
      const entry = row.years && row.years[position];
      return entry && entry.year_end ? entry.year_end.date : null;
    }).filter(Boolean);
    if (!dates.length) { return null; }
    return dates.every(function (date) { return date === dates[0]; }) ? dates[0] : null;
  }

  function headerLabels(doc) {
    return (doc.years || []).map(function (year, position) {
      const shared = sharedYearEndDate(doc.rates || [], position);
      return {end: shared ? 'שער ל־' + Statso.core.formatIsoDateHe(shared) : 'שער סוף ' + year,
        average: 'ממוצע ' + year};
    });
  }

  function cell(value, title) {
    const attribute = title ? ' title="' + Statso.core.escapeHtml(title) + '"' : '';
    return '<td dir="ltr"' + attribute + '>' + (value === null ? '—' : Statso.core.formatRate(value)) + '</td>';
  }

  function buildRow(row, yearCount) {
    const name = Statso.core.escapeHtml(Statso.core.CURRENCY_NAMES[row.code] || row.code);
    const unit = row.unit && row.unit !== 1 ? ' <span class="currency-code">×' + Statso.core.escapeHtml(row.unit) + '</span>' : '';
    let html = '<tr><th scope="row">' + name + ' <span class="currency-code">' + Statso.core.escapeHtml(row.code) + '</span>' + unit + '</th>';
    html += cell(row.latest ? row.latest.rate : null, row.latest ? row.latest.date : '');
    for (let position = 0; position < yearCount; position += 1) {
      const entry = row.years && row.years[position];
      html += cell(entry && entry.year_end ? entry.year_end.rate : null, entry && entry.year_end ? entry.year_end.date : '');
      html += cell(entry ? entry.average : null, entry ? entry.count + ' שערים שפורסמו' : '');
    }
    return html + '</tr>';
  }

  function render(doc) {
    const rates = doc.rates || [];
    if (!rates.length) { throw new Error('טבלת שערי החליפין ריקה'); }
    const labels = headerLabels(doc);
    const heads = ['מטבע', 'שער עדכני'];
    labels.forEach(function (label) { heads.push(label.end); heads.push(label.average); });
    document.getElementById('fx-table-head').innerHTML = heads.map(function (text) {
      return '<th scope="col">' + Statso.core.escapeHtml(text) + '</th>';
    }).join('');
    document.getElementById('fx-table-body').innerHTML = rates.map(function (row) {
      return buildRow(row, labels.length);
    }).join('');
    document.getElementById('fx-table-note').textContent =
      'שערים יציגים של בנק ישראל מול השקל החדש. שער סוף שנה הוא השער האחרון שפורסם באותה שנה, והממוצע הוא ממוצע כל השערים שפורסמו בה. ×100 מציין ציטוט ל־100 יחידות מטבע.';
  }

  function init(doc) {
    render(doc);
    Statso.data.setState(document.getElementById('fx-table-section'), 'ready');
  }

  Statso.fxtable = {sharedYearEndDate: sharedYearEndDate, headerLabels: headerLabels, buildRow: buildRow,
    render: render, init: init};
})(window);
