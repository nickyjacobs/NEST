# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""PreToolUse hook on AskUserQuestion: what the user must judge has to be in the dialog.

During a setup the assistant often asks "Is this summary right?" or "Do these twelve folders
fit?". In a real setup the summary and the folder list were four times only in the model's own
reasoning, never in the chat, and the user approved something she had not seen. A rule in the
prompt did not stop it, so this hook does.

It reads the dialog the assistant is about to show. A question that asks the user to judge
something (it says "is this right", "these folders", "this proposal", in one of a few
languages) passes when the thing is in the dialog itself: in the `preview` of an option, or in
the question text as more than one line. Otherwise the hook refuses the dialog once, and the
reason tells the assistant to put the content in the preview of the first option. The same
question asked again right away passes, so a question the check misreads costs one retry, never
a loop.

It only acts while a setup is running: `_setup/STATE.md` exists in the project folder and its
`next:` line is not `done`. Anything unexpected (no input, another tool, a file it cannot read)
lets the dialog through: this is a help for the user, not a security check.

State: `_setup/.ask_guard.json`, the fingerprints of questions it refused and that were not asked
again yet. A retry that passes takes its fingerprint off the list.

Left behind after a setup (the wrap-up takes it out), and with `_setup/nest/` removed, uv cannot
find this file and exits 2, which blocks every dialog: the hook must not outlive the setup.

Usage (settings, hooks.PreToolUse, matcher "AskUserQuestion"):
  uv run --quiet --script ${CLAUDE_PROJECT_DIR}/<path>/ask_guard.py
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

# Words that ask the user to judge something shown to them. Matched as whole words, case
# insensitive. Kept short on purpose: a miss costs nothing, a hit costs one retry.
JUDGE_WORDS = [
    # English
    r"is this (right|correct|ok|okay)", r"are these", r"does this (look|fit|match)",
    r"do these", r"look(s)? (right|good|correct)", r"this (summary|overview|proposal|list|plan|tree|picture)",
    r"these \w+ (right|correct|fit|ok)", r"above",
    r"is (this|the|that) .{0,40}(right|correct|ok|okay|fine)",
    # Dutch
    r"klopt", r"kloppen", r"deze samenvatting", r"dit overzicht", r"dit voorstel", r"dit beeld",
    r"deze lijst", r"deze mappen", r"dit plan", r"hierboven", r"zo goed", r"akkoord",
    r"is (dit|de|het) .{0,40}(goede?|juiste?|in orde)",
    # German
    r"stimmt", r"stimmen", r"diese zusammenfassung", r"dieser vorschlag", r"diese ordner", r"oben",
    r"passt (das|diese|dieser|dieses)",
    # French
    r"est-ce correct", r"ce résumé", r"cette proposition", r"ces dossiers", r"ci-dessus",
    # Spanish
    r"es correcto", r"este resumen", r"esta propuesta", r"estas carpetas", r"arriba", r"te parece bien",
]
JUDGE_RE = re.compile(r"\b(?:" + "|".join(JUDGE_WORDS) + r")\b", re.IGNORECASE)

REASON = (
    "This dialog asks the user to judge something that is not in the dialog. Text you meant to "
    "write in the chat may never have been sent. Put the thing to judge (the summary, the list, "
    "the folder tree, the proposal) in the `preview` field of the first option, as plain text "
    "without backticks, and ask again. Only when there is truly nothing to show (the options "
    "themselves are all there is to judge), ask the same question again unchanged: it will pass. "
    "Never use that to skip showing what you prepared."
)


def setup_running(project: Path) -> bool:
    state = project / "_setup" / "STATE.md"
    try:
        text = state.read_text(encoding="utf-8")
    except OSError:
        return False
    for line in text.splitlines():
        m = re.match(r"\s*next:\s*(.*)$", line)
        if m:
            return m.group(1).strip().strip("`").lower() != "done"
    return True


def needs_content(question: dict) -> bool:
    """True when the question asks to judge something and the dialog does not show it."""
    options = question.get("options") or []
    if any(isinstance(o, dict) and str(o.get("preview") or "").strip() for o in options):
        return False
    text = str(question.get("question") or "")
    if sum(1 for line in text.splitlines() if line.strip()) >= 3:  # the content is in the question
        return False
    return bool(JUDGE_RE.search(text))


def fingerprint(question: dict) -> str:
    text = re.sub(r"\s+", " ", str(question.get("question") or "")).strip().lower()
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def load_seen(path: Path) -> list[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    seen = data.get("refused_once") if isinstance(data, dict) else None
    return [s for s in seen if isinstance(s, str)] if isinstance(seen, list) else []


def save_seen(path: Path, seen: list[str]) -> None:
    try:
        path.write_text(json.dumps({"refused_once": seen[-200:]}, indent=1) + "\n", encoding="utf-8")
    except OSError:
        pass


def decide(payload: dict, project: Path) -> str | None:
    """Return the refusal reason, or None to let the dialog through."""
    if payload.get("tool_name") != "AskUserQuestion":
        return None
    if not setup_running(project):
        return None
    questions = [q for q in (payload.get("tool_input") or {}).get("questions") or [] if isinstance(q, dict)]
    flagged = [fingerprint(q) for q in questions if needs_content(q)]
    fine = {fingerprint(q) for q in questions if not needs_content(q)}
    state_file = project / "_setup" / ".ask_guard.json"
    seen = load_seen(state_file)
    # A refused question is cleared as soon as it comes back, fixed (a preview) or unchanged: the
    # same wording later in the setup (a recap is often worded the same) is checked again.
    kept = [s for s in seen if s not in fine]
    if flagged and all(p in kept for p in flagged):
        kept = [s for s in kept if s not in flagged]  # the immediate retry passes, only that one
        flagged = []
    if flagged:
        kept += [p for p in flagged if p not in kept]
    if kept != seen:
        save_seen(state_file, kept)
    return REASON if flagged else None


def main() -> int:
    try:
        # bytes, decoded here: Windows would read text in its own code page (hooks-notes.md)
        raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
        payload = json.loads(raw or "{}")
        if not isinstance(payload, dict):
            return 0
        project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or ".")
        reason = decide(payload, project)
    except Exception:  # a help, not a gate: never block on our own error
        return 0
    if reason:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
