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
  another plugin or that is reached through a link, never reads or writes through a link or
  anything that is not a plain file, names a settings file it cannot use, and reports each
  plugin on its own: one that fails does not stop the others. It has `status`, `restore` (moves
  a `data.json.bak` back into place once, for the plugins in the lock file, and keeps the file
  it replaces) and `vaults` (the vaults Obsidian knows on this computer).
- `tools/obsidian_lock.py` writes that lock file from upstream, and `--check` says when a
  plugin has a newer version, when a file changed under the same version, when a name or a
  repository in the lock file differs, or when the list of plugins changed. The release steps
  ask for that check.
- `validate.py --changed` scans the files git reports as changed or untracked under the
  workspace folder, and those of the wiki's own backup repository when `nest.json` names one.
  The names come from git, so none has to be typed, and a last line says how many files were
  scanned. It calls nothing clean after a `git status` that failed or did not answer, or when
  the backup `nest.json` names cannot be used (missing, not a repository, a wiki folder outside
  the workspace): each is named and the exit status is 3.

- `kit/wiki/palette-preview.html`: the setup fills it with two or three palettes and opens it in
  the browser, so the user picks colours by eye and never from colour codes.
- `obsidian_setup.py vaults --count` counts the notes per vault. Without the flag the command
  only lists the vaults, and no longer walks through every folder Obsidian knows.
- The updater knows what a rename is. `RENAMES` in `kit/scripts/nest_update.py` maps an old kit
  path to its new one, a folder or a file, one line per rename. `plan` reports a renamed part
  this workspace has as one `rename` item (the recorded files and where they go, the user's own
  files in the folder, what the part gained, and any place that is already taken) where it used
  to report "removed" plus "new". The new command `rename` backs up every file of the part and
  moves it as it is, and re-records it against the kit file under its new name with the hash
  it was made from, so the next plan lists what NEST changed as an ordinary replace or merge.
  In a skill it changes one line, the `name:` in `SKILL.md`, to the new folder name, so the
  skills catalogue is valid at every moment. A file is moved by renaming it, never by copying
  and deleting, and the stamp is saved after every file (`renaming` in `nest.json` marks a
  rename that was begun): a run that stops at a file another program holds, or is killed
  between two moves, leaves every file in one place, the plan keeps showing the rename until
  the old folder holds nothing of the part, and the same command carries on. A file at the new
  place that this rename did not put there blocks it before anything moves; the same file at
  both places does not. Folders the rename emptied are removed, and symbolic links in the old
  folder are named as left in place.
  `diff` compares a renamed kit file across its two names. `decline` on a rename moves nothing
  and re-records the files against the new kit paths, so the offer does not return and later
  changes still arrive under the old name; it is refused for a rename that is half done. Both
  clear what was declined under either name, so a "no" given to an updater from before the
  table does not hide what NEST changed in the part. `restore` puts the old folder back and
  takes the new one away, empty folders included; files the user changed in the new folder
  after the update stay there and are named. A workspace that never had the part hears
  nothing about it, and neither does one that has it under a folder name of its own (a
  translated name, a rename it declined before): there the files just follow the kit file's
  new name. `stamp` takes a folder under a part's old name for the kit's only when at least
  one file in it is still the kit file, so a skill of the user's own that happens to be called
  `idea` is left alone.
- The updater never writes a renamed part's new name into a workspace that has the part under
  another name (the old name was kept, the rename is still to be done, or the folder has a
  name of the user's own). A kit file whose new version says the new name where the old one
  said the old name (the last parts of the two paths in `RENAMES`, as whole words, per changed
  block of lines: a `name: idea` that became `name: verdict`, a path `../idea/reference.md`
  that became `../verdict/reference.md`) is a `merge` with `name_kept` in the plan, also when
  the file is an untouched copy, and `apply` refuses it and says why. After `rename` the same
  file is an ordinary `replace`. Scripts are exempt: they read both names.
- `rename` changes the `name:` line of a moved `SKILL.md` only when it holds exactly the old
  folder name, and keeps quotes, spacing and a trailing comment. A name of the user's own, an
  empty or a missing `name:` is left alone, and the command says so.
- A `rename` that stops before one file was moved is not begun: the marker is cleared, the
  plan shows the ordinary offer again and `decline` works. The text form of `plan` says when
  a rename is begun and not finished.

- The interview asks where else the user wants their notes (a phone, a tablet, a second
  computer) and proposes a sync route from the new `kit/wiki/obsidian/DEVICES.md`: Obsidian
  Sync, or Syncthing as the free route for someone technical, with the steps per route. The
  guide `docs/guide/devices.md` says the same for people. NEST installs nothing for it, and the
  routes have not been tried on a real phone yet.
- The interview asks who saves the snapshots: the assistant by itself, when a piece of work is
  done and at the end of a session, or after a yes every time. The commits rule and the
  session-end skill come in both variants. A push stays a question in both.
- `docs/guide/getting-started.md`: from nothing to the first sentence, for people who have
  never opened a terminal, with a picture of every click: VS Code, the Claude Code extension,
  Obsidian, the release as a zip, opening and trusting the folder, and starting the setup. The
  README names it as the first route. The pictures are real screenshots with numbered marks
  (`assets/start/`, drawn by `assets/start/src/compose.py`).

- The updater recognises files of a renamed part that were taken out earlier in the same
  update. The 1.1.0 updater has no rename table and lists such a part as "no longer in NEST",
  and its `retire` moves the files into the update's history and drops their records. `plan`
  now reads those records from the update's own copies of the stamp, in every part of the
  update in progress (also a part that `finish` with open points or a pause of more than
  twelve hours closed, the parts `restore` takes together), and shows one `rename` item with
  `taken`; `rename` and `decline` bring the files back from the update's `files/` with their
  records before they do their own work, so the result equals a run in which nothing was taken
  out, and `restore` still returns the starting state. `restore --run` on a part that brought
  such files back takes its whole update along: alone it would take them away again while the
  earlier part still keeps them out, with nothing left to offer them. When the user wants the
  part gone, `done` on its `rename` item leaves its files out (their copies stay in the
  history), provided all of them were taken out. Files in a folder of the user's own (a
  translated name) are a `taken` item each, never `missing` or `unchanged`, and the new command
  `bring-back` puts them back where they were. A copy someone put back by hand is recognised
  when it equals the kept one and blocks when it does not. A new version built at the new
  place in the meantime (`fresh`) stops both commands: nothing is merged, and the message points
  to undo. `apply`, `apply --new` and `mark` refuse the old and the new place of a taken file.
  `decline` is only stopped by something at a taken file's old place, not by a file of the
  user's own at the new one. A file comes back through a temporary copy in the history folder
  and a rename, so a run that stops never leaves half a file. A file that names the part stays
  a `merge` while its files are out.
- `plan` decides whether the update is still open before it builds the plan, so it never shows
  an offer that the next command no longer sees.
- `diff` takes the workspace path of a recorded or offered file as well as the kit path, and
  `apply --new` takes several `KIT=PATH` pairs after one flag as well as one flag per pair.

### 🔧 Changed

- The Council's skill is called `verdict` (the command `/verdict`), after what it gives, the
  way The Architects' skill is called `blueprint`. It was `idea`, which named what the user
  brings. `kit/skills/idea/` is `kit/skills/verdict/`, and the setup prompt, Appendix B, the
  blueprint skill, the Council's agents and the wiki kit name the skill by its new name. The
  team, its seats, the idea page (`idea.md`), `idea_page.py`, the ideas section and the
  `idea-note` snippet keep their names: an idea is still an idea.
- `idea_page.py` counts The Council as installed when the skill folder is `verdict` or `idea`,
  and `nest_update.py` reads the light size and the team of an agent under either name
  (`stamp --light` takes both), so a workspace that keeps `/idea` behaves as before.
- A new file of a skill is offered next to that skill's own files, also when its folder in the
  workspace has another name than in the kit.
- `retire` works on a file a rename moved in the same update: the copy it keeps goes to the
  update's `created/` folder, and the version from before the move stays under its old name.
- Build step B2.5 installs the plugins and the theme after one yes, where the user used to
  install five plugins and a theme by hand. What is left for the user is opening the vault and
  "Trust author and enable plugins", and restarting Obsidian once. The instruction gives the
  full path to paste, and the setup checks afterwards that Obsidian opened the wiki folder and
  not the folder above it: in a trial that went wrong three times in a row.
- The workspace `.gitignore` and the wiki backup leave out what `obsidian_setup.py install`
  can put back, and nothing more: the code of the plugins and the theme in the lock file, named
  one by one. The plugin settings stay in, and so does a plugin or theme you added yourself,
  code and all. An existing wiki backup gets the new exclude lines on its next push. They keep
  new files out: plugin code that a backup or a repository already holds stays in it and keeps
  being backed up, nothing is taken out of an existing backup.

- The setup prompt comes in parts. `SETUP.md` keeps what every session needs (sections 0 to 4)
  and a table of the parts; the phases moved to `setup/`: `check.md`, `interview.md`,
  `routing.md`, `build.md`, `finish.md` and `catalogue.md`. The text itself is unchanged. A
  session reads the part its phase needs, where it used to read 1011 lines in two pieces at
  every start. `STATE.md` names parts after `read:`, and the handover copies `setup/` along.
- `tools/release_check.py` checks that every part `SETUP.md` names exists, that every file in
  `setup/` is named, and that none is larger than one read.
- `validate.py --file` names every path it did not scan, with the reason: does not exist, is a
  folder, outside the workspace, left out by a skip rule, over 2 MB, cannot be read. The exit
  status is then 3 when no finding makes it 2, so no output means scanned and clean. It used to
  say nothing and exit with 0 for a path that does not exist, which a name with a space or an
  accent easily becomes. Files that are not text, symbolic links and folders that are a
  repository of their own (a submodule, a cloned project) are named in one line each and change
  nothing. The `checks.yml` workflow accepts the 3, so only a finding fails the check.
- `validate.py --file` and `--changed` follow no symbolic link and read nothing outside the
  workspace. No file name is printed as it is: a line end or a control character in a name is
  shown as its escape, so a name cannot pose as a line of the scanner's report.

- The interview asks by click where it can. Every question with a known set of answers goes
  through the choice dialog, also in the build; long lists are multi-select questions grouped by
  theme; an open question stands alone in its message. Question IDs (A1, F3) are no longer shown
  to the user. For a beginner a block opens with a proposal, and choices that need knowledge
  they do not have take a default. In the first run by a real user 40 answers were typed
  against 14 clicked.
- The setup follows where the user works. Phase 0 records it as `surface` in `STATE.md`
  (the Claude Code panel in VS Code, a terminal, the desktop app), and every instruction to
  open a folder or start a session takes that form. The `!` prefix is no longer suggested in
  the VS Code panel, where it does not exist.
- The setup creates the workspace folder itself at the handover. It used to tell the user it
  could not, and gave a command for a terminal.
- The build runs B1, B2 and B3 in one session: hooks and skills are active in the session that
  writes them. Two of the three restarts are gone, and the commit question comes once per
  session.
- A tool installed during the machine check is used by its full path for the rest of that
  session, and the app is restarted once at the next moment the user reopens something.
- B4: the setup runs the tests itself, with a sample note and a test idea of its own, and takes
  them out again. The user is asked once, at the start, whether a team run is included.
- Existing notes: with a yes the setup lists the vaults Obsidian knows on the computer, and
  bringing the chosen ones in becomes the first task after the build.
- The session plan is four sessions, and the docs say what a run really takes.
- Files for `.claude/` are built in a staging folder under `_setup/` and copied in once per
  phase. In a trial every write into `.claude/` raised a permission question: about
  thirty-seven during one build.
- Before the build the setup tells the user that Claude Code itself asks before every write
  and command in its default mode (a trial counted 143 questions in one build), and offers a
  short list of things it may do without asking for the length of the build: writing in the
  workspace's own folders, running the workspace's own scripts, copying out of NEST's own kit
  copy, looking at and staging changes. A trial with the list: 64 questions where there were
  143, none of them for writing a file; the build is now told to work in plain single commands,
  which is what the remaining ones came from. After a yes the rules of `kit/claude/setup-permissions.example.json` go into the
  workspace's local settings, and the wrap-up takes them out again. Deleting, the network,
  installs, `.claude/` and commits stay questions. The setup never changes the permission mode.
- Helper agents: the setup stays in the turn while they work and reports per finished piece.
  A postponed step (opening Obsidian) no longer keeps the wrap-up from finishing.
- Labels stay out of sight: phase names (B2, block C) and working files (`STATE.md`) are no
  longer shown to the user, a proposal is always in a visible message before the dialog that
  asks about it, and a later session reads the user's language before its first word.

- The roadmap, after the first run by a real user. Shipped and off the list: the plugins the
  setup installs itself, a run on Windows by a person, and notes from your phone into your
  inbox. New under Now: plugins for Claude Code that fit you, and bringing your old notes in.
  The board on Home became a command board and moved to Next, with a shorter route through the
  setup. New under Later: your workspace on two computers.

- The quick start GIF in the README shows the route through VS Code in five real screens (add
  the extension, open the folder, trust it twice, type the sentence), built by
  `assets/quickstart-src/slides.py`. It used to be a drawn terminal.

- From the trial before the release: the interview offers to write the setup's own notes
  (`_setup/`) without a permission question each time, as one rule that is taken out again at
  the handover (a trial in Claude Code's default mode counted 60 questions in one interview);
  answers are written with the edit tools, never with a shell append; the first message is the
  language question and nothing else; a question about a fact has no recommended option; the
  question about other devices names the price and says that the assistant stays on this
  computer, in a message before the dialog.
- From the last trial of the build (54 permission questions where earlier trials had 143 and
  64): helper agents, the security reviewer among them, get the single-command rule in their
  brief; every later change to `.claude/` goes through the staging folder; each snapshot is
  said in one line with one word; the overview comes before the dialog with the first tasks;
  the build permissions are the very last thing removed; the words the user gave for an old
  notes folder are kept, so nobody asks again.

### 🐛 Fixed

- Plugin settings the setup wrote were lost for every user: installing a plugin from inside
  Obsidian renames an existing `data.json` to `data.json.bak` when the folder has no
  `manifest.json` yet. The Home buttons, the excluded folders of Meta Bind and the sidebar
  colours were gone after the installs. Found in the first run by a real user, on Windows.
- Headings showed in a different colour per level: "Colorful headings" was on in the Minimal
  settings while the kit's CSS does not colour headings.
- `validate.py` reported a private term in every absolute path when the user's own user name
  holds that term (a surname on the terms list, a home folder named after it). A term that occurs
  only inside the path of the user's own home folder is no longer a finding. Exempt is that one
  folder as this computer spells it (either slash, backslashes escaped, URL-encoded, any case,
  the Git Bash and WSL form of a Windows folder, after `file://`, and `~name`), standing on its
  own: after white space, a quote, a bracket or `=` (after a colon only in a list of paths such
  as `PATH`), and followed by a separator, a quote, a closing bracket, the end of the line, or
  what ends it in ordinary text: one of `. , ; : ! ?` before white space or the end of the line,
  or a `|` of a table cell. The same names on another computer or share, at the end
  of a longer path, in a web address, in a markdown link, and a folder that only starts with the
  name are still found, as is the term anywhere else on the line; the secret rules are
  untouched. The check looks at a short piece of the line around each match, so a long line costs
  no more per character than a short one. Found in the first run by a real user, on Windows.
- `session_guard.py` announced a second session at the start of every session that followed
  another within half an hour: it counted every session file with recent activity, and a
  session that has just ended, is writing its last message or never ran its SessionEnd hook has
  one. Another session now counts only when it was active more than a minute after this one was
  opened, so the line comes on the first prompt after a second session really showed itself and
  no longer at the start. The line gives the time of that session's last activity and the first
  words of its last message (secrets and private terms taken out, plain characters only, and no
  words at all when `validate.py` is not there to take them out), says where the user would see it in a terminal
  and in the VS Code extension or the desktop app, what to do once it is found, and what it
  means when they find none. A damaged list of sessions already named no longer silences the
  line.
- The `security-reviewer` agent searched with the raw terms file (`rg -f`), where every comment
  line and empty line is a pattern and an empty line matches everything. It now asks
  `validate.py`, and `agent_git_readonly.py` lets it: `uv run --quiet --script
  scripts/validate.py` (or `-q`) with `--changed`, `--file` or `--staged`, from the workspace
  folder, is the one program the guard lets a read-only agent start, with each option as a word
  of its own (no `--file=<path>`) and every name after `--file` checked as a path, and a pattern
  file for
  `grep` or `rg` (`-f`, `--file`) is refused. The agent scans with `--changed`, which takes the
  file names from git itself, so a space or an accent in a name cannot lose a file; its
  instructions say what an unscanned path looks like, what each exit code means, and how
  PowerShell differs (no pipe, no variables, no double quote inside a word). A test runs every
  command the agent file shows through the guard.
- `agent_git_readonly.py` read a backslash inside double quotes as an escape before any
  character, where a shell does so only before `$`, a backtick, `"` and a backslash; it took a
  vertical tab off the end of a command, which the shell hands to the program; and in
  PowerShell it let a word with a double quote in it pass, which Windows PowerShell 5.1 hands to
  the program in a way that can turn `'"--output=x"'` into an option. All three are closed; the
  last was found by reading and has not been tried on Windows.

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
