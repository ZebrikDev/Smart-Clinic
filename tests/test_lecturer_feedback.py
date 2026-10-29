import unittest
from datetime import datetime
from pathlib import Path

from smart_clinic.context_managers import AppointmentProcessing
from smart_clinic.models import Appointment, ClinicManager, Doctor, Patient
from smart_clinic.repository import load_clinic_data


class LecturerFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.patient = Patient("P1", "Example Patient")
        self.doctor = Doctor("D1", "Example Doctor", "General")
        self.clinic = ClinicManager()
        self.clinic.register_patient(self.patient)
        self.clinic.register_doctor(self.doctor)

    def appointment(self, status="scheduled", appointment_id="A1", patient=None, doctor=None):
        return Appointment(
            appointment_id,
            self.patient if patient is None else patient,
            self.doctor if doctor is None else doctor,
            datetime(2026, 10, 29, 9),
            status,
        )

    def test_all_initial_statuses_remain_supported(self):
        for status in Appointment.VALID_STATUSES:
            with self.subTest(status=status):
                appointment = self.appointment(status)
                self.assertEqual(appointment.status, status)
                self.assertEqual(appointment.is_active, status in Appointment.ACTIVE_STATUSES)

    def test_direct_status_assignment_is_blocked(self):
        appointment = self.appointment()
        for value in ("completed", "cancelled", "invalid", None, []):
            with self.subTest(value=value):
                with self.assertRaises(AttributeError):
                    appointment.status = value
                self.assertEqual(appointment.status, "scheduled")

    def test_direct_assignment_cannot_reactivate_terminal_appointment(self):
        for status in ("completed", "cancelled", "no_show"):
            for target in Appointment.ACTIVE_STATUSES:
                with self.subTest(status=status, target=target):
                    appointment = self.appointment(status)
                    with self.assertRaises(AttributeError):
                        appointment.status = target
                    self.assertEqual(appointment.status, status)

    def test_invalid_statuses_are_rejected_without_changing_state(self):
        for value in ("invalid", "", None, [], {}, 1):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.appointment(value)
                appointment = self.appointment()
                with self.assertRaises(ValueError):
                    appointment.update_status(value)
                self.assertEqual(appointment.status, "scheduled")

    def test_all_business_status_transitions(self):
        for initial in Appointment.VALID_STATUSES:
            for target in Appointment.VALID_STATUSES:
                with self.subTest(initial=initial, target=target):
                    appointment = self.appointment(initial)
                    # M1 adds no_show as terminal: reactivation must now fail too.
                    if (
                        initial in {"completed", "cancelled", "no_show"}
                        and target in Appointment.ACTIVE_STATUSES
                    ):
                        with self.assertRaises(ValueError):
                            appointment.update_status(target)
                        self.assertEqual(appointment.status, initial)
                    else:
                        appointment.update_status(target)
                        self.assertEqual(appointment.status, target)

    def test_context_success(self):
        for initial in ("scheduled", "in_progress"):
            with self.subTest(initial=initial):
                appointment = self.appointment(initial)
                with AppointmentProcessing(appointment) as entered:
                    self.assertIs(entered, appointment)
                    self.assertEqual(appointment.status, "in_progress")
                self.assertEqual(appointment.status, "completed")

    def test_context_rollback_preserves_original_exception(self):
        for initial in ("scheduled", "in_progress"):
            for inside in (None, "completed", "cancelled", "no_show"):
                with self.subTest(initial=initial, inside=inside):
                    appointment = self.appointment(initial)
                    original = RuntimeError("processing failed")
                    with self.assertRaises(RuntimeError) as raised:
                        with AppointmentProcessing(appointment):
                            if inside is not None:
                                appointment.update_status(inside)
                            raise original
                    self.assertIs(raised.exception, original)
                    self.assertEqual(appointment.status, initial)

    def test_context_does_not_suppress_exception(self):
        appointment = self.appointment()
        context = AppointmentProcessing(appointment)
        context.__enter__()
        error = RuntimeError("processing failed")
        self.assertIs(context.__exit__(RuntimeError, error, None), False)
        self.assertEqual(appointment.status, "scheduled")

    def test_context_rejects_terminal_appointments(self):
        for status in ("completed", "cancelled", "no_show"):
            with self.subTest(status=status):
                appointment = self.appointment(status)
                with self.assertRaises(ValueError):
                    with AppointmentProcessing(appointment):
                        self.fail("Inactive appointment entered the context")
                self.assertEqual(appointment.status, status)

    def test_registered_objects_can_be_scheduled(self):
        appointment = self.appointment()
        self.clinic.schedule_appointment(appointment)
        self.assertIs(self.clinic.find_appointment("A1"), appointment)

    def test_unregistered_patient_is_rejected(self):
        outsider = Patient("P2", "Unregistered Patient")
        with self.assertRaisesRegex(ValueError, "patient must be registered"):
            self.clinic.schedule_appointment(self.appointment(patient=outsider))
        self.assertEqual(self.clinic.appointments, {})

    def test_unregistered_doctor_is_rejected(self):
        outsider = Doctor("D2", "Unregistered Doctor", "General")
        with self.assertRaisesRegex(ValueError, "doctor must be registered"):
            self.clinic.schedule_appointment(self.appointment(doctor=outsider))
        self.assertEqual(self.clinic.appointments, {})

    def test_same_patient_id_on_another_object_is_rejected(self):
        outsider = Patient(self.patient.id, "Different Patient")
        with self.assertRaisesRegex(ValueError, "patient must be registered"):
            self.clinic.schedule_appointment(self.appointment(patient=outsider))
        self.assertEqual(self.clinic.appointments, {})

    def test_same_doctor_id_on_another_object_is_rejected(self):
        outsider = Doctor(self.doctor.id, "Different Doctor", "General")
        with self.assertRaisesRegex(ValueError, "doctor must be registered"):
            self.clinic.schedule_appointment(self.appointment(doctor=outsider))
        self.assertEqual(self.clinic.appointments, {})

    def test_objects_from_another_clinic_are_rejected(self):
        other = ClinicManager()
        other.register_patient(Patient("P1", "Other Patient"))
        other.register_doctor(Doctor("D1", "Other Doctor", "General"))
        with self.assertRaises(ValueError):
            other.schedule_appointment(self.appointment())
        self.assertEqual(other.appointments, {})

    def test_inactive_appointments_also_require_registered_objects(self):
        for status in ("completed", "cancelled", "no_show"):
            with self.subTest(status=status):
                with self.assertRaises(ValueError):
                    ClinicManager().schedule_appointment(self.appointment(status))

    def test_registration_alias_also_validates_membership(self):
        with self.assertRaises(ValueError):
            ClinicManager().register_appointment(self.appointment())
        appointment = self.appointment()
        self.clinic.register_appointment(appointment)
        self.assertIs(self.clinic.find_appointment("A1"), appointment)

    def test_duplicate_id_and_doctor_conflict_checks_remain(self):
        first = self.appointment()
        self.clinic.schedule_appointment(first)
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.clinic.schedule_appointment(self.appointment())
        second = self.appointment(appointment_id="A2")
        with self.assertRaisesRegex(ValueError, "already has an active appointment"):
            self.clinic.schedule_appointment(second)
        self.assertEqual(list(self.clinic.appointments), ["A1"])
        first.update_status("cancelled")
        self.clinic.schedule_appointment(second)
        self.assertIs(self.clinic.find_appointment("A2"), second)

    def test_sample_data_still_loads_with_registered_references(self):
        path = Path(__file__).resolve().parents[1] / "data" / "sample_data.jsonl"
        clinic = load_clinic_data(path)
        self.assertEqual(len(clinic.appointments), 7)
        for appointment in clinic.appointments.values():
            self.assertIs(clinic.find_patient(appointment.patient.id), appointment.patient)
            self.assertIs(clinic.find_doctor(appointment.doctor.id), appointment.doctor)


if __name__ == "__main__":
    unittest.main()
