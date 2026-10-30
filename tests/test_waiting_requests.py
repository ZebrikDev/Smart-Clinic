from datetime import datetime, timezone

import pytest

from smart_clinic.models import Doctor, Patient, WaitingRequest


@pytest.fixture
def fields():
    return {'request_id': 'R1', 'patient': Patient('P1', 'Patient'),
            'doctor': Doctor('D1', 'Doctor', 'General'),
            'window_start': datetime(2026, 10, 29, 9), 'window_end': datetime(2026, 10, 29, 12)}


@pytest.mark.parametrize('duration', [True, False, 0, -1, 1.5, '30', None])
def test_invalid_waiting_duration(fields, duration):
    with pytest.raises(ValueError, match='duration_minutes'):
        WaitingRequest(**fields, duration_minutes=duration)


@pytest.mark.parametrize('field, value', [
    ('request_id', ''), ('request_id', None), ('window_end', datetime(2026, 10, 29, 8)),
    ('window_start', datetime(2026, 10, 29, 9, tzinfo=timezone.utc)),
])
def test_invalid_waiting_request_fields(fields, field, value):
    fields[field] = value
    with pytest.raises(ValueError):
        WaitingRequest(**fields)


def test_waiting_duration_must_fit_acceptable_window(fields):
    fields['window_end'] = datetime(2026, 10, 29, 9, 15)
    with pytest.raises(ValueError, match='fit within'):
        WaitingRequest(**fields)


@pytest.mark.parametrize('field', ['request_id', 'patient', 'doctor', 'window_start', 'window_end', 'duration_minutes'])
def test_queued_contract_fields_are_read_only(fields, field):
    request = WaitingRequest(**fields)
    with pytest.raises(AttributeError):
        setattr(request, field, None)
    assert request.request_id == 'R1' and request.duration_minutes == 30


def test_waiting_request_retains_objects_and_normalized_id(fields):
    fields['request_id'] = ' R1 '
    request = WaitingRequest(**fields, duration_minutes=45)
    assert request.request_id == 'R1' and request.duration_minutes == 45
    assert request.patient is fields['patient'] and request.doctor is fields['doctor']
    assert 'R1' in repr(request) and 'duration_minutes=45' in repr(request)
