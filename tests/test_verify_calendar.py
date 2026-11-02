from unittest.mock import Mock, patch

import requests

from smart_clinic import verify_calendar
from smart_clinic.api_client import CalendarReadError


ARGS = ['--doctor-id', 'D1', '--start', '2026-10-29T09:00:00', '--end', '2026-10-29T12:00:00']


def test_verification_command_reports_busy_decision_with_mocked_http(capsys):
    config = {'api_key': 'FAKE_COMMAND_KEY', 'doctor_calendars': {'D1': 'synthetic@example.test'}}
    reply = Mock(spec=requests.Response)
    reply.status_code = 200
    reply.json.return_value = {
        'kind': 'calendar#events', 'timeZone': 'Asia/Jerusalem', 'items': [{
            'start': {'dateTime': '2026-10-29T10:00:00+02:00'},
            'end': {'dateTime': '2026-10-29T10:30:00+02:00'},
        }],
    }
    with patch('smart_clinic.verify_calendar.load_config', return_value=config), patch(
        'smart_clinic.api_client.requests.get', return_value=reply
    ) as get:
        assert verify_calendar.main(ARGS) == 0
    assert get.call_count == 1
    output = capsys.readouterr().out
    assert 'source=live' in output  # Mocked command test, not real-provider evidence.
    assert 'busy_intervals=' in output and 'blocked_slots=[' in output
    assert 'datetime.datetime(2026, 10, 29, 9, 30)' in output
    assert config['api_key'] not in output


def test_missing_configuration_does_not_request_or_dump_traceback(capsys):
    with patch('smart_clinic.verify_calendar.load_config', side_effect=ValueError('Live mode requires GOOGLE_CALENDAR_API_KEY.')):
        with patch('smart_clinic.api_client.requests.get') as get:
            assert verify_calendar.main(ARGS) == 1
    get.assert_not_called()
    output = capsys.readouterr().out
    assert 'requires GOOGLE_CALENDAR_API_KEY' in output and 'Traceback' not in output


def test_failed_read_prints_safe_category_without_booking(capsys):
    client = Mock()
    client.fetch_busy_intervals.side_effect = CalendarReadError('http', 403)
    with patch('smart_clinic.verify_calendar.load_config', return_value={}), patch(
        'smart_clinic.verify_calendar.create_calendar_client', return_value=client
    ):
        assert verify_calendar.main(ARGS) == 1
    assert capsys.readouterr().out.strip() == 'Calendar read failed: http (HTTP 403).'
