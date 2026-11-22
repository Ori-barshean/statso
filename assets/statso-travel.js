(function (root) {
  'use strict';
  const Statso = root.Statso = root.Statso || {};
  const CAPS = {
    2018: {"lodging7": 278, "floor": 122, "max": 208.5, "perDiemLodging": 78, "perDiemNoLodging": 130, "car": 61, "gift": 15, "note": "בשנת 2018 המקסימום ללילות 8–90 (208.5 דולר) נגזר כ־75% מתקרת 7 הלילות הראשונים, במקום 200 דולר שמופיע בטופס. רשימת המדינות עם תוספת 25% לקוחה מטופס 2019, כי בטופס 2018 אין רשימה."},
    2019: {"lodging7": 284, "floor": 125, "max": 213, "perDiemLodging": 80, "perDiemNoLodging": 133, "car": 62, "gift": 15, "note": null},
    2020: {"lodging7": 289, "floor": 127, "max": 216.75, "perDiemLodging": 81, "perDiemNoLodging": 136, "car": 64, "gift": 15, "note": "בשנת 2020 המקסימום ללילות 8–90 (216.75 דולר) נגזר כ־75% מתקרת 7 הלילות הראשונים, ואין לשנה זו טופס מילולי."},
    2021: {"lodging7": 293, "floor": 129, "max": 220, "perDiemLodging": 82, "perDiemNoLodging": 137, "car": 64, "gift": 15, "note": "בשנת 2021 התקרות נלקחו מטקסט ההסבר בתבנית האקסל, ואין לשנה זו טופס מילולי."},
    2022: {"lodging7": 313, "floor": 137, "max": 235, "perDiemLodging": 88, "perDiemNoLodging": 147, "car": 69, "gift": 15, "note": null},
    2023: {"lodging7": 335, "floor": 147, "max": 251, "perDiemLodging": 94, "perDiemNoLodging": 157, "car": 69, "gift": 15, "note": null},
    2024: {"lodging7": 346, "floor": 152, "max": 259.5, "perDiemLodging": 97, "perDiemNoLodging": 162, "car": 76, "gift": 15, "note": "בשנת 2024 המקסימום ללילות 8–90 (259.5 דולר) נגזר כ־75% מתקרת 7 הלילות הראשונים, במקום 346 דולר שמופיע בטופס."},
    2025: {"lodging7": 355, "floor": 156, "max": 266.25, "perDiemLodging": 100, "perDiemNoLodging": 167, "car": 78, "gift": 15, "note": "בשנת 2025 תקרת 7 הלילות הראשונים למדינה רגילה (355 דולר) נגזרה מהערך 443.75 דולר שבטופס, שהוא הערך הכולל תוספת 25%."},
    2026: {"lodging7": 365, "floor": 160, "max": 273.75, "perDiemLodging": 102, "perDiemNoLodging": 171, "car": 80, "gift": 15, "note": null},
  };
  const YEARS = Object.keys(CAPS).map(Number).sort(function (a, b) { return a - b; });
  const COUNTRIES = ["אוסטריה", "אוסטרליה", "איטליה", "איסלנד", "אירלנד", "אנגולה", "בלגיה", "גרמניה", "דובאי", "דנמרק", "הולנד", "הונג קונג", "אנגליה/בריטניה", "טיוואן", "יוון", "יפן", "לוקסמבורג", "נורווגיה", "ספרד", "עומאן", "פינלנד", "צרפת", "קטאר", "קוריאה", "קמרון", "קנדה", "שבדיה", "שוויץ"];
  const LABELS = {"flight": "טיסה", "insurance": "ביטוח", "lodging7": "לינה — 7 הלילות הראשונים", "lodging90": "לינה — לילות 8–90", "perDiem": "אש״ל", "car": "השכרת רכב", "transport": "תחבורה ציבורית", "phone": "טלפון", "gifts": "מתנות", "hosting": "אירוח תושב חוץ", "other": "אחרות"};
  const DISCLAIMER = "הכלי מסייע בחישוב משוער של הוצאות נסיעה לחו״ל לפי התקרות והכללים שבטפסי הדיווח לשנות המס, ואינו מהווה ייעוץ מס, חשבונאי או משפטי. בחלק מהשנים תקרה אחת או יותר נגזרה בחישוב ואינה מופיעה במפורש במקור, והדבר מסומן בדוח. לפני מילוי הדוח ואחריו, ובכל מקרה לפני הגשה או הכרה בהוצאה, יש להיוועץ ברואה חשבון או ביועץ מס מוסמך ולאמת מולו את הנתונים, התקרות ותוצאות החישוב. האחריות לנתונים שהוזנו ולשימוש בתוצאות היא של המשתמש.";
  const SHORT = "אינו ייעוץ מס. יש לאמת את הנתונים, התקרות והתוצאות מול רואה חשבון או יועץ מס מוסמך לפני המילוי ואחריו.";
  const FLIGHT = "! שימו לב: במחלקה ראשונה מוכר רק עד מחיר מחלקת עסקים באותה טיסה; הכלי אינו מגביל זאת.";
  const CURRENCY = "אם הנסיעה הייתה במטבע שאינו אחד מהמטבעות הנתמכים באתר, יש להזין את הסכומים בש״ח לאחר המרה.";
  const EDUCATION = "חינוך ילדים בנסיעה מעל 10 חודשים אינו מחושב: לא צוינה תקרה בחומר המקור.";
  const KEYS = Object.keys(LABELS);
  const CODES = ['USD', 'EUR', 'GBP', 'CHF', 'JPY', 'CAD', 'AUD', 'DKK', 'NOK', 'SEK', 'ILS'];
  const HEAD = ['הוצאה', 'סכום במט״ח', 'מטבע', 'סכום בש״ח', 'תקרה בש״ח', 'הוצאה מוכרת', 'סכום לתיאום', 'הסבר'];
  function say(text) { return Statso.i18n ? Statso.i18n.t(text) : text; }
  function el(id) { return document.getElementById(id); }
  function esc(text) { return Statso.xlsx.escapeXml(text); }
  function dateValue(value) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value || '')) { return NaN; }
    const time = Date.parse(value + 'T00:00:00Z');
    return Number.isFinite(time) && new Date(time).toISOString().slice(0, 10) === value ? time : NaN;
  }
  function daysBetween(start, end) { return (dateValue(end) - dateValue(start)) / 86400000 + 1; }
  function number(value) { return new Intl.NumberFormat('en-GB', {minimumFractionDigits: 2, maximumFractionDigits: 2}).format(value); }
  function exact(value) { return String(Number(value.toPrecision(14))); }
  function roundTotal(value) {
    // 14 significant digits absorb the binary noise of a long sum (12455.624999999998), then a decimal shift
    // avoids the multiplication error at values such as 1.005: one half-up rounding of the exact amount.
    const parts = String(Number(value.toPrecision(14))).split('e');
    return Number(Math.round(Number(parts[0] + 'e' + (Number(parts[1] || 0) + 2))) + 'e-2');
  }
  function dateText(date) { return date ? date.split('-').reverse().join('/') : '—'; }
  function yearNote(input) {
    return input.depart && input.ret && (Number(input.depart.slice(0, 4)) !== Number(input.year) || Number(input.ret.slice(0, 4)) !== Number(input.year))
      ? 'שימו לב: שנת תאריך היציאה או החזרה שונה משנת המס שנבחרה (' + input.year + '). התקרות נקבעות לפי שנת המס שנבחרה בלבד.' : '';
  }
  function daysNote(b, total) {
    return Number.isInteger(b) && b >= 1 && b < total ? 'הימים העסקיים (' + b + ') פחותים מסך ימי הנסיעה (' + total + ').' : '';
  }
  function staleNote(code, date) {
    return 'שימו לב: אין שער בטווח 7 ימים מתאריך היציאה עבור ' + code + '. נעשה שימוש בשער האחרון שפורסם ל־' + dateText(date) + '.';
  }
  function rateText(q) {
    if (q.code === 'ILS') { return 'שקל חדש (ILS): 1 ₪ ליחידה.'; }
    const unit = q.unit || 1;
    return (Statso.core.CURRENCY_NAMES[q.code] || q.code) + ' (' + q.code + '): ' + exact(q.rate * unit)
      + (unit === 1 ? ' ₪ ליחידה' : ' ₪ ל־' + unit + ' יחידות') + ' — שער יציג שפורסם ל־' + dateText(q.date);
  }

  // Pure calculation: quotes are already ILS per one currency unit. No DOM or rounding of rows.
  function calculate(input, quote) {
    const result = {ok: false, errors: [], totalDays: daysBetween(input.depart, input.ret), nights: 0, rows: [], totals: {}, notes: [], rates: []};
    function error(message, fields) { result.errors.push({message: message, fields: fields}); }
    const caps = CAPS[input.year], B = Number(input.businessDays), K = Number(input.lodgingDays);
    const N = Array.isArray(input.travelers) ? input.travelers.length : Number(input.travelers);
    const L = input.partial ? K : B, m = input.listed ? 1.25 : 1;
    result.nights = L;
    if (!caps) { error('יש לבחור שנת מס מהרשימה.', ['tt-year']); }
    if (!Number.isFinite(dateValue(input.depart))) { error('יש להזין תאריך יציאה תקין.', ['tt-depart']); }
    if (!Number.isFinite(dateValue(input.ret))) { error('יש להזין תאריך חזרה תקין.', ['tt-return']); }
    if (result.totalDays < 1) { error('תאריך החזרה חייב להיות בתאריך היציאה או אחריו.', ['tt-depart', 'tt-return']); }
    // the range of business days is only meaningful once the dates are: without them the date errors say it all
    const dated = Number.isFinite(result.totalDays) && result.totalDays >= 1;
    const daysOk = dated && Number.isInteger(B) && B >= 1 && B <= result.totalDays;
    if (dated && !daysOk) { error('מספר הימים העסקיים חייב להיות שלם בטווח 1 עד ' + result.totalDays + '.', ['tt-business-days']); }
    if (input.partial && daysOk) {
      if (B <= 1) { error('יש יום עסקי אחד בלבד, ולכן אי אפשר לחלק אותו לימים עם לינה ובלי לינה. יש לבטל את הסימון בתיבה או להגדיל את מספר הימים העסקיים.', ['tt-lodging-days']); }
      else if (K > B - 1) { error('מספר ימי הלינה לא יעלה על ' + (B - 1), ['tt-lodging-days']); }
      else if (!Number.isInteger(K) || K < 1) { error('מספר ימי הלינה חייב להיות מספר שלם וחיובי.', ['tt-lodging-days']); }
    }
    if (!Number.isInteger(N) || N < 1) { error('נדרש נוסע אחד לפחות.', ['tt-add-traveler']); }
    const amounts = {};
    KEYS.forEach(function (key) {
      const row = (input.rows || {})[key] || {amount: 0, currency: 'USD'};
      const amount = row.amount === '' ? 0 : Number(row.amount);
      amounts[key] = {amount: amount, currency: row.currency || 'USD'};
      if (!Number.isFinite(amount) || amount < 0) { error('יש להזין סכום תקין שאינו שלילי בשורה ' + LABELS[key] + '.', ['tt-' + key + '-amount']); }
      if (!CODES.includes(amounts[key].currency)) { error('יש לבחור מטבע נתמך בשורה ' + LABELS[key] + '.', ['tt-' + key + '-currency']); }
    });
    if (result.errors.length) { return result; }
    const quotes = {};
    ['USD'].concat(KEYS.filter(function (key) { return amounts[key].amount > 0; }).map(function (key) { return amounts[key].currency; })).forEach(function (code) {
      if (quotes[code]) { return; }
      const q = code === 'ILS' ? {ok: true, rate: 1, date: null, unit: 1} : quote(code);
      quotes[code] = q || {ok: false};
      if (!q || !q.ok || !Number.isFinite(q.rate) || q.rate <= 0) {
        error('אין שער עבור ' + code + ' בתאריך היציאה או לפניו.', ['tt-depart']); return;
      }
      result.rates.push(Object.assign({}, q, {code: code}));
      if (q.date && daysBetween(q.date, input.depart) - 1 > 7) { result.notes.push(staleNote(code, q.date)); }
    });
    if (result.errors.length) { return result; }
    const usd = quotes.USD.rate;
    const extra = input.listed ? ' (כולל תוספת 25%)' : '';
    const tail = function (total) { return ' = ' + exact(total) + ' דולר · לפי שער ' + exact(usd) + ' = ' + number(total * usd) + ' ₪.'; };
    const first = amounts.lodging7, later = amounts.lodging90;
    const hasLodging = first.amount > 0 || later.amount > 0;
    const rows = KEYS.filter(function (key) { return L <= 90 || key !== 'lodging90'; });
    rows.forEach(function (sourceKey) {
      const row = amounts[sourceKey];
      let key = sourceKey, label = LABELS[key], amount = row.amount, currency = row.currency;
      let ils = amount === 0 ? 0 : amount * quotes[currency].rate;
      let cap = ils, explain = 'מוכר במלואו לפי קבלות, ללא תקרה.';
      if (key === 'lodging7' && L > 90) {
        key = 'lodgingAll'; label = 'לינה — כל הלילות (מעל 90 לילות)';
        ils += later.amount === 0 ? 0 : later.amount * quotes[later.currency].rate;
        // one amount in one currency: the entered pair when only one row has a sum or both share a currency, else shekels
        if (later.amount === 0) { /* the first row's amount and currency stand */ }
        else if (amount === 0) { amount = later.amount; currency = later.currency; }
        else if (currency === later.currency) { amount += later.amount; }
        else { amount = ils; currency = 'ILS'; }
        const f = caps.floor * m, total = f * L * N;
        cap = total * usd;
        explain = 'מעל 90 לילות: כל הלילות, מהלילה הראשון, לפי ' + exact(f) + ' דולר ללילה' + extra
          + ' (תקרת הסף ללילות 8–90 בשנת ' + input.year + ') · לילות: ' + L + ' · נוסעים: ' + N + tail(total);
      } else if (key === 'lodging7') {
        const c = caps.lodging7 * m, nights = Math.min(L, 7), total = c * nights * N;
        cap = total * usd;
        explain = 'תקרה: ' + exact(c) + ' דולר ללילה' + extra + ' · לילות: ' + nights + ' · נוסעים: ' + N + tail(total);
      } else if (key === 'lodging90') {
        const nights = Math.max(0, Math.min(L, 90) - 7), f = caps.floor * m, max = caps.max * m;
        if (!amount) { cap = null; explain = 'לא הוזן סכום.'; }
        else if (!nights) {
          cap = 0; explain = 'אין לילות בטווח 8–90 (סה״כ לילות: ' + L + '), ולכן אין הכרה בשורה זו.';
        } else {
          const x = ils / usd / (nights * N), p = .75 * x, a = Math.min(max, Math.max(f, p));
          if (x <= f) {
            cap = ils;
            explain = 'ממוצע ללילה לנוסע ' + exact(x) + ' דולר, עד הסף של ' + exact(f) + ' דולר' + extra + ' — מוכר במלואו.';
          } else {
            cap = a * nights * N * usd;
            explain = 'ממוצע ללילה לנוסע ' + exact(x) + ' דולר, מעל הסף של ' + exact(f) + ' דולר' + extra
              + ': 75% הם ' + exact(p) + ' דולר; בגבולות ' + exact(f) + '–' + exact(max) + ' דולר מוכרים ' + exact(a)
              + ' דולר ללילה · לילות: ' + nights + ' · נוסעים: ' + N + tail(a * nights * N);
          }
        }
      } else if (key === 'perDiem') {
        const low = caps.perDiemLodging * m, high = caps.perDiemNoLodging * m;   // the rates as the sentence shows them: already with the uplift
        const total = (input.partial ? K * caps.perDiemLodging + (B - K) * caps.perDiemNoLodging
          : B * (hasLodging ? caps.perDiemLodging : caps.perDiemNoLodging)) * m * N;
        cap = total * usd;
        explain = input.partial ? 'ימים עם לינה: ' + K + ' · ' + exact(low) + ' דולר; ימים בלי לינה: ' + (B - K) + ' · ' + exact(high) + ' דולר' + extra
          : 'ימים: ' + B + ' · ' + exact(hasLodging ? low : high) + ' דולר ליום (' + (hasLodging ? 'עם הוצאות לינה' : 'בלי הוצאות לינה') + ')' + extra;
        explain += ' · נוסעים: ' + N + tail(total);
      } else if (key === 'car') {
        const total = caps.car * m * B * N;
        cap = total * usd;
        explain = 'תקרה: ' + exact(caps.car * m) + ' דולר ליום' + extra + ' · ימים: ' + B + ' · נוסעים: ' + N + tail(total);
      } else if (key === 'gifts') {
        cap = caps.gift * N * usd;
        explain = 'תקרה: ' + exact(caps.gift) + ' דולר לאדם · נוסעים: ' + N + tail(caps.gift * N).slice(0, -1) + ' (ללא תוספת 25%).';
      }
      const recognized = cap === null ? ils : Math.min(ils, cap);
      result.rows.push({key: key, label: label, amount: amount, currency: currency, ils: ils, cap: cap,
        recognized: recognized, adjust: Math.max(ils - (cap === null ? ils : cap), 0), explain: explain});
    });
    ['ils', 'recognized', 'adjust'].forEach(function (key) {
      result.totals[key] = roundTotal(result.rows.reduce(function (sum, row) { return sum + row[key]; }, 0));
    });
    [caps.note, yearNote(input), daysNote(B, result.totalDays), FLIGHT, EDUCATION, CURRENCY].filter(Boolean).forEach(function (note) { result.notes.push(note); });
    result.ok = true;
    return result;
  }

  const state = {fx: null, pending: false, failed: false, touched: false, businessTouched: false, model: null, serial: 0};
  function travelerRows() { return Array.from(el('tt-travelers').querySelectorAll('.rent-option')); }
  function travelerHtml() {
    state.serial += 1;
    const title = 'tt-person-title-' + state.serial, button = 'tt-person-remove-' + state.serial;
    return '<div class="rent-option" role="group" aria-labelledby="' + title + '">'
      + '<p class="rent-option-title" id="' + title + '"></p>'
      + '<label>שם הנוסע (אופציונלי)<input class="tt-name" type="text" autocomplete="name"></label>'
      + '<label>תפקיד (אופציונלי)<input class="tt-role" type="text" autocomplete="organization-title"></label>'
      + '<button type="button" class="btn-ghost tt-remove" id="' + button + '" aria-labelledby="' + button + ' ' + title + '">הסר נוסע</button></div>';
  }
  function renumber() {
    const rows = travelerRows();
    rows.forEach(function (row, i) {
      row.querySelector('.rent-option-title').textContent = say('נוסע ' + (i + 1));
      row.querySelector('.tt-remove').hidden = rows.length === 1;
    });
    el('tt-traveler-count').textContent = say('מספר הנוסעים: ' + rows.length + '.');
  }
  function addTraveler(interactive) {
    const host = el('tt-travelers');
    host.insertAdjacentHTML('beforeend', travelerHtml());
    const row = host.lastElementChild;
    row.querySelector('.tt-remove').addEventListener('click', function () {
      const rows = travelerRows(), index = rows.indexOf(row);
      if (rows.length <= 1) { return; }
      row.remove(); renumber(); state.touched = true; compute();
      const remaining = travelerRows();
      remaining[Math.min(index, remaining.length - 1)].querySelector('.tt-name').focus();
      Statso.exporter.announce(say('נוסע ' + (index + 1) + ' הוסר. מספר הנוסעים: ' + remaining.length + '.'));
    });
    renumber();
    if (Statso.i18n) { Statso.i18n.apply(row); }
    if (interactive) {
      state.touched = true; compute(); row.querySelector('.tt-name').focus();
      const n = travelerRows().length;
      Statso.exporter.announce(say('נוסע ' + n + ' נוסף. מספר הנוסעים: ' + n + '.'));
    }
  }
  function readForm() {
    const rows = {};
    KEYS.forEach(function (key) {
      const amount = el('tt-' + key + '-amount');
      rows[key] = {amount: amount.validity && amount.validity.badInput ? NaN : amount.value, currency: el('tt-' + key + '-currency').value};
    });
    return {year: Number(el('tt-year').value), listed: el('tt-country').value !== 'other',
      depart: el('tt-depart').value, ret: el('tt-return').value, businessDays: Number(el('tt-business-days').value),
      partial: el('tt-partial').checked, lodgingDays: Number(el('tt-lodging-days').value), rows: rows,
      travelers: travelerRows().map(function (row) { return {name: row.querySelector('.tt-name').value, role: row.querySelector('.tt-role').value}; }),
      company: el('tt-company').value, account: el('tt-account').value, purpose: el('tt-purpose').value,
      country: el('tt-country').value === 'other' ? el('tt-country-other').value : COUNTRIES[Number(el('tt-country').value)],
      other: el('tt-other-desc').value};
  }
  function quoteAt(code, date) {
    if (code === 'ILS') { return {ok: true, rate: 1, unit: 1, date: null}; }
    const entry = state.fx && state.fx.currencies[code];
    if (!entry) { return {ok: false}; }
    const found = Statso.core.lookupRateAt(entry.dates, entry.rates, date);
    return {ok: found.ok, rate: found.rate / entry.unit, unit: entry.unit, date: found.date};
  }
  // A live region or alert announces whatever is written into it, even the same words again, so every write
  // here goes through a comparison: an unchanged message is left alone while the visitor keeps typing.
  const written = {};
  function setText(id, text) {
    const shown = say(text), node = el(id);
    if (node.textContent !== shown) { node.textContent = shown; }
  }
  function setHtml(id, html) {
    if (written[id] !== html) { written[id] = html; el(id).innerHTML = html; }
  }
  function showError(message, fields) {
    setText('tt-error', message);
    Statso.core.flagFields('tt-error', fields || []);
  }
  function matrix(model) {
    return model.rows.map(function (row) { return [row.label, row.amount, row.currency, row.ils, row.cap === null ? '—' : row.cap, row.recognized, row.adjust, row.explain]; });
  }
  function totalRow(model) { return ['סה״כ', '—', '—', model.totals.ils, '—', model.totals.recognized, model.totals.adjust, '']; }
  function renderCells(values, row, form) {
    return values.map(function (value, i) {
      const tag = i === 0 ? 'th scope="row"' : 'td' + (i === 7 ? ' class="travel-explain"' : '');
      let text = esc(typeof value === 'number' ? number(value) : say(value));
      if (row && i === 7 && row.key === 'flight') { text += '<p>' + esc(say(FLIGHT)) + '</p>'; }
      if (row && i === 7 && row.key === 'other' && form.other) { text += '<p><span dir="auto" data-i18n-skip>' + esc(form.other) + '</span></p>'; }
      return '<' + tag + (typeof value === 'number' ? ' dir="ltr"' : '') + '>' + text + '</' + (i === 0 ? 'th' : 'td') + '>';
    }).join('');
  }
  function compute() {
    const total = daysBetween(el('tt-depart').value, el('tt-return').value);
    if (!state.businessTouched) { el('tt-business-days').value = total > 0 ? String(total) : ''; }
    setText('tt-total-days', 'סה״כ ימי הנסיעה: ' + (total > 0 ? total : '—') + '.');
    el('tt-country-other-wrap').hidden = el('tt-country').value !== 'other';
    el('tt-lodging-days-wrap').hidden = !el('tt-partial').checked;
    const form = readForm();
    el('tt-business-days').max = total > 0 ? String(total) : '';
    el('tt-lodging-days').max = String(Math.max(0, form.businessDays - 1));
    setText('tt-year-note', yearNote(form));
    setText('tt-days-note', daysNote(form.businessDays, total));
    state.model = null;
    if (!state.fx) {
      setHtml('tt-rates', '<p>' + esc(say(state.failed ? 'לא ניתן לטעון את שערי החליפין.' : 'טוען שערי חליפין…')) + '</p>');
      el('tt-output').hidden = true;
      showError('');
      return;
    }
    if (!state.touched) { setHtml('tt-rates', ''); el('tt-output').hidden = true; showError(''); return; }
    const model = calculate(form, function (code) { return quoteAt(code, form.depart); });
    setHtml('tt-rates', model.rates.map(function (q) { return '<p>' + esc(say(rateText(q))) + '</p>'; }).join('')
      + model.notes.filter(function (note) { return note.indexOf('שימו לב: אין שער') === 0; }).map(function (note) { return '<p>' + esc(say(note)) + '</p>'; }).join(''));
    if (!model.ok) {
      // One sentence per error, so that each complete sentence can be translated.
      showError(model.errors.map(function (error) { return say(error.message); }).join(' '), model.errors.flatMap(function (error) { return error.fields; }));
      el('tt-output').hidden = true;
      return;
    }
    showError('');
    state.model = model; model.form = form;
    el('tt-summary').innerHTML = [['סה״כ סכום שולם (בש״ח)', model.totals.ils], ['סה״כ הוצאה מוכרת', model.totals.recognized], ['סה״כ סכום לתיאום', model.totals.adjust]].map(function (pair) {
      return '<div class="rent-summary-card"><span>' + esc(say(pair[0])) + '</span><strong dir="ltr">' + number(pair[1]) + '</strong><small>₪</small></div>';
    }).join('');
    el('tt-body').innerHTML = matrix(model).map(function (values, i) { return '<tr>' + renderCells(values, model.rows[i], form) + '</tr>'; }).join('');
    el('tt-foot').innerHTML = '<tr>' + renderCells(totalRow(model)) + '</tr>';
    el('tt-notes').innerHTML = model.notes.map(function (note) { return '<li>' + esc(say(note)) + '</li>'; }).join('');
    el('tt-output').hidden = false;
  }
  function ensureFx() {
    if (root.location.hash !== '#/accounting/travel' || state.fx || state.pending) { return; }
    state.pending = true; state.failed = false; compute();
    Statso.data.loadFxDaily().then(function (doc) {
      state.fx = doc; state.pending = false; compute();
    }).catch(function () { state.pending = false; state.failed = true; compute(); });
  }
  function raw(value) { return {v: value || '—', raw: true}; }
  function details(model) {
    const f = model.form;
    return [['שנת מס', String(f.year)], ['שם החברה/העסק (אופציונלי)', raw(f.company)], ['כרטיס בהנהלת החשבונות (אופציונלי)', raw(f.account)],
      ['מטרת הנסיעה (אופציונלי)', raw(f.purpose)], ['יעד', f.listed ? f.country : raw(f.country || say('מדינה אחרת'))],
      ['תאריך יציאה', dateText(f.depart)], ['תאריך חזרה', dateText(f.ret)], ['סה״כ ימים', String(model.totalDays)],
      ['ימים עסקיים', String(f.businessDays)], ['לילות לינה', String(model.nights)], ['מספר נוסעים', String(f.travelers.length)],
      ['תיאור הוצאות אחרות (אופציונלי)', raw(f.other)]];
  }
  function exportTravel(kind) {
    if (!state.model) { return; }
    const model = state.model, exporter = Statso.exporter;
    const filename = 'statso-' + say('דו״ח נסיעה לחו״ל') + '-' + exporter.stamp();
    const travelers = model.form.travelers.map(function (person, i) { return [say('נוסע ' + (i + 1)), raw(person.name), raw(person.role)]; });
    const tables = [
      {caption: 'פרטי הנסיעה', head: ['פריט', 'ערך'], rows: details(model)},
      {caption: 'נוסעים', head: ['נוסע', 'שם', 'תפקיד'], rows: travelers},
      {caption: 'שערי חליפין', head: ['שער'], rows: model.rates.map(function (q) { return [rateText(q)]; })},
      {caption: 'חישוב ההוצאות', head: HEAD, rows: matrix(model).map(function (row, i) {
        if (model.rows[i].key === 'flight') { row[7] = say(row[7]) + ' ' + say(FLIGHT); }
        return row;
      }).concat([totalRow(model)])}
    ];
    if (kind === 'xlsx') {
      const S = Statso.xlsx.STYLE;
      function cells(row, style) { return row.map(function (value) {
        return typeof value === 'object' && value !== null ? {v: value.v, raw: value.raw, s: style || S.boxed}
          : {v: value, s: style || (typeof value === 'number' ? S.money : S.boxed)};
      }); }
      const first = {name: 'פרטי הנסיעה', freezeRows: 3, columns: [{width: 35}, {width: 55}, {width: 30}],
        rows: [[{v: say('דו״ח נסיעה לחו״ל'), s: S.title}], [SHORT], cells(tables[0].head, S.header)].concat(tables[0].rows.map(function (row) { return cells(row); }))};
      tables.slice(1, 3).forEach(function (table) {
        first.rows.push([say(table.caption)], cells(table.head, S.header));
        table.rows.forEach(function (row) { first.rows.push(cells(row)); });
      });
      const last = tables[3];
      const second = {name: 'חישוב ההוצאות', freezeRows: 3, columns: [30, 18, 14, 18, 18, 18, 18, 90].map(function (width) { return {width: width}; }),
        rows: [[{v: say('דו״ח נסיעה לחו״ל'), s: S.title}], [CAPS[model.form.year].note || ''], cells(HEAD, S.header)].concat(last.rows.map(function (row) { return cells(row); }))};
      model.notes.concat([DISCLAIMER]).forEach(function (note) { second.rows.push([{v: say(note), s: S.muted}]); });
      exporter.downloadWorkbook(filename + '.xlsx', [first, second], {title: say('דו״ח נסיעה לחו״ל')});
      return;
    }
    if (kind === 'docx') {
      const blocks = [{type: 'title', text: say('דו״ח נסיעה לחו״ל')}];
      tables.forEach(function (table) {
        blocks.push({type: 'heading', level: 1, text: say(table.caption)}, {type: 'table', caption: say(table.caption), head: table.head.map(say),
          rows: table.rows.map(function (row) { return row.map(function (cell) {
            const obj = cell !== null && typeof cell === 'object' ? cell : {v: cell};
            return {text: typeof obj.v === 'number' ? number(obj.v) : obj.raw ? obj.v : say(obj.v), numeric: typeof obj.v === 'number', raw: obj.raw};
          }); })});
      });
      blocks.push({type: 'heading', level: 2, text: say('הערות')});
      model.notes.concat([DISCLAIMER]).forEach(function (note) { blocks.push({type: 'paragraph', text: say(note)}); });
      exporter.downloadBytes(filename + '.docx', Statso.docx.build({title: say('דו״ח נסיעה לחו״ל'),
        language: Statso.i18n ? Statso.i18n.locale() : 'he-IL', rtl: !Statso.i18n || Statso.i18n.current() === 'he', footer: say(SHORT), blocks: blocks}), exporter.DOCX_MIME);
      return;
    }
    const blocks = tables.map(function (table) { return '<h2>' + esc(say(table.caption)) + '</h2>' + exporter.tableHtml(table.head.map(say), table.rows, say(table.caption)); });
    model.notes.concat([DISCLAIMER]).forEach(function (note) { blocks.push('<p>' + esc(say(note)) + '</p>'); });
    exporter.printDocument('דו״ח נסיעה לחו״ל', exporter.documentHtml(say('דו״ח נסיעה לחו״ל'), '', blocks, say(SHORT)));
  }
  function init() {
    const form = el('tt-form');
    if (!form || typeof form.querySelectorAll !== 'function') { return; }
    el('tt-year').innerHTML = YEARS.map(function (year) { return '<option value="' + year + '">' + year + '</option>'; }).join('');
    el('tt-year').value = String(Math.max.apply(null, YEARS));
    el('tt-country').innerHTML = '<option value="other">מדינה אחרת</option>' + COUNTRIES.map(function (country, i) { return '<option value="' + i + '">' + esc(country) + '</option>'; }).join('');
    el('tt-country').value = 'other';
    KEYS.forEach(function (key) {
      const select = el('tt-' + key + '-currency');
      select.innerHTML = CODES.map(function (code) { return '<option value="' + code + '">' + code + '</option>'; }).join('');
      select.value = 'USD';
    });
    addTraveler(false);
    ['input', 'change'].forEach(function (event) { form.addEventListener(event, function (e) {
      state.touched = true;
      if (e.target.id === 'tt-business-days') { state.businessTouched = true; }
      compute();
    }); });
    el('tt-add-traveler').addEventListener('click', function () { addTraveler(true); });
    el('tt-xlsx').addEventListener('click', function () { exportTravel('xlsx'); });
    el('tt-pdf').addEventListener('click', function () { exportTravel('pdf'); });
    el('tt-docx').addEventListener('click', function () { exportTravel('docx'); });
    root.addEventListener('hashchange', ensureFx);
    if (Statso.i18n && Statso.i18n.onChange) { Statso.i18n.onChange(function () { renumber(); compute(); }); }
    compute(); ensureFx();
  }
  Statso.travel = {init: init, calculate: calculate, CAPS: CAPS, COUNTRIES: COUNTRIES, YEARS: YEARS, daysBetween: daysBetween, state: state};
  document.addEventListener('DOMContentLoaded', init);
})(window);
