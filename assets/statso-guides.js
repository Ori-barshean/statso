(function (root) {
  'use strict';
  const Statso = root.Statso = root.Statso || {};
  const URLS = {
    boi: {csv: 'https://raw.githubusercontent.com/Ori-barshean/statso/main/data/boi_interest_rate.csv', json: 'https://raw.githubusercontent.com/Ori-barshean/statso/main/data/boi_interest_rate.json'},
    cpi: {csv: 'https://raw.githubusercontent.com/Ori-barshean/statso/main/data/cpi.csv', json: 'https://raw.githubusercontent.com/Ori-barshean/statso/main/data/cpi.json'},
    next: 'https://raw.githubusercontent.com/Ori-barshean/statso/main/data/boi_next_decision.json'
  };
  const guides = [{id: 'excel', title: 'שאיבת נתונים מ-statso לתוך Excel', description: 'כך מייבאים ריבית או מדד לאקסל, עם הוראות מותאמות למחשב ולשיטת העבודה.'}];
  const state = {platform: 'mac', method: 'power', dataset: 'boi'};

  function getSteps(platform, method, dataset) {
    const csv = URLS[dataset].csv; const json = URLS[dataset].json;
    if (method === 'power') {
      return [
        {text: 'פותחים חוברת עבודה חדשה ועוברים ללשונית Data / ״נתונים״.', art: 'ribbon-data'},
        {text: platform === 'mac' ? 'בוחרים Data ← Get Data ← From Web (בעברית: נתונים ← קבלת נתונים ← מהאינטרנט).' : 'בוחרים Get Data ← From Other Sources ← From Web (בעברית: קבל נתונים ← ממקורות אחרים ← מהאינטרנט).', art: 'menu-getdata'},
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
  function artSlot(source, lang, stepNumber) {
    const caption = lang === 'he' ? 'אקסל בעברית' : 'אקסל באנגלית';
    let visual;
    if (source.img) { visual = '<img src="' + source.img + '" alt="' + source.alt + '">'; }
    else { visual = Statso.guideArt.render(source.art, {lang: lang, platform: state.platform, url: source.url || URLS[state.dataset].csv, dataset: state.dataset, step: stepNumber}); }
    return '<figure><div class="art-scroll art-scroll-' + (lang === 'he' ? 'rtl' : 'ltr') + '">' + visual + '</div><figcaption>' + caption + '</figcaption></figure>';
  }
  function renderSteps() {
    const target = document.querySelector('.guide-steps-host');
    if (state.platform === 'mac' && state.method === 'webservice') {
      target.innerHTML = '<aside class="guide-notice" role="status"><h2>WEBSERVICE אינה זמינה ב-Excel for Mac</h2><p>אין צעדים להצגה עבור שילוב זה. אפשר לייבא את הנתונים באמצעות Power Query.</p><button type="button" class="choose-power">מעבר ל-Power Query</button></aside>';
      document.querySelector('.choose-power').addEventListener('click', function () { state.method = 'power'; renderGuide(); });
      return;
    }
    const steps = getSteps(state.platform, state.method, state.dataset);
    const note = state.platform === 'mac' && state.method === 'power' ? '<aside class="guide-note">״From Web״ קיים ב-Excel for Mac מתוך Microsoft 365 בגרסאות מ-2022 ואילך. אם הוא לא מופיע — יש לעדכן את אקסל או להשתמש בשיטת ההורדה הידנית.</aside>' : '';
    target.innerHTML = note + '<ol class="guide-steps">' + steps.map(function (step, index) {
      const number = index + 1;
      return '<li><div class="step-copy"><h2>שלב ' + number + '</h2><p>' + step.text + '</p>' + (step.formula ? '<p><code dir="ltr">=WEBSERVICE(&quot;&lt;JSON URL&gt;&quot;)</code></p>' : '') + (step.url ? urlBlock(step.url) : '') + '</div><div class="step-art">' + artSlot(step, 'he', number) + artSlot(step, 'en', number) + '</div></li>';
    }).join('') + '</ol>';
    attachCopyButtons();
  }
  function renderGuide() {
    document.getElementById('guide-content').innerHTML = '<header class="guide-header"><p class="eyebrow">מדריך אינטראקטיבי</p><h1 id="excel-guide-title">שאיבת נתונים מ-statso לתוך Excel</h1><p>בחרו את סביבת העבודה והנתונים, והשלבים יתעדכנו מיד.</p></header><form class="guide-selectors">' +
      selector('platform', 'מערכת הפעלה', [['mac','מק (macOS)'],['win','ווינדוס']]) +
      selector('method', 'שיטה', [['power','Power Query (מומלץ)'],['manual','הורדה ידנית של CSV'],['webservice','נוסחת WEBSERVICE']]) +
      selector('dataset', 'נתונים', [['boi','ריבית בנק ישראל'],['cpi','מדד המחירים לצרכן']]) + '</form><div class="guide-steps-host"></div>';
    document.querySelectorAll('.guide-selectors input').forEach(function (radio) { radio.addEventListener('change', function () { state[radio.name.replace('guide-', '')] = radio.value; renderSteps(); }); });
    renderSteps();
  }
  function showGuide() { document.getElementById('guides-index').hidden = true; document.getElementById('guide-detail').hidden = false; renderGuide(); root.scrollTo(0, 0); }
  function showIndex() { document.getElementById('guide-detail').hidden = true; document.getElementById('guides-index').hidden = false; root.scrollTo(0, 0); }
  function renderIndex() {
    document.getElementById('guide-cards').innerHTML = guides.map(function (guide) { return '<button class="guide-card" type="button" data-guide="' + guide.id + '"><span>' + guide.title + '</span><small>' + guide.description + '</small><b aria-hidden="true">←</b></button>'; }).join('');
    document.querySelectorAll('[data-guide]').forEach(function (button) { button.addEventListener('click', showGuide); });
  }
  function legacyCopy(text) {
    const input = document.createElement('textarea'); input.value = text; input.setAttribute('readonly', ''); input.style.position = 'fixed'; input.style.opacity = '0'; document.body.appendChild(input); input.select();
    let ok = false; try { ok = document.execCommand('copy'); } catch (error) { ok = false; } document.body.removeChild(input); return ok;
  }
  function copy(button) {
    const done = function (ok) { if (!ok) { return; } const old = button.textContent; button.textContent = 'הועתק'; root.setTimeout(function () { button.textContent = old; }, 1400); };
    if (navigator.clipboard && navigator.clipboard.writeText) { navigator.clipboard.writeText(button.dataset.url).then(function () { done(true); }).catch(function () { done(legacyCopy(button.dataset.url)); }); }
    else { done(legacyCopy(button.dataset.url)); }
  }
  function attachCopyButtons() { document.querySelectorAll('.copy-url').forEach(function (button) { button.addEventListener('click', function () { copy(button); }); }); }
  function init() { renderIndex(); document.getElementById('guide-back').addEventListener('click', showIndex); }
  document.addEventListener('DOMContentLoaded', init);
  Statso.guides = {URLS: URLS, guides: guides, state: state, getSteps: getSteps, renderGuide: renderGuide, showGuide: showGuide, showIndex: showIndex};
})(window);
