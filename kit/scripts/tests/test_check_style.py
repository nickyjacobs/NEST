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


# Any language, odd entries, and a check that cannot run

def hits(text: str, words: str) -> list[str]:
    return [issue for _, issue, _ in check_style.check_text(text, check_style.parse_words(words))]


def test_entries_match_in_scripts_without_spaces():
    words = "[banned]\n重要\nสำคัญ\nявляется\n[options]\nem_dash = false\n"
    assert hits("これは重要なことです。", words) == ["word '重要'"]
    assert hits("นี่เป็นเรื่องสำคัญมาก", words) == ["word 'สำคัญ'"]
    assert hits("Это является важным, но неявляется нет.", words) == ["word 'является'"]  # boundaries kept


def test_a_bracketed_entry_is_an_entry_not_a_section():
    words = "[banned]\n[sic]\ncrucial\nc#\n"
    found = hits("It is crucial [sic] to learn c# first.", words)
    assert sorted(found) == ["word '[sic]'", "word 'c#'", "word 'crucial'"]


def test_typographic_apostrophe_matches_a_plain_one():
    words = "[banned]\ndon't worry\n[openers]\nin today's world\n"
    assert len(hits("In today’s world you don’t worry.", words)) == 2


def test_frontmatter_is_skipped_behind_a_bom(words, tmp_path, capsys):
    f = tmp_path / "bom.md"
    f.write_bytes(b"\xef\xbb\xbf---\ntitle: delve\n---\nPlain body.\n")
    assert check_style.main(["--words", str(words), "--strict", str(f)]) == 0
    words.write_bytes(b"\xef\xbb\xbf" + words.read_bytes())
    assert check_style.main(["--words", str(words), "--strict", "--text", "We delve."]) == 1


def test_stdin_is_read_as_utf8_whatever_the_console_says(words, monkeypatch, capsys):
    raw = io.BytesIO("A dash — here.".encode())
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(raw, encoding="cp1252"))
    assert check_style.main(["--words", str(words), "--strict", "-"]) == 1
    assert "em dash" in capsys.readouterr().out


def test_strict_fails_when_the_check_could_not_run(words, tmp_path, capsys):
    assert check_style.main(["--words", str(words), "--strict", str(tmp_path / "missing.md")]) == 2
    assert check_style.main(["--words", str(words), str(tmp_path / "missing.md")]) == 0  # advisory stays advisory
    assert check_style.main(["--words", str(tmp_path / "no-list.txt"), "--strict", "--text", "We delve."]) == 2
    assert check_style.main(["--words", str(tmp_path / "no-list.txt"), "--text", "We delve."]) == 0
