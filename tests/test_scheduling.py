from datetime import datetime

import pytest

from smart_clinic.scheduling import intervals_conflict


@pytest.mark.parametrize(
    "start, end, conflict",
    [
        (datetime(2026, 10, 29, 9, 16), datetime(2026, 10, 29, 9, 46), True),
        (datetime(2026, 10, 29, 9, 15), datetime(2026, 10, 29, 9, 45), False),
        (datetime(2026, 10, 29, 9, 14), datetime(2026, 10, 29, 9, 44), False),
        (datetime(2026, 10, 29, 10, 44), datetime(2026, 10, 29, 11, 14), True),
        (datetime(2026, 10, 29, 10, 45), datetime(2026, 10, 29, 11, 15), False),
        (datetime(2026, 10, 29, 10, 46), datetime(2026, 10, 29, 11, 16), False),
        (datetime(2026, 10, 29, 10, 15), datetime(2026, 10, 29, 10, 20), True),
        (datetime(2026, 10, 29, 9), datetime(2026, 10, 29, 11), True),
    ],
)
def test_interval_rule_is_symmetric(start, end, conflict):
    other_start = datetime(2026, 10, 29, 10)
    other_end = datetime(2026, 10, 29, 10, 30)
    assert intervals_conflict(start, end, other_start, other_end) is conflict
    assert intervals_conflict(other_start, other_end, start, end) is conflict


@pytest.mark.parametrize(
    "start, end",
    [
        (datetime(2026, 10, 29, 10), datetime(2026, 10, 29, 10)),
        (datetime(2026, 10, 29, 11), datetime(2026, 10, 29, 10)),
    ],
)
def test_invalid_intervals_are_rejected_on_either_side(start, end):
    valid = (datetime(2026, 10, 29, 12), datetime(2026, 10, 29, 12, 30))
    with pytest.raises(ValueError, match="end after"):
        intervals_conflict(start, end, *valid)
    with pytest.raises(ValueError, match="end after"):
        intervals_conflict(*valid, start, end)
