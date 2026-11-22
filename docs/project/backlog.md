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

- **Not tried on Windows:** the update check gives git two seconds at session start. On Windows a
  killed `git.exe` can leave a helper process holding the pipe, which could stretch that wait.

## Skills

- The Obsidian Markdown and Bases skills are a copy of `obsidianmd/obsidian-skills` at the commit
  named in their `NOTICE.md`. Upstream has moved on (a kanban view, sorting, a new folder
  layout); taking the newer version over is a whole-folder replace plus a new commit hash.

## Tests

- No real setup run on Windows or Linux yet; CI runs the script tests and the pre-commit hook on
  all three.
- Not covered by the trial runs: installing the Obsidian plugins and how Home renders (needs a
  person), a real mail or calendar connection, and a pushed GitHub setup (B5).
- The session guard, the lesson hook, the plan hook and the blind seat guard are tested as
  scripts; nobody has watched them through a real compaction, a real second session or a real
  Council run yet.
