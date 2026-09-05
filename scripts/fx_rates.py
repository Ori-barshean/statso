import argparse
import csv
import datetime
import io
import json
import math
import os
import pathlib
import re
import sys

from .common import (DATA_DIR, ParseError, StatsoError, ValidationError,
                     dumps_csv, dumps_json, fmt_number, http_get, write_atomic)

BASE_URL = ("https://edge.boi.gov.il/FusionEdgeServer/sdmx/v2/data/dataflow/"
            "BOI.STATISTICS/EXR/1.0/")
CURRENCIES = ("USD", "EUR", "GBP", "CHF", "JPY", "CAD", "AUD", "DKK", "NOK", "SEK")
SERIES_KEY = "+".join(f"RER_{code}_ILS" for code in CURRENCIES) + ".."
FULL_URL = BASE_URL + SERIES_KEY + "?format=csv"
DEFAULT_LAST_N = 10
EXPECTED_UNITS = {code: (100 if code == "JPY" else 1) for code in CURRENCIES}
FIRST_DATES = {"USD": "1948-05-15", "EUR": "1999-01-04", "GBP": "1962-02-10",
    "CHF": "1962-02-10", "JPY": "1974-11-10", "CAD": "1962-02-10",
    "AUD": "1962-02-10", "DKK": "1962-02-10", "NOK": "1962-02-10",
    "SEK": "1962-02-10"}
MIN_COUNTS = {"USD": 13273, "EUR": 6775, "GBP": 12897, "CHF": 12892,
    "JPY": 12886, "CAD": 12893, "AUD": 12901, "DKK": 12894,
    "NOK": 12895, "SEK": 12892}
REQUIRED_COLUMNS = ("SERIES_CODE", "BASE_CURRENCY", "COUNTER_CURRENCY",
                    "UNIT_MULT", "TIME_PERIOD", "OBS_VALUE")
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")


def recent_url(last_n=DEFAULT_LAST_N):
    if isinstance(last_n, bool) or not isinstance(last_n, int) or last_n < 1:
        raise ValueError("last_n must be a positive integer")
    return FULL_URL + f"&lastNObservations={last_n}"


def parse_observations(raw):
    try:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    except UnicodeError as exc:
        raise ParseError(f"invalid BOI FX encoding: {exc}") from exc
    fields = reader.fieldnames or []
    missing = [name for name in REQUIRED_COLUMNS if name not in fields]
    if missing:
        raise ParseError(f"BOI FX CSV missing columns: {', '.join(missing)}")
    series = {code: [] for code in CURRENCIES}
    for line, row in enumerate(reader, 2):
        series_code = (row.get("SERIES_CODE") or "").strip()
        if not series_code.startswith("RER_") or not series_code.endswith("_ILS"):
            raise ValidationError(f"unexpected BOI FX series code {series_code!r} at row {line}")
        code = series_code[4:-4]
        if code not in series:
            raise ValidationError(f"unexpected BOI FX series code {series_code!r} at row {line}")
        if (row.get("BASE_CURRENCY") or "").strip() != code:
            raise ValidationError(f"unexpected base currency at BOI FX row {line}")
        if (row.get("COUNTER_CURRENCY") or "").strip() != "ILS":
            raise ValidationError(f"unexpected counter currency at BOI FX row {line}")
        unit_mult = (row.get("UNIT_MULT") or "").strip()
        expected_mult = "2" if code == "JPY" else "0"
        if unit_mult != expected_mult:
            raise ValidationError(f"unexpected UNIT_MULT {unit_mult!r} for {code}")
        date_text = (row.get("TIME_PERIOD") or "").strip()
        value_text = (row.get("OBS_VALUE") or "").strip()
        try:
            if not DATE_RE.fullmatch(date_text):
                raise ValueError("date is not YYYY-MM-DD")
            datetime.date.fromisoformat(date_text)
            value = float(value_text)
        except (TypeError, ValueError) as exc:
            raise ParseError(f"invalid BOI FX row {line}: {exc}") from exc
        series[code].append({"date": date_text, "rate": value})
    for observations in series.values():
        observations.sort(key=lambda item: item["date"])
    return series


def merge_series(stored, fetched):
    merged = {item["date"]: item["rate"] for item in stored}
    merged.update((item["date"], item["rate"]) for item in fetched)
    return [{"date": date_text, "rate": merged[date_text]} for date_text in sorted(merged)]


def validate(series, previous=None, *, require_minimum=True):
    if set(series) != set(CURRENCIES):
        missing = sorted(set(CURRENCIES) - set(series))
        extra = sorted(set(series) - set(CURRENCIES))
        raise ValidationError(f"BOI FX currencies mismatch; missing={missing}, extra={extra}")
    previous = previous or {}
    for code in CURRENCIES:
        observations = series[code]
        if require_minimum and len(observations) < MIN_COUNTS[code]:
            raise ValidationError(f"{code} FX observation count below minimum: {len(observations)}")
        if require_minimum and (not observations or observations[0]["date"] != FIRST_DATES[code]):
            raise ValidationError(f"{code} FX first date is invalid")
        prior_date = None
        for item in observations:
            if set(item) != {"date", "rate"} or not isinstance(item["date"], str):
                raise ValidationError(f"invalid {code} FX observation shape")
            date_text = item["date"]
            try:
                if not DATE_RE.fullmatch(date_text):
                    raise ValueError
                datetime.date.fromisoformat(date_text)
            except ValueError:
                raise ValidationError(f"invalid {code} FX date {date_text!r}") from None
            if prior_date is not None and date_text <= prior_date:
                raise ValidationError(f"{code} FX dates are not strictly ascending")
            prior_date = date_text
            try:
                rate = float(item["rate"])
            except (TypeError, ValueError):
                raise ValidationError(f"invalid {code} FX rate at {date_text}") from None
            if not math.isfinite(rate) or rate <= 0:
                raise ValidationError(f"invalid {code} FX rate at {date_text}")
            fmt_number(rate)
        old_count = previous.get(code, 0)
        if (len(observations) < old_count
                and os.environ.get("STATSO_ALLOW_SHRINK") != "1"):
            raise ValidationError(f"{code} FX dataset would shrink")


def to_json_bytes(code, observations):
    obj = {"dataset": "boi_exchange_rate", "source": "בנק ישראל",
        "source_url": FULL_URL, "currency": code, "counter_currency": "ILS",
        "unit": EXPECTED_UNITS[code], "count": len(observations),
        "first_date": observations[0]["date"], "last_date": observations[-1]["date"],
        "observations": observations}
    return dumps_json(obj)


def to_csv_bytes(observations):
    return dumps_csv(("date", "rate"),
                     ([item["date"], fmt_number(item["rate"])] for item in observations))


def latest_json_bytes(series):
    rates = []
    for code in CURRENCIES:
        observations = series[code]
        rates.append({"code": code, "unit": EXPECTED_UNITS[code],
            "latest_date": observations[-1]["date"], "latest_rate": observations[-1]["rate"],
            "first_date": observations[0]["date"], "count": len(observations)})
    return dumps_json({"dataset": "boi_exchange_rates_latest", "source": "בנק ישראל",
        "source_url": FULL_URL, "counter_currency": "ILS", "count": len(rates),
        "rates": rates})


def _backfill_message(detail):
    return ValidationError(f"{detail}; run python3 -m scripts.fx_rates --backfill")


def load_stored(data_dir):
    target = pathlib.Path(data_dir)
    series, previous = {}, {}
    for code in CURRENCIES:
        stem = f"{code.lower()}_ils"
        json_path, csv_path = target / "fx" / f"{stem}.json", target / "fx" / f"{stem}.csv"
        try:
            obj = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise _backfill_message(f"stored FX file is absent or unreadable: {json_path}") from exc
        try:
            observations = obj["observations"]
            if (obj.get("dataset") != "boi_exchange_rate" or obj.get("currency") != code
                    or obj.get("counter_currency") != "ILS"
                    or obj.get("unit") != EXPECTED_UNITS[code]
                    or obj.get("count") != len(observations)):
                raise ValueError
        except (KeyError, TypeError, ValueError):
            raise _backfill_message(f"stored FX file has invalid metadata: {json_path}") from None
        if not isinstance(observations, list):
            raise _backfill_message(f"stored FX observations are invalid: {json_path}")
        try:
            csv_bytes = csv_path.read_bytes()
        except OSError as exc:
            raise _backfill_message(f"stored FX file is absent or unreadable: {csv_path}") from exc
        try:
            expected_csv = to_csv_bytes(observations)
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise _backfill_message(f"stored FX observations are invalid: {json_path}") from exc
        if csv_bytes != expected_csv:
            raise _backfill_message(f"stored FX CSV does not match JSON: {csv_path}")
        series[code] = observations
        previous[code] = len(observations)
    try:
        validate(series, previous, require_minimum=True)
    except ValidationError as exc:
        raise _backfill_message(f"stored FX history is invalid ({exc})") from exc
    return series, previous


def prepare_update(*, fetch=http_get, data_dir=DATA_DIR, backfill=False,
                   last_n=DEFAULT_LAST_N):
    if backfill:
        series = parse_observations(fetch(FULL_URL))
        validate(series)
    else:
        stored, previous = load_stored(data_dir)
        fetched = parse_observations(fetch(recent_url(last_n)))
        validate(fetched, require_minimum=False)
        if any(not fetched[code] for code in CURRENCIES):
            raise ValidationError("BOI FX recent window is missing a currency")
        series = {code: merge_series(stored[code], fetched[code]) for code in CURRENCIES}
        validate(series, previous)
    payloads = {}
    for code in CURRENCIES:
        stem = f"fx/{code.lower()}_ils"
        payloads[f"{stem}.json"] = to_json_bytes(code, series[code])
        payloads[f"{stem}.csv"] = to_csv_bytes(series[code])
    payloads["fx_latest.json"] = latest_json_bytes(series)
    return series, payloads


def update(*, fetch=http_get, data_dir=DATA_DIR, backfill=False, last_n=DEFAULT_LAST_N):
    series, payloads = prepare_update(fetch=fetch, data_dir=data_dir,
                                      backfill=backfill, last_n=last_n)
    changed = [name for name, payload in payloads.items()
               if write_atomic(pathlib.Path(data_dir) / name, payload)]
    counts = ", ".join(f"{code} {len(series[code])}" for code in CURRENCIES)
    print(f"FX: {counts}; files changed: {len(changed)}"
          + (f" ({', '.join(changed)})" if changed else ""))
    return changed


def main(argv=None):
    parser = argparse.ArgumentParser(description="Refresh Bank of Israel FX histories")
    parser.add_argument("--backfill", action="store_true", help="fetch full history")
    parser.add_argument("--last-n", type=int, default=DEFAULT_LAST_N,
                        help="observations per series in incremental mode")
    args = parser.parse_args(argv)
    try:
        update(backfill=args.backfill, last_n=args.last_n)
    except (StatsoError, OSError, ValueError) as exc:
        print(f"statso FX update failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
