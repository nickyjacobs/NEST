"""Tests for blind_seat_guard.py: a blind seat reads its own run file and nothing else."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import blind_seat_guard as guard

SCRIPT = Path(guard.__file__)


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    run = tmp_path / ".runs" / "council" / "20260108-1430-idea"
    run.mkdir(parents=True)
    for name in ("outsider.md", "believer.md", "verifier.md"):
        (run / name).write_text("run file\n", encoding="utf-8")
    (tmp_path / "CLAUDE.local.md").write_text("private\n", encoding="utf-8")
    return tmp_path


def call(ws: Path, agent: str | None, tool: str, **tool_input) -> dict:
    data = {"hook_event_name": "PreToolUse", "cwd": str(ws), "tool_name": tool, "tool_input": tool_input}
    if agent:
        data["agent_type"] = agent
    return data


def run_file(ws: Path, name: str) -> str:
    return str(ws / ".runs" / "council" / "20260108-1430-idea" / name)


def test_own_run_file_passes(ws):
    assert guard.check(call(ws, "council-outsider", "Read", file_path=run_file(ws, "outsider.md"))) is None


def test_another_seats_run_file_is_refused(ws):
    reason = guard.check(call(ws, "council-outsider", "Read", file_path=run_file(ws, "believer.md")))
    assert reason and "believer.md" in reason


def test_file_outside_the_run_folder_is_refused(ws):
    assert guard.check(call(ws, "council-outsider", "Read", file_path=str(ws / "CLAUDE.local.md")))


def test_same_name_outside_the_run_folder_is_refused(ws):
    (ws / "outsider.md").write_text("not a run file\n", encoding="utf-8")
    assert guard.check(call(ws, "council-outsider", "Read", file_path=str(ws / "outsider.md")))


def test_path_that_climbs_out_is_refused(ws):
    sneaky = str(ws / ".runs" / ".." / "outsider.md")
    (ws / "outsider.md").write_text("x\n", encoding="utf-8")
    assert guard.check(call(ws, "council-outsider", "Read", file_path=sneaky))


@pytest.mark.parametrize("tool", ["Grep", "Glob"])
def test_search_tools_are_refused(ws, tool):
    assert guard.check(call(ws, "architect-dreamer", tool, pattern="*", path=str(ws)))


@pytest.mark.parametrize("agent", [None, "council-believer", "security-reviewer"])
def test_other_agents_are_left_alone(ws, agent):
    assert guard.check(call(ws, agent, "Read", file_path=str(ws / "CLAUDE.local.md"))) is None
    assert guard.check(call(ws, agent, "Grep", pattern="x")) is None


def test_windows_separators(ws):
    path = run_file(ws, "verifier.md").replace("/", "\\") if sys.platform == "win32" else run_file(ws, "verifier.md")
    assert guard.check(call(ws, "council-verifier", "Read", file_path=path)) is None


def test_seat_argument_when_input_has_no_agent_type(ws):
    data = call(ws, None, "Read", file_path=str(ws / "CLAUDE.local.md"))
    assert guard.check(data, "council-outsider")


def test_config_replaces_table_and_run_dir(ws):
    (ws / "nest.json").write_text(json.dumps({"blind_seats": {"run_dir": "work", "seats": {"my-seat": ["seat.md"]}}}),
                                  encoding="utf-8")
    (ws / "work").mkdir()
    (ws / "work" / "seat.md").write_text("x\n", encoding="utf-8")
    assert guard.check(call(ws, "my-seat", "Read", file_path=str(ws / "work" / "seat.md"))) is None
    assert guard.check(call(ws, "my-seat", "Read", file_path=run_file(ws, "outsider.md")))
    assert guard.check(call(ws, "council-outsider", "Read", file_path=str(ws / "CLAUDE.local.md"))) is None


def test_cli_exit_codes(ws):
    def run(data: dict) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(SCRIPT)], input=json.dumps(data), capture_output=True,
                              text=True, encoding="utf-8", check=False)

    ok = run(call(ws, "council-outsider", "Read", file_path=run_file(ws, "outsider.md")))
    assert ok.returncode == 0
    blocked = run(call(ws, "council-outsider", "Read", file_path=str(ws / "CLAUDE.local.md")))
    assert blocked.returncode == 2 and "run file" in blocked.stderr
    bad = subprocess.run([sys.executable, str(SCRIPT)], input="{not json", capture_output=True, text=True,
                         encoding="utf-8", check=False)
    assert bad.returncode == 2


# --- findings from the hooks audit -----------------------------------------------------------

@pytest.mark.parametrize("agent", ["Council-Outsider", "COUNCIL-OUTSIDER", " council-outsider "])
def test_seat_names_match_without_regard_to_case(ws, agent):
    assert guard.check(call(ws, agent, "Read", file_path=str(ws / "CLAUDE.local.md")))
    assert guard.check(call(ws, agent, "Read", file_path=run_file(ws, "outsider.md"))) is None


@pytest.mark.parametrize("agent", ["general-purpose", "outsider", "the-renamed-seat", None])
def test_seat_argument_wins_over_the_reported_agent_type(ws, agent):
    data = call(ws, agent, "Read", file_path=str(ws / "CLAUDE.local.md"))
    assert guard.check(data, "council-outsider")
    assert guard.check(data, "Council-Outsider")
    assert guard.check(call(ws, agent, "Read", file_path=run_file(ws, "outsider.md")), "council-outsider") is None


def test_config_seat_names_match_without_regard_to_case(ws):
    (ws / "nest.json").write_text(json.dumps({"blind_seats": {"seats": {"My-Seat": ["seat.md"]}}}), encoding="utf-8")
    assert guard.check(call(ws, "my-seat", "Read", file_path=str(ws / "CLAUDE.local.md")))


def test_path_with_an_accent_survives_a_console_code_page(tmp_path, monkeypatch):
    import os
    root = tmp_path / "werk-Jos\u00e9"
    (root / ".runs" / "r").mkdir(parents=True)
    target = root / ".runs" / "r" / "outsider.md"
    target.write_text("idea\n", encoding="utf-8")
    payload = json.dumps({"agent_type": "council-outsider", "tool_name": "Read", "tool_input": {"file_path": str(target)}},
                         ensure_ascii=False).encode("utf-8")
    result = subprocess.run([sys.executable, str(SCRIPT)], input=payload, capture_output=True, check=False,
                            env={**os.environ, "CLAUDE_PROJECT_DIR": str(root), "PYTHONIOENCODING": "cp1252",
                                 "PYTHONUTF8": "0"})
    assert result.returncode == 0, result.stderr


def test_cli_takes_the_seat_from_the_argument(ws):
    data = json.dumps(call(ws, "general-purpose", "Read", file_path=str(ws / "CLAUDE.local.md")))
    result = subprocess.run([sys.executable, str(SCRIPT), "--seat", "council-outsider"], input=data, capture_output=True,
                            text=True, encoding="utf-8", check=False)
    assert result.returncode == 2 and "run file" in result.stderr


def test_nest_json_with_a_byte_order_mark_is_read(ws):
    raw = json.dumps({"blind_seats": {"seats": {"my-seat": ["seat.md"]}}}).encode("utf-8")
    (ws / "nest.json").write_bytes(b"\xef\xbb\xbf" + raw)
    assert guard.check(call(ws, "my-seat", "Read", file_path=str(ws / "CLAUDE.local.md")))


# --- what the review of the guards found -----------------------------------------------------

def test_link_named_after_the_seat_that_leads_to_another_report_is_refused(ws):
    import os
    first = ws / ".runs" / "r1"
    second = ws / ".runs" / "r2"
    first.mkdir(parents=True, exist_ok=True)
    second.mkdir(parents=True, exist_ok=True)
    (first / "skeptic.md").write_text("another seat's report\n", encoding="utf-8")
    link = second / "outsider.md"
    try:
        os.symlink(first / "skeptic.md", link)
    except (OSError, NotImplementedError):
        pytest.skip("no symlinks here")
    assert guard.check(call(ws, "council-outsider", "Read", file_path=str(link)))


def test_seat_argument_that_is_not_in_the_table_is_refused(ws):
    data = call(ws, "general-purpose", "Read", file_path=run_file(ws, "outsider.md"))
    reason = guard.check(data, "council-outsidr")
    assert reason and "not a blind seat" in reason
    assert guard.check(call(ws, "council-outsidr", "Read", file_path=str(ws / "CLAUDE.local.md"))) is None
