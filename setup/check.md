# NEST setup: the machine check

Part of the NEST setup prompt. `SETUP.md`, one folder up, holds the rules for every part and says
when to read this one. Read `SETUP.md` first.

---

## 5. Phase 0: check the machine and fetch the docs

Do this before the first interview block. A half interview on a machine that misses half the
tools is work done twice.

**0.1 Where are we.** Confirm the current folder is the NEST folder (it contains `SETUP.md`,
`setup/` and `kit/`). The NEST repository has a `CLAUDE.md` for people who work on NEST itself; it does not
apply to a setup, ignore it. Create `_setup/` with `STATE.md`, `log.md`, `interview/`,
`open-questions.md`, `backlog.md`.

**0.1b The setup's own notes, without a question each time.** During the interview you write
often, and only in one place: the folder `_setup/` (the user's answers, the state, the log).
In Claude Code's default mode every one of those writes is a permission question; a trial
counted thirty in one interview. So right after the language is chosen, say in two plain
sentences that Claude Code asks before it changes a file, and that you would like to write your
own notes of this setup without asking each time: only in the folder `_setup/`, nothing else.
Then one dialog: yes, or no, ask me every time. After a yes, write `.claude/settings.local.json`
in this folder with exactly one rule under `permissions.allow`, `Edit(/_setup/**)`, adding to
what the file holds and changing nothing else (Claude Code asks once for this write; say so),
and note in STATE.md under "Open during the setup" the line
`- [ ] take the interview permission out again (handover)`. Nothing else goes on this list
during the interview: commands, installs and the network stay questions. With a no, tell them
that each of those questions offers to allow all edits for the session.

**0.2 What machine, and where the user works.** Detect the OS and version (macOS `sw_vers`,
Windows `ver`, Linux `/etc/os-release` for the distribution, not only the kernel).

Then find out where the user is typing, and store it as `surface` in STATE.md: the environment
variable `CLAUDE_CODE_ENTRYPOINT` says `claude-vscode` in the Claude Code panel of VS Code and
`cli` in a terminal. When it says something else or is empty, ask one closed question: where
are you typing this (the Claude panel in VS Code, a terminal window, the Claude desktop app,
something else). Everything you tell the user to do from here on takes the form for that place
(section 3, "Starting a session").

Then check, one line each with ✓ or ✗:

| Tool | Why | Check |
|---|---|---|
| Claude Code | runs everything; v2.1.295 or later is needed (blocking hooks use `onFailure`; the agent teams use `omitClaudeMd`, v2.1.271+) | terminal: `claude --version`. VS Code panel: `claude` is usually not found there, which is normal (the extension brings its own copy); read the version with `code --list-extensions --show-versions` (the line `anthropic.claude-code@<version>`), and when that does not work either, note it and go on |
| git | versioning, backups | `git --version` |
| uv | runs the Python scripts on every OS, installs Python itself | `uv --version` |
| Obsidian | opens the wiki | macOS: `/Applications/Obsidian.app`; Windows: Start menu or `%LOCALAPPDATA%\Programs\Obsidian`; Linux: `which obsidian`, flatpak or AppImage; else ask |
| GitHub CLI (optional) | GitHub setup in block E | `gh --version`, `gh auth status` |

For every ✗: say in one plain sentence what the tool is for before you name it ("a small
helper that runs the tools of your workspace; it is called uv"), in the user's language, also
inside the dialog. Look up the current install command for this OS on the tool's own site
(fetch the page; do not rely on memory). Install only after a yes, and run the command
yourself. Only a command that needs the user's own login or admin rights is theirs to run: in
a terminal they type `! <command>`; in the VS Code panel they open Terminal > New Terminal and
paste it there.

After an install, run the tool's check again. A tool that was just installed is often not
found yet, because this app started before it existed. Do not stop for that: find where the
installer put the program (it usually prints the path), use that full path from then on, and
write it under `tool_paths:` in STATE.md, so a later session that still cannot find it by name
uses it too (a new conversation inherits the app's old list of programs). Only for uv set
`restart_app: yes`: the workspace's hooks call it by name, and a hook cannot use a path from
STATE.md. The user then quits and restarts the app once, at the next moment they reopen
something anyway (section 3). Only when you cannot find the program at all is this a stop
point.

**Signing in to GitHub.** When the GitHub CLI is installed and `gh auth status` says it is not
signed in (now, in block E or in the build, whichever comes first with a GitHub account), first
say in one line what happens: GitHub asks once whether this computer may work in their
account. Then one *choice*: I start the sign-in and you only log in on the GitHub website
(recommended); or you do it yourself in a terminal, step by step.
- **I start it:** run `gh auth login --web --hostname github.com --git-protocol https` as a
  background command (with the full path from `tool_paths:` when `gh` is not found by name).
  Without a terminal to type in, it prints a one-time code (`XXXX-XXXX`) and the address
  `https://github.com/login/device`, and waits. Read the code from its output, give it to the
  user in a message of its own with the code alone on a line, and open the address in their
  browser (macOS `open`, Windows `start ""`, Linux `xdg-open`). The code is not a secret: it
  only works for the person who logs in, for a few minutes. The user logs in, types the code
  and approves. When the background command has finished, check with `gh auth status`, then
  run `gh auth setup-git` so git uses the same sign-in. When it ended without a sign-in (the
  code expired, the user cancelled), offer it once more, then the other route.
- **Yourself:** the steps for where they work (section 3): in a terminal `! gh auth login`, in
  the VS Code panel Terminal > New Terminal, with the answers to its questions written out
  (GitHub.com, HTTPS, yes, log in with a web browser) and "say done when you are through".
  Then the same checks.

**0.3 Fetch the docs.** Save these Claude Code docs pages to `_setup/docs/` with `curl -sL`
(`curl.exe -sL` on Windows; append `.md` to the URL if the page comes back as HTML), not with a
summarising tool, so the exact field names survive:

- `https://code.claude.com/docs/en/memory` (CLAUDE.md, imports, rules)
- `https://code.claude.com/docs/en/skills`
- `https://code.claude.com/docs/en/sub-agents`
- `https://code.claude.com/docs/en/hooks`
- `https://code.claude.com/docs/en/settings` (permissions, `claudeMdExcludes`)
- `https://code.claude.com/docs/en/mcp`
- `https://code.claude.com/docs/en/discover-plugins` (install scopes, `--marketplace`, updates)
- with `surface: vscode`: `https://code.claude.com/docs/en/vs-code` (how a conversation is
  started and resumed in the panel, and what the panel does not have)

If a URL moved, find the new one from `https://code.claude.com/docs/en/overview`. Write
`_setup/docs/FACTS.md`: per page the field names and behaviours this setup relies on (skill
frontmatter fields, agent frontmatter fields, hook events and stdin JSON, exit code 2, permission
rule syntax for MCP tools, how rules load by path). From now on FACTS.md overrides this file.

Windows: note in `_setup/log.md` what the hooks page says about how Claude Code runs hooks
there (which shell, whether Git for Windows is needed). B1 uses the exec form, which needs no
shell, so this is only a fallback.

**0.4 What Claude can reach.** List the MCP servers and connectors this session already has, by
**name only**, from the tool names you can see (`mcp__<server>__<tool>`). Do **not** run
`claude mcp list` or read MCP configuration files: they print full server URLs and headers, which
often contain API keys and tokens, and whatever is printed lands in the session transcript. If the
user wants to know more about a server, ask them to look it up themselves. Write the names to
`_setup/log.md`; blocks D and E use the list. Do not call any of the servers yet.

**0.5 The user's level.** One closed question, with each word explained in a few words inside
the question: how at home are you with a terminal (a window where you type commands), git
(keeping versions of your files) and Obsidian (the notes app)? (new to all / used some /
daily). Store it as `level` in STATE.md. It decides how much you explain and how much you ask
(section 4.2).

**0.5b The check on dialogs.** Now that uv is on this machine, add the check that keeps every
proposal inside its dialog (section 4.2): copy the `hooks` block of
`kit/claude/ask-guard.example.json` into `.claude/settings.local.json` in this folder, adding
to what the file holds and changing nothing else, with the full path of uv as `command` (from
`command -v uv`, or `where uv` on Windows; a bare `uv` is not found by an app that was open
before uv was installed) and `kit` in the script path. Claude Code asks once for this write;
say in one line that this is a check on your own questions, not a permission. Add the line
`- [ ] take the dialog check out again (handover)` under "Open during the setup" in STATE.md.
When the write is refused, note it in `_setup/log.md` and go on: the rule in 4.2 still holds.

**0.6 Tell the plan.** The session plan from section 3, in two or three lines. Then block A:
read `setup/interview.md` now, and set `read:` in STATE.md to it.
