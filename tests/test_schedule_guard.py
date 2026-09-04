import unittest
from collections import Counter
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from scripts.schedule_guard import SUMMER_CRON, WINTER_CRON, should_run

ISRAEL = ZoneInfo("Asia/Jerusalem")


class ScheduleTests(unittest.TestCase):
    def test_manual(self):
        self.assertTrue(should_run("workflow_dispatch", None, datetime.now(ISRAEL)))

    def test_winter_and_summer(self):
        winter = datetime(2026, 1, 15, 2, tzinfo=ISRAEL)
        summer = datetime(2026, 7, 15, 2, tzinfo=ISRAEL)
        self.assertTrue(should_run("schedule", WINTER_CRON, winter))
        self.assertFalse(should_run("schedule", SUMMER_CRON, winter))
        self.assertTrue(should_run("schedule", SUMMER_CRON, summer))
        self.assertFalse(should_run("schedule", WINTER_CRON, summer))

    def test_every_date_covered(self):
        start, end = datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2028, 1, 2, tzinfo=timezone.utc)
        accepted = Counter()
        accepted_times = []
        day = start
        while day < end:
            for hour, cron in ((0, WINTER_CRON), (23, SUMMER_CRON)):
                instant = day.replace(hour=hour).astimezone(ISRAEL)
                if should_run("schedule", cron, instant):
                    accepted[instant.date()] += 1
                    accepted_times.append(instant)
            day += timedelta(days=1)
        for date, count in accepted.items():
            self.assertLessEqual(count, 2, date)
        for year in (2026, 2027):
            date = datetime(year, 1, 1).date()
            while date.year == year:
                self.assertGreaterEqual(accepted[date], 1, date)
                date += timedelta(days=1)
        for instant in accepted_times:
            utc = instant.astimezone(timezone.utc)
            prior_offset = (utc - timedelta(hours=24)).astimezone(ISRAEL).utcoffset()
            if instant.utcoffset() == prior_offset:
                self.assertEqual(instant.hour, 2)
