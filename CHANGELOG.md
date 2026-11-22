<p align="center">
  <img src="assets/release-banner.png" alt="NEST: New Environment Setup Toolkit" width="520">
</p>

# Changelog

Every release of NEST, newest first. Each one starts with a sentence and a **For your workspace**
section in plain words: what it means if you already built a workspace with an earlier release.
`/nest-update` in your workspace reads that section to you.

| Release | Date | In short |
|---|---|---|
| [1.0.0](#100---2026-11-22) | 2026-11-22 | The first release: an interview that builds your own Claude Code workspace, and a way to keep it up to date afterwards. |

<sub>Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) · Versions: [Semantic Versioning](https://semver.org/) · How a release is made: [docs/project/releasing.md](docs/project/releasing.md)</sub>

## [Unreleased]

### 🏠 For your workspace

- **Undo is safer.** `/nest-update undo` now tells you first which update it puts back and
  which files that concerns. It always means the last update: asking twice no longer reaches
  back to an earlier one.
- **A typing mistake in `nest.json` no longer costs you your settings.** The update stops and
  names the line instead of starting over with an empty file.
- An update you brought over in parts no longer shows you changes you already have.
- When your workspace could not look for a new release (no internet), it tries again the next
  day instead of a week later.
- When NEST changes an example that something of yours was made from, such as your wiki
  settings, the update now tells you.

### 🔧 Changed

- `nest_update.py restore` has `--list` and `--dry-run`. The plan has a new status,
  `reference`, for a changed example file without a fixed place in a workspace.

### 🐛 Fixed

- `nest_update.py restore --force` after a `restore` put back an older update and wrote over
  the user's own changes. It now puts back only the files the first `restore` left alone.
- `restore` took an older update when the last one changed no files. An update that only
  declined parts or set the version now has its own history folder.
- `restore` that failed halfway (a read-only file, a file open in another program) could not be
  run again and overwrote the copies in `undone/`. It now reports the file, keeps the first
  copy, and picks up where it stopped.
- A `nest.json` that is not valid JSON was read as empty, after which `stamp` wrote over every
  other setting in it. A byte order mark at the start of the file is read correctly.
- `diff` always started at the workspace's version, also for a file that was already brought
  over. The stamp now records per file which release it came from.
- A deleted pre-commit hook came back without its executable bit, so git skipped it. `apply
  <path>` now brings back a deleted copy file and keeps the mode.
- The two-second limit of the update check at session start did not hold when git's helper
  process kept running (seen on macOS as a leftover process, expected on Windows as a long
  wait). The whole process group is stopped now.
- A workspace built from a version newer than the newest release got "up to date" from
  `check` and an error from `plan`. Both now say it is ahead.
- Smaller: a missing `git` is named as such, a file of the other team size is no longer
  offered as new, a path spelled with other capitals in `backup` no longer blocks `mark`, an
  undo leaves no empty folders, and the fetched copy of a release follows a changed `source`.

---

## [1.0.0] - 2026-11-22

> **In short:** The first release: an interview that builds your own Claude Code workspace, and a way to keep it up to date afterwards.

### 🏠 For your workspace

- This is the first release, so there is nothing to bring over.
- From now on your workspace tells you when a newer release is out. `/nest-update` then shows
  what is new in plain words and changes only the parts you pick.

### ✨ Added

- **The setup prompt.** `SETUP.md`: a machine check, an interview in six blocks, a table that
  says where every answer lands, build steps with a check each, a final test round and a wrap-up
  with first tasks. It keeps its progress in a state file, so you can stop and continue in a
  later session.
- **Skills.** Wiki inbox, ingest, query and maintenance, Obsidian Markdown and Bases, idea (The
  Council), blueprint (The Architects), career, study inbox, research, session end, writing
  style, release, calendar, mail, mail organizer, morning briefing and a skill builder. You
  choose them one by one.
- **Agents.** The Council and The Architects in a full and a light size, a researcher and a
  read-only security reviewer.
- **Guards.** A secret scan before and after every write, a session-start line, a pre-commit
  scan, a guard that keeps the read-only reviewer read-only, and a guard that keeps the blind
  seats of the two teams inside their own run file.
- **Session guards.** Your own messages are kept word for word across a compaction, the
  assistant is told when a second session is open in the same folder, recorded lessons are shown
  when they apply, and an approved plan can be copied into the wiki inbox.
- **Updates.** `nest.json` records which release a workspace was built from. The `nest-update`
  skill and `nest_update.py` bring over a newer release: untouched files are replaced, adapted
  files are merged with your changes kept, every file is backed up first, and one command puts
  everything back.
- **The wiki kit.** Templates, Bases views, a Home page, base CSS with colour tokens, Obsidian
  settings and a plugin guide.
- **Integrations.** A decision guide per app category, a tool map, permission rules and a
  Microsoft Graph route for mail and calendar that cannot send mail.
- **GitHub kit.** A README template, a gitignore, a pre-commit hook and workflows for a
  workspace repo, plus a separate backup for the wiki.
- **Scripts with tests.** Wiki lint, reindex, stats and log, the skills catalogue, Council
  scoring, the idea page builder, the writing-style check and the wiki backup, tested on macOS,
  Linux and Windows.

[Unreleased]: https://github.com/nickyjacobs/NEST/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/nickyjacobs/NEST/releases/tag/v1.0.0
