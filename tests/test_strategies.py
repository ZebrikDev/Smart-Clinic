from datetime import datetime

import pytest

from smart_clinic.api_client import CalendarSnapshot
from smart_clinic.models import Appointment, ClinicManager, Doctor, Patient
from smart_clinic.scheduling import calculate_available_slots
from smart_clinic.strategies import (
    ClosestToRequestedStrategy, EarliestAvailableStrategy, SlotSelectionStrategy,
)


def at(hour, minute=0):
    return datetime(2026, 10, 29, hour, minute)


@pytest.fixture
def slots():
    # Already-valid alternatives in deliberately unsorted order.
    return [(at(11, 30), at(12)), (at(9, 15), at(9, 45)), (at(10, 45), at(11, 15))]


@pytest.mark.parametrize("strategy_type", [EarliestAvailableStrategy, ClosestToRequestedStrategy])
def test_strategies_share_contract(strategy_type):
    assert isinstance(strategy_type(), SlotSelectionStrategy)


@pytest.mark.parametrize("preferred", [None, at(8), at(12)])
def test_earliest_selects_first_start_regardless_of_preference(slots, preferred):
    before = list(slots)
    selected = EarliestAvailableStrategy().select(slots, preferred)
    assert selected is slots[1]  # 09:15, even though 11:30 appears first.
    assert slots == before


@pytest.mark.parametrize(
    "preferred, expected_index",
    [(at(8), 1), (at(9, 15), 1), (at(10), 1),
     (at(11), 2), (at(11, 30), 0), (at(14), 0)],
    ids=["before-all", "exact-early", "equal-distance", "nearest-middle", "exact-late", "after-all"],
)
def test_closest_selects_by_preference(slots, preferred, expected_index):
    before = list(slots)
    selected = ClosestToRequestedStrategy().select(slots, preferred)
    assert selected is slots[expected_index]
    assert slots == before


@pytest.mark.parametrize("later_first", [True, False])
def test_closest_tie_chooses_earlier_in_either_input_order(slots, later_first):
    early, late = slots[1], slots[2]  # 09:15 and 10:45 are both 45 minutes from 10:00.
    choices = (late, early) if later_first else (early, late)
    assert ClosestToRequestedStrategy().select(choices, at(10)) is early
    assert choices == ((late, early) if later_first else (early, late))


@pytest.mark.parametrize("strategy_type", [EarliestAvailableStrategy, ClosestToRequestedStrategy])
@pytest.mark.parametrize("empty", [[], ()])
def test_empty_collection_returns_none(strategy_type, empty):
    assert strategy_type().select(empty, None) is None


@pytest.mark.parametrize(
    "strategy_type, expected_slot",
    [(EarliestAvailableStrategy, (at(9), at(9, 30))),
     (ClosestToRequestedStrategy, (at(11), at(11, 30)))],
)
def test_selection_preserves_valid_slots_and_clinic_state(strategy_type, expected_slot):
    clinic = ClinicManager()
    patient = Patient("P1", "Synthetic Patient")
    doctor = Doctor("D1", "Synthetic Doctor", "General")
    clinic.register_patient(patient)
    clinic.register_doctor(doctor)
    appointment = Appointment("A1", patient, doctor, at(10))
    clinic.schedule_appointment(appointment)
    snapshot = CalendarSnapshot("D1", at(8, 45), at(12, 15), [], "simulated")
    valid_slots = calculate_available_slots(
        "D1", "P1", [(at(9), at(12))], at(9), at(12), snapshot,
        clinic.appointments.values(),
    )
    before_slots = list(valid_slots)
    before_appointments = dict(clinic.appointments)
    before_fields = vars(appointment).copy()

    selected = strategy_type().select(valid_slots, at(11))

    assert selected == expected_slot
    assert any(selected is slot for slot in valid_slots)
    assert valid_slots == before_slots
    assert clinic.appointments == before_appointments
    assert vars(appointment) == before_fields
    assert snapshot.busy_intervals == ()
