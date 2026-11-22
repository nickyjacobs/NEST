# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""SessionStart hook: one line of workspace facts for Claude.

Claude Code adds a SessionStart hook's plain-text stdout to Claude's context, so this prints
exactly one line, for example:

  Workspace: wiki inbox 4 notes (1 question), wiki backup 3 unpushed changes, first open item in docs/next-session.md: Fix the login redirect

What it reads, all optional:
  wiki.config.json   found like wiki.py finds it: $NEST_WIKI_CONFIG, else the first
                     wiki.config.json from the workspace root upwards. `wiki_dir` is relative
                     to the config file's folder. The inbox is the first section with
                     "raw": true (fallback: "_inbox"). A note counts as an open question when
                     its frontmatter `status` (as `wiki.py stats` counts) or `kind` is "question".
  nest.json          at the workspace root: {"wiki_backup": {"git_dir": "~/.<name>-wiki.git"}}.
                     When set, the line reports uncommitted files plus commits not yet pushed.
  docs/next-session.md   the first unchecked "- [ ]" item.
  the always-loaded files   CLAUDE.md, CLAUDE.local.md and the rules without a `paths`
                     frontmatter load in every session. Above the ceiling the line says so:
                     nest.json {"size_ceiling": {"lines": 400}} (default 400, 0 turns it off).
  nest_update.py     next to this script: when the workspace has a NEST stamp and a newer release
                     exists, the line says so (looked up online at most once a week; switch it
                     off with nest.json {"nest": {"update_check": false}}).
  morning nudge      nest.json {"morning_nudge": {"before": "11:00", "text": "say good morning
                     for your briefing"}}: on a new session before that hour, when the
                     morning-briefing skill is installed, the line ends with the text.

When nest.json is there but is not valid JSON, the line says so, because every setting above is
then off. A byte order mark at its start is read past.

The workspace root is $CLAUDE_PROJECT_DIR, else the hook's cwd, else the current directory.
The hook input is read as UTF-8 bytes, whatever the console code page is.
It never fails the session: every error is swallowed, git calls are time-boxed, exit code is 0.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

GIT_TIMEOUT = 2.0
SIZE_CEILING = 400
ALWAYS_LOADED = ("CLAUDE.md", "CLAUDE.local.md", ".claude/CLAUDE.md")
BRIEFING_SKILL = Path(".claude/skills/morning-briefing/SKILL.md")
NEXT_FILE = Path("docs/next-session.md")
ITEM_CHARS = 120
OPEN_ITEM = re.compile(r"^\s*[-*] \[ \] (.+)$")


def workspace_root(hook_cwd: str | None) -> Path:
    for candidate in (os.environ.get("CLAUDE_PROJECT_DIR"), hook_cwd):
        if candidate and Path(candidate).is_dir():
            return Path(candidate)
    return Path.cwd()


def read_json(path: Path) -> dict:
    """The file's JSON object, or {}. A byte order mark (Windows editors add one) is read past."""
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


BROKEN_PREFIX = "nest.json cannot be read"


def broken_part(root: Path) -> str | None:
    """A plain part for the line when nest.json is there but is not a JSON object: without it the
    settings in that file (the backup, the ceiling, the update check, the nudge) go quiet unseen."""
    path = root / "nest.json"
    try:
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except OSError:
        return None
    except ValueError:
        return f"{BROKEN_PREFIX} (not valid JSON), so its settings are off"
    return None if isinstance(data, dict) else f"{BROKEN_PREFIX} (not a JSON object), so its settings are off"


def find_config(root: Path) -> Path | None:
    """$NEST_WIKI_CONFIG, else the first wiki.config.json from the root upwards (as wiki.py)."""
    env = os.environ.get("NEST_WIKI_CONFIG")
    if env:
        p = Path(env).expanduser()
        return p if p.is_file() else None
    here = root.resolve()
    for d in (here, *here.parents):
        if (d / "wiki.config.json").is_file():
            return d / "wiki.config.json"
    return None


def inbox_section(config: dict) -> str:
    sections = config.get("sections")
    if isinstance(sections, dict):
        for name, props in sections.items():
            if isinstance(props, dict) and props.get("raw") is True:
                return str(name)
    return "_inbox"


def frontmatter_values(text: str, keys: tuple[str, ...]) -> set[str]:
    text = text.lstrip("\ufeff")
    if not text.startswith("---"):
        return set()
    end = text.find("\n---", 3)
    block = text[3:end] if end != -1 else ""
    found = set()
    for key in keys:
        m = re.search(rf"^{re.escape(key)}:\s*['\"]?([^'\"\n#]+)", block, re.MULTILINE)
        if m:
            found.add(m.group(1).strip().lower())
    return found


def inbox_counts(wiki: Path, section: str, words: set[str] | None = None) -> tuple[int, int] | None:
    """Notes in the inbox, and how many are questions (status or kind is one of `words`)."""
    words = {w.lower() for w in (words or {"question"})}
    folder = wiki / section
    if not folder.is_dir():
        return None
    notes = questions = 0
    for note in folder.glob("*.md"):
        if note.name.lower() in ("index.md", "readme.md") or note.name.startswith("."):
            continue
        notes += 1
        try:
            head = note.read_text(encoding="utf-8", errors="replace")[:4000]
        except OSError:
            continue
        if words & frontmatter_values(head, ("status", "kind")):
            questions += 1
    return notes, questions


def git(git_dir: Path, work_tree: Path, *args: str) -> str | None:
    try:
        out = subprocess.run(["git", f"--git-dir={git_dir}", f"--work-tree={work_tree}", *args],
                             capture_output=True, text=True, timeout=GIT_TIMEOUT, check=False, encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout if out.returncode == 0 else None


def backup_pending(root: Path, wiki: Path) -> int | None:
    git_dir_raw = (read_json(root / "nest.json").get("wiki_backup") or {}).get("git_dir")
    if not git_dir_raw:
        return None
    git_dir = Path(os.path.expanduser(str(git_dir_raw)))
    if not git_dir.is_dir():
        return None
    status = git(git_dir, wiki, "status", "--porcelain")
    if status is None:
        return None
    pending = len([line for line in status.splitlines() if line.strip()])
    ahead = git(git_dir, wiki, "rev-list", "--count", "@{u}..HEAD")
    if ahead and ahead.strip().isdigit():
        pending += int(ahead.strip())
    return pending


def first_open_item(root: Path) -> str | None:
    try:
        lines = (root / NEXT_FILE).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    for line in lines:
        m = OPEN_ITEM.match(line)
        if m:
            item = m.group(1).strip()
            return item if len(item) <= ITEM_CHARS else item[: ITEM_CHARS - 3].rstrip() + "..."
    return "none"


def line_count(path: Path) -> int:
    try:
        return len(path.read_text(encoding="utf-8", errors="replace").splitlines())
    except OSError:
        return 0


def always_loaded(root: Path) -> list[tuple[str, int]]:
    """The files that load in every session, with their line counts, biggest first."""
    found = [(name, line_count(root / name)) for name in ALWAYS_LOADED if (root / name).is_file()]
    rules = root / ".claude" / "rules"
    if rules.is_dir():
        for rule in sorted(rules.rglob("*.md")):
            try:
                head = rule.read_text(encoding="utf-8", errors="replace")[:2000]
            except OSError:
                continue
            front = head[3:head.find("\n---", 3)] if head.startswith("---") and head.find("\n---", 3) != -1 else ""
            if not re.search(r"^paths:", front, re.MULTILINE):
                found.append((rule.relative_to(root).as_posix(), line_count(rule)))
    return sorted(found, key=lambda item: item[1], reverse=True)


def size_part(root: Path) -> str | None:
    conf = read_json(root / "nest.json").get("size_ceiling")
    ceiling = conf.get("lines") if isinstance(conf, dict) else None
    ceiling = SIZE_CEILING if not isinstance(ceiling, (int, float)) or isinstance(ceiling, bool) else int(ceiling)
    if ceiling <= 0:
        return None
    files = always_loaded(root)
    total = sum(lines for _, lines in files)
    if total <= ceiling:
        return None
    name, lines = files[0]
    return f"always-loaded files {total} lines (ceiling {ceiling}, largest {name} with {lines})"


def update_part(root: Path) -> str | None:
    """The line of nest_update.py when a newer NEST release exists; silent on any problem."""
    try:
        if not isinstance(read_json(root / "nest.json").get("nest"), dict) and not broken_part(root):
            return None  # no stamp: nothing to update. A broken file is the updater's to judge too.
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import nest_update
        return nest_update.notice(root, timeout=GIT_TIMEOUT) or None
    except Exception:
        return None


def nudge_part(root: Path, source: str | None, now: datetime | None = None) -> str | None:
    conf = read_json(root / "nest.json").get("morning_nudge")
    if not isinstance(conf, dict) or source not in (None, "startup") or not (root / BRIEFING_SKILL).is_file():
        return None
    m = re.match(r"^(\d{1,2})(?::(\d{2}))?$", str(conf.get("before") or "").strip())
    if not m:
        return None
    now = now or datetime.now()
    if (now.hour, now.minute) >= (int(m.group(1)), int(m.group(2) or 0)):
        return None
    return str(conf.get("text") or "say good morning for your briefing").strip() or None


def build_line(root: Path, source: str | None = None) -> str:
    parts: list[str] = []
    config_path = find_config(root)
    config = read_json(config_path) if config_path else {}
    wiki = (config_path.parent if config_path else root) / str(config.get("wiki_dir") or "wiki")
    if wiki.is_dir():
        roles = config.get("status_roles") if isinstance(config.get("status_roles"), dict) else {}
        words = {str(roles.get("question") or "question"), str(config.get("question_kind") or "question")}
        counts = inbox_counts(wiki, inbox_section(config), words)
        if counts is not None:
            notes, questions = counts
            q = f" ({questions} question{'s' if questions != 1 else ''})" if questions else ""
            parts.append(f"wiki inbox {notes} note{'s' if notes != 1 else ''}{q}")
        pending = backup_pending(root, wiki)
        if pending is not None:
            parts.append(f"wiki backup {pending} unpushed change{'s' if pending != 1 else ''}")
    item = first_open_item(root)
    if item is not None:
        parts.append(f"first open item in {NEXT_FILE.as_posix()}: {item}")
    broken = broken_part(root)
    for extra in (broken, size_part(root), update_part(root), nudge_part(root, source)):
        # nest_update.notice may report the broken file itself: say it once.
        if extra and not (broken and extra is not broken and extra.startswith(BROKEN_PREFIX)):
            parts.append(extra)
    return "Workspace: " + ", ".join(parts) if parts else ""


def read_stdin(seconds: float = 3.0) -> str:
    """The hook input, decoded as UTF-8 whatever the console code page is (on Windows a text read
    would use the code page and garble or lose a message with an accent or a curly quote).
    Claude Code writes it at once; a run by hand with stdin left open must not hang, so the read
    gives up after a moment."""
    if sys.stdin is None or sys.stdin.isatty():
        return ""
    box: list[str] = []

    def read() -> None:
        try:
            # Straight from the file descriptor: a read through sys.stdin.buffer would hold its
            # lock in this thread and abort the interpreter when the wait below gives up.
            try:
                fd = sys.stdin.fileno()
            except (OSError, ValueError, AttributeError):
                raw = sys.stdin.buffer.read()  # a stand-in stream without a descriptor cannot hang
            else:
                chunks: list[bytes] = []
                while chunk := os.read(fd, 65536):
                    chunks.append(chunk)
                raw = b"".join(chunks)
            box.append(raw.decode("utf-8", errors="replace"))
        except Exception:
            pass

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    reader.join(seconds)
    return box[0] if box else ""


def main() -> int:
    try:
        raw = read_stdin()
        data = json.loads(raw) if raw.strip() else {}
        hook_cwd = data.get("cwd") if isinstance(data, dict) else None
        source = data.get("source") if isinstance(data, dict) and isinstance(data.get("source"), str) else None
    except Exception:
        hook_cwd = source = None
    try:
        line = build_line(workspace_root(hook_cwd), source)
        if line:
            sys.stdout.buffer.write((line + "\n").encode("utf-8"))
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
