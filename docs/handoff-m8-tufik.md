# Proposed M8 handoff — Tufik

This is Shon's proposed division, pending coordination. It does not record
Tufik's agreement or contribution. This document gives interfaces and acceptance
criteria only; no coordinator, Lock or threading algorithm is implemented in M6.

## Verified starting point and setup

The M6 work starts from `846d2199c30bb4c3d89dd3c8161521cda64223db` on
`stage-2-development`. Reviewed M5 is `4709a90e85028b5167ffbd75958bbf3f9b5b2d83`;
the later baseline commit updates identity/TDD documentation only. At that
baseline, 434 cases and 63 subtests passed. Start from the published M6 commit,
verify Git status and preserve other students' work.

From the repository root, using Python 3.11 or newer:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install 'requests>=2.32,<3' 'python-dotenv>=1,<2' 'pytest>=8,<10'
.venv/bin/python -m pytest -p no:cacheprovider -q
.venv/bin/python -m unittest discover -s tests -p test_lecturer_feedback.py -v
.venv/bin/python main.py
git diff --check
```

No credentials or network are needed. Actual baseline runtime was Python 3.14.0;
Python 3.11 AST parsing is a syntax check, not execution on that interpreter.

## Existing interfaces and prepared contention input

The injected constructor is
`AppointmentService(manager, client, strategy, working_hours)`. Bound methods:

```python
fetch_snapshot(patient, doctor, window_start, window_end)
book_using_snapshot(appointment_id, patient, doctor, start, snapshot,
                    duration_minutes=30)
```

`fetch_snapshot` validates registered participants, adds the 15-minute query
padding once and returns a complete CalendarSnapshot or raises
AvailabilityUnknownError. It performs a client read: always prepare it **before**
locking. The JSON client also reads a file, so its read belongs outside the lock.

`book_using_snapshot` does no IO. It rechecks exact participant membership,
duplicate appointment IDs, grid/working hours, snapshot doctor/coverage, external
busy time and current local doctor/patient gaps, then registers via ClinicManager.
It returns the registered Appointment. ValueError means invalid/unavailable
booking; AvailabilityUnknownError means unusable external evidence, with no
booking. It does not silently select another time. These interfaces are frozen.

Single-thread interface example only, not the shared coordinator solution:

```python
from smart_clinic.demo_data import WINDOW_START, prepare_demo_inputs

service, patient, doctors, snapshots = prepare_demo_inputs()
doctor = doctors[1]  # D002: valid empty external calendar, explicit 09:00-12:00 hours.
snapshot = service.fetch_snapshot(patient, doctor, WINDOW_START,
                                  WINDOW_START.replace(hour=9, minute=30))
appointment = service.book_using_snapshot(
    "EXAMPLE-BOOKING", patient, doctor, WINDOW_START, snapshot
)
```

Use a **fresh** prepared clinic for the two-thread experiment, not the clinic
mutated by this example. P001 and P002 are both registered/free on that fixed
date. Give each request its own unique ID, the same D002 doctor, 09:00 start and
30-minute duration. Use one preloaded D002 snapshot covering that candidate and
both gap checks (the helper's 08:45-12:15 snapshot is sufficient for both
patients; external evidence is doctor-specific). Expect the second request's
doctor conflict to be detected whichever patient wins.

## Task boundaries and acceptance criteria

- Implement one BookingCoordinator and one shared Lock in
  `threaded_processing.py`, using the **same** manager/service for both Threads.
  Coordinate new coordinator method names with Shon; no implementation is supplied.
- Prepare external snapshots before the critical section. Hold the same Lock
  across final `book_using_snapshot` validation **and insertion**. All concurrent
  writers of this booking state must use that coordinator; locking only a lookup
  or only the dictionary write is insufficient.
- `book` and `cancel` are orchestration methods that can read externally and are
  not protected entry points for this contention experiment. Do not put HTTP or
  JSON-file reads inside the critical section.
- Start both Threads before joining either. Store their separate outcomes and
  inspect them after both joins. Require exactly one approval and one rejected
  conflicting request, with one new registered booking at the contested slot.
  The helper already contains seven historical appointments: check a delta of
  one or count the contested slot, not a total clinic length of one.
- Do not prescribe a winner. Preserve memberships, unique IDs and 15-minute
  doctor/patient gaps, including patient conflicts across doctors. Failure must
  leave no extra appointment. Keep all existing tests green and add M8 coverage.
- Explain the possible check-then-write interleaving. An unprotected experiment
  need not fail every run, so do not require nondeterministic failure as a test.

The guarantee is local to writers using this coordinator in this process. A
snapshot and Python Lock cannot prevent Google Calendar edits or implement a
transaction against Google. Real provider evidence and final M7/M8 integration
remain M9 work; M6 does not implement them.
