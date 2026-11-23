<sub>[Docs](../README.md) · [What to expect](../guide/what-to-expect.md) · [Updating](../guide/updating.md) · [FAQ](../guide/faq.md) · [nest.json](../reference/nest-json.md) · [Hooks](../reference/hooks-notes.md) · [Releasing](../project/releasing.md) · [Backlog](../project/backlog.md)</sub>

# nest.json

One file at the root of your workspace holds its settings. Every key is optional; a workspace
without the key uses the default. Your assistant can change these for you: just ask.

**On this page:** [nest](#nest) · [session_guard](#session_guard) · [size_ceiling](#size_ceiling) · [morning_nudge](#morning_nudge) · [secret_scan](#secret_scan) · [blind_seats](#blind_seats) · [wiki_backup](#wiki_backup) · [Other files](#other-files)

```json
{
  "nest": {"version": "1.1.0", "update_check": true},
  "session_guard": {"live_minutes": 30, "keep_days": 14},
  "size_ceiling": {"lines": 400},
  "morning_nudge": {"before": "11:00", "text": "say good morning for your briefing"},
  "secret_scan": {"soft_skip": ["wiki/_inbox/**"], "private_terms": "warn"},
  "wiki_backup": {"git_dir": "~/.my-wiki.git", "branch": "main"}
}
```

## nest

The stamp that makes updates safe. Written by the setup and by `/nest-update`; you normally
change only `update_check`. Read by `scripts/nest_update.py`.

| Key | Default | Meaning |
|---|---|---|
| `version` | set by the setup | The NEST release this workspace is level with |
| `source` | the NEST repository | Where releases come from: a git URL or a folder |
| `update_check` | `true` | `false` silences the session-start line about new releases |
| `skipped_version` | none | A release you chose to skip; the line stays quiet until the next one |
| `files` | set by the setup | Per installed file: its kit file, whether it is a `copy` or `adapted`, the hash of the kit original, and the release that original came from. The kit file can have another folder name than yours: after you kept the old name of a part NEST renamed, `.claude/skills/idea/SKILL.md` is recorded against `kit/skills/verdict/SKILL.md` |
| `declined` | `{}` | Changes you said no to, so they are not offered again |
| `renaming` | none | Only while a move to a new name is unfinished: the old kit path and the new one. `/nest-update` reads it to carry on or to undo, and removes it when the move is done |

## session_guard

Read by `scripts/session_guard.py`.

| Key | Default | Meaning |
|---|---|---|
| `live_minutes` | `30` | How long after its last activity another session can still be named as a second session; it is named only when it was active while yours was already open |
| `keep_days` | `14` | How long the files with your own messages stay in `.claude/.session/` |
| `words_chars` | `8000` | How much of your own words is handed to a conversation summary: your first message and the newest ones, at most 9500 characters |
| `plan_author` | `"claude"` | The author value on a plan note in the inbox; `""` leaves the field out |

## size_ceiling

Read by `scripts/session_context.py`. The files that load in every session (`CLAUDE.md`,
`CLAUDE.local.md`, rules without a `paths` filter) cost attention each time. Above the ceiling
the session-start line says so.

| Key | Default | Meaning |
|---|---|---|
| `lines` | `400` | The ceiling in lines; `0` turns the check off |

## morning_nudge

Read by `scripts/session_context.py`. Only with the morning-briefing skill installed.

| Key | Default | Meaning |
|---|---|---|
| `before` | none | An hour such as `"11:00"`: a new session before it ends its start line with the text |
| `text` | `"say good morning for your briefing"` | The reminder, in your language |

## secret_scan

Read by `scripts/validate.py`. Globs are relative to the workspace root; `**` matches any depth.

| Key | Default | Meaning |
|---|---|---|
| `skip` | `[]` | Files that are not scanned at all |
| `soft_skip` | `[]` | Files where soft warnings (paths, email addresses, private IPs) stay silent; real secrets still block |
| `private_terms` | `"warn"` | `"block"` refuses a write that contains a term from `.claude/sensitive-terms.txt` |

## blind_seats

Read by `scripts/blind_seat_guard.py`. Only with The Council or The Architects installed.

| Key | Default | Meaning |
|---|---|---|
| `run_dir` | `".runs"` | The folder that holds the run files |
| `seats` | the three built-in seats | Agent name to the run file names it may read; replaces the built-in table |

## wiki_backup

Read by `scripts/wiki_backup.py`, the session-start line and the scan after a shell command. Only when your wiki has its own
backup repository.

| Key | Default | Meaning |
|---|---|---|
| `git_dir` | `~/.<workspace>-wiki.git` | Where the backup's git data lives, outside the wiki |
| `branch` | `"main"` | The branch that is pushed |

## Other files

| File | Holds |
|---|---|
| `wiki.config.json` | The shape of your wiki: sections, kinds, status words, authors |
| `.claude/settings.json` | Claude Code's own settings: permissions and the hooks |
| `.claude/sensitive-terms.txt` | Words that must never land in a committed file; you fill it yourself, it is not committed |
| `.claude/lessons.json` | One-line lessons your assistant recorded, each with the step it applies to |
