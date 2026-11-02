"""Simple Factory: select a calendar product, then use its shared contract."""

from pathlib import Path

from smart_clinic.api_client import GoogleCalendarClient, JsonCalendarClient


def create_calendar_client(mode, config):
    if mode not in ("offline", "live"):
        raise ValueError("Calendar mode must be offline or live.")
    if not isinstance(config, dict):
        raise ValueError("Calendar configuration must be a dictionary.")
    if mode == "offline":
        path = config.get("json_path")
        if not isinstance(path, (str, Path)) or not str(path).strip():
            raise ValueError("Offline mode requires a JSON calendar path.")
        return JsonCalendarClient(path)
    return GoogleCalendarClient(
        config.get("api_key"), config.get("doctor_calendars"), config.get("timeout", 10)
    )
