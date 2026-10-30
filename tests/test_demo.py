from datetime import timedelta
from unittest.mock import Mock

import main

from smart_clinic.api_client import JsonCalendarClient
from smart_clinic.config import PROJECT_ROOT
from smart_clinic.demo_data import WINDOW_END, WINDOW_START, prepare_demo_inputs
from smart_clinic.demo_stage2 import DemonstrationFailureClient, run_stage2_demo


def test_default_main_preserves_stage1_and_runs_offline_without_credentials(monkeypatch, capsys):
    for key in ("GOOGLE_CALENDAR_API_KEY", "GOOGLE_CALENDAR_MAPPING", "REQUEST_TIMEOUT"):
        monkeypatch.delenv(key, raising=False)
    http = Mock(side_effect=AssertionError("Default demo must not attempt HTTP."))
    dotenv = Mock(side_effect=AssertionError("Offline demo must not read .env."))
    monkeypatch.setattr("requests.sessions.Session.request", http)
    monkeypatch.setattr("smart_clinic.config.load_dotenv", dotenv)
    paths = [PROJECT_ROOT / "data/sample_data.jsonl", PROJECT_ROOT / "data/calendar_responses.json"]
    before = [path.read_bytes() for path in paths]
    main.main()
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
    assert [path.read_bytes() for path in paths] == before
    http.assert_not_called()
    dotenv.assert_not_called()


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
