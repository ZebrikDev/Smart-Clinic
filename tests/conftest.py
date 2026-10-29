import json

import pytest


@pytest.fixture
def calendar_file(tmp_path):
    """A complete synthetic calendar for D1; callers control the real input file."""
    def write(items, time_zone="Asia/Jerusalem"):
        path = tmp_path / "calendar.json"
        payload = {"kind": "calendar#events", "timeZone": time_zone, "items": items}
        path.write_text(json.dumps({"doctors": {"D1": payload}}), encoding="utf-8")
        return path
    return write
