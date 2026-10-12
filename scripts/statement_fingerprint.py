"""Fingerprint of the accessibility statement text without its review dates.

Shared by tests/test_a11y_round8_source.py (the guard) and
scripts/update_statement_date.py (which re-pins the guard).
"""
import hashlib
import re

PAGE_RE = re.compile(r'<article[^>]*id="accessibility-page".*?</article>', re.S)
TIME_RE = re.compile(r'<time datetime="([^"]*)">([^<]*)</time>')


def accessibility_page(html):
    match = PAGE_RE.search(html)
    if match is None:
        raise ValueError('no <article id="accessibility-page"> in the HTML')
    if html.count('id="accessibility-page"') != 1 or match.group(0).count('<article') != 1:
        raise ValueError('the accessibility page must be one well-formed <article> (missing </article>, nesting or a duplicate id)')
    return match


def fingerprint(html):
    body = TIME_RE.sub('<time>', accessibility_page(html).group(0))
    return hashlib.sha256(' '.join(body.split()).encode('utf-8')).hexdigest()
