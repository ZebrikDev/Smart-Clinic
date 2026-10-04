#### Iterator over a sequence of appointments.
class AppointmentIterator:
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


#### Iterable collection of appointments.
class AppointmentCollection:
    def __init__(self, appointments: list):
        self.appointments = appointments

    def __iter__(self):
        return AppointmentIterator(self.appointments)


#### Completed appointments for one patient.
def completed_appointments_for_patient(appointments, patient_id: str):
    for appointment in appointments:
        if appointment.patient.id == patient_id and appointment.status == "completed":
            yield appointment


#### Three-stage lazy pipeline for active appointments.
def appointment_label_pipeline(appointments):
    active_appointments = (
        appointment
        for appointment in appointments
        if appointment.is_active
    )

    patient_doctor_pairs = (
        (appointment.patient.name, appointment.doctor.name)
        for appointment in active_appointments
    )

    labels = (
        f"{patient_name} -> {doctor_name}"
        for patient_name, doctor_name in patient_doctor_pairs
    )

    return labels
