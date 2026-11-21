"""Tests for session_context.py: one line, and never a failed session."""
from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import session_context as sc

SCRIPT = Path(sc.__file__)


def note(path: Path, kind: str | None = None, key: str = "kind") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    front = f"---\ntitle: x\n{key}: {kind}\n---\n" if kind else "---\ntitle: x\n---\n"
    path.write_text(front + "body\n", encoding="utf-8")


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("NEST_WIKI_CONFIG", raising=False)
    return tmp_path


def test_full_line(ws):
    (ws / "wiki.config.json").write_text(json.dumps({"wiki_dir": "vault", "sections": {
        "notes": {"index": "by_kind"}, "inbox": {"index": "flat", "raw": True, "kinds": {"question": "Q"}}}}),
        encoding="utf-8")
    note(ws / "vault/inbox/a.md", "question")
    note(ws / "vault/inbox/b.md", "capture")
    note(ws / "vault/inbox/c.md", "question", key="status")
    note(ws / "vault/inbox/index.md")
    (ws / "docs").mkdir()
    (ws / "docs/next-session.md").write_text("# Next\n\n- [x] done\n- [ ] Fix the login redirect\n- [ ] later\n",
                                             encoding="utf-8")
    line = sc.build_line(ws)
    assert line == ("Workspace: wiki inbox 3 notes (2 questions), "
                    "first open item in docs/next-session.md: Fix the login redirect")


def test_defaults_without_config(ws):
    note(ws / "wiki/_inbox/a.md")
    assert sc.build_line(ws) == "Workspace: wiki inbox 1 note"


def test_nothing_to_report(ws):
    assert sc.build_line(ws) == ""


def test_no_open_items(ws):
    (ws / "docs").mkdir()
    (ws / "docs/next-session.md").write_text("- [x] all done\n", encoding="utf-8")
    assert sc.build_line(ws).endswith("first open item in docs/next-session.md: none")


def test_long_item_is_cut(ws):
    (ws / "docs").mkdir()
    (ws / "docs/next-session.md").write_text("- [ ] " + "word " * 60 + "\n", encoding="utf-8")
    item = sc.build_line(ws).split("next-session.md: ", 1)[1]
    assert len(item) <= sc.ITEM_CHARS and item.endswith("...")


def git(*args: str, cwd: Path | None = None) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def test_backup_pending_counts_uncommitted_files(ws, tmp_path_factory):
    gd = tmp_path_factory.mktemp("backup") / "w.git"
    note(ws / "wiki/_inbox/a.md")
    git(f"--git-dir={gd}", f"--work-tree={ws / 'wiki'}", "init", "-q")
    (ws / "nest.json").write_text(json.dumps({"wiki_backup": {"git_dir": str(gd)}}), encoding="utf-8")
    assert "wiki backup 1 unpushed change" in sc.build_line(ws)


def test_missing_backup_dir_is_silent(ws):
    note(ws / "wiki/_inbox/a.md")
    (ws / "nest.json").write_text(json.dumps({"wiki_backup": {"git_dir": "~/.does-not-exist-wiki.git"}}),
                                  encoding="utf-8")
    assert "backup" not in sc.build_line(ws)


def test_broken_config_never_fails(ws):
    (ws / "wiki.config.json").write_text("{broken", encoding="utf-8")
    (ws / "nest.json").write_text("[1, 2]", encoding="utf-8")
    note(ws / "wiki/_inbox/a.md")
    assert sc.build_line(ws) == "Workspace: wiki inbox 1 note"


def test_main_reads_hook_json_and_exits_zero(ws, monkeypatch, capsysbinary):
    monkeypatch.delenv("CLAUDE_PROJECT_DIR")
    note(ws / "wiki/_inbox/a.md")
    payload = json.dumps({"hook_event_name": "SessionStart", "source": "startup", "cwd": str(ws)})
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(payload.encode())))
    assert sc.main() == 0
    assert capsysbinary.readouterr().out == b"Workspace: wiki inbox 1 note\n"


def test_main_survives_garbage_stdin(ws, monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(b"\xff\xfe not json")))
    assert sc.main() == 0


def test_script_prints_one_line(ws):
    note(ws / "wiki/_inbox/a.md")
    r = subprocess.run(check=False, args=[sys.executable, str(SCRIPT)], input=b"{}", capture_output=True)
    assert r.returncode == 0 and r.stdout.decode().count("\n") == 1


def test_status_question_counts_even_with_another_kind(ws):
    p = ws / "wiki/_inbox/a.md"
    p.parent.mkdir(parents=True)
    p.write_text("---\nkind: capture\nstatus: question\n---\nq\n", encoding="utf-8")
    assert sc.build_line(ws) == "Workspace: wiki inbox 1 note (1 question)"


def test_inbox_is_the_raw_section_whatever_its_index(ws):
    (ws / "wiki.config.json").write_text(json.dumps({"sections": {"inbox": {"raw": True, "index": "none"}}}),
                                         encoding="utf-8")
    note(ws / "wiki/inbox/a.md")
    assert sc.build_line(ws) == "Workspace: wiki inbox 1 note"


def test_config_from_env_and_wiki_dir_relative_to_config(ws, tmp_path_factory, monkeypatch):
    elsewhere = tmp_path_factory.mktemp("cfg")
    (elsewhere / "wiki.config.json").write_text(json.dumps({"wiki_dir": "vault"}), encoding="utf-8")
    note(elsewhere / "vault/_inbox/a.md", "question", key="status")
    monkeypatch.setenv("NEST_WIKI_CONFIG", str(elsewhere / "wiki.config.json"))
    assert sc.build_line(ws) == "Workspace: wiki inbox 1 note (1 question)"


def test_config_found_upwards(ws):
    sub = ws / "project"
    sub.mkdir()
    (ws / "wiki.config.json").write_text(json.dumps({"wiki_dir": "notes"}), encoding="utf-8")
    note(ws / "notes/_inbox/a.md")
    assert sc.build_line(sub) == "Workspace: wiki inbox 1 note"


# --- size ceiling, update line, morning nudge ------------------------------------------------

def test_size_ceiling_counts_what_always_loads(ws):
    (ws / "CLAUDE.md").write_text("line\n" * 300, encoding="utf-8")
    (ws / ".claude" / "rules").mkdir(parents=True)
    (ws / ".claude/rules/always.md").write_text("rule\n" * 150, encoding="utf-8")
    (ws / ".claude/rules/scoped.md").write_text("---\npaths:\n  - wiki/**\n---\n" + "rule\n" * 500, encoding="utf-8")
    assert sc.build_line(ws) == "Workspace: always-loaded files 450 lines (ceiling 400, largest CLAUDE.md with 300)"


def test_size_ceiling_is_silent_under_the_limit_and_can_be_changed(ws):
    (ws / "CLAUDE.md").write_text("line\n" * 120, encoding="utf-8")
    assert sc.build_line(ws) == ""
    (ws / "nest.json").write_text(json.dumps({"size_ceiling": {"lines": 100}}), encoding="utf-8")
    assert "ceiling 100" in sc.build_line(ws)
    (ws / "nest.json").write_text(json.dumps({"size_ceiling": {"lines": 0}}), encoding="utf-8")
    assert sc.build_line(ws) == ""


def test_update_line_comes_from_nest_update(ws, monkeypatch):
    import nest_update
    (ws / "nest.json").write_text(json.dumps({"nest": {"version": "1.0.0"}}), encoding="utf-8")
    monkeypatch.setattr(nest_update, "notice", lambda root, **kw: "NEST 1.1.0 is available")
    assert sc.build_line(ws) == "Workspace: NEST 1.1.0 is available"
    monkeypatch.setattr(nest_update, "notice", lambda root, **kw: 1 / 0)
    assert sc.build_line(ws) == ""


def test_update_line_needs_a_stamp(ws, monkeypatch):
    import nest_update
    monkeypatch.setattr(nest_update, "notice", lambda root, **kw: "should not show")
    assert sc.build_line(ws) == ""


def test_morning_nudge(ws):
    from datetime import datetime
    (ws / "nest.json").write_text(json.dumps({"morning_nudge": {"before": "11:00", "text": "say brief me"}}),
                                  encoding="utf-8")
    early, late = datetime(2026, 1, 8, 8, 30), datetime(2026, 1, 8, 11, 0)
    assert sc.nudge_part(ws, "startup", early) is None
    (ws / ".claude/skills/morning-briefing").mkdir(parents=True)
    (ws / ".claude/skills/morning-briefing/SKILL.md").write_text("x", encoding="utf-8")
    assert sc.nudge_part(ws, "startup", early) == "say brief me"
    assert sc.nudge_part(ws, "resume", early) is None
    assert sc.nudge_part(ws, "startup", late) is None
    (ws / "nest.json").write_text(json.dumps({"morning_nudge": {"before": "soon"}}), encoding="utf-8")
    assert sc.nudge_part(ws, "startup", early) is None
    (ws / "nest.json").write_text("{}", encoding="utf-8")
    assert sc.nudge_part(ws, "startup", early) is None


def test_a_run_by_hand_with_stdin_left_open_does_not_hang(ws):
    import time
    proc = subprocess.Popen([sys.executable, str(SCRIPT)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    started = time.time()
    try:
        assert proc.wait(timeout=20) == 0
    finally:
        proc.kill()
        for stream in (proc.stdin, proc.stdout, proc.stderr):
            stream.close()
    assert time.time() - started < 15
