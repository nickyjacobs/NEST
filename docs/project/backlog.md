<sub>[Docs](../README.md) · [What to expect](../guide/what-to-expect.md) · [Updating](../guide/updating.md) · [FAQ](../guide/faq.md) · [nest.json](../reference/nest-json.md) · [Hooks](../reference/hooks-notes.md) · [Releasing](../project/releasing.md) · [Backlog](../project/backlog.md)</sub>

# Backlog

Things NEST does not do yet, with why they wait. This is the technical list; what is planned
for users is in the [roadmap](../../ROADMAP.md).

## Guards

- **Context thresholds:** one warning per threshold as a conversation fills up. No hook input
  carries the context window's fill level today (see [hooks-notes.md](../reference/hooks-notes.md)); it would need the
  user's status line. Waits for Claude Code to expose it to hooks.
- **Blind seats in a headless run:** the isolation guard is an agent hook, and agent hooks only
  run in a folder whose trust dialog was accepted. A `claude -p` run does not count as trusted,
  so there the agents' own instructions are still the only guard.

## Updates

- **Wiki files are not mapped one to one.** A workspace's wiki is translated and restructured, so
  the updater reports a changed wiki template or style and leaves the comparison to the
  nest-update skill. A mapping the setup records per template would make those merges exact.

- **Not tried on Windows by a person:** the update check stops git and its helper processes as
  a group when the time is up, and a test on Windows covers that. A slow real connection on a
  Windows machine has not been watched.
- **Undo of an update nobody closed:** an update that was started and left without `finish`
  counts as the update's own work when it is put back, also for edits made days later. Those
  edits are kept in the history folder, not in place.

## Secret scan

- **What it does not see:** a password without a digit, with spaces or shorter than ten
  characters, and a secret written in a sentence. `SECURITY.md` lists the limits.
- **After a shell command** the scan reads files changed in the last two minutes, within a
  budget; a commit on another branch and a stash are not followed.

## Language

- **Two things stay English in a workspace in another language:** the session-start line
  ("Workspace: wiki inbox 3 notes, ...") and the headings of the generated skills list in
  `docs/skills.md`. Both need labels in `nest.json` that the scripts read. The idea pages
  already have them (`idea_page.labels`), and the setup now fills those in.

## Skills

- The Obsidian Markdown and Bases skills are a copy of `obsidianmd/obsidian-skills` at the commit
  named in their `NOTICE.md`. Upstream has moved on (a kanban view, sorting, a new folder
  layout); taking the newer version over is a whole-folder replace plus a new commit hash.

## Tests

- A complete setup run has been done on macOS and on Linux (Debian), each with a fictional
  user. Not yet on Windows; CI runs the script tests and the pre-commit hook on all three.
- Not covered by the trial runs: installing the Obsidian plugins and how Home renders (needs a
  person), a real mail or calendar connection, and a pushed GitHub setup (B5).
- The PowerShell rules of the read-only guard and the Windows code paths of the session guards
  are tested by simulation, not on a Windows machine.
- The session guard, the lesson hook, the plan hook and the blind seat guard are tested as
  scripts; nobody has watched them through a real compaction, a real second session or a real
  Council run yet.
