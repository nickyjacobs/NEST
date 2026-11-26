# NEST setup: the build

Part of the NEST setup prompt. `SETUP.md`, one folder up, holds the rules for every part and says
when to read this one. Read `SETUP.md` first.

---

## 8. Build

At the start of each build phase (B1, B2, B3, B3b, B5) show the whole plan for that phase as one
short tree or list, in the preview of the dialog's first option (section 4.2), and ask **one yes
for the phase**. Then build its
steps one after the other without asking again, unless something deviates from the plan, leaves
the machine, or cannot be undone. After each step run its check and tick the line in STATE.md.
If a check fails, fix the cause; never tick around it.

B1, B2 and B3 run in one session: the hooks you write in B1 are active from that moment, and
the skills from B3 exist as soon as their files do. After each phase offer the user a stop, and
go on when they want to. A commit follows the answer to E8. When the user chose that you save
snapshots yourself: commit at the end of each phase without asking, the files of that phase by
name (never a whole folder), and say so in one line every time, using one word for it: the
word the user heard in E8, in their language ("Snapshot saved: the wiki."). When they chose to be asked: ask
once per session, at its end or when the user stops, as one dialog that says in a plain
sentence what a commit is ("a snapshot of the workspace you can go back to"); never once per
phase. A push is always its own question.

The user watches most of the build. Keep them posted in their language, one short line per
step, and in B3 one line per skill or agent as it is finished ("The routine that files your
notes is ready."): twenty minutes of silence reads as a program that hangs. Save questions for
what only they can answer. Helper agents are fine for speed. When you hand the turn back while
they work, say in one line that you carry on by yourself when they are done, so the user knows
nothing is asked of them; report per finished piece as it comes in.

**A helper gets the rules of this section in its brief, word for word:** one command per call,
files changed with the edit tools, nothing written into `.claude/` except under the staging
folder, no chain such as `; echo "exit=$?"` or `| head`, and every line it writes for the user
(a report you pass on, text in a file the user reads) in the language in `language:` of
STATE.md, named in the brief. A helper does not read this file,
so a rule you do not hand it does not exist for it. In a trial fourteen of the permission
questions of one build came from helpers, ten of them from the security reviewer in the final
check.

**How often Claude Code asks, and the short list for the build.** In its default mode Claude
Code asks the user before every file it writes and every command it runs. A trial counted 143
such questions in one build. Nobody reads the hundredth one, so they protect nothing; what
protects the workspace is its own guards, which check every file whatever Claude Code asks.

Before B1, in a message of its own and in plain words: these questions come from Claude Code,
not from you; and for the length of the build you can give Claude Code a short list of things
it may do without asking, which you take away again at the end. Say what is on the list:
writing files in the folders of this workspace; running the workspace's own tools; copying
from NEST's own files; looking at changes and staging them. And what is not: deleting, anything on the internet, installing, the
assistant's own settings, and saving a snapshot. Then one dialog: yes, use the short list
(recommended); or no, ask me every time.

- **Yes:** write the rules from `kit/claude/setup-permissions.example.json` into
  `.claude/settings.local.json` in the workspace (a file of this computer only, ignored by
  git), exactly as they are, adding to what the file already holds and changing nothing else
  in it. Claude Code asks once for this write; say so. Compare the syntax with FACTS.md. When
  this session's shell tool is PowerShell and FACTS.md does not show how a rule for it is
  written, leave the command rules out and keep the file rules. Record in STATE.md, under
  "Open during the setup", the line `- [ ] take the build permissions out again (wrap-up)`, and
  the rules you added in `_setup/log.md`. Never add a rule that is not in that file, and never
  widen one, whatever would be convenient.
- **No:** tell them that each of Claude Code's questions about a file offers to allow all file
  edits for the rest of the session, and that picking it once is reasonable. It is their
  choice.

Either way, also add the check on dialogs (section 4.2) to the same file: the `hooks` block of
`kit/claude/ask-guard.example.json`, with `uv` as `command` as in the workspace's other hooks and
`_setup/nest/kit` in the script path, plus the line
`- [ ] take the dialog check out again (wrap-up)` under "Open during the setup" in STATE.md.

Never change the permission mode yourself, and never suggest skipping permissions
altogether. The copy into `.claude/` and a commit stay questions on purpose.

**Work in plain single commands, or the list does not help.** (This holds for the whole setup,
the interview and the handover included, and for every helper.) Claude Code can only wave
through a command it can read. A trial with the list in place still had 57 questions, nearly
all of them made by the way the commands were written. So during the build:

- One command per call. No chain with `&&`, `;` or a pipe, no `cd` in front (give paths from
  the workspace root), no shell variable, no brace expansion, no here-document.
- Read a file with the Read tool and search with the search tool, not with `cat`, `sed -n` or
  `grep` in the shell.
- Change a file with the Edit and Write tools, also `_setup/STATE.md` and `_setup/log.md`:
  never `printf >>`, `sed -i` or a script that rewrites a file. Those ask every time, and they
  slip past the scan that checks a file before it is written.
- Copy from the kit with a plain `cp _setup/nest/kit/<path> <target>`, one file per call and
  without options: Claude Code asks for every `cp` that carries an option such as `-R`, whatever
  the list says. A whole folder is one `cp -R` and one question, which is fine.
- Wait for a helper agent by waiting for its result, never with a `sleep` loop in the shell.

Commands that are still asked after that are asked rightly: `git init`, a commit, and the
tests in B4 that write a fake key or remove a test file.

### B1. The skeleton

1. You are now in the workspace folder (check: the current folder is the path in STATE.md and
   `_setup/nest/SETUP.md` exists; if not, see the end of "The handover" in
   `setup/interview.md` and build nothing here). Every file for `.claude/` goes through the
   staging folder (see the top of this section), in B1 and in every later phase: the rules, the
   settings, the terms list, and a later change to one of them (a status word added to the wiki
   rule in B2 is a change in the staging copy, then one copy). One copy into `.claude/` at the
   end of B1, before the stamp of step 11; the only other writes into `.claude/` are
   `settings.local.json` before B1 (the short permission list, the check on dialogs) and its
   clean-up in the wrap-up.
2. `git init -b main` (some systems still start on `master`; the rules and the workflows expect
   `main`), the commit identity from E5 set for this repo (`git config user.name` and
   `user.email` without `--global`), and a `.gitignore` from `kit/github/gitignore.template`:
   keep the `/wiki/` line only when E4 is (a) (check: `git status` runs; `git config user.name`
   prints a name; `CLAUDE.local.md`, `.claude/settings.local.json`,
   `.claude/sensitive-terms.txt`, `.runs/` and `_setup/` are ignored; `wiki/` too if E4 is (a)).
3. `CLAUDE.md`, under 150 lines, in this order: who the assistant is (name, the sentence from F2,
   personality); who the user is (the card from A, at most 10 lines); how to talk; the workspace
   (where things are, how it is opened day to day in the form for `surface`, and the language
   and the local formats from A1 in one line each); the
   wiki rules (the four from section 1, points 1 to 4, in one short list); when the assistant
   acts on its own (D5); with a yes to lessons in D8, one line that a lesson goes into
   `.claude/lessons.json`; the skills list (one line each); and at the top a
   temporary line: "Setup in progress: whatever the first message of a session says, read
   `_setup/nest/SETUP.md` and follow it."
   Write it in the user's language unless they chose English. No project facts that change weekly:
   those live in the wiki (check: `wc -l` under 150; the assistant's name appears in the title).
4. `CLAUDE.local.md` with the private context from A2, A4, C7, and a section "Approved to keep here"
   listing the personal details the user explicitly allowed in the workspace (for example their
   city or background), so the security reviewer does not flag them (check: ignored by git).
5. `.claude/rules/`: from `kit/claude/rules/`, only what applies, at most five (wiki, commits,
   writing, privacy, obsidian), each adapted (check: each file has a `paths` frontmatter if it should
   load by path, per FACTS.md).
6. `scripts/`: copy from `kit/scripts/` with a file copy: `validate.py`, `session_context.py`,
   `session_guard.py`, `nest_update.py`, `agent_git_readonly.py`, `wiki.py`, `skills_catalog.py`,
   `obsidian_setup.py` with its `obsidian.lock.json`, plus, each when its feature was chosen: `wiki_backup.py` (E4 a), `council_score.py` (verdict),
   `idea_page.py` and `blind_seat_guard.py` (verdict or blueprint), `check_style.py`
   (writing-style). Then run `uv run --script scripts/validate.py --self-test` once:
   it proves the scanner works and makes uv fetch Python now, so the first hook does not time out
   (check: the self-test passes; `uv run --script scripts/wiki.py --help` runs). Tell the user
   once what it looks like when uv cannot be found later: every write is refused with a line
   such as `PreToolUse:Write hook error: ... failed; blocking because onFailure is "block"`.
   That is the guard failing safe, not a broken workspace. The cure is to quit the app they
   work in completely (VS Code, or the terminal program) and start it again, so it sees uv.
7. `.claude/settings.json` from `kit/claude/settings.reference.json`: the hooks, permissions from
   D6, the `attribution` block exactly as the reference has it (it keeps "Co-Authored-By" lines out of
   the user's commits), with verdict or blueprint the three allow rules their scripts need
   (`Bash(uv run scripts/council_score.py *)`, `Bash(uv run --script scripts/idea_page.py *)`,
   `Bash(uv run scripts/wiki.py *)`, so a run is not stopped by a prompt halfway), and nothing
   else yet. Always: the secret scan before and after writes and after shell commands, the session-start
   line, and the `session_guard.py` hooks for `start`, `prompt`, `precompact` and `end`. From D8:
   the `lesson` hook and the `plan` hook, each only on a yes: on a no, take that entry out of the
   file. Take out the lists the reference leaves empty (`permissions.ask`, `permissions.deny`,
   `claudeMdExcludes`) when you have nothing to put in them; never the `attribution` block: its
   empty strings are the setting. Leave out the `check_style.py` hook
   unless writing-style was chosen. Keep the exec form the reference uses (`"command": "uv"` with
   `args`, and `${CLAUDE_PROJECT_DIR}` in braces): it runs the same on macOS, Linux and Windows
   without depending on a shell. Compare with FACTS.md (check: valid JSON; the paths in the
   commands exist).
8. `.claude/sensitive-terms.txt`, from `kit/claude/sensitive-terms.example.txt` (keep its
   comment lines, which explain the format, and remove the example lines with `<fill in`): the
   user fills it themselves, in an editor, not in the chat: names, domains, IP ranges or words
   that must never land in a committed file. One per line. You never fill it for them from what
   they told you in the interview. Give the way to open the file that fits where they work: in
   VS Code the file `.claude/sensitive-terms.txt` in the Explorer; else macOS
   `open -e .claude/sensitive-terms.txt`, Windows `notepad .claude\sensitive-terms.txt`, Linux
   `xdg-open .claude/sensitive-terms.txt`. Ask with the dialog: now or later; "later" becomes
   one open item, with one sentence on what the list is for (check: the file exists, even if it
   holds no terms; it is ignored by git).
9. If E7 said yes: `.githooks/pre-commit` from `kit/github/pre-commit` with a file copy (never
   written out by hand: the copy keeps it executable), `chmod +x .githooks/pre-commit` on macOS
   and Linux, `.gitattributes` from `kit/github/gitattributes.template` (it keeps the hook's
   line endings right on Windows) and `git config core.hooksPath .githooks` (check:
   `git config core.hooksPath` prints `.githooks`; on macOS and Linux
   `test -x .githooks/pre-commit` succeeds. Git skips a hook that is not executable without
   saying so).
10. `docs/next-session.md`: a title, then one line per open item as a Markdown checkbox
    (`- [ ] ...`); a done item becomes `- [x] ...`. The session-start line shows the first unchecked
    one (check: `uv run --script scripts/session_context.py` prints it).
11. The stamp: `uv run --script scripts/nest_update.py stamp`. It writes into `nest.json` which
    NEST release this workspace is built from and which kit file each installed file came from,
    so a later release can be brought over without touching what the user changed. With D8
    answers, add them to `nest.json` now: `"update_check": false` inside `nest` when the user
    does not want the session-start line about new releases, and `morning_nudge` when they want
    the nudge (check: `nest.json` has a `nest` block with the version from the header of this
    file; `uv run --script scripts/nest_update.py check` answers: up to date, a newer release, no
    release found, or that it could not reach the source. All four are fine here). The stamp
    is run again at the end of B3, B3b and B5 (each has its own step): it only adds what is new.
    A kit file installed under another name gets `--map <workspace path>=<kit path>`.
12. Update STATE.md (`next: B2`, `read: setup/build.md (B2)`; `trigger:` stays the plain
    "continue"). The guards are active now: say so in
    one line. Offer a stop; otherwise go on with B2 in this session.

### B2. The wiki

1. `wiki.config.json` in the workspace root (next to `CLAUDE.md`, not inside `wiki/`), from
   `kit/scripts/wiki.config.example.json`, with the sections, kinds, status words and labels
   from block C. Keep its `authors` list as it is unless the user wants other names
   (`kit/scripts/WIKI-CONFIG.md` explains every key); pages you write carry `author: claude`
   (check: valid JSON; every section in the tree from C1 is in it). When verdict or blueprint was
   chosen, add the ideas section exactly as `kit/skills/verdict/reference.md` specifies (index type
   `folders`, page `idea.md`, its own status words), with the section name recorded in STATE.md.
   When the user's language is not English, also fill that section's `idea_page.labels` with
   the headings and texts of the idea page in their language (the header of
   `kit/scripts/idea_page.py` lists every key): without it every idea page is half English.
2. The folders, each section's `index.md` from `kit/wiki/section-index.md` (hand-written intro,
   optional Bases embed, the `<!-- AUTO-INDEX -->` marker; context and decisions keep a
   hand-written index), the root pages `index.md`, `log.md`, `Home.md`,
   `how-this-wiki-works.md` from `kit/wiki/`, translated and filled, and the decisions log
   (`log.md` in the decisions section) from `kit/wiki/decisions-log.md` with its format block and
   the user's areas (check: list the `wiki` folder two levels deep; every section has its index).
3. The context pages from block A: profile, goals, priorities, apps and tools, open questions. Each
   with frontmatter (`author: claude`), short, in the user's language. Show them; the user corrects.
4. `_templates/` from `kit/wiki/_templates/`, translated, with the `author` value a note the
   user writes themselves gets (`user`, unless the `authors` list was changed); `_bases/`
   adapted to the sections, the status words and the dashboard from C4.
5. `.obsidian/`, in this order. `kit/wiki/obsidian/PLUGINS.md` has the detail of every step.
   1. **Settings.** Write them before the user opens the vault; if the vault is already open
      in Obsidian, ask them to quit Obsidian first (it rewrites these files from memory).
      Settings from `kit/wiki/obsidian/`, CSS from `kit/wiki/snippets/` with the palette from
      C5. Resolve the `customise:` comments in the CSS and remove them, like everywhere else.
      In the Meta Bind settings (`plugins/obsidian-meta-bind-plugin/data.json`), set
      `excludedFolders` to the user's own names for the templates folder, the inbox, the raw
      sources folder and the archive, plus every other folder in `raw_folders`: a button inside
      text that came from outside must never run.
   2. **One yes.** Say in one or two sentences what gets downloaded (the plugins they chose and
      the theme, each from its own project on GitHub, at a version this release was tried with)
      and that a plugin can do anything Obsidian can. Ask with the dialog. Without a yes,
      record it as an open item and go to step 6; the wiki works as plain notes until then.
   3. **Install.** `uv run --script scripts/obsidian_setup.py install --vault wiki`, where
      `wiki` is the wiki folder (`wiki_dir` in `wiki.config.json`, default `wiki`) (check: it
      ends with 0, and `status` lists every plugin and the theme as installed, each plugin the
      setup wrote settings for still has its settings file (Style Settings ships none, on
      purpose), and none has settings set aside). When it ends with anything but 0 (no
      connection, an Obsidian that is too old, a checksum that does not match, a folder it
      refused, a settings file it could not use), record that as an open item with the reason
      the script printed, and tell the user that reason in plain words; do not work around a
      refusal. When it says the vault is open in Obsidian, or may be, ask the user to quit
      Obsidian and run it again; never add `--assume-closed` on your own, only after the user
      has confirmed that Obsidian is closed. The user never installs a plugin through
      Obsidian's own browser: that sets the settings you wrote aside.
   4. **The user opens the vault,** in three small steps you give one at a time: open the wiki
      folder as a vault (give the full path to paste, never "the folder wiki": people pick the
      folder above it), choose "Trust author and enable plugins", and quit and reopen Obsidian
      once (until then the buttons on Home show as text). Give the steps for the user's own
      system only (the key for pasting a path on theirs, not all three), and each button by the
      name it has on screen, with what it means in their language next to it when Obsidian
      shows it in English.
   5. **Check which folder Obsidian opened:** `uv run --script scripts/obsidian_setup.py vaults`
      must list the wiki folder itself, not the workspace folder above it. When it lists the
      folder above, follow "The wiki folder is not in the list?" in `PLUGINS.md`.
   The user may postpone opening Obsidian and steps 7 and 8: record them as open items, carry
   on with B3, and mention them at most once per session. They never block B3 or B4.
6. `uv run scripts/wiki.py log migrate "Wiki created by NEST"`, then `reindex`, then `lint`
   (check: lint reports zero errors; a search of `wiki/` for `customise:` and `<fill in` finds
   nothing).
7. With a sync route from C8: offer, with the dialog, to set it up now or leave it as an open
   item. Now means you give the steps from `kit/wiki/obsidian/DEVICES.md` for their route one
   at a time, in their language, and they do them: signing in, paying and installing an app on
   a phone are theirs. You change no file for it. Later means one open item with those steps in
   `docs/next-session.md`. Either way it never blocks B3.
8. Ask the user to look at Home in Obsidian and say what looks wrong; this is the one thing in
   the build only their eyes can check. Give them what to look for: buttons in the tiles, a
   colour per section in the sidebar, their own section names. Fix, lint again.

### B3. Skills and agents

1. For each skill chosen in D, and always `nest-update`: create `.claude/skills/<name>/` (through
   the staging folder, one copy for all skills and agents at the end of step 3) from
   `kit/skills/<name>/`. Rewrite,
   don't copy: paths and section names from `wiki.config.json`, labels in the user's language,
   their apps from A7, every `<!-- customise: ... -->` resolved and removed. The exception:
   `obsidian-markdown` and `obsidian-bases` come from Obsidian's own repository; copy those two
   folders as they are, with their `NOTICE.md` (the licence asks for it), and change nothing.
   With the obsidian plugin chosen in D9, do not copy them at all: the plugin brings both. For verdict and blueprint
   take `SKILL.md` with `formats.md` (full) or `SKILL.light.md` renamed to `SKILL.md` with
   `formats.light.md` kept under its own name (light; the skill refers to it), plus the other
   supporting files in the folder (`reference.md`, `run-files.md`). Leave out the files of the
   variant that was not chosen. Idea pages come in two looks: styled (own callout types, needs the
   `idea-note.css` snippet) or plain (standard callouts only). Resolve the `callout` customise
   markers in both skills and the `idea-note` entry in `.obsidian/appearance.json` the same way:
   styled when the user said yes to the Minimal theme in C6 and to the styled look in D2, else plain.
   Add `.runs/` to `.gitignore` if it is not there.
2. The agents those skills need, from `kit/agents/full/` or `kit/agents/light/`, plus `researcher`
   with research and `security-reviewer` always. Adjust names, output language and the user
   description; keep tools to the minimum each agent needs. The agent files ship with their hooks in the frontmatter: leave
   those lines as they are. The security reviewer's hook (`scripts/agent_git_readonly.py`) keeps
   it read-only; on Windows add `PowerShell` to that agent's `tools`. The blind seats
   (`council-outsider`, `council-verifier`, `architect-dreamer`, where built) carry a hook that
   runs `scripts/blind_seat_guard.py` with `--seat <name>`: it keeps each of them inside its own
   run file. When you rename a seat, keep the original name after `--seat`. When the run folder
   is not `.runs`, record that under `blind_seats` in `nest.json` (the script's header shows the
   shape).
   Build the skills one at a time and run `uv run --script scripts/skills_catalog.py --check` after
   each one, or in parallel with helper agents: then give each helper the frontmatter rules from
   FACTS.md, and before the stop point check every file they wrote (catalogue check, secret scan,
   no `customise:` left). Saving verdict and blueprint results always goes through
   `scripts/idea_page.py`, never through a script you write yourself.
3. `disable-model-invocation` per skill from D5. The skills list in CLAUDE.md, one line each.
4. `uv run scripts/skills_catalog.py` to write `docs/skills.md`, then
   `uv run scripts/skills_catalog.py --check --installed` (check: zero problems; `--installed`
   also fails on a `customise:` or `<fill in` marker left in a skill or agent).
5. `uv run --script scripts/nest_update.py stamp` again, so the skills and agents are in the
   stamp (check: `nest.json` lists a file under `.claude/skills/nest-update/`).
6. **Plugins chosen in D9**, one at a time, with its card from Appendix C open. Say first, in
   one line, that this downloads the plugins the user chose.
   1. **What it needs.** `node --version` (22.18 or newer for claude-hud, any for
      session-report), `python3 --version` (3.10 to 3.14 for ppt-master; `python --version` on
      Windows), `uv --version` for dutchquill (the setup's own uv is enough; without uv,
      `python3` at 3.10 or newer). Node missing or too old: offer the install the way Phase 0.2 installs a tool,
      after a yes. `python3` at another version: ppt-master becomes an open item; do not offer a
      second Python, which the plugin would not use, and never change the user's default one.
      Without what it needs, the plugin is not installed and becomes an open item.
   2. **Check the card.** Read the plugin's manifest and, where they exist, its hooks file and
      `.mcp.json` from the source at the version you will install (the maker's repository on
      GitHub; for `claude-plugins-official` the folder `plugins/<name>/` there). When it brings
      a hook, a server or a script the card does not name, do not install it: tell the user
      what changed, and it becomes an open item.
   3. **Install** in the project scope, one command per call. When `claude` is not found (Windows
      with only the VS Code extension has no `claude` on its path), use the program the
      extension brings: `<home>\.vscode\extensions\anthropic.claude-code-<version>-win32-x64\resources\native-binary\claude.exe`,
      the newest version folder there, by its full path; the same folder holds `claude` on
      macOS and Linux. Only when there is none, the lines below are for the user, as said there.
      `claude plugin install <name> --marketplace <source> --scope project`, with `<source>` from
      the card (`anthropics/claude-plugins-official` for Anthropic's plugins, the
      `owner/repo#tag` given otherwise). An older Claude Code that does not know `--marketplace`:
      `claude plugin marketplace add <source>` first, then
      `claude plugin install <name>@<marketplace> --scope project`. Check: the exit status is 0
      and `enabledPlugins` in the workspace's `.claude/settings.json` lists `<name>@<marketplace>`
      as `true`. Check only that file: never read the user's own Claude Code settings
      (`~/.claude/settings.json`), which can hold keys. When Claude Code refuses the command,
      the same lines are for the user to run in a terminal in the workspace folder (in VS Code:
      Terminal, New Terminal); then check that file again, and believe the file, not the report.
   4. **What a card adds.** ppt-master: its four core packages with
      `python3 -m pip install --user python-pptx XlsxWriter skia-pathops uharfbuzz`, after
      their own yes. When pip refuses because the system manages that Python, never force it
      (no `--break-system-packages`): it becomes an open item with the link to the maker's
      install notes. `flask` only when the user wants ppt-master's pages in the browser; without
      it, ppt-master confirms in the chat. claude-hud: its setup (`/hud`) runs in the test session, after the yes
      from its card, because the plugin loads when a session starts. The obsidian plugin's
      `defuddle`, `knap` and `ob` programs are installed only when the user first asks for
      what they do.
      dutchquill: `/dutchquill:instellen` runs in the test session, after the yes from its card;
      it asks where its work folder goes, and its first `dq` command downloads its Python
      packages into the plugin's data folder, so say that once.
   5. In `CLAUDE.md`, under the skills list, one line per plugin: what it is for, and that its
      maker keeps it up to date.
7. Stop point: STATE.md `next: B3b` (or `next: B4` without integrations to connect now), the
   commit question for this session, and a new session for what comes next: the tests run in a
   session that starts the way every later one will, with the workspace's own `CLAUDE.md`,
   rules, skills and hooks loaded from the start.

### B3b. Integrations

Per integration skill the user wants connected now (D4), in a fresh session. A skill whose
connection was postponed has nothing to do here: its open item stays.

1. Connect the route the user chose: add the MCP server, enable the connector, or run the login
   script. Only after a yes; a login the user does themselves, in the form for where they work (section 3). Tokens stay where the
   route keeps them, never in the workspace. Add an MCP server in the local scope (the default
   of `claude mcp add`), not the project scope: a project-scoped server is written to
   `.mcp.json` in the workspace, which can hold addresses and keys. For the Microsoft route: copy
   `kit/integrations/microsoft-graph/graph.py` to `scripts/graph.py` and follow its README (the
   user registers the app and signs in with the device code; NEST never sees a password).
2. `tool-map.md` in the workspace root, from `kit/integrations/tool-map.example.md`: which tool does
   which operation, from the tools that now actually exist; `none` where nothing does (always for
   `mail.send`).
3. Permission rules in `.claude/settings.json` from D4 point 3, in the syntax of
   `kit/integrations/permissions.example.json`: `ask` for every action with "yes" under
   "Ask first" in the tool map, `deny` for any send-mail tool the route offers and for reading
   the folder where the route keeps its token. MCP rules cannot be limited per argument, so gate
   the whole tool.
4. `uv run --script scripts/nest_update.py stamp` again, so `scripts/graph.py` and
   `tool-map.md` are in the stamp when they were installed.
5. Stop point when a server or connector was added: STATE.md `next: B3b, step 6 (test the
   integrations)`, the commit question for this session, and a new session so the new tools
   load. A route that is only a script (the Microsoft route) needs no new session: go on.
6. One read-only test per integration: the next three appointments, or the unread count, or
   today's weather (check: the result is real and matches what the user sees in their app).
   Only then tick it.
7. Anything that did not work: STATE.md "Open", with what is missing. Then `next: B4`.

### B4. Test

In a session that started after B3 (and after B3b step 5 when a server or connector was added).
Record every outcome in `_setup/log.md`.

**You run the tests, not the user.** The first real user spent twenty-four minutes and
twenty-one messages here supplying a note, an idea, approvals and typed commands, until she
wrote "do all the tests that are still needed" and the assistant simply did. Start with one
dialog: you will now test the workspace yourself, it takes about ten minutes (about twenty with
a team to run), they can watch or step away; and, with a team installed, whether to include a
trial run of the team now (recommended) or leave it for their first real idea. After that, ask
nothing until the tests are done, except when something fails in a way only they can judge.

Everything the tests write is yours and temporary. Keep a list in `_setup/log.md` of every file
a test created or changed. The user's wiki must look afterwards as it did before, except for
the wiki log.

1. **Secret guard:** `uv run --script scripts/validate.py --self-test` passes; then try to write a
   file containing a fake key in the shape of a real one (for example a GitHub token prefix with
   random characters): the write is blocked. Never use a real key. With the pre-commit scan
   (E7): put the same fake key in a new file `guard-test.txt` with a shell command (the one
   place a shell write is meant; the scan after the command reports the key, which is the
   guard working), `git add` it and try to commit: the commit is refused. Then take the file out again
   (`git rm --cached guard-test.txt`, and remove this test file you made yourself).
2. **Session start:** the session-start line appeared at the start of this session. After the
   first message, `.claude/.session/` holds a words file with that message in it.
3. **Wiki:** without the wiki skills (the backbone only): lint is zero and the context pages
   open; go on to step 4. With them: write a sample note into the inbox yourself, two lines in
   the user's language on a neutral subject, with a title that starts with the word for "test"
   in their language. Run the inbox skill on it and approve its proposal yourself; check the
   note is filed, linked and logged, and the original is in the archive unchanged. Ask one
   question with the query skill that the sample note answers. Then take the test out again:
   remove the filed page and the archived original, run `reindex` and `lint` (zero), and add one
   line to the wiki log that a setup test was run and removed. These are files you made for the
   test, not the user's notes: the rule that nothing is deleted is about theirs.
4. **One run per chosen team,** when the user said yes to it in the opening dialog: an idea of
   your own, small and harmless, in the area the user named in block B (never their real idea:
   that one deserves a run they follow). Run it through `verdict` (light or full) and, if chosen,
   through `blueprint`. Say at the start of the run that it is a setup test, approve the brief
   yourself, and take the recommended answer to every question a seat asks. Check the board
   shows and the score comes from `council_score.py`. Do not save the result to the wiki: the
   run files under `.runs/` are enough proof, and they are ignored by git. Saving is tested by
   the script itself (`uv run --script scripts/idea_page.py --help` runs).
5. **Each other chosen skill:** one natural test phrase from its `metadata.try`, which you run
   yourself. A skill that only the user can start (`disable-model-invocation: true`) is not run:
   its test is that `uv run --script scripts/skills_catalog.py --check --installed` passes and
   that every file and section its `SKILL.md` names exists. Never ask the user to type a list
   of commands for you. An integration skill that is not connected yet: its test is that it says
   so in one line and invents nothing. **Each installed plugin:** `claude plugin list` shows it
   enabled in the project scope, and one natural request uses it (a diagram of the user's week, a
   playground for a choice they named, a usage report). claude-hud: run its setup after the yes
   from its card; the test is that the line shows under the chat.
6. **Updates:** `uv run --script scripts/nest_update.py plan` says the workspace is up to date (or
   that it could not reach the source, which is an open item, not a failure).
7. **Leftovers:** search the workspace for `customise:`, `<fill in` and `TODO` outside `_setup/`
   (check: nothing, or each one is a known open item). `git status` shows no file a test left
   behind.
8. **Tell the user** in at most six lines what you tested, what passed, and what is open. One
   thing is theirs, if it is still open from B2: looking at Home in Obsidian.

### B5. GitHub

Only with a GitHub account (E1); each action after a yes. Without one, do step 1 only when the
user wants a README, and go on to the final check.

1. README from `kit/github/README.template.md` in the style from E6 (also without GitHub, when
   the user answered E6 or asks for one), with the name, the tagline from
   F2 and a "what is in here" table generated from the chosen parts. Never personal details.
2. `.github/` from `kit/github/`, as chosen in E7: `workflows/gitleaks.yml`,
   `workflows/checks.yml` (it runs the skills catalogue check and the secret scan on every
   push) and `dependabot.yml`.
3. Ask the `security-reviewer` agent to scan everything that will be pushed. Fix hard findings.
4. `gh repo create <name> --private --source . --remote origin`, then push after a yes. With
   the gitleaks workflow, find its first run (`gh run list --workflow gitleaks.yml --limit 1`;
   ask again after a few seconds when none is listed yet), wait for it with
   `gh run watch <id> --exit-status`, and tell the user the result in one line. It scans the whole history on every run. When it
   fails, read the log (`gh run view <id> --log-failed`) and say what it found; never tell the
   user that a later run will fix a failed scan.
5. Wiki backup per E4 (a): the backup needs its own private repository, so after a yes
   `gh repo create <name>-wiki --private` (no `--source`: the script fills it). Then
   `uv run scripts/wiki_backup.py init <private-repo-url>` and the first backup after a yes;
   record the git dir in `nest.json` (`wiki_backup.git_dir`), so a second workspace with the
   same folder name can never share it. The first backup scans every page for secrets; when it
   stops on one, show the user the line: they replace the value, or say it is a false alarm
   (then `--no-scan`, once). The backup uses git's own identity settings: when the
   script says name and address are missing, set the ones from E5 for the backup only
   (`git --git-dir <its git dir> config user.name ...` and `user.email`), not with `--global`
   (check: the session-start line shows the backup state).
6. `uv run --script scripts/nest_update.py stamp` again, so the files under `.github/` are in
   the stamp. STATE.md: `next: section 9 (final check)`, `read: setup/finish.md`.
