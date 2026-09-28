class AppointmentIterator:
    """Iterator over a sequence of appointments."""

    def __init__(self, appointments: list):
        self.appointments = appointments
        self.index = 0

    def __iter__(self):
        return self

    def __next__(self):
        if self.index >= len(self.appointments):
            raise StopIteration
        appointment = self.appointments[self.index]
        self.index += 1
        return appointment


class AppointmentCollection:
    """Iterable collection of appointments."""

    def __init__(self, appointments: list):
        self.appointments = appointments

    def __iter__(self):
        return AppointmentIterator(self.appointments)


def completed_appointments_for_patient(appointments, patient_id: str):
    """Yield completed appointments for one patient."""
    for appointment in appointments:
        if appointment.patient.id == patient_id and appointment.status == "completed":
            yield appointment


def appointment_label_pipeline(appointments):
    """Return labels for active appointments."""
    active = (a for a in appointments if a.is_active)
    pairs = ((a.patient.name, a.doctor.name) for a in active)
    labels = (f"{patient} -> {doctor}" for patient, doctor in pairs)
    return labels
