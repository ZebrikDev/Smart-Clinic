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

## 4. Stage 2: M0 planning and authorized M1 implementation

Tool: Codex, used by Shon as an implementation assistant on 2026-10-29.

- The actual Stage 2 master prompt supplied the architecture, course sources,
  business rules and milestone boundaries. This is an actual Stage 2 planning
  prompt, not a reconstruction of a Stage 1 conversation. It first authorized
  read-only M0 inspection and planning; M1 was authorized separately after review.
- Codex backed up the dirty Stage 1 checkout and prepared a separate
  `stage-2-development` worktree from the main commit verified against GitHub.
  Lecturer-feedback fixes and the 19 existing tests were transferred. This file
  used main as its baseline; the older local draft was retained in the backup,
  and historical attribution differences were not reconciled.
- For M1, Codex implemented duration validation and end times, `no_show`, a pure
  gap predicate, local doctor/patient conflict checks and optional JSONL duration
  loading, and added pytest coverage and test setup documentation.
- Verification preserved the existing regressions, checked 14/15/16-minute gaps
  in both directions and both registration paths, tested invalid durations and
  the unchanged dataset, and ran the existing demonstration. The terminal-status
  tests were explicitly extended so `no_show` cannot become active again.
- Shon's two expected external-calendar rejections remain attributed to Shon:
  with work hours 09:00-12:00 and busy time 10:00-10:30, requests 09:30-10:00 and
  10:00-10:30 must both be rejected. They are reserved for M2; they were not
  exercised against an external calendar in M1. The proposed valid boundaries
  09:15-09:45 and 10:45-11:15 came from the planning agent.
- No Calendar connection, strategies, waiting-list behavior or concurrency were
  implemented in M1. No commits, push or merge were performed by Codex in M0/M1.

## 5. Stage 2: authorized M2 implementation

Tool: Codex, used by Shon as an implementation assistant on 2026-10-29.

- Shon reported Technical Lead approval of M1 and explicitly authorized M2 only.
  A byte-for-byte snapshot of the reviewed worktree was saved before changes.
- Codex implemented pure candidate generation and availability filtering,
  CalendarClient/CalendarSnapshot, JsonCalendarClient, one shared Google-shaped
  event normalizer and small standard-library datetime/zoneinfo helpers. The
  calendar fixture contains synthetic events only; the Stage 1 JSONL is unchanged.
- The implementation reuses the M1 gap predicate. The caller pads the search
  window once; the client preserves original event endpoints and exact coverage.
  Timezone helpers convert offsets before removing tzinfo, interpret all-day
  dates in the calendar timezone and generate date-specific query offsets.
- Shon's two rejection expectations and the planning agent's two acceptance
  boundaries are tested with their attribution retained. Additional checks cover
  working hours, local conflicts, invalid coverage/input and timezone conversion.
- The existing 115 M1 cases passed before implementation. Final verification
  passed all 242 cases (127 new M2 cases), 63 unittest subtests, the separate
  19-case unittest suite, all 15 original demo sections and git diff --check.
  Execution used Python 3.14.0; 18 Python files also passed Python 3.11 syntax
  parsing. No network, API keys or real calendar data were used by the tests.
- No Google client, Factory, selection strategy, booking service, waiting-list
  behavior or concurrency was implemented. The M3 TDD opportunity remains open.
  No commits, push or merge were performed for M2.
