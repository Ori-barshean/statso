"""Record a re-checked accessibility statement; dry run unless --reviewed.

Set the review date in both <time> elements of #accessibility-page and re-pin
STATEMENT_DATE / STATEMENT_FINGERPRINT in the guard test.
"""
import argparse
import re
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .common import REPO_ROOT, write_atomic
from .statement_fingerprint import TIME_RE, accessibility_page, fingerprint

HTML_FILE = Path("index.html")
GUARD_FILE = Path("tests") / "test_a11y_round8_source.py"
COMMAND = "python3 -m scripts.update_statement_date --reviewed"
BLOCK_RE = re.compile(r'<div class="prose-guide" data-lang="(he|en)"[^>]*>(.*?)</div>', re.S)
CONSTANT_RE = r"^{name} = '([^'\n]*)'$"
MONTHS_HE = ("ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני", "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר")
MONTHS_EN = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
REMINDER = (
    "כל משפט בהצהרה חייב להיות נתמך בקוד, בטסט או בבדיקה שבוצעה בפועל.",
    "Every statement sentence must be supported by code, tests or a check actually performed.",
)


class StatementError(Exception):
    pass


def israel_today():
    return datetime.now(ZoneInfo("Asia/Jerusalem")).date()


def parse_date(text):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD")
    try:
        day = date.fromisoformat(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    if day > israel_today():
        raise argparse.ArgumentTypeError("review date cannot be later than today in Asia/Jerusalem")
    return day


def visible_dates(day):
    return {"he": f"{day.day} ב{MONTHS_HE[day.month - 1]} {day.year}",
            "en": f"{day.day} {MONTHS_EN[day.month - 1]} {day.year}"}


def time_elements(html):
    try:
        page = accessibility_page(html)
    except ValueError as exc:
        raise StatementError(str(exc)) from exc
    blocks = list(BLOCK_RE.finditer(html, page.start(), page.end()))
    if sorted(block.group(1) for block in blocks) != ['en', 'he']:
        raise StatementError("accessibility page must have exactly one he and one en block")
    elements = {}
    for block in blocks:
        lang = block.group(1)
        count = len(re.findall(r'<time\b', block.group(2)))
        matches = list(TIME_RE.finditer(html, block.start(2), block.end(2)))
        if count != 1 or len(matches) != 1:
            raise StatementError(f"{lang}: expected one time element; found {count} <time tags and {len(matches)} valid elements")
        elements[lang] = matches[0]
    return elements


def read_constant(text, name):
    assignments = re.findall(rf"^[ \t]*{name}[ \t]*=", text, re.M)
    matches = list(re.finditer(CONSTANT_RE.format(name=name), text, re.M))
    if len(assignments) != 1 or len(matches) != 1:
        raise StatementError(f"expected exactly one {name} = '...' assignment; found {len(assignments)}")
    return matches[0]


def rewrite(html, guard, day):
    elements = time_elements(html)
    constants = {name: read_constant(guard, name)
                 for name in ('STATEMENT_DATE', 'STATEMENT_FINGERPRINT')}
    iso = day.isoformat()
    visible = visible_dates(day)
    new_html = html
    for lang, match in sorted(elements.items(), key=lambda item: item[1].start(), reverse=True):
        replacement = f'<time datetime="{iso}">{visible[lang]}</time>'
        new_html = new_html[:match.start()] + replacement + new_html[match.end():]
    values = {'STATEMENT_DATE': iso, 'STATEMENT_FINGERPRINT': fingerprint(new_html)}
    new_guard = guard
    for name, match in sorted(constants.items(), key=lambda item: item[1].start(1), reverse=True):
        new_guard = new_guard[:match.start(1)] + values[name] + new_guard[match.end(1):]
    report = [f"{lang}: {elements[lang].group(1)} / {elements[lang].group(2)} -> {iso} / {visible[lang]}"
              for lang in ('he', 'en')]
    report += [f"{name}: {match.group(1)} -> {values[name]}" for name, match in constants.items()]
    return new_html, new_guard, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reviewed', action='store_true')
    parser.add_argument('--date', type=parse_date)
    parser.add_argument('--root', type=Path, default=REPO_ROOT)
    args = parser.parse_args(argv)
    day = args.date or israel_today()
    html_path, guard_path = args.root / HTML_FILE, args.root / GUARD_FILE
    try:
        html = html_path.read_bytes().decode('utf-8')
        guard = guard_path.read_bytes().decode('utf-8')
        new_html, new_guard, report = rewrite(html, guard, day)
    except (OSError, UnicodeError, StatementError) as exc:
        print(f"update_statement_date: {exc}", file=sys.stderr)
        return 1
    print('\n'.join(report + list(REMINDER)))
    if (html, guard) == (new_html, new_guard):
        print('nothing to change')
        return 0
    if not args.reviewed:
        print(f'dry run: nothing written. After re-checking the statement, run: {COMMAND}')
        return 0
    try:
        write_atomic(html_path, new_html.encode('utf-8'))
    except OSError as exc:
        print(f"update_statement_date: {exc}", file=sys.stderr)
        return 1
    try:
        write_atomic(guard_path, new_guard.encode('utf-8'))
    except OSError as exc:
        print(f"update_statement_date: {exc}", file=sys.stderr)
        try:
            write_atomic(html_path, html.encode('utf-8'))
            print("update_statement_date: index.html was restored; nothing changed.", file=sys.stderr)
        except OSError as restore_exc:
            print(f"update_statement_date: could not restore index.html ({restore_exc}); run the command again to finish.", file=sys.stderr)
        return 1
    print(f'updated {html_path} and {guard_path}')
    print('index.html changed: rebuild the offline file with python3 -m scripts.build_offline '
          '(writes ~/Desktop/statso-test.html).')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
