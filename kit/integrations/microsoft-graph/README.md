# Microsoft Graph route (Outlook mail and calendar)

`graph.py` is a single-file Python CLI (PEP 723, run with `uv run`) for an Outlook.com or
Microsoft 365 mailbox and calendar, proven on a real inbox before it went into NEST. It
covers every mail, organizer and calendar operation in `../tool-map.example.md`.

What it will never do, by design:

- **Send mail.** The sign-in requests `Mail.ReadWrite`, `MailboxSettings.ReadWrite` and
  `Calendars.ReadWrite`, never `Mail.Send`, and the code has no send call. Graph's
  `POST /me/messages/{id}/send` requires `Mail.Send`, so the token cannot send a message. A reply
  is `createReply`: a draft in Drafts. Two things do reach other people, and the skills ask
  first for both: answering an invitation tells the organiser, and cancelling or moving a
  meeting the user organises makes Outlook notify its attendees. `MailboxSettings.ReadWrite`
  also covers inbox rules. This script only ever writes rules that move mail to a folder or
  mark it read; it has no forward or redirect action. Keep the token cache out of reach of
  other tools all the same (the deny rule in `../permissions.example.json`).
- **Move mail into Deleted Items** or point a rule at it. That is checked by folder id, so a
  translated display name cannot slip through. `mail delete` is the only way there (recoverable).
- **Write a broad rule.** The organizer builds rule strings only from senders its own scan saw;
  sender text in a plan is ignored.

## Setup (once, at the keyboard)

### 1. Register an app in Microsoft Entra

Verified 2026-11-21 against:
[Register an application](https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-register-app),
[Desktop app registration](https://learn.microsoft.com/en-us/entra/identity-platform/scenario-desktop-app-registration),
[Device authorization grant](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-device-code).

1. Sign in to the [Microsoft Entra admin center](https://entra.microsoft.com) with the same
   Microsoft account (a personal account gets a default directory).
2. **Entra ID > App registrations > New registration.** A name the user recognises, such as
   `<assistant name> mail`.
3. **Supported account types:** *Personal accounts only* for Outlook.com, Hotmail and Live
   mailboxes. A work or school mailbox needs *Single tenant* and, often, the tenant admin's
   consent: ask the user whether their employer allows that before trying.
4. No redirect URI and no client secret. **Register.**
5. Copy the **Application (client) ID** from the Overview page. It is not a secret, but keep it
   out of the wiki anyway.
6. **Authentication > Advanced settings > Allow public client flows: Yes > Save.** The device
   code flow needs this.
7. API permissions are requested at sign-in; nothing to add here. Do not add `Mail.Send`.

### 2. Put the script in the workspace and sign in

```bash
cp <nest>/kit/integrations/microsoft-graph/graph.py scripts/graph.py
uv run scripts/graph.py login --client-id <Application (client) ID> --timezone <IANA zone, e.g. Europe/Berlin>
```

It prints a link and a code; the user opens the link, enters the code, signs in and accepts the
three permissions. For a work account add `--tenant organizations` (or the tenant id). Then:

```bash
uv run scripts/graph.py status
uv run scripts/graph.py mail list --limit 3
```

`login` is interactive: in a Claude Code session the user runs it themselves with
`! uv run scripts/graph.py login ...`, so the code lands in the conversation and no one types it
for them.

### 3. Where its files live

Outside the workspace, in the OS user data dir (`platformdirs.user_data_dir("nest-graph")`):

| OS | Folder |
|---|---|
| macOS | `~/Library/Application Support/nest-graph/` |
| Linux | `~/.local/share/nest-graph/` |
| Windows | `%LOCALAPPDATA%\nest-graph\` |

Files: `config.json` (client id, tenant, timezone), `token-cache.json` (0600, refreshes itself),
`refs.json` (short refs), `organizer/scan.json` and `organizer/run-*.json` (journals). Put a
`Read(<that folder>/**)` deny rule in the workspace settings (see `../permissions.example.json`)
so Claude's file tools never read the token cache. `NEST_GRAPH_HOME` overrides the folder (tests).

## Commands

Every command prints JSON. Refs (`m1`, `c1`) are short names for Graph's long ids; they are kept
between runs and are immutable ids, so a ref still works after its mail moved.

| Area | Commands |
|---|---|
| `mail` | `list [--folder F] [--unread] [--limit N]`, `search "<q>" [--folder F\|all]`, `read <ref>`, `unread-count`, `folders`, `rules`, `move <refs> --to F`, `archive <refs>`, `mark-read <refs> [--unread]`, `delete <refs>`, `folder-create "<name>"`, `folder-rename "<name>" "<new>"`, `rule-create --sender S [--subject S] --to F [--name N] [--mark-read]`, `draft-reply <ref> --text "<t>" \| --text-file <path>` |
| `calendar` | `list --start <iso> --end <iso>`, `invites [--days N]`, `add --title T --start <iso> [--end <iso>] [--rrule R]`, `update <ref> [--title T] [--start <iso>] [--end <iso>]`, `delete <ref> [--series]`, `respond <ref> accept\|decline\|maybe` |
| `organize` | `scan`, `check --plan <file>`, `apply --plan <file>`, `undo`, `status` |

Times are local (`2026-12-03T14:30`, or a date for all day) in the configured timezone.

### Limits and checks

| Rule | Value | Where |
|---|---|---|
| Mails per list or search | 50 | `MAX_LIST` |
| Mails per action | 100, moves in JSON batches of 20 ([Graph limit](https://learn.microsoft.com/en-us/graph/json-batching)) | `MAX_REFS`, `BATCH_SIZE` |
| Repeats | `FREQ=DAILY` or `WEEKLY`, optional `INTERVAL` 1 to 4 and `BYDAY`, `COUNT` or `UNTIL` required, at most 366 days | `check_rrule` |
| New folders per organizer run | 30 | `MAX_NEW_FOLDERS` |
| Senders per rule | 60 | `MAX_RULE_SENDERS` |
| Scan age before apply | 2 hours | `SCAN_MAX_AGE_SECS` |
| Undo window | 24 hours, newest run only | `UNDO_SECS` |
| Never a target | Inbox, Deleted Items, Sent, Drafts, Outbox, Conversation History | `NOT_TARGETS` |

Grouping: a sender at a freemail provider (`FREEMAIL`) groups per address, everyone else per
registrable domain (`n.shop.com` and `shop.com` are one group); Apple Hide My Email relays are
unwrapped to the real domain.

### The organizer plan

`organize check` and `apply` read a JSON plan built from the scan's group ids:

```json
{"buckets": [
  {"folder": "Shopping", "groups": ["g1", "g4"], "rule": true},
  {"folder": "Travel", "groups": ["g7"], "rule": false, "note": "Bookings and boarding passes"}
]}
```

An existing folder is matched by name; a new folder needs a `note` (what it is for). `check`
refuses a group in two folders, an unknown group, a protected target, a `/` in a new folder
name, more than 30 new folders and a rule over 60 senders, and reports what moves, what stays in
the inbox and which rules are new or extended. Groups not in any bucket stay in the inbox.
`apply` re-checks, writes the journal after every step (so a failed run can still be undone),
and lists the new folders with their notes so the skill can add them to `mail-folders.md`.

## Tests

`kit/scripts/tests/test_graph_logic.py`, no network:

```bash
uv run --with pytest --with pyyaml --with msal --with platformdirs pytest -q kit/scripts/tests/test_graph_logic.py
```

Sources for Graph behaviour (read 2026-11-21):
[message: move](https://learn.microsoft.com/en-us/graph/api/message-move),
[createReply](https://learn.microsoft.com/en-us/graph/api/message-createreply),
[message: send](https://learn.microsoft.com/en-us/graph/api/message-send) (needs `Mail.Send`),
[messageRulePredicates](https://learn.microsoft.com/en-us/graph/api/resources/messagerulepredicates),
[recurrenceRange](https://learn.microsoft.com/en-us/graph/api/resources/recurrencerange),
[calendarView](https://learn.microsoft.com/en-us/graph/api/user-list-calendarview) (times without
an offset are read as UTC, so the CLI always sends an offset),
[immutable ids](https://learn.microsoft.com/en-us/graph/outlook-immutable-id).
