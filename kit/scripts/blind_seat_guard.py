# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""PreToolUse hook for blind seats: an agent that must see only its own run file reads nothing else.

Some agents are blind on purpose: The Outsider and The Verifier on The Council and The Dreamer of
The Architects get one run file and nothing about the user. Their instructions say so; this hook
enforces it. Wire it in the agent's own frontmatter, so it runs only while that agent works:

  hooks:
    PreToolUse:
      - matcher: "Read|Grep|Glob"
        hooks:
          - type: command
            command: uv
            args: ["run", "--quiet", "--script", "${CLAUDE_PROJECT_DIR}/scripts/blind_seat_guard.py",
                   "--seat", "council-outsider"]
            onFailure: block

What passes: a Read of a file named after the seat (`outsider.md` for `council-outsider`) inside
the run folder. Everything else is refused: any other file, and every Grep or Glob. An agent type
that is not a blind seat is left alone, so the hook is also safe at settings level.

The seat is `--seat <agent-name>` when the hook is wired with one (in a seat's own frontmatter that
is the safe choice: the hook then guards that seat whatever name the session reports), else the
`agent_type` field of the hook input. Seat names are matched without regard to case; an unknown
name in `agent_type` is not a blind seat and passes; an unknown name in `--seat` is refused,
because a hook wired for a seat must not fall open on a typing mistake. Configuration (optional), in nest.json at the workspace root:
  {"blind_seats": {
      "run_dir": ".runs",                                  the run folder, relative to the root
      "seats": {"council-outsider": ["outsider.md"]}       replaces the built-in table
  }}

The workspace root is $CLAUDE_PROJECT_DIR, else the hook's cwd, else the current directory.
The hook input is read as UTF-8 bytes, whatever the console code page is.
Exit 2 blocks the call (stderr is the reason Claude sees); exit 0 leaves it to the normal flow.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

SEATS = {
    "council-outsider": ["outsider.md"],
    "council-verifier": ["verifier.md"],
    "architect-dreamer": ["dreamer.md"],
}
RUN_DIR = ".runs"


def workspace_root(hook_cwd: str | None) -> Path:
    for candidate in (os.environ.get("CLAUDE_PROJECT_DIR"), hook_cwd):
        if candidate and Path(candidate).is_dir():
            return Path(candidate)
    return Path.cwd()


def load_config(root: Path) -> tuple[str, dict[str, list[str]]]:
    try:
        data = json.loads((root / "nest.json").read_text(encoding="utf-8-sig"))
        conf = data.get("blind_seats") if isinstance(data, dict) else None
    except (OSError, ValueError):
        conf = None
    if not isinstance(conf, dict):
        return RUN_DIR, SEATS
    run_dir = conf.get("run_dir") if isinstance(conf.get("run_dir"), str) and conf.get("run_dir") else RUN_DIR
    seats = conf.get("seats")
    if isinstance(seats, dict) and seats:
        table = {str(k): [str(n) for n in v] if isinstance(v, list) else [str(v)] for k, v in seats.items()}
        return run_dir, table
    return run_dir, SEATS


def inside(path: Path, folder: Path) -> bool:
    try:
        path.resolve().relative_to(folder.resolve())
        return True
    except (OSError, ValueError):
        return False


def check(data: dict, seat_arg: str | None = None) -> str | None:
    """Why the call is refused, or None when it may run."""
    root = workspace_root(data.get("cwd") if isinstance(data.get("cwd"), str) else None)
    run_dir, table = load_config(root)
    seats = {name.lower(): files for name, files in table.items()}
    # --seat comes from the agent's own frontmatter, so it wins: a hook wired into a seat's file
    # guards that seat whatever name the session reports.
    agent_type = data.get("agent_type")
    seat = str(seat_arg or (agent_type if isinstance(agent_type, str) else "") or "").strip().lower()
    if seat not in seats:
        if seat_arg:
            # Wired for a seat the table does not know: a typing mistake must not open the door.
            return (f"{seat_arg} is not a blind seat this guard knows (known: {', '.join(sorted(seats))}); "
                    "add it under blind_seats in nest.json or correct --seat")
        return None
    names = {n.lower() for n in seats[seat]}
    tool = str(data.get("tool_name") or "")
    tool_input = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
    if tool != "Read":
        return f"{seat} reads its own run file and nothing else: {tool or 'this tool'} is not available to it"
    raw = str(tool_input.get("file_path") or "").replace("\\", "/")
    if not raw:
        return f"{seat} reads its own run file and nothing else: the call names no file"
    path = Path(raw)
    if not path.is_absolute():
        path = root / path
    # The name is tested twice: as asked for, and as the file it leads to. A link named after the
    # seat's own file that points at another seat's report is not the seat's own file.
    try:
        real_name = path.resolve().name.lower()
    except (OSError, ValueError):
        real_name = ""
    if path.name.lower() in names and real_name in names and inside(path, root / run_dir):
        return None
    return (f"{seat} reads its own run file and nothing else: {path.name} is not it. "
            f"Its run file is {' or '.join(sorted(seats[seat]))} inside {run_dir}/")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="PreToolUse guard that keeps a blind seat inside its run file.")
    ap.add_argument("--seat", help="Agent name, used when the hook input has no agent_type")
    args = ap.parse_args(argv)
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
        data = json.loads(raw) if raw.strip() else {}
    except (ValueError, OSError):
        print("blind_seat_guard: the hook input is not valid JSON", file=sys.stderr)
        return 2
    if not isinstance(data, dict):
        return 0
    reason = check(data, args.seat)
    if reason:
        print(reason, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
