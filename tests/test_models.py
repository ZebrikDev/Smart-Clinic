from datetime import datetime, timedelta

import pytest

from smart_clinic.models import Appointment, ClinicManager, Doctor, Patient, Visit


@pytest.fixture
def clinic():
    manager = ClinicManager()
    for patient_id in ("P1", "P2"):
        manager.register_patient(Patient(patient_id, f"Patient {patient_id}"))
    for doctor_id in ("D1", "D2"):
        manager.register_doctor(Doctor(doctor_id, f"Doctor {doctor_id}", "General"))
    return manager


def make_appointment(clinic, appointment_id, start, **kwargs):
    patient = clinic.find_patient(kwargs.pop("patient_id", "P1"))
    doctor = clinic.find_doctor(kwargs.pop("doctor_id", "D1"))
    return Appointment(appointment_id, patient, doctor, start, **kwargs)


@pytest.mark.parametrize("resource", ["doctor", "patient"])
@pytest.mark.parametrize("direction", ["before", "after"])
@pytest.mark.parametrize("gap, accepted", [(14, False), (15, True), (16, True)])
@pytest.mark.parametrize("method", ["schedule_appointment", "register_appointment"])
def test_gap_boundaries(clinic, resource, direction, gap, accepted, method):
    # The existing appointment occupies 10:00-10:45; the candidate lasts 20 minutes.
    first = make_appointment(
        clinic, "A1", datetime(2026, 10, 29, 10), duration_minutes=45
    )
    clinic.schedule_appointment(first)
    if direction == "before":
        start = datetime(2026, 10, 29, 9, 40) - timedelta(minutes=gap)
    else:
        start = datetime(2026, 10, 29, 10, 45) + timedelta(minutes=gap)
    candidate = make_appointment(
        clinic,
        "A2",
        start,
        patient_id="P2" if resource == "doctor" else "P1",
        doctor_id="D1" if resource == "doctor" else "D2",
        duration_minutes=20,
    )

    if accepted:
        getattr(clinic, method)(candidate)
        assert clinic.find_appointment("A2") is candidate
    else:
        with pytest.raises(ValueError, match=resource.capitalize()):
            getattr(clinic, method)(candidate)
        assert clinic.appointments == {"A1": first}


@pytest.mark.parametrize("resource", ["doctor", "patient"])
@pytest.mark.parametrize("status", ["scheduled", "in_progress"])
@pytest.mark.parametrize(
    "start, duration",
    [
        (datetime(2026, 10, 29, 9, 45), 30),  # overlaps from before
        (datetime(2026, 10, 29, 10), 20),  # same start
        (datetime(2026, 10, 29, 10, 15), 15),  # contained in the existing interval
        (datetime(2026, 10, 29, 9, 30), 120),  # contains the existing interval
        (datetime(2026, 10, 29, 10, 45), 30),  # touching still lacks the gap
    ],
)
def test_active_conflicts(clinic, resource, status, start, duration):
    first = make_appointment(
        clinic, "A1", datetime(2026, 10, 29, 10), status=status, duration_minutes=45
    )
    clinic.schedule_appointment(first)
    candidate = make_appointment(
        clinic,
        "A2",
        start,
        patient_id="P2" if resource == "doctor" else "P1",
        doctor_id="D1" if resource == "doctor" else "D2",
        duration_minutes=duration,
    )
    with pytest.raises(ValueError, match=resource.capitalize()):
        clinic.schedule_appointment(candidate)
    assert clinic.appointments == {"A1": first}


def test_unrelated_doctor_and_patient_can_book_same_time(clinic):
    first = make_appointment(clinic, "A1", datetime(2026, 10, 29, 10))
    second = make_appointment(
        clinic, "A2", datetime(2026, 10, 29, 10), patient_id="P2", doctor_id="D2"
    )
    clinic.schedule_appointment(first)
    clinic.schedule_appointment(second)
    assert list(clinic.appointments.values()) == [first, second]


@pytest.mark.parametrize("duration", [True, False, 0, -1, 1.5, "30", None, [], {}])
def test_invalid_duration_is_rejected(clinic, duration):
    with pytest.raises(ValueError, match="duration_minutes must be a positive integer"):
        make_appointment(
            clinic, "A1", datetime(2026, 10, 29, 10), duration_minutes=duration
        )
    assert clinic.appointments == {}


@pytest.mark.parametrize("value", [True, 0, -1, None, 45])
def test_duration_cannot_be_assigned_directly(clinic, value):
    appointment = make_appointment(clinic, "A1", datetime(2026, 10, 29, 10))
    with pytest.raises(AttributeError):
        appointment.duration_minutes = value
    assert appointment.duration_minutes == 30
    assert appointment.end_at == datetime(2026, 10, 29, 10, 30)


@pytest.mark.parametrize(
    "duration, expected_end",
    [
        (1, datetime(2026, 10, 29, 10, 1)),
        (30, datetime(2026, 10, 29, 10, 30)),
        (90, datetime(2026, 10, 29, 11, 30)),
        (1440, datetime(2026, 10, 30, 10)),
    ],
)
def test_positive_duration_and_computed_end(clinic, duration, expected_end):
    appointment = make_appointment(
        clinic, "A1", datetime(2026, 10, 29, 10), duration_minutes=duration
    )
    assert appointment.duration_minutes == duration
    assert appointment.end_at == expected_end
    with pytest.raises(AttributeError):
        appointment.end_at = datetime(2026, 10, 29, 12)


def test_legacy_constructor_and_new_trailing_argument(clinic):
    args = (
        "A1", clinic.find_patient("P1"), clinic.find_doctor("D1"),
        datetime(2026, 10, 29, 10),
    )
    default = Appointment(*args)
    legacy_status = Appointment(*args, "completed")
    explicit_duration = Appointment(*args, "scheduled", 45)
    assert (default.status, default.duration_minutes) == ("scheduled", 30)
    assert (legacy_status.status, legacy_status.duration_minutes) == ("completed", 30)
    assert explicit_duration.end_at == datetime(2026, 10, 29, 10, 45)
    assert "duration_minutes=45" in repr(explicit_duration)


@pytest.mark.parametrize("status", ["cancelled", "completed", "no_show"])
def test_terminal_appointments_do_not_block(clinic, status):
    first = make_appointment(clinic, "A1", datetime(2026, 10, 29, 10), status=status)
    second = make_appointment(clinic, "A2", datetime(2026, 10, 29, 10))
    clinic.schedule_appointment(first)
    clinic.register_appointment(second)
    assert not first.is_active
    assert list(clinic.appointments.values()) == [first, second]


@pytest.mark.parametrize("status", ["cancelled", "completed", "no_show"])
def test_terminal_history_can_be_registered_while_slot_is_active(clinic, status):
    first = make_appointment(clinic, "A1", datetime(2026, 10, 29, 10))
    history = make_appointment(clinic, "A2", datetime(2026, 10, 29, 10), status=status)
    clinic.schedule_appointment(first)
    clinic.register_appointment(history)
    assert list(clinic.appointments.values()) == [first, history]


@pytest.mark.parametrize("initial", ["scheduled", "in_progress"])
def test_marking_no_show_frees_slot_and_cannot_create_visit(clinic, initial):
    first = make_appointment(clinic, "A1", datetime(2026, 10, 29, 10), status=initial)
    clinic.schedule_appointment(first)
    first.update_status("no_show")
    assert not first.is_active
    with pytest.raises(ValueError, match="completed appointment"):
        Visit("V1", first, "Synthetic summary")
    replacement = make_appointment(clinic, "A2", datetime(2026, 10, 29, 10))
    clinic.schedule_appointment(replacement)
    assert clinic.find_appointment("A1").status == "no_show"
    assert clinic.find_appointment("A2") is replacement


def test_doctor_conflict_query_retains_legacy_arguments(clinic):
    first = make_appointment(clinic, "A1", datetime(2026, 10, 29, 10))
    clinic.schedule_appointment(first)
    doctor = clinic.find_doctor("D1")
    assert clinic.has_doctor_conflict(doctor, datetime(2026, 10, 29, 10))
    assert not clinic.has_doctor_conflict(doctor, datetime(2026, 10, 29, 10, 45))
