"""Complete calendar snapshots and offline synthetic calendar input."""

import json
import logging
import time
from abc import ABC, abstractmethod
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote

import requests

from smart_clinic.config import validate_live_config
from smart_clinic.time_utils import (
    calendar_timezone,
    normalize_all_day_date,
    normalize_external_datetime,
    clinic_time_to_rfc3339,
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
    Network clients must collect all pages before declaring coverage.
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


logger = logging.getLogger(__name__)


class CalendarReadError(RuntimeError):
    """Only fixed categories/reasons and an integer HTTP status are exposed."""

    def __init__(self, category, http_status=None, reason=None):
        self.category = category
        self.http_status = http_status
        self.reason = reason
        message = f"Calendar read failed: {category}"
        if http_status is not None:
            message += f" (HTTP {http_status})"
        if reason is not None:
            message += f" ({reason})"
        super().__init__(message + ".")


def _read_failure(category, http_status=None, reason=None):
    logger.error("Calendar read failed: category=%s http_status=%s reason=%s",
                 category, http_status, reason)
    raise CalendarReadError(category, http_status, reason) from None


def _google_page_intervals(payload):
    """Adapt omitted empty items in a recognized Google envelope only.

    M2's synthetic normalizer remains strict. Present null/wrong-type items and
    unrecognized/error responses never become an empty calendar.
    """
    if not isinstance(payload, dict) or "error" in payload:
        raise ValueError("Invalid Google calendar response.")
    if "accessRole" in payload and payload["accessRole"] not in (
        "reader", "writer", "writerWithoutPrivateAccess", "owner"
    ):
        raise ValueError("Insufficient calendar read access.")
    if "items" not in payload:
        if (
            payload.get("kind") != "calendar#events"
            or not isinstance(payload.get("etag"), str) or not payload["etag"].strip()
        ):
            raise ValueError("Unrecognized empty Google calendar response.")
        calendar_timezone(payload.get("timeZone"))
        payload = {**payload, "items": []}
    return normalize_calendar_events(payload)


class GoogleCalendarClient(CalendarClient):
    """Read a configured public synthetic calendar; no HTTP in construction."""

    def __init__(self, api_key, doctor_calendars, timeout=10):
        validate_live_config(api_key, doctor_calendars, timeout)
        self._api_key = api_key
        self.doctor_calendars = dict(doctor_calendars)
        self.timeout = timeout

    def _get_response(self, url, params):
        for attempt in range(1, 4):
            try:
                return requests.get(url, params=params, timeout=self.timeout,
                                    allow_redirects=False)
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as error:
                reason = "timeout" if isinstance(error, requests.exceptions.Timeout) else "connection"
                if attempt == 3:
                    _read_failure("communication", reason=reason)
                logger.warning("Calendar GET retry: reason=%s failed_attempt=%d", reason, attempt)
                time.sleep(1)
            except requests.exceptions.RequestException:
                _read_failure("communication", reason="request")

    def _read_page(self, url, params):
        response = self._get_response(url, params)
        try:
            status = response.status_code
            status = status if type(status) is int and 100 <= status <= 599 else None
            try:
                response.raise_for_status()
            except requests.exceptions.RequestException:
                _read_failure("http", http_status=status)
            if status is None or not 200 <= status < 300:
                _read_failure("http", http_status=status)
            try:
                return response.json()
            except ValueError:
                _read_failure("json")
        finally:
            try:
                response.close()
            except OSError:
                _read_failure("communication", reason="response")

    def fetch_busy_intervals(self, doctor_id, window_start, window_end) -> CalendarSnapshot:
        try:
            validate_local_window(window_start, window_end)
            if not isinstance(doctor_id, str) or doctor_id not in self.doctor_calendars:
                raise ValueError("Missing doctor calendar mapping.")
            # Google ignores fractional seconds. Round the HTTP bounds outward,
            # then filter to exact requested coverage without clipping events.
            query_start = window_start.replace(microsecond=0)
            query_end = window_end.replace(microsecond=0)
            if window_end.microsecond:
                query_end += timedelta(seconds=1)
            bounds = (clinic_time_to_rfc3339(query_start), clinic_time_to_rfc3339(query_end))
        except (ValueError, TypeError, OverflowError):
            _read_failure("validation")
        calendar_id = quote(self.doctor_calendars[doctor_id], safe="")
        url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
        params = {"key": self._api_key, "timeMin": bounds[0], "timeMax": bounds[1],
                  "timeZone": "Asia/Jerusalem", "singleEvents": True,
                  "showDeleted": False, "orderBy": "startTime"}
        busy = []
        seen_tokens = set()
        pages = 0
        while True:
            payload = self._read_page(url, params)
            pages += 1
            try:
                busy.extend(_google_page_intervals(payload))
                token = payload.get("nextPageToken")
                if "nextPageToken" in payload:
                    if not isinstance(token, str) or not token.strip() or token in seen_tokens:
                        raise ValueError("Invalid or repeated page token.")
                    if "nextSyncToken" in payload:
                        raise ValueError("Conflicting pagination fields.")
                if "nextSyncToken" in payload:
                    sync = payload["nextSyncToken"]
                    if not isinstance(sync, str) or not sync.strip():
                        raise ValueError("Invalid sync token.")
            except (ValueError, TypeError, OverflowError):
                _read_failure("validation")
            if token is None:
                break
            seen_tokens.add(token)
            params = {**params, "pageToken": token}
        logger.info("Calendar read completed: source=live pages=%d", pages)
        matching = [(start, end) for start, end in busy if end > window_start and start < window_end]
        return CalendarSnapshot(doctor_id, window_start, window_end, matching, "live")
