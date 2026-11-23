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

- **Not tried on Windows:** the read-only guard refuses, in PowerShell, every word with a
  double quote in it, because Windows PowerShell 5.1 hands such a quote to the program
  (`git diff '"--output=x.txt"'` would reach git as an option). That behaviour was found by
  reading and has not been watched on a Windows machine, with 5.1 or with 7.
- **Not tried on Windows:** a network path with mixed separators. The read-only guard refuses a
  word that starts with `//` or two backslashes, but `cat '/\server/share/a.md'` passes (on
  `develop` too) and so does `cat "\/\/server/share/a.md"`. Whether Windows, under Git Bash,
  reads either as a network share is not known (see
  [hooks-notes.md](../reference/hooks-notes.md)).
- The scan after a shell command (`validate.py --hook shell`) still reads the whole repository
  around a project folder and the wiki backup wherever `wiki.config.json` points; `--file` and
  `--changed` stay inside the workspace.
- **Second session, two cases that depend on the app:** going back to an earlier conversation
  without a SessionStart, and a resumed session with a new id on the old transcript, each give
  the second-session line once where no second session works (see
  [hooks-notes.md](../reference/hooks-notes.md)).

## Updates

- **Wiki files are not mapped one to one.** A workspace's wiki is translated and restructured, so
  the updater reports a changed wiki template or style and leaves the comparison to the
  nest-update skill. A mapping the setup records per template would make those merges exact.

- **Not tried on Windows by a person:** the update check stops git and its helper processes as
  a group when the time is up, and a test on Windows covers that. A slow real connection on a
  Windows machine has not been watched.
- **Undo after carrying on:** when an undo fails in an older part of an update and the user
  starts a new update without running `restore` again, that older part is only reachable by
  name (`restore --run`). `restore --list` does not show which parts belong together.
- **Undo of an update nobody closed:** an update that was started and left without `finish`
  counts as the update's own work when it is put back, also for edits made days later. Those
  edits are kept in the history folder, not in place.

## Secret scan

- **What it does not see:** a password without a digit, with spaces or shorter than ten
  characters, and a secret written in a sentence. `SECURITY.md` lists the limits.
- **After a shell command** the scan reads files changed in the last two minutes, within a
  budget; a commit on another branch and a stash are not followed.

- Left open by the last review of the scanner and the read-only guard, none of them reachable
  without access to the workspace already:
  - `validate.py --file sub/link/../x.md`, with `sub/link` a link to a folder outside the
    workspace, reads the file outside and reports it under a name that does not exist: the path
    that is judged and the path that is read differ.
  - The exemption for the user's own home folder also covers a few forms that are another
    place: a variable or a path used as a host name before a colon (`$HOST:/Users/<name>`,
    `/net/host:/Users/<name>`), a web address with the path in its query, and a folder whose
    name is the user name followed by punctuation and a space (`<name>. Backup`).
  - A `nest.json` that exists but cannot be read makes `--changed` skip the wiki backup without
    saying so.
  - `--file` on a folder that is a repository of its own is named and exits 0; for a path the
    caller gave it should be 3.
  - The quoted start of the other session's last prompt keeps typographic quotation marks, and
    a session state file edited by hand is shown without the secret and term rules applied
    again.

## Devices

- The sync routes in `kit/wiki/obsidian/DEVICES.md` come from Obsidian's documentation and from
  research in November 2026. Nobody has set one up on a real phone with a NEST wiki yet: how Home
  looks on a narrow screen, whether the Meta Bind buttons work on mobile, and what Obsidian Sync
  does with the plugin settings are untried.
- Routes that need the vault inside a cloud folder (iCloud Drive, OneDrive, Dropbox, Google
  Drive) are not offered: the wiki would have to live outside the workspace, and the scanner and
  the plugin installer now refuse a wiki folder that is a link or lies outside the workspace.

## Idea pages

- With only one of the two teams installed, an idea page still shows the empty section and
  the counter of the other (a "Blueprint" section in a workspace with only The Council).

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
- Not covered by the trial runs: a real mail or calendar connection, and a pushed GitHub setup
  (B5).
- A person opened a vault that `obsidian_setup.py` had filled, on macOS: the settings stayed,
  and Home showed its buttons after one restart of Obsidian. Still open from that trial:
  Notebook Navigator is not the pane in front the first time the vault opens, the
  `<!-- AUTO-INDEX -->` marker shows as text in Live Preview, six capture tiles wrap as five and
  one, and a workspace built before this release keeps "Colorful headings" on (the updater does
  not carry wiki settings over).
- `obsidian_setup.py vaults` counts the notes in every vault Obsidian knows, up to 5000 each.
  With a home folder once opened as a vault that takes long, and it prints the paths of the
  user's other vaults into the session. The build step only needs to know whether the wiki
  folder is in the list.
- Step B2.5 in `setup/build.md` is one long paragraph with its check in the middle.
- `obsidian_setup.py` has installed the plugins and the theme into a real vault on macOS only.
  On Windows and Linux nothing of it has run for real: `obsidian_running` (`tasklist`, `pgrep`),
  `config_dirs` and `installer_version` are tested with stand-ins for the process list, the
  environment and the home folder, which shows the logic and not what those systems really
  answer. The link checks are tested with symbolic links; a Windows junction is refused by the
  same code path and has not been tried. On Linux a vault that Obsidian marks as open always
  needs the user's word that Obsidian is closed, because the process list proves nothing there.
- The PowerShell rules of the read-only guard and the Windows code paths of the session guards
  are tested by simulation, not on a Windows machine.
- The session guard, the lesson hook, the plan hook and the blind seat guard are tested as
  scripts; nobody has watched them through a real compaction, a real second session or a real
  Council run yet.
