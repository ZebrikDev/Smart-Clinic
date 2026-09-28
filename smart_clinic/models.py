from datetime import datetime


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


class Appointment:
    VALID_STATUSES = {"scheduled", "cancelled", "in_progress", "completed"}
    ACTIVE_STATUSES = {"scheduled", "in_progress"}

    def __init__(
        self,
        appointment_id: str,
        patient: Patient,
        doctor: Doctor,
        scheduled_at: datetime,
        status: str = "scheduled",
    ):
        if not isinstance(appointment_id, str) or not appointment_id.strip():
            raise ValueError("Appointment ID must be a non-empty string.")
        if not isinstance(patient, Patient):
            raise TypeError("patient must be a Patient instance.")
        if not isinstance(doctor, Doctor):
            raise TypeError("doctor must be a Doctor instance.")
        if not isinstance(scheduled_at, datetime):
            raise TypeError("scheduled_at must be a datetime instance.")

        self.appointment_id = appointment_id.strip()
        self.patient = patient
        self.doctor = doctor
        self.scheduled_at = scheduled_at
        self.update_status(status)

    @property
    def is_active(self) -> bool:
        return self.status in self.ACTIVE_STATUSES

    def update_status(self, status: str) -> None:
        if status not in self.VALID_STATUSES:
            raise ValueError(f"status must be one of {self.VALID_STATUSES}.")
        self.status = status

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
            f"scheduled_at={self.scheduled_at!r}, status={self.status!r})"
        )


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

    def has_doctor_conflict(self, doctor: Doctor, scheduled_at: datetime) -> bool:
        for existing in self.appointments.values():
            if (
                existing.doctor.id == doctor.id
                and existing.scheduled_at == scheduled_at
                and existing.is_active
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
        if appointment.is_active and self.has_doctor_conflict(
            appointment.doctor, appointment.scheduled_at
        ):
            raise ValueError(
                f"Doctor {appointment.doctor.id} already has an active appointment at {appointment.scheduled_at}."
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
