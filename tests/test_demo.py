import asyncio
import socket
from datetime import timedelta
from unittest.mock import Mock

import main
import pytest

from smart_clinic.api_client import JsonCalendarClient
from smart_clinic.config import PROJECT_ROOT
from smart_clinic.demo_data import WINDOW_END, WINDOW_START, prepare_demo_inputs
from smart_clinic.demo_stage2 import DemonstrationFailureClient, run_stage2_demo


@pytest.fixture(scope="module")
def run():
    """Create Windows' internal event-loop socket pair before the per-test guard.

    Network isolation stays active throughout each combined demonstration, as
    in Yotam's reviewed M7 tests. Only the runner is injected, not the collectors.
    """
    with asyncio.Runner() as runner:
        runner.get_loop()
        yield runner.run


def test_default_main_preserves_stage1_and_runs_offline_without_credentials(monkeypatch, capsys, run):
    for key in ("GOOGLE_CALENDAR_API_KEY", "GOOGLE_CALENDAR_MAPPING", "REQUEST_TIMEOUT"):
        monkeypatch.delenv(key, raising=False)
    http = Mock(side_effect=AssertionError("Default demo must not attempt HTTP."))
    dotenv = Mock(side_effect=AssertionError("Offline demo must not read .env."))
    monkeypatch.setattr("requests.sessions.Session.request", http)
    monkeypatch.setattr("smart_clinic.config.load_dotenv", dotenv)
    paths = [PROJECT_ROOT / "data/sample_data.jsonl", PROJECT_ROOT / "data/calendar_responses.json"]
    before = [path.read_bytes() for path in paths]
    result = main.main(run=run)
    output = capsys.readouterr().out
    for section in range(1, 16):
        assert f"=== {section}. " in output
    assert output.index("=== 15. ") < output.index("=== Stage 2:")
    assert "source=simulated" in output and "source=live" not in output
    assert "Working-hour candidates: 11; available after external busy: 6" in output
    assert "EarliestAvailableStrategy: 09:00-09:30" in output
    assert "ClosestToRequestedStrategy: 11:00-11:30" in output
    assert "Explicit 09:30-10:00 rejected, as expected" in output
    assert "injected DemonstrationFailureClient (test client, no HTTP)" in output
    assert "backfill=deferred" in output
    collected = result["availability"]
    assert collected["sequential"] == collected["concurrent"]
    assert [(identifier, len(slots)) for identifier, slots in collected["concurrent"]] == [
        ("D001", 6), ("D002", 11), ("D003", 0),
    ]
    assert sorted(kind for kind, value in result["bookings"]) == ["booked", "rejected"]
    assert "Appointments before: 7, after: 8" in output
    assert "Scheduled at D002 09:00-09:30: 1" in output
    assert "Same complete results, in input order: True" in output
    assert "Sequential:" in output and "Concurrent:" in output
    assert [path.read_bytes() for path in paths] == before
    http.assert_not_called()
    dotenv.assert_not_called()


def test_combined_demonstrations_use_independent_fresh_clinics(monkeypatch, capsys, run):
    clinics = []

    def record_inputs():
        prepared = prepare_demo_inputs()
        clinics.append(prepared[0].manager)
        return prepared

    for module in ("demo_stage2", "demo_async", "threaded_processing"):
        monkeypatch.setattr(f"smart_clinic.{module}.prepare_demo_inputs", record_inputs)
    main.main(run=run)
    assert len(clinics) == 4  # Business, controlled failure, M7, M8.
    assert len({id(clinic) for clinic in clinics}) == 4
    assert [len(clinic.appointments) for clinic in clinics] == [11, 8, 7, 8]


def test_network_guard_still_blocks_outbound_connections():
    with socket.socket() as connection:
        with pytest.raises(AssertionError, match="must not access the network"):
            connection.connect(("192.0.2.1", 443))


def test_demo_books_locally_and_preserves_fifo_history(capsys):
    result = run_stage2_demo()["successful"]
    service = result["service"]
    manager = service.manager
    original = result["original"]
    first = result["first_backfill"]["replacement"]
    second = result["second_backfill"]["replacement"]
    assert manager.find_appointment("DEMO-REJECTED") is None
    assert original.status == "cancelled"
    assert first.patient is manager.find_patient("P003") and first.status == "cancelled"
    assert second.patient is manager.find_patient("P002") and second.status == "scheduled"
    assert len({original.appointment_id, first.appointment_id, second.appointment_id}) == 3
    assert original.scheduled_at == first.scheduled_at == second.scheduled_at == WINDOW_START.replace(hour=10, minute=45)
    assert [r.request_id for r in result["queue_after_first"]] == ["WAIT-FIRST", "WAIT-THIRD"]
    assert [r.request_id for r in service.waiting_requests("D001")] == ["WAIT-THIRD"]
    assert len(manager.appointments) == 11  # Seven historical records plus four new local records.
    assert [a.appointment_id for a in manager.appointments.values()
            if a.is_active and a.doctor.id == "D001" and a.scheduled_at.date() == WINDOW_START.date()] == [second.appointment_id]


def test_injected_failure_demo_preserves_cancellation_and_waiting_request(capsys):
    deferred = run_stage2_demo()["deferred"]
    service, result, request = deferred["service"], deferred["result"], deferred["request"]
    assert isinstance(service.client, DemonstrationFailureClient)
    assert result["backfill_status"] == "deferred" and result["replacement"] is None
    assert result["cancelled_appointment"].status == "cancelled"
    assert service.waiting_requests("D001") == (request,)
    assert len(service.manager.appointments) == 8  # Only the original local booking was added.


def test_handoff_inputs_cover_three_registered_doctors_without_mutation():
    service, patient, doctors, snapshots = prepare_demo_inputs()
    assert isinstance(service.client, JsonCalendarClient)
    assert [doctor.id for doctor in doctors] == ["D001", "D002", "D003"]
    before = dict(service.manager.appointments)
    results = []
    for doctor in doctors:
        assert doctor is service.manager.find_doctor(doctor.id)
        assert service.working_hours[doctor.id] == [(WINDOW_START, WINDOW_END)]
        snapshot = snapshots[doctor.id]
        assert snapshot.source == "simulated" and snapshot.doctor_id == doctor.id
        assert snapshot.window_start == WINDOW_START - timedelta(minutes=15)
        assert snapshot.window_end == WINDOW_END + timedelta(minutes=15)
        results.append(service.available_slots_using_snapshot(patient, doctor, WINDOW_START, WINDOW_END, snapshot))
    assert [len(slots) for slots in results] == [6, 11, 0]
    assert results[0][0] == (WINDOW_START, WINDOW_START + timedelta(minutes=30))
    assert results[1][-1] == (WINDOW_END - timedelta(minutes=30), WINDOW_END)
    assert service.manager.appointments == before
