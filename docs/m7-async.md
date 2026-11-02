# M7 — Sequential vs concurrent availability with asyncio (Yotam)

M9 integration note (2026-11-02): the reviewed implementation is merged and its
existing demonstration is now called from main.py. Verification below records
the original milestone checkpoint, not a new run on the contributor's platform.

M7 adds an asyncio comparison on top of the reviewed M6 inputs. It is offline
and simulated: delays come from `asyncio.sleep`, not from a calendar provider.
At the original M7 checkpoint, the shared `main.py` demonstration was unchanged;
M9 now invokes the existing timing comparison. M8 (threading) is not part of this work.

Starting point: `stage-2-development` at reviewed M6 commit
`722244c09062d515501e2c2c404b3974c8a4c393` (verified to be the branch tip when
work started). Feature branch: `m7-yotam-async`.

## Files

| File | Responsibility |
|---|---|
| `smart_clinic/async_processing.py` | `doctor_availability`, `collect_sequential`, `collect_concurrent` |
| `smart_clinic/demo_async.py` | Explicitly invoked M7 demo; measures both durations outside the calculation |
| `tests/test_async_processing.py` | 30 focused M7 checks (11 test functions, some parametrized) |
| `docs/m7-async.md` | This document |

No existing module, test or data file was changed.

## Public signatures

```python
# smart_clinic/async_processing.py
async def doctor_availability(service, patient, doctor, window_start, window_end, snapshot, delay)
    -> tuple[str, list[tuple[datetime, datetime]]]

async def collect_sequential(service, patient, doctors, snapshots, window_start, window_end, delays)
    -> list[tuple[str, list[tuple[datetime, datetime]]]]

async def collect_concurrent(service, patient, doctors, snapshots, window_start, window_end, delays)
    -> list[tuple[str, list[tuple[datetime, datetime]]]]

# smart_clinic/demo_async.py
DEMO_DELAYS = {"D001": 0.15, "D002": 0.05, "D003": 0.10}
def run_m7_demo(delays=DEMO_DELAYS, run=asyncio.run) -> dict
```

Parameters (both collectors take the same ones):

- `service`, `patient`, `doctors`, `snapshots`: exactly what
  `prepare_demo_inputs()` returns — one `AppointmentService`, the registered
  patient object, registered doctors in input order, and preloaded snapshots
  keyed by doctor ID.
- `window_start`, `window_end`: the search window (`WINDOW_START`/`WINDOW_END`).
- `delays`: simulated delay in seconds per doctor ID, e.g. `DEMO_DELAYS`.

Return value: `[(doctor_id, slots), ...]` in the same order as `doctors`, where
`slots` is the list returned by the existing
`available_slots_using_snapshot` (possibly empty).

The function names `collect_sequential` / `collect_concurrent` were given in
the M7 task prompt. Shon's handoff left the names open for coordination.

## Usage

```python
import asyncio
from smart_clinic.async_processing import collect_concurrent, collect_sequential
from smart_clinic.demo_async import DEMO_DELAYS
from smart_clinic.demo_data import WINDOW_END, WINDOW_START, prepare_demo_inputs

# Prepared synchronously, before any coroutine starts.
service, patient, doctors, snapshots = prepare_demo_inputs()
args = (service, patient, doctors, snapshots, WINDOW_START, WINDOW_END, DEMO_DELAYS)
sequential = asyncio.run(collect_sequential(*args))
concurrent = asyncio.run(collect_concurrent(*args))
assert sequential == concurrent  # [("D001", 6 slots), ("D002", 11 slots), ("D003", [])]
```

Demo (also part of main.py after M9 integration):

```bash
.venv/bin/python -m smart_clinic.demo_async      # Windows: .venv\Scripts\python
```

## How scheduling differs

Each doctor's coroutine does the same two steps: `await asyncio.sleep(delay)`,
then call the existing pure `available_slots_using_snapshot`.

- **Sequential**: a plain `for` loop awaits one doctor's coroutine to completion
  before creating the next. Only one doctor is ever waiting, so the total time is
  roughly the **sum** of the delays (0.15 + 0.05 + 0.10 = 0.30 s).
- **Concurrent**: `asyncio.create_task` schedules all three coroutines first; then
  `asyncio.gather` waits for all of them. All three sleeps are pending at the same
  time on one event loop (one thread), so the total time is roughly the
  **longest** delay (0.15 s). The doctors finish in delay order D002, D003, D001,
  but `gather` returns results in the order the tasks were given, so the output
  is still D001, D002, D003.

This is concurrency (overlapping waits), not parallelism: the calculation itself
still runs on one thread, one doctor at a time.

## Errors and empty results

- D003's synthetic calendar has an all-day busy event (not an empty calendar), so
  its valid result is `("D003", [])`: no available slots.
- Missing, wrong-doctor or insufficient snapshots are **not** turned into empty
  lists: the existing service raises `AvailabilityUnknownError`. An unregistered
  patient/doctor raises the service's `ValueError`.
- Sequential: the first failure stops the loop and propagates unchanged; later
  doctors are not started.
- Concurrent: `gather(..., return_exceptions=True)` lets every task finish (no
  task is left running), then the first failure **in input order** is raised
  unchanged — the same error the sequential version raises for the same inputs.
- Delays are checked before any doctor starts (before any simulated sleep or
  calculation): each doctor needs a finite, non-negative `int`/`float`, otherwise
  `ValueError`. Zero is valid. Missing values, `bool`, strings, negative numbers,
  `inf`, `-inf` and `NaN` are rejected. (`NaN < 0` is false, so NaN needs the
  explicit `math.isfinite` check.)

## Boundaries kept

- Snapshots are fetched once, synchronously, by `prepare_demo_inputs()`.
- Inside coroutines: no HTTP, no file reads, no `time.sleep`, no booking and no
  clinic mutation. Scheduling rules are reused from `AppointmentService`; none are
  duplicated. Timing (`time.perf_counter`) lives only in `demo_async.py`.

## Tests (`tests/test_async_processing.py`)

- Both versions return results equal to direct per-doctor service calls, with
  6/11/0 slots and D001/D002 start times from the handoff.
- Input order is kept although the calculation is reached in order D002, D003, D001.
- Real concurrent scheduling: a recording `asyncio.sleep` shows all three waits
  start before any ends (concurrent) vs start/end pairs (sequential).
- D003's valid empty list (no available slots) vs `AvailabilityUnknownError` for a
  missing snapshot.
- Wrong-doctor snapshot and unregistered patient propagate as errors in both versions.
- Sequential stops at the first failure; concurrent raises the first error in input
  order (D001) although D003 failed earlier in time, and leaves no running tasks.
- Invalid delays (missing, negative float/int, `bool`, string, `inf`, `-inf`, `NaN`)
  raise `ValueError` in both versions before any simulated sleep or calculation
  starts. Only D003's delay is invalid, so the earlier valid doctors must not start
  either. A recording `asyncio.sleep` returns at once, so no test ever waits on an
  infinite delay.
- Zero and ordinary int/float delays (`0`, `0.0`, `2`) stay valid in both versions;
  the requested delays are recorded, not waited.
- Clinic, snapshots, doctors, working hours, waiting lists and delays are unchanged
  after successful and failing runs.
- File reads (`open`), `time.sleep` and HTTP are patched to fail during collection.
- The M7 demo returns equal results for both versions and makes no HTTP request.
- No elapsed-time or speedup threshold is asserted.

Two deliberate faults were tried temporarily to check that the tests catch them:
making `collect_concurrent` run sequentially failed 3 tests; dropping
`return_exceptions=True` failed 1 test. Both were reverted.

## Technical Lead review corrections (after `a11f580`)

The review of `a11f580b14a6a6101a84973c7395eca7fe1850ca` accepted the core
implementation and asked for three focused corrections:

1. `_checked_delays` now also rejects non-finite float delays (`inf`, `-inf`,
   `NaN`) before any doctor task starts. Valid zero and ordinary non-negative
   int/float delays are unchanged.
2. Regression coverage for both collectors (see Tests above). When the new tests
   were run against the reviewed `a11f580` implementation, `inf` and `NaN` were
   actually accepted ("DID NOT RAISE ValueError", 2 values × 2 collectors). The
   other 12 new invalid-delay cases failed there only because the error message
   now says "finite, non-negative"; `-inf` was already rejected by the `< 0` check.
3. The demo now prints `D003: 0 slots; starts none (no available slots)` instead
   of calling D003 an empty calendar. D003 has an all-day busy event. The demo
   output test checks the new wording.

Service interfaces, `main.py`, source data and other contributors' files are
unchanged. The correction is a normal follow-up commit; history was not rewritten.

## Verification (2026-11-02)

Runtime: CPython 3.14.0 on Windows 11 (10.0.26200), pytest 9.2.0, in a fresh
`.venv` with `requests`, `python-dotenv`, `pytest` and `tzdata` (see findings).

| Check | Initial M7 (`a11f580`) | After review corrections |
|---|---|---|
| Baseline before M7 | 438 passed, 63 subtests passed | — |
| `pytest -p no:cacheprovider -q` | 458 passed (438 + 20), 63 subtests | **468 passed** (438 existing + 30 M7), 63 subtests passed |
| `unittest discover -s tests -p test_lecturer_feedback.py` | 19 tests OK | 19 tests OK |
| `python main.py` | exit 0; 15 Stage 1 sections + Stage 2, no M7 output | exit 0; same, `main.py` unchanged |
| `python -m smart_clinic.demo_async` | exit 0; equal results in input order | exit 0; equal results, D003 "no available slots" |
| `git diff --check` | clean | clean |
| Python 3.11 syntax | 35 files parsed | 35 files parsed with `ast.parse(..., feature_version=(3, 11))` |

The 3.11 check is a **syntax** check only; no Python 3.11 interpreter was
installed, so nothing was **executed** on 3.11. `asyncio.Runner` and
`asyncio.create_task` used here are available from Python 3.11.

### Timing observations

Five runs of `python -m smart_clinic.demo_async` with delays 0.15/0.05/0.10 s,
before and after the review corrections:

| Run | Sequential (initial) | Concurrent (initial) | Sequential (corrected) | Concurrent (corrected) |
|---|---|---|---|---|
| 1 | 0.331 s | 0.156 s | 0.331 s | 0.154 s |
| 2 | 0.330 s | 0.157 s | 0.335 s | 0.154 s |
| 3 | 0.323 s | 0.154 s | 0.332 s | 0.152 s |
| 4 | 0.335 s | 0.155 s | 0.329 s | 0.154 s |
| 5 | 0.334 s | 0.154 s | 0.330 s | 0.156 s |

As expected, sequential ≈ sum of delays plus overhead, concurrent ≈ longest delay
plus overhead. These are observations on one machine, not guarantees.

## Findings

1. **Windows needs `tzdata` for tests.** On Windows there is no system time-zone
   database, so `zoneinfo.ZoneInfo("Asia/Jerusalem")` fails and 14 test modules
   could not even be collected. Installing `tzdata` into the virtual environment
   fixed it. `pyproject.toml` was not changed (outside M7 scope); adding
   `tzdata; sys_platform == "win32"` to the dependencies is suggested for M9.
2. **Windows event loop vs the network guard.** `tests/conftest.py` blocks
   `socket.socket.connect`. On Windows, creating an asyncio event loop opens an
   internal local socket pair via `connect`, so a plain `asyncio.run` inside a test
   fails there (it works on macOS/Linux). The M7 tests create one event loop in a
   module-scoped fixture, which pytest sets up before the function-scoped guard,
   so the guard stays fully active during every M7 check. `conftest.py` is unchanged.

## Limitations

- Delays are simulated with `asyncio.sleep`; there is no real network IO, so this
  shows overlapping waits, not provider latency.
- The calculation is CPU work on one thread; asyncio does not make it faster.
- Snapshots are a point-in-time copy and do not protect against later external
  calendar edits. Booking and locking are M8 concerns.
- No live Google verification was performed or is claimed.
- README and AI_USAGE.md were not edited to avoid conflicts with parallel M8/M9
  work; this document is the M7 record to fold in during M9.


M9 resolves the Windows installation finding with the conditional tzdata
dependency in pyproject.toml. The combined-demo tests inject the same style of
pre-initialized module-scoped Runner, preserving the active per-test network guard.

AI-use documentation is centralized in [AI_USAGE.md](../AI_USAGE.md#11-m7-yotams-contributor-supplied-record).
