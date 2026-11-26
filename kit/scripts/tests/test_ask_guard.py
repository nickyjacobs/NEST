"""Tests for ask_guard.py: what the user must judge has to be inside the dialog."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ask_guard as guard

SCRIPT = Path(guard.__file__)


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "_setup").mkdir()
    (tmp_path / "_setup" / "STATE.md").write_text(
        "# Setup state\nnext: interview, block C\nlanguage: Dutch\n", encoding="utf-8"
    )
    return tmp_path


def ask(*questions: dict) -> dict:
    return {"hook_event_name": "PreToolUse", "tool_name": "AskUserQuestion",
            "tool_input": {"questions": list(questions)}}


def q(text: str, preview: str | None = None) -> dict:
    first = {"label": "Ja, dit klopt", "description": "Zo bouwen."}
    if preview is not None:
        first["preview"] = preview
    return {"question": text, "header": "Voorstel", "multiSelect": False,
            "options": [first, {"label": "Ik wil iets aanpassen", "description": "Eerst iets anders."}]}


@pytest.mark.parametrize("text", [
    "Kloppen deze twaalf mappen voor je notities?",
    "Klopt deze samenvatting van wie je bent?",
    "Is this summary right?",
    "Do these folders fit how you work?",
    "Stimmt diese Zusammenfassung?",
    "Est-ce correct ?",
    "¿Es correcto este resumen?",
    "Is this folder layout right?",
    "Is the summary correct?",
    "Is dit de goede indeling?",
    "Akkoord met de mappen?",
    "Passt diese Struktur?",
    "¿Te parece bien?",
])
def test_judge_question_without_content_is_refused_once(ws, text):
    reason = guard.decide(ask(q(text)), ws)
    assert reason and "preview" in reason
    # the same question again passes: a misread costs one retry, never a loop
    assert guard.decide(ask(q(text)), ws) is None
    # and only that retry: the same wording later in the setup is checked again
    assert guard.decide(ask(q(text)), ws)


def test_recaps_with_the_same_wording_are_each_checked(ws):
    for _ in range(3):
        assert guard.decide(ask(q("Klopt deze samenvatting?")), ws)
        assert guard.decide(ask(q("Klopt deze samenvatting?")), ws) is None


def test_preview_passes(ws):
    assert guard.decide(ask(q("Kloppen deze mappen?", preview="00-inbox\n10-studie")), ws) is None


def test_blank_preview_does_not_count(ws):
    assert guard.decide(ask(q("Kloppen deze mappen?", preview="   ")), ws)


def test_a_fixed_retry_clears_the_refusal(ws):
    # refused, then asked again with the content in the preview (what the model does) ...
    assert guard.decide(ask(q("Klopt deze samenvatting?")), ws)
    assert guard.decide(ask(q("Klopt deze samenvatting?", preview="Shannon, 21, studeert")), ws) is None
    # ... so the next recap with the same words and no content is refused again
    assert guard.decide(ask(q("Klopt deze samenvatting?")), ws)


def test_two_refused_one_retried(ws):
    a, b = q("Klopt deze samenvatting?"), q("Kloppen deze mappen?")
    assert guard.decide(ask(a, b), ws)
    assert guard.decide(ask(q("Klopt deze samenvatting?", preview="x"), q("Kloppen deze mappen?", preview="y")), ws) is None
    data = json.loads((ws / "_setup" / ".ask_guard.json").read_text(encoding="utf-8"))
    assert data["refused_once"] == []


def test_blank_lines_are_not_content(ws):
    assert guard.decide(ask(q("Hier is het:\n\n\nKlopt dit?")), ws)


def test_content_in_question_text_passes(ws):
    text = "Kloppen deze mappen?\n00-inbox\n10-studie\n20-projecten"
    assert guard.decide(ask(q(text)), ws) is None


def test_plain_choice_passes(ws):
    assert guard.decide(ask(q("Waar typ je dit nu?")), ws) is None


def test_preview_on_any_option_passes(ws):
    question = q("Kloppen deze mappen?")
    question["options"][1]["preview"] = "00-inbox"
    assert guard.decide(ask(question), ws) is None


def test_one_flagged_question_among_several(ws):
    reason = guard.decide(ask(q("Welke kleur?"), q("Klopt dit overzicht?")), ws)
    assert reason


def test_not_during_setup_without_state(tmp_path):
    assert guard.decide(ask(q("Kloppen deze mappen?")), tmp_path) is None


@pytest.mark.parametrize("line", ["next: done", "next: `done`", "next:   DONE  "])
def test_not_after_setup_is_done(ws, line):
    (ws / "_setup" / "STATE.md").write_text(f"{line}\n", encoding="utf-8")
    assert guard.decide(ask(q("Kloppen deze mappen?")), ws) is None


def test_state_without_next_line_counts_as_running(ws):
    (ws / "_setup" / "STATE.md").write_text("language: Dutch\n", encoding="utf-8")
    assert guard.decide(ask(q("Kloppen deze mappen?")), ws)


def test_other_tools_pass(ws):
    data = ask(q("Kloppen deze mappen?"))
    data["tool_name"] = "Bash"
    assert guard.decide(data, ws) is None


@pytest.mark.parametrize("tool_input", [None, {}, {"questions": None}, {"questions": ["x", 3]},
                                        {"questions": [{"options": "nope"}]}])
def test_odd_input_passes(ws, tool_input):
    data = {"tool_name": "AskUserQuestion", "tool_input": tool_input}
    assert guard.decide(data, ws) is None


def test_broken_state_file_is_ignored(ws):
    (ws / "_setup" / ".ask_guard.json").write_text("{not json", encoding="utf-8")
    assert guard.decide(ask(q("Kloppen deze mappen?")), ws)
    data = json.loads((ws / "_setup" / ".ask_guard.json").read_text(encoding="utf-8"))
    assert len(data["refused_once"]) == 1


def test_seen_list_is_capped(ws):  # questions refused and never asked again
    for i in range(250):
        guard.decide(ask(q(f"Kloppen deze {i} mappen?")), ws)
    data = json.loads((ws / "_setup" / ".ask_guard.json").read_text(encoding="utf-8"))
    assert len(data["refused_once"]) == 200


def run_hook(ws: Path, data: dict | str | bytes, **env_extra: str) -> subprocess.CompletedProcess:
    raw = data if isinstance(data, (str, bytes)) else json.dumps(data, ensure_ascii=False)
    raw = raw if isinstance(raw, bytes) else raw.encode("utf-8")
    env = {"CLAUDE_PROJECT_DIR": str(ws), "PATH": "", "SYSTEMROOT": "", **env_extra}
    out = subprocess.run([sys.executable, str(SCRIPT)], input=raw, capture_output=True,
                         env=env, timeout=30)
    return subprocess.CompletedProcess(out.args, out.returncode,
                                       out.stdout.decode("utf-8"), out.stderr.decode("utf-8"))


def test_hook_reads_utf8_whatever_the_code_page(ws):
    # Windows reads text in its own code page; the hook must read bytes (hooks-notes.md)
    data = ask(q("Est-ce que ce résumé te convient ? ”"))
    out = run_hook(ws, data, PYTHONIOENCODING="cp1252", PYTHONUTF8="0")
    assert json.loads(out.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_hook_prints_deny(ws):
    out = run_hook(ws, ask(q("Kloppen deze mappen?")))
    assert out.returncode == 0
    decision = json.loads(out.stdout)["hookSpecificOutput"]
    assert decision["hookEventName"] == "PreToolUse"
    assert decision["permissionDecision"] == "deny"
    assert "preview" in decision["permissionDecisionReason"]


def test_hook_silent_when_fine(ws):
    out = run_hook(ws, ask(q("Kloppen deze mappen?", preview="00-inbox")))
    assert out.returncode == 0 and out.stdout == ""


@pytest.mark.parametrize("raw", ["", "not json", "[1, 2]", "null"])
def test_hook_never_blocks_on_bad_input(ws, raw):
    out = run_hook(ws, raw)
    assert out.returncode == 0 and out.stdout == ""
