# AI Usage

This file describes the AI usage in the Smart Clinic project. It lists only what actually happened. Most of the code was written by the team in milestones. AI tools were used as helpers, as described below.

## 1. Synthetic data (`data/sample_data.jsonl`)

- AI tool used: ChatGPT
- Prompt record: the original generation prompt was not retained. The reconstructed prompt below describes the intended requirements for the final dataset.
- Record structure: the file uses a `record_type` field. The fields are `id` and `name` for `patient`; `id`, `name` and `specialty` for `doctor`; `appointment_id`, `patient_id`, `doctor_id`, `scheduled_at` and `status` for `appointment`; and `visit_id`, `appointment_id` and `summary` for `visit`.

### Reconstructed demo-data prompt

```text
Generate synthetic demonstration data for the Smart Clinic project in JSONL format.

Produce exactly 19 JSON objects: 5 patients, 4 doctors, 7 appointments, and 3 visits. Output one JSON object per line, without Markdown or explanatory text.

Use these fields:
- patient: record_type, id, name
- doctor: record_type, id, name, specialty
- appointment: record_type, appointment_id, patient_id, doctor_id, scheduled_at, status
- visit: record_type, visit_id, appointment_id, summary

Place patients and doctors before appointments, and appointments before visits. Use unique IDs and valid references.

Include scheduled, in_progress, completed, and cancelled appointments. Avoid active appointments for the same doctor at the same datetime. Visits must reference completed appointments, with at most one visit per appointment.

Use fictional identities and short synthetic visit summaries. Include enough variety to demonstrate filtering, sorting, patient history, and a lazy pipeline.
```

### Problems found during data validation and corrections made

During later validation testing, two loader issues were found: malformed reference values could cause TypeError without a JSONL line number, and duplicate-record errors did not identify the affected line.

Reference IDs are now checked as non-empty strings before dictionary lookups. Registration errors are caught and reported with the current JSONL line number.

The final 19-record dataset was checked for valid JSON objects, unique IDs, valid references, appointment statuses, and completed appointments linked to visits. No validation errors were found in the final dataset.

How the data was verified (checked later, during Milestone 9):
- The file has 19 records: 5 patients, 4 doctors, 7 appointments and 3 visits, one JSON object per line.
- The IDs are unique within each record type.
- `load_clinic_data` in `smart_clinic/repository.py` loads the whole file without errors. It checks required fields, statuses, datetimes, duplicate IDs and references between records.
- All data is synthetic and contains no real personal information.

## 2. Other AI usage during development

| Tool | How it was used |
|---|---|
| ChatGPT | Helped plan the architecture of the project , codebase reviews|
| GitHub Copilot | Code completion inside the IDE while the team wrote the code |
| Opus 5.5 | Quality checks (QA) of the code |

### Reconstructed architecture-planning prompt

The following reconstructed prompt describes the planning scope. It is not a preserved copy of the original conversation.

```text
Help prepare a Markdown architecture and milestone plan for a Smart Clinic project for a Stage 1 Advanced Python assignment.

This request is for planning the project.

Describe the proposed classes:
- Person: shared identity and name information.
- Patient: patient details and its relationship to appointments.
- Doctor: doctor details, specialty, and its relationship to appointments.
- Appointment: patient, doctor, scheduled datetime, and appointment status.
- Visit: a completed appointment and its visit summary.
- ClinicManager: managing the collections of patients, doctors, appointments, and visits.

Explain the inheritance and composition relationships, each class's responsibilities, and the validation rules the team should consider.

Organize the work into milestones covering the domain model, scheduling rules, JSONL data loading, collection processing, iterators and generators, a context manager, a final demonstration, and documentation.

For each milestone, describe its goal, planned responsibilities, and what the team should verify before continuing.

Keep the plan simple and aligned with the course material. Leave all coding and implementation decisions to the team.
```

## 3. Milestone 9 (final milstone): documentation and final review

Tool: Claude Code (Claude Sonnet 5.5), used by Tufik Sarbuh as an assistant.

- It was used to compare the repository with the course requirements and to point out gaps.
- It found two gaps in the existing code: the waiting-queue demo never used `deque.append`, and `ClinicManager.register_visit` allowed two visits for the same appointment. Both were fixed in a separate commit.
- It helped draft the technical documentation in `README.md`.

How it was checked:
- `main.py` was run after the changes and all 15 demonstration sections still worked.
- A second visit for an already visited appointment was tried and rejected with a `ValueError`.
- Each statement in the README was compared with the code and with the output of `main.py`.
- `git diff` was reviewed before each commit, and the approved Project Proposal in the README was not changed.
