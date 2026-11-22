# NEST setup: the build

Part of the NEST setup prompt. `SETUP.md`, one folder up, holds the rules for every part and says
when to read this one. Read `SETUP.md` first.

---

## 8. Build

At the start of each build phase (B1, B2, B3, B3b, B5) show the whole plan for that phase as one
short tree or list and ask **one yes for the phase**. Then build its steps one after the other
without asking again, unless something deviates from the plan, leaves the machine, or cannot be
undone. After each step run its check and tick the line in STATE.md. If a check fails, fix the
cause; never tick around it. Commits stay separate questions.

### B1. The skeleton

1. You are now in the workspace folder (check: the current folder is the path in STATE.md and
   `_setup/nest/SETUP.md` exists; if not, see the end of "The handover" in
   `setup/interview.md` and build nothing here). Writes into `.claude/` ask for permission in Claude Code; tell
   the user before B1 starts so they expect those prompts and approve them. If a write there is
   refused anyway, build the files under `_setup/build/dot-claude/` and give the user one copy
   command for their OS; after they say it ran, run the stamp of step 11 again, so the files
   under `.claude/` are in it. A refusal counts for that moment only: at the start of each
   later phase try one write into `.claude/` again before you fall back.
2. `git init -b main` (some systems still start on `master`; the rules and the workflows expect
   `main`), the commit identity from E5 set for this repo (`git config user.name` and
   `user.email` without `--global`), and a `.gitignore` from `kit/github/gitignore.template`:
   keep the `/wiki/` line only when E4 is (a) (check: `git status` runs; `git config user.name`
   prints a name; `CLAUDE.local.md`, `.claude/settings.local.json`,
   `.claude/sensitive-terms.txt`, `.runs/` and `_setup/` are ignored; `wiki/` too if E4 is (a)).
3. `CLAUDE.md`, under 150 lines, in this order: who the assistant is (name, the sentence from F2,
   personality); who the user is (the card from A, at most 10 lines); how to talk; the workspace
   (where things are, with the language and the local formats from A1 in one line each); the
   wiki rules (the four from section 1, points 1 to 4, in one short list); when the assistant
   acts on its own (D5); with a yes to lessons in D8, one line that a lesson goes into
   `.claude/lessons.json`; the skills list (one line each); and at the top a
   temporary line: "Setup in progress: next session, read `_setup/nest/SETUP.md` and follow it."
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
   `obsidian_setup.py` with its `obsidian.lock.json`, plus, each when its feature was chosen: `wiki_backup.py` (E4 a), `council_score.py` (idea),
   `idea_page.py` and `blind_seat_guard.py` (idea or blueprint), `check_style.py`
   (writing-style). Then run `uv run --script scripts/validate.py --self-test` once:
   it proves the scanner works and makes uv fetch Python now, so the first hook does not time out
   (check: the self-test passes; `uv run --script scripts/wiki.py --help` runs). Tell the user
   once what it looks like when uv cannot be found later (a new terminal without it on the
   PATH, an app started from the dock): every write is refused with a line such as
   `PreToolUse:Write hook error: ... failed; blocking because onFailure is "block"`. That is the
   guard failing safe, not a broken workspace: start Claude Code from a terminal where
   `uv --version` works.
7. `.claude/settings.json` from `kit/claude/settings.reference.json`: the hooks, permissions from
   D6, the `attribution` block exactly as the reference has it (it keeps "Co-Authored-By" lines out of
   the user's commits), with idea or blueprint the three allow rules their scripts need
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
   comment lines, which explain the format, and remove the example lines with `<fill in`): the user fills it themselves, in an editor, not in the chat:
   names, domains, IP ranges or words that must never land in a committed file. One per line.
   The folder is hidden in most file explorers, so give the command that opens the file in
   their editor (macOS `open -e .claude/sensitive-terms.txt`, Windows
   `notepad .claude\sensitive-terms.txt`, Linux `xdg-open .claude/sensitive-terms.txt`). Ask:
   now or later (check: the file exists, even if it holds no terms; it is ignored by git).
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
12. Stop point: update STATE.md (`next: B2`, `read: setup/build.md (B2)`,
    `trigger: Read _setup/nest/SETUP.md and follow it.`),
    ask to commit, then ask the user to close Claude Code and start it again in this folder, so the
    hooks and settings load.

### B2. The wiki

Do this in the new folder, in a fresh session (the hooks are now active).

1. `wiki.config.json` in the workspace root (next to `CLAUDE.md`, not inside `wiki/`), from
   `kit/scripts/wiki.config.example.json`, with the sections, kinds, status words and labels
   from block C. Keep its `authors` list as it is unless the user wants other names
   (`kit/scripts/WIKI-CONFIG.md` explains every key); pages you write carry `author: claude`
   (check: valid JSON; every section in the tree from C1 is in it). When idea or blueprint was
   chosen, add the ideas section exactly as `kit/skills/idea/reference.md` specifies (index type
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
5. `.obsidian/`: settings from `kit/wiki/obsidian/`, CSS from `kit/wiki/snippets/` with the palette
   from C5. Resolve the `customise:` comments in the CSS and remove them, like everywhere else.
   In the Meta Bind settings (`plugins/obsidian-meta-bind-plugin/data.json`), set
   `excludedFolders` to the user's own names for the templates folder, the inbox, the raw sources
   folder and the archive, plus every other folder in `raw_folders`: a button inside text that
   came from outside must never run. Write all of this before the user opens the vault; if the
   vault is already open in Obsidian, ask them to quit Obsidian first (it rewrites these files
   from memory). Then install the theme and the plugins yourself, as
   `kit/wiki/obsidian/PLUGINS.md` describes: say in one or two sentences what gets downloaded
   (the plugins they chose and the theme, each from its own project on GitHub, at a version this
   release was tried with) and that a plugin can do anything Obsidian can, ask for one yes, and
   run `uv run --script scripts/obsidian_setup.py install --vault wiki` (check: `status` lists
   every plugin and the theme as installed, each plugin still has its settings file, and no
   `data.json.bak` exists). The user never installs a plugin through Obsidian's own browser: that
   sets the settings you wrote aside. What is left for them is two clicks: open the `wiki`
   folder as a vault, and choose "Trust author and enable plugins". Without a yes, or without a
   connection, record it as an open item; the wiki works as plain notes until then. The user may
   postpone opening Obsidian and step 7: record both as open items, carry on with B3, and
   mention them at most once per session. They never block B3 or B4.
6. `uv run scripts/wiki.py log migrate "Wiki created by NEST"`, then `reindex`, then `lint`
   (check: lint reports zero errors; a search of `wiki/` for `customise:` and `<fill in` finds
   nothing).
7. Ask the user to open Home in Obsidian and say what looks wrong. Fix, lint again.

### B3. Skills and agents

1. For each skill chosen in D, and always `nest-update`: create `.claude/skills/<name>/` from
   `kit/skills/<name>/`. Rewrite,
   don't copy: paths and section names from `wiki.config.json`, labels in the user's language,
   their apps from A7, every `<!-- customise: ... -->` resolved and removed. The exception:
   `obsidian-markdown` and `obsidian-bases` come from Obsidian's own repository; copy those two
   folders as they are, with their `NOTICE.md` (the licence asks for it), and change nothing. For idea and blueprint
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
   no `customise:` left). Saving idea and blueprint results always goes through
   `scripts/idea_page.py`, never through a script you write yourself.
3. `disable-model-invocation` per skill from D5. The skills list in CLAUDE.md, one line each.
4. `uv run scripts/skills_catalog.py` to write `docs/skills.md`, then
   `uv run scripts/skills_catalog.py --check --installed` (check: zero problems; `--installed`
   also fails on a `customise:` or `<fill in` marker left in a skill or agent).
5. `uv run --script scripts/nest_update.py stamp` again, so the skills and agents are in the
   stamp (check: `nest.json` lists a file under `.claude/skills/nest-update/`).
6. Stop point: STATE.md `next: B3b`, ask to commit, ask for a restart so skills and agents load.

### B3b. Integrations

Per integration skill the user wants connected now (D4), in a fresh session. A skill whose
connection was postponed has nothing to do here: its open item stays.

1. Connect the route the user chose: add the MCP server, enable the connector, or run the login
   script. Only after a yes; a login the user does themselves (`! <command>`). Tokens stay where the
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
   integrations)`, ask to commit, ask for a restart so the new tools load. A route that is only
   a script (the Microsoft route) needs no restart: go on.
6. One read-only test per integration: the next three appointments, or the unread count, or
   today's weather (check: the result is real and matches what the user sees in their app).
   Only then tick it.
7. Anything that did not work: STATE.md "Open", with what is missing. Then `next: B4`.

### B4. Test

In a session that started after B3 (and after B3b step 5 when a server or connector was added).
Record every outcome in `_setup/log.md`.

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
   open; go on to step 4. With them: ask the user for a small real note for the inbox (a thought, a link, a question);
   write a sample yourself only if they would rather not. Run the inbox skill, check it is filed,
   linked, logged, and the original is in the archive unchanged. Ask one question with the query skill. Lint is zero.
4. **One run per chosen team:** a small, real idea of the user's through `idea` (light or full),
   and, if chosen, through `blueprint`. Check the board shows, the score comes from
   `council_score.py`, and saving writes the idea pages and lint stays zero.
5. **Each other chosen skill:** one natural test phrase from its `metadata.try`. An integration
   skill that is not connected yet: its test is that it says so in one line and invents nothing.
6. **Updates:** `uv run --script scripts/nest_update.py plan` says the workspace is up to date (or
   that it could not reach the source, which is an open item, not a failure).
7. **Leftovers:** search the workspace for `customise:`, `<fill in` and `TODO` outside `_setup/`
   (check: nothing, or each one is a known open item).

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
4. `gh repo create <name> --private --source . --remote origin`, then push after a yes.
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
