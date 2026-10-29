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
- No external packages are needed.

From the project root:

```bash
python3 main.py
```

`main.py` loads `data/sample_data.jsonl` and prints a short demonstration in 15 numbered sections.

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
python3 -m unittest discover -s tests -p test_lecturer_feedback.py -v
```

These checks cover status encapsulation, clinic membership, scheduling rules, and context-manager rollback.

## Stage 2

### What has been added

M1 extends the local model with appointment durations, a computed end time,
the terminal `no_show` status, and a 15-minute minimum gap for both doctors
and patients. M2 adds pure slot generation and availability filtering using a
complete synthetic calendar snapshot, explicit doctor working hours and current
local appointments. The Google client, selection strategies, booking service,
waiting-list backfill and concurrency remain pending.

### How to run

Python 3.11 or newer is required. The current demonstration has no network,
API key or environment-variable requirements. Install the test extra's dependency
inside an isolated virtual environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install 'pytest>=8,<10'
.venv/bin/python main.py
.venv/bin/python -m pytest -p no:cacheprovider -q
.venv/bin/python -m unittest discover -s tests -p test_lecturer_feedback.py -v
```

The `test` extra in `pyproject.toml` declares the same pytest requirement.
There is no live-service command at M2; the explicit live entry point will be
added in its authorized milestone. `python-dotenv` is not needed at M2.

The original `main.py` demonstration is preserved. To inspect M2 availability
directly, run this separate offline calculation from the project root:

```python
from datetime import datetime
from smart_clinic.api_client import JsonCalendarClient
from smart_clinic.scheduling import calculate_available_slots, padded_search_window

start = datetime(2026, 10, 29, 9)
end = datetime(2026, 10, 29, 12)
client = JsonCalendarClient("data/calendar_responses.json")
snapshot = client.fetch_busy_intervals("D001", *padded_search_window(start, end))
slots = calculate_available_slots("D001", "P001", [(start, end)], start, end, snapshot)
print(snapshot.source)  # simulated
print(slots)
```

### Code organization

The Stage 1 modules listed above remain in place. M1/M2 add or extend:

| File | Responsibility |
|---|---|
| `smart_clinic/models.py` | Duration/end time, statuses, and local doctor/patient conflict checks |
| `smart_clinic/scheduling.py` | Shared interval-gap rule, candidate generation, padded bounds and read-only availability |
| `smart_clinic/api_client.py` | CalendarClient contract, CalendarSnapshot, shared event normalization and JsonCalendarClient |
| `smart_clinic/time_utils.py` | Standard-library boundary between external timestamps and clinic-local time |
| `data/calendar_responses.json` | Complete synthetic Google-shaped calendars for three independent doctors |
| `smart_clinic/repository.py` | Optional JSONL `duration_minutes` with validation through the model |
| `tests/test_lecturer_feedback.py` | Preserved 19 regression checks, extended for `no_show` |
| `tests/test_models.py` | Durations, constructor compatibility, local conflicts and statuses |
| `tests/test_scheduling.py` | Symmetric gap boundaries and invalid intervals |
| `tests/test_repository.py` | Original dataset compatibility and temporary JSONL input checks |
| `tests/conftest.py` | Temporary synthetic calendar file fixture |
| `tests/test_availability.py` | Candidate grid, business boundaries, local conflicts and coverage |
| `tests/test_api_client.py` | Snapshot validation, file reading and event normalization |
| `tests/test_time_utils.py` | Offset conversion, all-day dates and date-specific query offsets |

### Main design decisions

- `Appointment(..., status="scheduled", duration_minutes=30)` preserves the old
  positional parameters. Duration accepts positive integers, excluding bool.
  Both `duration_minutes` and `end_at` are read-only properties; duration is set
  at construction and `end_at` is calculated from the start and duration.
- JSONL records may include `duration_minutes`. An absent field means 30 minutes;
  explicit invalid values are rejected with a line number. The original
  19-record dataset is unchanged, and loading remains entirely local.
- Datetimes follow the existing clinic-local, naive convention for
  `Asia/Jerusalem`. External offsets are parsed first, converted with
  `astimezone(ZoneInfo("Asia/Jerusalem"))`, and only then stripped of tzinfo.
  An offset-free external dateTime requires an explicit endpoint timeZone;
  ambiguous or nonexistent wall times without an offset are rejected.
  All-day dates use midnight in the response calendar's timeZone, with an
  exclusive end. Local calculation inputs must be naive; aware values are
  rejected before comparisons. Demo working hours avoid clock-change periods.
  `zoneinfo` is a small standard-library adaptation for this boundary, not a
  claim about material taught in the slides. It uses the available IANA timezone
  database. See the [Python zoneinfo documentation](https://docs.python.org/3.11/library/zoneinfo.html).
- One pure `intervals_conflict` function compares original endpoints in either
  chronological order. A gap of 14 minutes is rejected; 15 or 16 minutes is
  accepted. The required total gap is 15 minutes, not double padding.
- `ClinicManager.schedule_appointment` enforces the rule for active appointments
  of the same doctor or patient. `register_appointment` delegates to that method.
  Exact registered-object checks and duplicate-ID rejection are preserved.
- `no_show` is inactive and terminal, as are `cancelled` and `completed`.
  A Visit still requires `completed`. Exception rollback keeps the saved status
  and the original exception, including after a temporary `no_show` transition.
- `generate_candidate_slots(working_hours, window_start, window_end,
  duration_minutes=30)` returns sorted, deduplicated `(start, end)` tuples.
  Each working interval anchors its own 15-minute grid; narrowing the search
  window does not move that grid. Appointments must finish inside both windows;
  gaps are checked against other appointments, not treated as extra visit time
  that must fit in a shift. Explicit empty working hours produce no slots.
- `calculate_available_slots(doctor_id, patient_id, working_hours, window_start,
  window_end, snapshot, appointments=(), duration_minutes=30)` calls the shared
  M1 predicate against external doctor busy periods and relevant active local
  doctor/patient appointments. It does not rank slots, fetch data, mutate the
  clinic or check registration for a booking; booking remains a later service's
  responsibility, with the M1 manager invariants preserved.
- CalendarSnapshot carries doctor_id, window_start/window_end, sorted normalized
  busy interval tuples and source (`simulated` or `live`). Availability rejects
  a wrong doctor or coverage short of the search window plus 15 minutes on each
  side. `padded_search_window` supplies those caller-side bounds. Clients cover
  exactly the bounds they receive and never pad again or clip busy endpoints.
- JsonCalendarClient reads only when `fetch_busy_intervals` is called. The file
  maps `doctors` to Google-shaped responses with `kind: calendar#events`, an IANA
  `timeZone` and an explicit `items` list. An empty list is a valid empty calendar;
  a missing mapping, missing items, bad file or unusable blocking event raises
  ValueError. The file represents each complete simulated calendar; a remaining
  page token or unexpanded recurrence is rejected. Every blocking event is
  validated before selecting events intersecting the requested window.
- `normalize_calendar_events` is the single reusable normalization path. It
  supports timed and all-day events, ignores cancelled/transparent events and
  treats absent transparency as busy. JSON results always say `simulated`.
  The [Google Event contract](https://developers.google.com/workspace/calendar/api/v3/reference/events)
  defines these fields; the [events.list contract](https://developers.google.com/workspace/calendar/api/v3/reference/events/list)
  defines exclusive time bounds and pagination. No requests are sent in M2.
- The live calendar connection, Factory, both selection strategies, booking
  service and concurrency are still pending. The M3 TDD behavior is untouched.

### Verification evidence

At M1 review on 2026-10-29, Python 3.14.0 with pytest 9.2.0 passed 115 collected test cases
(19 preserved unittest cases plus 96 new pytest cases), with 63 unittest
subtests also passing. The separate unittest run passed all 19 cases; the
existing demo completed all 15 sections, and `git diff --check` passed.
Python 3.11 syntax compatibility was checked separately; execution was on 3.14.0.

The expected-result change in the existing transition matrix is explicit:
`no_show` now rejects transitions to `scheduled` and `in_progress`. The old
terminal cases retain their expectations. Related direct-assignment, inactive
membership and context-manager cases also include `no_show`.

At M2 verification on the same date and runtime, all 242 cases passed: the same
115 M1 cases plus 127 new M2 cases, with 63 unittest subtests also passing.
The separate 19-case unittest suite, all 15 original demo sections and
`git diff --check` passed. All 18 Python files passed Python 3.11 syntax parsing;
execution was on 3.14.0, not a separate 3.11 interpreter. Tests use synthetic
fixtures and tmp_path, without network, API keys or new runtime dependencies.

For working hours 09:00-12:00 and external busy time 10:00-10:30, with a free
patient and no local appointments:

| Request | Expected result | Expectation supplied by |
|---|---|---|
| 09:30-10:00 | Rejected: insufficient gap | Shon |
| 10:00-10:30 | Rejected: overlap | Shon |
| 09:15-09:45 | Available | Architecture/planning agent |
| 10:45-11:15 | Available | Architecture/planning agent |

Tests also cover events just outside the search window, working-hour boundaries,
local doctor/patient conflicts, invalid/aware windows, insufficient snapshots,
malformed files/events, empty calendars, all-day exclusive ends and different
timezone offsets. These are local/simulated M2 results. Real API evidence, the
M3 Red/Green/Refactor commit links and concurrency verification remain pending.
