from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

# Calendar dates in admin UI are interpreted in store-local time (Ukraine).
LEADS_FILTER_TZ = ZoneInfo("Europe/Kyiv")


def parse_filter_date_start(value: str) -> datetime:
    d = date.fromisoformat(value.strip()[:10])
    local_start = datetime.combine(d, time.min, tzinfo=LEADS_FILTER_TZ)
    return local_start.astimezone(timezone.utc)


def parse_filter_date_end_exclusive(value: str) -> datetime:
    """Upper bound: start of the next calendar day in Kyiv (exclusive)."""
    d = date.fromisoformat(value.strip()[:10])
    next_day = d + timedelta(days=1)
    local_next = datetime.combine(next_day, time.min, tzinfo=LEADS_FILTER_TZ)
    return local_next.astimezone(timezone.utc)
