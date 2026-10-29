"""Pure interval rules for clinic-local datetimes (Asia/Jerusalem, no tzinfo)."""

from datetime import datetime, timedelta

from smart_clinic.api_client import CalendarSnapshot
from smart_clinic.time_utils import validate_local_window


MINIMUM_GAP = timedelta(minutes=15)


def intervals_conflict(
    start: datetime, end: datetime, other_start: datetime, other_end: datetime
) -> bool:
    """Return whether two positive intervals overlap or have a gap below 15 minutes.

    Either interval may come first. Exactly 15 minutes between their original
    endpoints is allowed; padding both appointments would count the gap twice.
    """
    if end <= start or other_end <= other_start:
        raise ValueError("Intervals must end after they start.")
    return not (
        other_start - end >= MINIMUM_GAP or start - other_end >= MINIMUM_GAP
    )


def padded_search_window(window_start, window_end):
    """Caller-side bounds for one complete read, including both gap checks."""
    validate_local_window(window_start, window_end)
    return window_start - MINIMUM_GAP, window_end + MINIMUM_GAP


def generate_candidate_slots(working_hours, window_start, window_end, duration_minutes=30):
    """Return sorted (start, end) tuples on each working interval's 15-minute grid."""
    validate_local_window(window_start, window_end)
    if (
        not isinstance(duration_minutes, int)
        or isinstance(duration_minutes, bool)
        or duration_minutes <= 0
    ):
        raise ValueError("duration_minutes must be a positive integer.")
    if not isinstance(working_hours, (list, tuple)):
        raise ValueError("Explicit working-hour intervals are required.")
    duration = timedelta(minutes=duration_minutes)
    grid = timedelta(minutes=15)
    slots = set()
    for interval in working_hours:
        if not isinstance(interval, (list, tuple)) or len(interval) != 2:
            raise ValueError("Each working interval needs two endpoints.")
        work_start, work_end = interval
        validate_local_window(work_start, work_end)
        start = work_start
        if start < window_start:
            start += ((window_start - start) // grid) * grid
            if start < window_start:
                start += grid
        limit = min(work_end, window_end)
        while start + duration <= limit:
            slots.add((start, start + duration))
            start += grid
    return sorted(slots)


def calculate_available_slots(
    doctor_id, patient_id, working_hours, window_start, window_end,
    snapshot, appointments=(), duration_minutes=30,
):
    """Read-only calculation from a complete snapshot and current local appointments.

    No fetching, ranking, booking or clinic mutation occurs here. A future service
    fetches padded_search_window(...) once and passes that snapshot to this function.
    """
    if (
        not isinstance(doctor_id, str) or not doctor_id.strip()
        or not isinstance(patient_id, str) or not patient_id.strip()
    ):
        raise ValueError("Availability needs doctor_id and patient_id.")
    if not isinstance(snapshot, CalendarSnapshot):
        raise ValueError("Availability needs a complete CalendarSnapshot.")
    snapshot.validate_for(doctor_id, *padded_search_window(window_start, window_end))
    candidates = generate_candidate_slots(
        working_hours, window_start, window_end, duration_minutes
    )
    busy = list(snapshot.busy_intervals)
    for appointment in appointments:
        if appointment.is_active and (
            appointment.doctor.id == doctor_id or appointment.patient.id == patient_id
        ):
            validate_local_window(appointment.scheduled_at, appointment.end_at)
            busy.append((appointment.scheduled_at, appointment.end_at))
    return [
        (start, end) for start, end in candidates
        if not any(intervals_conflict(start, end, first, last) for first, last in busy)
    ]
