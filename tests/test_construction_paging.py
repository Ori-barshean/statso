import json
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from scripts import construction_inputs as ci
from scripts.common import ParseError, ValidationError

FIXTURES = Path(__file__).parent / "fixtures"


class ConstructionPagingTests(unittest.TestCase):
    def fixture_fetch(self, changes=None):
        calls = []
        def fetch(url):
            calls.append(url)
            page = int(parse_qs(urlparse(url).query)["page"][0])
            payload = json.loads((FIXTURES / f"cbs_construction_paged_page{page}.json").read_text())
            if changes:
                changes(page, payload)
            return json.dumps(payload).encode()
        return fetch, calls

    def test_all_pages(self):
        fetch, calls = self.fixture_fetch()
        rows, total = ci.fetch_all_pages(fetch)
        self.assertEqual((len(rows), total), (6, 6))
        self.assertEqual([parse_qs(urlparse(u).query)["page"][0] for u in calls], ["1", "2", "3"])
        self.assertTrue(all("pagesize=1000" in url for url in calls))

    def test_one_page_one_call(self):
        def alter(page, payload):
            payload["paging"].update(last_page=1, total_items=2)
        fetch, calls = self.fixture_fetch(alter)
        rows, total = ci.fetch_all_pages(fetch)
        self.assertEqual((len(rows), total, len(calls)), (2, 2, 1))

    def test_truncated_fails_validation(self):
        def alter(page, payload):
            if page == 3: payload["month"][0]["date"].pop()
        fetch, _ = self.fixture_fetch(alter)
        rows, total = ci.fetch_all_pages(fetch)
        with self.assertRaises(ValidationError):
            ci.validate(ci.build_records(rows), total)

    def test_paging_drift(self):
        def alter(page, payload):
            if page == 2: payload["paging"]["last_page"] = 4
        with self.assertRaises(ParseError):
            ci.fetch_all_pages(self.fixture_fetch(alter)[0])

    def test_page_url(self):
        query = parse_qs(urlparse(ci.page_url(2)).query)
        self.assertEqual(query, {"id": ["200010"], "format": ["json"], "download": ["false"],
                                 "coef": ["true"], "page": ["2"], "pagesize": ["1000"]})


if __name__ == "__main__":
    unittest.main()
