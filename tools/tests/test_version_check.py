"""Tests for version_check.py: the cards are read from the real catalogue, GitHub is a dictionary."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import version_check as vc


def test_every_card_in_the_real_catalogue_can_be_checked():
    cards = vc.parse_cards(vc.CATALOGUE.read_text(encoding="utf-8"))
    names = [c.name for c in cards]
    assert len(names) == len(set(names)) >= 9
    for card in cards:
        # a pinned card is compared by tag, every other card needs a reading date
        assert card.tag or card.read_on, card.name
        assert "/" in card.repo


def test_card_shapes():
    text = """## Appendix C

**alpha** · `alpha@alpha`, marketplace `someone/alpha#v1.2.0` (MIT). Read again on
2026-11-20.

**beta** · `beta@claude-plugins-official` (Anthropic). Runs: a skill. Read on 2026-11-19, and
Read again on 2026-11-21.

**gamma** · `gamma@gamma`, marketplace `someone/gamma` (MIT). Has no tags.
"""
    a, b, g = vc.parse_cards(text)
    assert (a.repo, a.tag, a.read_on, a.path) == ("someone/alpha", "v1.2.0", "2026-11-20", None)
    assert (b.repo, b.path, b.read_on) == (vc.OFFICIAL, "plugins/beta", "2026-11-21")
    assert (g.repo, g.tag, g.read_on) == ("someone/gamma", None, None)


def test_no_appendix_no_cards():
    assert vc.parse_cards("**alpha** · `alpha@alpha`, marketplace `a/b#1`") == []


@pytest.fixture
def github(monkeypatch):
    answers: dict[str, object] = {}

    def fake(path: str):
        for prefix, value in answers.items():
            if path.startswith(prefix):
                return value
        return None

    monkeypatch.setattr(vc, "api", fake)
    return answers


def card(**kw) -> vc.Card:
    base = dict(name="alpha", repo="someone/alpha", path=None, tag=None, read_on="2026-11-20")
    base.update(kw)
    return vc.Card(**base)


def test_newer_tag_is_reported(github):
    github["repos/someone/alpha/releases/latest"] = {"tag_name": "v1.10.0"}
    github["repos/someone/alpha/tags"] = [{"name": "v1.9.0"}, {"name": "v1.2.0"}]
    line = vc.check_card(card(tag="v1.2.0"))
    assert line and "`v1.10.0`" in line


def test_same_or_older_tag_is_quiet(github):
    github["repos/someone/alpha/releases/latest"] = {"tag_name": "v1.2.0"}
    github["repos/someone/alpha/tags"] = [{"name": "v1.1.0"}, {"name": "nightly"}]
    assert vc.check_card(card(tag="v1.2.0")) is None


def test_unreadable_tags_are_said(github):
    line = vc.check_card(card(tag="v1.2.0"))
    assert line and "could not read" in line


def test_commits_since_reading_are_reported(github):
    github["repos/someone/alpha/commits"] = [
        {"sha": "abcdef123", "commit": {"message": "Add a hook\n\nbody"}}]
    line = vc.check_card(card())
    assert line and "`abcdef1` Add a hook" in line and "since 2026-11-20" in line


def test_official_cards_look_at_their_folder(github, monkeypatch):
    seen = []
    monkeypatch.setattr(vc, "api", lambda path: seen.append(path) or [])
    assert vc.check_card(card(repo=vc.OFFICIAL, path="plugins/alpha")) is None
    assert "path=plugins/alpha" in seen[0]


def test_no_date_is_said(github):
    line = vc.check_card(card(read_on=None))
    assert line and "no \"Read again on\" date" in line


def test_report_empty_when_nothing_moved():
    assert vc.report([], []) == ""


def test_report_sections():
    text = vc.report(["- plugin x: 1 -> 2"], ["- **alpha**: moved"])
    assert "### Claude Code plugins" in text and "### Obsidian plugins" in text


def test_strict_exit(monkeypatch, capsys):
    monkeypatch.setattr(vc, "check_card", lambda c: None)
    monkeypatch.setattr(vc, "obsidian_lines", lambda: ["- plugin x: 1 -> 2"])
    assert vc.main(["--strict"]) == 1
    assert vc.main([]) == 0
    assert vc.main(["--strict", "--no-obsidian"]) == 0
    assert "plugin x" in capsys.readouterr().out
