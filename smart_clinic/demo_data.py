"""Fresh offline inputs for the M6 demo and the proposed M7/M8 handoffs."""

from datetime import datetime

from smart_clinic.config import PROJECT_ROOT, load_config
from smart_clinic.factories import create_calendar_client
from smart_clinic.repository import load_clinic_data
from smart_clinic.services import AppointmentService
from smart_clinic.strategies import EarliestAvailableStrategy


WINDOW_START = datetime(2026, 10, 29, 9)
WINDOW_END = datetime(2026, 10, 29, 12)


def prepare_demo_inputs():
    """Return service, registered patient, ordered doctors and preloaded snapshots.

    Each call loads a fresh clinic. All three doctors have explicit 09:00-12:00
    hours on the fixed date, independent of today. Source files are never changed.
    Snapshots are fetched synchronously here, before any future concurrent work.
    """
    manager = load_clinic_data(PROJECT_ROOT / "data/sample_data.jsonl")
    doctors = [manager.find_doctor(identifier) for identifier in ("D001", "D002", "D003")]
    patient = manager.find_patient("P001")
    hours = {doctor.id: [(WINDOW_START, WINDOW_END)] for doctor in doctors}
    client = create_calendar_client("offline", load_config("offline"))
    service = AppointmentService(manager, client, EarliestAvailableStrategy(), hours)
    snapshots = {
        doctor.id: service.fetch_snapshot(patient, doctor, WINDOW_START, WINDOW_END)
        for doctor in doctors
    }
    return service, patient, doctors, snapshots
