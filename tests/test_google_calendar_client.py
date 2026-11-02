import logging
import traceback
from datetime import datetime
from unittest.mock import Mock, call, patch

import pytest
import requests

from smart_clinic.api_client import CalendarReadError, GoogleCalendarClient
from smart_clinic.scheduling import calculate_available_slots


FAKE_KEY = "FAKE_KEY_FOR_MOCKED_TESTS_ONLY"
FAKE_CALENDAR = "synthetic /+@example.test"
SECRET_URL = "https://www.googleapis.com/calendar/v3/calendars/test/events?key=" + FAKE_KEY


def at(hour, minute=0):
    return datetime(2026, 10, 29, hour, minute)


def page(items=(), **extra):
    return {"kind": "calendar#events", "timeZone": "Asia/Jerusalem", "etag": "test-etag",
            "items": list(items), **extra}


def busy_event():
    return {"start": {"dateTime": "2026-10-29T08:00:00Z"},
            "end": {"dateTime": "2026-10-29T08:30:00Z"}}


def response(payload=None, status=200):
    result = Mock(spec=requests.Response)
    result.status_code = status
    result.json.return_value = page() if payload is None else payload
    if status >= 400:
        result.raise_for_status.side_effect = requests.HTTPError(SECRET_URL)
    return result


@pytest.fixture
def http():
    with patch("smart_clinic.api_client.requests.get") as get, patch("smart_clinic.api_client.time.sleep") as sleep:
        get.return_value = response()
        yield get, sleep


@pytest.fixture
def client():
    return GoogleCalendarClient(FAKE_KEY, {"D1": FAKE_CALENDAR}, timeout=4)


def test_success_exact_parameters_coverage_and_pure_availability(client, http):
    get, sleep = http
    reply = response(page([busy_event()]))
    get.return_value = reply
    snapshot = client.fetch_busy_intervals("D1", at(8, 45), at(12, 15))
    get.assert_called_once_with(
        "https://www.googleapis.com/calendar/v3/calendars/synthetic%20%2F%2B%40example.test/events",
        params={"key": FAKE_KEY, "timeMin": "2026-10-29T08:45:00+02:00",
                "timeMax": "2026-10-29T12:15:00+02:00", "timeZone": "Asia/Jerusalem",
                "singleEvents": True, "showDeleted": False, "orderBy": "startTime"},
        timeout=4, allow_redirects=False,
    )
    assert (snapshot.doctor_id, snapshot.window_start, snapshot.window_end) == ("D1", at(8, 45), at(12, 15))
    assert snapshot.source == "live"  # Exercises the Google product contract with mocked HTTP only.
    assert snapshot.busy_intervals == ((at(10), at(10, 30)),)
    available = calculate_available_slots("D1", "P1", [(at(9), at(12))], at(9), at(12), snapshot)
    assert (at(9, 30), at(10)) not in available
    assert (at(10), at(10, 30)) not in available
    assert (at(9, 15), at(9, 45)) in available
    assert (at(10, 45), at(11, 15)) in available
    reply.close.assert_called_once()
    sleep.assert_not_called()


@pytest.mark.parametrize("error_type", [requests.Timeout, requests.ConnectionError])
def test_retry_recovers_and_waits_between_attempts(client, http, error_type):
    get, sleep = http
    get.side_effect = [error_type(SECRET_URL), error_type(SECRET_URL), response()]
    assert client.fetch_busy_intervals("D1", at(9), at(12)).busy_intervals == ()
    assert get.call_count == 3
    assert sleep.call_args_list == [call(1), call(1)]


@pytest.mark.parametrize("error_type, reason", [(requests.Timeout, "timeout"), (requests.ConnectionError, "connection")])
def test_retry_stops_at_exactly_three_and_sanitizes(client, http, caplog, error_type, reason):
    get, sleep = http
    get.side_effect = error_type(SECRET_URL)
    with caplog.at_level(logging.DEBUG), pytest.raises(CalendarReadError) as caught:
        client.fetch_busy_intervals("D1", at(9), at(12))
    assert (caught.value.category, caught.value.reason) == ("communication", reason)
    assert get.call_count == 3
    assert sleep.call_args_list == [call(1), call(1)]
    exposed = str(caught.value) + repr(caught.value) + "".join(traceback.format_exception(caught.value)) + caplog.text
    assert FAKE_KEY not in exposed and SECRET_URL not in exposed


@pytest.mark.parametrize("status", [400, 401, 403, 404, 429, 500, 503, 302])
def test_http_failures_are_not_retried_or_decoded(client, http, caplog, status):
    get, sleep = http
    reply = response(status=status)
    get.return_value = reply
    with pytest.raises(CalendarReadError) as caught:
        client.fetch_busy_intervals("D1", at(9), at(12))
    assert (caught.value.category, caught.value.http_status) == ("http", status)
    assert get.call_count == 1
    reply.json.assert_not_called()
    reply.close.assert_called_once()
    sleep.assert_not_called()
    assert FAKE_KEY not in str(caught.value) + caplog.text + "".join(traceback.format_exception(caught.value))


def test_status_is_checked_before_json(client, http):
    get, _ = http
    reply = response()
    calls = Mock()
    calls.attach_mock(reply.raise_for_status, "status")
    calls.attach_mock(reply.json, "json")
    get.return_value = reply
    client.fetch_busy_intervals("D1", at(9), at(12))
    assert calls.mock_calls == [call.status(), call.json()]


def test_other_request_errors_are_sanitized_without_retry(client, http, caplog):
    get, sleep = http
    get.side_effect = requests.exceptions.RequestException(SECRET_URL)
    with pytest.raises(CalendarReadError) as caught:
        client.fetch_busy_intervals("D1", at(9), at(12))
    assert (caught.value.category, caught.value.reason) == ("communication", "request")
    assert get.call_count == 1
    sleep.assert_not_called()
    assert FAKE_KEY not in caplog.text + "".join(traceback.format_exception(caught.value))


def test_close_error_cannot_expose_a_raw_request_exception(client, http, caplog):
    get, sleep = http
    reply = response()
    reply.close.side_effect = requests.ConnectionError(SECRET_URL)
    get.return_value = reply
    with pytest.raises(CalendarReadError) as caught:
        client.fetch_busy_intervals("D1", at(9), at(12))
    assert caught.value.category == 'communication'
    assert get.call_count == 1
    sleep.assert_not_called()
    assert FAKE_KEY not in caplog.text + ''.join(traceback.format_exception(caught.value))


def test_fractional_query_precision_still_covers_the_exact_window(client, http):
    get, _ = http
    start = at(9).replace(microsecond=500000)
    end = at(12).replace(microsecond=500000)
    edge = {'start': {'dateTime': '2026-10-29T12:00:00.250000+02:00'},
            'end': {'dateTime': '2026-10-29T12:30:00+02:00'}}
    outside = {'start': {'dateTime': '2026-10-29T12:00:00.750000+02:00'},
               'end': {'dateTime': '2026-10-29T12:30:00+02:00'}}
    get.return_value = response(page([edge, outside]))
    snapshot = client.fetch_busy_intervals('D1', start, end)
    assert get.call_args.kwargs['params']['timeMin'] == '2026-10-29T09:00:00+02:00'
    assert get.call_args.kwargs['params']['timeMax'] == '2026-10-29T12:00:01+02:00'
    assert (snapshot.window_start, snapshot.window_end) == (start, end)
    assert snapshot.busy_intervals == ((at(12).replace(microsecond=250000), at(12, 30)),)


def test_bad_json_is_distinct_and_not_retried(client, http, caplog):
    get, sleep = http
    reply = response()
    reply.json.side_effect = requests.exceptions.JSONDecodeError(SECRET_URL, "bad", 0)
    get.return_value = reply
    with pytest.raises(CalendarReadError) as caught:
        client.fetch_busy_intervals("D1", at(9), at(12))
    assert caught.value.category == "json"
    assert get.call_count == 1
    sleep.assert_not_called()
    assert FAKE_KEY not in str(caught.value) + caplog.text + "".join(traceback.format_exception(caught.value))


@pytest.mark.parametrize(
    "payload",
    [[], {}, {"error": {"message": SECRET_URL}},
     page([{"start": {"dateTime": "2026-10-29T10:00:00Z"}}]),
     {"kind": "calendar#events", "timeZone": "Asia/Jerusalem", "items": None},
     {"kind": "calendar#events", "timeZone": "Asia/Jerusalem"},
     {"kind": "calendar#events", "timeZone": "Invalid/Zone", "etag": "test"},
     {"kind": "wrong", "timeZone": "Asia/Jerusalem", "etag": "test"}],
)
def test_validation_failure_never_becomes_empty_or_retried(client, http, caplog, payload):
    get, sleep = http
    get.return_value = response(payload)
    with pytest.raises(CalendarReadError) as caught:
        client.fetch_busy_intervals("D1", at(9), at(12))
    assert caught.value.category == "validation"
    assert get.call_count == 1
    sleep.assert_not_called()
    assert FAKE_KEY not in str(caught.value) + caplog.text


def test_omitted_items_adapted_only_in_recognized_empty_google_response(client, http):
    get, _ = http
    data = {"kind": "calendar#events", "timeZone": "Asia/Jerusalem", "etag": "empty-etag"}
    get.return_value = response(data)
    assert client.fetch_busy_intervals("D1", at(9), at(12)).busy_intervals == ()
    assert "items" not in data  # Adapter does not mutate the HTTP payload.


def test_every_page_is_collected_with_independent_retry(client, http):
    get, sleep = http
    late = {"start": {"dateTime": "2026-10-29T11:00:00+02:00"},
            "end": {"dateTime": "2026-10-29T11:30:00+02:00"}}
    get.side_effect = [requests.Timeout(SECRET_URL), response(page([late], nextPageToken="p2")),
                       requests.ConnectionError(SECRET_URL), response(page([busy_event()]))]
    snapshot = client.fetch_busy_intervals("D1", at(8, 45), at(12, 15))
    assert snapshot.busy_intervals == ((at(10), at(10, 30)), (at(11), at(11, 30)))
    assert get.call_count == 4
    assert [c.kwargs["params"].get("pageToken") for c in get.call_args_list] == [None, None, "p2", "p2"]
    assert sleep.call_args_list == [call(1), call(1)]


def test_empty_intermediate_page_does_not_stop_pagination(client, http):
    get, _ = http
    get.side_effect = [response({"kind": "calendar#events", "timeZone": "Asia/Jerusalem",
                                "etag": "test", "nextPageToken": "p2"}), response(page([busy_event()]))]
    assert client.fetch_busy_intervals("D1", at(9), at(12)).busy_intervals == ((at(10), at(10, 30)),)
    assert get.call_count == 2


@pytest.mark.parametrize("token", [None, "", " ", 12, [], {}])
def test_malformed_page_tokens_are_rejected(client, http, token):
    get, sleep = http
    get.return_value = response(page(nextPageToken=token))
    with pytest.raises(CalendarReadError, match="validation"):
        client.fetch_busy_intervals("D1", at(9), at(12))
    assert get.call_count == 1
    sleep.assert_not_called()


def test_repeated_page_token_is_rejected(client, http):
    get, _ = http
    get.side_effect = [response(page(nextPageToken="p2")), response(page(nextPageToken="p2"))]
    with pytest.raises(CalendarReadError, match="validation"):
        client.fetch_busy_intervals("D1", at(9), at(12))
    assert get.call_count == 2


@pytest.mark.parametrize("metadata", [
    {"nextPageToken": "p2", "nextSyncToken": "sync"}, {"nextSyncToken": None},
    {"accessRole": "none"}, {"accessRole": "freeBusyReader"},
])
def test_unusable_page_metadata_is_rejected(client, http, metadata):
    get, sleep = http
    get.return_value = response(page(**metadata))
    with pytest.raises(CalendarReadError, match="validation"):
        client.fetch_busy_intervals("D1", at(9), at(12))
    assert get.call_count == 1
    sleep.assert_not_called()


@pytest.mark.parametrize("second", [requests.Timeout(SECRET_URL), "http", "json", "validation"])
def test_later_page_failure_never_returns_partial_snapshot(client, http, second):
    get, sleep = http
    first = response(page([busy_event()], nextPageToken="p2"))
    if isinstance(second, Exception):
        get.side_effect = [first, second, second, second]
        expected_category, expected_calls = "communication", 4
    else:
        bad = response(status=403) if second == "http" else response(page([{}]))
        if second == "json":
            bad.json.side_effect = ValueError(SECRET_URL)
        get.side_effect = [first, bad]
        expected_category, expected_calls = second, 2
    with pytest.raises(CalendarReadError) as caught:
        client.fetch_busy_intervals("D1", at(9), at(12))
    assert caught.value.category == expected_category
    assert get.call_count == expected_calls
    assert sleep.call_count == (2 if expected_calls == 4 else 0)


def test_normalization_preserves_endpoints_and_ignores_nonblocking_events(client, http):
    get, _ = http
    data = page([{"status": "cancelled"}, {"transparency": "transparent"},
                 {"start": {"date": "2026-10-29"}, "end": {"date": "2026-10-30"}}])
    get.return_value = response(data)
    snapshot = client.fetch_busy_intervals("D1", at(8, 45), at(12, 15))
    assert snapshot.busy_intervals == ((datetime(2026, 10, 29), datetime(2026, 10, 30)),)


@pytest.mark.parametrize("doctor_id, start, end", [("missing", at(9), at(12)), ("D1", at(12), at(9))])
def test_bad_request_fails_before_http(client, http, doctor_id, start, end):
    get, sleep = http
    with pytest.raises(CalendarReadError, match="validation"):
        client.fetch_busy_intervals(doctor_id, start, end)
    get.assert_not_called()
    sleep.assert_not_called()
