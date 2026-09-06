import inspect
import re
import unittest
from pathlib import Path

from scripts.common import http_get

ROOT = Path(__file__).parent.parent
WORKFLOW = ROOT / ".github/workflows/update-data.yml"

WORKFLOW_ATTEMPTS = 3
WORKFLOW_SLEEP_SECONDS = 300


class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")
        cls.defaults = {name: parameter.default
                        for name, parameter in inspect.signature(http_get).parameters.items()
                        if parameter.default is not inspect.Parameter.empty}

    def test_source_fetches_wait_long_enough(self):
        self.assertGreaterEqual(self.defaults["timeout"], 120)
        self.assertGreaterEqual(self.defaults["retries"], 3)
        self.assertGreaterEqual(self.defaults["backoff"], 10)

    def test_refresh_step_retries_then_fails(self):
        step = re.search(r"- name: Refresh datasets\n.*?(?=\n      - name:)", self.text, re.DOTALL)
        self.assertIsNotNone(step, "the refresh step is missing")
        body = step.group(0)
        self.assertIn(f"for attempt in {' '.join(str(n) for n in range(1, WORKFLOW_ATTEMPTS + 1))}; do", body)
        self.assertIn(f"sleep {WORKFLOW_SLEEP_SECONDS}", body)
        self.assertIn("exit 1", body, "a run that never succeeds must still fail")
        self.assertNotIn("continue-on-error", body)

    def test_job_timeout_covers_every_attempt(self):
        timeout_minutes = int(re.search(r"timeout-minutes: (\d+)", self.text).group(1))
        attempt_seconds = self.defaults["retries"] * self.defaults["timeout"]
        attempt_seconds += sum(self.defaults["backoff"] * n for n in range(1, self.defaults["retries"]))
        worst_case = WORKFLOW_ATTEMPTS * attempt_seconds
        worst_case += (WORKFLOW_ATTEMPTS - 1) * WORKFLOW_SLEEP_SECONDS
        self.assertGreater(timeout_minutes * 60, worst_case,
                           "the job would be killed before the last retry finishes")

    def test_tests_gate_the_refresh(self):
        self.assertLess(self.text.index("- name: Unit tests"), self.text.index("- name: Refresh datasets"))
        self.assertLess(self.text.index("- name: Refresh datasets"), self.text.index("- name: Commit data changes"))


if __name__ == "__main__":
    unittest.main()
