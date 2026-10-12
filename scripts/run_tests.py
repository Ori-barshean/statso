"""Run one group of the statso unit tests from the repository root.

Every tests/test*.py file belongs to exactly one group; tests/test_tooling.py
fails otherwise. The nightly refresh blocks on the data group only; the site
group runs in a separate step whose failure is a warning. The pre-push hook
runs the whole suite with unittest discover, independent of these lists.
"""
import argparse
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"

# Data pipeline: pure Python, no index.html/assets, no node. Some read committed data/.
DATA_TESTS = (
    "test_boi.py",                   # BOI SDMX parser/validator on fixtures
    "test_boi_next_decision.py",     # next-decision parser; update_all writes it and soft-fails on it
    "test_construction_inputs.py",   # construction-inputs normalizer/chaining on the CBS snapshot
    "test_construction_paging.py",   # construction-inputs CBS paging
    "test_cpi.py",                   # CPI normalizer/chaining on the CBS snapshot
    "test_cpi_paging.py",            # CPI CBS paging
    "test_fx_rates.py",              # FX fetcher, merge, derived fx files (temp dirs)
    "test_indexation_reference.py",  # reference indexation vs committed data/cpi.json, boi_interest_rate.json
    "test_published_data.py",        # contract of the committed data/ files
    "test_schedule_guard.py",        # DST guard of the nightly cron
    "test_serialization.py",         # JSON/CSV bytes, write_atomic, update_all failure handling
    "test_workflow.py",              # nightly workflow structure, retry and timeout budget
)

# Site: index.html, assets/, node-driven DOM checks, offline build, repo tooling.
SITE_TESTS = (
    "test_a11y_controls_source.py",  # controls markup + rent tool via node
    "test_a11y_pages_source.py",     # info pages + node runs of assets
    "test_a11y_round4_source.py",    # index.html/CSS/assets + node
    "test_a11y_round5_source.py",    # index.html/CSS/assets + node
    "test_a11y_round8_source.py",    # script guard, 404, statement guard; uses build_offline
    "test_a11y_round9_source.py",    # nav Escape on hover, language of parts (markup + guides via node)
    "test_a11y_source.py",           # main accessibility source checks + node
    "test_build_offline.py",         # offline single-file build (embeds data/*.json, index.html)
    "test_guides_source.py",         # guides markup/JS + node
    "test_i18n.py",                  # every Hebrew string in index.html has an English entry
    "test_mcode_source.py",          # Power Query generator via node; also reads data/boi_interest_rate.csv
    "test_tooling.py",               # pre-push hook, these groups, statement-date script
    "test_tools_source.py",          # tools pages/JS source checks
    "test_ui_source.py",             # UI/CSS source checks, README tool table
    "test_xlsx_writer.py",           # assets/statso-xlsx.js via node
)

GROUPS = {"data": DATA_TESTS, "site": SITE_TESTS, "all": DATA_TESTS + SITE_TESTS}


def classification_problems():
    """Every test*.py under tests/ (the pattern discover uses) in exactly one group."""
    on_disk = {path.name for path in TESTS.glob("test*.py")}
    listed = DATA_TESTS + SITE_TESTS
    problems = [f"{name} is listed more than once" for name in sorted({n for n in listed if listed.count(n) > 1})]
    problems += [f"{name} is in no group" for name in sorted(on_disk - set(listed))]
    problems += [f"{name} is listed but does not exist" for name in sorted(set(listed) - on_disk)]
    return problems


def build_suite(names):
    # One discover per file: import errors become failing tests, exactly as in plain discover.
    suite = unittest.TestSuite()
    for name in names:
        suite.addTests(unittest.TestLoader().discover(str(TESTS), pattern=name, top_level_dir=str(ROOT)))
    return suite


def run_suite(suite, stream=None, verbosity=2):
    result = unittest.TextTestRunner(stream=stream, verbosity=verbosity).run(suite)
    return 0 if result.wasSuccessful() and result.testsRun > 0 else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run one group of the statso tests from the repository root")
    parser.add_argument("--group", required=True, choices=sorted(GROUPS))
    args = parser.parse_args(argv)
    names = GROUPS[args.group]
    missing = [name for name in names if not (TESTS / name).is_file()]
    if missing:
        print("run_tests: listed in scripts/run_tests.py but missing: " + ", ".join(missing), file=sys.stderr)
        return 1
    print(f"run_tests: group {args.group}, {len(names)} files", file=sys.stderr)
    return run_suite(build_suite(names))


if __name__ == "__main__":
    raise SystemExit(main())
