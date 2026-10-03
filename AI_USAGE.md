# AI Usage

This file describes the AI usage in the Smart Clinic project. It lists only what actually happened. The code was written by the team in milestones. AI tools were used as helpers, as described below.

## 1. Synthetic data (`data/sample_data.jsonl`)

- AI tool used: ChatGPT
- Final prompt used to generate the data: the prompt was not saved and the team member who used it does not remember it.
- Record structure: the file uses a `record_type` field. The fields are `id` and `name` for `patient`; `id`, `name` and `specialty` for `doctor`; `appointment_id`, `patient_id`, `doctor_id`, `scheduled_at` and `status` for `appointment`; and `visit_id`, `appointment_id` and `summary` for `visit`.
- Problems found in the generated data and corrections made: not recorded.

How the data was verified (checked later, during Milestone 9):
- The file has 19 records: 5 patients, 4 doctors, 7 appointments and 3 visits, one JSON object per line.
- The IDs are unique within each record type.
- `load_clinic_data` in `smart_clinic/repository.py` loads the whole file without errors. It checks required fields, statuses, datetimes, duplicate IDs and references between records.
- All data is synthetic and contains no real personal information.

## 2. Other AI usage during development

| Tool | How it was used |
|---|---|
| ChatGPT | Helped plan the architecture of the project |
| GitHub Copilot | Code completion inside the IDE while the team wrote the code |
| Opus 5.5 | Quality checks (QA) of the code |

The team wrote the code step by step, milestone by milestone.

## 3. Milestone 9: documentation and final review

Tool: Claude Code (Claude Sonnet 5.5), used by Tufik Sarbuh as an assistant.

- It was used to compare the repository with the course requirements and to point out gaps.
- It found two gaps in the existing code: the waiting-queue demo never used `deque.append`, and `ClinicManager.register_visit` allowed two visits for the same appointment. Both were fixed in a separate commit.
- It helped draft the technical documentation in `README.md`.

How it was checked:
- `main.py` was run after the changes and all 15 demonstration sections still worked.
- A second visit for an already visited appointment was tried and rejected with a `ValueError`.
- Each statement in the README was compared with the code and with the output of `main.py`.
- `git diff` was reviewed before each commit, and the approved Project Proposal in the README was not changed.
