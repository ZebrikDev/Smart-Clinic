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

## 6. Stage 2: authorized M3 Strategy and TDD

Tool: Codex, used by Shon as an implementation assistant on 2026-10-30.

- Shon reported Technical Lead approval of M2 and explicitly authorized local
  commits for the reviewed baseline and genuine M3 Red/Green/Refactor stages.
  No push, merge, rebase, amend or history rewriting was authorized or performed.
- Codex reproduced the reviewed M2 files from the saved artifacts before staging.
  All 25 project files matched, with no unexpected changes. The 242 existing
  cases passed. Only reviewed project sources, synthetic data, tests and
  documentation were included; virtual environments, backups and review artifacts
  remained outside Git.
- The reviewed M1-M2 baseline was committed locally as
  `550ab9316e6a94859ba7a4d7032a8d2750e89b0d`
  (Preserve reviewed Smart Clinic M1 and M2).
- Codex added the shared SlotSelectionStrategy contract and both alternatives.
  Tests for closest-slot behavior were written before its implementation. The
  initial method raised NotImplementedError; the actual run had 11 failures and
  8 passes, without import/environment failures. That state and the captured
  output in docs/tdd/m3-red.txt were committed as
  `679aafd6e4430c55b12490f0e9dbb6685687b586`
  (test: record Red for closest slot selection).
- Green implemented distance/start ranking with an explicit loop, and all 261
  cases passed. The local commit is
  `60d2d3c02a3136612ef1d58f0e401bbd5506eddb`
  (feat: implement closest slot selection (Green)).
- Refactor replaced the manual best-slot/key bookkeeping with min and an explicit
  ranking key, preserving tests and behavior. All 261 cases remained green.
  The local commit is `5e8ba6d8e8b71ca68cb1a4db0fd504b31fb78608`
  (refactor: express closest selection with a ranking key).
- The 19 new cases cover both strategies, empty and unsorted input, exact
  preferences, equal-distance ties and unchanged slots/clinic state. Existing
  M1-M2 implementation and tests were preserved. The final checks also ran the
  original demo and git diff --check, using Python 3.14.0 and pytest 9.2.0;
  Python 3.11 syntax was checked separately.
- README/AI_USAGE record the completed TDD hashes in a later documentation
  commit so no circular or self-referential hash is required. No Google client,
  Factory, booking service, waiting list or concurrency was implemented in M3.

## 7. Stage 2: authorized M4 calendar client and Factory

Tool: Codex, used by Shon as an implementation assistant on 2026-10-30.

- Shon reported M3 approval and authorized M4 only, without an M4 commit. The
  initial worktree was clean at 72cd2840290c576b5c724ffd71db842f91eda7f1;
  all 261 existing cases passed before changes. The baseline and TDD history
  were preserved.
- Codex implemented GoogleCalendarClient using requests, per-page bounded Retry,
  complete pagination and sanitized failure categories; added Simple Factory,
  minimal offline/live configuration, .env.example and an explicit read-only
  verification command. Default main.py and the original JSONL are unchanged.
- Current Google documentation and its official client schema were consulted.
  The shared M2 normalizer stayed strict; a separate Google adapter handles an
  omitted empty items list only in a recognized envelope. Fractional query
  bounds are rounded outward because Google ignores query fractions, then
  results are filtered to exact coverage while preserving original endpoints.
- requests and python-dotenv were declared in pyproject.toml and installed only
  in the isolated .venv. No real key or calendar ID was invented. The environment
  example has an empty key and empty mapping; tests use clearly fake values.
- Final mocked/local verification passed 349 cases (88 new M4 cases), with 63
  unittest subtests, the separate 19-case suite, original demo, dependency check
  and git diff --check. Tests replace HTTP and actual waits, and a socket guard
  prohibits network access. Fake-key checks cover error text, tracebacks and logs.
- Runtime verification used Python 3.14.0; 26 files passed Python 3.11 syntax
  parsing. Real-provider verification remains pending: .env is absent in this
  worktree and no key/mapping is present in the process environment. The explicit
  command failed safely before HTTP. Mocked responses are not real API evidence.
- No credentials, calendars, account permissions or paid services were created
  or changed. No M5 booking service, waiting list, concurrency or final integrated
  demo was implemented. No commit, push, merge or history rewriting occurred in M4.

Publication follow-up: after Technical Lead review, Shon authorized a normal
commit and push of the reviewed M1-M4 history to stage-2-development. The preceding
no-commit statement records the earlier implementation checkpoint. Implementation
and mocked verification are complete; real-provider verification remains pending
configuration. Publication does not prove Google connectivity.

## 8. Stage 2: authorized M5 appointment workflow

Tool: Codex, used by Shon as an implementation assistant on 2026-10-30.

- Shon authorized M5 only, including a focused commit and normal branch push
  before stopping for Technical Lead review. The clean local and remote baseline
  was c86172f03a9be05ac6e930ba175256388ede3f20. All 349 existing cases passed first.
- Codex added AppointmentService with constructor-injected manager, calendar
  client, strategy and explicit working hours. Fetching, pure snapshot calculation
  and snapshot-based booking are separate. Booking reuses M2 availability and
  the manager registration path, with no alternate-time selection or fallback.
- WaitingRequest was added with validated, read-only fields. Existing appointment
  duration validation and manager membership checks were extracted into shared
  helpers so the service/model reuse them; the original regression expectations
  were not changed. A per-doctor deque tracks unique pending requests locally.
- The explicit M5 policies came from Shon's implementation request: scheduled-only
  cancellation; valid cancellation survives read failure with deferred backfill;
  replacements start at the original start, fit the freed interval and fit the
  request window. The service preserves skipped FIFO order and removes only a
  successfully registered request, creating at most one distinct replacement.
- Final verification passed 434 cases (85 new M5 cases), 63 unittest subtests,
  the separate 19-case lecturer suite, the original demo and git diff --check.
  Execution used Python 3.14.0 and pytest 9.2.0; 29 files passed Python 3.11 syntax
  parsing. A complete offline test uses the real JSON client and preserved source
  data; malformed tmp_path JSON also verifies safe deferred cancellation.
- The service interfaces for Yotam's pure calculation and Tufik's later protected
  booking are documented without implementing their modules or an M6 handoff.
  No M6 demo, Lock, coordinator, threads, asyncio, persistence or Google writes
  were added. Real Google verification remains pending configuration; automated
  tests and milestone publication are not provider evidence.

## 9. Authorized Stage 2 Git identity correction

On 2026-10-30, Shon explicitly approved correcting the author and committer of
his seven published Stage 2 commits to ZebrikDev, using the email associated
with his earlier GitHub commits. Codex performed the metadata correction after
creating a local backup branch and verifying a Git bundle. Each replacement
retains the original complete file tree, message and both timestamps; only the
identities and resulting parent/commit hashes change. The genuine M3 TDD states
and their order are preserved. Source code, tests, data and Stage 1 history are
unchanged. README references are repaired in a separate documentation commit.
The [correction record](docs/git-author-correction.md) maps original historical
hashes retained in this log to the current hashes. The approved publication uses
an explicit force-with-lease for stage-2-development only. This attribution
correction does not alter the AI-assistance records or establish live API proof.
