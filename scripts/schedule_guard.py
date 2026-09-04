import os
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

WINTER_CRON = "0 0 * * *"
SUMMER_CRON = "0 23 * * *"


def should_run(event_name, schedule_expr, now_israel):
    if event_name != "schedule":
        return True
    if not schedule_expr:
        return now_israel.hour in (1, 2, 3)
    offset_now = now_israel.utcoffset()
    offset_previous = (now_israel.astimezone(timezone.utc) - timedelta(hours=24)).astimezone(
        now_israel.tzinfo).utcoffset()
    if offset_now != offset_previous:
        return True
    return schedule_expr == (WINTER_CRON if offset_now == timedelta(hours=2) else SUMMER_CRON)


def main():
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    schedule = os.environ.get("STATSO_SCHEDULE")
    now = datetime.now(ZoneInfo("Asia/Jerusalem"))
    result = should_run(event_name, schedule, now)
    print(f"should_run={'true' if result else 'false'}")
    if event_name == "schedule" and not schedule:
        print("warning: scheduled event has no cron expression; using a fail-open time window", file=sys.stderr)
    print(f"DST guard: event={event_name or 'unknown'}, schedule={schedule!r}, "
          f"Israel time={now.isoformat()}, run={result}", file=sys.stderr)


if __name__ == "__main__":
    main()
