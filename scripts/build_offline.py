import argparse
import pathlib
import re
import sys

from .common import REPO_ROOT, StatsoError, write_atomic

_HTML_UNSAFE = {"<": "\\u003C", ">": "\\u003E", "\u2028": "\\u2028", "\u2029": "\\u2029"}
_STYLE_RE = re.compile(r'<link\b[^>]*\bdata-inline="style"[^>]*>', re.IGNORECASE)
_SCRIPT_RE = re.compile(r'<script\b[^>]*\bdata-inline="script"[^>]*>\s*</script>', re.IGNORECASE)
_JSON_RE = re.compile(r'(<script\b[^>]*\bdata-inline="json"[^>]*>)(\s*)(</script>)', re.IGNORECASE)
_ATTR_RE = re.compile(r'\b([\w-]+)="([^"]*)"')
_FORBIDDEN = ("</script", "</style", "<!--", "-->")


def escape_json_for_html(text: str) -> str:
    return "".join(_HTML_UNSAFE.get(ch, ch) for ch in text)


def default_output_path():
    return pathlib.Path.home() / "Desktop" / "statso-test.html"


def _attributes(tag):
    return dict(_ATTR_RE.findall(tag))


def _read_source(relative_path, kind):
    path = REPO_ROOT / relative_path
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise StatsoError(f"cannot inline {relative_path}: {exc}") from exc
    if kind in {"style", "script"}:
        lowered = text.lower()
        found = next((token for token in _FORBIDDEN if token in lowered), None)
        if found:
            raise StatsoError(f"unsafe token {found!r} in {relative_path}")
    return text


def build(*, out=None, source=None):
    output_path = default_output_path() if out is None else pathlib.Path(out)
    source_path = REPO_ROOT / "index.html" if source is None else pathlib.Path(source)
    try:
        html = source_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise StatsoError(f"cannot read UI source: {exc}") from exc
    if len(_STYLE_RE.findall(html)) < 1:
        raise StatsoError("UI source must contain at least one style marker")
    if len(_SCRIPT_RE.findall(html)) < 10:
        raise StatsoError("UI source must contain at least ten script markers")
    if len(_JSON_RE.findall(html)) != 3:
        raise StatsoError("UI source must contain exactly three JSON markers")

    def style_replace(match):
        attrs = _attributes(match.group(0))
        if "href" not in attrs:
            raise StatsoError("inline style marker has no href")
        return "<style>\n" + _read_source(attrs["href"], "style") + "\n</style>"

    def script_replace(match):
        attrs = _attributes(match.group(0))
        relative = attrs.get("data-offline-src") or attrs.get("src")
        if not relative:
            raise StatsoError("inline script marker has no source")
        return "<script>\n" + _read_source(relative, "script") + "\n</script>"

    def json_replace(match):
        attrs = _attributes(match.group(1))
        if "data-src" not in attrs:
            raise StatsoError("inline JSON marker has no data source")
        payload = escape_json_for_html(_read_source(attrs["data-src"], "json"))
        return match.group(1) + "\n" + payload + "\n" + match.group(3)

    transformed = _STYLE_RE.sub(style_replace, html)
    transformed = _SCRIPT_RE.sub(script_replace, transformed)
    transformed = _JSON_RE.sub(json_replace, transformed)
    if 'data-inline="style"' in transformed or 'data-inline="script"' in transformed:
        raise StatsoError("offline transform left asset markers behind")
    if transformed.count('data-inline="json"') != 3:
        raise StatsoError("offline transform left an invalid number of JSON markers")
    remaining = re.findall(r'<script\b[^>]*\bdata-inline="json"[^>]*>(.*?)</script>', transformed,
                           flags=re.IGNORECASE | re.DOTALL)
    if len(remaining) != 3 or any(not content.strip() for content in remaining):
        raise StatsoError("offline transform did not embed all JSON datasets")
    return write_atomic(output_path, transformed.encode("utf-8"))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build the single-file offline statso dashboard")
    parser.add_argument("--out", type=pathlib.Path, default=None)
    args = parser.parse_args(argv)
    try:
        changed = build(out=args.out)
    except StatsoError as exc:
        print(f"statso offline build failed: {exc}", file=sys.stderr)
        return 1
    destination = default_output_path() if args.out is None else args.out
    print(f"offline dashboard: {destination} ({'updated' if changed else 'unchanged'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
