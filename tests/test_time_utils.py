from datetime import datetime, timezone

import pytest

from smart_clinic.api_client import normalize_calendar_events
from smart_clinic.time_utils import (
    clinic_time_to_rfc3339, normalize_all_day_date, normalize_external_datetime,
)


@pytest.mark.parametrize(
    "value, expected",
    [
        ("2026-01-01T10:00:00Z", datetime(2026, 1, 1, 12)),
        ("2026-07-01T10:00:00+00:00", datetime(2026, 7, 1, 13)),
        ("2026-01-01T10:00:00+05:30", datetime(2026, 1, 1, 6, 30)),
        ("2026-01-01T23:30:00-04:00", datetime(2026, 1, 2, 5, 30)),
    ],
)
def test_offset_is_converted_before_tzinfo_is_removed(value, expected):
    result = normalize_external_datetime(value)
    assert result == expected
    assert result.tzinfo is None


def test_offset_free_time_needs_explicit_endpoint_zone():
    assert normalize_external_datetime("2026-01-01T10:00:00", "America/New_York") == datetime(2026, 1, 1, 17)
    data = {
        "kind": "calendar#events", "timeZone": "America/New_York",
        "items": [{
            "start": {"dateTime": "2026-01-01T10:00:00", "timeZone": "America/New_York"},
            "end": {"dateTime": "2026-01-01T10:30:00", "timeZone": "America/New_York"},
        }],
    }
    assert normalize_calendar_events(data) == ((datetime(2026, 1, 1, 17), datetime(2026, 1, 1, 17, 30)),)


@pytest.mark.parametrize(
    "value", [None, 10, "bad", "2026-01-01", "2026-02-30T10:00:00Z",
              "2026-01-01T10:00:00", "2026-01-01T10:00:00+02:99"],
)
def test_invalid_external_timestamps(value):
    with pytest.raises(ValueError):
        normalize_external_datetime(value)


@pytest.mark.parametrize("value", [None, "20260101", "2026-01-01T00:00:00", "2026-02-30"])
def test_invalid_all_day_dates(value):
    with pytest.raises(ValueError):
        normalize_all_day_date(value, "Asia/Jerusalem")


@pytest.mark.parametrize(
    "value, expected",
    [(datetime(2026, 1, 1, 9), "2026-01-01T09:00:00+02:00"),
     (datetime(2026, 7, 1, 9), "2026-07-01T09:00:00+03:00")],
)
def test_query_bounds_use_date_specific_clinic_offset(value, expected):
    assert clinic_time_to_rfc3339(value) == expected


def test_query_bound_cannot_accept_an_aware_local_model_value():
    with pytest.raises(ValueError, match="naive clinic-local"):
        clinic_time_to_rfc3339(datetime(2026, 1, 1, 9, tzinfo=timezone.utc))


@pytest.mark.parametrize("value", ["2026-11-01T01:30:00", "2026-03-08T02:30:00"])
def test_unresolved_clock_change_wall_time_is_rejected(value):
    with pytest.raises(ValueError, match="Ambiguous or nonexistent"):
        normalize_external_datetime(value, "America/New_York")


@pytest.mark.parametrize("zone", ["Invalid/Zone", "", 42])
def test_invalid_endpoint_timezone(zone):
    with pytest.raises(ValueError):
        normalize_external_datetime("2026-01-01T10:00:00", zone)
