# Scheduling contracts and business boundaries

Detailed technical reference for the reviewed M1–M5 contracts, retained during M9.

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
  clinic or check registration for a booking; booking is the AppointmentService responsibility, with the M1 manager invariants preserved.
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
- `SlotSelectionStrategy.select(slots, preferred_start)` returns one of the
  supplied valid slots, or None for empty input. EarliestAvailableStrategy uses
  the earliest start and ignores the preference. ClosestToRequestedStrategy uses
  `(absolute distance from preferred_start, start)` so equal distances choose
  the earlier start. Nonempty closest selection requires a clinic-local naive
  datetime preference, matching the local slot convention. Neither strategy
  sorts/mutates the input, checks availability, fetches data or books anything.
  This is the course-style Strategy pattern with a small shared contract;
  selection remains separate from availability and AppointmentService composition.
- `create_calendar_client(mode, config)` is the second course pattern, a Simple
  Factory. `offline` creates JsonCalendarClient; `live` creates GoogleCalendarClient.
  Both implement CalendarClient; unknown modes and invalid configuration are
  rejected. Configuration is passed in, without a framework or extra pattern.
  Constructors perform no HTTP or calendar-file reading.
- GoogleCalendarClient uses requests GET with a URL-encoded calendar path,
  timeMin/timeMax, timeZone=Asia/Jerusalem, singleEvents=True, showDeleted=False,
  orderBy=startTime, finite timeout and pageToken when needed. Redirects are not
  followed. HTTP is checked before JSON. It gathers every page, rejects repeated
  or malformed tokens and never returns a partial snapshot. A supplied padded
  window is not gap-padded again. Because Google ignores fractional query seconds,
  only fractional HTTP bounds are rounded outward to whole seconds; results are
  filtered back to the exact supplied coverage without clipping event endpoints.
- The M2 normalizer remains shared and strict. A Google-only adapter accepts
  omitted items as empty only with kind=calendar#events, a nonempty etag, valid
  timeZone and no error. Present null/wrong-type items remain errors, and any
  nextPageToken still requires another page. This follows the documented
  collection format, Google's [empty-property guidance](https://google.github.io/styleguide/jsoncguide.html#emptynull-property-values),
  and the [official client Events schema](https://github.com/googleapis/google-api-go-client/blob/main/calendar/v3/calendar-gen.go),
  which models items with omitempty. This is a documented adapter rule, not a
  claim that every malformed/missing collection is empty. The M2 JSON format
  still requires explicit items. Unusable blocking events fail the entire read;
  insufficient read access and error envelopes are rejected.
- Each page's GET retries only Timeout or ConnectionError, at most three attempts
  with a one-second wait between attempts. HTTP (including 401/403/429/503), JSON
  and validation failures are not retried. CalendarReadError exposes a fixed
  category (communication/http/json/validation), optional safe reason and integer
  HTTP status. Logs never include keys, request URLs, raw response bodies or raw
  requests exceptions; exception chaining is suppressed at the live boundary.
  A failure never switches to JSON or an empty calendar. Successful Google reads
  produce source=live; JSON results remain source=simulated.
- AppointmentService receives the existing manager, client, strategy and a
  doctor-ID-to-working-intervals dictionary through its constructor. Inputs use
  exact registered Patient/Doctor objects and clinic-local naive datetimes.
  Availability reuses the M2 pure calculation; mutation registers through the
  manager, with shared exact-object membership and M1 conflict checks. Explicit
  booking accepts only the requested start/duration and never invokes a strategy
  to silently replace them.
- WaitingRequest(request_id, patient, doctor, window_start, window_end,
  duration_minutes=30) has read-only fields, a positive integer duration (not bool)
  and a positive naive window long enough for that duration. Enqueue validates
  current registration and unique pending request IDs across all doctor queues,
  without calendar access. Queues are local deques owned by this service instance.
- M5 project cancellation policy: only scheduled appointments can be cancelled.
  Unknown IDs, in_progress and terminal statuses are rejected before calendar IO
  or mutation. A valid cancellation remains cancelled even if backfill reads fail.
  With no pending requests, no calendar read is needed. Otherwise a failed or
  incomplete read defers backfill and preserves the queue; it never creates an
  empty-calendar fallback.
- M5 replacement policy: start exactly at the cancelled start, fit entirely within
  its original freed interval, and fit inside the waiting request's acceptable
  window. Shorter replacements are allowed; longer ones are skipped. The first
  currently eligible request is booked after all usual working-hour, grid,
  external and local checks. Skipped requests retain relative order, other doctor
  queues are untouched, and at most one replacement is created. The selected
  request is removed only after successful manager registration. The cancelled
  appointment stays as history. A monotonic BACKFILL counter checks every proposed
  ID against existing appointments; IDs are not based on collection length.
- M6 demonstrates the completed local workflow. M7/M8 implementations are now integrated; real-provider evidence and final
  Technical Lead/release approval remain separate requirements.

The M5 public service contracts are:

| Method | Result and side effects |
|---|---|
| `fetch_snapshot(patient, doctor, window_start, window_end)` | Complete snapshot; performs one client call using bounds padded by 15 minutes on each side |
| `available_slots(patient, doctor, window_start, window_end, duration_minutes=30)` | Sorted `(start, end)` list after a complete read; no clinic mutation |
| `available_slots_using_snapshot(patient, doctor, window_start, window_end, snapshot, duration_minutes=30)` | Same list with no IO or mutation, using current local appointments |
| `suggest_slot(patient, doctor, window_start, window_end, preferred_start, duration_minutes=30)` | Injected strategy's valid slot, or None for a valid empty result; reads but does not book |
| `book(appointment_id, patient, doctor, start, duration_minutes=30)` | Registered Appointment; fetches before delegating to local recheck/registration |
| `book_using_snapshot(appointment_id, patient, doctor, start, snapshot, duration_minutes=30)` | Registered Appointment with no IO; rechecks membership, IDs, availability and final manager invariants |
| `add_waiting_request(request)` | The enqueued WaitingRequest; no IO |
| `waiting_requests(doctor_id)` | Read-only FIFO tuple; empty/unknown queue gives an empty tuple |
| `cancel(appointment_id)` | Dictionary with `cancelled_appointment`, `replacement` (Appointment or None) and `backfill_status` |

`backfill_status` is `filled`, `unfilled` (valid cancellation with no eligible
replacement), or `deferred` (cancellation succeeded but external availability is
unknown). Invalid business input, membership, duplicate IDs or unavailable
explicit slots raise ValueError; wrong model/contract types raise TypeError.
AvailabilityUnknownError means a read or snapshot is unusable, with no booking
and no switch to another source. Snapshots are validated/copied through the
existing CalendarSnapshot constructor and must cover the requested interval plus
its gaps. A source flag is preserved, not relabelled.

For Yotam, the prepared pure entry point is available_slots_using_snapshot with
preloaded per-doctor snapshots and registered participants; its output is the M2
slot list. For the shared coordinator, fetch_snapshot belongs before the Lock and
book_using_snapshot belongs inside the protected check-and-insert section, on
the same manager/service. All concurrent writers must use the M8 common
coordinator. The M5 service itself is not synchronized; methods such as book and
cancel are orchestration paths that may read externally. M8 supplies BookingCoordinator around book_using_snapshot; M7 supplies the
independent read-only collectors. A snapshot is not an atomic transaction
against Google Calendar. See m7-async.md and m8-threading.md for those interfaces.
