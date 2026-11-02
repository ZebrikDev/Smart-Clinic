from datetime import datetime, timezone

import pytest

from smart_clinic.api_client import CalendarSnapshot, JsonCalendarClient
from smart_clinic.models import Appointment, ClinicManager, Doctor, Patient
from smart_clinic.scheduling import (
    calculate_available_slots,
    generate_candidate_slots,
    padded_search_window,
)


def at(hour, minute=0):
    return datetime(2026, 10, 29, hour, minute)


@pytest.fixture
def working_hours():
    return [(at(9), at(12))]


@pytest.fixture
def busy_snapshot():
    return CalendarSnapshot("D1", at(8, 45), at(12, 15), [(at(10), at(10, 30))], "simulated")


@pytest.mark.parametrize(
    "start, end, expected",
    [
        pytest.param(at(9, 30), at(10), False, id="Shon-reject-no-gap"),
        pytest.param(at(10), at(10, 30), False, id="Shon-reject-overlap"),
        pytest.param(at(9, 15), at(9, 45), True, id="architecture-allow-before"),
        pytest.param(at(10, 45), at(11, 15), True, id="architecture-allow-after"),
    ],
)
def test_attributed_business_expectations(working_hours, busy_snapshot, start, end, expected):
    slots = calculate_available_slots("D1", "P1", working_hours, at(9), at(12), busy_snapshot)
    assert ((start, end) in slots) is expected
    assert slots == [
        (at(9), at(9, 30)), (at(9, 15), at(9, 45)),
        (at(10, 45), at(11, 15)), (at(11), at(11, 30)),
        (at(11, 15), at(11, 45)), (at(11, 30), at(12)),
    ]


def test_grid_is_anchored_to_working_start_not_search_start():
    assert generate_candidate_slots([(at(9, 7), at(10, 7))], at(9, 20), at(10)) == [
        (at(9, 22), at(9, 52)),
    ]


def test_exact_working_and_search_boundaries():
    assert generate_candidate_slots([(at(9), at(12))], at(8), at(9, 30)) == [
        (at(9), at(9, 30)),
    ]
    assert generate_candidate_slots([(at(9), at(12))], at(11, 30), at(13)) == [
        (at(11, 30), at(12)),
    ]
    assert generate_candidate_slots([(at(9), at(12))], at(8), at(8, 59)) == []


def test_separate_shifts_sorted_deduplicated_without_crossing_breaks():
    hours = [(at(11), at(12)), (at(9), at(10)), (at(9), at(10))]
    original = list(hours)
    assert generate_candidate_slots(hours, at(9), at(12)) == [
        (at(9), at(9, 30)), (at(9, 15), at(9, 45)), (at(9, 30), at(10)),
        (at(11), at(11, 30)), (at(11, 15), at(11, 45)), (at(11, 30), at(12)),
    ]
    assert hours == original


def test_configurable_duration_and_explicit_empty_hours():
    assert generate_candidate_slots([(at(9), at(10))], at(9), at(10), 45) == [
        (at(9), at(9, 45)), (at(9, 15), at(10)),
    ]
    assert generate_candidate_slots([], at(9), at(12)) == []
    assert generate_candidate_slots([(at(9), at(9, 15))], at(9), at(12)) == []


@pytest.mark.parametrize("duration", [True, False, 0, -1, 1.5, "30", None])
def test_candidate_duration_validation(working_hours, duration):
    with pytest.raises(ValueError, match="duration_minutes"):
        generate_candidate_slots(working_hours, at(9), at(12), duration)


@pytest.mark.parametrize(
    "start, end",
    [(at(9), at(9)), (at(12), at(9)), (None, at(12)),
     (at(9).replace(tzinfo=timezone.utc), at(12))],
)
def test_invalid_search_windows(working_hours, start, end):
    with pytest.raises(ValueError):
        generate_candidate_slots(working_hours, start, end)
    with pytest.raises(ValueError):
        padded_search_window(start, end)


@pytest.mark.parametrize("hours", [None, {}, [None], [(at(9),)], [(at(12), at(9))]])
def test_invalid_working_hours(hours):
    with pytest.raises(ValueError):
        generate_candidate_slots(hours, at(9), at(12))


@pytest.mark.parametrize(
    "doctor_id, start, end",
    [("D2", at(8, 45), at(12, 15)), ("D1", at(8, 46), at(12, 15)),
     ("D1", at(8, 45), at(12, 14)), ("D1", at(9), at(12))],
)
def test_wrong_doctor_or_insufficient_snapshot(working_hours, doctor_id, start, end):
    snapshot = CalendarSnapshot(doctor_id, start, end, [], "simulated")
    with pytest.raises(ValueError, match="different doctor|insufficient coverage"):
        calculate_available_slots("D1", "P1", working_hours, at(9), at(12), snapshot)


@pytest.mark.parametrize("snapshot", [None, {}])
def test_missing_snapshot_is_not_free_time(working_hours, snapshot):
    with pytest.raises(ValueError, match="CalendarSnapshot"):
        calculate_available_slots("D1", "P1", working_hours, at(9), at(12), snapshot)


@pytest.mark.parametrize("resource", ["doctor", "patient"])
@pytest.mark.parametrize("status", ["scheduled", "in_progress", "completed", "cancelled", "no_show"])
def test_local_conflicts_without_mutating_clinic(working_hours, resource, status):
    clinic = ClinicManager()
    for identifier in ("P1", "P2"):
        clinic.register_patient(Patient(identifier, identifier))
    for identifier in ("D1", "D2"):
        clinic.register_doctor(Doctor(identifier, identifier, "General"))
    appointment = Appointment(
        "A1", clinic.find_patient("P2" if resource == "doctor" else "P1"),
        clinic.find_doctor("D1" if resource == "doctor" else "D2"), at(10), status,
    )
    clinic.schedule_appointment(appointment)
    before = dict(clinic.appointments)
    snapshot = CalendarSnapshot("D1", at(8, 45), at(12, 15), [], "simulated")
    slots = calculate_available_slots(
        "D1", "P1", working_hours, at(9), at(12), snapshot, clinic.appointments.values()
    )
    blocks = status in ("scheduled", "in_progress")
    assert ((at(9, 30), at(10)) in slots) is not blocks
    assert ((at(10), at(10, 30)) in slots) is not blocks
    assert (at(9, 15), at(9, 45)) in slots
    assert (at(10, 45), at(11, 15)) in slots
    assert clinic.appointments == before
    assert appointment.status == status
    assert snapshot.busy_intervals == ()


def test_unrelated_appointment_is_not_a_conflict(working_hours):
    appointment = Appointment("A1", Patient("P2", "Other"), Doctor("D2", "Other", "General"), at(10))
    snapshot = CalendarSnapshot("D1", at(8, 45), at(12, 15), [], "simulated")
    slots = calculate_available_slots("D1", "P1", working_hours, at(9), at(12), snapshot, [appointment])
    assert (at(10), at(10, 30)) in slots


def test_local_aware_time_is_rejected_before_comparison(working_hours):
    appointment = Appointment(
        "A1", Patient("P1", "Patient"), Doctor("D1", "Doctor", "General"),
        at(10).replace(tzinfo=timezone.utc),
    )
    snapshot = CalendarSnapshot("D1", at(8, 45), at(12, 15), [], "simulated")
    with pytest.raises(ValueError, match="naive clinic-local"):
        calculate_available_slots("D1", "P1", working_hours, at(9), at(12), snapshot, [appointment])


@pytest.mark.parametrize(
    "event, expected_intervals, blocked",
    [
        ({"start": {"dateTime": "2026-10-29T08:00:00+02:00"},
          "end": {"dateTime": "2026-10-29T08:50:00+02:00"}},
         [(at(8), at(8, 50))], (at(9), at(9, 30))),
        ({"start": {"dateTime": "2026-10-29T12:10:00+02:00"},
          "end": {"dateTime": "2026-10-29T13:00:00+02:00"}},
         [(at(12, 10), at(13))], (at(11, 30), at(12))),
    ],
)
def test_outside_events_gap_is_seen_without_double_padding_or_clipping(
    calendar_file, working_hours, event, expected_intervals, blocked
):
    path = calendar_file([event])
    bounds = padded_search_window(at(9), at(12))
    assert bounds == (at(8, 45), at(12, 15))
    snapshot = JsonCalendarClient(path).fetch_busy_intervals("D1", *bounds)
    assert (snapshot.window_start, snapshot.window_end) == bounds
    assert snapshot.busy_intervals == tuple(expected_intervals)
    slots = calculate_available_slots("D1", "P1", working_hours, at(9), at(12), snapshot)
    assert blocked not in slots


def test_all_day_exclusive_end_and_gap(calendar_file):
    path = calendar_file([{"start": {"date": "2026-10-29"}, "end": {"date": "2026-10-30"}}])
    start, end = datetime(2026, 10, 30), datetime(2026, 10, 30, 1)
    snapshot = JsonCalendarClient(path).fetch_busy_intervals("D1", *padded_search_window(start, end))
    slots = calculate_available_slots("D1", "P1", [(start, end)], start, end, snapshot)
    assert slots == [
        (datetime(2026, 10, 30, 0, 15), datetime(2026, 10, 30, 0, 45)),
        (datetime(2026, 10, 30, 0, 30), datetime(2026, 10, 30, 1)),
    ]
