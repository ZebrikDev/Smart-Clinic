"""Complete calendar snapshots and offline synthetic calendar input."""

import json
from abc import ABC, abstractmethod
from pathlib import Path

from smart_clinic.time_utils import (
    calendar_timezone,
    normalize_all_day_date,
    normalize_external_datetime,
    validate_local_window,
)


class CalendarSnapshot:
    """Busy endpoints are original normalized endpoints, not clipped to coverage."""

    def __init__(self, doctor_id, window_start, window_end, busy_intervals, source):
        if not isinstance(doctor_id, str) or not doctor_id.strip():
            raise ValueError("Snapshot needs a doctor_id.")
        validate_local_window(window_start, window_end)
        if source not in ("simulated", "live"):
            raise ValueError("Snapshot source must be simulated or live.")
        if not isinstance(busy_intervals, (list, tuple)):
            raise ValueError("Busy intervals must be a list or tuple.")
        normalized = []
        for interval in busy_intervals:
            if not isinstance(interval, (list, tuple)) or len(interval) != 2:
                raise ValueError("Each busy interval needs two endpoints.")
            start, end = interval
            validate_local_window(start, end)
            normalized.append((start, end))
        self.doctor_id = doctor_id
        self.window_start = window_start
        self.window_end = window_end
        self.busy_intervals = tuple(sorted(normalized))
        self.source = source

    def validate_for(self, doctor_id, window_start, window_end):
        validate_local_window(window_start, window_end)
        if self.doctor_id != doctor_id:
            raise ValueError("Snapshot belongs to a different doctor.")
        if self.window_start > window_start or self.window_end < window_end:
            raise ValueError("Snapshot has insufficient coverage.")


class CalendarClient(ABC):
    @abstractmethod
    def fetch_busy_intervals(self, doctor_id, window_start, window_end) -> CalendarSnapshot:
        """Cover exactly the supplied window, already padded by the caller, or raise."""
        raise NotImplementedError


def normalize_calendar_events(payload):
    """Shared validation/normalization for a Google-shaped events response.

    This function does not fetch, pad, clip, expand recurrence or create snapshots.
    A future network client must collect all pages before declaring coverage.
    """
    if not isinstance(payload, dict) or payload.get("kind") != "calendar#events":
        raise ValueError("Expected a calendar#events object.")
    calendar_timezone(payload.get("timeZone"))
    items = payload.get("items")
    if not isinstance(items, list):
        raise ValueError("Calendar items must be an explicit list (empty is allowed).")
    busy = []
    for event in items:
        if not isinstance(event, dict):
            raise ValueError("Calendar event must be an object.")
        status = event.get("status", "confirmed")
        if status == "cancelled":
            continue
        if status not in ("confirmed", "tentative"):
            raise ValueError("Invalid event status.")
        transparency = event.get("transparency", "opaque")
        if transparency == "transparent":
            continue
        if transparency != "opaque":
            raise ValueError("Invalid event transparency.")
        if event.get("endTimeUnspecified", False) is not False:
            raise ValueError("Blocking event needs a specified end time.")
        if event.get("recurrence"):
            raise ValueError("Calendar must contain expanded event instances.")
        start = event.get("start")
        end = event.get("end")
        if not isinstance(start, dict) or not isinstance(end, dict):
            raise ValueError("Blocking event needs start and end objects.")
        for endpoint in (start, end):
            if "timeZone" in endpoint:
                calendar_timezone(endpoint["timeZone"])
        start_fields = set(start) & {"date", "dateTime"}
        end_fields = set(end) & {"date", "dateTime"}
        if start_fields == end_fields == {"dateTime"}:
            first = normalize_external_datetime(start["dateTime"], start.get("timeZone"))
            last = normalize_external_datetime(end["dateTime"], end.get("timeZone"))
        elif start_fields == end_fields == {"date"}:
            first = normalize_all_day_date(start["date"], payload["timeZone"])
            last = normalize_all_day_date(end["date"], payload["timeZone"])
        else:
            raise ValueError("Event endpoints must use matching dateTime or date fields.")
        validate_local_window(first, last)
        busy.append((first, last))
    return tuple(sorted(busy))


class JsonCalendarClient(CalendarClient):
    """Read a complete synthetic calendar per doctor; never perform network IO."""

    def __init__(self, file_path):
        self.file_path = Path(file_path)

    def fetch_busy_intervals(self, doctor_id, window_start, window_end) -> CalendarSnapshot:
        validate_local_window(window_start, window_end)
        if not isinstance(doctor_id, str) or not doctor_id.strip():
            raise ValueError("Calendar request needs a doctor_id.")
        try:
            with self.file_path.open(encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise ValueError("Cannot read synthetic calendar JSON.") from error
        if not isinstance(data, dict) or not isinstance(data.get("doctors"), dict):
            raise ValueError("Synthetic calendars need a doctors mapping.")
        if doctor_id not in data["doctors"]:
            raise ValueError("Missing doctor calendar mapping.")
        payload = data["doctors"][doctor_id]
        if isinstance(payload, dict) and "nextPageToken" in payload:
            raise ValueError("Synthetic calendar must be complete, without nextPageToken.")
        intervals = normalize_calendar_events(payload)
        matching = [
            (start, end) for start, end in intervals
            if end > window_start and start < window_end
        ]
        return CalendarSnapshot(doctor_id, window_start, window_end, matching, "simulated")
