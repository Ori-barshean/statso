(function (root) {
  'use strict';
  const Statso = root.Statso = root.Statso || {};
  const CURRENCIES = ['usd','eur','gbp','chf','jpy','cad','aud','dkk','nok','sek'];

  function dateLiteral(iso) { return '#date(' + iso.split('-').map(Number).join(', ') + ')'; }
  function source(url) { return 'Csv.Document(Web.Contents("' + url + '"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv])'; }
  function rateSteps(url) {
    return [['Source', source(url)],
      ['Promoted', 'Table.PromoteHeaders(Source, [PromoteAllScalars = true])'],
      ['Typed', 'Table.TransformColumnTypes(Promoted, {{"date", type date}, {"rate", type number}}, "en-US")']];
  }
  function generate(selection) {
    // Resolve the shared URLs only when called, after the guides module has loaded.
    const base = Statso.guides.URLS.boi.csv.replace(/[^/]+$/, '');
    const from = selection.from; const to = selection.to;
    let header; let pairs; let columns; let key = 'date';
    const dates = [['From', dateLiteral(from)], ['To', dateLiteral(to)]];
    if (selection.series === 'boi') {
      const url = base + 'boi_interest_rate.csv';
      header = '// statso - Bank of Israel interest rate\n// Source: ' + url + '\n' +
        '// The file records rate CHANGES only, not one row per day. To show the rate in\n' +
        '// force at the start of the range, the last change dated before ' + from + ' is\n' +
        '// carried forward into the result, on top of every change inside the range.';
      columns = ['boi_rate'];
      pairs = dates.concat(rateSteps(url), [
        ['InRange', 'Table.SelectRows(Typed, each [date] >= From and [date] <= To)'],
        ['Earlier', 'Table.Sort(Table.SelectRows(Typed, each [date] < From), {{"date", Order.Ascending}})'],
        ['Carried', 'Table.LastN(Earlier, 1)'],
        ['Combined', 'Table.Combine({Carried, InRange})'],
        ['Sorted', 'Table.Sort(Combined, {{"date", Order.Ascending}})'],
        ['Renamed', 'Table.RenameColumns(Sorted, {{"rate", "boi_rate"}})']]);
    } else if (selection.series === 'cpi') {
      const url = base + 'cpi.csv'; key = 'month'; columns = ['cpi_chained'];
      header = '// statso - Israeli consumer price index (CBS)\n// Source: ' + url + '\n' +
        '// The exported column is chained_1951_09 - the CBS CHAINED index: one continuous\n' +
        '// series across every base change, chained back to the earliest CBS base, the\n' +
        '// September 1951 average. The plain "value" column holds each period\'s figure on\n' +
        '// its own base and is NOT comparable across bases, so it is dropped here. Only\n' +
        '// the RATIO between two months of the chained series is meaningful; the absolute\n' +
        '// level of the number is not.';
      pairs = [['FromMonth', '"' + from.slice(0, 7) + '"'], ['ToMonth', '"' + to.slice(0, 7) + '"'],
        ['Source', source(url)], ['Promoted', 'Table.PromoteHeaders(Source, [PromoteAllScalars = true])'],
        ['Kept', 'Table.SelectColumns(Promoted, {"month", "chained_1951_09"})'],
        ['Typed', 'Table.TransformColumnTypes(Kept, {{"month", type text}, {"chained_1951_09", type number}}, "en-US")'],
        ['Filtered', 'Table.SelectRows(Typed, each [month] >= FromMonth and [month] <= ToMonth)'],
        ['Sorted', 'Table.Sort(Filtered, {{"month", Order.Ascending}})'],
        ['Renamed', 'Table.RenameColumns(Sorted, {{"chained_1951_09", "cpi_chained"}})']];
    } else if (selection.series === 'construction') {
      const url = base + 'construction_inputs.csv'; key = 'month'; columns = ['construction_chained'];
      header = '// statso - Israeli residential construction inputs price index (CBS series 200010)\n// Source: ' + url + '\n' +
        '// The exported column is chained_1950_07 - the CBS CHAINED index: one continuous\n' +
        '// series across every base change, chained back to the earliest CBS base for this\n' +
        '// series, the July 1950 average. The plain "value" column holds each period\'s\n' +
        '// figure on its own base and is NOT comparable across bases, so it is dropped\n' +
        '// here. Only the RATIO between two months of the chained series is meaningful;\n' +
        '// the absolute level of the number is not. The published history starts at\n' +
        '// January 2000 - that is only where publication begins, not the chain base.';
      pairs = [['FromMonth', '"' + from.slice(0, 7) + '"'], ['ToMonth', '"' + to.slice(0, 7) + '"'],
        ['Source', source(url)], ['Promoted', 'Table.PromoteHeaders(Source, [PromoteAllScalars = true])'],
        ['Kept', 'Table.SelectColumns(Promoted, {"month", "chained_1950_07"})'],
        ['Typed', 'Table.TransformColumnTypes(Kept, {{"month", type text}, {"chained_1950_07", type number}}, "en-US")'],
        ['Filtered', 'Table.SelectRows(Typed, each [month] >= FromMonth and [month] <= ToMonth)'],
        ['Sorted', 'Table.Sort(Filtered, {{"month", Order.Ascending}})'],
        ['Renamed', 'Table.RenameColumns(Sorted, {{"chained_1950_07", "construction_chained"}})']];
    } else {
      const currencies = Array.from(new Set(selection.currencies)).filter(function (code) { return CURRENCIES.includes(code); });
      if (!currencies.length) { throw new Error('Choose at least one supported currency.'); }
      const urls = currencies.map(function (code) { return base + 'fx/' + code + '_ils.csv'; });
      columns = currencies.map(function (code) { return code + '_ils'; });
      header = '// statso - Bank of Israel representative exchange rate - ' + currencies.map(function (code) { return code.toUpperCase() + '/ILS'; }).join(', ') + '\n' +
        urls.map(function (url) { return '// Source: ' + url; }).join('\n') + '\n// Rates are published on business days only, so the series has gaps.';
      const filtered = ['Filtered', 'Table.SelectRows(Typed, each [date] >= From and [date] <= To)'];
      if (currencies.length === 1) {
        pairs = dates.concat(rateSteps(urls[0]), [filtered,
          ['Renamed', 'Table.RenameColumns(Filtered, {{"rate", "' + columns[0] + '"}})'],
          ['Sorted', 'Table.Sort(Renamed, {{"date", Order.Ascending}})']]);
      } else {
        const names = currencies.map(function (code) { return code[0].toUpperCase() + code.slice(1); });
        pairs = dates.concat(currencies.map(function (code, index) {
          const inner = rateSteps(urls[index]).concat([filtered]);
          return [names[index], '\n        let\n' + inner.map(function (pair) { return '            ' + pair[0] + ' = ' + pair[1]; }).join(',\n') +
            '\n        in\n            Table.RenameColumns(Filtered, {{"rate", "' + columns[index] + '"}})'];
        }));
        pairs.push(['Spine', 'Table.TransformColumnTypes(Table.FromColumns({List.Sort(List.Distinct(' + names.map(function (name) { return name + '[date]'; }).join(' & ') + '), Order.Ascending)}, {"date"}), {{"date", type date}})']);
        currencies.forEach(function (code, index) {
          const previous = pairs[pairs.length - 1][0];
          pairs.push(['With' + names[index], 'Table.ExpandTableColumn(Table.NestedJoin(' + previous + ', {"date"}, ' + names[index] + ', {"date"}, "' + code + '", JoinKind.LeftOuter), "' + code + '", {"' + columns[index] + '"}, {"' + columns[index] + '"})']);
        });
      }
    }
    if (selection.average) {
      header += '\n// last row: simple arithmetic mean of the rows above; the key cell stays empty';
      const previous = pairs[pairs.length - 1][0];
      const fields = [key + ' = null'].concat(columns.map(function (column) {
        return column + ' = List.Average(List.RemoveNulls(' + previous + '[' + column + ']))';
      }));
      pairs.push(['Average', 'Table.InsertRows(' + previous + ', Table.RowCount(' + previous + '), {[' + fields.join(', ') + ']})']);
    }
    pairs[pairs.length - 1][0] = 'Result';
    return header + '\nlet\n' + pairs.map(function (pair) { return '    ' + pair[0] + ' = ' + pair[1]; }).join(',\n') + '\nin\n    Result';
  }

  function el(id) { return document.getElementById(id); }
  function read() {
    return {series: document.querySelector('input[name="mc-series"]:checked').value,
      currencies: Array.from(document.querySelectorAll('#mc-currencies input:checked')).map(function (box) { return box.value; }),
      from: el('mc-from').value, to: el('mc-to').value, average: el('mc-average').checked};
  }
  function render() {
    const selection = read();
    el('mc-currencies-block').hidden = selection.series !== 'fx';
    let error = '';
    if (!selection.from || !selection.to) { error = 'יש לבחור תאריך התחלה ותאריך סיום.'; }
    else if (selection.from > selection.to) { error = 'תאריך ההתחלה חייב להיות לפני תאריך הסיום.'; }
    else if (selection.series === 'fx' && !selection.currencies.length) { error = 'יש לבחור מטבע אחד לפחות.'; }
    el('mc-error').textContent = error;
    el('mc-code').textContent = error ? '' : generate(selection);
    el('mc-copy').disabled = Boolean(error);
  }
  function legacyCopy(text) {
    const input = document.createElement('textarea'); input.value = text; input.setAttribute('readonly', ''); input.style.position = 'fixed'; input.style.opacity = '0'; document.body.appendChild(input); input.select();
    let ok = false; try { ok = document.execCommand('copy'); } catch (error) { ok = false; } document.body.removeChild(input); return ok;
  }
  function init() {
    const escape = Statso.core.escapeHtml;
    el('mc-currencies').innerHTML = CURRENCIES.map(function (code) {
      const label = Statso.core.CURRENCY_NAMES[code.toUpperCase()];
      return '<label class="fxh-currency"><input type="checkbox" value="' + escape(code) + '"' + (code === 'usd' ? ' checked' : '') + '> <span>' + escape(label) + '</span> <span class="currency-code">' + escape(code.toUpperCase()) + '</span></label>';
    }).join('');
    const today = new Date(); const month = String(today.getMonth() + 1).padStart(2, '0');
    el('mc-from').value = (today.getFullYear() - 3) + '-' + month + '-01';
    el('mc-to').value = today.getFullYear() + '-' + month + '-' + String(today.getDate()).padStart(2, '0');
    document.querySelectorAll('#mcode-view input').forEach(function (input) {
      input.addEventListener('change', render); input.addEventListener('input', render);
    });
    el('mc-copy').addEventListener('click', function () {
      const button = el('mc-copy'); const text = el('mc-code').textContent;
      if (!text) { return; }
      const done = function (ok) {
        if (!ok) { return; }
        const t = function (label) { return Statso.i18n ? Statso.i18n.t(label) : label; };
        button.textContent = t('הועתק'); root.setTimeout(function () { button.textContent = t('העתקת הקוד'); }, 1400);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) { navigator.clipboard.writeText(text).then(function () { done(true); }).catch(function () { done(legacyCopy(text)); }); }
      else { done(legacyCopy(text)); }
    });
    render();
  }
  document.addEventListener('DOMContentLoaded', init);
  Statso.mcode = {generate: generate, read: read, render: render, init: init, CURRENCIES: CURRENCIES};
})(window);
