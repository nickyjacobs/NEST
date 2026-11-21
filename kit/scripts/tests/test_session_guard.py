"""Tests for session_guard.py: the user's words, the second-session line, lessons and plans."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import session_guard as sg

SCRIPT = Path(sg.__file__)
NOW = time.time()


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("NEST_WIKI_CONFIG", raising=False)
    return tmp_path


def conf(ws: Path) -> dict:
    return sg.config(ws)


def event(sid: str = "s1", **fields) -> dict:
    return {"session_id": sid, **fields}


# --- the user's words ------------------------------------------------------------------------

def test_prompt_is_kept_word_for_word(ws):
    sg.on_prompt(ws, event(prompt="Keep the old pricing page, I said."), conf(ws), NOW)
    sg.on_prompt(ws, event(prompt="And no emoji."), conf(ws), NOW + 60)
    text = sg.words_path(ws, "s1").read_text(encoding="utf-8")
    assert "Keep the old pricing page, I said." in text and "And no emoji." in text
    assert text.index("pricing") < text.index("emoji")


def test_empty_prompt_writes_nothing(ws):
    sg.on_prompt(ws, event(prompt="   "), conf(ws), NOW)
    assert not sg.words_path(ws, "s1").exists()


def test_long_prompt_is_cut(ws):
    sg.on_prompt(ws, event(prompt="x" * (sg.PROMPT_CHARS + 500)), conf(ws), NOW)
    text = sg.words_path(ws, "s1").read_text(encoding="utf-8")
    assert "(message cut here)" in text and len(text) < sg.PROMPT_CHARS + 200


def test_precompact_prints_the_words(ws):
    sg.on_prompt(ws, event(prompt="Never touch the archive folder."), conf(ws), NOW)
    out = sg.on_precompact(ws, event(), conf(ws), NOW + 5)
    assert out.startswith("Keep the user's own messages") and "Never touch the archive folder." in out


def test_precompact_without_words_is_silent(ws):
    assert sg.on_precompact(ws, event(), conf(ws), NOW) == ""


def test_precompact_keeps_the_newest_when_over_the_limit(ws):
    (ws / "nest.json").write_text(json.dumps({"session_guard": {"words_chars": 200}}), encoding="utf-8")
    for i in range(20):
        sg.on_prompt(ws, event(prompt=f"message number {i} " + "y" * 30), conf(ws), NOW + i * 60)
    out = sg.on_precompact(ws, event(), conf(ws), NOW + 3000)
    assert "message number 19" in out and "message number 0 " not in out and "(earlier messages left out)" in out


def test_start_after_compaction_names_the_words_file(ws):
    sg.on_prompt(ws, event(prompt="hello"), conf(ws), NOW)
    out = sg.on_start(ws, event(source="compact"), conf(ws), NOW + 10)
    assert ".claude/.session/s1.words.md" in out
    assert sg.on_start(ws, event(source="resume"), conf(ws), NOW + 20) == ""


# --- two sessions ----------------------------------------------------------------------------

def test_single_session_is_silent(ws):
    assert sg.on_start(ws, event("s1", source="startup"), conf(ws), NOW) == ""
    assert sg.on_prompt(ws, event("s1", prompt="hi"), conf(ws), NOW + 30) == ""


def test_second_session_is_told_once(ws):
    sg.on_start(ws, event("s1", source="startup"), conf(ws), NOW)
    out = sg.on_start(ws, event("s2", source="startup"), conf(ws), NOW + 120)
    assert "Another Claude Code session" in out and "2 minutes ago" in out
    assert sg.on_prompt(ws, event("s2", prompt="hi"), conf(ws), NOW + 180) == ""


def test_first_session_hears_about_the_second_on_its_next_prompt(ws):
    sg.on_start(ws, event("s1", source="startup"), conf(ws), NOW)
    sg.on_start(ws, event("s2", source="startup"), conf(ws), NOW + 60)
    assert "Another Claude Code session" in sg.on_prompt(ws, event("s1", prompt="go on"), conf(ws), NOW + 90)
    assert sg.on_prompt(ws, event("s1", prompt="again"), conf(ws), NOW + 120) == ""


def test_stale_session_is_ignored(ws):
    sg.on_start(ws, event("s1", source="startup"), conf(ws), NOW)
    assert sg.on_start(ws, event("s2", source="startup"), conf(ws), NOW + 31 * 60) == ""


def test_ended_session_is_ignored(ws):
    sg.on_start(ws, event("s1", source="startup"), conf(ws), NOW)
    sg.on_end(ws, event("s1", reason="other"), conf(ws), NOW + 10)
    assert sg.on_start(ws, event("s2", source="startup"), conf(ws), NOW + 20) == ""


def test_old_files_are_cleaned(ws):
    import os
    sg.on_prompt(ws, event("old", prompt="x"), conf(ws), NOW)
    old = NOW - 20 * 86400
    for path in (ws / sg.STATE_DIR).iterdir():
        os.utime(path, (old, old))
    sg.on_start(ws, event("new", source="startup"), conf(ws), NOW)
    names = {p.name for p in (ws / sg.STATE_DIR).iterdir()}
    assert names == {"new.json"}


def test_session_id_cannot_leave_the_folder(ws):
    sg.on_prompt(ws, event("../../evil", prompt="x"), conf(ws), NOW)
    assert sg.words_path(ws, "evil").is_file()
    assert not (ws.parent / "evil.words.md").exists()


# --- lessons ---------------------------------------------------------------------------------

def lessons(ws: Path, items) -> None:
    (ws / ".claude").mkdir(exist_ok=True)
    (ws / sg.LESSONS_FILE).write_text(json.dumps(items), encoding="utf-8")


def bash(command: str, sid: str = "s1") -> dict:
    return event(sid, tool_name="Bash", tool_input={"command": command})


def test_lesson_on_a_command_is_shown_once(ws):
    lessons(ws, [{"id": "force", "on": "command", "match": r"git push .*--force", "lesson": "Ask before a force push."}])
    out = json.loads(sg.on_lesson(ws, bash("git push origin main --force"), conf(ws), NOW))
    assert out["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    assert "Ask before a force push." in out["hookSpecificOutput"]["additionalContext"]
    assert sg.on_lesson(ws, bash("git push --force"), conf(ws), NOW + 5) == ""
    assert sg.on_lesson(ws, bash("git push --force", sid="s2"), conf(ws), NOW + 5) != ""


def test_lesson_that_does_not_match_is_silent(ws):
    lessons(ws, [{"on": "command", "match": "rm -rf", "lesson": "Careful."}])
    assert sg.on_lesson(ws, bash("ls -la"), conf(ws), NOW) == ""


def test_lesson_on_a_file_path(ws):
    lessons(ws, {"lessons": [{"on": "file", "match": r"^wiki/00-context/", "lesson": "Context pages are the user's."}]})
    edit = event(tool_name="Edit", tool_input={"file_path": str(ws / "wiki" / "00-context" / "me.md")})
    assert "Context pages" in sg.on_lesson(ws, edit, conf(ws), NOW)
    other = event("s3", tool_name="Write", tool_input={"file_path": str(ws / "docs" / "x.md")})
    assert sg.on_lesson(ws, other, conf(ws), NOW) == ""
    command = bash("cat wiki/00-context/me.md", sid="s4")
    assert sg.on_lesson(ws, command, conf(ws), NOW) == ""


def test_broken_lessons_are_skipped(ws):
    lessons(ws, [{"match": "(", "lesson": "bad regex"}, {"match": "ok"}, "nonsense",
                 {"match": "deploy", "lesson": "Run the tests first."}])
    assert "Run the tests first." in sg.on_lesson(ws, bash("make deploy"), conf(ws), NOW)


def test_no_lessons_file_is_silent(ws):
    assert sg.on_lesson(ws, bash("git push --force"), conf(ws), NOW) == ""


# --- plan to inbox ---------------------------------------------------------------------------

def plan_event(plan: str) -> dict:
    return event(tool_name="ExitPlanMode", tool_input={}, tool_response={"plan": plan, "filePath": "/x/plan.md"})


def test_plan_lands_in_the_inbox(ws):
    (ws / "wiki" / "_inbox").mkdir(parents=True)
    out = json.loads(sg.on_plan(ws, plan_event("# Move the site: step one\n\n1. Export.\n"), conf(ws), NOW))
    note = next((ws / "wiki" / "_inbox").glob("*-plan-move-the-site-step-one.md"))
    assert note.relative_to(ws).as_posix() in out["hookSpecificOutput"]["additionalContext"]
    text = note.read_text(encoding="utf-8")
    assert text.startswith("---\ntitle: \"Move the site: step one\"\n")
    assert "category: _inbox" in text and "kind: capture" in text and "author: claude" in text
    assert text.count("# Move the site: step one") == 1 and "1. Export." in text


def test_plan_uses_the_configured_inbox_and_status(ws):
    (ws / "wiki.config.json").write_text(json.dumps({"wiki_dir": "vault", "status_roles": {"draft": "concept"},
                                                     "sections": {"postvak": {"raw": True}}}), encoding="utf-8")
    (ws / "nest.json").write_text(json.dumps({"session_guard": {"plan_author": ""}}), encoding="utf-8")
    (ws / "vault" / "postvak").mkdir(parents=True)
    sg.on_plan(ws, plan_event("Just a line without a heading"), conf(ws), NOW)
    text = next((ws / "vault" / "postvak").glob("*.md")).read_text(encoding="utf-8")
    assert "category: postvak" in text and "status: concept" in text and "author:" not in text
    assert "# Just a line without a heading" in text


def test_plan_never_overwrites(ws):
    (ws / "wiki" / "_inbox").mkdir(parents=True)
    sg.on_plan(ws, plan_event("# Same title\n\nfirst"), conf(ws), NOW)
    sg.on_plan(ws, plan_event("# Same title\n\nsecond"), conf(ws), NOW)
    notes = sorted(p.name for p in (ws / "wiki" / "_inbox").glob("*.md"))
    assert len(notes) == 2 and any(name.endswith("-2.md") for name in notes)


def test_plan_without_wiki_or_inbox_does_nothing(ws):
    assert sg.on_plan(ws, plan_event("# Plan"), conf(ws), NOW) == ""
    (ws / "wiki").mkdir()
    assert sg.on_plan(ws, plan_event("# Plan"), conf(ws), NOW) == ""


def test_plan_ignores_other_tools(ws):
    (ws / "wiki" / "_inbox").mkdir(parents=True)
    data = event(tool_name="Write", tool_response={"plan": "# Not a plan"})
    assert sg.on_plan(ws, data, conf(ws), NOW) == ""


# --- command line ----------------------------------------------------------------------------

def run(ws: Path, name: str, data) -> subprocess.CompletedProcess:
    payload = data if isinstance(data, str) else json.dumps(data)
    return subprocess.run([sys.executable, str(SCRIPT), "--event", name], input=payload, capture_output=True,
                          text=True, encoding="utf-8", check=False, cwd=ws)


def test_cli_round_trip(ws):
    assert run(ws, "prompt", event(prompt="Use British spelling.", cwd=str(ws))).returncode == 0
    out = run(ws, "precompact", event(cwd=str(ws), trigger="auto"))
    assert out.returncode == 0 and "Use British spelling." in out.stdout


@pytest.mark.parametrize("name", sorted(sg.EVENTS))
def test_cli_never_fails_on_bad_input(ws, name):
    for payload in ("", "{not json", "[1, 2]", json.dumps({"session_id": None, "tool_input": "x"})):
        result = run(ws, name, payload)
        assert result.returncode == 0 and result.stderr == ""
