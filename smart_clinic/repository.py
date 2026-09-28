import json
from datetime import datetime
from pathlib import Path

from smart_clinic.models import (
    Appointment,
    ClinicManager,
    Doctor,
    Patient,
    Visit,
)


def _load_patient(record: dict, manager: ClinicManager, line_num: int) -> None:
    if "id" not in record or "name" not in record:
        raise ValueError(
            f"Line {line_num}: Patient record missing required fields ('id', 'name')."
        )
    try:
        patient = Patient.from_dict(record)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Line {line_num}: Invalid patient record: {exc}") from exc
    manager.register_patient(patient)


def _load_doctor(record: dict, manager: ClinicManager, line_num: int) -> None:
    if "id" not in record or "name" not in record or "specialty" not in record:
        raise ValueError(
            f"Line {line_num}: Doctor record missing required fields ('id', 'name', 'specialty')."
        )
    try:
        doctor = Doctor.from_dict(record)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Line {line_num}: Invalid doctor record: {exc}") from exc
    manager.register_doctor(doctor)


def _load_appointment(record: dict, manager: ClinicManager, line_num: int) -> None:
    required = {"appointment_id", "patient_id", "doctor_id", "scheduled_at", "status"}
    if not required.issubset(record.keys()):
        missing = required - set(record.keys())
        raise ValueError(f"Line {line_num}: Appointment record missing fields: {missing}.")

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
        ) from exc

    try:
        appointment = Appointment(
            appointment_id=record["appointment_id"],
            patient=patient,
            doctor=doctor,
            scheduled_at=scheduled_at,
            status=record["status"],
        )
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Line {line_num}: Invalid appointment record: {exc}") from exc

    manager.schedule_appointment(appointment)


def _load_visit(record: dict, manager: ClinicManager, line_num: int) -> None:
    required = {"visit_id", "appointment_id", "summary"}
    if not required.issubset(record.keys()):
        missing = required - set(record.keys())
        raise ValueError(f"Line {line_num}: Visit record missing fields: {missing}.")

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
        raise ValueError(f"Line {line_num}: Invalid visit record: {exc}") from exc

    manager.register_visit(visit)


def load_clinic_data(file_path: str | Path) -> ClinicManager:
    manager = ClinicManager()
    path = Path(file_path)

    with open(path, "r", encoding="utf-8") as file:
        for line_num, line in enumerate(file, start=1):
            stripped = line.strip()
            if not stripped:
                continue

            try:
                record = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Line {line_num}: Malformed JSON: {exc}") from exc

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
