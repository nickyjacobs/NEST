<p align="center">
  <img src="assets/release-banner.png" alt="NEST: New Environment Setup Toolkit" width="520">
</p>

# Changelog

Every release of NEST, newest first. Each one starts with a sentence and a **For your workspace**
section in plain words: what it means if you already built a workspace with an earlier release.
`/nest-update` in your workspace reads that section to you.

| Release | Date | In short |
|---|---|---|
| [1.1.0](#110---2026-11-22) | 2026-11-22 | Everything an audit of 1.0.0 found, fixed and tested: safer updates and undo, a secret scan that sees more, guards that hold, a setup that resumes where you stopped, and a roadmap. |
| [1.0.0](#100---2026-11-22) | 2026-11-22 | The first release: an interview that builds your own Claude Code workspace, and a way to keep it up to date afterwards. |

<sub>Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) · Versions: [Semantic Versioning](https://semver.org/) · How a release is made: [docs/project/releasing.md](docs/project/releasing.md)</sub>

## [Unreleased]

### ✨ Added

- `kit/scripts/obsidian_setup.py` installs the Obsidian plugins and the theme a vault asks for,
  from each project's own GitHub release at the versions in `kit/scripts/obsidian.lock.json`,
  with a checksum on every file. It refuses to write under a vault that is open in Obsidian or
  may be, leaves installed plugins and every settings file alone, refuses a folder that holds
  another plugin or that is reached through a link, and reports each plugin on its own: one
  that fails does not stop the others. It has `status`, `restore` (moves a `data.json.bak` back
  into place once, and keeps the file it replaces) and `vaults` (the vaults Obsidian knows on
  this computer).
- `tools/obsidian_lock.py` writes that lock file from upstream, and `--check` says when a
  plugin has a newer version, when a file changed under the same version, or when the list of
  plugins changed.

### 🔧 Changed

- Build step B2.5 installs the plugins and the theme after one yes, where the user used to
  install five plugins and a theme by hand. What is left for the user is opening the vault and
  "Trust author and enable plugins".
- The workspace `.gitignore` and the wiki backup keep plugin and theme code out from now on; the
  plugin settings stay in. An existing wiki backup gets the new exclude lines on its next push.
  They keep new files out: plugin code that a backup or a repository already holds stays in it
  and keeps being backed up, nothing is taken out of an existing backup.

- The setup prompt comes in parts. `SETUP.md` keeps what every session needs (sections 0 to 4)
  and a table of the parts; the phases moved to `setup/`: `check.md`, `interview.md`,
  `routing.md`, `build.md`, `finish.md` and `catalogue.md`. The text itself is unchanged. A
  session reads the part its phase needs, where it used to read 1011 lines in two pieces at
  every start. `STATE.md` names parts after `read:`, and the handover copies `setup/` along.
- `tools/release_check.py` checks that every part `SETUP.md` names exists, that every file in
  `setup/` is named, and that none is larger than one read.

### 🐛 Fixed

- Plugin settings the setup wrote were lost for every user: installing a plugin from inside
  Obsidian renames an existing `data.json` to `data.json.bak` when the folder has no
  `manifest.json` yet. The Home buttons, the excluded folders of Meta Bind and the sidebar
  colours were gone after the installs. Found in the first run by a real user, on Windows.
- Headings showed in a different colour per level: "Colorful headings" was on in the Minimal
  settings while the kit's CSS does not colour headings.

---

## [1.1.0] - 2026-11-22

> **In short:** Everything an audit of 1.0.0 found, fixed and tested: safer updates and undo, a secret scan that sees more, guards that hold, a setup that resumes where you stopped, and a roadmap.

### 🏠 For your workspace

Nothing breaks: everything you have keeps working. What you will notice after `/nest-update`:

- **The secret scan sees more, and stops less by mistake.** It now catches the everyday forms
  (`DB_PASSWORD=`, `token:`, `Wachtwoord:`, `**Password:**`), so a write or a commit that
  passed before can be refused. Code and example values such as `replace-me` are let through.
- **New guard, your choice:** after a shell command, the files it wrote, copied or unpacked
  are scanned too, also in a wiki with its own backup. It needs two new entries in your
  settings; `/nest-update` adds them after your yes.
- **A secret you paste into the chat is no longer kept on disk.** The file with your own
  messages shows `[secret removed]` in its place and is readable by you alone. Older files are
  not cleaned; they go by themselves after 14 days.
- **Undo is safer.** `/nest-update undo` tells you first which update it puts back and which
  files that concerns. It always means the last update, all of it, also when you brought it
  over in parts; asking twice no longer reaches back to an earlier one.
- **A typing mistake in `nest.json` no longer costs you your settings.** The update stops and
  names the line, and the start of a session tells you the file is broken.
- **The wiki check is stricter, and right.** A link to a folder that no longer exists used to
  pass when a note with the same name lived somewhere else. The first check after this update
  may show a few broken links: they were broken all along.
- **New notes keep their name in every language.** A title in Greek, Arabic, Japanese or
  Cyrillic gave a note without a name, and ß, ø and ł were lost. Existing notes do not change.
- **The wiki backup protects you from three mistakes:** it stops when a note holds what looks
  like a real key, when the wiki folder is suddenly empty, and when the backup folder belongs
  to another wiki. It says what to do in each case. After moving your workspace, ask your
  assistant to point the wiki backup at the new folder (it runs `wiki_backup.py init <address>
  --rebind`).
- **Long conversations:** when one is summarised, the summary gets your first message plus
  your newest ones, and lessons are shown again.
- **The read-only reviewer is really read-only now.** It can only run a fixed list
  of read commands, so now and then it words a search differently.
- **The Council and The Architects:** an idea page no longer points at a team you did not
  install, and its summary shows the assumption the plan really rests on. If a run stops
  halfway to ask permission for its own scripts, ask your assistant to add the allow rules for
  `council_score.py`, `idea_page.py` and `wiki.py` to your settings.
- **Mail and calendar through Microsoft:** "any new mail?" no longer fails on some mailboxes;
  without internet or after an expired sign-in you get one plain sentence with the command to
  type; and before a meeting you organise is moved or cancelled, you hear that the people in
  it get a message.
- **Updates:** an update you brought over in parts no longer shows you changes you already
  have, a check that failed offline is tried again the next day, and you hear it when NEST
  changes an example that something of yours was made from, such as your wiki settings.
- **Two things by hand, once.** In Obsidian, add your inbox, your raw sources folder and your
  archive to "Excluded folders" in the settings of Meta Bind, so a button inside text that
  came from outside cannot run anything; `/nest-update` shows the exact names. And if your
  commits got a "Co-Authored-By: Claude" line, let `/nest-update` add the `attribution`
  setting.
- Without uv on the path, the check before a commit now says so in one line and does not
  fail with a cryptic error.
- The fixes to the setup itself are for new workspaces; nothing in yours changes because of
  them.

### ✨ Added

- `validate.py --hook shell`: after a shell command the files it wrote, copied, moved,
  unpacked or committed are scanned, also in the wiki's own backup repository; at most 50
  files, 8 MB, 20 commits and 15 seconds per run, and it says what it left out.
- Secret shapes: Azure storage keys, Telegram, Stripe, DigitalOcean, PyPI, Docker, Vault,
  Slack app, Twilio, age, Tavily, Notion, Google OAuth, Discord webhooks, PuTTY keys, GitLab
  deploy tokens, Linear, Figma, Shopify, Atlassian and Square keys, basic auth headers,
  `curl -u`, `--password value`, `sshpass -p`, XML and Markdown table forms, and the Dutch and
  German words for password.
- The reviewer may use `2>/dev/null`, `2>&1`, a pipe into `head`, `tail`, `wc`, `sort` or
  `uniq`, `git show <commit>`, `git log -5`, `git blame`, `git grep`, `git check-ignore`,
  `git rev-parse` and `diff`.
- `SECURITY.md` describes what the secret scan and the guards cover, and what they do not.
- `wiki_backup.py`: refuses a git directory that belongs to another wiki (`init --rebind`
  after a move), `init --set-remote`, `push --allow-empty`, a secret scan before each commit
  (`--no-scan`) and a warning for a folder in the wiki that is a git repository itself.
- `skills_catalog.py --installed`: fails on a leftover `customise:` or `<fill in:` marker in
  a built workspace.
- Meta Bind leaves the folders with raw outside text alone, and the ingest and inbox skills
  make Meta Bind code blocks and Templater tags in outside text inert.
- `kit/wiki/decisions-log.md`: the decisions log with its format block, which the session-end,
  inbox and career skills write to.

### 🔧 Changed

- **The setup.** The wiki is part of every workspace and is always a new vault: NEST never
  writes into a vault you already have. An integration you want "later" is built with its
  not-connected path, without researching routes first. Without GitHub the setup still asks
  for a commit identity and offers the pre-commit scan, and the wiki goes into the local
  repository. The workspace folder is no longer proposed inside a downloads folder or a folder
  a cloud service syncs. In a workspace in another language the setup fills in the labels of
  the idea pages.
- The setup now builds `.github/dependabot.yml` and the checks workflow and asks about them
  in E7, adds an MCP server in the local scope and never in the project, and makes the
  sensitive terms file from the kit's example with the command that opens it. The empty
  folder `kit/claude/hooks/` is gone.
- `kit/claude/settings.reference.json` sets `attribution` to empty, so a commit never
  carries a "Co-Authored-By" line.
- `NEST`'s own `CLAUDE.md` says first that a session asked to follow `SETUP.md` ignores it.
- `agent_git_readonly.py` works from an allow list of commands and of options per command.
  `sort`, `uniq`, `file` and `tree` on their own, `git -C`, `--git-dir`, a path starting with
  `~`, a word starting with a wildcard and a network path are refused; a name or pattern
  that starts with `-` is written `./-name` or `--regexp=-x`.
- `validate.py --hook pre` refuses a write when it cannot read the hook input. A private key
  block counts only when key material follows the header. `pass:` and `pw:` on their own no
  longer count as a secret name. A file over 2 MB is named as skipped.
- The compaction summary gets the first message and the newest ones, 8,000 characters by
  default and at most 9,500, between two marker lines.
- The agent templates ship real hooks where they had a placeholder; the blind seats pass
  `--seat`.
- `ROADMAP.md` says where NEST is going, and the README links to it. Questions and ideas now
  go to Discussions: the README, the FAQ, `CONTRIBUTING.md` and the issue chooser point there.
- `wiki_backup.py` leaves nested git repositories out of the backup and never waits for a
  password. `check_style.py --strict` exits 2 when the check could not run. `dashboard.base`
  uses `file.hasTag("query")`, which also works for a note without tags.
- `nest_update.py restore` has `--list` and `--dry-run`. The plan has a new status,
  `reference`, for a changed example file without a fixed place in a workspace.
- The idea skill no longer carries `allowed-tools`: that grant ends at the user's next
  message, before the scoring and saving scripts run. The setup writes allow rules instead.
- `kit/github/gitignore.template` ignores `.mcp.json` and `mail-folders.md`.
  `kit/claude/rules/writing.md` also loads for the README and `docs/`.
- `calendar update` takes `--end` on its own. The tool map has a "Sign in again" line and a
  row for `organize status`; the deny rule for the token folder is a placeholder per system.

### 🐛 Fixed

- A secret in a stored message is replaced on its own: the words after it were removed with
  it when two rules found the same token.
- **Undo covered only the last part of an update.** An update with something left for later
  is closed in parts; `restore` now puts back every part that began from the same release,
  the dry run lists them, and a second `restore` (after a failure, or with `--force`) works on
  the same parts.
- The stricter status check refused the ideas index of a workspace built with 1.0.0, which
  carries one of the section's own words. Both forms pass now, and an unknown status names
  the words that are allowed.
- The nest-update skill asked for a restart before the commit question was settled, so the
  next session committed the user's own notes along with the update. The commit comes first.
- The setup wrote "yes" for an answer to a proposal without the proposal itself, so a session
  that continued built something else than the user agreed to.
- **The setup lost answers when a session ended without warning.** Answers are now written
  after every message, and a new session reads the interview files, the facts file and the
  log back before it continues.
- **The setup after the handover.** The state said "build" before the workspace folder
  existed; a session started in the wrong folder now knows what to do. Every stop point names
  the folder and the line that starts the next session, and the state file ends on `done`.
  The kit copy in `_setup/nest` stays where it is, so nothing points at a moved folder.
- The stamp was not written again after the integrations and the GitHub step; a new
  connection was tested in the session that added it, before it could load; the backup
  repository for the wiki was never created.
- The pre-commit hook could be written without its executable bit, after which git skips it
  without a word. The setup now copies it, makes it executable and tests a refused commit.
- The pain point list had more options than the choice dialog can hold; references to steps
  and files that do not exist are gone; `git init` starts on `main` on every system; a write
  into `.claude/` that was refused once is tried again in the next phase.
- An idea page pointed at The Architects in a workspace without them. The inbox skill left
  the source field empty on a page it made from a note, which gave a lint warning that never
  went away.
- **The read-only reviewer's guard could be passed.** zsh `=( )` and glob qualifiers,
  PowerShell parentheses, `sort -o`, `file -C`, git pointed at another repository,
  `find -rm` (which deletes inside Claude Code), an option behind `--` or behind an option
  that takes a value (`rg -e -- --pre=sh`), and a wildcard that turns into an option after the
  check. Found by three rounds of independent review, the last with 18,000 generated commands
  held against the real shells.
- **The secret scan missed the common `.env` form** (`DB_PASSWORD=`, `SECRET_KEY=`,
  `MY_API_KEY=`), a bare `token`, a password in any URL, and Markdown emphasis before a
  value; a placeholder word in the name hid a real value. Files written through a shell
  command were never scanned.
- Code and example values were mistaken for secrets (`password = hashlib.sha256(x)`,
  `postgres://postgres:postgres@localhost`, a sentence that quotes a private key header).
- A secret pasted into the chat was kept in the session's words file and handed to the
  compaction summary. The files under `.claude/.session/` were readable by other users on a
  shared Linux machine.
- On Windows a message with an accent or a curly quote was lost or garbled, and a workspace
  path with an accent locked the blind seats out.
- A sensitive terms file saved as UTF-16, with a byte order mark or in a Windows code page
  stopped every write. `"skip": "vendor/**"` written as text, not as a list, switched the
  whole scan off. A `nest.json` with a byte order mark was read as empty by the session line.
- Editing `CLAUDE.local.md`, the terms file or an ignored `.env` told the assistant to "fix"
  it. A staged submodule blocked every commit.
- A session that works for a long time without a new prompt was invisible to the
  second-session line. A lesson was not shown again after a compaction, and lesson hooks
  that run side by side lost each other's record. A plan was saved before it was approved.
- The blind seat guard stepped aside when a seat was renamed, its name differed in case,
  `--seat` was mistyped, or a link named after its file pointed at another seat's report.
- Two patterns took minutes on a long hostile line.
- `idea_page.py` took the first list item under "Assumptions and risks" as the load-bearing
  assumption, also when the blueprint names it in a sentence above the list; and it pointed
  at The Council in a workspace that only has The Architects.
- `wiki.py lint` warned that a sourced section's own ingest log and index have no sources.
- The research skill installed its job profile and device inventory for everyone; both are
  now a choice. The skill builder adds a new skill to the list in `CLAUDE.md` too.
- The README's download link pointed at the newest state of the main branch, while the
  workspace is stamped with the release in `SETUP.md`. It points at the latest release now.
- `wiki.py lint` accepted a link whose folder does not exist when a file of the same name
  lived elsewhere. It also stopped on an `author` written as a list and on `---` inside a
  value, and counted links inside comments, tilde fences and double-backtick code. Notes made
  from the kit templates, and Home, now pass the lint.
- `wiki.py lint --fix` broke table rows by writing an unescaped `|`; `reindex` threw away intro
  text that mentioned the index marker. A section's own `index.md` keeps the top-level status
  words when the section has its own list, so saving an idea no longer ends in a lint error.
- `slug.js` gave an empty file name for titles in a non-Latin script.
- `council_score.py` took the score and verdict of a judge whose criteria it could not check,
  and crashed on a negative or non-finite score.
- `idea_page.py`: status words without a section list, a heading inside a desk report that
  cut the page short, ticks lost after a renamed heading, pages written with mode 0600, titles
  YAML misreads, a malformed `verdict.json`.
- `check_style.py` missed entries in scripts without spaces between words and read `[sic]` as
  a section; `skills_catalog.py --check` said "ok" for a folder that does not exist.
- Template titles with a backslash and source URLs with a colon broke the frontmatter.
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
- `graph.py` printed a Python traceback when the network, a date, a time zone or a file
  failed. Every command now prints one JSON line, and the short names for mails (m1, m2) stay
  true when two commands run at the same time.
- `graph.py mail list --unread` combined a filter and a sort order in a way Microsoft Graph
  documents as an error (`InefficientFilter`).
- The token cache of the Microsoft route was readable by other users for a moment while it
  was written. The README of that route no longer says the token cannot reach other people:
  answering an invitation and cancelling a meeting do.
- The mail, calendar and organizer skills pointed at a sign-in command the tool map did not
  have; the light Council formats lacked the `Assumptions` line the run files refer to; the
  session-end skill named a field its template does not have.
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

[Unreleased]: https://github.com/nickyjacobs/NEST/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/nickyjacobs/NEST/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/nickyjacobs/NEST/releases/tag/v1.0.0
