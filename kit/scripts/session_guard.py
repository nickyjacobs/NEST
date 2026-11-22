# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Session hooks that keep a workspace safe across a long conversation.

One script, one job per `--event`. Wire only the ones the user wants (see
`kit/claude/settings.reference.json`):

  start       SessionStart. Registers the session and notes when it was opened. After a
              compaction it names the file with the user's own words, and prints the
              second-session line when one is due (see prompt).
  prompt      UserPromptSubmit. Appends the user's message, word for word, to a file for this
              session. When another session was active in this workspace while this one was
              open, prints one line, once per other session, so Claude knows two sessions may
              write the same files.
              One thing is taken out first: a secret the user pasted (a key, a token, a
              password, a private key block), as validate.py next to this script recognises
              it. In its place stands "[secret removed]", so the file and the compaction
              summary never hold it. Without validate.py the message is stored as it is.
  precompact  PreCompact. Prints the user's messages as instructions for the compaction summary,
              so their own wording survives it: the first message of the session (where the
              goal usually is) and the newest ones, up to `words_chars`. All of them stay in
              the words file, which the start line after a compaction points to.
  end         SessionEnd. Removes the session's registration.
  lesson      PreToolUse. Shows a recorded lesson at the moment it applies, once per session
              and once more after each compaction.
  plan        PostToolUse on ExitPlanMode. Copies the approved plan into the wiki inbox.

Files, all under `.claude/.session/` (gitignored, local to this machine):
  <session>.json       when the session started, was opened last and was last seen, where its
                       transcript is, what it was already told, and the first words of its last
                       message, by which another session can name it: secrets and the private
                       terms of the workspace taken out, plain words only, and nothing at all
                       when validate.py is not there to take them out
  <session>.words.md   the user's messages of that session
Both are removed after `keep_days`. The folder is made for the user alone (mode 0700, the files
0600), because the words file holds everything the user typed; on Windows the folder keeps the
permissions of the user's profile.

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
                             (at most 9500: Claude Code cuts a hook's output at 10,000 characters)
      "plan_author": "claude"   author value for a plan note; "" leaves the field out
  }}

A session's last activity is the newer of two moments: its last prompt, and the last write to its
transcript file. The second one keeps a session visible while it works for a long time without a
new prompt.

Another session counts as a second session only when there is proof that it ran next to this one:
its last activity is later than the moment this session was opened plus a minute
(HANDOVER_SECONDS), and no older than `live_minutes`. A file of another session alone proves
nothing: a session that crashed cannot say goodbye, SessionEnd may not run or may not finish, and
a user who ends one conversation and starts the next sees the new one start while the old one
still writes its last message. All of those were active before this session opened, or in its
first minute, and then never again. The price is that a real second session is named on the first
prompt after it showed itself, not at the start.

The workspace root is $CLAUDE_PROJECT_DIR, else the hook's cwd, else the current directory.
The hook input is read as UTF-8 bytes, whatever the console code page is. Input without a
session id is ignored. It never fails a session: every error is swallowed and the exit code is always 0.
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
# How long after this session was opened another session may still finish its last step without
# counting as a second session. The first real user's old conversation wrote its last message 2
# and 8 seconds after the new one had started.
HANDOVER_SECONDS = 60
# How much of a session's last message is kept in its state file, so another session can say
# which conversation it means.
ASKED_CHARS = 80
WORDS_CEILING = 9500  # Claude Code cuts a hook's stdout at 10,000 characters; the intro needs room
STAMP = re.compile(r"(?m)^## \d{4}-\d{2}-\d{2} \d{2}:\d{2}$")
WORDS_OPEN, WORDS_CLOSE = "<<< the user's messages", ">>> end of the user's messages"
# A line in a message that looks like one of the guard's own lines gets a backslash in front, so
# pasted text cannot pose as a separate message or close the block early.
LOOKS_LIKE_OURS = re.compile(r"(?m)^(?=## \d{4}-\d{2}-\d{2} \d{2}:\d{2}[ \t]*$|<<< the user's messages|>>> end of the user's messages)")
SAFE_ID = re.compile(r"[^A-Za-z0-9_-]")


def workspace_root(hook_cwd: str | None) -> Path:
    for candidate in (os.environ.get("CLAUDE_PROJECT_DIR"), hook_cwd):
        if candidate and Path(candidate).is_dir():
            return Path(candidate)
    return Path.cwd()


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
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
    """The session's id as a safe file name, or "" when the input names none."""
    raw = data.get("session_id")
    return SAFE_ID.sub("", raw)[:80] if isinstance(raw, str) else ""


def state_path(root: Path, sid: str) -> Path:
    return root / STATE_DIR / f"{sid}.json"


def words_path(root: Path, sid: str) -> Path:
    return root / STATE_DIR / f"{sid}.words.md"


def load_state(root: Path, sid: str) -> dict:
    data = read_json(state_path(root, sid))
    return data if isinstance(data, dict) else {}


def private_folder(folder: Path) -> None:
    """The session folder, readable by the user alone: it holds every message the user typed."""
    folder.mkdir(parents=True, exist_ok=True)
    try:
        if os.name != "nt" and (folder.stat().st_mode & 0o077):
            folder.chmod(0o700)
    except OSError:
        pass


def private_file(path: Path, append: bool = False):
    """Open a file for writing with mode 0600, whatever the umask is, also when it already exists."""
    flags = os.O_WRONLY | os.O_CREAT | (os.O_APPEND if append else os.O_TRUNC)
    fd = os.open(path, flags, 0o600)
    try:
        if os.name != "nt":
            os.fchmod(fd, 0o600)
    except OSError:
        pass
    return os.fdopen(fd, "a" if append else "w", encoding="utf-8")


def save_state(root: Path, sid: str, state: dict) -> None:
    path = state_path(root, sid)
    private_folder(path.parent)
    # One name per process: hooks for calls that run side by side would otherwise share one
    # temporary file, and one of them would lose its write.
    tmp = path.with_name(f"{path.stem}.{os.getpid()}.tmp")
    try:
        with private_file(tmp) as fh:
            fh.write(json.dumps(state))
        tmp.replace(path)
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass


def touch(root: Path, sid: str, now: float, data: dict | None = None, opened: bool = False) -> dict:
    """Note that the session is alive. `opened` marks the moment the user opened it (a start or
    a resume): what another session did before that was not done next to this one."""
    state = load_state(root, sid)
    state.setdefault("started", now)
    if opened or not is_time(state.get("opened")):
        state["opened"] = now if opened else state["started"]
    state["seen"] = now
    transcript = (data or {}).get("transcript_path")
    if isinstance(transcript, str) and transcript:
        state["transcript"] = transcript
    save_state(root, sid, state)
    return state


def is_time(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


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


def last_active(state: dict) -> float | None:
    """The newer of the last prompt and the last write to the transcript: a session that works
    for a long time without a new prompt keeps writing its transcript."""
    seen = state.get("seen")
    seen = float(seen) if is_time(seen) else None
    transcript = state.get("transcript")
    if isinstance(transcript, str) and transcript:
        try:
            written = Path(transcript).stat().st_mtime
            seen = written if seen is None else max(seen, written)
        except (OSError, ValueError):
            pass
    return seen


def other_sessions(root: Path, sid: str, live_minutes: float, now: float,
                   after: float | None = None) -> list[tuple[str, float]]:
    """Other sessions seen within `live_minutes`, and later than `after` when that is given:
    (id, minutes since their last activity)."""
    folder = root / STATE_DIR
    found = []
    if folder.is_dir():
        for path in sorted(folder.glob("*.json")):
            if path.stem == sid:
                continue
            data = read_json(path)
            seen = last_active(data) if isinstance(data, dict) else None
            if seen is not None and 0 <= now - seen <= live_minutes * 60 and (after is None or seen > after):
                found.append((path.stem, (now - seen) / 60))
    return found


def second_session_line(root: Path, sid: str, conf: dict, now: float) -> str:
    """One line about sessions that were active while this one was open and that it was not
    told about yet; marks them as told. Without a known moment of opening nothing is said."""
    state = load_state(root, sid)
    told = state.get("told")
    # A value of another kind (a damaged file) counts as: not told yet.
    told = {item for item in told if isinstance(item, str)} if isinstance(told, list) else set()
    opened = next((float(state[key]) for key in ("opened", "started") if is_time(state.get(key))), now)
    fresh = [(other, minutes) for other, minutes
             in other_sessions(root, sid, conf["live_minutes"], now, after=opened + HANDOVER_SECONDS)
             if other not in told]
    if not fresh:
        return ""
    state["told"] = sorted(told | {other for other, _ in fresh})
    save_state(root, sid, state)
    newest, minutes = min(fresh, key=lambda item: item[1])
    ago = "less than a minute ago" if minutes < 1 else f"{int(minutes)} minute{'s' if int(minutes) != 1 else ''} ago"
    clock = datetime.fromtimestamp(now - minutes * 60).strftime("%H:%M")
    asked = load_state(root, newest).get("asked")
    asked = plain_words(asked) if isinstance(asked, str) else ""  # again: the file may be older, or not ours
    return ("A second Claude Code session was active in this workspace " + ago + " (at " + clock + "), while this "
            "session was already open. "
            + (f"Its last message from the user began: '{asked[:ASKED_CHARS + 3]}'. " if asked else "")
            + "Two sessions that write the same files can overwrite each other's work. "
            "Where the user finds it: in a terminal, another window or tab where Claude Code runs in this "
            "folder; in the VS Code extension or the desktop app, another conversation that is still working "
            "(a second Claude tab or panel, a second window on this folder, or an earlier conversation in the "
            "history). Once found, the safe way on is to let one of the two finish, or to close one, before "
            "going on with the same files. A conversation the user closed can go on for a moment to finish its "
            "last step; when the user finds no second one, nothing needs to be done. "
            "The user has not been told about it in this session yet.")


SECRET_MARK = "[secret removed]"
PRIVATE_MARK = "[private term removed]"
_rules: list | None = None
_key_blocks = None
_private_terms = None  # validate.load_private_rules, once secret_rules() has found validate.py


def secret_rules() -> list:
    """The hard rules of validate.py, when it sits next to this script; else none. What a private
    key block is comes from the same place, so the scan and this file cannot disagree about it."""
    global _rules, _key_blocks, _private_terms
    if _rules is None:
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            import validate
            _rules, _key_blocks = list(validate.HARD_RULES), validate.key_blocks
            _private_terms = validate.load_private_rules
        except Exception:
            _rules = []
    return _rules


# Rules that go by the name in front of a value, not by the shape of the value itself.
BY_NAME = {"secret_assignment", "cli_password", "xml_secret", "table_secret"}
QUOTED_GROUPS = ("dq", "sq", "bq")
# What may close a sentence or a bracket right after an unquoted value: not part of the secret.
TRAILING = ".,;)]}>"


def secret_spans(line: str, rules: list) -> list[tuple[int, int]]:
    """Where the secrets in one line start and end, without overlap, left to right.

    A rule that knows the shape of a token (a GitHub token, a key with a prefix) marks that token
    and nothing else. A rule that goes by the name in front (`password: ...`) marks the value up
    to the first white space or quote, without the punctuation that closes the sentence; when a
    token of a known shape lies inside that value, the token alone is marked. Two rules that find
    the same secret count once."""
    by_shape: list[tuple[int, int]] = []
    by_name: list[tuple[int, int]] = []
    for rule in rules:
        for m in rule.regex.finditer(line):
            if not rule.accepts(m):
                continue
            start, end = m.span()
            groups = m.re.groupindex
            quoted = next((g for g in QUOTED_GROUPS if g in groups and m.group(g) is not None), None)
            plain = next((g for g in ("raw", "v") if g in groups and m.group(g) is not None), None)
            if quoted:
                start, end = m.span(quoted)
            elif plain:
                start, end = m.span(plain)
                while end - start > 1 and line[end - 1] in TRAILING:
                    end -= 1
            (by_name if rule.name in BY_NAME else by_shape).append((start, end))
    by_name = [(a, b) for a, b in by_name if not any(a <= c and d <= b for c, d in by_shape)]
    merged: list[tuple[int, int]] = []
    for start, end in sorted(by_shape + by_name):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def without_secrets(text: str) -> str:
    """The text with every secret replaced by a marker, and nothing else touched: the words
    before and after a secret are the user's, and this file exists to keep them."""
    rules = secret_rules()
    if not rules:
        return text
    if _key_blocks is not None:
        for start, end in reversed(_key_blocks(text)):
            text = text[:start] + SECRET_MARK + text[end:]
    lines = []
    for line in text.split("\n"):
        for start, end in reversed(secret_spans(line, rules)):
            line = line[:start] + SECRET_MARK + line[end:]
        lines.append(line)
    return "\n".join(lines)


def plain_words(text: str) -> str:
    """Text that is safe to put into another session's context as a quotation: printable
    characters only (no control character, no escape sequence, no invisible or
    direction-changing character), no angle bracket and no backtick (a tag or a code block),
    no quote (it stands between quotes), all white space as single spaces."""
    return " ".join("".join(ch if ch.isprintable() and ch not in "<>`\"'" else " " for ch in text).split())


def asked_text(root: Path, prompt: str) -> str:
    """The start of a message for the second-session line of another session: the message after
    the secrets were taken out, with the private terms of this workspace taken out by the
    scanner's own rules as well, as plain words. "" when validate.py is not next to this script
    or the terms cannot be applied: then nothing vouches for the text, and none is kept."""
    if not prompt or not secret_rules() or _private_terms is None:
        return ""
    text = prompt[:ASKED_CHARS * 10]  # enough to show ASKED_CHARS of it, whatever is taken out
    try:
        for rule in _private_terms(root)[0]:
            text = rule.regex.sub(PRIVATE_MARK, text)
    except Exception:
        return ""
    text = plain_words(text)
    return text[:ASKED_CHARS].rstrip() + ("..." if len(text) > ASKED_CHARS else "")


def user_words(root: Path, sid: str, limit: int) -> str:
    """The user's messages for the compaction summary: all of them when they fit, else the first
    one (a session's goal is usually there) and as many of the newest as fit."""
    try:
        text = words_path(root, sid).read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""
    if len(text) <= limit:
        return text
    starts = [m.start() for m in STAMP.finditer(text)]
    if not starts or starts[0] != 0:
        starts.insert(0, 0)
    blocks = [text[a:b].strip() for a, b in zip(starts, [*starts[1:], len(text)])]
    marker = "(messages in between left out)"
    first = blocks[0]
    room = max(limit // 3, 1)
    if len(first) > room:
        first = first[:room].rstrip() + "\n(message cut here)"
    budget = limit - len(first) - len(marker) - 4
    newest: list[str] = []
    for block in reversed(blocks[1:]):
        if len(block) + 2 > budget:
            if not newest and budget > 40:
                newest.append(block[:budget - 22].rstrip() + "\n(message cut here)")
            break
        newest.append(block)
        budget -= len(block) + 2
    left_out = len(newest) < len(blocks) - 1
    return "\n\n".join([first, *([marker] if left_out else []), *reversed(newest)])


# --- events ------------------------------------------------------------------------------------

def on_start(root: Path, data: dict, conf: dict, now: float) -> str:
    sid = session_id(data)
    cleanup(root, conf["keep_days"], now)
    if not sid:
        return ""
    # A compaction happens inside a session that stays open; every other start opens it.
    state = touch(root, sid, now, data, opened=data.get("source") != "compact")
    if data.get("source") == "compact" and state.get("lessons"):
        # The lessons shown so far went out with the old context: show each again when it applies.
        state.pop("lessons")
        save_state(root, sid, state)
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
    if not sid:
        return ""
    touch(root, sid, now, data)
    prompt = data.get("prompt")
    prompt = prompt.strip() if isinstance(prompt, str) else ""
    unclean = False
    if prompt:
        try:
            # A little past the cut, so a secret that straddles it is still seen whole.
            prompt = without_secrets(prompt[:PROMPT_CHARS + 2000])
        except Exception:
            prompt = ""  # rather no words than a secret on disk
            unclean = True
        if len(prompt) > PROMPT_CHARS:
            prompt = prompt[:PROMPT_CHARS].rstrip() + "\n(message cut here)"
        prompt = LOOKS_LIKE_OURS.sub(r"\\\g<0>", prompt)
        path = words_path(root, sid)
        private_folder(path.parent)
        stamp = datetime.fromtimestamp(now).strftime("%Y-%m-%d %H:%M")
        with private_file(path, append=True) as fh:
            fh.write(f"## {stamp}\n\n{prompt}\n\n")
    # The start of the message for the second-session line of another session: secrets and
    # private terms taken out, plain words only. A message that could not be cleaned leaves none.
    if prompt or unclean:
        state = load_state(root, sid)
        state["asked"] = asked_text(root, prompt)
        save_state(root, sid, state)
    return second_session_line(root, sid, conf, now)


def on_precompact(root: Path, data: dict, conf: dict, now: float) -> str:
    sid = session_id(data)
    words = user_words(root, sid, min(int(conf["words_chars"]), WORDS_CEILING)) if sid else ""
    if not words:
        return ""
    return ("Keep the user's own messages in the summary word for word where they state a goal, a decision, "
            "a preference or a correction. These are their messages in this session, oldest first, between the "
            f"two marker lines; each starts with a line of the form '## date time':\n\n{WORDS_OPEN}\n{words}\n{WORDS_CLOSE}")


def on_end(root: Path, data: dict, conf: dict, now: float) -> str:
    sid = session_id(data)
    try:
        if sid:
            state_path(root, sid).unlink()
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
    if not sid:
        return ""
    state = load_state(root, sid)
    shown = set(state.get("lessons") or [])
    fresh = [item for item in lessons if item["id"] not in shown]
    if not fresh:
        return ""
    state.setdefault("started", now)
    state["seen"] = now
    state["lessons"] = sorted(shown | {item["id"] for item in fresh})
    try:
        save_state(root, sid, state)
    except OSError:
        pass  # a lesson shown twice is better than a lesson not shown
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
    # Only the tool response holds the approved plan. After a call that failed the response is
    # an error text, and the plan in the tool input is then one nobody approved.
    response = data.get("tool_response") if isinstance(data.get("tool_response"), dict) else {}
    plan = response.get("plan")
    plan = plan.strip() if isinstance(plan, str) else ""
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
