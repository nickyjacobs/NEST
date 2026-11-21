# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Session hooks that keep a workspace safe across a long conversation.

One script, one job per `--event`. Wire only the ones the user wants (see
`kit/claude/settings.reference.json`):

  start       SessionStart. Registers the session. When another session was active in this
              workspace a moment ago, prints one line so Claude knows two sessions may write the
              same files. After a compaction it names the file with the user's own words.
  prompt      UserPromptSubmit. Appends the user's message, word for word, to a file for this
              session, and repeats the second-session line once when another session turns up.
  precompact  PreCompact. Prints the user's messages as instructions for the compaction summary,
              so their own wording survives it.
  end         SessionEnd. Removes the session's registration.
  lesson      PreToolUse. Shows a recorded lesson at the moment it applies, once per session.
  plan        PostToolUse on ExitPlanMode. Copies the approved plan into the wiki inbox.

Files, all under `.claude/.session/` (gitignored, local to this machine):
  <session>.json       when the session started and was last seen, what it was already told
  <session>.words.md   the user's messages of that session
Both are removed after `keep_days`.

Lessons live in `.claude/lessons.json`, a list the assistant keeps when something went wrong:
  [{"id": "no-force-push", "on": "command", "match": "git push .*--force",
    "lesson": "A force push once removed a colleague's commits here. Ask first."}]
`on` is "command" (Bash and PowerShell) or "file" (the path of an edit or write, relative to
the workspace, with / as separator); `match` is a case-insensitive regex.

Configuration (optional), in nest.json at the workspace root:
  {"session_guard": {
      "live_minutes": 30,    how long after its last activity a session still counts as active
      "keep_days": 14,       how long the session files stay
      "words_chars": 8000,   how much of the user's words goes into the compaction instructions
      "plan_author": "claude"   author value for a plan note; "" leaves the field out
  }}

The workspace root is $CLAUDE_PROJECT_DIR, else the hook's cwd, else the current directory.
It never fails a session: every error is swallowed and the exit code is always 0.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import time
import unicodedata
from datetime import datetime
from pathlib import Path

STATE_DIR = Path(".claude/.session")
LESSONS_FILE = Path(".claude/lessons.json")
DEFAULTS = {"live_minutes": 30, "keep_days": 14, "words_chars": 8000, "plan_author": "claude"}
PROMPT_CHARS = 4000
SAFE_ID = re.compile(r"[^A-Za-z0-9_-]")


def workspace_root(hook_cwd: str | None) -> Path:
    for candidate in (os.environ.get("CLAUDE_PROJECT_DIR"), hook_cwd):
        if candidate and Path(candidate).is_dir():
            return Path(candidate)
    return Path.cwd()


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def config(root: Path) -> dict:
    data = read_json(root / "nest.json")
    conf = data.get("session_guard") if isinstance(data, dict) else None
    merged = dict(DEFAULTS)
    if isinstance(conf, dict):
        for key, default in DEFAULTS.items():
            value = conf.get(key)
            if isinstance(default, int) and isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
                merged[key] = value
            elif isinstance(default, str) and isinstance(value, str):
                merged[key] = value
    return merged


def session_id(data: dict) -> str:
    return SAFE_ID.sub("", str(data.get("session_id") or ""))[:80] or "unknown"


def state_path(root: Path, sid: str) -> Path:
    return root / STATE_DIR / f"{sid}.json"


def words_path(root: Path, sid: str) -> Path:
    return root / STATE_DIR / f"{sid}.words.md"


def load_state(root: Path, sid: str) -> dict:
    data = read_json(state_path(root, sid))
    return data if isinstance(data, dict) else {}


def save_state(root: Path, sid: str, state: dict) -> None:
    path = state_path(root, sid)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state), encoding="utf-8")
    tmp.replace(path)


def touch(root: Path, sid: str, now: float) -> dict:
    state = load_state(root, sid)
    state.setdefault("started", now)
    state["seen"] = now
    save_state(root, sid, state)
    return state


def cleanup(root: Path, keep_days: float, now: float) -> None:
    folder = root / STATE_DIR
    if not folder.is_dir():
        return
    for path in folder.iterdir():
        try:
            if path.is_file() and now - path.stat().st_mtime > keep_days * 86400:
                path.unlink()
        except OSError:
            pass


def other_sessions(root: Path, sid: str, live_minutes: float, now: float) -> list[tuple[str, float]]:
    """Other sessions seen within `live_minutes`: (id, minutes since their last activity)."""
    folder = root / STATE_DIR
    found = []
    if folder.is_dir():
        for path in sorted(folder.glob("*.json")):
            if path.stem == sid:
                continue
            data = read_json(path)
            seen = data.get("seen") if isinstance(data, dict) else None
            if isinstance(seen, (int, float)) and 0 <= now - seen <= live_minutes * 60:
                found.append((path.stem, (now - seen) / 60))
    return found


def second_session_line(root: Path, sid: str, conf: dict, now: float) -> str:
    """One line about sessions this one was not told about yet; marks them as told."""
    state = load_state(root, sid)
    told = set(state.get("told") or [])
    fresh = [(other, minutes) for other, minutes in other_sessions(root, sid, conf["live_minutes"], now)
             if other not in told]
    if not fresh:
        return ""
    state["told"] = sorted(told | {other for other, _ in fresh})
    save_state(root, sid, state)
    minutes = min(m for _, m in fresh)
    ago = "less than a minute ago" if minutes < 1 else f"{int(minutes)} minute{'s' if int(minutes) != 1 else ''} ago"
    return ("Another Claude Code session is open in this workspace (last active " + ago + "). "
            "Two sessions that write the same files can overwrite each other's work: tell the user once, "
            "and check which session should edit before writing.")


def user_words(root: Path, sid: str, limit: int) -> str:
    try:
        text = words_path(root, sid).read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""
    if len(text) <= limit:
        return text
    tail = text[-limit:]
    cut = tail.find("\n## ")
    return "(earlier messages left out)\n" + (tail[cut + 1:] if cut != -1 else tail)


# --- events ------------------------------------------------------------------------------------

def on_start(root: Path, data: dict, conf: dict, now: float) -> str:
    sid = session_id(data)
    cleanup(root, conf["keep_days"], now)
    touch(root, sid, now)
    lines = []
    line = second_session_line(root, sid, conf, now)
    if line:
        lines.append(line)
    if data.get("source") == "compact" and words_path(root, sid).is_file():
        lines.append("The user's own messages from before the compaction are kept word for word in "
                     + words_path(root, sid).relative_to(root).as_posix() + ".")
    return "\n".join(lines)


def on_prompt(root: Path, data: dict, conf: dict, now: float) -> str:
    sid = session_id(data)
    touch(root, sid, now)
    prompt = str(data.get("prompt") or "").strip()
    if prompt:
        if len(prompt) > PROMPT_CHARS:
            prompt = prompt[:PROMPT_CHARS].rstrip() + "\n(message cut here)"
        path = words_path(root, sid)
        path.parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.fromtimestamp(now).strftime("%Y-%m-%d %H:%M")
        with path.open("a", encoding="utf-8") as fh:
            fh.write(f"## {stamp}\n\n{prompt}\n\n")
    return second_session_line(root, sid, conf, now)


def on_precompact(root: Path, data: dict, conf: dict, now: float) -> str:
    words = user_words(root, session_id(data), int(conf["words_chars"]))
    if not words:
        return ""
    return ("Keep the user's own messages in the summary word for word where they state a goal, a decision, "
            "a preference or a correction. These are their messages in this session, oldest first:\n\n" + words)


def on_end(root: Path, data: dict, conf: dict, now: float) -> str:
    try:
        state_path(root, session_id(data)).unlink()
    except OSError:
        pass
    return ""


def load_lessons(root: Path) -> list[dict]:
    data = read_json(root / LESSONS_FILE)
    if isinstance(data, dict):
        data = data.get("lessons")
    lessons = []
    for i, item in enumerate(data if isinstance(data, list) else []):
        if not isinstance(item, dict) or not item.get("match") or not item.get("lesson"):
            continue
        try:
            pattern = re.compile(str(item["match"]), re.IGNORECASE)
        except re.error:
            continue
        on = str(item.get("on") or "command").lower()
        lessons.append({"id": str(item.get("id") or f"lesson-{i + 1}"), "on": on if on in ("command", "file") else "command",
                        "pattern": pattern, "lesson": str(item["lesson"]).strip()})
    return lessons


def lesson_subject(root: Path, data: dict) -> tuple[str, str]:
    """What the tool call is about: ("command", text) or ("file", workspace-relative path)."""
    tool_input = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
    if data.get("tool_name") in ("Bash", "PowerShell"):
        return "command", str(tool_input.get("command") or "")
    raw = str(tool_input.get("file_path") or tool_input.get("notebook_path") or "").replace("\\", "/")
    if not raw:
        return "", ""
    base = root.resolve().as_posix().rstrip("/") + "/"
    for prefix in (base, root.as_posix().rstrip("/") + "/"):
        if raw.lower().startswith(prefix.lower()):
            return "file", raw[len(prefix):]
    return "file", raw


def on_lesson(root: Path, data: dict, conf: dict, now: float) -> str:
    kind, subject = lesson_subject(root, data)
    if not subject:
        return ""
    lessons = [item for item in load_lessons(root) if item["on"] == kind and item["pattern"].search(subject)]
    if not lessons:
        return ""
    sid = session_id(data)
    state = load_state(root, sid)
    shown = set(state.get("lessons") or [])
    fresh = [item for item in lessons if item["id"] not in shown]
    if not fresh:
        return ""
    state.setdefault("started", now)
    state["seen"] = now
    state["lessons"] = sorted(shown | {item["id"] for item in fresh})
    save_state(root, sid, state)
    text = "A lesson recorded in this workspace applies to this step: " + " ".join(item["lesson"] for item in fresh)
    return json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": text}})


def find_wiki(root: Path) -> tuple[Path, dict] | None:
    """The wiki folder and its config, found as wiki.py finds it."""
    config_path = None
    env = os.environ.get("NEST_WIKI_CONFIG")
    if env:
        candidate = Path(env).expanduser()
        config_path = candidate if candidate.is_file() else None
    else:
        here = root.resolve()
        for folder in (here, *here.parents):
            if (folder / "wiki.config.json").is_file():
                config_path = folder / "wiki.config.json"
                break
    conf = read_json(config_path) if config_path else None
    conf = conf if isinstance(conf, dict) else {}
    wiki = (config_path.parent if config_path else root) / str(conf.get("wiki_dir") or "wiki")
    return (wiki, conf) if wiki.is_dir() else None


def inbox_section(conf: dict) -> str:
    sections = conf.get("sections")
    if isinstance(sections, dict):
        for name, props in sections.items():
            if isinstance(props, dict) and props.get("raw") is True:
                return str(name)
    return "_inbox"


def slugify(text: str, limit: int = 50) -> str:
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", plain).strip("-")
    return slug[:limit].rstrip("-") or "plan"


def plan_title(plan: str) -> str:
    for line in plan.splitlines():
        m = re.match(r"^#{1,3}\s+(.+?)\s*#*$", line)
        if m:
            return m.group(1).strip()
    for line in plan.splitlines():
        if line.strip():
            return line.strip()[:80]
    return "Plan"


def on_plan(root: Path, data: dict, conf: dict, now: float) -> str:
    if data.get("tool_name") != "ExitPlanMode":
        return ""
    response = data.get("tool_response") if isinstance(data.get("tool_response"), dict) else {}
    tool_input = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
    plan = str(response.get("plan") or tool_input.get("plan") or "").strip()
    found = find_wiki(root)
    if not plan or not found:
        return ""
    wiki, wiki_conf = found
    section = inbox_section(wiki_conf)
    folder = wiki / section
    if not folder.is_dir():
        return ""
    title = plan_title(plan)
    day = datetime.fromtimestamp(now).strftime("%Y-%m-%d")
    stem = f"{day}-plan-{slugify(title)}"
    path = folder / f"{stem}.md"
    n = 2
    while path.exists():
        path = folder / f"{stem}-{n}.md"
        n += 1
    roles = wiki_conf.get("status_roles") if isinstance(wiki_conf.get("status_roles"), dict) else {}
    front = ["---", "title: " + json.dumps(title, ensure_ascii=False), f"created: {day}", f"updated: {day}", "tags: []",
             f"category: {section}", f"status: {roles.get('draft') or 'draft'}", "kind: capture"]
    if conf["plan_author"]:
        front.append(f"author: {conf['plan_author']}")
    front.append("---")
    body = plan if re.match(r"^#\s", plan) else f"# {title}\n\n{plan}"
    path.write_text("\n".join(front) + "\n\n" + body + "\n", encoding="utf-8")
    rel = path.relative_to(root).as_posix() if path.is_relative_to(root) else path.as_posix()
    return json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                              "additionalContext": f"The approved plan was copied to {rel}."}})


EVENTS = {"start": on_start, "prompt": on_prompt, "precompact": on_precompact, "end": on_end,
          "lesson": on_lesson, "plan": on_plan}


def read_stdin(seconds: float = 3.0) -> str:
    """The hook input. Claude Code writes it at once; a run by hand with stdin left open must not
    hang, so the read gives up after a moment."""
    if sys.stdin is None or sys.stdin.isatty():
        return ""
    box: list[str] = []

    def read() -> None:
        try:
            box.append(sys.stdin.read())
        except Exception:
            pass

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    reader.join(seconds)
    return box[0] if box else ""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Session hooks: second-session line, the user's words, lessons, plans.")
    ap.add_argument("--event", required=True, choices=sorted(EVENTS))
    args = ap.parse_args(argv)
    try:
        raw = read_stdin()
        data = json.loads(raw) if raw.strip() else {}
        if not isinstance(data, dict):
            data = {}
        root = workspace_root(data.get("cwd") if isinstance(data.get("cwd"), str) else None)
        out = EVENTS[args.event](root, data, config(root), time.time())
        if out:
            sys.stdout.buffer.write((out + "\n").encode("utf-8"))
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
