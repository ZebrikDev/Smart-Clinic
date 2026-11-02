"""Local scheduling workflows; external reads stay outside snapshot-based mutation."""

from collections import deque
from datetime import timedelta

from smart_clinic.api_client import CalendarClient, CalendarSnapshot
from smart_clinic.models import Appointment, ClinicManager, WaitingRequest
from smart_clinic.scheduling import calculate_available_slots, padded_search_window
from smart_clinic.strategies import SlotSelectionStrategy
from smart_clinic.time_utils import validate_local_window


class AvailabilityUnknownError(RuntimeError):
    """A failed/incomplete external read cannot support availability or booking."""


class AppointmentService:
    def __init__(self, manager, client, strategy, working_hours):
        if not isinstance(manager, ClinicManager):
            raise TypeError("manager must be a ClinicManager.")
        if not isinstance(client, CalendarClient) or not isinstance(strategy, SlotSelectionStrategy):
            raise TypeError("Provide a CalendarClient and SlotSelectionStrategy.")
        if not isinstance(working_hours, dict):
            raise ValueError("Provide doctor-to-working-hours configuration.")
        self.manager = manager
        self.client = client
        self.strategy = strategy
        self.working_hours = dict(working_hours)
        self._waiting_lists = {}
        self._backfill_sequence = 1

    def _hours(self, doctor):
        if doctor.id not in self.working_hours:
            raise ValueError("Doctor working hours are not configured.")
        return self.working_hours[doctor.id]

    def _checked_snapshot(self, doctor, window_start, window_end, snapshot):
        validate_local_window(window_start, window_end)
        if not isinstance(snapshot, CalendarSnapshot):
            raise AvailabilityUnknownError("Availability is unknown; a complete snapshot is required.")
        try:
            checked = CalendarSnapshot(
                snapshot.doctor_id, snapshot.window_start, snapshot.window_end,
                snapshot.busy_intervals, snapshot.source,
            )
            checked.validate_for(doctor.id, *padded_search_window(window_start, window_end))
        except (ValueError, TypeError, AttributeError, OverflowError):
            raise AvailabilityUnknownError("Availability is unknown; snapshot is invalid or incomplete.") from None
        return checked

    def fetch_snapshot(self, patient, doctor, window_start, window_end):
        """Read once, using caller-side gap padding; return a complete snapshot or raise."""
        self.manager.validate_participants(patient, doctor)
        bounds = padded_search_window(window_start, window_end)
        try:
            snapshot = self.client.fetch_busy_intervals(doctor.id, *bounds)
        except Exception:
            # The injected CalendarClient promises a complete result or raises.
            # Only its read is guarded: local input/business errors stay distinct.
            raise AvailabilityUnknownError("Availability is unknown; calendar read failed.") from None
        return self._checked_snapshot(doctor, window_start, window_end, snapshot)

    def available_slots_using_snapshot(
        self, patient, doctor, window_start, window_end, snapshot, duration_minutes=30,
    ):
        """Pure local calculation: no calendar call, mutation, caching or ranking."""
        self.manager.validate_participants(patient, doctor)
        snapshot = self._checked_snapshot(doctor, window_start, window_end, snapshot)
        return calculate_available_slots(
            doctor.id, patient.id, self._hours(doctor), window_start, window_end,
            snapshot, self.manager.appointments.values(), duration_minutes,
        )

    def available_slots(self, patient, doctor, window_start, window_end, duration_minutes=30):
        self.manager.validate_participants(patient, doctor)
        self._hours(doctor)
        snapshot = self.fetch_snapshot(patient, doctor, window_start, window_end)
        return self.available_slots_using_snapshot(
            patient, doctor, window_start, window_end, snapshot, duration_minutes,
        )

    def suggest_slot(
        self, patient, doctor, window_start, window_end, preferred_start, duration_minutes=30,
    ):
        slots = self.available_slots(patient, doctor, window_start, window_end, duration_minutes)
        selected = self.strategy.select(slots, preferred_start)
        if selected is not None and selected not in slots:
            raise ValueError("Strategy must select from available slots.")
        return selected

    def _prepare_appointment(self, appointment_id, patient, doctor, start, duration_minutes):
        self.manager.validate_participants(patient, doctor)
        appointment = Appointment(appointment_id, patient, doctor, start,
                                  duration_minutes=duration_minutes)
        if self.manager.find_appointment(appointment.appointment_id) is not None:
            raise ValueError("Appointment ID already exists.")
        validate_local_window(appointment.scheduled_at, appointment.end_at)
        self._hours(doctor)
        return appointment

    def book(self, appointment_id, patient, doctor, start, duration_minutes=30):
        """Fetch before mutation; an explicit start is never replaced by a suggestion."""
        appointment = self._prepare_appointment(appointment_id, patient, doctor, start, duration_minutes)
        snapshot = self.fetch_snapshot(patient, doctor, start, appointment.end_at)
        return self.book_using_snapshot(appointment_id, patient, doctor, start, snapshot, duration_minutes)

    def book_using_snapshot(
        self, appointment_id, patient, doctor, start, snapshot, duration_minutes=30,
    ):
        """Recheck current local state and register, without IO. Future Lock boundary."""
        appointment = self._prepare_appointment(appointment_id, patient, doctor, start, duration_minutes)
        slots = self.available_slots_using_snapshot(
            patient, doctor, start, appointment.end_at, snapshot, duration_minutes,
        )
        if (start, appointment.end_at) not in slots:
            raise ValueError("Requested slot is not available.")
        self.manager.schedule_appointment(appointment)
        return appointment

    def add_waiting_request(self, request):
        """Enqueue without IO; pending request IDs are unique across all doctors."""
        if not isinstance(request, WaitingRequest):
            raise TypeError("request must be a WaitingRequest.")
        self.manager.validate_participants(request.patient, request.doctor)
        if any(item.request_id == request.request_id
               for queue in self._waiting_lists.values() for item in queue):
            raise ValueError("Waiting request ID is already pending.")
        self._waiting_lists.setdefault(request.doctor.id, deque()).append(request)
        return request

    def waiting_requests(self, doctor_id):
        """Read-only FIFO view; an unknown/empty doctor queue returns an empty tuple."""
        return tuple(self._waiting_lists.get(doctor_id, ()))

    def _next_backfill_id(self):
        while True:
            candidate = f"BACKFILL-{self._backfill_sequence}"
            self._backfill_sequence += 1
            if self.manager.find_appointment(candidate) is None:
                return candidate

    def cancel(self, appointment_id):
        """Cancel scheduled only, then fill at most one request at the original start.

        Return cancelled_appointment, replacement (or None), and backfill_status:
        filled, unfilled, or deferred when external availability is unknown.
        """
        if not isinstance(appointment_id, str) or not appointment_id.strip():
            raise ValueError("Cancellation needs an appointment ID.")
        appointment = self.manager.find_appointment(appointment_id.strip())
        if appointment is None or appointment.status != "scheduled":
            raise ValueError("Only a known scheduled appointment can be cancelled.")
        self.manager.validate_participants(appointment.patient, appointment.doctor)
        validate_local_window(appointment.scheduled_at, appointment.end_at)
        appointment.update_status("cancelled")
        result = {"cancelled_appointment": appointment, "replacement": None,
                  "backfill_status": "unfilled"}
        queue = self._waiting_lists.get(appointment.doctor.id)
        if not queue:
            return result
        start, end = appointment.scheduled_at, appointment.end_at
        try:
            snapshot = self.fetch_snapshot(appointment.patient, appointment.doctor, start, end)
        except AvailabilityUnknownError:
            result["backfill_status"] = "deferred"
            return result
        for request in queue:
            replacement_end = start + timedelta(minutes=request.duration_minutes)
            if (replacement_end > end or start < request.window_start
                    or replacement_end > request.window_end):
                continue
            try:
                replacement = self.book_using_snapshot(
                    self._next_backfill_id(), request.patient, request.doctor,
                    start, snapshot, request.duration_minutes,
                )
            except ValueError:
                continue
            except AvailabilityUnknownError:
                result["backfill_status"] = "deferred"
                return result
            queue.remove(request)  # Only after successful manager registration.
            result.update(replacement=replacement, backfill_status="filled")
            return result
        return result
