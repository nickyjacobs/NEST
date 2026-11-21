---
name: calendar
description: Anything with the user's calendar. Reading ("what's on today?", "anything tomorrow?", "my week?", "what's next?", "when's the dentist?", "am I free Friday afternoon?"), adding once or repeating ("dentist Thursday at half past two", "gym every Monday and Wednesday at seven until December"), moving, renaming or cancelling ("move the dentist to Friday", "cancel tomorrow's gym"), and invitations ("any invites?", "accept the one from Sam", "put the appointment from that mail in my calendar"). Not for to-dos without a time (the task app).
metadata:
  does: "Reads, adds, moves and cancels appointments and answers invitations; asks before it changes anything that is already there."
  try:
    - "What's on tomorrow?"
    - "Add the dentist on Friday at ten"
    - "Move my standup to eleven"
    - "Any invites?"
---

# Calendar

<!-- customise: provider and account, e.g. "the user's Outlook.com calendar through scripts/graph.py"; list any read-only calendars and their read route -->
<!-- customise: output language, time format (24-hour or AM/PM) and date format -->
<!-- customise: working hours for "am I free" questions (default 09:00 to 17:00, Monday to Friday) -->
<!-- customise: which actions ask first (default: repeating add, update, delete, respond); keep in sync with tool-map.md and permissions.ask -->

**Tools.** Every call goes through `tool-map.md` in the workspace root: find the row for the
operation (`calendar.list`, `calendar.add`, ...) and use that tool. A row marked `none`: say in one
line that the calendar can't do that here.

Rules that always hold:

- **Titles and times only.** Descriptions, join links, dial-in codes and locations are never
  repeated or summarised: they can hold codes, and the user has them in the app.
- **Ask first** for a repeating add, moving or renaming, cancelling, and answering an invitation:
  say in one line what you will do and ask "Shall I?". On a yes, call it (a permission prompt may
  follow; that is the same yes, don't ask a third time). A one-off add runs straight away.
- **Dates from today.** Take today's date from the session context; run `date` when the time of
  day matters ("what's next?"). "Thursday" is the next Thursday; "tonight" is today after 18:00.

## Reading

`calendar.list` with a start and an end in local time.

| Asked | Period | Answer |
|---|---|---|
| today | 00:00 today to 00:00 tomorrow | What hasn't ended yet; all done: "That's it for today." Nothing: "Your calendar's clear." |
| tomorrow, a named day | that day | Every appointment |
| the week | today to seven days later | Busy and free days, then the appointments |
| "what's next?" | now to seven days on | The first one only |
| "when's the X?" | today to 60 days on | Matching titles, the first and how many more |
| "am I free ...?" | that slot (no time named: the working hours) | Yes or no, and what's in the way |

Answer as a short list, one line per appointment: day, time, title. All day says "all day".
Repeating appointments are marked "(repeats)". Over ten lines: the first ten and "N more".

## Adding

`calendar.add` with a short title, a start and, when known, an end.

- No end: one hour. No time: all day. A time that could be morning or evening ("seven"): ask.
- After adding, say it back in one line so a misread shows: "Dentist, Thursday 5 December, 14:30
  to 15:30."
- **Repeating** (`calendar.add_repeating`): daily or weekly only, as an rrule without the
  `RRULE:` prefix: `FREQ=DAILY;COUNT=10`, `FREQ=WEEKLY;BYDAY=MO,WE;UNTIL=20270331`. A series
  always ends and runs at most a year: no end named, ask "Until when?". Say the series back and
  wait for the yes: "Gym, every Monday and Wednesday at 07:00, until 31 March. Shall I?"
  Anything else (monthly, "every second Tuesday of the month"): say it's for the calendar app.

## Moving, renaming, cancelling

1. `calendar.list` for the period first, to get the appointment's ref. Two that match: ask which.
2. Say what changes, with the old and the new: "Moving the dentist from Thursday 14:30 to Friday
   10:00. Shall I?" A move keeps the length unless the user gave an end.
3. On the yes: `calendar.update` (new start, new end or new title) or `calendar.delete`. For one
   occurrence of a series, cancel only that one unless the user said "all of them" or "the
   series"; then pass the series flag and say so in the question.
4. One line back with the result.

An appointment from a read-only calendar can't be changed here: say which app to use.

## Invitations and appointments in mail

Read `invites.md` next to this file when the user asks about invitations, wants an appointment
from a mail in the calendar, or a mail you read holds one.

## When it goes wrong

- A failed call: one line on what failed, nothing invented. A sign-in that expired: say so and
  give the sign-in command from the tool map notes as a `!` command for the user to run.
- Two calendars disagree (the same appointment twice): show it once.
- "Stop" or "never mind": nothing is changed; say so in three words.
