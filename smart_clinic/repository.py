import json
from datetime import datetime

from smart_clinic.models import (
    Appointment,
    ClinicManager,
    Doctor,
    Patient,
    Visit,
)


def _load_patient(record: dict, manager: ClinicManager, line_num: int):
    for field in ("id", "name"):
        if field not in record:
            raise ValueError(
                f"Line {line_num}: Patient record missing required fields ('id', 'name')."
            )
    try:
        patient = Patient.from_dict(record)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Line {line_num}: Invalid patient record: {exc}")
    manager.register_patient(patient)


def _load_doctor(record: dict, manager: ClinicManager, line_num: int):
    for field in ("id", "name", "specialty"):
        if field not in record:
            raise ValueError(
                f"Line {line_num}: Doctor record missing required fields ('id', 'name', 'specialty')."
            )
    try:
        doctor = Doctor.from_dict(record)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Line {line_num}: Invalid doctor record: {exc}")
    manager.register_doctor(doctor)


def _load_appointment(record: dict, manager: ClinicManager, line_num: int):
    for field in ("appointment_id", "patient_id", "doctor_id", "scheduled_at", "status"):
        if field not in record:
            raise ValueError(f"Line {line_num}: Missing appointment field '{field}'.")

    patient = manager.find_patient(record["patient_id"])
    if patient is None:
        raise ValueError(
            f"Line {line_num}: Unknown patient '{record['patient_id']}' for appointment '{record['appointment_id']}'."
        )

    doctor = manager.find_doctor(record["doctor_id"])
    if doctor is None:
        raise ValueError(
            f"Line {line_num}: Unknown doctor '{record['doctor_id']}' for appointment '{record['appointment_id']}'."
        )

    try:
        scheduled_at = datetime.fromisoformat(record["scheduled_at"])
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"Line {line_num}: Invalid scheduled_at datetime '{record['scheduled_at']}': {exc}"
        )

    try:
        appointment = Appointment(
            appointment_id=record["appointment_id"],
            patient=patient,
            doctor=doctor,
            scheduled_at=scheduled_at,
            status=record["status"],
        )
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Line {line_num}: Invalid appointment record: {exc}")

    manager.schedule_appointment(appointment)


def _load_visit(record: dict, manager: ClinicManager, line_num: int):
    for field in ("visit_id", "appointment_id", "summary"):
        if field not in record:
            raise ValueError(f"Line {line_num}: Missing visit field '{field}'.")

    appointment = manager.find_appointment(record["appointment_id"])
    if appointment is None:
        raise ValueError(
            f"Line {line_num}: Unknown appointment '{record['appointment_id']}' for visit '{record['visit_id']}'."
        )

    try:
        visit = Visit(
            visit_id=record["visit_id"],
            appointment=appointment,
            summary=record["summary"],
        )
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Line {line_num}: Invalid visit record: {exc}")

    manager.register_visit(visit)


def load_clinic_data(file_path) -> ClinicManager:
    manager = ClinicManager()

    with open(file_path, "r", encoding="utf-8") as file:
        for line_num, line in enumerate(file, start=1):
            stripped = line.strip()
            if not stripped:
                continue

            try:
                record = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Line {line_num}: Malformed JSON: {exc}")

            if not isinstance(record, dict):
                raise ValueError(f"Line {line_num}: Expected a JSON object.")

            record_type = record.get("record_type")
            if record_type == "patient":
                _load_patient(record, manager, line_num)
            elif record_type == "doctor":
                _load_doctor(record, manager, line_num)
            elif record_type == "appointment":
                _load_appointment(record, manager, line_num)
            elif record_type == "visit":
                _load_visit(record, manager, line_num)
            else:
                raise ValueError(f"Line {line_num}: Unknown record_type '{record_type}'.")

    return manager
