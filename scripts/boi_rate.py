import csv
import datetime
import io
import os

from .common import ParseError, ValidationError, dumps_csv, dumps_json, fmt_number

# The trailing ".." is load-bearing: replacing it with /all makes the API return 404.
BOI_URL = ("https://edge.boi.gov.il/FusionEdgeServer/sdmx/v2/data/dataflow/"
           "BOI.STATISTICS/BR/1.0/MNT_RIB_BOI_D..?format=csv")
SERIES_CODE = "MNT_RIB_BOI_D"
FIRST_DATE = "1994-01-27"
FIRST_RATE = 10.5
MIN_OBSERVATIONS = 11000
MIN_CHANGE_POINTS = 150
REQUIRED_COLUMNS = ("SERIES_CODE", "TIME_PERIOD", "OBS_VALUE")


def parse_observations(raw):
    try:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    except UnicodeError as exc:
        raise ParseError(f"invalid BOI encoding: {exc}") from exc
    fields = reader.fieldnames or []
    missing = [name for name in REQUIRED_COLUMNS if name not in fields]
    if missing:
        raise ParseError(f"BOI CSV missing columns: {', '.join(missing)}")
    observations = []
    for line, row in enumerate(reader, 2):
        if (row.get("SERIES_CODE") or "").strip() != SERIES_CODE:
            continue
        value = (row.get("OBS_VALUE") or "").strip()
        if not value:
            continue
        date_text = (row.get("TIME_PERIOD") or "").strip()
        try:
            datetime.date.fromisoformat(date_text)
            observations.append((date_text, float(value)))
        except (ValueError, TypeError) as exc:
            raise ParseError(f"invalid BOI row {line}: {exc}") from exc
    observations.sort(key=lambda item: item[0])
    for left, right in zip(observations, observations[1:]):
        if left[0] == right[0]:
            raise ValidationError(f"duplicate BOI date {left[0]}")
    return observations


def derive_change_points(observations):
    out, previous = [], None
    for date_text, value in observations:
        if previous is None or value != previous:
            out.append({"date": date_text, "rate": value})
        previous = value
    return out


def validate(changes, observations, previous=None):
    if len(observations) < MIN_OBSERVATIONS:
        raise ValidationError(f"BOI observation count below minimum: {len(observations)}")
    if not changes or changes[0] != {"date": FIRST_DATE, "rate": FIRST_RATE}:
        raise ValidationError("BOI first change point is invalid")
    if len(changes) < MIN_CHANGE_POINTS:
        raise ValidationError(f"BOI change-point count below minimum: {len(changes)}")
    if (previous and len(changes) < previous.get("count", 0)
            and os.environ.get("STATSO_ALLOW_SHRINK") != "1"):
        raise ValidationError("BOI change-point dataset would shrink")
    if changes[-1]["rate"] != observations[-1][1]:
        raise ValidationError("BOI latest source value does not match latest change")
    prior = None
    for change in changes:
        if prior is not None and change["date"] <= prior:
            raise ValidationError("BOI change dates are not strictly ascending")
        prior = change["date"]
        if change["rate"] <= 0:
            raise ValidationError(f"invalid BOI rate at {change['date']}")
        fmt_number(change["rate"])


def to_json_bytes(changes):
    obj = {"dataset": "boi_interest_rate", "source": "בנק ישראל",
        "source_url": BOI_URL, "series_code": SERIES_CODE, "unit": "percent",
        "content": "change_points_only", "count": len(changes),
        "first_change_date": changes[0]["date"], "last_change_date": changes[-1]["date"],
        "current_rate": changes[-1]["rate"], "changes": changes}
    return dumps_json(obj)


def to_csv_bytes(changes):
    return dumps_csv(("date", "rate"),
                     ([item["date"], fmt_number(item["rate"])] for item in changes))
