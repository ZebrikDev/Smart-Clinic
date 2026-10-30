from datetime import datetime, timedelta

from smart_clinic.scheduling import intervals_conflict
from smart_clinic.time_utils import validate_local_window


class Person:
    def __init__(self, id: str, name: str):
        if not isinstance(id, str) or not id.strip():
            raise ValueError("ID must be a non-empty string.")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Name must be a non-empty string.")
        self.id = id.strip()
        self.name = name.strip()

    def get_details(self) -> str:
        return f"Person: {self.name} (ID: {self.id})"

    def __str__(self) -> str:
        return f"{self.name} ({self.id})"

    def __repr__(self) -> str:
        return f"Person(id={self.id!r}, name={self.name!r})"


class Patient(Person):
    def __init__(self, id: str, name: str):
        super().__init__(id, name)

    def get_details(self) -> str:
        return f"Patient: {self.name} (ID: {self.id})"

    @classmethod
    def from_dict(cls, data: dict):
        return cls(id=data["id"], name=data["name"])

    def __repr__(self) -> str:
        return f"Patient(id={self.id!r}, name={self.name!r})"


class Doctor(Person):
    def __init__(self, id: str, name: str, specialty: str):
        super().__init__(id, name)
        if not isinstance(specialty, str) or not specialty.strip():
            raise ValueError("Specialty must be a non-empty string.")
        self.specialty = specialty.strip()

    def get_details(self) -> str:
        return f"Doctor: {self.name} (ID: {self.id}, Specialty: {self.specialty})"

    @classmethod
    def from_dict(cls, data: dict):
        return cls(id=data["id"], name=data["name"], specialty=data["specialty"])

    def __repr__(self) -> str:
        return f"Doctor(id={self.id!r}, name={self.name!r}, specialty={self.specialty!r})"


def _validate_duration(duration_minutes):
    if (
        not isinstance(duration_minutes, int)
        or isinstance(duration_minutes, bool)
        or duration_minutes <= 0
    ):
        raise ValueError("duration_minutes must be a positive integer.")


class Appointment:
    VALID_STATUSES = {"scheduled", "cancelled", "in_progress", "completed", "no_show"}
    ACTIVE_STATUSES = {"scheduled", "in_progress"}
    TERMINAL_STATUSES = {"cancelled", "completed", "no_show"}

    def __init__(
        self,
        appointment_id: str,
        patient: Patient,
        doctor: Doctor,
        scheduled_at: datetime,
        status: str = "scheduled",
        duration_minutes: int = 30,
    ):
        if not isinstance(appointment_id, str) or not appointment_id.strip():
            raise ValueError("Appointment ID must be a non-empty string.")
        if not isinstance(patient, Patient):
            raise TypeError("patient must be a Patient instance.")
        if not isinstance(doctor, Doctor):
            raise TypeError("doctor must be a Doctor instance.")
        if not isinstance(scheduled_at, datetime):
            raise TypeError("scheduled_at must be a datetime instance.")
        _validate_duration(duration_minutes)

        self.appointment_id = appointment_id.strip()
        self.patient = patient
        self.doctor = doctor
        self.scheduled_at = scheduled_at
        self._duration_minutes = duration_minutes
        self._status = None
        self.update_status(status)

    @property
    def status(self) -> str:
        return self._status

    @property
    def duration_minutes(self) -> int:
        return self._duration_minutes

    @property
    def end_at(self) -> datetime:
        return self.scheduled_at + timedelta(minutes=self.duration_minutes)

    @property
    def is_active(self) -> bool:
        return self.status in self.ACTIVE_STATUSES

    def update_status(self, status: str) -> None:
        if not isinstance(status, str) or status not in self.VALID_STATUSES:
            raise ValueError(f"status must be one of {self.VALID_STATUSES}.")
        if self.status in self.TERMINAL_STATUSES and status in self.ACTIVE_STATUSES:
            raise ValueError(f"Cannot reactivate a {self.status} appointment.")
        self._status = status

    def __str__(self) -> str:
        time_str = self.scheduled_at.strftime("%Y-%m-%d %H:%M")
        return (
            f"Appointment {self.appointment_id}: {self.patient.name} with "
            f"{self.doctor.name} at {time_str} [{self.status}]"
        )

    def __repr__(self) -> str:
        return (
            f"Appointment(appointment_id={self.appointment_id!r}, "
            f"patient={self.patient!r}, doctor={self.doctor!r}, "
            f"scheduled_at={self.scheduled_at!r}, status={self.status!r}, "
            f"duration_minutes={self.duration_minutes!r})"
        )


class WaitingRequest:
    """A flexible local request; clinic membership/uniqueness is checked on enqueue."""

    def __init__(self, request_id, patient, doctor, window_start, window_end, duration_minutes=30):
        if not isinstance(request_id, str) or not request_id.strip():
            raise ValueError("Waiting request ID must be a non-empty string.")
        if not isinstance(patient, Patient) or not isinstance(doctor, Doctor):
            raise TypeError("Waiting request needs Patient and Doctor instances.")
        validate_local_window(window_start, window_end)
        _validate_duration(duration_minutes)
        if window_start + timedelta(minutes=duration_minutes) > window_end:
            raise ValueError("Waiting request duration must fit within its window.")
        self._request_id = request_id.strip()
        self._patient = patient
        self._doctor = doctor
        self._window_start = window_start
        self._window_end = window_end
        self._duration_minutes = duration_minutes

    @property
    def request_id(self):
        return self._request_id

    @property
    def patient(self):
        return self._patient

    @property
    def doctor(self):
        return self._doctor

    @property
    def window_start(self):
        return self._window_start

    @property
    def window_end(self):
        return self._window_end

    @property
    def duration_minutes(self):
        return self._duration_minutes

    def __repr__(self):
        return (f"WaitingRequest(request_id={self.request_id!r}, patient={self.patient.id!r}, "
                f"doctor={self.doctor.id!r}, window_start={self.window_start!r}, "
                f"window_end={self.window_end!r}, duration_minutes={self.duration_minutes!r})")


class Visit:
    def __init__(self, visit_id: str, appointment: Appointment, summary: str):
        if not isinstance(visit_id, str) or not visit_id.strip():
            raise ValueError("Visit ID must be a non-empty string.")
        if not isinstance(appointment, Appointment):
            raise TypeError("appointment must be an Appointment instance.")
        if appointment.status != "completed":
            raise ValueError("Visit can only be created for a completed appointment.")
        if not isinstance(summary, str) or not summary.strip():
            raise ValueError("summary must be a non-empty string.")

        self.visit_id = visit_id.strip()
        self.appointment = appointment
        self.summary = summary.strip()

    def __str__(self) -> str:
        return f"Visit {self.visit_id} ({self.appointment.appointment_id}): {self.summary}"

    def __repr__(self) -> str:
        return (
            f"Visit(visit_id={self.visit_id!r}, "
            f"appointment={self.appointment!r}, summary={self.summary!r})"
        )


class ClinicManager:
    def __init__(self):
        self.patients = {}
        self.doctors = {}
        self.appointments = {}
        self.visits = {}

    def register_patient(self, patient: Patient) -> None:
        if not isinstance(patient, Patient):
            raise TypeError("patient must be a Patient instance.")
        if patient.id in self.patients:
            raise ValueError(f"Patient with ID {patient.id} already exists.")
        self.patients[patient.id] = patient

    def find_patient(self, patient_id: str):
        return self.patients.get(patient_id)

    def register_doctor(self, doctor: Doctor) -> None:
        if not isinstance(doctor, Doctor):
            raise TypeError("doctor must be a Doctor instance.")
        if doctor.id in self.doctors:
            raise ValueError(f"Doctor with ID {doctor.id} already exists.")
        self.doctors[doctor.id] = doctor

    def find_doctor(self, doctor_id: str):
        return self.doctors.get(doctor_id)

    def validate_participants(self, patient, doctor):
        """Share exact registered-object checks with new service entry points."""
        if not isinstance(patient, Patient) or not isinstance(doctor, Doctor):
            raise TypeError("Expected Patient and Doctor instances.")
        if self.patients.get(patient.id) is not patient:
            raise ValueError("Appointment patient must be registered with this clinic.")
        if self.doctors.get(doctor.id) is not doctor:
            raise ValueError("Appointment doctor must be registered with this clinic.")

    def has_doctor_conflict(
        self, doctor: Doctor, scheduled_at: datetime, duration_minutes: int = 30
    ) -> bool:
        end_at = scheduled_at + timedelta(minutes=duration_minutes)
        for existing in self.appointments.values():
            if (
                existing.doctor.id == doctor.id
                and existing.is_active
                and intervals_conflict(
                    scheduled_at, end_at, existing.scheduled_at, existing.end_at
                )
            ):
                return True
        return False

    def has_patient_conflict(
        self, patient: Patient, scheduled_at: datetime, duration_minutes: int = 30
    ) -> bool:
        end_at = scheduled_at + timedelta(minutes=duration_minutes)
        for existing in self.appointments.values():
            if (
                existing.patient.id == patient.id
                and existing.is_active
                and intervals_conflict(
                    scheduled_at, end_at, existing.scheduled_at, existing.end_at
                )
            ):
                return True
        return False

    def schedule_appointment(self, appointment: Appointment) -> None:
        if not isinstance(appointment, Appointment):
            raise TypeError("appointment must be an Appointment instance.")
        if appointment.appointment_id in self.appointments:
            raise ValueError(
                f"Appointment with ID {appointment.appointment_id} already exists."
            )
        self.validate_participants(appointment.patient, appointment.doctor)
        if appointment.is_active and self.has_doctor_conflict(
            appointment.doctor, appointment.scheduled_at, appointment.duration_minutes
        ):
            raise ValueError(
                f"Doctor {appointment.doctor.id} already has an active appointment "
                f"overlapping or less than 15 minutes from {appointment.scheduled_at}."
            )
        if appointment.is_active and self.has_patient_conflict(
            appointment.patient, appointment.scheduled_at, appointment.duration_minutes
        ):
            raise ValueError(
                f"Patient {appointment.patient.id} already has an active appointment "
                f"overlapping or less than 15 minutes from {appointment.scheduled_at}."
            )
        self.appointments[appointment.appointment_id] = appointment

    def register_appointment(self, appointment: Appointment) -> None:
        self.schedule_appointment(appointment)

    def find_appointment(self, appointment_id: str):
        return self.appointments.get(appointment_id)

    def register_visit(self, visit: Visit) -> None:
        if not isinstance(visit, Visit):
            raise TypeError("visit must be a Visit instance.")
        if visit.visit_id in self.visits:
            raise ValueError(f"Visit with ID {visit.visit_id} already exists.")
        for existing in self.visits.values():
            if existing.appointment.appointment_id == visit.appointment.appointment_id:
                raise ValueError(
                    f"Appointment {visit.appointment.appointment_id} already has a visit."
                )
        self.visits[visit.visit_id] = visit

    def find_visit(self, visit_id: str):
        return self.visits.get(visit_id)

    def __repr__(self) -> str:
        return (
            f"ClinicManager(patients={len(self.patients)}, "
            f"doctors={len(self.doctors)}, "
            f"appointments={len(self.appointments)}, "
            f"visits={len(self.visits)})"
        )
