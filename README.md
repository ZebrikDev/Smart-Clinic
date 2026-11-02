# Project Proposal: Smart Clinic

**1. Project Name and Description**
Smart Clinic - A centralized clinic management system designed to streamline appointment scheduling and manage comprehensive medical histories in one unified platform.

**2. Business Need / Problem Solved**
Many clinics rely on manual and scattered administrative processes, which often lead to human errors, double-booked appointments, and fragmented medical records. This system provides a structured solution to organize data, prevent conflicts, and save valuable time for the medical staff.

**3. Key Users and Their Roles**
* **Secretary / Receptionist:** Responsible for scheduling and canceling appointments, as well as managing patients' personal details.
* **Doctor:** Responsible for writing visit summaries, reviewing medical histories, and updating patients' personal medical files.
* **Clinic Manager:** Monitors doctors' schedules, analyzes peak hours, and tracks patient arrival rates.

**4. Main Business Process**
A patient requests an appointment -> The secretary checks availability, schedules the appointment, and sends a reminder -> On the day of the appointment, the doctor reviews the patient's medical file beforehand -> The examination takes place, and a visit summary is recorded -> If needed, a follow-up appointment is scheduled, and the system updates the visit status accordingly.

**5. Information Flow**
* **Inputs:** Appointment requests, patient personal details (e.g., ID, Name), and doctors' availability.
* **Creators/Updaters:** Secretaries create and update appointments; Doctors create and update medical records (visit summaries).
* **Outputs:** Weekly schedule reports, visit histories, and statistical reports on resource utilization and peak hours.

**6. Expected Business Value**
Centralizing administrative processes reduces dependency on manual labor, prevents scheduling conflicts (double-booking), unifies medical records, improves overall patient service, and supports data-driven decision-making (such as shift planning based on peak hour analysis).

**7. Main Entities and Relationships**
* **Entities:** Doctor, Patient, Appointment, Visit (Medical Summary).
* **Relationships:** 
  * A `Patient` can have multiple `Appointments` and `Visits` (1-to-Many).
  * A `Doctor` handles multiple `Appointments` (1-to-Many).
  * An `Appointment` is linked to exactly one `Doctor` and one `Patient`.
  * A `Visit` is generated from a completed `Appointment` to store the medical summary.

**8. Main Use Cases**
* **Conflict-Free Scheduling:** The system schedules a new appointment while automatically detecting and preventing time-slot overlaps.
* **Medical History Review:** A doctor accesses a patient's historical records right before an examination to gain insights and provide better, informed medical care.

**9. Future Extension Idea**
Integration of an automated reminder system (e.g., via an external SMS or EMAIL API) to automatically notify patients one day prior to their scheduled appointment.

---

# Technical Documentation

## Requirements and How to Run

- Python 3.11 or newer
- Install the declared dependencies in an isolated environment as shown under Stage 2.

From the project root:

```bash
.venv/bin/python main.py
```

`main.py` preserves the 15 numbered Stage 1 sections loading `data/sample_data.jsonl`,
then runs a separate Stage 2 offline demonstration with fresh synthetic inputs.

## Project Map

| File | Responsibility |
|---|---|
| `smart_clinic/models.py` | Business classes: `Person`, `Patient`, `Doctor`, `Appointment`, `Visit`, `ClinicManager` |
| `smart_clinic/repository.py` | Reads the JSONL file line by line, converts records to objects, validates data |
| `smart_clinic/processing.py` | Collection processing: grouping, counting, queues, comprehensions, sorting |
| `smart_clinic/iterators.py` | `AppointmentCollection`, `AppointmentIterator`, a generator and a lazy pipeline |
| `smart_clinic/context_managers.py` | `AppointmentProcessing` context manager |
| `data/sample_data.jsonl` | 19 synthetic records, one JSON object per line |
| `main.py` | Demonstration only, no business classes |

## Object-Oriented Design

**Inheritance and polymorphism.** `Person` is the base class and `Patient` and `Doctor` inherit from it. Both override `get_details()`. In `main.py` (section 3) a list that contains patients and doctors is looped over and `get_details()` is called on each item, without checking the type.

**Composition.** `ClinicManager` contains four dictionaries (patients, doctors, appointments, visits). It provides operations on them: `register_patient`, `register_doctor`, `schedule_appointment`, `register_visit` and the lookups `find_patient`, `find_doctor`, `find_appointment`, `find_visit`. An `Appointment` holds one `Patient` and one `Doctor`, and a `Visit` holds its `Appointment`.

**Validation.** Invalid data raises `ValueError` with a message that explains the problem, for example an empty ID, an unknown status, or a `Visit` for an appointment that is not completed.

**Other class tools.** `Patient.from_dict` and `Doctor.from_dict` are alternative constructors (`@classmethod`). `Appointment.is_active` is a computed `@property`.

`Appointment.status` is a read-only property backed by `_status`. Normal status changes go through `update_status`, so direct assignment to `status` cannot bypass validation. On exception, `AppointmentProcessing` restores the saved internal status as rollback rather than as a new business transition.

**Design decisions.**
- Active appointments for the same doctor or patient must not overlap and must have at least 15 minutes between them. Active means `scheduled` or `in_progress`.
- An appointment must refer to the patient and doctor objects registered with that clinic; matching IDs on different objects are not sufficient.
- Cancelling an appointment frees its time slot.
- Cancelled, completed and no-show appointments cannot become active again.
- A `Visit` can only be created for a completed appointment, and each appointment can have only one visit.
- Adding an ID that already exists raises `ValueError` and does not overwrite the old object.

## Data Structures

| Need | Structure | Why it fits |
|---|---|---|
| Ordered group of appointments that can change | `list` | Order matters and items are added and filtered |
| Short fixed record (ID, names, status) | `tuple` | The fields are fixed. Star unpacking `first, *middle, last` splits it in `appointment_summary_parts` |
| Statuses in use, doctors with appointments | `set` | Only unique values matter. `&` and `-` compare active and inactive statuses |
| Find a patient, doctor, appointment or visit by ID | `dict` | Lookup by key is fast and IDs are unique |
| Count appointments per status and group them per doctor | `dict` | The key is the status or the doctor ID and the value is a count or a list |
| Regular requests handled by arrival order | `deque` | `append` adds at the end and `popleft` takes from the front. Arrival order is fair to waiting patients |
| Urgent requests handled before regular ones | `heapq` | The smallest tuple comes out first |

**Priority queue.** Priority 1 is urgent and 2 is regular, so a smaller number means a higher priority. Each item is `(priority, sequence, appointment)`. The sequence number decides between equal priorities, so they come out in arrival order. The internal heap list is not fully sorted, and items must be taken out with `heappop`.

**Queue edge case.** `process_waiting_queue` uses `while queue`, so an empty `deque` returns an empty list and does not crash.

**Comprehensions and sorting** (`processing.py`):
- list comprehension: `active_appointment_ids`
- set comprehension: `unique_doctor_ids`
- dict comprehension: `appointment_status_map`
- `sorted` with a named function as key: `by_scheduled_at`
- `sorted` with a lambda as key: `sorted_by_patient_name`
- `sorted` with a two-field tuple key: `sorted_by_doctor_then_time`

### Operations That Change a Collection vs. Create a New One

| Changes the existing collection | Creates a new collection |
|---|---|
| `deque.append`, `deque.popleft` in the waiting queue | list, set and dict comprehensions |
| `heapq.heappush`, `heapq.heappop` in the priority queue | `sorted(...)` (the original list keeps its order) |
| `set.add` in `status_groups` | `&` and `-` between sets (a new set is returned) |
| assigning `counts[status] = ...` and `groups[doctor_id].append(...)` | `active_appointments` (builds a new list) |

## Data File and Loading

Each line of `data/sample_data.jsonl` is one JSON object with a `record_type` field. The records are in dependency order:

| record_type | Fields |
|---|---|
| `patient` | `id`, `name` |
| `doctor` | `id`, `name`, `specialty` |
| `appointment` | `appointment_id`, `patient_id`, `doctor_id`, `scheduled_at`, `status` |
| `visit` | `visit_id`, `appointment_id`, `summary` |

All data is synthetic. The records were generated with ChatGPT, and how the file was checked is described in `AI_USAGE.md`.

`load_clinic_data` in `repository.py` opens the file with `with open(..., encoding="utf-8")` and reads it line by line. It does not use `read()` or `readlines()`. Each line goes through `json.loads` to become a `dict`, and then the dict is converted to an object (`from_dict` for patients and doctors, and the constructors for appointments and visits). The loader stops with a `ValueError` that includes the line number when it finds:
- malformed JSON or a line that is not a JSON object
- an unknown `record_type`
- a missing required field
- an invalid status or datetime
- a duplicate ID
- an appointment or visit that points to a patient, doctor or appointment that does not exist

## Iterable and Iterator

`AppointmentCollection` (the iterable) stores the appointments and implements `__iter__`. Every `iter(collection)` call returns a new `AppointmentIterator`. The iterator implements `__iter__` and `__next__`, keeps the current position in `index`, and raises `StopIteration` at the end. In `main.py` (section 11) two iterators go over the same collection and move forward independently. When the first one is exhausted, the second one continues from its own position.

## Generator and Lazy Pipeline

**Generator.** `completed_appointments_for_patient` uses `yield` to return the completed appointments of one patient, one at a time. Creating it does not process anything. After one `next()`, a `for` loop continues from where it stopped. When it finishes, it cannot be used again, so a new generator must be created to start from the beginning (`main.py`, section 12).

**Pipeline.** `appointment_label_pipeline` has three stages, all generator expressions with no lists in between:
1. keep only active appointments
2. turn each one into a `(patient name, doctor name)` pair
3. turn each pair into a text label such as `Diana Prince -> Leonard McCoy`

In section 13 of `main.py` only the first two results are taken.

- **What starts the work:** creating the pipeline reads 0 appointments. The work starts only when `next()` or a `for` loop asks for a result.
- **What was not processed:** after the two results, 5 of the 10 appointments were read (A001 to A005). A006 to A010 were never checked.
- **Difference from a list comprehension:** a list comprehension would check all 10 appointments immediately and keep the full result in memory. A generator expression produces one value at a time, only when asked.
- **Why a new generator is needed:** a generator is used up when it ends, and it remembers its position. To go over the data again, a new one must be created.

## Context Manager

`AppointmentProcessing` in `context_managers.py` is used with `with AppointmentProcessing(appointment):`.
- On entering, it saves the previous status and sets the status to `in_progress`. If the appointment is not active, it raises `ValueError`.
- On a normal exit, the status becomes `completed`.
- If an exception happens inside the block, the previous status is restored and the exception continues to the caller, because `__exit__` returns `False`.

`main.py` shows both cases (sections 14 and 15).

## Regression Checks

Run the lecturer-feedback checks from the project root:

```bash
.venv/bin/python -m unittest discover -s tests -p test_lecturer_feedback.py -v
```

These checks cover status encapsulation, clinic membership, scheduling rules, and context-manager rollback.

## Stage 2

### 1. Business extension and value

The clinic now combines a doctor's external Google Calendar busy periods with
explicit local working hours and active doctor/patient appointments. It can offer
valid slots, select earliest or closest to a preference, book locally, and fill a
cancelled appointment from a FIFO waiting list. This reduces conflicting
appointments while keeping cancellation usable during provider failure.

M1–M6 scheduling and demonstrations, Yotam's reviewed M7 collectors and Tufik's
reviewed M8 coordinator are integrated. **M9 implementation and verification are
complete for final Technical Lead review**, including a real Google availability
decision. Approval of the final commit, merge to main and the actual GitHub main
download check remain pending; no release approval is implied.
The project has three students; the four-person subsystem requirements do not apply.

### 2. Installation and offline/live/test commands

Use Python 3.11 or newer from the extracted source/project root. Create and
activate an isolated environment:

```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

```powershell
# Windows PowerShell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Then, on either platform with that environment active:

```bash
python -m pip install ".[test]"
python main.py
python -m pytest -p no:cacheprovider -q
python -m unittest discover -s tests -p test_lecturer_feedback.py -v
python -m smart_clinic.demo_async
python -m smart_clinic.threaded_processing
python -m pip check
git diff --check  # Git checkout only; omit for a source ZIP without .git
```

If activation is unavailable, replace `python` with `.venv/bin/python` on
macOS/Linux or `.\.venv\Scripts\python.exe` on Windows. Installation reads
pyproject.toml: requests, python-dotenv, pytest via the test extra, and **tzdata
on Windows**. The explicit package configuration makes installation from a
source ZIP deterministic instead of relying on flat-directory discovery.
Dependency download requires connectivity; after installation the default demo
and tests require no network or credentials. Run commands from the source root;
the data files are source fixtures, not a standalone installed command's data.

Default execution retains the original 15 sections, followed by the Stage 2
business workflow, M7 timings and M8 contention. Calendars and delays are labelled
simulated. It never loads .env. Independent demonstrations use fresh clinics;
the two competing writers share one clinic/service/coordinator/Lock.

The separate, explicitly live command is:

```bash
python -m smart_clinic.verify_calendar --doctor-id D001 \
  --start 2026-10-29T09:00:00 --end 2026-10-29T12:00:00
```

Follow [live setup instructions](docs/live-verification.md) for a dedicated public
calendar containing synthetic events only, Calendar API enablement, a locally
stored API key, `GOOGLE_CALENDAR_MAPPING` JSON and `REQUEST_TIMEOUT`. .env is ignored;
.env.example contains placeholders only. Never paste keys into chat or log request
URLs. No calendar/account resource is created by the application. This command
calculates availability; it does not run a full live booking workflow.

### 3. Updated code organization

Stage 1 modules retain the responsibilities documented above. Stage 2 adds:

| Module / directory | Responsibility |
|---|---|
| models.py, repository.py | Duration/end time, terminal no_show, exact membership, local gaps, WaitingRequest, compatible JSONL loading |
| scheduling.py, time_utils.py | Pure grid/availability/gap rules, single padding boundary, timezone conversion |
| api_client.py | CalendarClient/Snapshot, shared event normalizer, JSON and Google clients, complete pagination and safe Retry/errors |
| factories.py, config.py | Simple Factory and explicit offline/live configuration |
| strategies.py | EarliestAvailableStrategy and ClosestToRequestedStrategy |
| services.py | Injected availability/booking/cancellation/FIFO workflows and snapshot-based local recheck |
| demo_data.py, demo_stage2.py | Fresh fixed-date inputs and scheduling/failure presentation |
| async_processing.py, demo_async.py | Yotam's sequential and scheduled/gather collectors plus observed timing demo |
| threaded_processing.py | Tufik's shared BookingCoordinator and two-thread experiment |
| verify_calendar.py | Explicit read-only live availability verification |
| data/ | Original 19-record JSONL and complete synthetic calendars for three doctors |
| tests/ | Regression, interval/API/Retry/pattern/service/async/Lock and combined-entry-point checks |
| docs/ | Technical contracts, M7/M8 milestone records, live instructions, TDD output and submission checklist |

### 4. Design decisions

- **External information:** a real requests GET to Google's
  [events.list](https://developers.google.com/workspace/calendar/api/v3/reference/events/list)
  reads doctor busy intervals. See the [Event resource](https://developers.google.com/workspace/calendar/api/v3/reference/events)
  and [credential guide](https://developers.google.com/workspace/guides/create-credentials).
  Timed/all-day intervals are normalized to naive Asia/Jerusalem clinic time
  after offset conversion. Recurrence is expanded by Google; all pages must
  succeed. The caller pads once by 15 minutes and original busy endpoints remain.
- **Failure:** HTTP is checked before JSON. Only Timeout/ConnectionError retry,
  at most three GET attempts per page with waits; permanent HTTP, JSON and invalid
  data do not retry. Unknown/incomplete availability prevents booking; valid local
  cancellation survives with deferred backfill and its queue intact. No empty or
  simulated fallback is presented as live. Logs expose safe categories/statuses.
- **Two patterns:** the Simple Factory creates actual JSON or Google products
  from mode/config. Strategy selects from already-valid slots: earliest start or
  closest start, with earlier starts breaking ties. Selection never books.
- **Dependency injection:** AppointmentService receives manager, client, strategy
  and explicit hours through its constructor. Tests replace external dependencies
  where looked up, preserving real calculations. No DI framework or third pattern.
- **Local rules:** default duration is 30 positive-integer minutes (not bool), with
  starts on a 15-minute grid anchored to each working interval. Active doctor and
  patient appointments require one total 15-minute gap in either chronological
  direction; no_show/cancelled/completed are terminal and inactive. Exact object
  membership, duplicate IDs, encapsulated status and rollback are preserved.
  Historical JSONL defaults missing duration to 30 minutes without requiring a calendar.
- **FIFO:** cancellation is scheduled-only. At most one currently eligible request
  fills the original start, within its window and freed duration. Skipped requests
  stay in order; the cancelled record remains history and the replacement gets a
  distinct ID. See [detailed service contracts](docs/scheduling-contracts.md).
- **Async tasks:** three independent doctors share preloaded simulated snapshots.
  Each coroutine awaits asyncio.sleep then calls pure local availability; no IO,
  booking or mutation. Sequential and create_task/gather versions use identical
  inputs and return complete results in input order. Observed durations are printed
  without a required speedup. [M7 details](docs/m7-async.md).
- **Protected resource:** two Threads compete for one local slot through the same
  coordinator and Lock. External reads precede locking; final local recheck plus
  insertion are protected together. All concurrent writers must cooperate. Both
  Threads start before join; tests require one approval without choosing a winner.
  Without the Lock, two free checks could precede either write; an unprotected run
  need not fail every time. The guarantee is local, not a Google transaction.
  [M8 details](docs/m8-threading.md).
- **Windows testing:** module-scoped asyncio.Runner fixtures initialize the internal
  event-loop socket pair before the function-scoped network guard. The combined
  demo accepts the runner at its composition boundary; the guard stays active
  during collectors, booking and the full test. It is not disabled globally.

### 5. Verification evidence and submission status

On 2026-11-02 the integrated suite passed **478 cases and 63 subtests**, including
all 476 merged cases plus two focused integration/isolation checks. The separate
lecturer suite passed 19 tests. Combined main.py, explicit M7/M8 demos, pip check
and git diff --check passed. Actual execution: **macOS 26.6.2 arm64, CPython 3.14.0,
pytest 9.2.0**. Python 3.11 AST parsing is a syntax check, not execution on 3.11.
Yotam's Windows 11 / Python 3.14 and Tufik's Python 3.13 results are their historical
milestone records; this M9 run does not claim new Windows execution.

Offline outcomes: external busy time reduces 11 candidates to 6; earliest and
closest choose 09:00 and 11:00 for preference 11:00; local booking/FIFO/backfill
and controlled deferred failure preserve history and queues. M7 returns D001/D002/
D003 in input order with 6/11/0 slots; D003 is all-day busy, not an empty calendar.
M8 creates one new appointment from two competing requests. Timings are observed,
not asserted. [M9 evidence](docs/m9-verification.md) records commands/status and
[the three-person checklist](docs/submission-checklist.md) identifies remaining gates.

The following business expectations retain their original attribution (working
hours 09:00–12:00, external busy 10:00–10:30, free patient, no other local appointments):

| Request | Expected | Supplied by |
|---|---|---|
| 09:30–10:00 | Reject: insufficient gap | Shon |
| 10:00–10:30 | Reject: overlap | Shon |
| 09:15–09:45 | Allow when other constraints permit | Architecture/planning agent |
| 10:45–11:15 | Allow when other constraints permit | Architecture/planning agent |

**Real Google evidence: verified on 2026-11-02.** Shon supplied the successful
setup log; a read-only rerun through the existing GoogleCalendarClient and explicit
command independently reproduced it on macOS 26.6.2 arm64 / Python 3.14.0:
`source=live`, D001 window 2026-10-29 09:00–12:00 Asia/Jerusalem, normalized busy
time 10:00–10:30, **5 blocked / 6 available slots**, exit **0**. The event rejects
both of Shon's requests above and permits the two architecture boundaries.
[Actual command/output/runtime](docs/evidence/google-calendar-live.txt) records
all slot endpoints without secrets or authenticated URLs. The previous missing-key
attempt remains historical in [M9 evidence](docs/m9-verification.md). This is live
availability verification, not a complete live booking workflow or a transaction
against Google. The default demo and automated tests remain offline.

ClosestToRequestedStrategy has a genuine Git Red/Green/Refactor sequence:

| Stage | Commit | Recorded result |
|---|---|---|
| Red | [6d2e55a](https://github.com/ZebrikDev/Smart-Clinic/commit/6d2e55af73126fcd2bca25b3112eec685ce80e9d) | 11 failures from missing behavior, 8 passes |
| Green | [97dde51](https://github.com/ZebrikDev/Smart-Clinic/commit/97dde5106213a1aa090bc0610416435e465e8498) | 261 cases passed |
| Refactor | [ab5ebde](https://github.com/ZebrikDev/Smart-Clinic/commit/ab5ebde75af843c3651800d3e2bc64dcaf4f9709) | min with ranking key; 261 cases stayed green |

[Saved Red output](docs/tdd/m3-red.txt) is unchanged. The
[identity correction map](docs/git-author-correction.md) explains historical hashes;
all original TDD states and contributor commits remain reachable.

A review ZIP is built from an exact committed integration tree, excluding .env,
environments, caches, untracked files and backups. Its source SHA, checksum and
fresh-extraction installation/test results are recorded in the external review
package. The final PR remains unmerged; after Technical Lead approval of the exact
commit, merge to main and verification of the actual GitHub main download are a
separate release step.
