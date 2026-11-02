import json
import socket

import pytest


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Automated tests must not access the network.")
    monkeypatch.setattr(socket.socket, "connect", blocked)


@pytest.fixture
def calendar_file(tmp_path):
    """A complete synthetic calendar for D1; callers control the real input file."""
    def write(items, time_zone="Asia/Jerusalem"):
        path = tmp_path / "calendar.json"
        payload = {"kind": "calendar#events", "timeZone": time_zone, "items": items}
        path.write_text(json.dumps({"doctors": {"D1": payload}}), encoding="utf-8")
        return path
    return write
