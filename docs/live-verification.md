# Explicit live availability verification — pending

No real Google call was run in M6. The Google implementation and mocked tests
are complete; real-provider verification still requires configuration. These
instructions are for a later, explicitly requested human setup and run. M6 did
not create resources, change calendar visibility or obtain credentials.

## Setup for the existing command

1. Use a separate calendar containing **synthetic events only**, never a personal
   or patient calendar. In the Google Calendar web UI, next to Other calendars,
   choose Create new calendar and use Asia/Jerusalem. Google's
   [calendar creation guide](https://support.google.com/a/users/answer/13293412?hl=en)
   describes this flow.
2. In that calendar's Settings and sharing, under Access permissions for events,
   select Make available to public and See all event details. The client needs
   readable event intervals; free/busy-only access is rejected. A school account
   may prohibit public sharing, which is a configuration blocker. See Google's
   [public calendar instructions](https://support.google.com/calendar/answer/37083?hl=en).
3. In the same dedicated calendar, add a synthetic event on **2026-10-29,
   10:00-10:30 Asia/Jerusalem**, shown as Busy, with no other busy events in the
   demonstration window. This is a known test event, not real medical data.
4. Copy the calendar's actual Calendar ID from Settings and sharing > Integrate
   calendar. Use the ID, not a sharing URL, event ID or `primary`. Google's
   [Calendar ID instructions](https://support.google.com/calendar/answer/44105?hl=en)
   identify that setting.
5. Select a Google Cloud project and enable **Google Calendar API** under APIs &
   Services > Library. Google's [API enablement section](https://developers.google.com/workspace/calendar/api/quickstart/python#enable_the_api)
   describes this step. The rest of that OAuth quickstart is not this project's
   authentication flow.
6. In that project's APIs & Services > Credentials, use Create credentials > API
   key. Restrict the key to Google Calendar API; any application restriction must
   permit the local Python caller. This project uses an API key to read public
   data; it does not require OAuth client files or extra Google SDKs. See the
   [official API key instructions](https://developers.google.com/workspace/guides/create-credentials#api_key).
7. Install dependencies as in README. Copy the placeholder-only `.env.example`
   to an ignored local `.env` **if one does not already exist**, then edit locally:

   ```dotenv
   GOOGLE_CALENDAR_API_KEY=REPLACE_LOCALLY_WITH_YOUR_KEY
   GOOGLE_CALENDAR_MAPPING='{"D001":"REPLACE_WITH_DEDICATED_CALENDAR_ID"}'
   REQUEST_TIMEOUT=10
   ```

   These are placeholders, not credentials. Do not paste keys into chat, commit
   .env, print configuration or enable HTTP debug logs. The mapping is JSON,
   and timeout must be finite and positive. Existing process environment values
   override .env values, so remove stale overrides locally if needed. Offline
   mode never reads .env.

## Execute only when live verification is authorized

From the project root, after setup:

```bash
.venv/bin/python -m smart_clinic.verify_calendar --doctor-id D001 \
  --start 2026-10-29T09:00:00 --end 2026-10-29T12:00:00
```

The command calls `events.list` read-only. Its explicit working hours equal the
requested window, its verification patient is free, and it has no local bookings.
It queries 08:45-12:15 with the date-specific Jerusalem offset, covering the gap
checks. It does not create an AppointmentService booking or run a full live
booking/waiting-list workflow.

For exactly the known busy event above, a successful response should print:

- `source=live` and a normalized busy interval 10:00-10:30.
- `blocked_slots`: 30-minute visits starting 09:30, 09:45, 10:00, 10:15, 10:30.
- `available_slots`: starts 09:00, 09:15, 10:45, 11:00, 11:15, 11:30.

All starts above are on 2026-10-29, and each visit lasts 30 minutes. The command
prints datetime tuples rather than this shortened notation. Missing mapping,
invalid configuration or provider failure prints a safe error, exits 1 and never
falls back to simulated or empty data. Additional calendar events legitimately
change the result; use the controlled calendar to make the expectation comparable.

Later evidence must record the command/window, actual source label, busy/slot
decision and exit status without keys or authenticated URLs. A mock's `live`
label or a successful Git push is not real-provider evidence. A fetched snapshot
does not prevent another calendar user changing events afterward.
