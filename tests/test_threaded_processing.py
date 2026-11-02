import threading
import time

import pytest

from smart_clinic.demo_data import WINDOW_START, prepare_demo_inputs
from smart_clinic.threaded_processing import (
    BookingCoordinator, demonstrate_booking_race, run_competing_bookings,
)


@pytest.fixture
def clinic():
    service, _, doctors, snapshots = prepare_demo_inputs()
    manager = service.manager
    return {
        "service": service,
        "coordinator": BookingCoordinator(service),
        "p1": manager.find_patient("P001"),
        "p2": manager.find_patient("P002"),
        "d1": doctors[0],
        "d2": doctors[1],
        "snapshots": snapshots,
    }


def scheduled_at(service, doctor, start):
    return [a for a in service.manager.appointments.values()
            if a.doctor.id == doctor.id and a.scheduled_at == start and a.status == "scheduled"]


def test_coordinator_requires_appointment_service():
    with pytest.raises(TypeError):
        BookingCoordinator(object())


def test_two_threads_same_slot_one_booked_one_rejected(clinic):
    service, d2 = clinic["service"], clinic["d2"]
    before = len(service.manager.appointments)
    requests = [("R1", clinic["p1"], d2, WINDOW_START, 30),
                ("R2", clinic["p2"], d2, WINDOW_START, 30)]

    outcomes = run_competing_bookings(clinic["coordinator"], requests, clinic["snapshots"]["D002"])

    kinds = sorted(kind for kind, _ in outcomes)
    assert kinds == ["booked", "rejected"]
    rejected = next(value for kind, value in outcomes if kind == "rejected")
    assert isinstance(rejected, ValueError)
    assert len(service.manager.appointments) == before + 1
    assert len(scheduled_at(service, d2, WINDOW_START)) == 1


def test_repeated_races_never_double_book():
    for _ in range(20):
        outcomes = demonstrate_booking_race()
        assert sorted(kind for kind, _ in outcomes) == ["booked", "rejected"]


def test_duplicate_appointment_id_is_rejected_without_extra_booking(clinic):
    service, coordinator, d2 = clinic["service"], clinic["coordinator"], clinic["d2"]
    snapshot = clinic["snapshots"]["D002"]
    coordinator.book_with_snapshot("SAME-ID", clinic["p1"], d2, WINDOW_START, snapshot)
    before = len(service.manager.appointments)

    with pytest.raises(ValueError, match="already exists"):
        coordinator.book_with_snapshot("SAME-ID", clinic["p2"], d2,
                                       WINDOW_START.replace(hour=11), snapshot)
    assert len(service.manager.appointments) == before


def test_doctor_conflict_needs_the_15_minute_gap(clinic):
    service, coordinator, d2 = clinic["service"], clinic["coordinator"], clinic["d2"]
    snapshot = clinic["snapshots"]["D002"]
    coordinator.book_with_snapshot("FIRST", clinic["p1"], d2, WINDOW_START, snapshot)
    before = len(service.manager.appointments)

    with pytest.raises(ValueError):
        coordinator.book_with_snapshot("TOO-CLOSE", clinic["p2"], d2,
                                       WINDOW_START.replace(minute=30), snapshot)
    assert len(service.manager.appointments) == before


def test_patient_conflict_across_doctors(clinic):
    service, coordinator, p1 = clinic["service"], clinic["coordinator"], clinic["p1"]
    coordinator.book_with_snapshot("P1-D2", p1, clinic["d2"], WINDOW_START,
                                   clinic["snapshots"]["D002"])
    before = len(service.manager.appointments)

    with pytest.raises(ValueError):
        coordinator.book_with_snapshot("P1-D1", p1, clinic["d1"], WINDOW_START,
                                       clinic["snapshots"]["D001"])
    assert len(service.manager.appointments) == before


def test_protected_calls_never_run_at_the_same_time(clinic):
    service, d2 = clinic["service"], clinic["d2"]
    original = service.book_using_snapshot
    active = 0
    max_active = 0
    counter_lock = threading.Lock()

    def slow_booking(*args, **kwargs):
        nonlocal active, max_active
        with counter_lock:
            active += 1
            max_active = max(max_active, active)
        time.sleep(0.05)  # give the other Thread a chance to enter if it could
        try:
            return original(*args, **kwargs)
        finally:
            with counter_lock:
                active -= 1

    service.book_using_snapshot = slow_booking
    requests = [("R1", clinic["p1"], d2, WINDOW_START, 30),
                ("R2", clinic["p2"], d2, WINDOW_START, 30)]
    run_competing_bookings(clinic["coordinator"], requests, clinic["snapshots"]["D002"])

    assert max_active == 1


def test_unexpected_worker_error_is_not_reported_as_conflict(clinic):
    service = clinic["service"]

    def broken(*args, **kwargs):
        raise KeyError("bug")

    service.book_using_snapshot = broken
    requests = [("R1", clinic["p1"], clinic["d2"], WINDOW_START, 30)]
    with pytest.raises(RuntimeError, match="unexpectedly") as info:
        run_competing_bookings(clinic["coordinator"], requests, clinic["snapshots"]["D002"])
    assert isinstance(info.value.__cause__, KeyError)
