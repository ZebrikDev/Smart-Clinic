# M8 — Thread-safe booking (Tufik)

Starting point: `stage-2-development` at reviewed M6 commit
`722244c09062d515501e2c2c404b3974c8a4c393`. Feature branch: `m8-tufik-threading`.
The existing `AppointmentService` interfaces and scheduling rules are unchanged.

## The problem: check-then-write

`book_using_snapshot` does two things: it **checks** that the slot is still free
(current local appointments, 15-minute doctor/patient gaps, external busy time)
and then **writes** the appointment into `ClinicManager`. Without a Lock, two
Threads could interleave like this:

```text
Thread A: check D002 09:00 -> free
Thread B: check D002 09:00 -> free      (A has not written yet)
Thread A: write A's appointment
Thread B: write B's appointment         -> doctor double-booked
```

Locking only the check, or only the dictionary write, does not help: the other
Thread can still run between the check and the write. The coordinator therefore
holds **one** Lock across the whole `book_using_snapshot` call, so check and
write happen together. The second Thread waits, then rechecks and sees the
first Thread's appointment, so it is rejected with `ValueError`.

The external snapshot is fetched **before** the Lock (`fetch_snapshot` may read
a file or call Google). Slow IO must not hold the Lock, and nothing inside the
critical section reads HTTP or JSON files.

## Public interface (`smart_clinic/threaded_processing.py`)

```python
BookingCoordinator(service)
BookingCoordinator.book_with_snapshot(appointment_id, patient, doctor, start,
                                      snapshot, duration_minutes=30)
run_competing_bookings(coordinator, requests, snapshot)
demonstrate_booking_race()
```

- `BookingCoordinator(service)` — receives an existing `AppointmentService`
  (constructor injection) and creates its own `threading.Lock`. Raises
  `TypeError` for anything else.
- `book_with_snapshot(...)` — returns the registered `Appointment`. Business
  failures (`ValueError`, `AvailabilityUnknownError`) propagate unchanged and
  leave no extra appointment.
- `run_competing_bookings(...)` — starts one Thread per request
  `(appointment_id, patient, doctor, start, duration_minutes)`, starts all of
  them before joining any, and returns `("booked", appointment)` or
  `("rejected", error)` per request, in input order. Any other exception is a
  bug, not a conflict: it is raised as `RuntimeError` after all joins.
- `demonstrate_booking_race()` — the explicitly invoked M8 demo (not yet in
  `main.py`; that integration is M9).

All concurrent writers in this experiment must use the **same** coordinator,
service, manager and Lock. `book` and `cancel` are orchestration paths that can
read externally and are not protected entry points here.

## Usage

```bash
.venv/bin/python -m smart_clinic.threaded_processing
```

Fresh `prepare_demo_inputs()` clinic; P001 and P002 request D002 at 09:00 on
2026-10-29 for 30 minutes, both using the preloaded D002 snapshot (08:45–12:15,
covers the slot and both gaps). The winner is not prescribed. Example run:

```text
M8-RACE-P001 (P001): booked -> M8-RACE-P001
M8-RACE-P002 (P002): rejected -> Requested slot is not available.
Approved: 1, rejected: 1
Appointments before: 7, after: 8
Scheduled at D002 09:00-09:30: 1
```

The prepared clinic already has 7 historical appointments, so the check is a
delta of one and exactly one scheduled appointment at the contested slot.

## Tests (`tests/test_threaded_processing.py`)

- two competing Threads: exactly one booked, one `ValueError`, one new appointment;
- the demo repeated 20 times never double-books;
- duplicate appointment ID rejected, no extra booking;
- doctor conflict (09:30 is inside the 15-minute gap) rejected, no extra booking;
- patient conflict across doctors (P001 at D002 and D001, both 09:00) rejected;
- a slowed `book_using_snapshot` shows at most one Thread inside the Lock at a time;
- an unexpected worker exception is raised, not reported as a conflict.

No test requires an unprotected version to fail: a race is nondeterministic and
may not appear in every run.

## Limitations

The Lock protects only cooperating writers that use this coordinator, inside one
Python process. It does not prevent changes made directly in Google Calendar, by
another process, or by code that bypasses the coordinator, and a snapshot is not
a transaction against Google. No live Google verification was performed. M7
(asyncio) is not implemented here.

## Verification

Runtime used: Python 3.13 (project requires ≥ 3.11; the new file also parses
with Python 3.11 grammar).

| Command | Result |
|---|---|
| `pytest -p no:cacheprovider -q` | 446 passed, 63 subtests passed (438 existing + 8 new) |
| `unittest discover -s tests -p test_lecturer_feedback.py` | 19 tests OK |
| `python main.py` | existing M1–M6 demo runs, exit code 0 |
| `python -m smart_clinic.threaded_processing` | 1 approved, 1 rejected, 7 → 8 appointments |
| `git diff --check` | clean |

## AI assistance

Claude (Anthropic) was used to read the M8 handoff and `AppointmentService`,
draft the coordinator, demo, tests and this document, and run the checks above.
Tufik reviewed the code and is responsible for understanding and presenting it.
