"""Manually refresh the two full offline snapshots (never run in CI)."""
import argparse
import gzip
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import boi_rate, construction_inputs, cpi
from scripts.common import http_get

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cpi-source", type=Path)
    parser.add_argument("--boi-source", type=Path)
    parser.add_argument("--construction-source", type=Path)
    args = parser.parse_args()
    FIXTURES.mkdir(parents=True, exist_ok=True)
    cpi_raw = args.cpi_source.read_bytes() if args.cpi_source else http_get(cpi.page_url(1))
    boi_raw = args.boi_source.read_bytes() if args.boi_source else http_get(boi_rate.BOI_URL)
    construction_raw = (args.construction_source.read_bytes() if args.construction_source
        else http_get(construction_inputs.page_url(1)))
    outputs = (("cbs_cpi_snapshot_2026-09-05.json.gz", cpi_raw),
               ("boi_snapshot_2026-09-05.csv.gz", boi_raw),
               ("cbs_construction_snapshot_2026-09-16.json.gz", construction_raw))
    for name, raw in outputs:
        # mtime=0 keeps regenerated fixture bytes deterministic.
        (FIXTURES / name).write_bytes(gzip.compress(raw, compresslevel=9, mtime=0))


if __name__ == "__main__":
    main()
