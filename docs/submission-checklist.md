# Three-person Stage 2 submission checklist

Scope: Shon, Yotam and Tufik. Assignment sections 1–5 and 7–8 apply; the four-person
subsystem/report/four-additional-tests requirements do not. The cached assignment,
architecture and reviewed milestone contracts were checked before integration.

| Requirement | Evidence / status |
|---|---|
| Preserve Stage 1, lecturer fixes, source data and rollback | 15 sections, unchanged JSONL and regression expectations; 19 lecturer tests pass |
| External information changes a business decision | Service availability/booking/FIFO uses busy intervals; offline integration passes |
| At least one real GET with business effect | **VERIFIED:** actual source=live, busy 10:00–10:30, 5 blocked/6 available, exit 0; docs/evidence/google-calendar-live.txt |
| GET parameters, timeout, HTTP-before-JSON validation and normalization | Google client/time_utils and mocked API tests |
| Three attempts only for communication failures; safe failure | Retry/permanent-error/paging/no-partial-result and redaction tests |
| Configuration, ignored .env, placeholder example and safe logging | config.py, .gitignore, .env.example and safe-output tests |
| Two actual patterns and constructor injection | JSON/Google Factory, earliest/closest Strategy, injected service/coordinator |
| >=16 meaningful cases and required pytest tools | 478 cases, fixture, >=3-input parametrize, raises, Mock/patch, tmp_path, integration |
| Tests without network/keys/Retry waits | Autouse guard retained; guarded main and outbound-blocking test pass |
| Genuine Git Red/Green/Refactor | README commit links and unchanged docs/tdd/m3-red.txt |
| Three independent tasks; sequential vs scheduled/gather; ordered equal output | Reviewed M7, 6/11/0 slots, observed durations without timing assertions |
| Two Threads; one shared Lock across recheck+write; correct final state | Reviewed M8, one approval and one new booking, no prescribed winner |
| Default offline main and explicit labelled live command | Combined demos pass without .env/HTTP; separate real command verified with source=live |
| Dependencies and documented installation | .[test], conditional Windows tzdata, fresh-extraction install tested |
| One Stage 2 README section with five required parts | Stage 1 text preserved verbatim; Stage 2 sections 1–5 |
| AI documentation only in AI_USAGE.md | M7/M8 supplied records faithfully centralized; milestone docs link there |
| Exact committed ZIP and clean-install verification | External final-review manifest records source SHA, checksum and fresh logs |
| Meaningful history and attribution | Normal M7/M8 merges and focused Shon integration/docs commits |
| Final PR and review | Integration PR to main remains **UNMERGED**; exact-HEAD approval required |
| Final main release/download | **Not authorized in this run**; later normal merge and actual GitHub main download check |

Required M9 implementation and verification, including real-provider evidence,
are complete for final Technical Lead review. Exact-commit approval, main release
and verification of the actual GitHub main download remain pending.
[m9-verification.md](m9-verification.md) records commands, platform and limitations.
The group remains responsible for explaining the code and presenting it; this
checklist does not claim that those explanations/presentations already occurred.
