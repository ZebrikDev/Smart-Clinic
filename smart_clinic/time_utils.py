"""Timezone boundary between external calendars and the naive local model."""

import re
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


CLINIC_TIMEZONE = ZoneInfo("Asia/Jerusalem")
TIMESTAMP_PATTERN = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?"
    r"(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)?"
)


def require_local_datetime(value):
    if not isinstance(value, datetime) or value.tzinfo is not None:
        raise ValueError("Expected a naive clinic-local datetime.")


def validate_local_window(start, end):
    require_local_datetime(start)
    require_local_datetime(end)
    if end <= start:
        raise ValueError("Window must end after it starts.")


def calendar_timezone(name):
    if not isinstance(name, str) or not name:
        raise ValueError("Calendar timeZone must be an IANA timezone name.")
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError("Unknown calendar timeZone.") from None


def _attach_timezone(value, zone):
    """Reject ambiguous/nonexistent wall times rather than guessing an offset."""
    aware = value.replace(tzinfo=zone, fold=0)
    round_trip = aware.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None)
    if (
        round_trip != value
        or aware.utcoffset() != aware.replace(fold=1).utcoffset()
    ):
        raise ValueError("Ambiguous or nonexistent local time; use an explicit offset.")
    return aware


def normalize_external_datetime(value, time_zone=None):
    """Convert the supplied instant to Jerusalem, then remove tzinfo.

    An offset (including Z) identifies the instant. Google also permits an
    offset-free dateTime when the endpoint explicitly supplies timeZone.
    """
    if not isinstance(value, str) or not TIMESTAMP_PATTERN.fullmatch(value):
        raise ValueError("Invalid external dateTime.")
    zone = calendar_timezone(time_zone) if time_zone is not None else None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise ValueError("Invalid external dateTime.") from None
    if parsed.tzinfo is None:
        if zone is None:
            raise ValueError("External dateTime needs an offset or explicit timeZone.")
        parsed = _attach_timezone(parsed, zone)
    return parsed.astimezone(CLINIC_TIMEZONE).replace(tzinfo=None)


def normalize_all_day_date(value, time_zone):
    """Interpret an all-day date at midnight in its calendar's timezone."""
    if not isinstance(value, str):
        raise ValueError("Invalid all-day date.")
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise ValueError("Invalid all-day date.") from None
    if parsed.isoformat() != value:
        raise ValueError("All-day dates must use YYYY-MM-DD.")
    aware = _attach_timezone(datetime.combine(parsed, time()), calendar_timezone(time_zone))
    return aware.astimezone(CLINIC_TIMEZONE).replace(tzinfo=None)


def clinic_time_to_rfc3339(value):
    """Use the clinic offset for this date, rather than a year-round constant."""
    require_local_datetime(value)
    return _attach_timezone(value, CLINIC_TIMEZONE).isoformat()
