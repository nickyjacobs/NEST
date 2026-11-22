<sub>[Docs](../README.md) · [What to expect](../guide/what-to-expect.md) · [Updating](../guide/updating.md) · [FAQ](../guide/faq.md) · [nest.json](../reference/nest-json.md) · [Hooks](../reference/hooks-notes.md) · [Releasing](../project/releasing.md) · [Backlog](../project/backlog.md)</sub>

# Claude Code hooks: notes for NEST

Source: https://code.claude.com/docs/en/hooks (fetched as Markdown via `/docs/en/hooks.md` on
2026-11-21, twice, and checked again on 2026-11-22), plus `/docs/en/skills.md`,
`/docs/en/sub-agents.md`, `/docs/en/memory.md`, `/docs/en/settings.md`, `/docs/en/sessions.md` and
`/docs/en/tools-reference.md`. Re-check these facts when Claude Code changes; the scripts in
`kit/scripts/` depend on them.

**On this page:** [Input on stdin (JSON)](#input-on-stdin-json) · [Exit codes and feedback](#exit-codes-and-feedback) · [Hook command format, and Windows](#hook-command-format-and-windows) · [Matchers](#matchers) · [Shell commands and the tools around them](#shell-commands-and-the-tools-around-them) · [Hooks in agent and skill frontmatter](#hooks-in-agent-and-skill-frontmatter) · [Not documented, so not relied on](#not-documented-so-not-relied-on) · [Settings facts](#settings-facts) · [Frontmatter fields (for `skills_catalog.py --check`)](#frontmatter-fields-for-skills_catalogpy---check)

## Input on stdin (JSON)

- The input is UTF-8. A script must read it as bytes and decode it itself
  (`sys.stdin.buffer.read().decode("utf-8")`): on Windows, before Python 3.15, a text read of a
  pipe uses the console code page, which garbles an accent and fails on a curly quote. Every
  hook script in the kit reads bytes.
- Common: `session_id`, `transcript_path`, `cwd`, `hook_event_name`, `permission_mode` (not on
  every event), `agent_id` / `agent_type` inside a subagent, `prompt_id`, `effort`,
  `scratchpad_dir`. `agent_type` is the `name` from the agent's frontmatter, not the file name.
- PreToolUse / PostToolUse: `tool_name`, `tool_input`, `tool_use_id`; PostToolUse adds
  `tool_response` and `duration_ms`. PostToolUse runs after a tool call that succeeded.
- PostToolUseFailure runs when a tool that started failed; for Bash and PowerShell that includes
  a command that ran and exited with another code than 0 (`error` starts with `Exit code N`). It
  gets `tool_name`, `tool_input`, `error`, optionally `is_interrupt` and `duration_ms`, and does
  not fire for a call that was refused before it ran. `validate.py --hook shell` is wired on
  both events, because a command can write a file and still fail.
- `tool_input` per tool: Write `file_path`, `content`; Edit `file_path`, `old_string`,
  `new_string`, `replace_all`; Bash and PowerShell `command`, `description`, `timeout`,
  `run_in_background`. NotebookEdit edits one cell (`notebook_path`, `new_source`).
- `file_path` is always absolute. On Windows it arrives with backslashes, even under Git Bash:
  normalise with `replace("\\", "/")` before comparing paths.
- MultiEdit is no longer in the tool list. `validate.py` still reads a legacy `edits[]` array, and
  the matcher still names MultiEdit, which is harmless.
- SessionStart: `source` (`startup`, `resume`, `clear`, `compact`, `fork`), optionally `model`,
  `agent_type`, `session_title`.
- UserPromptSubmit: `prompt`, the submitted text; a typed skill or command arrives as typed, not
  expanded. `session_guard.py --event prompt` keeps it word for word.
- PreCompact: `trigger` (`manual`, `auto`) and `custom_instructions`. On exit 0 its stdout becomes
  instructions for the compaction summary (cap 10,000 characters per hook), which is how
  `session_guard.py --event precompact` hands the user's own words to the summary.
- SessionEnd: `reason`. No decision control; default timeout 1.5 s, raised by a per-hook `timeout`.
- Read `file_path`, `offset`, `limit`; Glob `pattern`, `path`; Grep `pattern`, `path`, `glob`.
  `blind_seat_guard.py` reads these together with `agent_type`.
- ExitPlanMode: Claude Code injects `plan` and `planFilePath` into `tool_input`; in PostToolUse
  `tool_response` is an object whose `plan` holds the approved plan. `session_guard.py --event
  plan` saves only that: the plan in `tool_input` is the proposal, approved or not.
- No hook input carries the context window's fill level. `context_tokens` exists only on
  SessionStart for a resumed or forked session and on the model-switch events; the status line
  gets `context_window`, hooks do not. A per-threshold context warning from a hook is therefore
  not possible today without taking over the user's status line.
- `transcript_path` is on every event. The file is written asynchronously and its entry format
  is internal and changes between versions, so the scripts never parse it. `session_guard.py`
  uses one thing only: the file's modification time, as a sign that the session is still working.

## Exit codes and feedback

- Exit 0: success. Stdout is parsed as JSON only when it is one JSON object and nothing else.
  Plain stdout becomes context for Claude only on SessionStart, UserPromptSubmit,
  UserPromptExpansion and PostModelSwitch. Stderr on exit 0 is never shown to Claude.
- Exit 2: blocking error, stderr is the reason. PreToolUse: the tool call is blocked and Claude
  sees stderr. PostToolUse: nothing is blocked (the tool already ran), but Claude sees stderr.
  SessionStart: stderr goes to the user only.
- Any other exit code: non-blocking error, the action goes ahead, unless `onFailure: "block"`.
  Exit 1 is not a block.
- `additionalContext` (in `hookSpecificOutput`) reaches Claude as a system reminder on
  SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, PostToolUseFailure and Stop. The docs
  ask for factual statements, not commands: text framed as an out-of-band instruction can trip
  Claude's prompt-injection defences. The session guard's lines state what is the case (another
  session is open, a lesson applies, the plan was copied) and leave the action to Claude.
- Exit 2 on PostToolUseFailure, like on PostToolUse, blocks nothing and shows stderr to Claude.
- JSON alternatives: PreToolUse `hookSpecificOutput.permissionDecision`
  (`allow`/`deny`/`ask`/`defer`) with `permissionDecisionReason`; PostToolUse top-level
  `decision: "block"` + `reason`, or `hookSpecificOutput.additionalContext`; SessionStart
  `hookSpecificOutput.additionalContext`. Strings are capped at 10,000 characters.
- `onFailure: "block"` (v2.1.295+): a hook that cannot start, crashes, times out or prints
  invalid JSON blocks the action. No effect on Stop, SubagentStop, TaskCompleted, TeammateIdle or
  async hooks. Without it, a mistyped script path silently lets everything through.
- Timeouts: in seconds; default 600 for command hooks, lowered to 30 on UserPromptSubmit and
  1.5 on SessionEnd. Every hook in the kit sets its own. A timed-out PreToolUse hook does not
  block unless `onFailure: "block"`.
- Hooks that match one event run in parallel, so two hooks must not depend on each other's
  output. Settings hooks also run for tool calls inside a subagent.

## Hook command format, and Windows

- Exec form: `"command": "<executable>", "args": [...]`. No shell; each element is one argument;
  `${CLAUDE_PROJECT_DIR}` is substituted as a plain string, so paths with spaces need no quoting.
  The docs recommend exec form for any hook that references a path placeholder.
- Shell form (no `args`): `sh -c` on macOS and Linux, Git Bash on Windows, PowerShell when Git Bash
  is missing. In PowerShell the bare `$CLAUDE_PROJECT_DIR` resolves to `$null`; Claude Code only
  rewrites the `${CLAUDE_PROJECT_DIR}` spelling. A shell-form command written as
  `"\"$CLAUDE_PROJECT_DIR\"/..."` would therefore break on Windows without Git Bash.
- On Windows, exec form needs a real `.exe` as `command`; `.cmd`/`.bat` shims fail.
- `CLAUDE_PROJECT_DIR` is exported to the hook process in both forms. It stays at the session's
  start directory when Claude enters a worktree; the `cwd` input field follows Claude.
- On Windows the PowerShell tool may replace Bash entirely: hooks that inspect shell commands
  should match `Bash|PowerShell`.

### Chosen format

```json
{"type": "command", "command": "uv",
 "args": ["run", "--quiet", "--script", "${CLAUDE_PROJECT_DIR}/scripts/validate.py", "--hook", "pre"],
 "onFailure": "block", "timeout": 30}
```

Why: `uv.exe` is a real executable on Windows, so exec form works with or without Git Bash;
there is no `python3` on a default Windows PATH (it is `python` or `py`), and `uv` picks a
Python >= 3.11 from the PEP 723 header itself. `--script` makes uv treat the file as an inline
script and ignore any `pyproject.toml` nearby; `--quiet` keeps uv's own messages out of stderr,
which is the block reason. Measured warm start on macOS: 40 to 90 ms.

`uv run` is not mentioned in the hooks docs; it is fine as long as uv already has a Python. On a
cold machine uv may download one on the first run, which can exceed the timeout. The setup should
therefore run `uv run --script scripts/validate.py --self-test` once during installation.

## Matchers

- Only letters, digits, `_`, `-`, spaces, `,` and `|`: an exact name or a list
  (`Edit|Write|NotebookEdit`). Anything else is an unanchored JavaScript regex (`Edit.*` also
  matches NotebookEdit).
- SessionStart matchers: `startup`, `resume`, `clear`, `compact`, `fork`.

## Shell commands and the tools around them

- On macOS, Linux and WSL the Glob and Grep tools are left out of the default tool set: Claude
  searches with `find` and `grep` through the Bash tool (embedded `bfs` and `ugrep`), and those
  searches reach hooks as `Bash` calls. An agent whose `tools` list has no `Bash` gets Glob and
  Grep back. So a hook on `Bash` sees every search of an agent that has Bash, and a pattern
  such as `grep -E "a|b"` must pass a guard that reads commands.
- Inside Claude Code's shell `find` and `grep` are shell functions for the embedded `bfs` and
  `ugrep`, and those have options the system tools lack: bfs deletes with `-rm` (next to
  `-delete`) and stops with `-exit`; ugrep runs programs with `--filter`, `--pager` and `--view`
  and writes with `--save-config`. A list of forbidden options cannot keep up with that, so
  `agent_git_readonly.py` lists the options each command may get and refuses every other one.
- The shell fills in a wildcard after a PreToolUse hook has judged the command. With a file
  named `-delete` in the folder, `find . -de*` becomes `find . -delete`. The guard therefore
  refuses a word that starts with an unquoted `*`, `?` or `[`, or starts with `-` and holds
  one; `./*` is fine, because what it expands to starts with `./`.
- Two more ways a word changes meaning after the check, both closed by one rule each. A program
  reads the word after an option that takes a value as that value, whatever it is: in
  `rg -e -- --pre=sh` the `--` is the pattern, not the end of the options, and `--pre=sh` is
  an option again. So the guard judges every word that starts with `-` as an option wherever it
  stands, also after `--` (a file with such a name is written `./-name`), and refuses an option
  that takes a value when the next word starts with `-`. And empty quotes do not hide the start
  of a word from the shell: `''?delete` still expands to `-delete`. So "starts with a wildcard"
  is judged on the first character the shell is left with. With zsh's EXTENDED_GLOB `^`, `#`
  and `~` are pattern characters too; a word that starts with `^`, or starts with `-` and holds
  one of them, is refused.
- The Bash tool runs the user's own shell, non-interactive: zsh on a default macOS. zsh runs
  what stands in `=( )` and in a glob qualifier such as `*(e:'cmd':)`, with none of the
  characters a POSIX shell needs for that. PowerShell runs what stands in plain parentheses and
  reads typographic quotes and dashes as the plain ones. `agent_git_readonly.py` therefore works
  from an allow list and refuses parentheses and braces outside quotes in every shell.
- git accepts any unambiguous abbreviation of a long option, and a repository's own
  configuration can name programs that git runs (`core.fsmonitor`, a diff driver). A guard that
  lets git read must refuse options by prefix, and must not let git be pointed at another
  repository (`-C`, `--git-dir`, `--work-tree`, `-c`).
- A network path (`\\server\share` or `//server/share`) makes Windows sign in to that machine,
  which hands it the user's password hash. The guard refuses such a path.
- A shell command can write a file without the edit tools (a redirect, a heredoc, `sed -i`,
  `Set-Content`). No hook sees that content before it is written. `validate.py --hook shell`
  scans afterwards what git reports as changed or untracked and changed in the last two minutes.
  "Changed" is the newer of the modification time and the status change time, because `cp -p`,
  `mv` and an unpacked archive keep an old modification time. It also reads the commits made
  since its previous run, from the commits themselves (`git show <commit>:<path>`, at most 20
  commits, the checked-out branch only), because the working file may be overwritten or removed
  right after the commit. It keeps the last `HEAD` in `.claude/.session/shell-scan.json`, with a
  list of files it already scanned clean; without a remembered `HEAD` it reads the newest commit
  when that is younger than two minutes. It reads the wiki's own backup repository the same
  way when `nest.json` names one, since the workspace ignores that folder. A file git ignores, or a file
  outside a git work tree, is not seen that way.
- Three things the read-only guard cannot see. A read command without a file (`cat`,
  `grep pattern`, `rg pattern` with its input left open) waits for input until the call times
  out. git runs what the repository's own configuration names (a diff driver, a file system
  monitor); that configuration is the user's own, and the guard only keeps git from being
  pointed at another repository. And the guard judges the text of the command, not what the
  user's own shell makes of it: an alias or function of their own with the name of an allowed
  command, a zsh global alias, or `setopt extendedglob` in their `.zshenv` is outside it.
- An unquoted `#` is refused wherever it stands in a word. In most shells it starts a comment;
  with zsh's EXTENDED_GLOB it makes what stands before it optional, so `a#-delete` can expand to
  a file named `-delete`. Inside quotes it is a plain character.
- Limits of the scan after a shell command, in one place: the checked-out branch only, no stash,
  at most 20 new commits, 50 files and 8 MB per run (what was left out is counted in the
  message), nothing git ignores apart from the wiki backup, nothing that changed more than two
  minutes ago.
- Limits of secret recognition: a value that is an address (`https://...`) or names a password
  manager counts as a pointer, not a secret; a password without a digit, shorter than ten
  characters or with spaces passes; a line that gives `minimaal12tekens` (Dutch for "at least 12 characters") as the value of
  `wachtwoord` has the shape of a password and is stopped, so such a value is written with
  spaces or between `<` and `>`.

## Hooks in agent and skill frontmatter

- Same format as settings, exec form and `onFailure` included. Agent hooks run only while that
  agent runs, and only after the workspace trust dialog for the folder holding the agent file
  was accepted. A `-p` session does not count as trusted: there the agent still runs, but its
  frontmatter hooks are skipped. A blind seat or the read-only reviewer called from a headless
  run (a scheduled `claude -p`) is therefore not guarded by its own hook; wire the guard in
  `.claude/settings.json` as well when that matters (both scripts leave other agents alone).
- `agent_git_readonly.py` and `blind_seat_guard.py` are meant for this. The blind seats pass
  their own name with `--seat`, so the guard does not depend on the name the session reports.
- `once: true` works only in skill frontmatter.

## Not documented, so not relied on

- Whether `session_id` stays the same after `--resume`, after `/clear` and after a compaction.
  The session guard keys its files on the id; when a resumed session gets a new one, the words
  file of the old id is no longer added to (it stays on disk for `keep_days`). After `/clear`
  the SessionStart matcher (`startup|resume|compact`) does not fire; the session registers with
  its first prompt.
- What fires when the user rejects a plan. PostToolUse is documented for a successful call
  only, so the plan hook reads the approved plan from `tool_response` and saves nothing when
  that is not an object with a `plan`.
- Whether SessionStart and UserPromptSubmit fire inside a subagent. The scripts work either way.
- Starting `claude` in a subfolder: `${CLAUDE_PROJECT_DIR}` is "the project root where the
  session started" and `.claude/settings.json` is read from the session's primary working
  directory, so the workspace hooks load only when Claude Code is started in the workspace root.
- An app that is not started from a terminal (an IDE, a git client, a note app with a git
  plugin) may run with a PATH that lacks `uv`. The pre-commit hook then stops the commit with
  one line that says so. A blocking hook (`onFailure: "block"`) stops every Edit and Write, and
  what the user sees is Claude Code's own line, per the docs of the form
  `PreToolUse:Write hook error: [uv run --quiet --script ...]: failed; blocking because onFailure is "block"`,
  followed by the error of the program that could not start (`timed out` instead of `failed`
  after a timeout). The fix is to install uv or to start Claude Code where `uv` works.

## Settings facts

- `claudeMdExcludes` is documented (memory docs): globs against absolute paths, at any settings
  layer, arrays merge across layers.
- `$schema: https://json.schemastore.org/claude-code-settings.json` gives editor validation; the
  schema can lag behind new keys.

## Frontmatter fields (for `skills_catalog.py --check`)

- Skills: `name`, `description`, `when_to_use`, `argument-hint`, `arguments`,
  `disable-model-invocation`, `user-invocable`, `allowed-tools`, `disallowed-tools`, `model`,
  `effort`, `context`, `agent`, `background`, `hooks`, `paths`, `shell`, `metadata`, `license`,
  `compatibility`. Description plus when_to_use is cut at 1,536 characters in the listing.
- Agents: `name` (required), `description` (required), `tools`, `disallowedTools`, `model`,
  `permissionMode`, `maxTurns`, `autoCompactWindow`, `skills`, `mcpServers`, `hooks`, `memory`,
  `background`, `omitClaudeMd`, `effort`, `isolation`, `color`, `initialPrompt`, `experimental`.
  `metadata` is NEST's own addition for agents; Claude Code documents it for skills only.
