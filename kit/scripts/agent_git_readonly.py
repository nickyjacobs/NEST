# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""PreToolUse hook for read-only agents: only git read commands and plain read commands pass.

Wire it in the agent's own frontmatter, so it runs only while that agent works:

  hooks:
    PreToolUse:
      - matcher: "Bash|PowerShell"
        hooks:
          - type: command
            command: uv
            args: ["run", "--quiet", "--script", "${CLAUDE_PROJECT_DIR}/scripts/agent_git_readonly.py"]
            onFailure: block

Allowed, one command per call:
  git status | diff | ls-files, git show with --stat, git log with --oneline, optionally after
      --no-pager, -C <dir>, --git-dir <dir> or --work-tree <dir>
  ls, pwd, cat, head, tail, wc, grep, rg, find, file, stat, du, tree, sort, and the PowerShell
      Get-ChildItem, Get-Content, Select-String, Get-Location

Refused: anything else, and any command with a redirect (< >), command substitution ($( ),
backticks), a variable ($), chaining (; && || |), a background &, or a line break. Also refused
are the flags that make a read command write or execute: git -c / --output / -o / --ext-diff,
find -exec / -delete / -fprint, rg --pre, sort -o, tree -o, tail -f.

This guards against writing and running things; which files an agent may read is the permission
system's job. Exit 2 blocks the call (stderr is the reason Claude sees); exit 0 leaves the call to
the normal permission flow.
"""

from __future__ import annotations

import json
import shlex
import sys

FORBIDDEN_CHARS = {";": "chaining (;)", "|": "a pipe or || chaining", "&": "&& chaining or a background &",
                   "<": "a redirect", ">": "a redirect", "`": "backticks", "$": "a variable or $( ) substitution",
                   "\n": "a line break", "\r": "a line break"}

GIT_READS = {"status", "diff", "ls-files", "show", "log"}
GIT_REQUIRED = {"show": "--stat", "log": "--oneline"}
GIT_GLOBAL_WITH_VALUE = {"-C", "--git-dir", "--work-tree"}
GIT_GLOBAL_FLAGS = {"--no-pager"}
GIT_BAD_FLAGS = ("--output", "-o", "--ext-diff", "--textconv", "--open-files-in-pager", "--exec")

READ_COMMANDS = {"ls", "pwd", "cat", "head", "tail", "wc", "grep", "rg", "find", "file", "stat", "du", "tree", "sort",
                 "get-childitem", "get-content", "select-string", "get-location", "gci", "dir"}
BAD_FLAGS = {
    "find": ("-exec", "-execdir", "-ok", "-okdir", "-delete", "-fprint", "-fprint0", "-fprintf", "-fls"),
    "rg": ("--pre", "--pre-glob"),
    "sort": ("-o", "--output"),
    "tree": ("-o",),
    "tail": ("-f", "-F", "--follow"),
    "get-content": ("-wait",),
}


def check(command: str) -> str | None:
    """Why the command is refused, or None when it may run."""
    cmd = command.strip()
    if not cmd:
        return None
    for ch, what in FORBIDDEN_CHARS.items():
        if ch in cmd:
            return f"{what} is not allowed for a read-only agent"
    try:
        tokens = shlex.split(cmd, posix=True)
    except ValueError:
        return "the command could not be parsed (unbalanced quotes)"
    if not tokens:
        return None
    name = tokens[0].lower()
    if name == "git":
        return check_git(tokens[1:])
    if name in READ_COMMANDS:
        for tok in tokens[1:]:
            low = tok.lower()
            for bad in BAD_FLAGS.get(name, ()):
                if low == bad or low.startswith(bad + "="):
                    return f"{name} {bad} can write or run something"
        return None
    return f"only git read commands and plain read commands are allowed, not {tokens[0]}"


def check_git(args: list[str]) -> str | None:
    i = 0
    while i < len(args):
        tok = args[i]
        key = tok.split("=", 1)[0]
        if tok in GIT_GLOBAL_FLAGS:
            i += 1
        elif key in GIT_GLOBAL_WITH_VALUE:
            i += 1 if "=" in tok else 2
        elif tok.startswith("-"):
            return f"git option {tok} before the subcommand is not allowed (only --no-pager, -C, --git-dir, --work-tree)"
        else:
            break
    if i >= len(args):
        return "a bare git call is not a read command"
    sub, rest = args[i], args[i + 1:]
    if sub not in GIT_READS:
        return f"git {sub} is not a read command here (allowed: status, diff, ls-files, show --stat, log --oneline)"
    need = GIT_REQUIRED.get(sub)
    if need and need not in rest:
        return f"git {sub} is only allowed with {need}"
    for tok in rest:
        if tok == "--":
            break
        for bad in GIT_BAD_FLAGS:
            if tok == bad or tok.startswith(bad + "=") or (bad == "-o" and tok.startswith("-o") and not tok.startswith("--")):
                return f"git {sub} {tok} can write or run something"
    return None


def main() -> int:
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8", errors="replace") or "{}")
    except ValueError:
        print("read-only guard: the hook input was not JSON, so the call is refused", file=sys.stderr)
        return 2
    if not isinstance(data, dict) or data.get("tool_name") not in ("Bash", "PowerShell"):
        return 0
    command = str((data.get("tool_input") or {}).get("command") or "")
    reason = check(command)
    if reason:
        print(f"Read-only agent: {reason}. Refused: {command[:200]}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
