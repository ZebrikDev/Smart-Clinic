import json
import os
import traceback
from unittest.mock import patch

import pytest

from smart_clinic.api_client import CalendarClient, GoogleCalendarClient, JsonCalendarClient
from smart_clinic.config import load_config
from smart_clinic.factories import create_calendar_client


FAKE_KEY = "FAKE_CONFIGURATION_KEY"


@pytest.fixture
def clean_environment(monkeypatch, tmp_path):
    # Also isolate values inserted directly by load_dotenv, not only monkeypatch.
    monkeypatch.setattr(os, "environ", {})
    return tmp_path / ".env"


def test_offline_config_does_not_read_environment_file(clean_environment):
    with patch("smart_clinic.config.load_dotenv") as load:
        config = load_config("offline", env_file=clean_environment)
    load.assert_not_called()
    assert isinstance(create_calendar_client("offline", config), JsonCalendarClient)
    assert "api_key" not in config


def test_live_env_loading_is_explicit_and_does_not_override_process_values(clean_environment, monkeypatch):
    clean_environment.write_text(
        'GOOGLE_CALENDAR_API_KEY=unused-file-key\n'
        'GOOGLE_CALENDAR_MAPPING={"D1":"synthetic@example.test"}\nREQUEST_TIMEOUT=3.5\n'
    )
    monkeypatch.setenv("GOOGLE_CALENDAR_API_KEY", FAKE_KEY)
    config = load_config("live", env_file=clean_environment)
    assert config == {"api_key": FAKE_KEY, "doctor_calendars": {"D1": "synthetic@example.test"}, "timeout": 3.5}


@pytest.mark.parametrize(
    "key, mapping, timeout",
    [(None, '{}', '10'), ('', '{}', '10'), (FAKE_KEY, '{}', '10'),
     (FAKE_KEY, '[]', '10'), (FAKE_KEY, '{bad', '10'),
     (FAKE_KEY, '{"D1":""}', '10'), (FAKE_KEY, '{"D1":"primary"}', '10'),
     (FAKE_KEY, '{"D1":"synthetic@example.test"}', '0'),
     (FAKE_KEY, '{"D1":"synthetic@example.test"}', '-1'),
     (FAKE_KEY, '{"D1":"synthetic@example.test"}', 'nan'),
     (FAKE_KEY, '{"D1":"synthetic@example.test"}', 'inf'),
     (FAKE_KEY, '{"D1":"synthetic@example.test"}', FAKE_KEY)],
)
def test_invalid_live_config_has_safe_errors_before_http(
    clean_environment, monkeypatch, key, mapping, timeout, caplog
):
    if key is not None:
        monkeypatch.setenv("GOOGLE_CALENDAR_API_KEY", key)
    monkeypatch.setenv("GOOGLE_CALENDAR_MAPPING", mapping)
    monkeypatch.setenv("REQUEST_TIMEOUT", timeout)
    with patch("smart_clinic.api_client.requests.get") as get:
        with pytest.raises(ValueError) as caught:
            load_config("live", env_file=clean_environment)
    get.assert_not_called()
    assert FAKE_KEY not in str(caught.value) + caplog.text + "".join(traceback.format_exception(caught.value))


def test_offline_ignores_invalid_live_configuration(clean_environment, monkeypatch):
    monkeypatch.setenv("GOOGLE_CALENDAR_API_KEY", FAKE_KEY)
    monkeypatch.setenv("GOOGLE_CALENDAR_MAPPING", "bad")
    monkeypatch.setenv("REQUEST_TIMEOUT", "nan")
    assert "json_path" in load_config("offline")


def test_factory_has_two_real_contract_products_and_no_io(tmp_path):
    with patch("smart_clinic.api_client.requests.get") as get, patch("pathlib.Path.open") as opened:
        offline = create_calendar_client("offline", {"json_path": tmp_path / "future.json"})
        live = create_calendar_client("live", {"api_key": FAKE_KEY, "doctor_calendars": {"D1": "synthetic@example.test"}})
    assert isinstance(offline, CalendarClient) and isinstance(offline, JsonCalendarClient)
    assert isinstance(live, CalendarClient) and isinstance(live, GoogleCalendarClient)
    get.assert_not_called()
    opened.assert_not_called()


@pytest.mark.parametrize("mode, config", [("unknown", {}), (None, {}), ("live", None),
                                         ("offline", {}), ("offline", {"json_path": ""}),
                                         ("offline", {"json_path": 1}), ("live", {})])
def test_factory_rejects_bad_mode_and_config(mode, config):
    with pytest.raises(ValueError):
        create_calendar_client(mode, config)


@pytest.mark.parametrize("timeout", [True, False, 0, -1, float('nan'), float('inf'), '10', None])
def test_client_constructor_rejects_invalid_timeout(timeout):
    with pytest.raises(ValueError, match="REQUEST_TIMEOUT"):
        GoogleCalendarClient(FAKE_KEY, {"D1": "synthetic@example.test"}, timeout)


@pytest.mark.parametrize("mapping", [None, {}, [], {"D1": None}, {"": "synthetic@example.test"}, {"D1": ".."}])
def test_client_constructor_rejects_invalid_mapping(mapping):
    with pytest.raises(ValueError):
        GoogleCalendarClient(FAKE_KEY, mapping)


def test_environment_example_has_no_credentials():
    from pathlib import Path
    from dotenv import dotenv_values
    root = Path(__file__).resolve().parents[1]
    values = dotenv_values(root / '.env.example')
    assert values['GOOGLE_CALENDAR_API_KEY'] == ''
    assert json.loads(values['GOOGLE_CALENDAR_MAPPING']) == {}
    assert '.env' in (root / '.gitignore').read_text().splitlines()
