from collections import deque
from datetime import datetime
from pathlib import Path

from smart_clinic import processing
from smart_clinic.context_managers import AppointmentProcessing
from smart_clinic.iterators import (
    AppointmentCollection,
    appointment_label_pipeline,
    completed_appointments_for_patient,
)
from smart_clinic.models import Appointment, Patient, Visit
from smart_clinic.repository import load_clinic_data

DATA_FILE = Path(__file__).parent / "data" / "sample_data.jsonl"


def print_title(title):
    print(f"\n=== {title} ===")


def join_ids(appointments):
    return ", ".join(a.appointment_id for a in appointments)


def show_loading():
    print_title("1. Loading clinic data from JSONL")
    manager = load_clinic_data(DATA_FILE)
    print(manager)
    return manager


def show_dict_conversion(manager):
    print_title("2. Dict to object conversion")
    data = {"id": "P006", "name": "Barry Allen"}
    patient = Patient.from_dict(data)
    manager.register_patient(patient)
    print(f"{data} -> {patient!r}")

    try:
        Patient.from_dict({"id": "", "name": "Missing ID"})
    except ValueError as error:
        print(f"Invalid data rejected: {error}")


def show_polymorphism(manager):
    print_title("3. Inheritance and polymorphism")
    people = [
        manager.find_patient("P001"),
        manager.find_doctor("D001"),
        manager.find_patient("P002"),
        manager.find_doctor("D002"),
    ]
    for person in people:
        print(person.get_details())


def show_business_operations(manager):
    print_title("4. Composition and business operations")
    appointment = manager.find_appointment("A007")
    print(appointment)
    print(f"Patient: {appointment.patient}")
    print(f"Doctor: {appointment.doctor}, {appointment.doctor.specialty}")

    try:
        Visit("V004", appointment, "Written too early.")
    except ValueError as error:
        print(f"Visit rejected: {error}")

    appointment.update_status("completed")
    visit = Visit("V004", appointment, "Routine heart check, no issues found.")
    manager.register_visit(visit)
    print(visit)
    print(manager)


def show_scheduling(manager):
    print_title("5. Conflict-free scheduling")
    doctor = manager.find_doctor("D003")
    slot = datetime(2026, 10, 6, 9, 0)

    first = Appointment("A008", manager.find_patient("P003"), doctor, slot)
    manager.schedule_appointment(first)
    print(f"Scheduled: {first}")

    second = Appointment("A009", manager.find_patient("P004"), doctor, slot)
    try:
        manager.schedule_appointment(second)
    except ValueError as error:
        print(f"Rejected: {error}")

    first.update_status("cancelled")
    manager.schedule_appointment(second)
    print(f"A008 cancelled, slot is free again: {second}")

    third = Appointment(
        "A010",
        manager.find_patient("P006"),
        manager.find_doctor("D002"),
        datetime(2026, 10, 6, 8, 30),
    )
    manager.schedule_appointment(third)
    print(f"Scheduled: {third}")


def show_data_structures(manager, appointments):
    print_title("6. List, tuple, set and dict")
    active = processing.active_appointments(appointments)
    print(f"Active appointments (list): {join_ids(active)}")

    first, middle, last = processing.appointment_summary_parts(appointments[0])
    print(f"Summary tuple unpacked: id={first}, names={middle}, status={last}")

    active_statuses, inactive_statuses = processing.status_groups(appointments)
    print(f"Active statuses in use (set): {sorted(active_statuses)}")
    print(f"Inactive statuses in use (set): {sorted(inactive_statuses)}")

    print(f"Lookup by ID (dict): {manager.find_patient('P003')}")
    print(f"Count by status (dict): {processing.count_by_status(appointments)}")
    per_doctor = processing.appointment_count_by_doctor(appointments)
    print(f"Appointments per doctor (dict): {per_doctor}")


def show_waiting_queue(appointments):
    print_title("7. deque: regular requests in FIFO order")
    waiting = deque()
    for appointment in appointments:
        if appointment.status == "scheduled":
            waiting.append(appointment)
    print(f"Arrival order: {join_ids(waiting)}")
    handled = processing.process_waiting_queue(waiting)
    print(f"Handled order: {join_ids(handled)}")
    print(f"Empty queue handled safely: {processing.process_waiting_queue(waiting)}")


def show_priority_queue(manager):
    print_title("8. heapq: urgent requests first")
    requests = [
        (2, manager.find_appointment("A005")),
        (2, manager.find_appointment("A009")),
        (1, manager.find_appointment("A010")),
    ]

    heap = []
    for sequence, (priority, appointment) in enumerate(requests, start=1):
        processing.push_request(heap, priority, sequence, appointment)
        print(f"Request {sequence}: {appointment.appointment_id}, priority {priority}")

    while heap:
        appointment = processing.pop_next_request(heap)
        print(f"Handled next: {appointment.appointment_id}")


def show_comprehensions(appointments):
    print_title("9. Comprehensions")
    active_ids = processing.active_appointment_ids(appointments)
    print(f"Active IDs (list comprehension): {active_ids}")
    doctor_ids = processing.unique_doctor_ids(appointments)
    print(f"Doctors with appointments (set comprehension): {sorted(doctor_ids)}")
    status_map = processing.appointment_status_map(appointments)
    print(f"Status by ID (dict comprehension): {status_map}")


def show_sorting(appointments):
    print_title("10. Sorting")
    by_time = processing.sorted_by_time(appointments)
    print(f"By time (named function): {join_ids(by_time)}")

    by_patient = processing.sorted_by_patient_name(appointments)
    names = [f"{a.patient.name} {a.appointment_id}" for a in by_patient]
    print(f"By patient name (lambda): {', '.join(names)}")

    print("By doctor name, then time (tuple key):")
    for appointment in processing.sorted_by_doctor_then_time(appointments):
        time_str = appointment.scheduled_at.strftime("%m-%d %H:%M")
        print(f"  {appointment.doctor.name} | {time_str} | {appointment.appointment_id}")


def show_iterators(appointments):
    print_title("11. Two independent iterators")
    collection = AppointmentCollection(appointments)
    first = iter(collection)
    second = iter(collection)

    print(f"First iterator:  {next(first).appointment_id}")
    print(f"First iterator:  {next(first).appointment_id}")
    print(f"Second iterator: {next(second).appointment_id}")

    print(f"Rest of first iterator: {join_ids(first)}")
    try:
        next(first)
    except StopIteration:
        print("First iterator is exhausted (StopIteration)")
    print(f"Second iterator continues: {next(second).appointment_id}")


def show_generator(appointments):
    print_title("12. Generator")
    history = completed_appointments_for_patient(appointments, "P002")
    print(f"Created, nothing processed yet: {history}")
    print(f"next(): {next(history)}")
    for appointment in history:
        print(f"for loop continues: {appointment}")
    try:
        next(history)
    except StopIteration:
        print("Generator is exhausted")

    history = completed_appointments_for_patient(appointments, "P002")
    print(f"New generator starts over: {next(history)}")


def show_lazy_pipeline(appointments):
    print_title("13. Lazy pipeline")
    source = iter(AppointmentCollection(appointments))
    labels = appointment_label_pipeline(source)
    print(f"Pipeline created, appointments read: {source.index}")
    print(next(labels))
    print(next(labels))
    print(f"After two results, appointments read: {source.index} of {len(appointments)}")


def show_context_manager_success(manager):
    print_title("14. Context manager: successful processing")
    appointment = manager.find_appointment("A005")
    print(f"Before: {appointment.status}")
    with AppointmentProcessing(appointment):
        print(f"Inside: {appointment.status}")
    print(f"After:  {appointment.status}")

    visit = Visit("V005", appointment, "Blood pressure checked, all normal.")
    manager.register_visit(visit)
    print(visit)


def show_context_manager_failure(manager):
    print_title("15. Context manager: exception during processing")
    appointment = manager.find_appointment("A009")
    print(f"Before: {appointment.status}")
    try:
        with AppointmentProcessing(appointment):
            print(f"Inside: {appointment.status}")
            raise RuntimeError("Doctor was called to an emergency.")
    except RuntimeError as error:
        print(f"Exception reached the caller: {error}")
    print(f"After:  {appointment.status}")


def main():
    manager = show_loading()
    show_dict_conversion(manager)
    show_polymorphism(manager)
    show_business_operations(manager)
    show_scheduling(manager)

    appointments = list(manager.appointments.values())
    show_data_structures(manager, appointments)
    show_waiting_queue(appointments)
    show_priority_queue(manager)
    show_comprehensions(appointments)
    show_sorting(appointments)
    show_iterators(appointments)
    show_generator(appointments)
    show_lazy_pipeline(appointments)
    show_context_manager_success(manager)
    show_context_manager_failure(manager)


if __name__ == "__main__":
    main()
