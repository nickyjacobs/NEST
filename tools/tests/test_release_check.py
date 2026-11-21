"""Tests for release_check.py: the changelog template and the version numbers."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import release_check as rc

GOOD = """# Changelog

| Release | Date | In short |
|---|---|---|
| [1.1.0](#110---2026-02-01) | 2026-02-01 | A study skill. |
| [1.0.0](#100---2026-01-01) | 2026-01-01 | First release. |

## [Unreleased]

### ✨ Added

- Something new.

---

## [1.1.0] - 2026-02-01

> **In short:** A study skill.

### 🏠 For your workspace

- New: a study skill.

### ✨ Added

- `kit/skills/study/`.

### 🐛 Fixed

- A typo.

---

## [1.0.0] - 2026-01-01

> **In short:** First release.

### 🏠 For your workspace

- Nothing to do.

[Unreleased]: https://example.org/compare/v1.1.0...HEAD
[1.1.0]: https://example.org/releases/tag/v1.1.0
[1.0.0]: https://example.org/releases/tag/v1.0.0
"""


def problems(text: str) -> str:
    return "\n".join(rc.check_changelog(text))


def test_good_changelog_passes():
    assert rc.check_changelog(GOOD) == []
    assert rc.newest_version(GOOD) == "1.1.0"


def test_missing_divider():
    assert "must end with a `---` divider" in problems(GOOD.replace("- A typo.\n\n---\n", "- A typo.\n"))


def test_missing_in_short_and_workspace_section():
    text = GOOD.replace("> **In short:** A study skill.\n\n", "")
    assert "needs a `> **In short:** ...` line" in problems(text)
    text = GOOD.replace("### 🏠 For your workspace\n\n- New: a study skill.\n\n", "")
    assert "first section must be `### 🏠 For your workspace`" in problems(text)


def test_unknown_misordered_and_empty_sections():
    assert "is not one of" in problems(GOOD.replace("### 🐛 Fixed", "### Changed after the trial run"))
    assert "is not one of" in problems(GOOD.replace("### 🐛 Fixed", "### Fixed"))
    swapped = GOOD.replace("### ✨ Added\n\n- `kit/skills/study/`.", "### 🐛 Fixed\n\n- x").replace(
        "### 🐛 Fixed\n\n- A typo.", "### ✨ Added\n\n- y")
    assert "in the order" in problems(swapped)
    assert "is empty" in problems(GOOD.replace("- A typo.\n", ""))


def test_bad_heading_order_and_links():
    assert "YYYY-MM-DD" in problems(GOOD.replace("## [1.1.0] - 2026-02-01", "## [1.1.0] - Feb 2026"))
    flipped = GOOD.replace("[1.1.0] - 2026-02-01", "[0.9.0] - 2026-02-01")
    assert "newest first" in problems(flipped)
    assert "no link line for [1.0.0]" in problems(GOOD.replace("[1.0.0]: https://example.org/releases/tag/v1.0.0\n", ""))
    assert "must compare v1.1.0...HEAD" in problems(GOOD.replace("v1.1.0...HEAD", "v1.0.0...HEAD"))
    assert "first block must be" in problems(GOOD.replace("## [Unreleased]", "## Unreleased"))


def test_every_release_needs_a_row_in_the_table():
    assert "needs a row" in problems(GOOD.replace("| [1.1.0](#110---2026-02-01) | 2026-02-01 | A study skill. |\n", ""))


def test_em_dash_is_refused():
    assert "em dash" in problems(GOOD.replace("- A typo.", "- A typo — fixed."))


def test_notes_are_the_block_without_the_divider():
    body = rc.notes(GOOD, "1.1.0")
    assert body.startswith('<p align="center"><img src="https://example.org/raw/v1.1.0/assets/release-banner.png"')
    assert "> **In short:** A study skill." in body and "### 🐛 Fixed" in body
    assert "## [1.0.0]" not in body and body.count("\n---\n") == 5 and "/nest-update" in body
    assert rc.notes(GOOD, "9.9.9") is None


def write_repo(root: Path, badge: str = "1.1.0", header: str = "1.1.0", state: str = "1.1.0") -> None:
    (root / "CHANGELOG.md").write_text(GOOD, encoding="utf-8")
    (root / "README.md").write_text(
        f'<img src="https://img.shields.io/badge/NEST_v{badge}-3fb950" alt="NEST v{badge}">\n', encoding="utf-8")
    (root / "SETUP.md").write_text(f"# NEST\n\nVersion {header} · Toolkit\n\n```\nnest_version: {state}\n```\n",
                                   encoding="utf-8")


def test_versions_must_agree(tmp_path, capsys):
    write_repo(tmp_path)
    assert rc.main(["--root", str(tmp_path)]) == 0
    assert rc.main(["--root", str(tmp_path), "--tag", "v1.1.0"]) == 0
    assert rc.main(["--root", str(tmp_path), "--tag", "v1.2.0"]) == 1
    write_repo(tmp_path, state="1.0.0")
    assert rc.main(["--root", str(tmp_path)]) == 1
    assert "STATE template" in capsys.readouterr().err
    write_repo(tmp_path, badge="1.0.0")
    assert rc.main(["--root", str(tmp_path)]) == 1


def test_the_real_repository_passes():
    assert rc.main([]) == 0
