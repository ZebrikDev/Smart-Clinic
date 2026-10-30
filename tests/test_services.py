from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from smart_clinic.api_client import CalendarClient, CalendarReadError, CalendarSnapshot, JsonCalendarClient
from smart_clinic.models import Appointment, ClinicManager, Doctor, Patient, WaitingRequest
from smart_clinic.repository import load_clinic_data
from smart_clinic.services import AppointmentService, AvailabilityUnknownError
from smart_clinic.strategies import ClosestToRequestedStrategy, EarliestAvailableStrategy


def at(hour, minute=0):
    return datetime(2026, 10, 29, hour, minute)


@pytest.fixture
def service():
    manager = ClinicManager()
    for identifier in ('P1', 'P2', 'P3'):
        manager.register_patient(Patient(identifier, identifier))
    for identifier in ('D1', 'D2'):
        manager.register_doctor(Doctor(identifier, identifier, 'General'))
    client = Mock(spec=CalendarClient)
    client.fetch_busy_intervals.side_effect = lambda doctor_id, start, end: CalendarSnapshot(
        doctor_id, start, end, [], 'simulated'
    )
    return AppointmentService(manager, client, EarliestAvailableStrategy(),
                              {'D1': [(at(9), at(12))], 'D2': [(at(9), at(12))]})


def participants(service, patient='P1', doctor='D1'):
    return service.manager.find_patient(patient), service.manager.find_doctor(doctor)


def snapshot(busy=(), doctor='D1', start=None, end=None):
    return CalendarSnapshot(doctor, at(8) if start is None else start,
                            at(13) if end is None else end, list(busy), 'simulated')


def seed(service, identifier='ORIGINAL', patient='P1', doctor='D1', start=None,
         duration=30, status='scheduled'):
    p, d = participants(service, patient, doctor)
    appointment = Appointment(identifier, p, d, at(9) if start is None else start,
                              status, duration)
    service.manager.schedule_appointment(appointment)
    return appointment


def enqueue(service, identifier, patient='P2', doctor='D1', start=None, end=None, duration=30):
    p, d = participants(service, patient, doctor)
    request = WaitingRequest(identifier, p, d, at(9) if start is None else start,
                             at(12) if end is None else end, duration)
    return service.add_waiting_request(request)


@pytest.mark.parametrize('requested', [at(9, 30), at(10)])
def test_external_busy_changes_availability_and_blocks_shon_requests(service, requested):
    p, d = participants(service)
    service.client.fetch_busy_intervals.side_effect = lambda doctor_id, start, end: CalendarSnapshot(
        doctor_id, start, end, [(at(10), at(10, 30))], 'simulated'
    )
    assert service.available_slots(p, d, at(9), at(12)) == [
        (at(9), at(9, 30)), (at(9, 15), at(9, 45)), (at(10, 45), at(11, 15)),
        (at(11), at(11, 30)), (at(11, 15), at(11, 45)), (at(11, 30), at(12)),
    ]
    service.client.fetch_busy_intervals.assert_called_once_with('D1', at(8, 45), at(12, 15))
    with pytest.raises(ValueError, match='Requested slot'):
        service.book('A1', p, d, requested)
    assert service.manager.appointments == {}


@pytest.mark.parametrize('strategy, preference, expected', [
    (EarliestAvailableStrategy(), at(11), (at(9), at(9, 30))),
    (ClosestToRequestedStrategy(), at(11), (at(11), at(11, 30))),
    (ClosestToRequestedStrategy(), at(9, 7), (at(9), at(9, 30))),
])
def test_both_strategies_are_used_through_constructor_injection(service, strategy, preference, expected):
    injected = AppointmentService(service.manager, service.client, strategy, service.working_hours)
    p, d = participants(service)
    assert injected.suggest_slot(p, d, at(9), at(12), preference) == expected
    assert service.manager.appointments == {}


def test_calculation_using_snapshot_is_read_only_and_has_no_calendar_call(service):
    p, d = participants(service)
    existing = seed(service, start=at(10))
    before = vars(existing).copy()
    supplied = snapshot()
    slots = service.available_slots_using_snapshot(p, d, at(9), at(12), supplied)
    assert (at(9, 30), at(10)) not in slots
    assert (at(10, 45), at(11, 15)) in slots
    assert service.manager.appointments == {'ORIGINAL': existing}
    assert vars(existing) == before and supplied.busy_intervals == ()
    service.client.fetch_busy_intervals.assert_not_called()


def test_booking_fetches_once_and_never_invokes_selection_strategy(service):
    p, d = participants(service)
    service.strategy.select = Mock(side_effect=AssertionError('Explicit booking must not select another slot'))
    booked = service.book('A1', p, d, at(9, 15), 45)
    assert (booked.scheduled_at, booked.end_at) == (at(9, 15), at(10))
    assert service.manager.find_appointment('A1') is booked
    service.client.fetch_busy_intervals.assert_called_once_with('D1', at(9), at(10, 15))
    service.strategy.select.assert_not_called()


def test_snapshot_local_recheck_detects_booking_inserted_after_read(service):
    supplied = snapshot()
    other = seed(service, identifier='OTHER', patient='P2')
    p, d = participants(service)
    with pytest.raises(ValueError, match='Requested slot'):
        service.book_using_snapshot('A1', p, d, at(9), supplied)
    assert service.manager.appointments == {'OTHER': other}
    service.client.fetch_busy_intervals.assert_not_called()


@pytest.mark.parametrize('change', ['duplicate-id', 'replaced-patient'])
def test_book_rechecks_identifiers_and_membership_after_calendar_read(service, change):
    p, d = participants(service)
    def read(doctor_id, start, end):
        complete = CalendarSnapshot(doctor_id, start, end, [], 'simulated')
        if change == 'duplicate-id':
            seed(service, identifier='A1', patient='P2', doctor='D2', start=at(11))
        else:
            service.manager.patients['P1'] = Patient('P1', 'Different registered object')
        return complete
    service.client.fetch_busy_intervals.side_effect = read
    with pytest.raises(ValueError, match='already exists|registered'):
        service.book('A1', p, d, at(9))
    assert len(service.manager.appointments) == (1 if change == 'duplicate-id' else 0)
    if change == 'duplicate-id':
        assert service.manager.find_appointment('A1').patient.id == 'P2'


@pytest.mark.parametrize('resource', ['doctor', 'patient'])
@pytest.mark.parametrize('direction', ['before', 'after'])
@pytest.mark.parametrize('gap, allowed', [(14, False), (15, True), (16, True)])
def test_service_checks_doctor_patient_gap_boundary_in_both_directions(service, resource, direction, gap, allowed):
    # Only the requested slot uses the new grid; existing local history may be off-grid.
    if direction == 'before':
        requested, existing_start = at(9, 30), at(10) + timedelta(minutes=gap)
    else:
        requested = at(10, 45)
        existing_start = at(10, 15) - timedelta(minutes=gap)
    other = seed(service, identifier='OTHER', start=existing_start,
                 patient='P2' if resource == 'doctor' else 'P1',
                 doctor='D1' if resource == 'doctor' else 'D2')
    p, d = participants(service)
    if allowed:
        assert service.book_using_snapshot('A1', p, d, requested, snapshot()).scheduled_at == requested
    else:
        with pytest.raises(ValueError):
            service.book_using_snapshot('A1', p, d, requested, snapshot())
        assert service.manager.appointments == {'OTHER': other}
    service.client.fetch_busy_intervals.assert_not_called()


@pytest.mark.parametrize('start, duration', [(at(8, 45), 30), (at(11, 45), 30), (at(9, 7), 30)])
def test_explicit_booking_respects_working_hours_and_grid_without_moving(service, start, duration):
    p, d = participants(service)
    with pytest.raises(ValueError, match='Requested slot'):
        service.book_using_snapshot('A1', p, d, start, snapshot(), duration)
    assert service.manager.appointments == {}


@pytest.mark.parametrize('kind', ['wrong-doctor', 'short-start', 'short-end', 'none', 'invalid-busy'])
def test_bad_snapshot_means_unknown_without_mutation(service, kind):
    supplied = snapshot()
    if kind == 'wrong-doctor':
        supplied.doctor_id = 'D2'
    elif kind == 'short-start':
        supplied.window_start = at(8, 46)
    elif kind == 'short-end':
        supplied.window_end = at(12, 14)
    elif kind == 'none':
        supplied = None
    else:
        supplied.busy_intervals = [(at(10), at(9))]
    p, d = participants(service)
    with pytest.raises(AvailabilityUnknownError):
        service.available_slots_using_snapshot(p, d, at(9), at(12), supplied)
    assert service.manager.appointments == {}
    service.client.fetch_busy_intervals.assert_not_called()


def test_booking_requires_coverage_for_the_requested_slot_and_its_gaps(service):
    p, d = participants(service)
    with pytest.raises(AvailabilityUnknownError):
        service.book_using_snapshot('A1', p, d, at(9), snapshot(start=at(9), end=at(9, 30)))
    assert service.manager.appointments == {}


def test_booking_wrong_doctor_snapshot_cannot_mutate_clinic(service):
    p, d = participants(service)
    with pytest.raises(AvailabilityUnknownError):
        service.book_using_snapshot('A1', p, d, at(9), snapshot(doctor='D2'))
    assert service.manager.appointments == {}
    service.client.fetch_busy_intervals.assert_not_called()


@pytest.mark.parametrize('outsider', ['patient-alias', 'doctor-alias', 'patient-unregistered', 'doctor-unregistered'])
def test_exact_membership_is_required_for_booking_and_enqueue_before_io(service, outsider):
    p, d = participants(service)
    if outsider.startswith('patient'):
        p = Patient('P1' if outsider.endswith('alias') else 'PX', 'Outsider')
    else:
        d = Doctor('D1' if outsider.endswith('alias') else 'DX', 'Outsider', 'General')
    with pytest.raises(ValueError, match='registered'):
        service.book('A1', p, d, at(9))
    with pytest.raises(ValueError, match='registered'):
        service.add_waiting_request(WaitingRequest('R1', p, d, at(9), at(12)))
    assert service.manager.appointments == {} and service.waiting_requests('D1') == ()
    service.client.fetch_busy_intervals.assert_not_called()


def test_duplicate_appointment_id_is_rejected_without_overwrite_or_io(service):
    original = seed(service, identifier='A1')
    p, d = participants(service)
    with pytest.raises(ValueError, match='already exists'):
        service.book(' A1 ', p, d, at(11))
    assert service.manager.appointments == {'A1': original}
    service.client.fetch_busy_intervals.assert_not_called()


def test_duplicate_pending_request_id_across_doctors_is_rejected_without_io(service):
    first = enqueue(service, 'R1')
    with pytest.raises(ValueError, match='already pending'):
        enqueue(service, ' R1 ', doctor='D2')
    assert service.waiting_requests('D1') == (first,)
    assert service.waiting_requests('D2') == ()
    service.client.fetch_busy_intervals.assert_not_called()


@pytest.mark.parametrize('status', ['in_progress', 'completed', 'cancelled', 'no_show', None])
def test_invalid_cancellation_does_not_read_calendar_or_mutate(service, status):
    appointment = None if status is None else seed(service, status=status)
    queued = enqueue(service, 'R1')
    with pytest.raises(ValueError, match='scheduled'):
        service.cancel('MISSING' if status is None else 'ORIGINAL')
    if appointment:
        assert appointment.status == status
    assert service.waiting_requests('D1') == (queued,)
    service.client.fetch_busy_intervals.assert_not_called()


def test_invalid_local_cancellation_time_is_rejected_before_mutation(service):
    original = seed(service, start=at(9).replace(tzinfo=timezone.utc))
    with pytest.raises(ValueError, match='naive clinic-local'):
        service.cancel('ORIGINAL')
    assert original.status == 'scheduled'
    service.client.fetch_busy_intervals.assert_not_called()


def test_fifo_backfill_skips_without_rotating_queues_or_reusing_ids(service):
    original = seed(service, duration=60)
    collision = seed(service, identifier='BACKFILL-1', start=at(8), status='completed')
    first = enqueue(service, 'R1', duration=90)
    second = enqueue(service, 'R2', patient='P3', start=at(9, 15))
    selected = enqueue(service, 'R3', end=at(9, 30))
    fourth = enqueue(service, 'R4', patient='P3')
    other_doctor = enqueue(service, 'R5', doctor='D2')
    result = service.cancel('ORIGINAL')
    replacement = result['replacement']
    assert result['backfill_status'] == 'filled' and result['cancelled_appointment'] is original
    assert original.status == 'cancelled' and original.duration_minutes == 60
    assert replacement.patient is selected.patient and replacement.scheduled_at == at(9)
    assert replacement.end_at == at(9, 30) and replacement.status == 'scheduled'
    assert replacement.appointment_id not in ('ORIGINAL', 'BACKFILL-1')
    assert service.manager.find_appointment('BACKFILL-1') is collision
    assert len(service.manager.appointments) == 3
    assert service.waiting_requests('D1') == (first, second, fourth)
    assert service.waiting_requests('D2') == (other_doctor,)
    service.client.fetch_busy_intervals.assert_called_once_with('D1', at(8, 45), at(10, 15))


def test_temporarily_conflicting_patient_keeps_fifo_position_for_later_backfill(service):
    seed(service)
    seed(service, identifier='PATIENT_BUSY', patient='P2', doctor='D2')
    first = enqueue(service, 'R1', patient='P2')
    second = enqueue(service, 'R2', patient='P3')
    third = enqueue(service, 'R3', patient='P2')
    replacement = service.cancel('ORIGINAL')['replacement']
    assert replacement.patient is second.patient
    assert service.waiting_requests('D1') == (first, third)
    service.cancel('PATIENT_BUSY')
    next_result = service.cancel(replacement.appointment_id)
    assert next_result['replacement'].patient is first.patient
    assert service.waiting_requests('D1') == (third,)


def test_backfill_rechecks_exact_waiting_patient_membership(service):
    seed(service)
    stale = enqueue(service, 'R1', patient='P2')
    eligible = enqueue(service, 'R2', patient='P3')
    service.manager.patients['P2'] = Patient('P2', 'Replacement object')
    result = service.cancel('ORIGINAL')
    assert result['replacement'].patient is eligible.patient
    assert service.waiting_requests('D1') == (stale,)


@pytest.mark.parametrize('duration, start, end, expected', [
    (45, at(9), at(12), 'unfilled'), (30, at(9, 15), at(12), 'unfilled'),
    (30, at(8, 30), at(9, 15), 'unfilled'), (15, at(9), at(9, 15), 'filled'),
    (30, at(9), at(9, 30), 'filled'),
])
def test_replacement_must_fit_freed_interval_and_acceptable_window(service, duration, start, end, expected):
    original = seed(service)
    request = enqueue(service, 'R1', start=start, end=end, duration=duration)
    result = service.cancel('ORIGINAL')
    assert result['backfill_status'] == expected and original.status == 'cancelled'
    assert len(service.manager.appointments) == (2 if expected == 'filled' else 1)
    assert service.waiting_requests('D1') == (() if expected == 'filled' else (request,))
    if result['replacement']:
        assert result['replacement'].scheduled_at == original.scheduled_at
        assert result['replacement'].duration_minutes == duration


@pytest.mark.parametrize('constraint', ['external', 'working-hours', 'grid'])
def test_backfill_cannot_bypass_other_availability_constraints(service, constraint):
    original = seed(service, start=at(9, 7) if constraint == 'grid' else at(9))
    request = enqueue(service, 'R1')
    if constraint == 'external':
        service.client.fetch_busy_intervals.side_effect = lambda doc, start, end: CalendarSnapshot(
            doc, start, end, [(at(9), at(9, 30))], 'simulated'
        )
    elif constraint == 'working-hours':
        service.working_hours['D1'] = [(at(10), at(12))]
    result = service.cancel('ORIGINAL')
    assert result['backfill_status'] == 'unfilled' and result['replacement'] is None
    assert original.status == 'cancelled' and service.waiting_requests('D1') == (request,)


@pytest.mark.parametrize('failure', [CalendarReadError('communication'), CalendarReadError('http', 403),
                                   CalendarReadError('json'), CalendarReadError('validation'),
                                   ValueError('broken synthetic JSON'), RuntimeError('calendar read failed')])
def test_read_failure_prevents_booking_but_allows_cancellation_with_deferred_queue(service, failure):
    original = seed(service)
    request = enqueue(service, 'R1')
    service.client.fetch_busy_intervals.side_effect = failure
    p, d = participants(service, 'P3')
    with pytest.raises(AvailabilityUnknownError, match='unknown'):
        service.book('A1', p, d, at(11))
    assert list(service.manager.appointments) == ['ORIGINAL']
    result = service.cancel('ORIGINAL')
    assert result['backfill_status'] == 'deferred' and result['replacement'] is None
    assert original.status == 'cancelled' and service.waiting_requests('D1') == (request,)
    with pytest.raises(ValueError):
        original.update_status('scheduled')


def test_invalid_snapshot_defers_backfill_and_preserves_queue(service):
    original = seed(service)
    request = enqueue(service, 'R1')
    service.client.fetch_busy_intervals.side_effect = None
    service.client.fetch_busy_intervals.return_value = snapshot(doctor='D2')
    result = service.cancel('ORIGINAL')
    assert result['backfill_status'] == 'deferred' and original.status == 'cancelled'
    assert service.waiting_requests('D1') == (request,)


def test_request_removed_only_after_successful_registration(service):
    original = seed(service)
    first, second = enqueue(service, 'R1'), enqueue(service, 'R2', patient='P3')
    with patch.object(service.manager, 'schedule_appointment', side_effect=ValueError('Registration rejected')):
        result = service.cancel('ORIGINAL')
    assert result['backfill_status'] == 'unfilled' and original.status == 'cancelled'
    assert service.waiting_requests('D1') == (first, second)
    assert service.manager.appointments == {'ORIGINAL': original}


def test_no_pending_requests_needs_no_calendar_read(service):
    original = seed(service)
    result = service.cancel('ORIGINAL')
    assert result == {'cancelled_appointment': original, 'replacement': None, 'backfill_status': 'unfilled'}
    assert original.status == 'cancelled'
    service.client.fetch_busy_intervals.assert_not_called()


def test_real_json_file_failure_leaves_booking_absent_and_cancellation_deferred(service, tmp_path):
    path = tmp_path / 'broken-calendar.json'
    path.write_text('{not valid JSON', encoding='utf-8')
    service.client = JsonCalendarClient(path)
    original = seed(service)
    waiting = enqueue(service, 'R1')
    p, d = participants(service, 'P3')
    with pytest.raises(AvailabilityUnknownError):
        service.book('A1', p, d, at(11))
    result = service.cancel('ORIGINAL')
    assert result['backfill_status'] == 'deferred' and result['replacement'] is None
    assert service.manager.appointments == {'ORIGINAL': original}
    assert original.status == 'cancelled' and service.waiting_requests('D1') == (waiting,)


def test_complete_offline_flow_uses_real_json_and_preserved_source_data():
    root = Path(__file__).resolve().parents[1]
    manager = load_clinic_data(root / 'data/sample_data.jsonl')
    client = JsonCalendarClient(root / 'data/calendar_responses.json')
    service = AppointmentService(manager, client, ClosestToRequestedStrategy(),
                                 {'D001': [(at(9), at(12))]})
    p, d = manager.find_patient('P001'), manager.find_doctor('D001')
    assert service.suggest_slot(p, d, at(9), at(12), at(10)) == (at(9, 15), at(9, 45))
    original = service.book('OFFLINE-1', p, d, at(9, 15))
    request = WaitingRequest('OFFLINE-R1', manager.find_patient('P002'), d, at(9), at(12))
    service.add_waiting_request(request)
    result = service.cancel('OFFLINE-1')
    assert result['backfill_status'] == 'filled' and original.status == 'cancelled'
    assert result['replacement'].patient is request.patient
    assert result['replacement'].scheduled_at == at(9, 15)
    assert service.waiting_requests('D001') == ()
    assert len(manager.appointments) == 9  # Seven source records plus cancelled original and replacement.
    assert service.fetch_snapshot(p, d, at(9), at(12)).source == 'simulated'
