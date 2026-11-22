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

**0.2 What machine.** Detect the OS and version (macOS `sw_vers`, Windows `ver`, Linux
`/etc/os-release` for the distribution, not only the kernel). Then check, one line each with ✓ or ✗:

| Tool | Why | Check |
|---|---|---|
| Claude Code | runs everything; v2.1.295 or later is needed (blocking hooks use `onFailure`; the agent teams use `omitClaudeMd`, v2.1.271+) | `claude --version` |
| git | versioning, backups | `git --version` |
| uv | runs the Python scripts on every OS, installs Python itself | `uv --version` |
| Obsidian | opens the wiki | macOS: `/Applications/Obsidian.app`; Windows: Start menu or `%LOCALAPPDATA%\Programs\Obsidian`; Linux: `which obsidian`, flatpak or AppImage; else ask |
| GitHub CLI (optional) | GitHub setup in block E | `gh --version`, `gh auth status` |

For every ✗: look up the current install command for this OS on the tool's own site (fetch the
page; do not rely on memory) and give the user that command. Install only after a yes. A command
that needs the user's own login or admin rights: suggest they run it themselves by typing
`! <command>` in the prompt. After an install, run the tool's check again. A tool that was just
installed is often not found yet, because this session started before it existed: then ask the
user to close Claude Code, open a new terminal, start Claude Code again in this folder and type
the trigger line (a stop point).

**0.3 Fetch the docs.** Save these Claude Code docs pages to `_setup/docs/` with `curl -sL`
(`curl.exe -sL` on Windows; append `.md` to the URL if the page comes back as HTML), not with a
summarising tool, so the exact field names survive:

- `https://code.claude.com/docs/en/memory` (CLAUDE.md, imports, rules)
- `https://code.claude.com/docs/en/skills`
- `https://code.claude.com/docs/en/sub-agents`
- `https://code.claude.com/docs/en/hooks`
- `https://code.claude.com/docs/en/settings` (permissions, `claudeMdExcludes`)
- `https://code.claude.com/docs/en/mcp`

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

**0.5 The user's level.** One closed question: how comfortable are you with the terminal, git and
Obsidian? (new to all / used some / daily). Store it as `level` in STATE.md.

**0.6 Tell the plan.** The session plan from section 3, in two or three lines. Then block A:
read `setup/interview.md` now, and set `read:` in STATE.md to it.
