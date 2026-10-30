"""Presentation of reviewed scheduling rules with deterministic offline inputs."""

from datetime import timedelta

from smart_clinic.api_client import CalendarClient, CalendarReadError
from smart_clinic.demo_data import WINDOW_END, WINDOW_START, prepare_demo_inputs
from smart_clinic.models import WaitingRequest
from smart_clinic.scheduling import generate_candidate_slots
from smart_clinic.services import AppointmentService
from smart_clinic.strategies import ClosestToRequestedStrategy, EarliestAvailableStrategy


class DemonstrationFailureClient(CalendarClient):
    """Explicitly injected test client: no network, no synthetic success response."""

    def fetch_busy_intervals(self, doctor_id, window_start, window_end):
        raise CalendarReadError("communication")


def format_slot(slot):
    return "None" if slot is None else f"{slot[0]:%H:%M}-{slot[1]:%H:%M}"


def queue_ids(service, doctor):
    return [request.request_id for request in service.waiting_requests(doctor.id)]


def show_availability(service, patient, doctors, snapshots):
    doctor = doctors[0]
    snapshot = snapshots[doctor.id]
    candidates = generate_candidate_slots(service.working_hours[doctor.id], WINDOW_START, WINDOW_END)
    slots = service.available_slots_using_snapshot(patient, doctor, WINDOW_START, WINDOW_END, snapshot)
    print(f"\n1. Factory -> JSON client -> AppointmentService; source={snapshot.source}")
    print("Fixed clinic-local window: 2026-10-29 09:00-12:00 (Asia/Jerusalem).")
    print("External synthetic busy event: 10:00-10:30; a 15-minute gap is required.")
    print(f"Working-hour candidates: {len(candidates)}; available after external busy: {len(slots)}")
    print(f"Available: {', '.join(format_slot(slot) for slot in slots)}")
    print("Shon's expectations: 09:30-10:00 and 10:00-10:30 are rejected.")
    print("Architecture boundaries: 09:15-09:45 and 10:45-11:15 are available.")

    preferred = WINDOW_START.replace(hour=11)
    closest = AppointmentService(service.manager, service.client, ClosestToRequestedStrategy(),
                                 service.working_hours)
    earliest_slot = service.suggest_slot(patient, doctor, WINDOW_START, WINDOW_END, preferred)
    closest_slot = closest.suggest_slot(patient, doctor, WINDOW_START, WINDOW_END, preferred)
    print("\n2. Select an already-valid slot; preference=11:00 (neither suggestion books)")
    print(f"EarliestAvailableStrategy: {format_slot(earliest_slot)}")
    print(f"ClosestToRequestedStrategy: {format_slot(closest_slot)}")


def show_booking_and_backfill(service, patient, doctors):
    doctor, other_doctor = doctors[:2]
    print("\n3. Explicit booking, cancellation and FIFO backfill (local changes only)")
    try:
        service.book("DEMO-REJECTED", patient, doctor, WINDOW_START.replace(minute=30))
    except ValueError as error:
        print(f"Explicit 09:30-10:00 rejected, as expected: {error}")
    else:
        raise RuntimeError("Demo expected the insufficient-gap booking to be rejected.")

    start = WINDOW_START.replace(hour=10, minute=45)
    end = start + timedelta(minutes=30)
    original = service.book("DEMO-ORIGINAL", patient, doctor, start)
    print(f"Booked {original.appointment_id}: {format_slot((start, end))}")
    blocked_patient = service.manager.find_patient("P002")
    conflict = service.book("DEMO-PATIENT-CONFLICT", blocked_patient, other_doctor, start)
    for identifier, waiting_patient in (
        ("WAIT-FIRST", blocked_patient),
        ("WAIT-SECOND", service.manager.find_patient("P003")),
        ("WAIT-THIRD", service.manager.find_patient("P004")),
    ):
        service.add_waiting_request(WaitingRequest(identifier, waiting_patient, doctor, start, end))
    print(f"FIFO before cancellation: {queue_ids(service, doctor)}")
    first = service.cancel(original.appointment_id)
    remaining = service.waiting_requests(doctor.id)
    print("WAIT-FIRST temporarily conflicts with that patient's D002 appointment.")
    print(f"Backfill={first['backfill_status']}; WAIT-SECOND receives {first['replacement'].appointment_id}")
    print(f"Original {original.appointment_id} remains {original.status}; replacement has a distinct ID.")
    print(f"FIFO after skipping WAIT-FIRST: {queue_ids(service, doctor)}")

    # The other doctor's queue is empty; this cancellation needs no calendar read.
    service.cancel(conflict.appointment_id)
    second = service.cancel(first["replacement"].appointment_id)
    print(f"After cancelling the patient conflict, WAIT-FIRST receives {second['replacement'].appointment_id}.")
    print(f"Remaining FIFO: {queue_ids(service, doctor)}")
    return {"service": service, "original": original, "first_backfill": first,
            "queue_after_first": remaining, "second_backfill": second}


def show_deferred_backfill():
    # A separate fresh clinic keeps this controlled-failure scenario independent.
    healthy, patient, doctors, _ = prepare_demo_inputs()
    doctor = doctors[0]
    start = WINDOW_START.replace(hour=10, minute=45)
    original = healthy.book("DEMO-DEFERRED", patient, doctor, start)
    failing = AppointmentService(healthy.manager, DemonstrationFailureClient(),
                                 EarliestAvailableStrategy(), healthy.working_hours)
    request = WaitingRequest("WAIT-DEFERRED", healthy.manager.find_patient("P005"), doctor,
                             start, original.end_at)
    failing.add_waiting_request(request)
    print("\n4. Fresh clinic; injected DemonstrationFailureClient (test client, no HTTP)")
    result = failing.cancel(original.appointment_id)
    print(f"Cancellation={original.status}; backfill={result['backfill_status']}; replacement={result['replacement']}")
    print(f"Waiting list preserved: {queue_ids(failing, doctor)}")
    print("Availability is unknown; no fallback calendar or replacement booking.")
    return {"service": failing, "result": result, "request": request}


def run_stage2_demo():
    print("\n=== Stage 2: offline scheduling demonstration (simulated) ===")
    service, patient, doctors, snapshots = prepare_demo_inputs()
    show_availability(service, patient, doctors, snapshots)
    successful = show_booking_and_backfill(service, patient, doctors)
    deferred = show_deferred_backfill()
    print("\nM1-M6 demonstration complete; real Google verification, M7/M8 concurrency and M9 remain pending.")
    return {"successful": successful, "deferred": deferred}
