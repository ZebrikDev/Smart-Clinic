"""Explicit read-only verification for a configured public synthetic calendar."""

import argparse
from datetime import datetime

from smart_clinic.api_client import CalendarReadError
from smart_clinic.config import load_config
from smart_clinic.factories import create_calendar_client
from smart_clinic.scheduling import (
    calculate_available_slots, generate_candidate_slots, padded_search_window,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--doctor-id", required=True)
    parser.add_argument("--start", required=True, help="Clinic-local naive ISO datetime")
    parser.add_argument("--end", required=True, help="Clinic-local naive ISO datetime")
    args = parser.parse_args(argv)
    try:
        start, end = datetime.fromisoformat(args.start), datetime.fromisoformat(args.end)
    except ValueError:
        print("Invalid verification time bounds; use clinic-local ISO datetimes.")
        return 1
    try:
        bounds = padded_search_window(start, end)
        client = create_calendar_client("live", load_config("live"))
        snapshot = client.fetch_busy_intervals(args.doctor_id, *bounds)
        # Explicit demo working hours equal the requested window; no local bookings.
        hours = [(start, end)]
        candidates = generate_candidate_slots(hours, start, end)
        available = calculate_available_slots(
            args.doctor_id, "verification-patient", hours, start, end, snapshot
        )
    except (CalendarReadError, ValueError) as error:
        print(str(error))
        return 1
    print(f"source={snapshot.source}")
    print(f"busy_intervals={snapshot.busy_intervals}")
    print(f"blocked_slots={[slot for slot in candidates if slot not in available]}")
    print(f"available_slots={available}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
