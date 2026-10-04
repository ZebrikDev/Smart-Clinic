import heapq
from collections import deque

from smart_clinic.models import Appointment


def active_appointments(appointments: list) -> list:
    """Return appointments whose status is active."""
    result = []
    for appointment in appointments:
        if appointment.is_active:
            result.append(appointment)
    return result


def appointment_summary_parts(appointment: Appointment) -> tuple:
    """Return the appointment ID, middle fields, and status as separate parts."""
    summary = (
        appointment.appointment_id,
        appointment.patient.name,
        appointment.doctor.name,
        appointment.status,
    )

    first, *middle, last = summary
    return first, middle, last


def status_groups(appointments: list) -> tuple:
    """Return the active and inactive statuses currently in use."""
    statuses = set()

    for appointment in appointments:
        statuses.add(appointment.status)

    active = statuses & Appointment.ACTIVE_STATUSES
    inactive = statuses - Appointment.ACTIVE_STATUSES

    return active, inactive


def count_by_status(appointments: list) -> dict:
    """Count appointments per status."""
    counts = {}
    for appointment in appointments:
        status = appointment.status
        counts[status] = counts.get(status, 0) + 1
    return counts


def group_by_doctor(appointments: list) -> dict:
    """Group appointments by doctor ID."""
    groups = {}
    for appointment in appointments:
        doctor_id = appointment.doctor.id
        if doctor_id not in groups:
            groups[doctor_id] = []
        groups[doctor_id].append(appointment)
    return groups


def appointment_count_by_doctor(appointments: list) -> dict:
    """Return the number of appointments per doctor ID."""
    groups = group_by_doctor(appointments)
    counts = {}

    for doctor_id, doctor_appointments in groups.items():
        counts[doctor_id] = len(doctor_appointments)

    return counts


def process_waiting_queue(queue: deque) -> list:
    """Process appointments in waiting order."""
    processed = []
    while queue:
        appointment = queue.popleft()
        processed.append(appointment)
    return processed


def push_request(heap: list, priority: int, sequence: int, appointment: Appointment) -> None:
    """
    Push an appointment onto the priority heap.

    priority 1 = urgent, priority 2 = regular.
    sequence ensures that equal-priority items come out in insertion order.
    """
    heapq.heappush(heap, (priority, sequence, appointment))


def pop_next_request(heap: list) -> Appointment:
    """Pop and return the highest-priority appointment from the heap."""
    priority, sequence, appointment = heapq.heappop(heap)
    return appointment


def active_appointment_ids(appointments: list) -> list:
    """Return the IDs of all active appointments."""
    return [a.appointment_id for a in appointments if a.is_active]


def appointment_status_map(appointments: list) -> dict:
    """Map each appointment ID to its current status."""
    return {
        appointment.appointment_id: appointment.status
        for appointment in appointments
    }


def unique_doctor_ids(appointments: list) -> set:
    """Return the set of distinct doctor IDs across all appointments."""
    return {a.doctor.id for a in appointments}


def by_scheduled_at(appointment: Appointment):
    """Return the appointment's scheduled time."""
    return appointment.scheduled_at


def sorted_by_time(appointments: list) -> list:
    """Return appointments sorted by scheduled time."""
    return sorted(appointments, key=by_scheduled_at)


def sorted_by_patient_name(appointments: list) -> list:
    """Sort appointments by patient name."""
    return sorted(appointments, key=lambda a: a.patient.name)


def sorted_by_doctor_then_time(appointments: list) -> list:
    """Sort appointments by doctor name, then by scheduled time."""
    return sorted(appointments, key=lambda a: (a.doctor.name, a.scheduled_at))
