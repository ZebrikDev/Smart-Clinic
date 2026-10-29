import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from smart_clinic.api_client import (
    CalendarClient, CalendarSnapshot, JsonCalendarClient, normalize_calendar_events,
)


def at(hour, minute=0):
    return datetime(2026, 10, 29, hour, minute)


@pytest.fixture
def timed_event():
    return {
        "start": {"dateTime": "2026-10-29T08:00:00Z"},
        "end": {"dateTime": "2026-10-29T08:30:00Z"},
    }


def payload(items):
    return {"kind": "calendar#events", "timeZone": "Asia/Jerusalem", "items": items}


def test_constructor_does_not_read_and_contract_is_shared(tmp_path):
    path = tmp_path / "not_created_yet.json"
    with patch("pathlib.Path.open", side_effect=AssertionError("constructor read a file")):
        client = JsonCalendarClient(path)
    assert isinstance(client, CalendarClient)
    path.write_text(json.dumps({"doctors": {"D1": payload([])}}), encoding="utf-8")
    assert client.fetch_busy_intervals("D1", at(9), at(12)).busy_intervals == ()


def test_empty_calendar_is_complete_and_always_simulated(calendar_file):
    path = calendar_file([])
    snapshot = JsonCalendarClient(path).fetch_busy_intervals("D1", at(8, 45), at(12, 15))
    assert snapshot.doctor_id == "D1"
    assert (snapshot.window_start, snapshot.window_end) == (at(8, 45), at(12, 15))
    assert snapshot.busy_intervals == ()
    assert snapshot.source == "simulated"


def test_timed_event_and_file_reread(calendar_file, timed_event):
    path = calendar_file([timed_event])
    client = JsonCalendarClient(path)
    assert client.fetch_busy_intervals("D1", at(9), at(12)).busy_intervals == ((at(10), at(10, 30)),)
    calendar_file([])
    assert client.fetch_busy_intervals("D1", at(9), at(12)).busy_intervals == ()


def test_ignored_events_need_no_blocking_endpoints(calendar_file, timed_event):
    path = calendar_file([
        {"status": "cancelled", "id": "deleted-only-id"},
        {"transparency": "transparent"},
        {**timed_event, "status": "tentative"},
    ])
    assert JsonCalendarClient(path).fetch_busy_intervals("D1", at(9), at(12)).busy_intervals == (
        (at(10), at(10, 30)),
    )


def test_normalization_preserves_input_and_sorts(timed_event):
    earlier = {
        "start": {"dateTime": "2026-10-29T09:00:00+02:00"},
        "end": {"dateTime": "2026-10-29T09:30:00+02:00"},
    }
    data = payload([timed_event, earlier])
    before = deepcopy(data)
    assert normalize_calendar_events(data) == ((at(9), at(9, 30)), (at(10), at(10, 30)))
    assert data == before


def test_all_day_uses_calendar_timezone_and_preserves_exclusive_end(calendar_file):
    path = calendar_file(
        [{"start": {"date": "2026-01-01"}, "end": {"date": "2026-01-02"}}],
        "America/New_York",
    )
    snapshot = JsonCalendarClient(path).fetch_busy_intervals(
        "D1", datetime(2026, 1, 1, 12), datetime(2026, 1, 1, 13)
    )
    assert snapshot.busy_intervals == ((datetime(2026, 1, 1, 7), datetime(2026, 1, 2, 7)),)


def test_events_outside_requested_coverage_are_filtered_without_endpoint_clipping(calendar_file, timed_event):
    client = JsonCalendarClient(calendar_file([timed_event]))
    assert client.fetch_busy_intervals("D1", at(10, 10), at(10, 20)).busy_intervals == (
        (at(10), at(10, 30)),
    )
    assert client.fetch_busy_intervals("D1", at(10, 30), at(11)).busy_intervals == ()
    assert client.fetch_busy_intervals("D1", at(9), at(10)).busy_intervals == ()


@pytest.mark.parametrize(
    "data",
    [None, [], {}, {"doctors": []}, {"doctors": {}},
     {"doctors": {"D2": payload([])}}, {"doctors": {"D1": None}}],
)
def test_missing_mapping_or_malformed_root_is_an_error(tmp_path, data):
    path = tmp_path / "calendar.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        JsonCalendarClient(path).fetch_busy_intervals("D1", at(9), at(12))


@pytest.mark.parametrize("contents", [b"{bad json", b"", b"\xff"])
def test_malformed_files_are_not_empty_calendars(tmp_path, contents):
    path = tmp_path / "calendar.json"
    path.write_bytes(contents)
    with pytest.raises(ValueError, match="Cannot read synthetic"):
        JsonCalendarClient(path).fetch_busy_intervals("D1", at(9), at(12))


def test_missing_file_is_an_error(tmp_path):
    with pytest.raises(ValueError, match="Cannot read synthetic"):
        JsonCalendarClient(tmp_path / "absent.json").fetch_busy_intervals("D1", at(9), at(12))


@pytest.mark.parametrize(
    "data",
    [[], {}, {"kind": "other", "items": []},
     {"kind": "calendar#events", "timeZone": "Asia/Jerusalem"},
     {"kind": "calendar#events", "timeZone": "Asia/Jerusalem", "items": {}},
     {"kind": "calendar#events", "timeZone": "Invalid/Zone", "items": []},
     {"kind": "calendar#events", "items": []}],
)
def test_malformed_response_is_rejected(data):
    with pytest.raises(ValueError):
        normalize_calendar_events(data)


@pytest.mark.parametrize(
    "event",
    [None, [], {}, {"start": {}, "end": {}},
     {"start": {"dateTime": "2026-10-29T10:00:00+02:00"}},
     {"start": {"date": "2026-10-29"}, "end": {"dateTime": "2026-10-30T10:00:00Z"}},
     {"start": {"date": "2026-02-30"}, "end": {"date": "2026-03-01"}},
     {"start": {"date": "2026-10-29"}, "end": {"date": "2026-10-29"}},
     {"start": {"dateTime": "2026-10-29T11:00:00Z"}, "end": {"dateTime": "2026-10-29T10:00:00Z"}},
     {"start": {"dateTime": "2026-10-29T10:00:00"}, "end": {"dateTime": "2026-10-29T11:00:00"}},
     {"start": {"dateTime": 42}, "end": {"dateTime": "2026-10-29T11:00:00Z"}},
     {"start": {"dateTime": "2026-10-29T10:00:00Z", "timeZone": None},
      "end": {"dateTime": "2026-10-29T11:00:00Z"}},
     {"start": {"date": "2026-10-29", "dateTime": "2026-10-29T10:00:00Z"}, "end": {"date": "2026-10-30"}},
     {"status": "unknown"}, {"transparency": "unknown"},
     {"endTimeUnspecified": True}, {"recurrence": ["RRULE:FREQ=DAILY"]}],
)
def test_unusable_blocking_event_fails_whole_read(calendar_file, timed_event, event):
    # Even if an earlier event was valid, no partial snapshot may escape.
    client = JsonCalendarClient(calendar_file([timed_event, event]))
    with pytest.raises(ValueError):
        client.fetch_busy_intervals("D1", at(9), at(12))


def test_unusable_event_outside_window_is_not_silently_skipped(calendar_file):
    event = {"start": {"dateTime": "2027-01-01T10:00:00Z"}}
    with pytest.raises(ValueError):
        JsonCalendarClient(calendar_file([event])).fetch_busy_intervals("D1", at(9), at(12))


def test_paged_fixture_cannot_claim_completeness(tmp_path):
    data = {**payload([]), "nextPageToken": "remaining-page"}
    path = tmp_path / "calendar.json"
    path.write_text(json.dumps({"doctors": {"D1": data}}), encoding="utf-8")
    with pytest.raises(ValueError, match="complete"):
        JsonCalendarClient(path).fetch_busy_intervals("D1", at(9), at(12))


@pytest.mark.parametrize("source", ["unknown", None, "Simulated"])
def test_snapshot_source_is_validated(source):
    with pytest.raises(ValueError, match="source"):
        CalendarSnapshot("D1", at(9), at(12), [], source)


@pytest.mark.parametrize(
    "intervals", [None, {}, [None], [(at(9),)], [(at(10), at(9))],
                  [(at(9).replace(tzinfo=timezone.utc), at(10))]],
)
def test_snapshot_only_accepts_normalized_intervals(intervals):
    with pytest.raises(ValueError):
        CalendarSnapshot("D1", at(9), at(12), intervals, "simulated")


def test_snapshot_copies_interval_container():
    busy = [[at(10), at(10, 30)]]
    snapshot = CalendarSnapshot("D1", at(9), at(12), busy, "simulated")
    busy[0][0] = at(11)
    assert snapshot.busy_intervals == ((at(10), at(10, 30)),)


@pytest.mark.parametrize(
    "start, end", [(at(12), at(9)), (at(9), at(9)),
                   (at(9).replace(tzinfo=timezone.utc), at(12))],
)
def test_client_rejects_invalid_window_before_file_io(tmp_path, start, end):
    client = JsonCalendarClient(tmp_path / "not_read.json")
    with patch("pathlib.Path.open", side_effect=AssertionError("unexpected file read")):
        with pytest.raises(ValueError):
            client.fetch_busy_intervals("D1", start, end)


def test_supplied_fixture_has_three_independent_doctors():
    path = Path(__file__).resolve().parents[1] / "data" / "calendar_responses.json"
    client = JsonCalendarClient(path)
    assert client.fetch_busy_intervals("D001", at(9), at(12)).busy_intervals == ((at(10), at(10, 30)),)
    assert client.fetch_busy_intervals("D002", at(9), at(12)).busy_intervals == ()
    assert client.fetch_busy_intervals("D003", at(9), at(12)).busy_intervals == (
        (datetime(2026, 10, 29), datetime(2026, 10, 30)),
    )
