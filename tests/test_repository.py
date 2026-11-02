import json
from datetime import datetime
from pathlib import Path

import pytest

from smart_clinic.repository import load_clinic_data


def write_records(tmp_path, **appointment_fields):
    rows = [
        {"record_type": "patient", "id": "P1", "name": "Synthetic Patient"},
        {"record_type": "doctor", "id": "D1", "name": "Synthetic Doctor", "specialty": "General"},
        {
            "record_type": "appointment", "appointment_id": "A1",
            "patient_id": "P1", "doctor_id": "D1",
            "scheduled_at": "2026-10-29T10:00:00", "status": "scheduled",
            **appointment_fields,
        },
    ]
    path = tmp_path / "clinic.jsonl"
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    return path


def test_original_dataset_uses_default_duration():
    path = Path(__file__).resolve().parents[1] / "data" / "sample_data.jsonl"
    clinic = load_clinic_data(path)
    assert (len(clinic.patients), len(clinic.doctors), len(clinic.appointments), len(clinic.visits)) == (5, 4, 7, 3)
    assert all(a.duration_minutes == 30 for a in clinic.appointments.values())
    assert clinic.find_appointment("A004").end_at == datetime(2026, 10, 5, 11)


def test_jsonl_without_duration_remains_supported(tmp_path):
    clinic = load_clinic_data(write_records(tmp_path))
    appointment = clinic.find_appointment("A1")
    assert appointment.duration_minutes == 30
    assert appointment.end_at == datetime(2026, 10, 29, 10, 30)


def test_jsonl_can_load_explicit_duration_and_no_show(tmp_path):
    clinic = load_clinic_data(write_records(tmp_path, duration_minutes=60, status="no_show"))
    appointment = clinic.find_appointment("A1")
    assert appointment.duration_minutes == 60
    assert appointment.end_at == datetime(2026, 10, 29, 11)
    assert appointment.status == "no_show"
    assert not appointment.is_active
    assert appointment.patient is clinic.find_patient("P1")
    assert appointment.doctor is clinic.find_doctor("D1")


@pytest.mark.parametrize("duration", [True, False, 0, -1, 1.5, "30", None, [], {}])
def test_jsonl_rejects_invalid_duration_with_line_number(tmp_path, duration):
    path = write_records(tmp_path, duration_minutes=duration)
    with pytest.raises(ValueError, match="Line 3:.*duration_minutes"):
        load_clinic_data(path)


def test_jsonl_registration_enforces_gap_for_explicit_duration(tmp_path):
    path = write_records(tmp_path, duration_minutes=60)
    second = {
        "record_type": "appointment", "appointment_id": "A2",
        "patient_id": "P1", "doctor_id": "D1",
        "scheduled_at": "2026-10-29T11:14:00", "status": "scheduled",
    }
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(second) + "\n")
    with pytest.raises(ValueError, match="Line 4:.*Doctor D1"):
        load_clinic_data(path)
