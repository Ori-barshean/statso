import json
import os
import unicodedata
from urllib.parse import urlencode

from .common import (ChainedBaseNotFound, ParseError, ValidationError,
                     dumps_csv, dumps_json, fmt_number, http_get)

CBS_URL = "https://api.cbs.gov.il/index/data/price"
CBS_INDEX_ID = 200010
PAGE_SIZE = 1000
MAX_PAGES = 200
ANCHOR = "1950 יולי"
CHAINED_FIELD = "chained_1950_07"
EXPORT_FROM = "2000-01"
MIN_OBSERVATIONS = 848
MIN_EXPORTED = 320
SOURCE_URL = (f"{CBS_URL}?id={CBS_INDEX_ID}&format=json&download=false&coef=true")


def _norm(value):
    return " ".join(unicodedata.normalize("NFC", str(value)).strip().split())


def page_url(page):
    return CBS_URL + "?" + urlencode({"id": CBS_INDEX_ID, "format": "json",
        "download": "false", "coef": "true", "page": page, "pagesize": PAGE_SIZE})


def extract_rows(payload):
    months = payload.get("month") if isinstance(payload, dict) else None
    if not isinstance(months, list) or not months:
        raise ParseError("CBS payload has no non-empty month list")
    entry = next((item for item in months if item.get("code") == CBS_INDEX_ID), months[0])
    rows = entry.get("date") if isinstance(entry, dict) else None
    if not isinstance(rows, list):
        raise ParseError("CBS month entry date is not a list")
    return rows


def extract_paging(payload):
    paging = payload.get("paging") if isinstance(payload, dict) else None
    try:
        values = paging["current_page"], paging["last_page"], paging["total_items"]
    except (TypeError, KeyError):
        raise ParseError("CBS payload has invalid paging") from None
    if any(isinstance(v, bool) or not isinstance(v, int) for v in values):
        raise ParseError("CBS paging fields must be integers")
    return values


def _fetch_payload(fetch, page):
    try:
        return json.loads(fetch(page_url(page)).decode("utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ParseError(f"invalid CBS JSON on page {page}: {exc}") from exc


def fetch_all_pages(fetch=http_get):
    first = _fetch_payload(fetch, 1)
    current, last, total = extract_paging(first)
    if current != 1 or last < 1 or last > MAX_PAGES:
        raise ParseError(f"invalid CBS page range: current={current}, last={last}")
    rows = list(extract_rows(first))
    for page in range(2, last + 1):
        payload = _fetch_payload(fetch, page)
        current2, last2, total2 = extract_paging(payload)
        if current2 != page or last2 != last or total2 != total:
            raise ParseError(f"CBS paging drift on page {page}")
        rows.extend(extract_rows(payload))
    return rows, total


def resolve_chained(row):
    try:
        current = row["currBase"]
        if _norm(current["baseDesc"]) == ANCHOR:
            return float(current["value"])
        for previous in (row.get("prevBase") or []):
            if _norm(previous.get("baseDesc", "")) == ANCHOR:
                return float(previous["value"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ParseError(f"invalid CBS row: {exc}") from exc
    raise ChainedBaseNotFound(f"{row.get('year')}-{row.get('month')}: no '{ANCHOR}' base")


def build_records(rows):
    records = []
    seen = set()
    for row in rows:
        try:
            year, month_num = int(row["year"]), int(row["month"])
            current = row["currBase"]
            record = {"month": f"{year:04d}-{month_num:02d}", "year": year,
                "month_num": month_num, "value": float(current["value"]),
                "base_desc": _norm(current["baseDesc"]),
                CHAINED_FIELD: resolve_chained(row)}
        except (KeyError, TypeError, ValueError) as exc:
            raise ParseError(f"invalid CBS row: {exc}") from exc
        key = year, month_num
        if key in seen:
            raise ValidationError(f"duplicate construction inputs month {record['month']}")
        seen.add(key)
        records.append(record)
    records.sort(key=lambda r: (r["year"], r["month_num"]))
    return records


def validate(records, total_items):
    if len(records) != total_items:
        raise ValidationError(f"construction inputs count {len(records)} != source total {total_items}")
    if len(records) < MIN_OBSERVATIONS:
        raise ValidationError(f"construction inputs count below minimum: {len(records)}")
    if not records or records[0]["month"] > "1956-01":
        raise ValidationError("construction inputs history does not reach back to 1956-01")
    previous_month = None
    for record in records:
        ordinal = record["year"] * 12 + record["month_num"] - 1
        if not 1 <= record["month_num"] <= 12 or (previous_month is not None and ordinal != previous_month + 1):
            raise ValidationError(f"construction inputs months not consecutive at {record['month']}")
        previous_month = ordinal
        if record["value"] <= 0 or record[CHAINED_FIELD] <= 0 or not record["base_desc"]:
            raise ValidationError(f"invalid construction inputs observation {record['month']}")
        fmt_number(record["value"]); fmt_number(record[CHAINED_FIELD])


def export_records(records):
    return [r for r in records if r["month"] >= EXPORT_FROM]


def validate_export(exported, previous=None):
    if not exported or exported[0]["month"] != EXPORT_FROM:
        raise ValidationError("construction inputs export does not start at 2000-01")
    if len(exported) < MIN_EXPORTED:
        raise ValidationError(f"construction inputs export count below minimum: {len(exported)}")
    previous_month = None
    for record in exported:
        ordinal = record["year"] * 12 + record["month_num"] - 1
        if previous_month is not None and ordinal != previous_month + 1:
            raise ValidationError(f"construction inputs months not consecutive at {record['month']}")
        previous_month = ordinal
    if (previous and len(exported) < previous.get("count", 0)
            and os.environ.get("STATSO_ALLOW_SHRINK") != "1"):
        raise ValidationError("construction inputs dataset would shrink")


def to_json_bytes(exported):
    obj = {"dataset": "israel_construction_inputs",
        "source": "הלשכה המרכזית לסטטיסטיקה (CBS)",
        "source_url": SOURCE_URL, "series_id": str(CBS_INDEX_ID), "chained_base": ANCHOR,
        "chained_base_value": 100.0, "count": len(exported),
        "first_month": exported[0]["month"], "last_month": exported[-1]["month"],
        "observations": exported}
    return dumps_json(obj)


def to_csv_bytes(exported):
    header = ("month", "year", "month_num", "value", "base_desc", CHAINED_FIELD)
    rows = ([r["month"], str(r["year"]), str(r["month_num"]), fmt_number(r["value"]),
             r["base_desc"], fmt_number(r[CHAINED_FIELD])] for r in exported)
    return dumps_csv(header, rows)
