from smart_clinic.models import Appointment


class AppointmentProcessing:
    """Marks an appointment as in progress while the doctor handles it."""

    def __init__(self, appointment: Appointment):
        if not isinstance(appointment, Appointment):
            raise TypeError("appointment must be an Appointment instance.")
        self.appointment = appointment
        self.previous_status = None

    def __enter__(self):
        if not self.appointment.is_active:
            raise ValueError(
                f"Appointment {self.appointment.appointment_id} is "
                f"{self.appointment.status} and cannot be processed."
            )
        self.previous_status = self.appointment.status
        self.appointment.update_status("in_progress")
        return self.appointment

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            self.appointment.update_status("completed")
        else:
            self.appointment.status = self.previous_status
        return False
