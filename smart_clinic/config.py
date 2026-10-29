"""Small, explicit offline/live configuration; never display environment values."""

import json
import math
import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def validate_timeout(timeout):
    if (
        isinstance(timeout, bool) or not isinstance(timeout, (int, float))
        or not math.isfinite(timeout) or timeout <= 0
    ):
        raise ValueError("REQUEST_TIMEOUT must be a finite positive number.")


def validate_live_config(api_key, doctor_calendars, timeout):
    if not isinstance(api_key, str) or not api_key.strip():
        raise ValueError("Live mode requires GOOGLE_CALENDAR_API_KEY.")
    if not isinstance(doctor_calendars, dict) or not doctor_calendars:
        raise ValueError("Live mode requires a doctor-to-calendar mapping.")
    for doctor_id, calendar_id in doctor_calendars.items():
        if (
            not isinstance(doctor_id, str) or not doctor_id.strip()
            or not isinstance(calendar_id, str) or not calendar_id.strip()
            or calendar_id in ("primary", ".", "..")
        ):
            raise ValueError("Use explicit doctor IDs and dedicated demo calendar IDs.")
    validate_timeout(timeout)


def load_config(mode="offline", env_file=None):
    """Offline does not load .env; live loads only the explicitly located file."""
    if mode == "offline":
        return {"json_path": PROJECT_ROOT / "data/calendar_responses.json"}
    if mode != "live":
        raise ValueError("Calendar mode must be offline or live.")
    try:
        load_dotenv(dotenv_path=PROJECT_ROOT / ".env" if env_file is None else env_file,
                    override=False, interpolate=False)
    except (OSError, UnicodeError):
        raise ValueError("Cannot load local calendar environment file.") from None
    api_key = os.getenv("GOOGLE_CALENDAR_API_KEY")
    try:
        mapping = json.loads(os.getenv("GOOGLE_CALENDAR_MAPPING", "{}"))
        timeout = float(os.getenv("REQUEST_TIMEOUT", "10"))
    except (ValueError, TypeError):
        raise ValueError("Invalid calendar mapping JSON or REQUEST_TIMEOUT.") from None
    validate_live_config(api_key, mapping, timeout)
    return {"api_key": api_key, "doctor_calendars": mapping, "timeout": timeout}
