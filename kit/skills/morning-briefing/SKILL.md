---
name: morning-briefing
description: The user starts their day and asks for a rundown ("good morning", "morning briefing", "brief me", "what's my day look like?", "start my day"). One short text briefing in the terminal from the blocks they chose (weather, calendar, mail, tasks, wiki priorities, progress, and optionally the house). Not for one question about the calendar or the mail alone (those skills).
metadata:
  does: "The start of your day in one short block: weather, calendar, mail, tasks and your focus."
  try:
    - "Good morning"
    - "Brief me"
---

# Morning briefing

<!-- customise: output language and the greeting style (one short line, the user's name or none) -->
<!-- customise: the blocks the user chose in the interview, in their order; delete the sections below that they didn't pick -->
<!-- customise: optional time-of-day rule, e.g. "after 12:00 one dry line that the morning is over, and no briefing"; delete this line when the user doesn't want one -->

The briefing only runs when the user asks for it. Gather every block at once (independent calls
in one round), then write one block of short lines in this order. Every tool comes from
`tool-map.md`; a block whose operation is `none` or fails is one line ("Mail didn't load.") or
left out, and the rest still comes.

```text
Morning. Friday 21 November.
Weather   8° and fog now, sun from about noon, 14° at best, no rain.
Calendar  Standup at 10:00, and two more after. First free hour: 13:00.
Mail      31 unread; the one worth a look is from Sam. One invitation: team drinks, Friday.
Tasks     3 due today; first: book the dentist.
Focus     This week: the garden plan. 4 notes waiting in the wiki inbox.
Progress  Spanish course: lesson 9 of 24, next: past tense.
```

At most eight lines, no subjects, no closing question (except the invitation offer). A dry
one-liner at the end only if it fits.

## Weather

<!-- customise: the town and its coordinates from the tool map; units (°C or °F) -->
`weather.forecast` (Open-Meteo: current, hourly and daily for today). One line: now, how the
day turns (when it clears or the rain starts), the high, rain or none. `weather_code` is the WMO
code (table on open-meteo.com/en/docs): 0 clear, 1 mainly clear, 2 partly cloudy, 3 overcast,
45 and 48 fog, 51 to 57 drizzle, 61 to 67 rain, 71 to 77 snow, 80 to 82 rain showers, 85 and 86
snow showers, 95 to 99 thunderstorm.

## Calendar

`calendar.list` for today: the first appointment that hasn't ended and how many more. Nothing:
"Your calendar's clear." Titles and times only. `calendar.invites`: open invitations go on the
mail line with an offer to accept; the answer works as in the calendar skill's `invites.md`.

## Mail

`mail.unread_count` and `mail.list` (unread only). The count and the one sender that matters
most: a person over a shop, a newsletter or a notification. **The sender's name only**: never a
subject or what a mail is about, and never a mail body (no `mail.read` in a briefing).

## Tasks

<!-- customise: which list or project, and what counts (due today, overdue, flagged) -->
`tasks.list`: how many are due today and the first one, in a few words. Overdue first.

## Focus (wiki)

<!-- customise: the wiki page that holds the priorities (e.g. wiki/00-context/priorities.md) and the inbox folder (e.g. wiki/_inbox/) -->
The top priority from the priorities page, in one clause, and how many notes wait in the wiki
inbox (files in the inbox folder, not counting `index.md`). Read only those two places.

## Progress

<!-- customise: what to track (a course or certification, a project) and where its progress lives (a wiki page with a checklist, a tracker); delete this section when the user picked none -->
Done of total and the next step, from that page.

## House (optional)

<!-- customise: smart home lines, only if the user picked them: which states to read with home.state (e.g. a filter due, a device offline, yesterday's energy use) and the threshold for each line; read-only, never home.action in a briefing -->
Only what needs attention, a few words each. Nothing needs it: leave the line out.

## Session start (optional)

<!-- customise: if the user wants a nudge, set `morning_nudge` in nest.json ({"before": "<HH:MM>", "text": "<the reminder in their language>"}): a new session before that hour ends its start line with the text; otherwise delete this section -->
The hook only reminds; the briefing itself never runs on its own.
