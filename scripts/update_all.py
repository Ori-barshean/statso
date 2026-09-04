import sys

from . import boi_rate, cpi
from .common import DATA_DIR, StatsoError, http_get, read_published_json, write_atomic


def update(*, fetch=http_get, data_dir=None):
    target = DATA_DIR if data_dir is None else data_dir
    cpi_rows, total = cpi.fetch_all_pages(fetch)
    cpi_records = cpi.build_records(cpi_rows)
    cpi.validate(cpi_records, total, read_published_json(target / "cpi.json"))

    observations = boi_rate.parse_observations(fetch(boi_rate.BOI_URL))
    changes = boi_rate.derive_change_points(observations)
    boi_rate.validate(changes, observations,
                      read_published_json(target / "boi_interest_rate.json"))

    payloads = {"cpi.json": cpi.to_json_bytes(cpi_records),
        "cpi.csv": cpi.to_csv_bytes(cpi_records),
        "boi_interest_rate.json": boi_rate.to_json_bytes(changes),
        "boi_interest_rate.csv": boi_rate.to_csv_bytes(changes)}
    target.mkdir(parents=True, exist_ok=True)
    changed = [name for name, payload in payloads.items()
               if write_atomic(target / name, payload)]
    print(f"CPI: {len(cpi_records)} observations; BOI: {len(changes)} change points; "
          f"files changed: {len(changed)}" + (f" ({', '.join(changed)})" if changed else ""))
    return changed


def main():
    if sys.version_info < (3, 9):
        print("statso requires Python 3.9 or newer", file=sys.stderr)
        return 1
    try:
        update()
    except (StatsoError, OSError) as exc:
        print(f"statso update failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
