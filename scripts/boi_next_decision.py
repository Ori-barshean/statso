import datetime
import json

from .common import ParseError, ValidationError, dumps_json, fmt_number

BOI_NEXT_URL = "https://boi.org.il/PublicApi/GetInterest"


def parse_payload(raw: bytes) -> dict:
    try:
        value = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ParseError(f"invalid BOI next-decision response: {exc}") from exc
    if not isinstance(value, dict):
        raise ParseError("BOI next-decision response is not an object")
    return value


def normalize_next_date(value):
    if not isinstance(value, str) or len(value) < 10:
        return None
    candidate = value[:10]
    try:
        datetime.date.fromisoformat(candidate)
    except ValueError:
        return None
    return candidate


def build_record(raw: bytes) -> dict:
    payload = parse_payload(raw)
    next_interest_date = payload.get("nextInterestDate")
    return {
        "dataset": "boi_next_decision",
        "source": "בנק ישראל",
        "source_url": BOI_NEXT_URL,
        "content": "next_decision_only",
        "current_interest": payload.get("currentInterest"),
        "next_interest_date": next_interest_date,
        "next_decision_date": normalize_next_date(next_interest_date),
        "last_published_date": payload.get("lastPublishedDate"),
    }


def validate(record) -> None:
    if record.get("current_interest") is not None:
        try:
            fmt_number(record["current_interest"])
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"invalid current BOI interest: {exc}") from exc


def to_json_bytes(record) -> bytes:
    return dumps_json(record)
