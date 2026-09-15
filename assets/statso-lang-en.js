(function (root) {
  'use strict';
  const Statso = root.Statso = root.Statso || {};

  // Hebrew source string -> English. Keys are the exact trimmed text as it
  // reaches the DOM, so anything a module renders is covered without the module
  // itself knowing about languages.
  const en = {
    // --- Power Query exports -----------------------------------------------
    'קודים לייצוא (Power Query)': 'Export code (Power Query)',
    'בוחרים סדרת נתונים וטווח תאריכים, ומעתיקים קוד מוכן להדבקה בעורך המתקדם של Power Query באקסל.': 'Choose a data series and date range, then copy code into the Power Query Advanced Editor in Excel.',
    'סדרת נתונים': 'Data series',
    'מדד המחירים לצרכן (משורשר)': 'Consumer price index (chained)',
    'שערי חליפין יציגים': 'Representative exchange rates',
    'טווח תאריכים': 'Date range',
    'תאריך התחלה': 'Start date',
    'תאריך סיום': 'End date',
    'להוסיף שורת ממוצע בסוף הטבלה': 'Add an average row at the end of the table',
    'העתקת הקוד': 'Copy code',
    'הסבר שלב-אחר-שלב איך מדביקים את הקוד באקסל נמצא בעמוד': 'For step-by-step instructions on pasting the code into Excel, see',
    'יש לבחור תאריך התחלה ותאריך סיום.': 'Choose a start date and an end date.',
    'תאריך ההתחלה חייב להיות לפני תאריך הסיום.': 'The start date must be before the end date.',
    'בחלון ״בחר מקור נתונים״ (Choose data source) בוחרים ״שאילתה ריקה״ (Blank Query).': 'In Choose data source, select Blank Query.',
    'בעורך Power Query לוחצים על ״עורך מתקדם״ (Advanced Editor), מוחקים את כל מה שכתוב שם, מדביקים במקומו קוד מתוך': 'In Power Query, click Advanced Editor, delete all existing content, and paste code from',
    ', ולוחצים אישור/הבא.': ', then click OK/Next.',
    'אם מופיעה הודעה כתומה ״לא היתה אפשרות להעריך שאילתה זו עקב אישורים לא חוקיים או חסרים״ — לוחצים על ״קבע תצורה של חיבור״ (Configure connection), בוחרים ״אנונימי״ (Anonymous) ומתחברים.': 'If an orange warning says the query could not be evaluated because of invalid or missing credentials, click Configure connection, choose Anonymous access, and connect.',
    'הטבלה מופיעה בתצוגה המקדימה של העורך. לוחצים על ״סגור וטען״ (Close & Load) כדי לטעון אותה לגיליון.': 'The table appears in the editor preview. Click Close & Load to load it into the worksheet.',
    'אקסל למק בעברית: חלון ״בחר מקור נתונים״ (Choose data source) והכרטיס הנבחר ״שאילתה ריקה״ (Blank Query).': 'Excel for Mac in Hebrew: Choose data source and the selected Blank Query card.',
    'אקסל למק בעברית: הודעת האישורים והכפתור ״קבע תצורה של חיבור״.': 'Excel for Mac in Hebrew: the credentials warning and Configure connection button.',
    'אקסל למק בעברית: הטבלה בעורך Power Query והכפתור ״סגור וטען״.': 'Excel for Mac in Hebrew: the table in Power Query and the Close & Load button.',
    'שליפת נתונים חיה — בקרוב': 'Live data pull — coming soon',
    'מדריך לשליפה אוטומטית של נתוני statso לכלים נוספים. בהכנה.': 'A guide to automatically pulling statso data into other tools. In preparation.',
    'בחר מקור נתונים': 'Choose data source',
    'שאילתה ריקה': 'Blank Query',
    'טקסט/CSV': 'Text/CSV',
    'עורך מתקדם': 'Advanced Editor',
    'קבע תצורה של חיבור': 'Configure connection',
    'אישורים לא חוקיים או חסרים': 'Invalid or missing credentials',
    'סגור וטען': 'Close & Load',

    'לעדכון הנתונים עוברים ללשונית Data / ״נתונים״ ולוחצים על ״רענן את הכל״ (Refresh All).': 'To update the data, open the Data tab and click Refresh All.',
    'אקסל למק בעברית: לשונית נתונים והכפתור ״רענן את הכל״ (Refresh All).': 'Excel for Mac in Hebrew: the Data tab and Refresh All button.',
    'הקוד שלהלן הוא דוגמה מוכנה לריבית בנק ישראל לטווח 2022-12-01 עד 2025-12-31.': 'The code below is a ready-made Bank of Israel interest rate example for 2022-12-01 to 2025-12-31.',
    'בעמוד ״קודים לייצוא (Power Query)״ אפשר לבחור כל סדרה, טווח תאריכים והשוואה שהאתר מציע, להוסיף שורת ממוצע לפי הצורך ולקבל קוד M מוכן להעתקה למקרה שלכם.': 'On the Export code (Power Query) page, choose any series, date range, and comparison the site offers, optionally add an average row, and get copy-ready M code for your own case.',

    // --- chrome -----------------------------------------------------------
    'statso — נתונים בזריזות - ישראל': 'statso — Israeli economic data, fast',
    'נתונים בזריזות - ישראל': 'Israeli economic data, fast',
    'תמונת מצב עדכנית': 'Current snapshot',
    'מדד המחירים לצרכן, ריבית בנק ישראל וכלי הצמדה — על בסיס מקורות רשמיים.':
      'The consumer price index, the Bank of Israel rate and linkage tools — from official sources.',
    'ניווט ראשי': 'Main navigation',
    'דף הבית': 'Home',
    'statso — דף הבית': 'statso — home',
    'מדריכים': 'Guides',
    'כלים': 'Tools',
    'מידע': 'Information',
    'נתונים ממקורות רשמיים': 'Data from official sources',
    '· גרסה': '· version',
    'דילוג לתוכן המרכזי': 'Skip to main content',

    // --- dashboard cards ---------------------------------------------------
    'נתונים מרכזיים': 'Headline figures',
    'מדד המחירים לצרכן': 'Consumer price index',
    'טוען נתונים…': 'Loading data…',
    'שינוי שנתי': 'Year over year',
    'שינוי חודשי': 'Month over month',
    'ריבית בנק ישראל': 'Bank of Israel rate',
    'ריבית נוכחית': 'Current rate',
    'ריבית פריים': 'Prime rate',
    'החלטת הריבית הבאה:': 'Next rate decision:',
    'המועד עשוי להשתנות בהתאם להודעות בנק ישראל': 'The date may change based on Bank of Israel announcements',
    'שערי חליפין נבחרים': 'Selected exchange rates',
    'דולר / שקל': 'USD / ILS',
    'אירו / שקל': 'EUR / ILS',
    'עדכני ל־': 'As at ',
    'מעודכן לסוף יום המסחר האחרון': 'As at the close of the last trading day',
    'אינה ידועה': 'not known',

    // --- exchange-rate table ----------------------------------------------
    'שערי חליפין': 'Exchange rates',
    'מטבעות נבחרים מול השקל': 'Selected currencies against the shekel',
    'טוען שערי חליפין…': 'Loading exchange rates…',
    'מטבע': 'Currency',
    'שער עדכני': 'Latest rate',
    'שערים יציגים של בנק ישראל מול השקל החדש. שער סוף שנה הוא השער האחרון שפורסם באותה שנה, והממוצע הוא ממוצע כל השערים שפורסמו בה. ×100 מציין ציטוט ל־100 יחידות מטבע.':
      'Bank of Israel representative rates against the new shekel. The year-end rate is the last rate published that year, and the average covers every rate published in it. ×100 marks a quote per 100 units of the currency.',
    'שערי חליפין נבחרים מול השקל, לפי מטבע': 'Selected exchange rates against the shekel, by currency',

    // --- chart --------------------------------------------------------------
    'מגמה היסטורית': 'Historical trend',
    'המדד המשורשר לאורך זמן': 'The chained index over time',
    'תרשים מדד המחירים לצרכן': 'Consumer price index chart',
    'התרשים מציג את מגמת מדד המחירים לצרכן המשורשר לאורך הטווח שנבחר.':
      'The chart shows the trend of the chained consumer price index over the selected range.',
    'לצפייה בנתונים כטבלה': 'View as a table',
    'משנה': 'From year',
    'עד': 'to',
    'טוען תרשים…': 'Loading chart…',
    'מדד משורשר': 'Chained index',
    'שנת ההתחלה חייבת להיות מוקדמת משנת הסיום.': 'The start year must come before the end year.',
    'ספריית התרשים אינה זמינה. יתר הכלים ממשיכים לפעול.':
      'The chart library is unavailable. Everything else keeps working.',
    'משבר הסאב־פריים': 'Subprime crisis',
    'קורונה': 'Covid',
    '7 באוקטובר': '7 October',
    'מלחמת איראן הראשונה': 'First Iran war',
    'מלחמת איראן השנייה': 'Second Iran war',

    // --- dashboard calculator ----------------------------------------------
    'מחשבון': 'Calculator',
    'הצמדה למדד והמרת מטבע': 'Index linkage and currency conversion',
    'טוען מחשבון…': 'Loading calculator…',
    'סוג החישוב': 'Calculation',
    'הצמדה למדד': 'Index linkage',
    'המרת מטבע': 'Currency conversion',
    'סכום בשקלים': 'Amount in shekels',
    'סוג המדד': 'Index',
    'מדד ידוע': 'Known index',
    'מדד בגין': 'Index for the month',
    'חודש בסיס': 'Base month',
    'שנה': 'Year',
    'חודש': 'Month',
    'חודש יעד': 'Target month',
    'המרה': 'Conversion',
    'ממטבע': 'From',
    'למטבע': 'To',
    'לפי השער ליום': 'Rate as at',
    'סכום מוצמד': 'Linked amount',
    'הפרש': 'Difference',
    'סכום מומר': 'Converted amount',
    'סכום ממומר': 'Converted amount',
    'שער ההמרה': 'Rate used',
    'סכום': 'Amount',
    'התוצאה מיועדת להמחשה בלבד. לפני שימוש כספי או משפטי יש לאמת את הנתונים ואת שיטת החישוב.':
      'The result is for illustration only. Before financial or legal use, verify the data and the calculation method.',

    // --- tools index --------------------------------------------------------
    'כלי חישוב': 'Calculation tools',
    'מחשבוני הצמדה, נתוני מדד היסטוריים והצמדת הסכמי שכירות — כולם על בסיס הנתונים הרשמיים של הלמ״ס ובנק ישראל. כל כלי מייצא לאקסל או ל־PDF מעוצב.':
      'Linkage calculators, historical index data and rent-agreement linkage — all built on the official CBS and Bank of Israel data. Every tool exports to Excel or to a styled PDF.',
    'הצמדה למדדים': 'Index linkage',
    'הצמדה למטבע': 'Currency linkage',
    'נתוני מדד היסטוריים': 'Historical index data',
    'הצמדת הסכם שכירות': 'Rent agreement linkage',
    'הצמדת סכום בין שני חודשים לפי מדד המחירים לצרכן.':
      'Link an amount between two months by the consumer price index.',
    'המרה לפי שער יציג, או הצמדה לפי שינוי השער בין שני תאריכים.':
      'Convert at a representative rate, or link by the change in that rate between two dates.',
    'טבלת מדד לטווח שתבחר, עם העתקה ישירה לאקסל.':
      'An index table for the range you choose, ready to paste into Excel.',
    'חישוב הפרשי הצמדה לכל תקופות השכירות והאופציה, לשליחה לשוכר.':
      'Linkage differences across every rental and option period, ready to send to the tenant.',
    'כלי 1': 'Tool 1', 'כלי 2': 'Tool 2', 'כלי 3': 'Tool 3', 'כלי 4': 'Tool 4',
    '← לכל הכלים': '← All tools',
    'סוג המדד לחישוב': 'Index basis',
    'ייצוא לאקסל': 'Export to Excel',
    'ייצוא ל־PDF': 'Export to PDF',
    'העתקה לאקסל': 'Copy for Excel',
    'הועתק ✓': 'Copied ✓',
    'ההעתקה נכשלה': 'Copy failed',

    // --- currency tool ------------------------------------------------------
    'המרה לפי שער': 'Convert at a rate',
    'הצמדה בין תאריכים': 'Link between dates',
    'מטבע ההצמדה': 'Linkage currency',
    'תאריך השער': 'Rate date',
    'תאריך בסיס': 'Base date',
    'תאריך יעד': 'Target date',

    // --- history tool -------------------------------------------------------
    'מ־': 'From',
    'מדד מקורי': 'As published',
    'שינוי חודשי %': 'Month over month %',
    'שינוי שנתי %': 'Year over year %',
    'חודש ההתחלה חייב להיות מוקדם מחודש הסיום.': 'The start month must come before the end month.',
    'נתוני מדד המחירים לצרכן ההיסטוריים, לפי חודש': 'Historical consumer price index data, by month',


    // --- historical exchange rates tool --------------------------------------
    'נתוני שער חליפין היסטוריים': 'Historical exchange rate data',
    'שערי חליפין היסטוריים': 'Historical exchange rates',
    'שערים יציגים לטווח ולמטבעות שתבחר, יומי או כממוצע תקופתי.':
      'Representative rates for the range and currencies you pick, daily or as a period average.',
    'נתוני שערי חליפין היסטוריים, לפי מטבע ותאריך': 'Historical exchange rate data, by currency and date',
    'כלי 5': 'Tool 5',
    'מטבעות': 'Currencies',
    'טווח ורזולוציה': 'Range and resolution',
    'מתאריך': 'From date',
    'עד תאריך': 'To date',
    'רזולוציה': 'Resolution',
    'יומי — כל שער שפורסם': 'Daily — every published rate',
    'שבועי — ממוצע': 'Weekly — average',
    'חודשי — ממוצע': 'Monthly — average',
    'שנתי — ממוצע': 'Yearly — average',
    'ממוצע לתקופה': 'Period average',
    'ממוצע לתקופה ·': 'Period average ·',
    'יש לבחור מטבע אחד לפחות.': 'Choose at least one currency.',
    'יש לבחור טווח תאריכים.': 'Choose a date range.',
    'תאריך ההתחלה חייב להיות מוקדם מתאריך הסיום.': 'The start date must come before the end date.',
    'אין שערים שפורסמו בטווח שנבחר.': 'No rates were published in the selected range.',
    // --- rent tool ----------------------------------------------------------
    'הצמדת הסכם שכירות למדד': 'Rent agreement index linkage',
    'פרטי ההסכם': 'Agreement details',
    'מועד הסכם השכירות': 'Date of the rent agreement',
    'שם המשכיר': 'Landlord',
    'משכיר': 'Landlord',
    'שוכר': 'Tenant',
    'שם השוכר': 'Tenant',
    'שם מלא': 'Full name',
    'תקופת השכירות הבסיסית': 'Base rental period',
    'מחודש': 'From month',
    'עד חודש': 'To month',
    'דמי שכירות חודשיים (₪)': 'Monthly rent (₪)',
    'תקופות אופציה והארכה': 'Option and extension periods',
    'קיימות תקופות אופציה': 'The agreement has option periods',
    'הוספת תקופה': 'Add a period',
    'הסרה': 'Remove',
    'הסרת תקופה': 'Remove period',
    'מדד הבסיס': 'Base index',
    'מדד בסיס מוסכם אחר (במקום המדד הידוע במועד ההסכם)':
      'A different agreed base index (instead of the known index at signing)',
    'אופן ההצמדה': 'Linkage method',
    'רק הפרש לתשלום — אם המדד ירד, התשלום נשאר הנומינלי':
      'Amounts due only — if the index falls, the payment stays at the nominal rent',
    'הצמדה מלאה — להתחשב גם בירידת המדד': 'Full linkage — a falling index reduces the payment too',
    'טווח לייצוא': 'Export range',
    'תקופה': 'Period',
    'כל התקופות': 'All periods',
    'להשמיט חודשים שההפרש בגינם כבר שולם': 'Leave out months whose difference has already been settled',
    'נומינלי': 'Nominal',
    'מדד בבסיס ההסכם': "Index in the agreement's base",
    'מקדם': 'Coefficient',
    'ממודד': 'Linked',
    'שולם בפועל': 'Actually paid',
    'הפרש לתשלום': 'Amount due',
    'שולם': 'Settled',
    'ההפרש שולם': 'Difference settled',
    'סכום ששולם בפועל': 'Amount actually paid',
    'סימון כל התקופה כשולמה': 'Mark the whole period as settled',
    'סה״כ': 'Total',
    'סה״כ תקופה': 'Period total',
    'סה״כ לתשלום': 'Total due',
    'סה״כ נומינלי': 'Total nominal',
    'סה״כ ממודד': 'Total linked',
    'סה״כ שולם בפועל': 'Total actually paid',
    'יתרת הפרשים לתשלום': 'Outstanding difference',
    'תקופת השכירות': 'Rental period',
    'תקופות אופציה': 'Option periods',
    'אין': 'None',
    'ערך מדד הבסיס': 'Base index value',
    'הצמדה מלאה לשני הכיוונים': 'Full linkage in both directions',
    'רק הפרש לתשלום — ללא הפחתה בירידת מדד': 'Amounts due only — no reduction when the index falls',
    'אין חודשים בטווח שנבחר לייצוא.': 'No months fall in the selected export range.',
    'יש לבחור את מועד הסכם השכירות.': 'Choose the date of the rent agreement.',
    'יש לבחור את חודשי תחילת וסיום השכירות.': 'Choose the first and last month of the tenancy.',
    'חודש סיום השכירות מוקדם מחודש ההתחלה.': 'The last month comes before the first month.',
    'יש להזין דמי שכירות חודשיים תקינים.': 'Enter a valid monthly rent.',

    // --- historical interest rate tool ---------------------------------------
    'כלי 6': 'Tool 6',
    'נתוני ריבית היסטוריים': 'Historical interest rate data',
    'ריבית בנק ישראל ופריים, לפי תאריכי שינוי או ברמה חודשית.':
      'Bank of Israel and prime rate, by change date or at monthly level.',
    'נתוני ריבית בנק ישראל ופריים ההיסטוריים': 'Historical Bank of Israel and prime rate data',
    'סדרות': 'Series',
    'טווח ורמת פירוט': 'Range and detail level',
    'רמת פירוט': 'Detail level',
    'תאריכי שינוי בלבד': 'Change dates only',
    'רמה חודשית — ממוצע משוקלל': 'Monthly level — weighted average',
    'תאריך שינוי': 'Change date',
    'ריבית היסטורית': 'Historical interest rate',
    'יש לבחור סדרה אחת לפחות.': 'Choose at least one series.',
    'אין שינויי ריבית בטווח שנבחר.': 'No rate changes in the selected range.',
    'אין נתוני ריבית בטווח שנבחר.': 'No rate data in the selected range.',
    'שינויים בטווח שנבחר.': 'changes in the selected range.',
    'חודשים בטווח שנבחר.': 'months in the selected range.',
    'ריבית הפריים מחושבת כריבית בנק ישראל בתוספת 1.5 נקודות אחוז.':
      'The prime rate is calculated as the Bank of Israel rate plus 1.5 percentage points.',
    'חודש המסומן ב-* הוא חודש שבו בוצע שינוי ריבית בפועל, והריבית המוצגת בו היא ממוצע משוקלל לפי מספר הימים שבהם חלה כל ריבית באותו חודש.':
      'A month marked with * is one where an actual rate change took place; the rate shown for it is a weighted average by the number of days each rate was in effect that month.',
    'חודש שבו בוצע שינוי ריבית בפועל — הריבית המוצגת היא ממוצע משוקלל של הריבית שחלה בכל אחד מימי החודש.':
      'A month in which an actual rate change took place — the rate shown is a weighted average of the rates in effect on each day of the month.',

    // --- shared results and errors -----------------------------------------
    'יש להזין סכום תקין שאינו שלילי.': 'Enter a valid, non-negative amount.',
    'יש לבחור תאריך.': 'Choose a date.',
    'יש לבחור תאריך יעד.': 'Choose a target date.',
    'טוען שערי חליפין…': 'Loading exchange rates…',
    'שערי החליפין אינם זמינים.': 'Exchange rates are unavailable.',
    'לא ניתן לטעון את שערי החליפין.': 'The exchange rates could not be loaded.',
    'שערי החליפין אינם זמינים': 'Exchange rates are unavailable',
    'המדד העדכני חסר': 'The latest index reading is missing',
    'לא ניתן לחשב את השינוי במדד': 'The change in the index cannot be calculated',
    'הריבית הנוכחית חסרה': 'The current rate is missing',
    'מועד ההחלטה הבאה אינו זמין': 'The next decision date is unavailable',
    'לא ניתן לחשב שינוי שנתי': 'The annual change cannot be calculated',
    'הנתונים אינם זמינים כרגע': 'The data is unavailable right now',
    'טבלת שערי החליפין ריקה': 'The exchange-rate table is empty',
    'רשימת המטבעות ריקה': 'The currency list is empty',
    'חוברת העבודה ריקה': 'The workbook is empty',

    // --- export documents ---------------------------------------------------
    'פריט': 'Item',
    'ערך': 'Value',
    'סכום מקורי (₪)': 'Original amount (₪)',
    'סכום מקורי': 'Original amount',
    'מקדם הצמדה': 'Linkage coefficient',
    'סכום מוצמד (₪)': 'Linked amount (₪)',
    'הפרש (₪)': 'Difference (₪)',
    'בסיס החישוב': 'Basis',
    'מדד הבסיס בפועל': 'Base index month used',
    'מדד היעד בפועל': 'Target index month used',
    'ערך מדד היעד (בבסיס מדד הבסיס)': "Target index value (in the base month's base)",
    'הצמדה למדד המחירים לצרכן': 'Consumer price index linkage',
    'שער בסיס': 'Base rate',
    'שער יעד': 'Target rate',
    'שער': 'Rate',
    'הפרשי הצמדה': 'Linkage differences',
    'נתוני חוזה': 'Agreement data',
    'מדד היסטורי': 'Historical index',
    'שערים יציגים של בנק ישראל': 'Bank of Israel representative rates',

    // --- info pages ---------------------------------------------------------
    'אודות': 'About',
    'שיטת החישוב': 'Method',
    'תנאי שימוש והבהרות': 'Terms of Use & Disclaimers',
    'מדיניות פרטיות': 'Privacy policy',
    'הצהרת נגישות': 'Accessibility Statement',
    'צור קשר': 'Contact',
    '← חזרה לעמוד הבית': '← Back to the home page',
    '← חזרה לכל המדריכים': '← Back to all guides',
    'מקורות הנתונים': 'Data sources',
    'מחשבון ההצמדה': 'The linkage calculator',
    'פורמטים': 'Formats',
    'אימייל לחזרה': 'Reply-to email',
    'תוכן ההודעה': 'Message',
    'השאירו שדה זה ריק': 'Leave this field empty',
    'שלח': 'Send',
    'פרטי הפנייה יישלחו אלינו באמצעות Web3Forms וישמשו לצורך טיפול בפנייה ומתן תשובה. מידע נוסף ב':
      'Your details will be sent to us via Web3Forms and used to handle your inquiry and reply. More information in the ',
    'מדיניות הפרטיות': 'privacy policy',
    'statso הוא אתר אישי וחובבני, שאינו מופעל מטעם הלשכה המרכזית לסטטיסטיקה, בנק ישראל או גוף ממשלתי אחר.':
      'statso is a personal, hobby website, not operated on behalf of the Central Bureau of Statistics, the Bank of Israel, or any other government body.',
    '© 2026 מפעיל האתר. נתוני המקור שייכים לגופים המפרסמים.':
      '© 2026 Site operator. Source data belongs to the publishing bodies.',

    // --- currency names -----------------------------------------------------
    'שקל חדש': 'New shekel',
    'דולר ארה״ב': 'US dollar',
    'אירו': 'Euro',
    'ליש״ט': 'Pound sterling',
    'פרנק שווייצרי': 'Swiss franc',
    'ין יפני': 'Japanese yen',
    'דולר קנדי': 'Canadian dollar',
    'דולר אוסטרלי': 'Australian dollar',
    'כתר דני': 'Danish krone',
    'כתר נורווגי': 'Norwegian krone',
    'כתר שוודי': 'Swedish krona',
    'שקל חדש (ILS)': 'New shekel (ILS)',
    'דולר ארה״ב (USD)': 'US dollar (USD)',
    'אירו (EUR)': 'Euro (EUR)',
    'ליש״ט (GBP)': 'Pound sterling (GBP)',
    'פרנק שווייצרי (CHF)': 'Swiss franc (CHF)',
    'ין יפני (JPY)': 'Japanese yen (JPY)',
    'דולר קנדי (CAD)': 'Canadian dollar (CAD)',
    'דולר אוסטרלי (AUD)': 'Australian dollar (AUD)',
    'כתר דני (DKK)': 'Danish krone (DKK)',
    'כתר נורווגי (NOK)': 'Norwegian krone (NOK)',
    'כתר שוודי (SEK)': 'Swedish krona (SEK)',


    // --- guide steps and diagrams -------------------------------------------
    'פותחים חוברת עבודה חדשה, עוברים ללשונית Data / ״נתונים״ ולוחצים על ״יבא נתונים (Power Query)״.':
      'Open a new workbook, go to the Data tab, and click Get Data (Power Query).',
    'אקסל למק בעברית: לשונית נתונים והכפתור ״יבא נתונים (Power Query)״.':
      'Excel for Mac in Hebrew: the Data tab and the Get Data (Power Query) button.',
    'פותחים את כתובת ה-CSV בדפדפן.': 'Open the CSV address in your browser.',
    'פותחים את הקובץ באקסל דרך File ← Open / ״קובץ ← פתיחה״.':
      'Open the file in Excel through File → Open.',
    'הקבצים נשמרים ב-UTF-8 עם BOM, ולכן עברית תיפתח נכון בלי הגדרות מיוחדות. החיסרון: הנתונים קפואים ברגע ההורדה, וצריך לחזור על התהליך בכל עדכון.':
      'The files are saved as UTF-8 with a BOM, so Hebrew opens correctly with no special settings. The drawback: the data is frozen at the moment of download, and the process has to be repeated on every update.',
    'מזינים בתא את נוסחת WEBSERVICE עם כתובת ה-JSON. הפונקציה מחזירה את תוכן הקובץ כטקסט לתא.':
      'Enter the WEBSERVICE formula in a cell with the JSON address. The function returns the file contents into that cell as text.',
    'השיטה מתאימה לשליפת ערך בודד, למשל הריבית הנוכחית, ולא לטבלה שלמה. התוצאה חייבת להיכנס לתא אחד — עד 32,767 תווים.':
      'This suits a single value, such as the current interest rate, rather than a whole table. The result must fit in one cell — up to 32,767 characters.',
    'לקובצי המדד המלאים השיטה אינה מתאימה. משתמשים ב-Power Query, או בקובץ הקטן של החלטת הריבית הבאה.':
      'It does not suit the full index files. Use Power Query, or the small next-rate-decision file.',
    'פותחים חוברת עבודה חדשה ועוברים ללשונית ״נתונים״ (Data). לוחצים על ״יבא נתונים״ (Get Data), ואז על ״יבא נתונים (תצוגה מקדימה)״ (Get Data (Preview)).':
      'Open a new workbook and go to the "Data" tab. Click "Get Data", then "Get Data (Preview)".',
    'אקסל בווינדוס בעברית: לשונית נתונים, הכפתור ״יבא נתונים״ (Get Data) והפריט ״יבא נתונים (תצוגה מקדימה)״ (Get Data (Preview)) בתפריט הנשלף.':
      'Excel on Windows in Hebrew: the Data tab, the "Get Data" button and the "Get Data (Preview)" item in the flyout menu.',
    'בחלון ״יבא נתונים (Power Query)״ (Get Data (Power Query)) בוחרים ״שאילתה ריקה״ (Blank Query).':
      'In the "Get Data (Power Query)" window, choose "Blank Query".',
    'אקסל בווינדוס בעברית: חלון ״יבא נתונים (Power Query)״ (Get Data (Power Query)) והכרטיס ״שאילתה ריקה״ (Blank Query).':
      'Excel on Windows in Hebrew: the "Get Data (Power Query)" window and the "Blank Query" card.',
    'בחלון שנפתח לוחצים על ״עורך מתקדם״ (Advanced Editor).':
      'In the window that opens, click "Advanced Editor".',
    'אקסל בווינדוס בעברית: הכרטיסייה ״בית״ בעורך Power Query והכפתור ״עורך מתקדם״ (Advanced Editor).':
      'Excel on Windows in Hebrew: the Home tab of the Power Query editor and the "Advanced Editor" button.',
    'בחלון שנפתח מוחקים את כל הקוד הקיים ומדביקים במקומו קוד מתוך':
      'In the window that opens, delete all the existing code and paste in its place the code from',
    '. לאחר ההדבקה לוחצים על ״סיום״ (Done).':
      '. After pasting, click "Done".',
    'אקסל בווינדוס בעברית: חלון ״עורך מתקדם״ עם תיבת הקוד וכפתור ״סיום״ (Done).':
      'Excel on Windows in Hebrew: the "Advanced Editor" window with the code box and the "Done" button.',
    'אם מופיעה הודעה כתומה המבקשת לציין כיצד להתחבר (״ציין כיצד להתחבר.״), לוחצים על ״ערוך אישורים״ (Edit Credentials). בחלון שנפתח בוחרים ״אנונימי״ (Anonymous), ואז לוחצים על ״התחבר״ (Connect).':
      'If an orange message appears asking you to specify how to connect ("Specify how to connect."), click "Edit Credentials". In the window that opens, choose "Anonymous", then click "Connect".',
    'אקסל בווינדוס בעברית: הודעת ״ציין כיצד להתחבר.״ והכפתור ״ערוך אישורים״ (Edit Credentials).':
      'Excel on Windows in Hebrew: the "Specify how to connect." message and the "Edit Credentials" button.',
    'אקסל בווינדוס בעברית: חלון ״קבל גישה לתוכן אינטרנט״ עם האפשרות ״אנונימי״ (Anonymous) וכפתור ״התחבר״ (Connect).':
      'Excel on Windows in Hebrew: the "Access Web content" window with the "Anonymous" option and the "Connect" button.',
    'לאחר שהטבלה מופיעה, לוחצים על ״סגור וטען״ (Close & Load).':
      'Once the table appears, click "Close & Load".',
    'אקסל בווינדוס בעברית: הטבלה בעורך Power Query והכפתור ״סגור וטען״ (Close & Load).':
      'Excel on Windows in Hebrew: the table in the Power Query editor and the "Close & Load" button.',
    'לעדכון הנתונים עוברים ללשונית ״נתונים״ (Data) ולוחצים על ״רענן הכל״ (Refresh All).':
      'To update the data, go to the "Data" tab and click "Refresh All".',
    'אקסל בווינדוס בעברית: לשונית נתונים והכפתור ״רענן הכל״ (Refresh All).':
      'Excel on Windows in Hebrew: the Data tab and the "Refresh All" button.',
    'WEBSERVICE אינה זמינה ב-Excel for Mac': 'WEBSERVICE is not available in Excel for Mac',
    'אין צעדים להצגה עבור שילוב זה. אפשר לייבא את הנתונים באמצעות Power Query.':
      'There are no steps to show for this combination. You can import the data with Power Query instead.',
    'שומרים את הדף כקובץ ‎.csv באמצעות': 'Save the page as a .csv file with',
    'Cmd+S במק.': 'Cmd+S on a Mac.',
    'Ctrl+S בווינדוס.': 'Ctrl+S on Windows.',
    'קבל נתונים': 'Get Data', 'ממקורות אחרים': 'From Other Sources', 'מהאינטרנט': 'From Web',
    'רענן הכל': 'Refresh All', 'כתובת URL': 'URL', 'אישור': 'OK', 'נווט': 'Navigator',
    'טען': 'Load', 'קובץ': 'File', 'פתיחה': 'Open', 'שמירה': 'Save',
    'שורת הנוסחאות': 'Formula bar', 'תצוגה מקדימה': 'Preview',
    'חודש X': 'Month X', 'במהלך חודש X': 'During month X',
    'מדד ידוע = מדד X-1': 'Known index = index X-1',
    '15 בחודש X+1': '15th of month X+1', 'פרסום מדד בגין X': 'Index for X published',

    // --- CPI concepts guide --------------------------------------------------
    '1. שני שמות, אותו מדד': '1. Two names, one index',
    '2. מתי מתפרסם המדד': '2. When the index is published',
    '3. מה המדד כולל': '3. What the index covers',
    '4. מדדים נגזרים': '4. Derived indices',
    'מדד בגין חודש X': 'The index for month X',
    'הוא המדד שמודד את המחירים בחודש X עצמו. הוא מתפרסם ב-15 בחודש X+1.':
      'measures prices in month X itself. It is published on the 15th of month X+1.',
    'מדד ידוע במועד מסוים': 'The known index at a given date',
    'הוא המדד האחרון שפורסם עד אותו מועד — כלומר המדד של החודש הקודם.':
      'is the last index published by that date — that is, the previous month\'s index.',
    'לכן, לתשלום שחל בחודש X: מדד ידוע = המדד של חודש X-1; מדד בגין = המדד של חודש X.':
      'So for a payment falling in month X: known index = the index of month X-1; index for the month = the index of month X.',
    'אלה אותם מספרים בדיוק; ההבדל הוא רק לאיזה חודש מצמידים אותם. הפער ביניהם הוא חודש אחד.':
      'These are exactly the same numbers; the only difference is which month they are attached to. The gap between them is one month.',
    'המחשבון בדף הבית': 'The calculator on the home page',
    'מיישם בדיוק את ההבחנה הזו.': 'applies exactly this distinction.',
    'לפי הלמ״ס, הודעות מדדי המחירים מתפרסמות ב-15 בכל חודש בשעה 18:30, עבור החודש שקדם לו.':
      'According to the CBS, price index releases are published on the 15th of each month at 18:30, covering the month before.',
    'אם ה-15 בחודש נופל ביום שישי, בשבת, בערב חג או בחג — הפרסום מוקדם ליום שישי או לערב החג, בשעה 14:00.':
      'If the 15th falls on a Friday, a Saturday, a holiday eve or a holiday, publication is brought forward to the Friday or holiday eve, at 14:00.',
    'ציר הזמן של מדד בגין ומדד ידוע: פער קבוע של חודש אחד.':
      'The timeline of the two readings: a fixed one-month gap.',
    'לפי הלמ״ס, המדד מודד את שינוי העלות של סל הצריכה של משק בית ממוצע; הלמ״ס מתמחרת מדי חודש כ-1,300 מוצרים ושירותים מייצגים.':
      'According to the CBS, the index measures the change in the cost of an average household\'s consumption basket; the CBS prices around 1,300 representative goods and services each month.',
    'עשר קבוצות הצריכה הראשיות הן: מזון (ללא ירקות ופירות); ירקות ופירות; דיור; תחזוקת הדירה; ריהוט וציוד לבית; הלבשה והנעלה; בריאות; חינוך, תרבות ובידור; תחבורה ותקשורת; שונות.':
      'The ten main consumption groups are: food (excluding fruit and vegetables); fruit and vegetables; housing; dwelling maintenance; furniture and household equipment; clothing and footwear; health; education, culture and entertainment; transport and communication; miscellaneous.',
    'מה המדד לא כולל:': 'What the index leaves out:',
    'רכישת דירה. קבוצת ״דיור״ במדד מודדת את שירותי הדיור — בעיקר שכר דירה — ולא את מחיר קניית הדירה. מחירי רכישת דירות נמדדים במדד נפרד של הלמ״ס, ״מדד ומחירים ממוצעים משוק הדירות״.':
      'Buying a home. The “housing” group measures housing services — mainly rent — not the price of buying a dwelling. Home purchase prices are measured in a separate CBS index, the “Index and average prices of the dwellings market”.',
    'הלמ״ס מפרסמת גם חתכים שמנטרלים רכיבים תנודתיים: המדד ללא ירקות ופירות; המדד ללא דיור; המדד ללא ירקות ופירות וללא דיור; המדד ללא אנרגיה.':
      'The CBS also publishes cuts that strip out volatile components: the index excluding fruit and vegetables; excluding housing; excluding both; and excluding energy.',
    'החתכים האלה משמשים כדי לראות מגמה בסיסית בלי רעש עונתי או תנודות אנרגיה.':
      'These cuts are used to see the underlying trend without seasonal noise or energy swings.',
    // --- guides -------------------------------------------------------------
    'לומדים לעבוד עם הנתונים': 'Working with the data',
    'הסברים מעשיים לשימוש בנתוני statso בכלים מוכרים.':
      'Practical walkthroughs for using statso data in the tools you already have.',
    'שאיבת נתונים מ-statso לתוך Excel': 'Pulling statso data into Excel',
    'כך מייבאים ריבית או מדד לאקסל, עם הוראות מותאמות למחשב ולשיטת העבודה.':
      'How to import the rate or the index into Excel, with steps matched to your machine and method.',
    'מדד בגין מול מדד ידוע — ומה המדד בכלל מודד':
      'Index for the month vs known index — and what the index actually measures',
    'ההבדל בין שני המדדים, מתי הלמ״ס מפרסמת, ומה נכלל בסל.':
      'The difference between the two, when the CBS publishes, and what the basket holds.',
    'ההבדל בין שני המדדים, מועד הפרסום והרכב סל הצריכה.':
      'The difference between the two, the publication date and what the consumption basket holds.',
    'מדריך אינטראקטיבי': 'Interactive guide',
    'בחרו את סביבת העבודה ושיטת הייבוא, והשלבים יתעדכנו מיד.':
      'Pick your environment and import method, and the steps update instantly.',
    'מושגים במדד המחירים לצרכן': 'Consumer price index concepts',
    'מערכת הפעלה': 'Operating system',
    'מק (macOS)': 'Mac (macOS)',
    'ווינדוס (Windows)': 'Windows',
    'שיטה': 'Method',
    'Power Query (מומלץ)': 'Power Query (recommended)',
    'הורדה ידנית של CSV': 'Manual CSV download',
    'נוסחת WEBSERVICE': 'WEBSERVICE formula',
    'נתונים': 'Data',
    'העתק': 'Copy',
    'הועתק': 'Copied',
    'אקסל בעברית': 'Excel in Hebrew',
    'אקסל באנגלית': 'Excel in English',
    'המדריך מסביר את ההבחנה': 'The guide explains the distinction',
    'סכום מוצמד = הסכום × (מדד היעד ÷ מדד הבסיס).':
      'Linked amount = amount × (target index ÷ base index).',
    'שני שמות, אותו מדד': 'Two names, one index',
    'מתי מתפרסם המדד': 'When the index is published',
    'מה המדד כולל': 'What the index covers',
    'מדדים נגזרים': 'Derived indices',
    'דוגמה מהנתונים העדכניים': 'An example from the current data',
    'לא ניתן להציג דוגמה מהנתונים כרגע': 'No example can be shown from the data right now',
    'מעבר ל-Power Query': 'Switch to Power Query'
  };

  // Sentences the modules assemble at run time. First match wins.
  const enPatterns = [
    [/^סכום ממומר \((.+)\)$/, 'Converted amount ($1)'],
    [/^(.+) \(מוסכם\)$/, '$1 (agreed)'],
    [/^(.+) \(מדד ידוע במועד ההסכם\)$/, '$1 (known index at signing)'],
    [/^(.+) ← (.+) · מדד בסיס (.+)$/, '$1 → $2 · base index $3'],
    [/^שבוע של (.+)$/, 'Week of $1'],
    [/^(\d+) שורות בטווח שנבחר\. כל שער שפורסם בטווח\. הסדרות אינן רציפות — אין פרסום בסופי שבוע ובחלק מהחגים\.(.*)$/,
      '$1 rows in the selected range. Every rate published in it; the series are not continuous — nothing is published at weekends or on some holidays.$2'],
    [/^(\d+) שורות בטווח שנבחר\. כל שורה היא ממוצע השערים שפורסמו באותה תקופה\.(.*)$/,
      '$1 rows in the selected range. Each row is the average of the rates published in that period.$2'],
    [/^ מוצגות (\d+) השורות הראשונות; הייצוא וההעתקה כוללים את כל הטווח\.$/,
      ' Showing the first $1 rows; the export and the copy cover the whole range.'],
    [/^בחודש (.+), מדד בגין הוא מדד (.+)\. מדד ידוע באותו חודש הוא מדד (.+)\. מדד בגין החודש מתפרסם ב-(.+)$/,
      'In $1, the index for the month is the $2 reading. The known index that month is the $3 reading. The index for $1 is published on $4'],
    [/^(.+)–(.+) · (.+) ₪ לחודש$/, '$1–$2 · $3 ₪ per month'],
    [/^מדד (.+) = (.+) · מדד (.+) = (.+) \(באותו בסיס\) · מקדם (.+)$/,
      'Index $1 = $2 · index $3 = $4 (same base) · coefficient $5'],
    [/^שער (.+) · לפי השער שפורסם ל־(.+)$/, 'Rate $1 · using the rate published for $2'],
    [/^שער (.+) ב־(.+) = (.+) · ב־(.+) = (.+) · הפרש (.+) ₪$/,
      'Rate $1 on $2 = $3 · on $4 = $5 · difference $6 ₪'],
    [/^(\d+(?:\.\d+)?) שערים שפורסמו$/, '$1 published rates'],
    [/^המדד לחודש (.+) אינו זמין\. הטווח הוא (.+)\.$/,
      'The index for $1 is not available. The available range is $2.'],
    [/^המדד לחודש (.+) (אינו קיים בסדרה|מחוץ לטווח הנתונים)\. הטווח הזמין הוא (.+)\.$/,
      'The index for $1 is unavailable. The available range is $3.'],
    [/^מדד הבסיס לחודש (.+) אינו זמין בסדרה\.$/, 'The base index for $1 is not in the series.'],
    [/^המדד לחודש (.+) טרם פורסם$/, 'The index for $1 has not been published yet'],
    [/^יש להשלים את חודשי תקופת האופציה (\d+)\.$/, 'Complete the months of option period $1.'],
    [/^בתקופת אופציה (\d+) חודש הסיום מוקדם מחודש ההתחלה\.$/,
      'In option period $1 the last month comes before the first.'],
    [/^יש להזין דמי שכירות חודשיים בתקופת אופציה (\d+)\.$/,
      'Enter a monthly rent for option period $1.'],
    [/^תקופת אופציה (\d+)$/, 'Option period $1'],
    [/^לא ניתן לטעון את (.+)$/, 'Could not load $1'],
    [/^אין שער ל(.+) לפני (.+)\.$/, 'No rate for $1 before $2.'],
    [/^אין נתוני שער עבור (.+)\.$/, 'No rate data for $1.'],
    [/^לפי השער שפורסם ל־(.+)$/, 'Using the rate published for $1'],
    [/^מדד ידוע במועד ההסכם: (.+)$/, 'Known index at signing: $1'],
    [/^מדד בסיס מוסכם: (.+)$/, 'Agreed base index: $1'],
    [/^(\d+) חודשים בטווח שנבחר\..*$/,
      '$1 months in the selected range. The chained index is expressed in the 9/1951 base, '
      + 'and the published column is the reading in the base in force that month.'],
    [/^שער ל־(.+)$/, 'Rate at $1'],
    [/^שער סוף (\d+)$/, 'Year-end $1'],
    [/^ממוצע (\d+)$/, '$1 average'],
    [/^(\d+) שערים שפורסמו$/, '$1 published rates'],
    [/^הופק ב־(.+?) · נתוני מקור: הלשכה המרכזית לסטטיסטיקה ובנק ישראל · statso$/,
      'Produced $1 · Sources: Israel Central Bureau of Statistics and Bank of Israel · statso'],
    [/^סך ההפרשים לתשלום:$/, 'Total amount due:'],
    [/^שלב (\d+)$/, 'Step $1']
  ];

  Statso.lang = {en: en, enPatterns: enPatterns};
})(window);
