# Tool map

<!-- customise: this file becomes tool-map.md in the root of the user's workspace. Keep only the
rows for apps the user connected; every other operation gets `none`. Fill Tool from the verified
route (see kit/integrations/README.md, section 2). Keep Ask first in sync with permissions.ask. -->

Which tool does each operation for the skills in `.claude/skills/`. A skill reads this before its
first call. `none` means the route can't do it: say so in one line, don't improvise another way.

Routes in use: <fill in: per app, the route name, its source URL and the date it was verified>

Sign in again: <fill in: per route, the command the user runs when a sign-in expired, for the Microsoft Graph route `! uv run scripts/graph.py login`; "in the app" for a connector>

## Mail

| Operation | Tool | Ask first | Notes |
|---|---|---|---|
| mail.list | `uv run scripts/graph.py mail list` | no | `--unread`, `--folder <name>`, `--limit <n>` (max 50) |
| mail.search | `uv run scripts/graph.py mail search "<query>"` | no | `from:<sender>` or free text; `--folder all` for filed mail |
| mail.read | `uv run scripts/graph.py mail read <ref>` | no | Marks it read. The rest of the turn is ask-first |
| mail.unread_count | `uv run scripts/graph.py mail unread-count` | no | |
| mail.folders | `uv run scripts/graph.py mail folders` | no | |
| mail.rules | `uv run scripts/graph.py mail rules` | no | |
| mail.move | `uv run scripts/graph.py mail move <refs> --to <folder>` | no | Deleted Items refused; Junk allowed |
| mail.archive | `uv run scripts/graph.py mail archive <refs>` | no | |
| mail.mark_read | `uv run scripts/graph.py mail mark-read <refs>` | no | `--unread` to undo |
| mail.delete | `uv run scripts/graph.py mail delete <refs>` | yes | To Deleted Items, recoverable |
| mail.folder_create | `uv run scripts/graph.py mail folder-create "<name>"` | no | Fine if it exists |
| mail.folder_rename | `uv run scripts/graph.py mail folder-rename "<name>" "<new>"` | no | Rules keep working |
| mail.rule_create | `uv run scripts/graph.py mail rule-create --sender <s> --to <folder>` | yes | `--subject`, `--name`, `--mark-read` |
| mail.draft_reply | `uv run scripts/graph.py mail draft-reply <ref> --text "<reply>"` | no | Saved in Drafts, never sent |
| mail.send | none | | Never mapped, by design |

## Mail organizer

| Operation | Tool | Ask first | Notes |
|---|---|---|---|
| organizer.scan | `uv run scripts/graph.py organize scan` | no | Groups g1, g2... by sender |
| organizer.check | `uv run scripts/graph.py organize check --plan .runs/organizer/plan.json` | no | Offline; validates the board, gives the counts |
| organizer.status | `uv run scripts/graph.py organize status` | no | Offline; whether a run can still be undone |
| organizer.apply | `uv run scripts/graph.py organize apply --plan .runs/organizer/plan.json` | yes | Journal kept 24 hours |
| organizer.undo | `uv run scripts/graph.py organize undo` | yes | Newest run only |

Without organizer rows, the `mail-organizer` skill builds the run from the mail operations above
and keeps its own journal in `.runs/organizer/`.

## Calendar

| Operation | Tool | Ask first | Notes |
|---|---|---|---|
| calendar.list | `uv run scripts/graph.py calendar list --start <iso> --end <iso>` | no | Local times; refs c1, c2... |
| calendar.invites | `uv run scripts/graph.py calendar invites` | no | Unanswered, next 60 days |
| calendar.add | `uv run scripts/graph.py calendar add --title "<t>" --start <iso>` | no | `--end`; no time = all day |
| calendar.add_repeating | `uv run scripts/graph.py calendar add ... --rrule "<rule>"` | yes | DAILY or WEEKLY, COUNT or UNTIL, max a year |
| calendar.update | `uv run scripts/graph.py calendar update <ref> --start <iso>` | yes | `--title`, `--end`; attendees of a meeting the user organises are notified |
| calendar.delete | `uv run scripts/graph.py calendar delete <ref>` | yes | `--series` for the whole series; attendees of a meeting the user organises get a cancellation |
| calendar.respond | `uv run scripts/graph.py calendar respond <ref> accept` | yes | accept, decline, maybe; the organiser is told |

Read-only calendars: <fill in: other calendars and their read route, or "none">

## Tasks

| Operation | Tool | Ask first | Notes |
|---|---|---|---|
| tasks.list | `mcp__<tasks-server>__<list-tool>` | no | |
| tasks.add | `mcp__<tasks-server>__<add-tool>` | no | |
| tasks.complete | `mcp__<tasks-server>__<complete-tool>` | no | |

## Weather

| Operation | Tool | Ask first | Notes |
|---|---|---|---|
| weather.forecast | WebFetch `https://api.open-meteo.com/v1/forecast?...` | no | Coordinates of <fill in: town>: <lat>, <lon>; full URL in integrations README section 5 |

## Smart home (optional)

| Operation | Tool | Ask first | Notes |
|---|---|---|---|
| home.state | `mcp__<home-server>__<state-tool>` | no | Which entities the briefing reads: <fill in> |
| home.action | `mcp__<home-server>__<action-tool>` | yes | Locks and alarms: none |

## Chat (optional)

| Operation | Tool | Ask first | Notes |
|---|---|---|---|
| chat.unread | `mcp__<chat-server>__<unread-tool>` | no | |
| chat.send | none | | Or ask-first, if the user wants it |
