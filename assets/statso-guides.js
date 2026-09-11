(function (root) {
  'use strict';
  const Statso = root.Statso = root.Statso || {};
  const URLS = {
    boi: {csv: 'https://raw.githubusercontent.com/Ori-barshean/statso/main/data/boi_interest_rate.csv', json: 'https://raw.githubusercontent.com/Ori-barshean/statso/main/data/boi_interest_rate.json'},
    cpi: {csv: 'https://raw.githubusercontent.com/Ori-barshean/statso/main/data/cpi.csv', json: 'https://raw.githubusercontent.com/Ori-barshean/statso/main/data/cpi.json'},
    next: 'https://raw.githubusercontent.com/Ori-barshean/statso/main/data/boi_next_decision.json'
  };
  const guides = [
    {id: 'excel', title: 'שאיבת נתונים מ-statso לתוך Excel', description: 'כך מייבאים ריבית או מדד לאקסל, עם הוראות מותאמות למחשב ולשיטת העבודה.'},
    {id: 'cpi-terms', title: 'מדד בגין מול מדד ידוע — ומה המדד בכלל מודד', description: 'ההבדל בין שני המדדים, מתי הלמ״ס מפרסמת, ומה נכלל בסל.'},
    {id: 'live-pull', soon: true, title: 'שליפת נתונים חיה — בקרוב', description: 'מדריך לשליפה אוטומטית של נתוני statso לכלים נוספים. בהכנה.'}
  ];
  const state = {platform: 'mac', method: 'power', dataset: 'boi'};

  function getSteps(platform, method, dataset) {
    const csv = URLS[dataset].csv; const json = URLS[dataset].json;
    if (method === 'power') {
      if (platform === 'mac') {
        return [
          {
          text: 'פותחים חוברת עבודה חדשה, עוברים ללשונית Data / ״נתונים״ ולוחצים על ״יבא נתונים (Power Query)״.',
          art: 'ribbon-data',
          shots: {he: {src: 'assets/images/excel-mac-power-query-he.png',
                       alt: 'אקסל למק בעברית: לשונית נתונים והכפתור ״יבא נתונים (Power Query)״.',
                       width: 542, height: 260,
                       arrow: {from: [240, 240], c1: [280, 250], c2: [334, 228], to: [386, 212], width: 7, head: 24}}}
        },
          {text: 'בחלון ״בחר מקור נתונים״ (Choose data source) בוחרים ״שאילתה ריקה״ (Blank Query).', art: 'dialog-choose-source',
           shots: {he: {src: 'assets/images/excel-mac-blank-query-he.png', alt: 'אקסל למק בעברית: חלון ״בחר מקור נתונים״ (Choose data source) והכרטיס הנבחר ״שאילתה ריקה״ (Blank Query).', width: 542, height: 229,
                       arrow: {from: [12, 222], c1: [4, 200], c2: [18, 182], to: [66, 183], width: 7, head: 20}}}},
          {text: 'בעורך Power Query לוחצים על ״עורך מתקדם״ (Advanced Editor), מוחקים את כל מה שכתוב שם, מדביקים במקומו את הקוד הבא ומאשרים.', art: 'editor-advanced', mcodeCta: true,
           code: Statso.mcode ? Statso.mcode.generate({series: dataset === 'cpi' ? 'cpi' : 'boi', currencies: [], from: '2022-12-01', to: '2025-12-31', average: false}) : ''},
          {text: 'אם מופיעה הודעה כתומה ״לא היתה אפשרות להעריך שאילתה זו עקב אישורים לא חוקיים או חסרים״ — לוחצים על ״קבע תצורה של חיבור״ (Configure connection), בוחרים ״אנונימי״ (Anonymous) ומתחברים.', art: 'dialog-credentials',
           shots: {he: {src: 'assets/images/excel-mac-credentials-he.png', alt: 'אקסל למק בעברית: הודעת האישורים והכפתור ״קבע תצורה של חיבור״.', width: 542, height: 184}}},
          {text: 'הטבלה מופיעה בתצוגה המקדימה של העורך. לוחצים על ״סגור וטען״ (Close & Load) כדי לטעון אותה לגיליון.', art: 'sheet-loaded',
           shots: {he: {src: 'assets/images/excel-mac-close-load-he.png', alt: 'אקסל למק בעברית: הטבלה בעורך Power Query והכפתור ״סגור וטען״.', width: 542, height: 286}}},
          {text: 'לעדכון הנתונים עוברים ללשונית Data / ״נתונים״ ולוחצים על ״רענן את הכל״ (Refresh All).', art: 'ribbon-refresh',
           shots: {he: {src: 'assets/images/excel-mac-refresh-all-he.png', alt: 'אקסל למק בעברית: לשונית נתונים והכפתור ״רענן את הכל״ (Refresh All).', width: 542, height: 209,
                       arrow: {from: [350, 200], c1: [318, 202], c2: [290, 196], to: [268, 172], width: 7, head: 20}}}}
        ];
      }
      return [
        {text: 'פותחים חוברת עבודה חדשה ועוברים ללשונית Data / ״נתונים״.', art: 'ribbon-data'},
        {text: 'בוחרים Get Data ← From Other Sources ← From Web (בעברית: קבל נתונים ← ממקורות אחרים ← מהאינטרנט).', art: 'menu-getdata'},
        {text: 'מדביקים את כתובת ה-CSV בתיבת URL ומאשרים ב-OK / ״אישור״.', art: 'dialog-fromweb', url: csv},
        {text: 'בחלון Navigator / ״נווט״ לוחצים Load / ״טען״, או Transform Data / ״המר נתונים״ לעריכה לפני הטעינה.', art: 'dialog-navigator'},
        {text: 'הטבלה נטענת לגיליון כטבלת Query.', art: 'sheet-loaded'},
        {text: 'לעדכון הנתונים בוחרים Data ← Refresh All (בעברית: נתונים ← רענן הכל).', art: 'ribbon-refresh'}
      ];
    }
    if (method === 'manual') {
      return [
        {text: 'פותחים את כתובת ה-CSV בדפדפן.', art: 'browser-save', url: csv},
        {text: 'שומרים את הדף כקובץ ‎.csv באמצעות ' + (platform === 'mac' ? 'Cmd+S במק.' : 'Ctrl+S בווינדוס.'), art: 'browser-save'},
        {text: 'פותחים את הקובץ באקסל דרך File ← Open / ״קובץ ← פתיחה״.', art: 'dialog-open-file'},
        {text: 'הקבצים נשמרים ב-UTF-8 עם BOM, ולכן עברית תיפתח נכון בלי הגדרות מיוחדות. החיסרון: הנתונים קפואים ברגע ההורדה, וצריך לחזור על התהליך בכל עדכון.', art: 'sheet-loaded'}
      ];
    }
    if (platform === 'mac') { return []; }
    return [
      {text: 'מזינים בתא את נוסחת WEBSERVICE עם כתובת ה-JSON. הפונקציה מחזירה את תוכן הקובץ כטקסט לתא.', art: 'cell-formula', url: json, formula: true},
      {text: 'השיטה מתאימה לשליפת ערך בודד, למשל הריבית הנוכחית, ולא לטבלה שלמה. התוצאה חייבת להיכנס לתא אחד — עד 32,767 תווים.', art: 'sheet-loaded'},
      {text: 'לקובצי המדד המלאים השיטה אינה מתאימה. משתמשים ב-Power Query, או בקובץ הקטן של החלטת הריבית הבאה.', art: 'cell-formula', url: URLS.next}
    ];
  }

  function selector(name, legend, choices) {
    return '<fieldset><legend>' + legend + '</legend><div class="radio-options">' + choices.map(function (choice) {
      return '<label><input type="radio" name="guide-' + name + '" value="' + choice[0] + '"' + (state[name] === choice[0] ? ' checked' : '') + '> <span>' + choice[1] + '</span></label>';
    }).join('') + '</div></fieldset>';
  }
  function urlBlock(url) {
    return '<div class="url-block"><code dir="ltr">' + url + '</code><button class="copy-url" type="button" data-url="' + url + '">העתק</button></div>';
  }
  function codeBlock(code) {
    return '<div class="code-block"><pre dir="ltr" data-i18n-skip><code>' + Statso.core.escapeHtml(code) + '</code></pre><button class="copy-url" type="button">העתק</button></div>';
  }
  function escAttr(value) { return String(value == null ? '' : value).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
  function round1(value) { return Math.round(value * 10) / 10; }
  // The arrowhead is its own polygon laid along the curve's final tangent, not a <marker>,
  // so any number of screenshots can share a page without clashing ids. Needs |to - c2| > head.
  function arrowMarkup(arrow) {
    const dx = arrow.to[0] - arrow.c2[0]; const dy = arrow.to[1] - arrow.c2[1]; const length = Math.hypot(dx, dy);
    const ux = dx / length; const uy = dy / length; const half = 0.45 * arrow.head;
    const base = [arrow.to[0] - arrow.head * ux, arrow.to[1] - arrow.head * uy];
    const left = [base[0] - uy * half, base[1] + ux * half]; const right = [base[0] + uy * half, base[1] - ux * half];
    const point = function (p, sep) { return round1(p[0]) + sep + round1(p[1]); };
    return '<path d="M' + point(arrow.from, ' ') + ' C' + point(arrow.c1, ' ') + ' ' + point(arrow.c2, ' ') + ' ' + point(base, ' ') + '" fill="none" stroke="#f97316" stroke-width="' + arrow.width + '" stroke-linecap="round" stroke-linejoin="round"></path>' +
      '<polygon points="' + point(arrow.to, ',') + ' ' + point(left, ',') + ' ' + point(right, ',') + '" fill="#f97316"></polygon>';
  }
  function shotMarkup(shot) {
    const overlay = shot.arrow ? '<svg class="guide-shot-arrow" viewBox="0 0 ' + shot.width + ' ' + shot.height + '" aria-hidden="true" focusable="false">' + arrowMarkup(shot.arrow) + '</svg>' : '';
    return '<div class="guide-real-shot"><img src="' + escAttr(shot.src) + '" alt="' + escAttr(shot.alt) + '" width="' + shot.width + '" height="' + shot.height + '">' + overlay + '</div>';
  }
  function artSlot(source, lang, stepNumber) {
    const caption = lang === 'he' ? 'אקסל בעברית' : 'אקסל באנגלית';
    let visual;
    const shot = source.shots && source.shots[lang];
    if (shot) { visual = shotMarkup(shot); }
    else { visual = Statso.guideArt.render(source.art, {lang: lang, platform: state.platform, url: source.url || URLS[state.dataset].csv, dataset: state.dataset, step: stepNumber}); }
    return '<figure><div class="art-scroll art-scroll-' + (lang === 'he' ? 'rtl' : 'ltr') + '">' + visual + '</div><figcaption>' + caption + '</figcaption></figure>';
  }
  // A Hebrew reader may be running Excel in either language, so both screenshots
  // earn their place, except in the Mac Power Query guide with Hebrew screenshots.
  // An English reader has no use for the Hebrew Excel UI.
  function artSlots(step, number) {
    const site = Statso.i18n ? Statso.i18n.current() : 'he';
    if (site === 'en') { return artSlot(step, 'en', number); }
    if (hebrewMacPower()) { return artSlot(step, 'he', number); }
    return artSlot(step, 'he', number) + artSlot(step, 'en', number);
  }

  function hebrewMacPower() {
    const site = Statso.i18n ? Statso.i18n.current() : 'he';
    return site === 'he' && state.platform === 'mac' && state.method === 'power';
  }
  function mcodeCta() {
    const example = state.dataset === 'cpi'
      ? 'הקוד שלמעלה הוא דוגמה מוכנה למדד המחירים לצרכן לטווח 2022-12-01 עד 2025-12-31.'
      : 'הקוד שלמעלה הוא דוגמה מוכנה לריבית בנק ישראל לטווח 2022-12-01 עד 2025-12-31.';
    const explanation = 'בעמוד ״קודים לייצוא (Power Query)״ אפשר לבחור כל סדרה, טווח תאריכים והשוואה שהאתר מציע, להוסיף שורת ממוצע לפי הצורך ולקבל קוד M מוכן להעתקה למקרה שלכם.';
    const label = 'קודים לייצוא (Power Query)';
    return '<div class="guide-mcode-cta"><p>' + example + '</p><p>' + explanation + '</p><a class="guide-mcode-button" href="#/mcode">' + label + '</a></div>';
  }

  function renderSteps() {
    const target = document.querySelector('.guide-steps-host');
    if (state.platform === 'mac' && state.method === 'webservice') {
      target.innerHTML = '<aside class="guide-notice" role="status"><h2>WEBSERVICE אינה זמינה ב-Excel for Mac</h2><p>אין צעדים להצגה עבור שילוב זה. אפשר לייבא את הנתונים באמצעות Power Query.</p><button type="button" class="choose-power">מעבר ל-Power Query</button></aside>';
      document.querySelector('.choose-power').addEventListener('click', function () { state.method = 'power'; renderGuide(); });
      return;
    }
    const steps = getSteps(state.platform, state.method, state.dataset);
    const artClass = hebrewMacPower() ? 'step-art step-art-single' : 'step-art';
    target.innerHTML = '<ol class="guide-steps">' + steps.map(function (step, index) {
      const number = index + 1;
      return '<li><div class="step-copy"><h2>שלב ' + number + '</h2><p>' + step.text + '</p>' + (step.formula ? '<p><code dir="ltr">=WEBSERVICE(&quot;&lt;JSON URL&gt;&quot;)</code></p>' : '') + (step.url ? urlBlock(step.url) : '') + (step.code ? codeBlock(step.code) + (step.mcodeCta ? mcodeCta() : '') : '') + '</div><div class="' + artClass + '">' + artSlots(step, number) + '</div></li>';
    }).join('') + '</ol>';
    attachCopyButtons();
  }
  function renderExcelGuide() {
    document.getElementById('guide-detail').setAttribute('aria-labelledby', 'excel-guide-title');
    document.getElementById('guide-content').innerHTML = '<header class="guide-header"><p class="eyebrow">מדריך אינטראקטיבי</p><h1 id="excel-guide-title">שאיבת נתונים מ-statso לתוך Excel</h1><p>בחרו את סביבת העבודה והנתונים, והשלבים יתעדכנו מיד.</p></header><form class="guide-selectors">' +
      selector('platform', 'מערכת הפעלה', [['mac','מק (macOS)'],['win','ווינדוס']]) +
      selector('method', 'שיטה', [['power','Power Query (מומלץ)'],['manual','הורדה ידנית של CSV'],['webservice','נוסחת WEBSERVICE']]) +
      selector('dataset', 'נתונים', [['boi','ריבית בנק ישראל'],['cpi','מדד המחירים לצרכן']]) + '</form><div class="guide-steps-host"></div>';
    document.querySelectorAll('.guide-selectors input').forEach(function (radio) { radio.addEventListener('change', function () { state[radio.name.replace('guide-', '')] = radio.value; renderSteps(); }); });
    renderSteps();
  }
  function formatCpiExample(doc) {
    if (!doc || !Array.isArray(doc.observations) || doc.observations.length < 2) { throw new Error('missing observations'); }
    const latest = doc.observations.reduce(function (found, row) { return !found || row.month > found.month ? row : found; }, null);
    const knownMonth = Statso.core.shiftMonth(latest.month, -1);
    const known = doc.observations.find(function (row) { return row.month === knownMonth; });
    if (!known || !Number.isFinite(latest.value) || !Number.isFinite(known.value)) { throw new Error('missing values'); }
    const publicationDate = Statso.core.shiftMonth(latest.month, 1) + '-15';
    return 'בחודש ' + Statso.core.formatMonthHe(latest.month) + ', מדד בגין הוא מדד ' + Statso.core.formatMonthHe(latest.month) + ' — ' + Statso.core.formatNumber(latest.value, 1) + '. מדד ידוע באותו חודש הוא מדד ' + Statso.core.formatMonthHe(known.month) + ' — ' + Statso.core.formatNumber(known.value, 1) + '. מדד בגין החודש מתפרסם ב-' + Statso.core.formatIsoDateHe(publicationDate) + '.';
  }
  function fillCpiExample() {
    const target = document.querySelector('[data-cpi-live-example]');
    const source = document.getElementById('data-cpi');
    if (!target || !source || !Statso.data || typeof Statso.data.loadDataset !== 'function') { return; }
    Statso.data.loadDataset(source).then(function (doc) {
      const current = document.querySelector('[data-cpi-live-example]');
      if (current) { current.textContent = formatCpiExample(doc); }
    }).catch(function () { /* The immediate fallback remains visible. */ });
  }
  function renderCpiGuide() {
    document.getElementById('guide-detail').setAttribute('aria-labelledby', 'cpi-guide-title');
    const diagram = Statso.guideArt.render('timeline-publication', {lang: 'he', platform: 'win'});
    document.getElementById('guide-content').innerHTML = '<header class="guide-header"><p class="eyebrow">מושגים במדד המחירים לצרכן</p><h1 id="cpi-guide-title">מדד בגין מול מדד ידוע — ומה המדד בכלל מודד</h1><p>ההבדל בין שני המדדים, מועד הפרסום והרכב סל הצריכה.</p></header>' +
      '<div class="prose-guide">' +
      '<section><h2>1. שני שמות, אותו מדד</h2><p><strong>מדד בגין חודש X</strong> הוא המדד שמודד את המחירים בחודש X עצמו. הוא מתפרסם ב-15 בחודש X+1.</p><p><strong>מדד ידוע במועד מסוים</strong> הוא המדד האחרון שפורסם עד אותו מועד — כלומר המדד של החודש הקודם.</p><p>לכן, לתשלום שחל בחודש X: מדד ידוע = המדד של חודש X-1; מדד בגין = המדד של חודש X.</p><p>אלה אותם מספרים בדיוק; ההבדל הוא רק לאיזה חודש מצמידים אותם. הפער ביניהם הוא חודש אחד. <a href="#/">המחשבון בדף הבית</a> מיישם בדיוק את ההבחנה הזו.</p><aside class="guide-note live-example"><h3>דוגמה מהנתונים העדכניים</h3><p data-cpi-live-example>לא ניתן להציג דוגמה מהנתונים כרגע</p></aside></section>' +
      '<section><h2>2. מתי מתפרסם המדד</h2><p>לפי הלמ״ס, הודעות מדדי המחירים מתפרסמות ב-15 בכל חודש בשעה 18:30, עבור החודש שקדם לו.</p><p>אם ה-15 בחודש נופל ביום שישי, בשבת, בערב חג או בחג — הפרסום מוקדם ליום שישי או לערב החג, בשעה 14:00.</p><figure class="timeline-figure"><div class="art-scroll art-scroll-rtl">' + diagram + '</div><figcaption>ציר הזמן של מדד בגין ומדד ידוע: פער קבוע של חודש אחד.</figcaption></figure></section>' +
      '<section><h2>3. מה המדד כולל</h2><p>לפי הלמ״ס, המדד מודד את שינוי העלות של סל הצריכה של משק בית ממוצע; הלמ״ס מתמחרת מדי חודש כ-1,300 מוצרים ושירותים מייצגים.</p><p>עשר קבוצות הצריכה הראשיות הן: מזון (ללא ירקות ופירות); ירקות ופירות; דיור; תחזוקת הדירה; ריהוט וציוד לבית; הלבשה והנעלה; בריאות; חינוך, תרבות ובידור; תחבורה ותקשורת; שונות.</p><p><strong>מה המדד לא כולל:</strong> רכישת דירה. קבוצת ״דיור״ במדד מודדת את שירותי הדיור — בעיקר שכר דירה — ולא את מחיר קניית הדירה. מחירי רכישת דירות נמדדים במדד נפרד של הלמ״ס, ״מדד ומחירים ממוצעים משוק הדירות״.</p></section>' +
      '<section><h2>4. מדדים נגזרים</h2><p>הלמ״ס מפרסמת גם חתכים שמנטרלים רכיבים תנודתיים: המדד ללא ירקות ופירות; המדד ללא דיור; המדד ללא ירקות ופירות וללא דיור; המדד ללא אנרגיה.</p><p>החתכים האלה משמשים כדי לראות מגמה בסיסית בלי רעש עונתי או תנודות אנרגיה.</p></section></div>';
    fillCpiExample();
  }
  let currentGuide = null;
  function renderGuide(guideId) {
    currentGuide = guideId;
    if (guideId === 'cpi-terms') { renderCpiGuide(); } else { renderExcelGuide(); }
  }
  function showGuide(eventOrId) {
    const guideId = typeof eventOrId === 'string' ? eventOrId : eventOrId && eventOrId.currentTarget ? eventOrId.currentTarget.dataset.guide : 'excel';
    document.getElementById('guides-index').hidden = true; document.getElementById('guide-detail').hidden = false; renderGuide(guideId); root.scrollTo(0, 0);
    if (Statso.nav && Statso.nav.focusView) { Statso.nav.focusView(); }
  }
  function showIndex(fromRoute) {
    document.getElementById('guide-detail').hidden = true; document.getElementById('guides-index').hidden = false; root.scrollTo(0, 0);
    if (!fromRoute && Statso.nav && Statso.nav.focusView) { Statso.nav.focusView(); }
  }
  function renderIndex() {
    document.getElementById('guide-cards').innerHTML = guides.map(function (guide) {
      if (guide.soon) { return '<div class="guide-card guide-card-soon" aria-disabled="true"><span>' + Statso.core.escapeHtml(guide.title) + '</span><small>' + Statso.core.escapeHtml(guide.description) + '</small></div>'; }
      return '<button class="guide-card" type="button" data-guide="' + guide.id + '"><span>' + guide.title + '</span><small>' + guide.description + '</small><b aria-hidden="true">←</b></button>'; }).join('');
    document.querySelectorAll('[data-guide]').forEach(function (button) { button.addEventListener('click', showGuide); });
  }
  function legacyCopy(text) {
    const input = document.createElement('textarea'); input.value = text; input.setAttribute('readonly', ''); input.style.position = 'fixed'; input.style.opacity = '0'; document.body.appendChild(input); input.select();
    let ok = false; try { ok = document.execCommand('copy'); } catch (error) { ok = false; } document.body.removeChild(input); return ok;
  }
  function payload(button) {
    if (button.dataset.url) { return button.dataset.url; }
    const holder = button.closest('.code-block');
    const code = holder && holder.querySelector('code');
    return code ? code.textContent : '';
  }
  function copy(button) {
    const done = function (ok) { if (!ok) { return; } const old = button.textContent; button.textContent = 'הועתק'; root.setTimeout(function () { button.textContent = old; }, 1400); };
    if (navigator.clipboard && navigator.clipboard.writeText) { navigator.clipboard.writeText(payload(button)).then(function () { done(true); }).catch(function () { done(legacyCopy(payload(button))); }); }
    else { done(legacyCopy(payload(button))); }
  }
  function attachCopyButtons() { document.querySelectorAll('.copy-url').forEach(function (button) { button.addEventListener('click', function () { copy(button); }); }); }
  function init() { renderIndex(); document.getElementById('guide-back').addEventListener('click', function () { showIndex(); }); }
  document.addEventListener('DOMContentLoaded', init);
  if (root.Statso.i18n) {
    root.Statso.i18n.onChange(function () {
      const detail = document.getElementById('guide-detail');
      if (detail && !detail.hidden && currentGuide) { renderGuide(currentGuide); }
    });
  }

  Statso.guides = {URLS: URLS, guides: guides, state: state, getSteps: getSteps, renderGuide: renderGuide, renderExcelGuide: renderExcelGuide, renderCpiGuide: renderCpiGuide, showGuide: showGuide, showIndex: showIndex};
})(window);
