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

**Design decisions.**
- A doctor cannot have two active appointments at exactly the same time. Active means `scheduled` or `in_progress`.
- Cancelling an appointment frees its time slot.
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

All data is synthetic.

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
