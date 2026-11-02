import asyncio
import builtins
import io
import time
from datetime import timedelta
from unittest.mock import Mock

import pytest
import requests

from smart_clinic.async_processing import collect_concurrent, collect_sequential
from smart_clinic.demo_async import run_m7_demo
from smart_clinic.demo_data import WINDOW_END, WINDOW_START, prepare_demo_inputs
from smart_clinic.models import Patient
from smart_clinic.services import AvailabilityUnknownError

COLLECTORS = [collect_sequential, collect_concurrent]
# D001 finishes last and D002 first, so completion order differs from input order.
DELAYS = {"D001": 0.15, "D002": 0.05, "D003": 0.10}


@pytest.fixture(scope="module")
def run():
    """Drive coroutines on one event loop created before the network guard.

    On Windows the event loop opens an internal local socket pair when it is
    created, which the test-wide socket guard would reject. A module-scoped
    fixture is set up before that function-scoped guard, so the guard stays
    active during every collection below.
    """
    with asyncio.Runner() as runner:
        runner.get_loop()
        yield runner.run


@pytest.fixture
def inputs():
    """Prepared synchronously, before any coroutine, exactly as the handoff requires."""
    return prepare_demo_inputs()


@pytest.fixture
def no_io(inputs, monkeypatch):
    """Fail on file reads, blocking sleeps or HTTP once inputs are prepared."""
    for target, name in ((builtins, "open"), (io, "open"), (time, "sleep"),
                         (requests.sessions.Session, "request")):
        monkeypatch.setattr(target, name, Mock(side_effect=AssertionError(f"Unexpected {name} in M7")))


def collect(run, collector, inputs, snapshots=None, delays=DELAYS, patient=None):
    service, prepared_patient, doctors, prepared_snapshots = inputs
    return run(collector(service, patient or prepared_patient, doctors,
                         prepared_snapshots if snapshots is None else snapshots,
                         WINDOW_START, WINDOW_END, delays))


def spy_calculation(monkeypatch, service):
    """Record the order in which doctors reach the existing pure calculation."""
    calls = []
    original = service.available_slots_using_snapshot

    def recorder(patient, doctor, *args, **kwargs):
        calls.append(doctor.id)
        return original(patient, doctor, *args, **kwargs)

    monkeypatch.setattr(service, "available_slots_using_snapshot", recorder)
    return calls


def clinic_state(service, doctors, snapshots):
    manager = service.manager
    return (
        [(a.appointment_id, a.patient, a.doctor, a.scheduled_at, a.duration_minutes, a.status)
         for a in manager.appointments.values()],
        dict(manager.patients), dict(manager.doctors), dict(manager.visits),
        {doctor_id: list(hours) for doctor_id, hours in service.working_hours.items()},
        {doctor.id: list(service.waiting_requests(doctor.id)) for doctor in doctors},
        list(doctors),
        {doctor_id: (snapshot, snapshot.doctor_id, snapshot.window_start, snapshot.window_end,
                     snapshot.busy_intervals, snapshot.source)
         for doctor_id, snapshot in snapshots.items()},
    )


def test_both_versions_return_the_same_complete_results_as_direct_calls(run, inputs, no_io):
    service, patient, doctors, snapshots = inputs
    expected = [
        (doctor.id, service.available_slots_using_snapshot(
            patient, doctor, WINDOW_START, WINDOW_END, snapshots[doctor.id]))
        for doctor in doctors
    ]
    sequential = collect(run, collect_sequential, inputs)
    concurrent = collect(run, collect_concurrent, inputs)

    assert sequential == concurrent == expected
    assert [(doctor_id, len(slots)) for doctor_id, slots in concurrent] == [
        ("D001", 6), ("D002", 11), ("D003", 0)]
    d001, d002 = concurrent[0][1], concurrent[1][1]
    assert [f"{start:%H:%M}" for start, _ in d001] == ["09:00", "09:15", "10:45", "11:00", "11:15", "11:30"]
    assert [start for start, _ in d002] == [WINDOW_START + timedelta(minutes=15 * step) for step in range(11)]
    assert all(end - start == timedelta(minutes=30) for _, slots in concurrent for start, end in slots)


def test_results_keep_input_order_even_when_completion_order_differs(run, inputs, monkeypatch):
    service, *_ = inputs
    calls = spy_calculation(monkeypatch, service)

    sequential = collect(run, collect_sequential, inputs)
    assert calls == ["D001", "D002", "D003"]
    calls.clear()
    concurrent = collect(run, collect_concurrent, inputs)

    assert calls == ["D002", "D003", "D001"]  # completion follows the shortest delays
    assert [doctor_id for doctor_id, _ in concurrent] == ["D001", "D002", "D003"]
    assert concurrent == sequential


def test_concurrent_version_schedules_every_task_before_any_finishes(run, inputs, monkeypatch):
    events = []
    real_sleep = asyncio.sleep

    async def recording_sleep(delay):
        events.append(("start", delay))
        await real_sleep(delay)
        events.append(("end", delay))

    monkeypatch.setattr(asyncio, "sleep", recording_sleep)

    collect(run, collect_sequential, inputs)
    assert events == [("start", 0.15), ("end", 0.15), ("start", 0.05), ("end", 0.05),
                      ("start", 0.10), ("end", 0.10)]
    events.clear()
    collect(run, collect_concurrent, inputs)
    assert events[:3] == [("start", 0.15), ("start", 0.05), ("start", 0.10)]
    assert events[3:] == [("end", 0.05), ("end", 0.10), ("end", 0.15)]


@pytest.mark.parametrize("collector", COLLECTORS)
def test_valid_empty_availability_stays_distinct_from_unknown_availability(run, inputs, no_io, collector):
    results = collect(run, collector, inputs)
    assert results[2] == ("D003", [])

    *_, snapshots = inputs
    without_d003 = {doctor_id: snapshots[doctor_id] for doctor_id in ("D001", "D002")}
    with pytest.raises(AvailabilityUnknownError, match="snapshot is required"):
        collect(run, collector, inputs, snapshots=without_d003)


@pytest.mark.parametrize("collector", COLLECTORS)
def test_wrong_doctor_snapshot_and_unregistered_patient_propagate_as_errors(run, inputs, no_io, collector):
    *_, snapshots = inputs
    swapped = {**snapshots, "D002": snapshots["D001"]}
    with pytest.raises(AvailabilityUnknownError, match="invalid or incomplete"):
        collect(run, collector, inputs, snapshots=swapped)
    with pytest.raises(ValueError, match="must be registered"):
        collect(run, collector, inputs, patient=Patient("P001", "Unregistered copy"))


def test_sequential_failure_stops_before_later_doctors(run, inputs, monkeypatch):
    service, _, _, snapshots = inputs
    calls = spy_calculation(monkeypatch, service)
    with pytest.raises(AvailabilityUnknownError):
        collect(run, collect_sequential, inputs, snapshots={**snapshots, "D002": None})
    assert calls == ["D001", "D002"]


def test_concurrent_failure_raises_first_input_error_and_leaves_no_running_tasks(run, inputs, monkeypatch):
    service, patient, doctors, snapshots = inputs
    calls = spy_calculation(monkeypatch, service)
    # D003 fails first in time (0.10s), D001 fails last (0.15s) but comes first in input order.
    broken = {"D001": None, "D002": snapshots["D002"], "D003": snapshots["D002"]}

    async def collect_and_inspect():
        try:
            await collect_concurrent(service, patient, doctors, broken, WINDOW_START, WINDOW_END, DELAYS)
        except AvailabilityUnknownError as error:
            return error, asyncio.all_tasks() - {asyncio.current_task()}
        raise AssertionError("Expected unknown availability to propagate.")

    error, still_running = run(collect_and_inspect())
    assert "snapshot is required" in str(error)  # D001's error, not D003's "invalid or incomplete"
    assert still_running == set()
    assert calls == ["D002", "D003", "D001"]


@pytest.mark.parametrize("collector", COLLECTORS)
@pytest.mark.parametrize("delays", [
    {"D001": 0.01, "D002": 0.01},
    {"D001": 0.01, "D002": -0.01, "D003": 0.01},
    {"D001": 0.01, "D002": True, "D003": 0.01},
    {"D001": 0.01, "D002": "0.01", "D003": 0.01},
])
def test_invalid_delays_are_rejected_before_any_doctor_starts(run, inputs, monkeypatch, collector, delays):
    service, *_ = inputs
    calls = spy_calculation(monkeypatch, service)
    with pytest.raises(ValueError, match="non-negative simulated delay"):
        collect(run, collector, inputs, delays=delays)
    assert calls == []


@pytest.mark.parametrize("collector", COLLECTORS)
def test_collection_leaves_inputs_and_clinic_unchanged(run, inputs, no_io, collector):
    service, patient, doctors, snapshots = inputs
    delays = dict(DELAYS)
    before = clinic_state(service, doctors, snapshots)

    collect(run, collector, inputs, delays=delays)
    with pytest.raises(AvailabilityUnknownError):
        collect(run, collector, inputs, snapshots={**snapshots, "D001": None}, delays=delays)

    assert clinic_state(service, doctors, snapshots) == before
    assert delays == DELAYS
    assert service.manager.find_patient("P001") is patient


def test_m7_demo_compares_both_versions_on_the_same_inputs_without_http(run, monkeypatch, capsys):
    http = Mock(side_effect=AssertionError("M7 demo must not attempt HTTP."))
    monkeypatch.setattr("requests.sessions.Session.request", http)
    result = run_m7_demo(delays={"D001": 0.03, "D002": 0.01, "D003": 0.02}, run=run)
    output = capsys.readouterr().out

    assert result["sequential"] == result["concurrent"]
    assert [len(slots) for _, slots in result["concurrent"]] == [6, 11, 0]
    assert result["sequential_seconds"] > 0 and result["concurrent_seconds"] > 0
    assert "Same complete results, in input order: True" in output
    assert "D003: 0 slots; starts none (valid empty calendar result)" in output
    assert "Sequential: " in output and "Concurrent: " in output
    http.assert_not_called()
