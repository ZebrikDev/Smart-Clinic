# Proposed M7 handoff — Yotam

This is Shon's proposed division, pending coordination. It does not record
Yotam's agreement or contribution. Implement M7 only after coordination; this
document supplies interfaces and acceptance criteria, not an asyncio solution.

## Verified starting point and setup

The M6 work starts from `846d2199c30bb4c3d89dd3c8161521cda64223db` on
`stage-2-development`. Reviewed M5 is `4709a90e85028b5167ffbd75958bbf3f9b5b2d83`;
the later baseline commit updates identity/TDD documentation only. At that
baseline, all 434 cases and 63 subtests passed. M6 adds the offline demonstration
and prepared inputs below. Start from the published M6 commit and verify Git
status; do not discard other students' work.

From the repository root, using Python 3.11 or newer:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install 'requests>=2.32,<3' 'python-dotenv>=1,<2' 'pytest>=8,<10'
.venv/bin/python -m pytest -p no:cacheprovider -q
.venv/bin/python -m unittest discover -s tests -p test_lecturer_feedback.py -v
.venv/bin/python main.py
git diff --check
```

No API key, .env or network is needed. Actual baseline execution used Python
3.14.0; AST parsing for Python 3.11 is distinct from executing on Python 3.11.

## Prepared inputs and existing interface

`smart_clinic.demo_data.prepare_demo_inputs()` returns
`(service, patient, doctors, snapshots)`. It loads a fresh registered clinic from
the unchanged Stage 1 JSONL, creates the actual offline Factory product, sets
explicit hours and preloads all snapshots **synchronously**. Call it before any
coroutines. Do not call it inside a coroutine.

- `service`: one AppointmentService; `patient`: its exact registered P001 object.
- `doctors`: registered Doctor objects in input order D001, D002, D003.
- `snapshots`: dictionary keyed by doctor ID; CalendarSnapshot values all say
  `simulated` and cover 2026-10-29 08:45-12:15.
- `WINDOW_START` / `WINDOW_END`: naive clinic-local 2026-10-29 09:00 / 12:00,
  interpreted in Asia/Jerusalem. `service.working_hours` explicitly gives each
  doctor that same 09:00-12:00 interval.

| Doctor | Synthetic external calendar | Expected slot count |
|---|---|---|
| D001 | Busy 10:00-10:30 | 6 |
| D002 | Valid empty calendar | 11 |
| D003 | All-day busy, exclusive end 2026-10-30 | 0 |

Exact existing method (bound service; `self` omitted):

```python
available_slots_using_snapshot(patient, doctor, window_start, window_end,
                               snapshot, duration_minutes=30)
```

Single-call interface example, not a sequential/async implementation:

```python
from smart_clinic.demo_data import WINDOW_START, WINDOW_END, prepare_demo_inputs

service, patient, doctors, snapshots = prepare_demo_inputs()
doctor = doctors[0]
slots = service.available_slots_using_snapshot(
    patient, doctor, WINDOW_START, WINDOW_END, snapshots[doctor.id]
)
```

The result is a chronological list of `(start, end)` datetime tuples, possibly
empty. D001's starts are 09:00, 09:15, 10:45, 11:00, 11:15, 11:30. D002's starts
are every 15 minutes from 09:00 through 11:30. This method performs no IO or
clinic mutation. It rejects wrong-doctor/insufficient snapshots with
AvailabilityUnknownError, and invalid local inputs/membership with ValueError.
Do not replace failures with empty availability.

## Task boundaries and acceptance criteria

- In `async_processing.py`, provide sequential and scheduled/gather processing
  of the **same** at-least-three-doctor inputs and configured simulated delays.
  Agree the new function names with Shon; no M7 function names are frozen here.
- Each coroutine waits with `await asyncio.sleep`, then calls the pure method
  above. No requests, file reads, `time.sleep`, booking or state mutation inside
  a coroutine. Preload the snapshots once for both comparisons.
- Both versions return `(doctor_id, slots)` records in input order even when
  completion order differs. For example, different per-doctor delays such as
  0.15, 0.05 and 0.10 seconds can exercise that distinction.
- Tests require equal complete results, input order, empty D003 availability,
  and unchanged clinic/snapshot inputs; prevent accidental IO. Do not assert a
  brittle elapsed-time threshold. Measure the two durations in the eventual
  demo, outside the calculation functions.
- Preserve 30-minute default duration, each working interval's 15-minute grid,
  exact registered objects, active local doctor/patient conflicts and the shared
  15-minute gap. Reuse the existing service, not duplicated scheduling logic.
- Add meaningful M7 tests/docs and keep existing checks green. Timing display
  and final integration belong to coordinated M7/M9 work, not this M6 handoff.

Real Google verification and M8/M9 remain separate. These synthetic computations
do not claim live provider evidence or protect against external calendar edits.
