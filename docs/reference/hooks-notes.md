<sub>[Docs](../README.md) · [What to expect](../guide/what-to-expect.md) · [Updating](../guide/updating.md) · [FAQ](../guide/faq.md) · [nest.json](../reference/nest-json.md) · [Hooks](../reference/hooks-notes.md) · [Releasing](../project/releasing.md) · [Backlog](../project/backlog.md)</sub>

# Claude Code hooks: notes for NEST

Source: https://code.claude.com/docs/en/hooks (fetched as Markdown via `/docs/en/hooks.md` on
2026-11-21, twice), plus `/docs/en/skills.md`, `/docs/en/sub-agents.md`, `/docs/en/memory.md`,
`/docs/en/settings.md` and `/docs/en/tools-reference.md` the same day. Re-check these facts when
Claude Code changes; the scripts in `kit/scripts/` depend on them.

**On this page:** [Input on stdin (JSON)](#input-on-stdin-json) · [Exit codes and feedback](#exit-codes-and-feedback) · [Hook command format, and Windows](#hook-command-format-and-windows) · [Matchers](#matchers) · [Hooks in agent and skill frontmatter](#hooks-in-agent-and-skill-frontmatter) · [Settings facts](#settings-facts) · [Frontmatter fields (for `skills_catalog.py --check`)](#frontmatter-fields-for-skills_catalogpy---check)

## Input on stdin (JSON)

- Common: `session_id`, `transcript_path`, `cwd`, `hook_event_name`, `permission_mode` (not on
  every event), `agent_id` / `agent_type` inside a subagent, `prompt_id`, `effort`.
- PreToolUse / PostToolUse: `tool_name`, `tool_input`, `tool_use_id`; PostToolUse adds
  `tool_response` and `duration_ms`.
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
  `tool_response.plan` holds the approved plan. `session_guard.py --event plan` uses that.
- No hook input carries the context window's fill level. `context_tokens` exists only on
  SessionStart for a resumed or forked session and on the model-switch events; the status line
  gets `context_window`, hooks do not. A per-threshold context warning from a hook is therefore
  not possible today without taking over the user's status line.
- `transcript_path` is written asynchronously and its format is not documented, so the scripts
  never parse it.

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
  SessionStart, UserPromptSubmit, PreToolUse, PostToolUse and Stop. The docs ask for factual
  statements, not commands: text framed as an out-of-band instruction can trip Claude's
  prompt-injection defences. The session guard's lines are written that way.
- JSON alternatives: PreToolUse `hookSpecificOutput.permissionDecision`
  (`allow`/`deny`/`ask`/`defer`) with `permissionDecisionReason`; PostToolUse top-level
  `decision: "block"` + `reason`, or `hookSpecificOutput.additionalContext`; SessionStart
  `hookSpecificOutput.additionalContext`. Strings are capped at 10,000 characters.
- `onFailure: "block"` (v2.1.295+): a hook that cannot start, crashes, times out or prints
  invalid JSON blocks the action. No effect on Stop, SubagentStop, TaskCompleted, TeammateIdle or
  async hooks. Without it, a mistyped script path silently lets everything through.
- Timeouts: default 600 s for command hooks. A timed-out PreToolUse hook does not block unless
  `onFailure: "block"`.

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

## Hooks in agent and skill frontmatter

- Same format as settings. Agent hooks run only while that agent runs, and only after the
  workspace trust dialog for the folder holding the agent file was accepted (a `-p` session does
  not count as trusted). `agent_git_readonly.py` is meant for this.
- `once: true` works only in skill frontmatter.

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
