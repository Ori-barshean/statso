import codecs
import csv
import io
import json
import math
import os
import pathlib
import socket
import time
import urllib.error
import urllib.request

USER_AGENT = "statso-data-pipeline/1.0 (+https://github.com/Ori-barshean/statso)"
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"


class StatsoError(Exception):
    pass


class SourceError(StatsoError):
    pass


class ParseError(StatsoError):
    pass


class ChainedBaseNotFound(ParseError):
    pass


class ValidationError(StatsoError):
    pass


def http_get(url, *, timeout=60, retries=3, backoff=5):
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"}
    )
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            retryable = exc.code in {429, 500, 502, 503, 504}
            if not retryable or attempt == retries:
                raise SourceError(f"HTTP source failure for {url}: status {exc.code}") from exc
        except (urllib.error.URLError, socket.timeout) as exc:
            if attempt == retries:
                raise SourceError(f"source failure for {url}: {exc}") from exc
        time.sleep(backoff * attempt)
    raise SourceError(f"source failure for {url}")


def fmt_number(x):
    f = float(x)
    if not math.isfinite(f):
        raise ValidationError(f"non-finite number {f!r}")
    value = repr(f)
    if "e" in value or "E" in value:
        raise ValidationError(f"scientific notation for {f!r}")
    return value


def dumps_json(obj):
    return (json.dumps(obj, ensure_ascii=False, indent=2, separators=(",", ": "),
                       allow_nan=False, sort_keys=False) + "\n").encode("utf-8")


def dumps_csv(header, rows):
    stream = io.StringIO()
    writer = csv.writer(stream, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(header)
    writer.writerows(rows)
    return codecs.BOM_UTF8 + stream.getvalue().encode("utf-8")


def write_atomic(path, payload):
    path = pathlib.Path(path)
    try:
        if path.read_bytes() == payload:
            return False
    except FileNotFoundError:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise
    return True


def read_published_json(path):
    try:
        value = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
