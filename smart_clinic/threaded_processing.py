"""M8: two Threads compete for one slot; one shared Lock protects check + write."""

import threading
from datetime import timedelta

from smart_clinic.demo_data import WINDOW_START, prepare_demo_inputs
from smart_clinic.services import AppointmentService, AvailabilityUnknownError


class BookingCoordinator:
    """Every concurrent booking writer must go through the same coordinator."""

    def __init__(self, service):
        if not isinstance(service, AppointmentService):
            raise TypeError("service must be an AppointmentService.")
        self.service = service
        self._lock = threading.Lock()

    def book_with_snapshot(self, appointment_id, patient, doctor, start, snapshot,
                           duration_minutes=30):
        """Final recheck and registration run together while holding the Lock.

        The snapshot must be fetched before calling, so no calendar read happens
        inside the critical section. Returns the registered Appointment; business
        failures (ValueError, AvailabilityUnknownError) propagate unchanged.
        """
        with self._lock:
            return self.service.book_using_snapshot(
                appointment_id, patient, doctor, start, snapshot, duration_minutes
            )


def run_competing_bookings(coordinator, requests, snapshot):
    """Start one Thread per request, join them all, then return outcomes in input order.

    Each request is (appointment_id, patient, doctor, start, duration_minutes).
    An outcome is ("booked", appointment) or ("rejected", error). Any other
    exception is a bug, not a booking conflict, so it is raised after the joins.
    """
    outcomes = [None] * len(requests)

    def worker(index, appointment_id, patient, doctor, start, duration):
        try:
            appointment = coordinator.book_with_snapshot(
                appointment_id, patient, doctor, start, snapshot, duration
            )
            outcomes[index] = ("booked", appointment)
        except (ValueError, AvailabilityUnknownError) as error:
            outcomes[index] = ("rejected", error)
        except Exception as error:
            outcomes[index] = ("error", error)

    threads = [threading.Thread(target=worker, args=(index, *request))
               for index, request in enumerate(requests)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    for kind, error in outcomes:
        if kind == "error":
            raise RuntimeError("A booking worker failed unexpectedly.") from error
    return outcomes


def demonstrate_booking_race():
    """P001 and P002 both request D002 at 09:00 for 30 minutes, at the same time."""
    service, _, doctors, snapshots = prepare_demo_inputs()
    manager = service.manager
    doctor = doctors[1]
    snapshot = snapshots[doctor.id]  # fetched before any Thread starts
    first, second = manager.find_patient("P001"), manager.find_patient("P002")
    before = len(manager.appointments)

    coordinator = BookingCoordinator(service)
    requests = [
        ("M8-RACE-P001", first, doctor, WINDOW_START, 30),
        ("M8-RACE-P002", second, doctor, WINDOW_START, 30),
    ]
    outcomes = run_competing_bookings(coordinator, requests, snapshot)

    print("\nM8: two Threads book D002 at 09:00 through one BookingCoordinator")
    for (appointment_id, patient, *_), (kind, value) in zip(requests, outcomes):
        detail = value.appointment_id if kind == "booked" else value
        print(f"{appointment_id} ({patient.id}): {kind} -> {detail}")

    booked = [value for kind, value in outcomes if kind == "booked"]
    at_slot = [a for a in manager.appointments.values()
               if a.doctor.id == doctor.id and a.scheduled_at == WINDOW_START
               and a.status == "scheduled"]
    end = WINDOW_START + timedelta(minutes=30)
    print(f"Approved: {len(booked)}, rejected: {len(outcomes) - len(booked)}")
    print(f"Appointments before: {before}, after: {len(manager.appointments)}")
    print(f"Scheduled at D002 {WINDOW_START:%H:%M}-{end:%H:%M}: {len(at_slot)}")
    if len(booked) != 1 or len(at_slot) != 1 or len(manager.appointments) != before + 1:
        raise RuntimeError("Expected exactly one approved booking at the contested slot.")
    return outcomes


if __name__ == "__main__":
    demonstrate_booking_race()
