"""Tests for check_style.py: word list sections, text and stdin input, strict exit codes."""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import check_style

WORDS = """[banned]
delve
leverage
[connectors]
moreover
[openers]
I hope this email finds you well
[options]
connector_max = 2
"""


@pytest.fixture
def words(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    p = tmp_path / "words.txt"
    p.write_text(WORDS, encoding="utf-8")
    return p


def test_text_option_reports_hits(words, capsys):
    rc = check_style.main(["--words", str(words), "--strict", "--text", "Let us delve into it and leverage this."])
    out = capsys.readouterr().out
    assert rc == 1
    assert "delve" in out and "leverage" in out


def test_text_option_clean_text(words, capsys):
    assert check_style.main(["--words", str(words), "--strict", "--text", "Short and plain."]) == 0


def test_stdin(words, capsys, monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO("I hope this email finds you well. Thanks."))
    assert check_style.main(["--words", str(words), "--strict", "-"]) == 1
    assert "stdin" in capsys.readouterr().out


def test_file_and_advisory_exit(words, tmp_path, capsys):
    f = tmp_path / "note.md"
    f.write_text("---\ntitle: delve\n---\nMoreover this. Moreover that. Moreover again.\n", encoding="utf-8")
    assert check_style.main(["--words", str(words), str(f)]) == 0  # advisory without --strict
    out = capsys.readouterr().out
    assert "moreover" in out.lower()
    assert "title" not in out  # frontmatter is skipped
