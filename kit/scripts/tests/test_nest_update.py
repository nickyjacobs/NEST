"""Tests for nest_update.py: a fake NEST repo with two releases and a workspace built from the first."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import nest_update as nu

CHANGELOG_110 = """# Changelog

## [Unreleased]

---

## [1.1.0] - 2026-02-01

> **In short:** A study skill and a sturdier wiki check.

### 🏠 For your workspace

- The wiki check now catches empty links.
- New: a study skill you can add.

### ✨ Added

- `kit/skills/study/`.

---

## [1.0.0] - 2026-01-01

**In short:** First release.

### For your workspace

- Nothing to do.

[1.1.0]: https://example.org/compare/v1.0.0...v1.1.0
"""

V100 = {
    "SETUP.md": "# NEST setup prompt\n\nVersion 1.0.0 · New Environment Setup Toolkit\n",
    "CHANGELOG.md": "# Changelog\n\n## [1.0.0] - 2026-01-01\n\n**In short:** First release.\n",
    "kit/README.md": "kit readme\n",
    "kit/scripts/wiki.py": "print('wiki 1')\n",
    "kit/scripts/validate.py": "print('validate 1')\n",
    "kit/scripts/old_tool.py": "print('old')\n",
    "kit/scripts/tests/test_wiki.py": "def test(): pass\n",
    "kit/skills/inbox/SKILL.md": "---\nname: inbox\n---\n<!-- customise: language -->\nFile the inbox.\n",
    "kit/skills/mail/SKILL.md": "---\nname: mail\n---\nRead mail.\n",
    "kit/skills/idea/SKILL.md": "full idea\n",
    "kit/skills/idea/SKILL.light.md": "light idea\n",
    "kit/skills/idea/formats.md": "full formats\n",
    "kit/skills/idea/formats.light.md": "light formats\n",
    "kit/agents/full/council-judge.md": "full judge\n",
    "kit/agents/light/council-judge.md": "light judge\n",
    "kit/agents/security-reviewer.md": "reviewer\n",
    "kit/claude/rules/wiki.md": "wiki rule\n",
    "kit/wiki/_templates/note.md": "note template 1\n",
}
V110 = {
    "SETUP.md": "# NEST setup prompt\n\nVersion 1.1.0 · New Environment Setup Toolkit\n",
    "CHANGELOG.md": CHANGELOG_110,
    "kit/scripts/wiki.py": "print('wiki 2')\n",
    "kit/scripts/validate.py": "print('validate 2')\n",
    "kit/scripts/old_tool.py": None,
    "kit/scripts/guard.py": "print('guard')\n",
    "kit/skills/inbox/SKILL.md": "---\nname: inbox\n---\n<!-- customise: language -->\nFile the inbox, oldest first.\n",
    "kit/skills/inbox/reference.md": "inbox reference\n",
    "kit/skills/mail/SKILL.md": "---\nname: mail\n---\nRead mail, newest first.\n",
    "kit/skills/mail/rules.md": "mail rules\n",
    "kit/skills/study/SKILL.md": "---\nname: study\n---\nStudy.\n",
    "kit/agents/light/council-judge.md": "light judge, stricter\n",
    "kit/agents/full/council-judge.md": "full judge, stricter\n",
    "kit/wiki/_templates/note.md": "note template 2\n",
}


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.org", "-c", "commit.gpgsign=false",
                    "-c", "tag.gpgsign=false", *args], cwd=repo, check=True, capture_output=True)


def write_tree(folder: Path, tree: dict) -> None:
    for rel, text in tree.items():
        path = folder / rel
        if text is None:
            path.unlink()
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))


@pytest.fixture(scope="module")
def nest_repo(tmp_path_factory) -> Path:
    repo = tmp_path_factory.mktemp("nest-source")
    subprocess.run(["git", "init", "--quiet", "--initial-branch=main", str(repo)], check=True, capture_output=True)
    git(repo, "config", "core.autocrlf", "false")
    write_tree(repo, V100)
    git(repo, "add", "-A")
    git(repo, "commit", "--quiet", "-m", "Add: NEST 1.0.0")
    git(repo, "tag", "v1.0.0")
    write_tree(repo, V110)
    git(repo, "add", "-A")
    git(repo, "commit", "--quiet", "-m", "Release: v1.1.0")
    git(repo, "tag", "v1.1.0")
    git(repo, "tag", "not-a-version")
    return repo


@pytest.fixture
def ws(tmp_path, monkeypatch, nest_repo) -> Path:
    """A workspace built from release 1.0.0: light idea, the inbox skill, no mail."""
    root = tmp_path / "workspace"
    root.mkdir()
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(root))
    kit_copy = root / "_setup" / "nest"
    write_tree(kit_copy, {rel: text for rel, text in V100.items() if rel.startswith("kit/") or rel == "SETUP.md"})
    write_tree(root, {
        "scripts/wiki.py": V100["kit/scripts/wiki.py"],
        "scripts/validate.py": V100["kit/scripts/validate.py"],
        "scripts/old_tool.py": V100["kit/scripts/old_tool.py"],
        ".claude/skills/inbox/SKILL.md": "---\nname: inbox\n---\nRuim de inbox op.\n",
        ".claude/skills/idea/SKILL.md": "licht idee\n",
        ".claude/skills/idea/formats.light.md": V100["kit/skills/idea/formats.light.md"],
        ".claude/agents/council-judge.md": "lichte rechter\n",
        ".claude/agents/security-reviewer.md": V100["kit/agents/security-reviewer.md"],
        ".claude/rules/wiki.md": "wiki-regel\n",
        "wiki/index.md": "# Wiki\n",
        "CLAUDE.md": "# Mine\n",
        "nest.json": json.dumps({"wiki_backup": {"git_dir": "~/.x.git"}}),
    })
    assert run("stamp", "--source", str(nest_repo)) == 0
    return root


def run(*argv: str) -> int:
    return nu.main(list(argv))


def stamp(ws: Path) -> dict:
    return json.loads((ws / "nest.json").read_text(encoding="utf-8"))["nest"]


def plan(ws: Path) -> dict:
    return nu.current_plan(ws, nu.load_stamp(ws))


def status(ws: Path) -> dict[str, str]:
    return {item["path"] or item["kit"]: item["status"] for item in plan(ws)["items"]}


# --- the stamp -------------------------------------------------------------------------------

def test_stamp_records_version_source_and_kinds(ws, nest_repo):
    s = stamp(ws)
    assert s["version"] == "1.0.0" and s["source"] == str(nest_repo) and s["update_check"] is True
    files = s["files"]
    assert files["scripts/wiki.py"] == {"kit": "kit/scripts/wiki.py", "kind": "copy", "version": "1.0.0",
                                        "sha256": nu.sha(ws / "_setup/nest/kit/scripts/wiki.py")}
    assert files[".claude/skills/inbox/SKILL.md"]["kind"] == "adapted"
    assert files[".claude/rules/wiki.md"]["kit"] == "kit/claude/rules/wiki.md"
    assert "CLAUDE.md" not in files and "wiki/index.md" not in files


def test_stamp_keeps_other_keys_in_nest_json(ws):
    assert json.loads((ws / "nest.json").read_text(encoding="utf-8"))["wiki_backup"] == {"git_dir": "~/.x.git"}


def test_stamp_maps_the_light_size(ws):
    files = stamp(ws)["files"]
    assert files[".claude/skills/idea/SKILL.md"]["kit"] == "kit/skills/idea/SKILL.light.md"
    assert files[".claude/skills/idea/formats.light.md"]["kind"] == "copy"
    assert files[".claude/agents/council-judge.md"]["kit"] == "kit/agents/light/council-judge.md"
    assert files[".claude/agents/security-reviewer.md"]["kit"] == "kit/agents/security-reviewer.md"


def test_stamp_again_only_adds_what_is_new(ws):
    assert run("apply", "scripts/wiki.py") == 0
    updated = stamp(ws)["files"]["scripts/wiki.py"]
    write_tree(ws, {".claude/skills/mail/SKILL.md": V100["kit/skills/mail/SKILL.md"]})
    assert run("stamp", "--version", "1.0.0") == 0
    files = stamp(ws)["files"]
    assert files["scripts/wiki.py"] == updated
    assert files[".claude/skills/mail/SKILL.md"]["kind"] == "copy"
    assert status(ws)["scripts/wiki.py"] == "unchanged"


def test_stamp_with_an_explicit_map(ws):
    write_tree(ws, {".claude/skills/postvak/SKILL.md": "x\n"})
    assert run("stamp", "--map", ".claude/skills/postvak/SKILL.md=kit/skills/mail/SKILL.md") == 0
    assert stamp(ws)["files"][".claude/skills/postvak/SKILL.md"]["kit"] == "kit/skills/mail/SKILL.md"
    assert run("stamp", "--map", "../outside.md=kit/skills/mail/SKILL.md") == 1
    assert run("stamp", "--map", "CLAUDE.md=kit/nope.md") == 1


def test_stamp_without_kit_copy_needs_a_version(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    assert run("stamp") == 1
    (tmp_path / "_setup").mkdir()
    (tmp_path / "_setup" / "STATE.md").write_text("---\nnest_version: 1.0.0\n---\n", encoding="utf-8")
    assert run("stamp", "--source", str(tmp_path / "nowhere")) == 1
    assert not (tmp_path / "nest.json").exists()


def test_stamp_without_kit_copy_uses_the_release_itself(tmp_path, monkeypatch, nest_repo):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    write_tree(tmp_path, {"_setup/STATE.md": "---\nnest_version: 1.0.0\n---\n",
                          "scripts/wiki.py": V100["kit/scripts/wiki.py"],
                          ".claude/skills/inbox/SKILL.md": "mine\n"})
    assert run("stamp", "--source", str(nest_repo)) == 0
    files = stamp(tmp_path)["files"]
    assert files["scripts/wiki.py"]["kind"] == "copy" and files[".claude/skills/inbox/SKILL.md"]["kind"] == "adapted"
    found = status(tmp_path)
    assert found["scripts/wiki.py"] == "replace" and found[".claude/skills/inbox/SKILL.md"] == "merge"


def test_finish_refuses_an_empty_stamp(tmp_path, monkeypatch, nest_repo, capsys):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    (tmp_path / "nest.json").write_text(json.dumps({"nest": {"version": "1.0.0", "source": str(nest_repo)}}),
                                        encoding="utf-8")
    assert run("finish") == 1
    assert "records no files" in capsys.readouterr().err
    assert stamp(tmp_path)["version"] == "1.0.0"


def test_commands_need_a_stamp(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    assert run("plan") == 1
    assert "no NEST stamp" in capsys.readouterr().err


@pytest.mark.parametrize("bad", ["../x", "/etc/passwd", "C:/x", "a/../../b", ""])
def test_paths_cannot_leave_the_workspace(bad):
    with pytest.raises(nu.Problem):
        nu.safe_rel(bad)


def test_line_endings_do_not_change_the_hash(tmp_path):
    (tmp_path / "lf").write_bytes(b"a\nb\n")
    (tmp_path / "crlf").write_bytes(b"a\r\nb\r\n")
    assert nu.sha(tmp_path / "lf") == nu.sha(tmp_path / "crlf")


# --- looking for a release -------------------------------------------------------------------

def test_versions_come_from_tags_only(nest_repo):
    assert nu.remote_versions(str(nest_repo), 30) == [(1, 0, 0), (1, 1, 0)]


def test_check_says_what_is_available(ws, capsys):
    assert run("check") == 0
    assert "NEST 1.1.0 is available" in capsys.readouterr().out


def test_notice_line_and_its_switches(ws):
    assert nu.notice(ws).startswith("NEST 1.1.0 is available (this workspace is on 1.0.0)")
    data = json.loads((ws / "nest.json").read_text(encoding="utf-8"))
    data["nest"]["skipped_version"] = "1.1.0"
    (ws / "nest.json").write_text(json.dumps(data), encoding="utf-8")
    assert nu.notice(ws) == ""
    data["nest"].pop("skipped_version")
    data["nest"]["update_check"] = False
    (ws / "nest.json").write_text(json.dumps(data), encoding="utf-8")
    assert nu.notice(ws) == ""


def test_notice_uses_the_cache_and_survives_an_unreachable_source(ws):
    data = json.loads((ws / "nest.json").read_text(encoding="utf-8"))
    data["nest"]["source"] = str(ws / "nowhere")
    (ws / "nest.json").write_text(json.dumps(data), encoding="utf-8")
    assert nu.notice(ws) == ""
    cache = json.loads((ws / nu.CACHE_FILE).read_text(encoding="utf-8"))
    assert time.time() - cache["checked"] < 60
    cache["latest"] = "2.0.0"
    (ws / nu.CACHE_FILE).write_text(json.dumps(cache), encoding="utf-8")
    assert "NEST 2.0.0 is available" in nu.notice(ws)
    assert run("check", "--quiet") == 0


def test_quiet_check_without_a_stamp_is_silent(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    assert run("check", "--quiet") == 0
    assert capsys.readouterr().out == ""


# --- the plan --------------------------------------------------------------------------------

def test_plan_sorts_every_file(ws):
    (ws / "scripts/validate.py").write_text("print('validate 1')  # mine\n", encoding="utf-8")
    found = status(ws)
    assert found["scripts/wiki.py"] == "replace"
    assert found["scripts/validate.py"] == "merge"
    assert found[".claude/skills/inbox/SKILL.md"] == "merge"
    assert found[".claude/skills/idea/SKILL.md"] == "unchanged"
    assert found[".claude/agents/council-judge.md"] == "merge"
    assert found["scripts/old_tool.py"] == "removed"
    assert found[".claude/rules/wiki.md"] == "unchanged"
    assert found["scripts/guard.py"] == "new"
    assert found[".claude/skills/inbox/reference.md"] == "new"
    assert found[".claude/skills/study/SKILL.md"] == "new"
    assert found["kit/wiki/_templates/note.md"] == "wiki"


def test_plan_ignores_parts_the_user_never_installed(ws):
    kits = {item["kit"] for item in plan(ws)["items"]}
    assert not any(kit.startswith("kit/skills/mail/") for kit in kits)
    assert "kit/agents/full/council-judge.md" not in kits
    assert not any("tests" in kit or kit.endswith("README.md") for kit in kits)


def test_plan_reports_a_deleted_file(ws):
    (ws / "scripts/wiki.py").unlink()
    assert status(ws)["scripts/wiki.py"] == "missing"


def test_plan_carries_the_release_notes(ws):
    notes = plan(ws)["notes"]
    assert [n["version"] for n in notes] == ["1.1.0"]
    assert notes[0]["in_short"] == "A study skill and a sturdier wiki check."
    assert notes[0]["for_your_workspace"].startswith("- The wiki check now catches empty links.")
    assert "Added" not in notes[0]["for_your_workspace"] and "example.org/compare" not in notes[0]["body"]


def test_plan_command_as_json(ws, capsys):
    assert run("plan", "--json") == 0
    out = json.loads(capsys.readouterr().out)
    assert out["installed"] == "1.0.0" and out["latest"] == "1.1.0" and out["up_to_date"] is False
    assert out["run"].startswith("nest-update-")
    assert run("plan") == 0
    assert "safe to replace" in capsys.readouterr().out


def test_plan_without_a_tag_falls_back_to_the_kit_copy(ws):
    data = json.loads((ws / "nest.json").read_text(encoding="utf-8"))
    data["nest"]["version"] = "0.9.0"
    (ws / "nest.json").write_text(json.dumps(data), encoding="utf-8")
    result = plan(ws)
    assert "no tag" in result["note"]
    found = {item["path"] or item["kit"]: item["status"] for item in result["items"]}
    assert found["scripts/wiki.py"] == "replace" and found[".claude/skills/study/SKILL.md"] == "new"


def test_diff_shows_what_nest_changed(ws, capsys):
    assert run("diff", "kit/scripts/wiki.py") == 0
    out = capsys.readouterr().out
    assert "-print('wiki 1')" in out and "+print('wiki 2')" in out


# --- changing the workspace ------------------------------------------------------------------

def test_apply_replaces_an_untouched_copy_and_keeps_the_old_one(ws):
    assert run("apply", "scripts/wiki.py") == 0
    assert (ws / "scripts/wiki.py").read_text(encoding="utf-8") == V110["kit/scripts/wiki.py"]
    kept = list((ws / nu.HISTORY_DIR).glob("nest-update-*/files/scripts/wiki.py"))
    assert len(kept) == 1 and kept[0].read_text(encoding="utf-8") == V100["kit/scripts/wiki.py"]
    assert status(ws)["scripts/wiki.py"] == "unchanged"


def test_apply_refuses_what_the_user_changed(ws, capsys):
    (ws / "scripts/validate.py").write_text("mine\n", encoding="utf-8")
    assert run("apply", "scripts/validate.py") == 1
    assert "needs a merge" in capsys.readouterr().err
    assert (ws / "scripts/validate.py").read_text(encoding="utf-8") == "mine\n"
    assert run("apply", ".claude/skills/inbox/SKILL.md") == 1
    assert run("apply", "CLAUDE.md") == 1
    assert (ws / "CLAUDE.md").read_text(encoding="utf-8") == "# Mine\n"


def test_apply_adds_a_new_copy_file_but_never_overwrites(ws):
    assert run("apply", "--new", "kit/scripts/guard.py=scripts/guard.py") == 0
    assert stamp(ws)["files"]["scripts/guard.py"]["kind"] == "copy"
    assert run("apply", "--new", "kit/scripts/guard.py=CLAUDE.md") == 1
    assert run("apply", "--new", "kit/scripts/guard.py=../guard.py") == 1


def test_mark_needs_a_backup_first(ws, capsys):
    assert run("mark", ".claude/skills/inbox/SKILL.md=kit/skills/inbox/SKILL.md") == 1
    assert "was not backed up" in capsys.readouterr().err


def test_mark_after_a_merge(ws):
    assert run("backup", ".claude/skills/inbox/SKILL.md") == 0
    (ws / ".claude/skills/inbox/SKILL.md").write_text("---\nname: inbox\n---\nRuim de inbox op, oudste eerst.\n",
                                                      encoding="utf-8")
    assert run("mark", ".claude/skills/inbox/SKILL.md=kit/skills/inbox/SKILL.md") == 0
    entry = stamp(ws)["files"][".claude/skills/inbox/SKILL.md"]
    assert entry["kind"] == "adapted" and status(ws)[".claude/skills/inbox/SKILL.md"] == "unchanged"


def test_decline_is_remembered_until_nest_changes_the_file_again(ws):
    assert run("decline", "kit/skills/study") == 0
    assert status(ws)[".claude/skills/study/SKILL.md"] == "declined"
    assert run("decline", "scripts/old_tool.py") == 0
    assert status(ws)["scripts/old_tool.py"] == "declined"
    assert run("decline", "kit/skills/nothing") == 1
    data = json.loads((ws / "nest.json").read_text(encoding="utf-8"))
    data["nest"]["declined"]["kit/skills/study/SKILL.md"] = "an older hash"
    (ws / "nest.json").write_text(json.dumps(data), encoding="utf-8")
    assert status(ws)[".claude/skills/study/SKILL.md"] == "new"


def test_finish_sets_the_version_only_when_nothing_is_open(ws, capsys):
    assert run("finish") == 0
    assert "still open" in capsys.readouterr().out and stamp(ws)["version"] == "1.0.0"
    assert run("apply", "scripts/wiki.py", "scripts/validate.py", "--new", "kit/scripts/guard.py=scripts/guard.py") == 0
    for path, kit in ((".claude/skills/inbox/SKILL.md", "kit/skills/inbox/SKILL.md"),
                      (".claude/agents/council-judge.md", "kit/agents/light/council-judge.md")):
        assert run("backup", path) == 0
        assert run("mark", f"{path}={kit}") == 0
    assert run("decline", "kit/skills/study", "kit/skills/inbox/reference.md") == 0
    assert run("retire", "scripts/old_tool.py") == 0
    assert not (ws / "scripts/old_tool.py").exists() and "scripts/old_tool.py" not in stamp(ws)["files"]
    assert run("done", "kit/wiki/_templates/note.md") == 0
    assert run("finish") == 0
    assert stamp(ws)["version"] == "1.1.0"
    assert run("check") == 0
    assert "Up to date" in capsys.readouterr().out
    assert nu.notice(ws, max_age_days=0) == ""
    assert run("plan") == 0
    assert "Up to date" in capsys.readouterr().out


def test_finish_skip_silences_the_notice(ws):
    assert run("finish", "--skip") == 0
    assert stamp(ws)["skipped_version"] == "1.1.0" and stamp(ws)["version"] == "1.0.0"
    assert nu.notice(ws) == ""


def test_restore_puts_everything_back(ws, capsys):
    before = (ws / "nest.json").read_text(encoding="utf-8")
    assert run("plan", "--json") == 0
    assert run("apply", "scripts/wiki.py", "--new", "kit/scripts/guard.py=scripts/guard.py") == 0
    assert run("backup", ".claude/skills/inbox/SKILL.md") == 0
    (ws / ".claude/skills/inbox/SKILL.md").write_text("broken\n", encoding="utf-8")
    assert run("backup", ".claude/skills/study/SKILL.md") == 0
    write_tree(ws, {".claude/skills/study/SKILL.md": "studie\n"})
    assert run("mark", ".claude/skills/study/SKILL.md=kit/skills/study/SKILL.md") == 0
    capsys.readouterr()
    assert run("restore") == 0
    assert "Put back 2 file(s)" in capsys.readouterr().out
    assert (ws / "scripts/wiki.py").read_text(encoding="utf-8") == V100["kit/scripts/wiki.py"]
    assert (ws / ".claude/skills/inbox/SKILL.md").read_text(encoding="utf-8").endswith("Ruim de inbox op.\n")
    assert not (ws / "scripts/guard.py").exists() and not (ws / ".claude/skills/study/SKILL.md").exists()
    assert list((ws / nu.HISTORY_DIR).glob("nest-update-*/created/scripts/guard.py"))
    assert json.loads((ws / "nest.json").read_text(encoding="utf-8")) == json.loads(before)
    assert run("restore") == 1


def test_one_update_is_one_history_folder_until_it_is_closed(ws, capsys):
    assert run("plan", "--json") == 0
    first = json.loads(capsys.readouterr().out)["run"]
    assert run("apply", "scripts/wiki.py") == 0
    capsys.readouterr()
    assert run("plan", "--json") == 0
    assert json.loads(capsys.readouterr().out)["run"] == first
    assert run("backup", "docs/skills.md") == 0
    write_tree(ws, {"docs/skills.md": "generated\n"})
    assert run("finish") == 0
    assert len(list((ws / nu.HISTORY_DIR).glob("nest-update-*"))) == 1
    assert run("restore") == 0
    assert not (ws / "docs/skills.md").exists()
    assert (ws / "scripts/wiki.py").read_text(encoding="utf-8") == V100["kit/scripts/wiki.py"]


def test_restore_without_an_update(ws):
    assert run("restore") == 1


def test_user_files_are_never_in_the_plan(ws):
    paths = {item["path"] for item in plan(ws)["items"]}
    assert "CLAUDE.md" not in paths and "nest.json" not in paths and "wiki/index.md" not in paths


def test_cli_runs_as_a_script(ws):
    out = subprocess.run([sys.executable, str(Path(nu.__file__)), "check"], capture_output=True, text=True,
                         encoding="utf-8", check=False, cwd=ws)
    assert out.returncode == 0 and "NEST 1.1.0 is available" in out.stdout
    assert shutil.which("git")


# --- what a review found: an update never costs the user their own work ----------------------

def finished_update(ws: Path) -> None:
    """Replace wiki.py, add guard.py, close the update."""
    assert run("plan", "--json") == 0
    assert run("apply", "scripts/wiki.py", "--new", "kit/scripts/guard.py=scripts/guard.py") == 0
    assert run("finish") == 0


def test_restore_leaves_what_the_user_changed_after_the_update(ws, capsys):
    finished_update(ws)
    (ws / "scripts/wiki.py").write_text("print('wiki 2')  # my own fix\n", encoding="utf-8")
    (ws / "scripts/guard.py").write_text("print('guard')  # mine now\n", encoding="utf-8")
    data = json.loads((ws / "nest.json").read_text(encoding="utf-8"))
    data["size_ceiling"] = {"lines": 250}
    data["nest"]["update_check"] = False
    (ws / "nest.json").write_text(json.dumps(data), encoding="utf-8")
    capsys.readouterr()
    assert run("restore") == 0
    out = capsys.readouterr().out
    assert "Left alone" in out and "scripts/wiki.py" in out and "scripts/guard.py" in out
    assert "my own fix" in (ws / "scripts/wiki.py").read_text(encoding="utf-8")
    assert (ws / "scripts/guard.py").is_file()
    after = json.loads((ws / "nest.json").read_text(encoding="utf-8"))
    assert after["size_ceiling"] == {"lines": 250} and after["wiki_backup"] == {"git_dir": "~/.x.git"}
    assert after["nest"]["update_check"] is False
    assert after["nest"]["files"]["scripts/wiki.py"]["sha256"] == nu.sha(ws / ".claude/.nest-update/1.1.0/kit/scripts/wiki.py")


def test_restore_force_keeps_todays_version_aside(ws):
    finished_update(ws)
    (ws / "scripts/wiki.py").write_text("my own version\n", encoding="utf-8")
    assert run("restore", "--force") == 0
    assert (ws / "scripts/wiki.py").read_text(encoding="utf-8") == V100["kit/scripts/wiki.py"]
    aside = list((ws / nu.HISTORY_DIR).glob("nest-update-*/undone/scripts/wiki.py"))
    assert len(aside) == 1 and aside[0].read_text(encoding="utf-8") == "my own version\n"


def test_restore_of_a_finished_update_still_works_right_after(ws):
    finished_update(ws)
    assert run("restore") == 0
    assert (ws / "scripts/wiki.py").read_text(encoding="utf-8") == V100["kit/scripts/wiki.py"]
    assert not (ws / "scripts/guard.py").exists() and stamp(ws)["version"] == "1.0.0"


def test_a_file_of_the_users_own_at_a_new_files_place_is_never_taken_away(ws, capsys):
    write_tree(ws, {".claude/skills/inbox/reference.md": "my own reference\n"})
    item = next(i for i in plan(ws)["items"] if i["kit"] == "kit/skills/inbox/reference.md")
    assert item["status"] == "new" and item["exists"] is True
    assert run("apply", "--new", "kit/skills/inbox/reference.md=.claude/skills/inbox/reference.md") == 1
    assert run("mark", ".claude/skills/inbox/reference.md=kit/skills/inbox/reference.md") == 1
    assert run("backup", ".claude/skills/inbox/reference.md") == 0
    (ws / ".claude/skills/inbox/reference.md").write_text("my own reference, merged\n", encoding="utf-8")
    assert run("mark", ".claude/skills/inbox/reference.md=kit/skills/inbox/reference.md") == 0
    assert run("restore") == 0
    assert (ws / ".claude/skills/inbox/reference.md").read_text(encoding="utf-8") == "my own reference\n"


def test_backup_says_what_it_really_did(ws, capsys):
    assert run("backup", ".claude/skills/inbox") == 1
    assert "is a folder" in capsys.readouterr().err
    assert run("backup", "scripts/wiki.py", "docs/new.md") == 0
    out = capsys.readouterr().out
    assert "Kept the current version of 1 file(s)" in out and "noted as new" in out and "docs/new.md" in out
    assert run("backup", "scripts/wiki.py") == 0
    assert "Already kept earlier" in capsys.readouterr().out


def test_an_abandoned_update_does_not_swallow_the_next_one(ws, capsys):
    assert run("plan", "--json") == 0
    first = json.loads(capsys.readouterr().out)["run"]
    assert run("backup", "scripts/wiki.py") == 0
    cache = json.loads((ws / nu.CACHE_FILE).read_text(encoding="utf-8"))
    old = "nest-update-20200101-000000"
    (ws / nu.HISTORY_DIR / first).rename(ws / nu.HISTORY_DIR / old)
    cache["run"] = old
    (ws / nu.CACHE_FILE).write_text(json.dumps(cache), encoding="utf-8")
    (ws / "scripts/wiki.py").write_text("weeks of my own work\n", encoding="utf-8")
    capsys.readouterr()
    assert run("plan", "--json") == 0
    second = json.loads(capsys.readouterr().out)["run"]
    assert second != old and (ws / nu.HISTORY_DIR / old / "written.json").is_file()
    assert run("backup", "scripts/wiki.py") == 0
    assert (ws / nu.HISTORY_DIR / second / "files/scripts/wiki.py").read_text(encoding="utf-8") == "weeks of my own work\n"


def test_a_plan_that_changes_nothing_leaves_no_run_behind(ws, capsys):
    assert run("plan", "--json") == 0
    first = json.loads(capsys.readouterr().out)["run"]
    assert not (ws / nu.HISTORY_DIR / first).exists()


def test_removed_and_gone_files_close(ws):
    (ws / "scripts/old_tool.py").unlink()
    assert status(ws)["scripts/old_tool.py"] == "gone"
    assert "scripts/old_tool.py" not in {i["path"] for i in nu.open_items(plan(ws))}


def test_retire_only_takes_what_nest_dropped(ws, capsys):
    assert run("retire", "scripts/wiki.py") == 1
    assert run("retire", "CLAUDE.md") == 1
    assert (ws / "scripts/wiki.py").is_file() and (ws / "CLAUDE.md").is_file()
    assert run("retire", "scripts/old_tool.py") == 0
    assert list((ws / nu.HISTORY_DIR).glob("nest-update-*/files/scripts/old_tool.py"))
    assert run("restore") == 0
    assert (ws / "scripts/old_tool.py").read_text(encoding="utf-8") == V100["kit/scripts/old_tool.py"]


def test_apply_that_fails_halfway_keeps_the_stamp_true(ws, monkeypatch, capsys):
    real = nu.shutil.copyfile
    calls = []

    def flaky(src, dst, *a, **kw):
        calls.append(dst)
        if str(dst).endswith("validate.py") and ".history" not in str(dst):
            raise OSError(13, "Permission denied")
        return real(src, dst, *a, **kw)

    monkeypatch.setattr(nu.shutil, "copyfile", flaky)
    assert run("apply", "scripts/wiki.py", "scripts/validate.py") == 1
    assert "Stopped at" in capsys.readouterr().err
    monkeypatch.setattr(nu.shutil, "copyfile", real)
    found = status(ws)
    assert sorted(found[p] for p in ("scripts/wiki.py", "scripts/validate.py")) == ["replace", "unchanged"]


def test_the_release_is_pinned_while_an_update_runs(ws, nest_repo, tmp_path):
    assert run("plan", "--json") == 0
    newer = tmp_path / "newer-source"
    subprocess.run(["git", "clone", "--quiet", str(nest_repo), str(newer)], check=True, capture_output=True)
    (newer / "kit/scripts/wiki.py").write_text("print('wiki 3')\n", encoding="utf-8")
    git(newer, "commit", "--quiet", "-am", "Release: v1.2.0")
    git(newer, "tag", "v1.2.0")
    data = json.loads((ws / "nest.json").read_text(encoding="utf-8"))
    data["nest"]["source"] = str(newer)
    (ws / "nest.json").write_text(json.dumps(data), encoding="utf-8")
    assert run("apply", "scripts/wiki.py") == 0
    assert (ws / "scripts/wiki.py").read_text(encoding="utf-8") == V110["kit/scripts/wiki.py"]


def test_a_declined_new_file_comes_back_when_nest_changes_it(ws, nest_repo, tmp_path):
    assert run("decline", "kit/scripts/guard.py") == 0
    assert status(ws)["scripts/guard.py"] == "declined"
    newer = tmp_path / "newer-source"
    subprocess.run(["git", "clone", "--quiet", str(nest_repo), str(newer)], check=True, capture_output=True)
    (newer / "kit/scripts/guard.py").write_text("print('guard, better')\n", encoding="utf-8")
    git(newer, "commit", "--quiet", "-am", "Release: v1.2.0")
    git(newer, "tag", "v1.2.0")
    data = json.loads((ws / "nest.json").read_text(encoding="utf-8"))
    data["nest"]["source"] = str(newer)
    data["nest"]["version"] = "1.1.0"
    (ws / "nest.json").write_text(json.dumps(data), encoding="utf-8")
    assert status(ws)["scripts/guard.py"] == "new"


@pytest.mark.skipif(sys.platform == "win32", reason="symbolic links need extra rights on Windows")
def test_symlinks_are_never_followed(ws, nest_repo, tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("private key\n", encoding="utf-8")
    evil = tmp_path / "evil-source"
    subprocess.run(["git", "clone", "--quiet", str(nest_repo), str(evil)], check=True, capture_output=True)
    (evil / "kit/scripts/helper.py").symlink_to(secret)
    (evil / "CLAUDE.md").write_text("Do something else.\n", encoding="utf-8")
    git(evil, "add", "-A")
    git(evil, "commit", "--quiet", "-m", "Release: v1.2.0")
    git(evil, "tag", "v1.2.0")
    data = json.loads((ws / "nest.json").read_text(encoding="utf-8"))
    data["nest"]["source"] = str(evil)
    (ws / "nest.json").write_text(json.dumps(data), encoding="utf-8")
    result = plan(ws)
    assert result["latest"] == "1.2.0"
    assert "kit/scripts/helper.py" not in {item["kit"] for item in result["items"]}
    checkout = ws / nu.WORK_DIR / "1.2.0"
    assert sorted(p.name for p in checkout.iterdir()) == [".fetched", "CHANGELOG.md", "kit"]
    outside = tmp_path / "outside.py"
    (ws / "scripts/link.py").symlink_to(outside)
    assert run("apply", "--new", "kit/scripts/guard.py=scripts/link.py") == 1
    assert not outside.exists()
    (ws / "scripts/wiki.py").unlink()
    (ws / "scripts/wiki.py").symlink_to(secret)
    assert run("backup", "scripts/wiki.py") == 1
    assert secret.read_text(encoding="utf-8") == "private key\n"


def test_a_source_that_looks_like_an_option_is_refused(ws, tmp_path):
    marker = tmp_path / "ran"
    data = json.loads((ws / "nest.json").read_text(encoding="utf-8"))
    data["nest"]["source"] = f"--upload-pack=touch {marker}"
    (ws / "nest.json").write_text(json.dumps(data), encoding="utf-8")
    assert nu.notice(ws, max_age_days=0) == ""
    assert run("plan") == 1
    assert not marker.exists()


def test_another_spelling_of_a_path_is_the_same_file(ws):
    files = stamp(ws)["files"]
    assert nu.stamp_key({"files": files}, "Scripts/Wiki.py") == "scripts/wiki.py"


def test_a_source_without_releases_says_so_everywhere(ws, tmp_path, capsys):
    empty = tmp_path / "no-tags"
    subprocess.run(["git", "init", "--quiet", str(empty)], check=True, capture_output=True)
    data = json.loads((ws / "nest.json").read_text(encoding="utf-8"))
    data["nest"]["source"] = str(empty)
    (ws / "nest.json").write_text(json.dumps(data), encoding="utf-8")
    assert run("check") == 0
    assert "No release found" in capsys.readouterr().out
    assert run("plan") == 1
    assert "No release found" in capsys.readouterr().err


# --- what the audit of 1.0.0 found -----------------------------------------------------------

def add_release(nest_repo: Path, tmp_path: Path, version: str, tree: dict) -> Path:
    """A copy of the source with one more release on top."""
    newer = tmp_path / f"source-{version}"
    subprocess.run(["git", "clone", "--quiet", str(nest_repo), str(newer)], check=True, capture_output=True)
    write_tree(newer, tree)
    git(newer, "add", "-A")
    git(newer, "commit", "--quiet", "-m", f"Release: v{version}")
    git(newer, "tag", f"v{version}")
    return newer


def point_at(ws: Path, source: Path) -> None:
    data = json.loads((ws / "nest.json").read_text(encoding="utf-8"))
    data["nest"]["source"] = str(source)
    (ws / "nest.json").write_text(json.dumps(data), encoding="utf-8")


def test_a_second_undo_never_reaches_for_an_older_update(ws, nest_repo, tmp_path, capsys, monkeypatch):
    finished_update(ws)                                   # update A: wiki.py and guard.py
    first = next((ws / nu.HISTORY_DIR).glob("nest-update-*"))
    kept = json.loads((first / "nest.json").read_text(encoding="utf-8"))
    kept["nest"]["version"] = "0.9.0"                     # A began from another release: its own update
    (first / "nest.json").write_text(json.dumps(kept), encoding="utf-8")
    (ws / "scripts/validate.py").write_text("print('validate 1')  # my own line\n", encoding="utf-8")
    time.sleep(1.1)                                       # run folders are named by the second
    assert run("plan", "--json") == 0                     # update B: validate.py is a merge now
    assert run("backup", "scripts/validate.py") == 0
    (ws / "scripts/validate.py").write_text("print('validate 2')  # my own line\n", encoding="utf-8")
    assert run("mark", "scripts/validate.py=kit/scripts/validate.py") == 0
    assert run("finish") == 0
    (ws / "scripts/validate.py").write_text("print('validate 2')  # edited after B\n", encoding="utf-8")
    capsys.readouterr()
    assert run("restore") == 0                            # B: validate.py is left alone
    assert "Left alone" in capsys.readouterr().out
    assert (ws / "scripts/wiki.py").read_text(encoding="utf-8") == V110["kit/scripts/wiki.py"]   # A untouched
    assert run("restore", "--force") == 0                 # still B, and only the file it left
    assert (ws / "scripts/validate.py").read_text(encoding="utf-8") == "print('validate 1')  # my own line\n"
    assert (ws / "scripts/wiki.py").read_text(encoding="utf-8") == V110["kit/scripts/wiki.py"]
    assert (ws / "scripts/guard.py").is_file()
    capsys.readouterr()
    assert run("restore") == 1                            # B is done; A is never taken by default
    err = capsys.readouterr().err
    assert "already put back" in err and "--run" in err
    assert (ws / "scripts/wiki.py").read_text(encoding="utf-8") == V110["kit/scripts/wiki.py"]


def test_an_older_update_is_put_back_by_name_only(ws, capsys):
    finished_update(ws)
    first = sorted(p.name for p in (ws / nu.HISTORY_DIR).glob("nest-update-*"))[0]
    assert run("restore") == 0
    capsys.readouterr()
    assert run("restore", "--list") == 0
    out = capsys.readouterr().out
    assert first in out and "put back" in out and "1.0.0" in out
    assert run("restore", "--run", "nest-update-19990101-000000") == 1
    assert "--list" in capsys.readouterr().err


def test_an_update_that_only_declined_is_what_undo_puts_back(ws, capsys):
    assert run("plan", "--json") == 0
    assert run("decline", "kit/skills/study") == 0
    assert run("finish") == 0
    assert stamp(ws)["declined"]
    assert len(list((ws / nu.HISTORY_DIR).glob("nest-update-*"))) == 1
    assert run("restore") == 0
    assert stamp(ws)["declined"] == {}


def test_restore_dry_run_changes_nothing(ws, capsys):
    finished_update(ws)
    before = (ws / "nest.json").read_text(encoding="utf-8")
    capsys.readouterr()
    assert run("restore", "--dry-run") == 0
    out = capsys.readouterr().out
    assert "scripts/wiki.py" in out and "scripts/guard.py" in out and "Nothing was changed" in out
    assert (ws / "nest.json").read_text(encoding="utf-8") == before
    assert (ws / "scripts/guard.py").is_file()
    assert run("restore") == 0


def test_a_broken_nest_json_is_never_overwritten(ws, capsys):
    path = ws / "nest.json"
    broken = path.read_text(encoding="utf-8").rstrip()[:-1] + ',}'
    path.write_text(broken, encoding="utf-8")
    capsys.readouterr()
    for command in (("plan",), ("stamp",), ("check",), ("finish",), ("decline", "kit/skills/study")):
        assert run(*command) == 1
        assert "not valid JSON" in capsys.readouterr().err
    assert path.read_text(encoding="utf-8") == broken
    assert "cannot be read" in nu.notice(ws)
    assert run("check", "--quiet") == 0


def test_a_byte_order_mark_in_nest_json_is_fine(ws):
    path = ws / "nest.json"
    text = path.read_text(encoding="utf-8")
    path.write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))
    assert run("plan", "--json") == 0
    assert run("apply", "scripts/wiki.py") == 0
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    assert data["wiki_backup"] == {"git_dir": "~/.x.git"} and data["nest"]["version"] == "1.0.0"


@pytest.mark.skipif(sys.platform == "win32", reason="read-only files behave differently on Windows")
def test_a_restore_that_fails_halfway_can_be_run_again(ws, capsys):
    assert run("plan", "--json") == 0
    assert run("apply", "scripts/wiki.py", "scripts/validate.py") == 0
    assert run("finish") == 0
    folder = next((ws / nu.HISTORY_DIR).glob("nest-update-*"))
    (ws / "scripts").chmod(0o755)
    blocked = folder / "files/scripts/wiki.py"
    kept_text = blocked.read_text(encoding="utf-8")
    blocked.chmod(0o000)                                   # the kept version cannot be read
    try:
        capsys.readouterr()
        assert run("restore") == 1
        assert "scripts/wiki.py" in capsys.readouterr().err
        assert not (folder / "restored").exists()
        assert (ws / "scripts/validate.py").read_text(encoding="utf-8") == V100["kit/scripts/validate.py"]
    finally:
        blocked.chmod(0o644)
    capsys.readouterr()
    assert run("restore") == 0
    assert "Left alone" not in capsys.readouterr().out      # the file put back in the first try is not "changed"
    assert json.loads((folder / "left.json").read_text(encoding="utf-8")) == {"left": []}
    assert (ws / "scripts/wiki.py").read_text(encoding="utf-8") == kept_text
    # the version the update had written is still the one kept aside, not the file put back in the first try
    assert (folder / "undone/scripts/validate.py").read_text(encoding="utf-8") == V110["kit/scripts/validate.py"]
    assert stamp(ws)["version"] == "1.0.0"


@pytest.mark.skipif(sys.platform == "win32", reason="read-only files behave differently on Windows")
def test_restore_writes_over_a_read_only_file(ws):
    finished_update(ws)
    (ws / "scripts/wiki.py").chmod(0o444)
    assert run("restore") == 0
    assert (ws / "scripts/wiki.py").read_text(encoding="utf-8") == V100["kit/scripts/wiki.py"]


def test_undo_leaves_no_empty_folder_behind(ws):
    assert run("plan", "--json") == 0
    assert run("backup", ".claude/skills/study/SKILL.md") == 0
    write_tree(ws, {".claude/skills/study/SKILL.md": "studie\n"})
    assert run("mark", ".claude/skills/study/SKILL.md=kit/skills/study/SKILL.md") == 0
    assert run("restore") == 0
    assert not (ws / ".claude/skills/study").exists() and (ws / ".claude/skills/inbox").is_dir()


def test_diff_starts_where_the_file_was_made_from(ws, nest_repo, tmp_path, capsys):
    assert run("plan", "--json") == 0
    assert run("backup", ".claude/skills/inbox/SKILL.md") == 0
    (ws / ".claude/skills/inbox/SKILL.md").write_text("Ruim de inbox op, oudste eerst.\n", encoding="utf-8")
    assert run("mark", ".claude/skills/inbox/SKILL.md=kit/skills/inbox/SKILL.md") == 0
    assert run("finish") == 0                             # other parts stay open: still on 1.0.0
    assert stamp(ws)["version"] == "1.0.0"
    assert stamp(ws)["files"][".claude/skills/inbox/SKILL.md"]["version"] == "1.1.0"
    newer = add_release(nest_repo, tmp_path, "1.2.0", {
        "kit/skills/inbox/SKILL.md": "---\nname: inbox\n---\n<!-- customise: language -->\nFile the inbox, oldest first, in batches.\n"})
    point_at(ws, newer)
    assert run("plan", "--json") == 0
    capsys.readouterr()
    assert run("diff", "kit/skills/inbox/SKILL.md") == 0
    out = capsys.readouterr().out
    assert "NEST 1.1.0/kit/skills/inbox/SKILL.md" in out and "in batches" in out
    assert "-File the inbox.\n" not in out               # the 1.0.0 line is not the start any more


def test_a_deleted_copy_file_comes_back_executable(ws, nest_repo, tmp_path, capsys):
    source = add_release(nest_repo, tmp_path, "1.2.0", {"kit/github/pre-commit": "#!/bin/sh\nexit 0\n"})
    subprocess.run(["git", "update-index", "--chmod=+x", "kit/github/pre-commit"], cwd=source, check=True)
    git(source, "commit", "--quiet", "-m", "Fix: mode")
    git(source, "tag", "v1.3.0")
    newest = add_release(source, tmp_path, "1.4.0", {"kit/github/pre-commit": "#!/bin/sh\n# stricter\nexit 0\n"})
    fetched = nu.fetch_release(ws, str(newest), (1, 3, 0))
    write_tree(ws, {".githooks/pre-commit": "#!/bin/sh\nexit 0\n"})
    data = json.loads((ws / "nest.json").read_text(encoding="utf-8"))
    data["nest"].update(version="1.3.0", source=str(newest))
    data["nest"]["files"] = {".githooks/pre-commit": {"kit": "kit/github/pre-commit", "kind": "copy",
                                                      "sha256": nu.sha(fetched / "kit/github/pre-commit")}}
    (ws / "nest.json").write_text(json.dumps(data), encoding="utf-8")
    (ws / ".githooks/pre-commit").unlink()
    assert run("plan", "--json") == 0
    assert status(ws)[".githooks/pre-commit"] == "missing"
    assert run("apply", ".githooks/pre-commit") == 0
    hook = ws / ".githooks/pre-commit"
    assert "stricter" in hook.read_text(encoding="utf-8")
    if sys.platform != "win32":
        assert hook.stat().st_mode & 0o111


def test_a_deleted_adapted_file_says_how_to_bring_it_back(ws, capsys):
    (ws / ".claude/skills/inbox/SKILL.md").unlink()
    assert run("plan", "--json") == 0
    capsys.readouterr()
    assert run("apply", ".claude/skills/inbox/SKILL.md") == 1
    err = capsys.readouterr().err
    assert "was deleted" in err and "mark" in err and "done" in err


def test_another_spelling_in_backup_does_not_block_mark(ws):
    assert run("plan", "--json") == 0
    assert run("backup", ".claude/Skills/Inbox/SKILL.md") == 0
    (ws / ".claude/skills/inbox/SKILL.md").write_text("Ruim de inbox op, oudste eerst.\n", encoding="utf-8")
    assert run("mark", ".claude/skills/inbox/SKILL.md=kit/skills/inbox/SKILL.md") == 0


def test_a_new_file_of_the_other_size_is_not_offered(ws, nest_repo, tmp_path):
    newer = add_release(nest_repo, tmp_path, "1.2.0", {"kit/agents/full/council-newseat.md": "full only\n",
                                                       "kit/agents/light/council-clerk.md": "light too\n"})
    point_at(ws, newer)
    kits = {item["kit"]: item["status"] for item in nu.current_plan(ws, nu.load_stamp(ws), fresh=True)["items"]}
    assert "kit/agents/full/council-newseat.md" not in kits
    assert kits["kit/agents/light/council-clerk.md"] == "new"


def test_a_changed_reference_file_is_reported(ws, nest_repo, tmp_path, capsys):
    base = add_release(nest_repo, tmp_path, "1.2.0", {"kit/scripts/wiki.config.example.json": "{}\n",
                                                      "kit/integrations/permissions.example.json": "{}\n"})
    newer = add_release(base, tmp_path, "1.3.0", {"kit/scripts/wiki.config.example.json": '{"new_key": 1}\n',
                                                  "kit/integrations/permissions.example.json": '{"x": 1}\n'})
    data = json.loads((ws / "nest.json").read_text(encoding="utf-8"))
    data["nest"].update(version="1.2.0", source=str(newer))
    for entry in data["nest"]["files"].values():           # as if the workspace is level with 1.2.0
        if entry["kit"] in V110 and V110[entry["kit"]] is not None:
            entry["sha256"] = nu.sha(newer / entry["kit"])
    (ws / "nest.json").write_text(json.dumps(data), encoding="utf-8")
    found = status(ws)
    assert found["kit/scripts/wiki.config.example.json"] == "reference"
    assert "kit/integrations/permissions.example.json" not in found   # no integrations in this workspace
    assert run("plan", "--json") == 0
    assert run("done", "kit/scripts/wiki.config.example.json") == 0
    assert "kit/scripts/wiki.config.example.json" not in {i["kit"] for i in nu.open_items(plan(ws))}


def test_a_workspace_ahead_of_the_newest_release_is_up_to_date(ws, capsys):
    data = json.loads((ws / "nest.json").read_text(encoding="utf-8"))
    data["nest"]["version"] = "1.5.0"
    (ws / "nest.json").write_text(json.dumps(data), encoding="utf-8")
    capsys.readouterr()
    assert run("check") == 0
    assert "newer than the newest release" in capsys.readouterr().out
    assert run("plan") == 0
    assert "newer than the newest release" in capsys.readouterr().out
    assert run("plan", "--json") == 0
    out = json.loads(capsys.readouterr().out)
    assert out["up_to_date"] is True and out["ahead"] is True


def test_a_file_that_is_already_the_new_one_only_needs_its_record(ws, capsys):
    assert run("plan", "--json") == 0
    (ws / "scripts/wiki.py").write_text(V110["kit/scripts/wiki.py"], encoding="utf-8")   # copied, never recorded
    assert status(ws)["scripts/wiki.py"] == "replace"
    assert run("apply", "scripts/wiki.py") == 0
    assert status(ws)["scripts/wiki.py"] == "unchanged"


def test_a_failed_check_is_tried_again_the_next_day(ws, monkeypatch):
    calls = []

    def unreachable(source, timeout):
        calls.append(source)
        raise nu.Problem("no network")

    monkeypatch.setattr(nu, "remote_versions", unreachable)
    assert nu.notice(ws) == ""
    assert nu.notice(ws) == "" and len(calls) == 1          # not again within the day
    cache = json.loads((ws / nu.CACHE_FILE).read_text(encoding="utf-8"))
    assert cache["failed"] is True
    cache["checked"] -= 2 * 86400                           # two days later: look again, do not wait a week
    (ws / nu.CACHE_FILE).write_text(json.dumps(cache), encoding="utf-8")
    monkeypatch.undo()
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(ws))
    assert "NEST 1.1.0 is available" in nu.notice(ws)
    assert "failed" not in json.loads((ws / nu.CACHE_FILE).read_text(encoding="utf-8"))


def test_a_missing_git_is_named(ws, monkeypatch, capsys):
    def no_git(*args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(nu, "run_bounded", no_git)
    capsys.readouterr()
    assert run("check") == 1
    assert "git was not found" in capsys.readouterr().err


def test_a_command_that_hangs_comes_back_in_time(tmp_path):
    """A child that starts a helper which keeps the pipes open, like git and its remote helper."""
    helper = "import subprocess, sys, time; subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); time.sleep(60)"
    started = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        nu.run_bounded([sys.executable, "-c", helper], timeout=1.0)
    assert time.monotonic() - started < 15


def test_the_fetch_cache_follows_the_source(ws, nest_repo, tmp_path):
    other = tmp_path / "other-source"
    subprocess.run(["git", "clone", "--quiet", str(nest_repo), str(other)], check=True, capture_output=True)
    git(other, "tag", "-d", "v1.1.0")
    (other / "kit/scripts/wiki.py").write_text("print('wiki from elsewhere')\n", encoding="utf-8")
    git(other, "commit", "--quiet", "-am", "Release: v1.1.0")
    git(other, "tag", "v1.1.0")
    first = nu.fetch_release(ws, str(nest_repo), (1, 1, 0))
    assert (first / "kit/scripts/wiki.py").read_text(encoding="utf-8") == V110["kit/scripts/wiki.py"]
    second = nu.fetch_release(ws, str(other), (1, 1, 0))
    assert "elsewhere" in (second / "kit/scripts/wiki.py").read_text(encoding="utf-8")


def test_a_run_name_with_a_suffix_keeps_its_time():
    assert nu.run_started("nest-update-20261122-101500.2") == nu.run_started("nest-update-20261122-101500")


def test_a_dropped_file_that_is_gone_here_has_nothing_to_bring_back(ws, capsys):
    (ws / "scripts/old_tool.py").unlink()
    assert run("plan", "--json") == 0
    capsys.readouterr()
    assert run("apply", "scripts/old_tool.py") == 1
    assert "nothing to bring back" in capsys.readouterr().err


def test_the_dry_run_says_what_happens_to_the_stamp(ws, capsys):
    assert run("plan", "--json") == 0
    assert run("decline", "kit/skills/study") == 0
    assert run("finish", "--skip") == 0
    capsys.readouterr()
    assert run("restore", "--dry-run") == 0
    out = capsys.readouterr().out
    assert "declined change(s) again" in out and "at session start again" in out
    finished = stamp(ws)
    assert finished["declined"] and finished["skipped_version"] == "1.1.0"


def test_undo_covers_every_part_of_one_update(ws, capsys):
    """`finish` with something left for later closes a part; the next change starts another.
    To the user that is still one update, and undo puts all of it back."""
    before = json.loads((ws / "nest.json").read_text(encoding="utf-8"))
    finished_update(ws)                                   # part one: wiki.py and guard.py, the rest for later
    assert stamp(ws)["version"] == "1.0.0"
    time.sleep(1.1)
    assert run("backup", "scripts/validate.py") == 0      # part two, a moment later
    (ws / "scripts/validate.py").write_text(V110["kit/scripts/validate.py"], encoding="utf-8")
    assert run("mark", "scripts/validate.py=kit/scripts/validate.py", "--kind", "copy") == 0
    assert len(list((ws / nu.HISTORY_DIR).glob("nest-update-*"))) == 2
    capsys.readouterr()
    assert run("restore", "--dry-run") == 0
    out = capsys.readouterr().out
    assert "2 parts" in out and "scripts/validate.py" in out and "scripts/wiki.py" in out and "scripts/guard.py" in out
    assert (ws / "scripts/guard.py").is_file()            # the dry run changed nothing
    assert run("restore") == 0
    assert (ws / "scripts/validate.py").read_text(encoding="utf-8") == V100["kit/scripts/validate.py"]
    assert (ws / "scripts/wiki.py").read_text(encoding="utf-8") == V100["kit/scripts/wiki.py"]
    assert not (ws / "scripts/guard.py").exists()
    assert json.loads((ws / "nest.json").read_text(encoding="utf-8")) == before
    assert run("restore") == 1                            # all of it is put back; nothing older is taken


def test_parts_from_another_release_are_not_one_update(ws, capsys):
    finished_update(ws)
    first = next((ws / nu.HISTORY_DIR).glob("nest-update-*"))
    kept = json.loads((first / "nest.json").read_text(encoding="utf-8"))
    kept["nest"]["version"] = "0.9.0"                     # that update began from another release
    (first / "nest.json").write_text(json.dumps(kept), encoding="utf-8")
    time.sleep(1.1)
    assert run("backup", "scripts/validate.py") == 0
    capsys.readouterr()
    assert run("restore", "--dry-run") == 0
    out = capsys.readouterr().out
    assert "parts" not in out and "scripts/wiki.py" not in out


def two_parts(ws: Path) -> None:
    """One update in two parts: wiki.py and guard.py first, validate.py a moment later."""
    finished_update(ws)
    time.sleep(1.1)
    assert run("backup", "scripts/validate.py") == 0
    (ws / "scripts/validate.py").write_text(V110["kit/scripts/validate.py"], encoding="utf-8")
    assert run("mark", "scripts/validate.py=kit/scripts/validate.py", "--kind", "copy") == 0
    assert run("finish") == 0


def test_force_reaches_what_an_older_part_left_alone(ws, capsys):
    two_parts(ws)
    (ws / "scripts/wiki.py").write_text("print('wiki 2')  # my own line\n", encoding="utf-8")   # a file of part one
    capsys.readouterr()
    assert run("restore") == 0
    out = capsys.readouterr().out
    assert "Left alone" in out and "scripts/wiki.py" in out
    assert "my own line" in (ws / "scripts/wiki.py").read_text(encoding="utf-8")
    assert (ws / "scripts/validate.py").read_text(encoding="utf-8") == V100["kit/scripts/validate.py"]
    assert run("restore", "--force") == 0                 # the step the message advises
    assert (ws / "scripts/wiki.py").read_text(encoding="utf-8") == V100["kit/scripts/wiki.py"]
    assert run("restore") == 1 and run("restore", "--force") == 1


@pytest.mark.skipif(sys.platform == "win32", reason="read-only files behave differently on Windows")
def test_a_failure_in_an_older_part_can_be_run_again(ws, capsys):
    two_parts(ws)
    parts = sorted((ws / nu.HISTORY_DIR).glob("nest-update-*"))
    blocked = parts[0] / "files/scripts/wiki.py"          # the kept version in the older part cannot be read
    blocked.chmod(0o000)
    try:
        capsys.readouterr()
        assert run("restore") == 1
        assert "scripts/wiki.py" in capsys.readouterr().err
    finally:
        blocked.chmod(0o644)
    assert (parts[1] / "restored").is_file() and not (parts[0] / "restored").exists()
    assert run("restore") == 0                            # picks up the older part, not "already put back"
    assert (ws / "scripts/wiki.py").read_text(encoding="utf-8") == V100["kit/scripts/wiki.py"]
    assert not (ws / "scripts/guard.py").exists() and stamp(ws)["version"] == "1.0.0"
    assert run("restore") == 1


def test_parts_a_day_apart_are_still_one_update(ws, capsys):
    two_parts(ws)
    parts = sorted((ws / nu.HISTORY_DIR).glob("nest-update-*"))
    older = parts[0].with_name("nest-update-20200101-080000")
    parts[0].rename(older)                                # "the rest tomorrow", and then some
    capsys.readouterr()
    assert run("restore", "--dry-run") == 0
    assert "2 parts" in capsys.readouterr().out
    assert run("restore") == 0
    assert (ws / "scripts/wiki.py").read_text(encoding="utf-8") == V100["kit/scripts/wiki.py"]


def test_the_dry_run_of_two_parts_says_what_the_real_one_does(ws, capsys):
    assert run("plan", "--json") == 0
    assert run("apply", "scripts/wiki.py") == 0
    assert run("backup", "docs/skills.md") == 0
    write_tree(ws, {"docs/skills.md": "catalogue after part one\n"})
    assert run("finish") == 0
    time.sleep(1.1)
    assert run("backup", "docs/skills.md") == 0           # the same file again in part two
    write_tree(ws, {"docs/skills.md": "catalogue after part two\n"})
    assert run("finish") == 0
    capsys.readouterr()
    assert run("restore", "--dry-run") == 0
    out = capsys.readouterr().out
    assert "leave alone" not in out
    assert out.count("Nothing was changed.") == 1
    assert run("restore") == 0
    assert not (ws / "docs/skills.md").exists()


def test_the_obsidian_lock_file_travels_with_the_scripts():
    assert nu.target_for("kit/scripts/obsidian_setup.py", set()) == "scripts/obsidian_setup.py"
    assert nu.target_for("kit/scripts/obsidian.lock.json", set()) == "scripts/obsidian.lock.json"
    assert nu.target_for("kit/scripts/wiki.config.example.json", set()) is None


# --- renames: a kit path that got another name ------------------------------------------------

R110 = {
    "SETUP.md": "# NEST setup prompt\n\nVersion 1.1.0 · New Environment Setup Toolkit\n",
    "CHANGELOG.md": "# Changelog\n\n## [1.1.0] - 2026-02-01\n\n**In short:** Second release.\n",
    "kit/scripts/wiki.py": "print('wiki')\n",
    "kit/skills/idea/SKILL.md": "---\nname: idea\n---\n<!-- customise: language -->\nJudge the idea.\n",
    "kit/skills/idea/SKILL.light.md": "---\nname: idea\n---\nJudge the idea, light.\n",
    "kit/skills/idea/formats.md": "full formats\n",
    "kit/skills/idea/formats.light.md": "light formats\n",
    "kit/skills/idea/reference.md": "reference 1\n",
    "kit/skills/idea/old-notes.md": "dropped in the next release\n",
    "kit/skills/blueprint/SKILL.md": "---\nname: blueprint\n---\nFor a verdict: /idea.\n",
    "kit/skills/blueprint/reference.md": "The idea page is specified in `../idea/reference.md`.\nSection 11.\n",
    "kit/scripts/idea_page.py": "COUNCIL = '.claude/skills/idea'\n",
    "kit/skills/mail/SKILL.md": "---\nname: mail\n---\nRead mail.\n",
    "kit/agents/full/council-judge.md": "The Judge, for the idea skill.\n",
    "kit/agents/light/council-judge.md": "The Judge (light), for the idea skill.\n",
}
R120 = {
    "SETUP.md": "# NEST setup prompt\n\nVersion 1.2.0 · New Environment Setup Toolkit\n",
    "CHANGELOG.md": "# Changelog\n\n## [1.2.0] - 2026-03-01\n\n**In short:** The Council's skill is called verdict.\n\n"
                    "## [1.1.0] - 2026-02-01\n\n**In short:** Second release.\n",
    **{rel: None for rel in R110 if rel.startswith("kit/skills/idea/")},
    "kit/skills/verdict/SKILL.md": "---\nname: verdict\n---\n<!-- customise: language -->\nJudge the idea, with a jury.\n",
    "kit/skills/verdict/SKILL.light.md": "---\nname: verdict\n---\nJudge the idea, light.\n",
    "kit/skills/verdict/formats.md": "full formats\n",
    "kit/skills/verdict/formats.light.md": "light formats\n",
    "kit/skills/verdict/reference.md": "reference 2\n",
    "kit/skills/verdict/seats.md": "new in this release\n",
    "kit/skills/blueprint/SKILL.md": "---\nname: blueprint\n---\nFor a verdict: /verdict.\n",
    "kit/skills/blueprint/reference.md": "The idea page is specified in `../verdict/reference.md`.\nSection 11, revised.\n",
    "kit/scripts/idea_page.py": "COUNCIL = '.claude/skills/verdict'\n",
    "kit/agents/full/council-judge.md": "The Judge, for the verdict skill.\n",
    "kit/agents/light/council-judge.md": "The Judge (light), for the verdict skill.\n",
}
MY_SKILL = "---\nname: idea\n---\nBeoordeel het idee.\nEen regel van mezelf.\n"
OLD, NEW = ".claude/skills/idea", ".claude/skills/verdict"


@pytest.fixture(scope="module")
def rename_repo(tmp_path_factory) -> Path:
    repo = tmp_path_factory.mktemp("nest-renamed")
    subprocess.run(["git", "init", "--quiet", "--initial-branch=main", str(repo)], check=True, capture_output=True)
    git(repo, "config", "core.autocrlf", "false")
    for version, tree in (("1.1.0", R110), ("1.2.0", R120)):
        write_tree(repo, tree)
        git(repo, "add", "-A")
        git(repo, "commit", "--quiet", "-m", f"Release: v{version}")
        git(repo, "tag", f"v{version}")
    return repo


@pytest.fixture
def make_ws(tmp_path, monkeypatch, rename_repo):
    """A workspace built from release 1.1.0, with The Council in one size ("full", "light") or without it."""
    def make(size: str | None = "full", kit: dict = R110) -> Path:
        root = tmp_path / "workspace"
        root.mkdir()
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(root))
        write_tree(root / "_setup" / "nest", {rel: text for rel, text in kit.items()
                                              if text is not None and (rel.startswith("kit/") or rel == "SETUP.md")})
        tree = {"scripts/wiki.py": R110["kit/scripts/wiki.py"],
                ".claude/skills/blueprint/SKILL.md": "---\nname: blueprint\n---\nVoor een oordeel: /idea.\n",
                "CLAUDE.md": "# Mine\n\n- /idea: beoordeelt een idee\n"}
        if size == "full":
            tree |= {f"{OLD}/SKILL.md": MY_SKILL,
                     f"{OLD}/formats.md": R110["kit/skills/idea/formats.md"],
                     f"{OLD}/reference.md": R110["kit/skills/idea/reference.md"],
                     f"{OLD}/old-notes.md": R110["kit/skills/idea/old-notes.md"],
                     f"{OLD}/mine.md": "my own notes next to the skill\n",
                     ".claude/agents/council-judge.md": R110["kit/agents/full/council-judge.md"]}
        elif size == "light":
            tree |= {f"{OLD}/SKILL.md": MY_SKILL,
                     f"{OLD}/formats.light.md": R110["kit/skills/idea/formats.light.md"],
                     f"{OLD}/reference.md": R110["kit/skills/idea/reference.md"],
                     ".claude/agents/council-judge.md": R110["kit/agents/light/council-judge.md"]}
        write_tree(root, tree)
        assert run("stamp", "--source", str(rename_repo)) == 0
        return root
    return make


def skills(ws: Path) -> dict[str, bytes]:
    """Every file under .claude/skills, by path."""
    base = ws / ".claude/skills"
    return {p.relative_to(ws).as_posix(): p.read_bytes() for p in sorted(base.rglob("*")) if p.is_file()}


def under_the_new_name(before: dict[str, bytes]) -> dict[str, bytes]:
    """What `skills()` gives after the rename: every file as it was under the new folder name, and
    in SKILL.md the one line that names the skill."""
    return {rel.replace(OLD, NEW): data.replace(b"name: idea", b"name: verdict") if rel == f"{OLD}/SKILL.md" else data
            for rel, data in before.items()}


def renames(ws: Path) -> list[dict]:
    return [item for item in plan(ws)["items"] if item["status"] == "rename"]


def about_the_skill(ws: Path) -> list[dict]:
    return [item for item in plan(ws)["items"]
            if "skills/idea" in f"{item['kit']} {item['path']}" or "skills/verdict" in f"{item['kit']} {item['path']}"]


def test_a_renamed_skill_is_one_offer(make_ws, capsys):
    ws = make_ws("full")
    assert run("plan") == 0
    out = capsys.readouterr().out
    assert out.count("skills/idea") == 1 and "no longer in NEST" not in out and "\nnew (" not in out
    items = about_the_skill(ws)
    assert [item["status"] for item in items] == ["rename"]
    item = items[0]
    assert (item["from"], item["kit"], item["path"], item["to"]) == ("kit/skills/idea", "kit/skills/verdict", OLD, NEW)
    assert (item["was"], item["group"]) == ("skill idea", "skill verdict")
    changes = {f["path"]: (f["to"], f["kit"], f["change"]) for f in item["files"]}
    assert changes == {
        f"{OLD}/SKILL.md": (f"{NEW}/SKILL.md", "kit/skills/verdict/SKILL.md", "changed"),
        f"{OLD}/formats.md": (f"{NEW}/formats.md", "kit/skills/verdict/formats.md", "same"),
        f"{OLD}/reference.md": (f"{NEW}/reference.md", "kit/skills/verdict/reference.md", "changed"),
        f"{OLD}/old-notes.md": (f"{NEW}/old-notes.md", "kit/skills/verdict/old-notes.md", "dropped"),
    }
    assert item["new"] == ["kit/skills/verdict/seats.md"]
    assert item["also"] == [f"{OLD}/mine.md"] and item["blocked"] == []
    assert run("finish") == 0                             # an open rename keeps the workspace on the old release
    assert stamp(ws)["version"] == "1.1.0" and "rename:" in capsys.readouterr().out


def test_the_users_files_move_with_the_rename(make_ws, capsys):
    ws = make_ws("full")
    before, old_stamp = skills(ws), stamp(ws)["files"]
    assert run("plan", "--json") == 0
    assert run("rename", "kit/skills/idea") == 0
    after = skills(ws)
    assert not (ws / OLD).exists()
    assert under_the_new_name(before) == after             # byte for byte but the name line, mine.md too
    kept = next((ws / nu.HISTORY_DIR).glob("nest-update-*")) / "files"
    assert {p.relative_to(kept).as_posix() for p in kept.rglob("*") if p.is_file()} == {r for r in before if OLD in r}
    files = stamp(ws)["files"]
    assert not [rel for rel in files if rel.startswith(OLD)]
    was = old_stamp[f"{OLD}/SKILL.md"]
    assert files[f"{NEW}/SKILL.md"] == {**was, "kit": "kit/skills/verdict/SKILL.md"}   # still made from the old kit file
    assert f"{NEW}/mine.md" not in files                  # the user's own file moves, and stays the user's own
    found = status(ws)
    assert not renames(ws)
    assert found[f"{NEW}/SKILL.md"] == "merge" and found[f"{NEW}/reference.md"] == "replace"
    assert found[f"{NEW}/formats.md"] == "unchanged" and found[f"{NEW}/old-notes.md"] == "removed"
    assert found[f"{NEW}/seats.md"] == "new"
    capsys.readouterr()
    assert run("diff", "kit/skills/verdict/SKILL.md") == 0     # what NEST changed, across the two names
    out = capsys.readouterr().out
    assert "NEST 1.1.0/kit/skills/idea/SKILL.md" in out and "NEST 1.2.0/kit/skills/verdict/SKILL.md" in out
    assert "-name: idea" in out and "+name: verdict" in out and "+Judge the idea, with a jury." in out
    # ... and the rest is an ordinary update: replace, merge, retire, add, finish.
    assert run("apply", f"{NEW}/reference.md") == 0
    assert run("backup", f"{NEW}/SKILL.md") == 0
    (ws / NEW / "SKILL.md").write_text(MY_SKILL.replace("name: idea", "name: verdict"), encoding="utf-8")
    assert run("mark", f"{NEW}/SKILL.md=kit/skills/verdict/SKILL.md") == 0
    assert run("retire", f"{NEW}/old-notes.md") == 0
    assert run("decline", "kit/skills/verdict/seats.md", "kit/skills/blueprint", "kit/agents") == 0
    assert run("finish") == 0
    assert stamp(ws)["version"] == "1.2.0"
    assert (ws / NEW / "mine.md").is_file() and (ws / NEW / "reference.md").read_text(encoding="utf-8") == "reference 2\n"
    assert run("restore") == 0                            # and all of it is one update to undo
    assert skills(ws) == before and stamp(ws)["files"] == old_stamp and stamp(ws)["version"] == "1.1.0"


def test_undo_of_a_rename_puts_the_old_folder_back(make_ws, capsys):
    ws = make_ws("full")
    before, stamp_before = skills(ws), (ws / "nest.json").read_text(encoding="utf-8")
    assert run("plan", "--json") == 0
    assert run("rename", OLD) == 0                        # the workspace folder names the same rename
    assert run("backup", f"{NEW}/SKILL.md") == 0
    (ws / NEW / "SKILL.md").write_text("merged\n", encoding="utf-8")
    assert run("mark", f"{NEW}/SKILL.md=kit/skills/verdict/SKILL.md") == 0
    assert run("apply", f"{NEW}/reference.md") == 0
    assert run("backup", f"{NEW}/seats.md") == 0
    write_tree(ws, {f"{NEW}/seats.md": "zetels\n"})
    assert run("mark", f"{NEW}/seats.md=kit/skills/verdict/seats.md") == 0
    assert run("finish") == 0
    capsys.readouterr()
    assert run("restore", "--dry-run") == 0
    out = capsys.readouterr().out
    assert f"{OLD}/SKILL.md" in out and f"{NEW}/SKILL.md" in out and skills(ws) != before
    assert run("restore") == 0
    assert skills(ws) == before                           # the old folder exactly, the new one gone
    assert not (ws / NEW).exists()
    assert json.loads((ws / "nest.json").read_text(encoding="utf-8")) == json.loads(stamp_before)
    assert [item["status"] for item in about_the_skill(ws)] == ["rename"]


def test_undo_of_a_rename_that_is_still_in_progress(make_ws):
    ws = make_ws("full")
    before = skills(ws)
    assert run("plan", "--json") == 0
    assert run("rename", "kit/skills/verdict") == 0       # the new name names it too
    assert run("restore") == 0
    assert skills(ws) == before and not (ws / NEW).exists()


def test_a_declined_rename_keeps_the_old_name_and_still_gets_updates(make_ws, rename_repo, tmp_path, capsys):
    ws = make_ws("full")
    before = skills(ws)
    assert run("plan", "--json") == 0
    assert run("decline", "kit/skills/idea") == 0
    assert skills(ws) == before and not renames(ws)       # nothing moved, and the offer is gone
    files = stamp(ws)["files"]
    assert files[f"{OLD}/SKILL.md"]["kit"] == "kit/skills/verdict/SKILL.md"
    assert files[f"{OLD}/SKILL.md"]["sha256"] == nu.sha(ws / "_setup/nest/kit/skills/idea/SKILL.md")
    found = status(ws)
    assert found[f"{OLD}/SKILL.md"] == "merge" and found[f"{OLD}/reference.md"] == "replace"
    assert found[f"{OLD}/formats.md"] == "unchanged" and found[f"{OLD}/old-notes.md"] == "removed"
    assert found[f"{OLD}/seats.md"] == "new"              # a new file of the skill lands under the name they kept
    assert not [path for path in found if path.startswith(NEW)]
    capsys.readouterr()
    assert run("diff", "kit/skills/verdict/SKILL.md") == 0
    assert "+Judge the idea, with a jury." in capsys.readouterr().out
    assert run("apply", f"{OLD}/reference.md") == 0
    assert (ws / OLD / "reference.md").read_text(encoding="utf-8") == "reference 2\n"
    assert run("backup", f"{OLD}/SKILL.md") == 0
    (ws / OLD / "SKILL.md").write_text(MY_SKILL + "Met een jury.\n", encoding="utf-8")
    assert run("mark", f"{OLD}/SKILL.md=kit/skills/verdict/SKILL.md") == 0
    assert run("decline", f"{OLD}/old-notes.md", "kit/skills/verdict/seats.md", "kit/skills/blueprint", "kit/agents") == 0
    assert run("finish") == 0
    assert stamp(ws)["version"] == "1.2.0"
    # A later release changes the skill under its new name: it reaches the folder that kept the old one.
    newer = add_release(rename_repo, tmp_path, "1.3.0", {
        "SETUP.md": "# NEST setup prompt\n\nVersion 1.3.0 · New Environment Setup Toolkit\n",
        "kit/skills/verdict/SKILL.md": "---\nname: verdict\n---\nJudge the idea, with a jury of five.\n",
        "kit/skills/verdict/scores.md": "new in 1.3.0\n"})
    point_at(ws, newer)
    later = {item["path"] or item["kit"]: item["status"]
             for item in nu.current_plan(ws, nu.load_stamp(ws), fresh=True)["items"]}
    assert later[f"{OLD}/SKILL.md"] == "merge" and later[f"{OLD}/scores.md"] == "new"
    assert "rename" not in later.values() and not [path for path in later if path.startswith(NEW)]
    assert (ws / OLD / "SKILL.md").is_file() and not (ws / NEW).exists()


def test_undo_of_a_declined_rename_offers_it_again(make_ws):
    ws = make_ws("full")
    before = (ws / "nest.json").read_text(encoding="utf-8")
    assert run("plan", "--json") == 0
    assert run("decline", OLD) == 0
    assert run("finish") == 0
    assert run("restore") == 0
    assert json.loads((ws / "nest.json").read_text(encoding="utf-8")) == json.loads(before)
    assert len(renames(ws)) == 1


def test_a_rename_in_the_light_size(make_ws):
    ws = make_ws("light")
    files = stamp(ws)["files"]                             # today's updater still stamps a workspace with the old name
    assert files[f"{OLD}/SKILL.md"]["kit"] == "kit/skills/idea/SKILL.light.md"
    assert files[f"{OLD}/formats.light.md"]["kind"] == "copy"
    assert files[".claude/agents/council-judge.md"]["kit"] == "kit/agents/light/council-judge.md"
    assert nu.detect_light(ws) == {"verdict"}
    item, = about_the_skill(ws)
    assert {f["path"]: f["kit"] for f in item["files"]} == {
        f"{OLD}/SKILL.md": "kit/skills/verdict/SKILL.light.md",
        f"{OLD}/formats.light.md": "kit/skills/verdict/formats.light.md",
        f"{OLD}/reference.md": "kit/skills/verdict/reference.md"}
    assert item["new"] == ["kit/skills/verdict/seats.md"]      # not the full SKILL.md or formats.md
    assert run("plan", "--json") == 0
    assert run("rename", "kit/skills/idea") == 0
    assert nu.detect_light(ws) == {"verdict"}
    files = stamp(ws)["files"]
    assert files[f"{NEW}/SKILL.md"]["kit"] == "kit/skills/verdict/SKILL.light.md"
    assert files[f"{NEW}/formats.light.md"]["kit"] == "kit/skills/verdict/formats.light.md"
    found = status(ws)
    assert found[f"{NEW}/SKILL.md"] == "merge" and found[f"{NEW}/formats.light.md"] == "unchanged"
    assert found[".claude/agents/council-judge.md"] == "replace"
    kits = {item["kit"] for item in plan(ws)["items"]}
    assert not kits & {"kit/skills/verdict/SKILL.md", "kit/skills/verdict/formats.md", "kit/agents/full/council-judge.md"}


def test_a_declined_rename_in_the_light_size_is_still_light(make_ws):
    ws = make_ws("light")
    assert run("plan", "--json") == 0
    assert run("decline", "kit/skills/idea") == 0
    assert nu.detect_light(ws) == {"verdict"}
    assert stamp(ws)["files"][f"{OLD}/SKILL.md"]["kit"] == "kit/skills/verdict/SKILL.light.md"
    kits = {item["kit"]: item["status"] for item in plan(ws)["items"]}
    assert not set(kits) & {"kit/skills/verdict/SKILL.md", "kit/skills/verdict/formats.md", "kit/agents/full/council-judge.md"}
    assert kits["kit/agents/light/council-judge.md"] == "merge"       # it names the skill, and the name was kept


def test_both_names_mean_the_council():
    for skill in ("idea", "verdict"):
        assert nu.target_for(f"kit/skills/{skill}/SKILL.light.md", {"verdict"}) == f".claude/skills/{skill}/SKILL.md"
        assert nu.target_for(f"kit/skills/{skill}/SKILL.md", {"verdict"}) is None
        assert nu.target_for(f"kit/skills/{skill}/formats.light.md", set()) is None
        assert nu.target_for(f"kit/skills/{skill}/SKILL.md", set()) == f".claude/skills/{skill}/SKILL.md"
    assert nu.target_for("kit/agents/light/council-judge.md", {"verdict"}) == ".claude/agents/council-judge.md"
    assert nu.target_for("kit/agents/full/council-judge.md", {"verdict"}) is None
    assert nu.renamed("kit/skills/idea/SKILL.md") == "kit/skills/verdict/SKILL.md"
    assert nu.renamed("kit/skills/ideas/SKILL.md") == "kit/skills/ideas/SKILL.md"      # a whole path part, never a prefix
    assert nu.former("kit/skills/verdict/SKILL.md") == ["kit/skills/idea/SKILL.md"]
    assert nu.former("kit/skills/mail/SKILL.md") == []


def test_stamp_light_takes_the_old_name_too(make_ws):
    ws = make_ws(None)
    write_tree(ws, {f"{OLD}/SKILL.md": "licht\n"})          # light, but without the file that shows it
    assert run("stamp", "--light", "idea") == 0
    assert stamp(ws)["files"][f"{OLD}/SKILL.md"]["kit"] == "kit/skills/idea/SKILL.light.md"


def test_stamp_finds_a_skill_that_kept_its_old_name(make_ws):
    ws = make_ws("full", kit=R110 | R120)                  # the kit copy is the new release, the folder the old name
    files = stamp(ws)["files"]
    assert files[f"{OLD}/SKILL.md"]["kit"] == "kit/skills/verdict/SKILL.md"
    assert files[f"{OLD}/formats.md"] == {"kit": "kit/skills/verdict/formats.md", "kind": "copy", "version": "1.2.0",
                                          "sha256": nu.sha(ws / "_setup/nest/kit/skills/verdict/formats.md")}


def test_a_workspace_without_the_skill_hears_nothing_about_the_rename(make_ws, capsys):
    ws = make_ws(None)
    assert not about_the_skill(ws) and not renames(ws)
    assert run("plan") == 0
    out = capsys.readouterr().out
    assert "verdict/" not in out and "skills/idea" not in out
    assert run("rename", "kit/skills/idea") == 1 and "Nothing open" in capsys.readouterr().err


def test_a_workspace_built_from_the_new_release_has_the_new_name_only(tmp_path, monkeypatch, rename_repo):
    root = tmp_path / "workspace"
    root.mkdir()
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(root))
    new_kit = {rel: text for rel, text in (R110 | R120).items() if text is not None}
    write_tree(root / "_setup" / "nest", new_kit)
    write_tree(root, {f"{NEW}/SKILL.md": "oordeel\n", f"{NEW}/formats.md": new_kit["kit/skills/verdict/formats.md"],
                      "scripts/wiki.py": new_kit["kit/scripts/wiki.py"]})
    assert run("stamp", "--source", str(rename_repo)) == 0
    files = stamp(root)["files"]
    assert files[f"{NEW}/SKILL.md"]["kit"] == "kit/skills/verdict/SKILL.md"
    assert not [rel for rel, entry in files.items() if "idea" in rel or "idea" in entry["kit"]]
    assert stamp(root)["version"] == "1.2.0" and not nu.open_items(plan(root))


def test_the_rest_of_the_update_changes_the_files_that_name_the_command(make_ws):
    ws = make_ws("full")
    found = status(ws)
    assert found[".claude/skills/blueprint/SKILL.md"] == "merge"     # "then run /idea" is a kit change like any other
    assert found[".claude/agents/council-judge.md"] == "merge"       # not a replace while the skill has its old name here
    assert run("plan", "--json") == 0
    assert run("rename", "kit/skills/idea") == 0
    assert status(ws)[".claude/agents/council-judge.md"] == "replace"   # ... and safe once it has the new one
    assert "CLAUDE.md" not in found                       # never the updater's; the skill tells the user
    skill = (Path(nu.__file__).resolve().parent.parent / "skills/nest-update/SKILL.md").read_text(encoding="utf-8")
    assert "`rename`" in skill and "CLAUDE.md" in skill.split("`rename`", 1)[1]


def test_a_rename_never_writes_over_a_folder_of_the_users_own(make_ws, capsys):
    ws = make_ws("full")
    write_tree(ws, {f"{NEW}/SKILL.md": "my own verdict skill\n"})
    before = skills(ws)
    item, = renames(ws)
    assert item["blocked"] == [f"{NEW}/SKILL.md"]
    assert run("plan", "--json") == 0
    capsys.readouterr()
    assert run("rename", "kit/skills/idea") == 1
    err = capsys.readouterr().err
    assert "In the way" in err and "decline kit/skills/idea" in err and skills(ws) == before
    assert run("decline", "kit/skills/idea") == 0          # keeping the old name is the way out
    assert skills(ws) == before and not renames(ws)


def test_a_rename_that_fails_halfway_can_be_run_again(make_ws, monkeypatch, capsys):
    ws = make_ws("full")
    before = skills(ws)
    assert run("plan", "--json") == 0
    real, calls = nu.move_file, []

    def flaky(src, dst):
        calls.append(src)
        if len(calls) == 3:
            raise PermissionError(13, "in use by another program")
        return real(src, dst)

    monkeypatch.setattr(nu, "move_file", flaky)
    assert run("rename", "kit/skills/idea") == 1
    assert "2 file(s)" in capsys.readouterr().err
    assert len([rel for rel in stamp(ws)["files"] if rel.startswith(NEW)]) + (ws / NEW / "mine.md").is_file() == 2
    assert run("rename", "kit/skills/idea") == 0           # picks up where it stopped
    assert under_the_new_name(before) == skills(ws) and not (ws / OLD).exists()
    assert run("restore") == 0
    assert skills(ws) == before


def test_a_rename_is_one_line_in_the_table(ws, nest_repo, tmp_path, monkeypatch):
    """The table is data: a file that moves is covered by adding its two names, nothing else."""
    newer = add_release(nest_repo, tmp_path, "1.2.0", {"kit/scripts/validate.py": None,
                                                       "kit/scripts/check.py": "print('validate 3')\n"})
    point_at(ws, newer)
    (ws / "scripts/validate.py").write_text("print('validate 1')  # mine\n", encoding="utf-8")
    fresh = {item["path"]: item["status"] for item in nu.current_plan(ws, nu.load_stamp(ws), fresh=True)["items"]}
    assert fresh["scripts/validate.py"] == "removed" and fresh["scripts/check.py"] == "new"      # without the line
    monkeypatch.setitem(nu.RENAMES, "kit/scripts/validate.py", "kit/scripts/check.py")
    assert run("plan", "--json") == 0
    item, = renames(ws)
    assert (item["path"], item["to"], item["also"]) == ("scripts/validate.py", "scripts/check.py", [])
    assert "scripts/check.py" not in status(ws)
    assert run("rename", "scripts/validate.py") == 0
    assert (ws / "scripts/check.py").read_text(encoding="utf-8").endswith("# mine\n") and not (ws / "scripts/validate.py").exists()
    assert status(ws)["scripts/check.py"] == "merge"


def test_a_name_that_changed_twice_is_followed(monkeypatch):
    monkeypatch.setitem(nu.RENAMES, "kit/skills/verdict", "kit/skills/ruling")
    assert nu.renamed("kit/skills/idea/SKILL.md") == "kit/skills/ruling/SKILL.md"
    assert nu.former("kit/skills/ruling/SKILL.md") == ["kit/skills/verdict/SKILL.md", "kit/skills/idea/SKILL.md"]


# --- a rename that stops halfway: one place per file, and the next run carries on ---------------

OWN = {f"{OLD}/mine.md": "my own notes next to the skill\n", f"{OLD}/runs/2026/een idee é.md": "eigen run\n",
       f"{OLD}/zzz last.md": "the last file to move\n"}


def held(monkeypatch, name: str):
    """`name` behaves like a file another program holds open on Windows: it can be read and
    copied, and it cannot be renamed or removed. Returns a function that lets go of it."""
    real_rename, real_unlink = os.rename, os.unlink

    def rename(src, dst, *a, **k):
        if Path(src).name == name:
            raise PermissionError(13, "The process cannot access the file because it is being used by another process")
        return real_rename(src, dst, *a, **k)

    def unlink(path, *a, **k):
        if Path(path).name == name:
            raise PermissionError(13, "The process cannot access the file because it is being used by another process")
        return real_unlink(path, *a, **k)

    monkeypatch.setattr(nu.os, "rename", rename)
    monkeypatch.setattr(nu.os, "unlink", unlink)

    def let_go():
        monkeypatch.setattr(nu.os, "rename", real_rename)
        monkeypatch.setattr(nu.os, "unlink", real_unlink)
    return let_go


def in_both_places(ws: Path) -> list[str]:
    old = {p.relative_to(ws / OLD).as_posix() for p in (ws / OLD).rglob("*") if p.is_file()} if (ws / OLD).is_dir() else set()
    new = {p.relative_to(ws / NEW).as_posix() for p in (ws / NEW).rglob("*") if p.is_file()} if (ws / NEW).is_dir() else set()
    return sorted(old & new)


def test_a_file_that_cannot_be_moved_stays_in_one_place_and_the_rename_carries_on(make_ws, monkeypatch, capsys):
    ws = make_ws("full")
    write_tree(ws, OWN)
    before, stamp_before = skills(ws), json.loads((ws / "nest.json").read_text(encoding="utf-8"))
    assert run("plan", "--json") == 0
    let_go = held(monkeypatch, "reference.md")
    capsys.readouterr()
    assert run("rename", "kit/skills/idea") == 1
    err = capsys.readouterr().err
    assert f"Stopped at {OLD}/reference.md" in err and "still where it was" in err and "decline" not in err
    assert (ws / OLD / "reference.md").is_file() and not (ws / NEW / "reference.md").exists()   # never a copy
    assert in_both_places(ws) == []
    files = stamp(ws)["files"]
    assert files[f"{NEW}/SKILL.md"]["kit"] == "kit/skills/verdict/SKILL.md"      # recorded as it went
    assert files[f"{OLD}/reference.md"]["kit"] == "kit/skills/idea/reference.md"
    item, = renames(ws)                                    # still open, and it knows it was begun
    assert item["half"] and item["blocked"] == [] and [f"{OLD}/reference.md", f"{NEW}/reference.md"] in item["moves"]
    assert set(item["also"]) == set(OWN)
    state = skills(ws)
    assert run("decline", "kit/skills/idea") == 1          # keeping the old name now would split the skill
    assert "restore" in capsys.readouterr().err and skills(ws) == state
    let_go()
    assert run("rename", "kit/skills/idea") == 0           # the same command, once the file is free
    assert skills(ws) == under_the_new_name(before) and not (ws / OLD).exists() and not renames(ws)
    assert "renaming" not in stamp(ws)
    assert run("restore") == 0
    assert skills(ws) == before and not (ws / NEW).exists()
    assert json.loads((ws / "nest.json").read_text(encoding="utf-8")) == stamp_before


def test_undo_right_after_a_rename_that_stopped(make_ws, monkeypatch):
    ws = make_ws("full")
    write_tree(ws, OWN)
    before, stamp_before = skills(ws), json.loads((ws / "nest.json").read_text(encoding="utf-8"))
    assert run("plan", "--json") == 0
    held(monkeypatch, "reference.md")
    assert run("rename", "kit/skills/idea") == 1
    assert run("restore") == 0
    assert skills(ws) == before and not (ws / NEW).exists()
    assert json.loads((ws / "nest.json").read_text(encoding="utf-8")) == stamp_before      # no trace of a begun rename


def test_a_rename_that_stops_at_a_file_of_the_users_own_stays_open(make_ws, monkeypatch, capsys):
    ws = make_ws("full")
    write_tree(ws, OWN)
    (ws / OLD / "empty/deeper").mkdir(parents=True)        # an empty folder is not worth keeping the old name for
    before = skills(ws)
    assert run("plan", "--json") == 0
    let_go = held(monkeypatch, "een idee é.md")            # every recorded file moves first, then this one fails
    assert run("rename", "kit/skills/idea") == 1
    assert not [rel for rel in stamp(ws)["files"] if rel.startswith(OLD)]
    item, = renames(ws)                                    # nothing recorded is left, and it is still one open rename
    assert item["half"] and item["also"] == [f"{OLD}/runs/2026/een idee é.md", f"{OLD}/zzz last.md"]
    capsys.readouterr()
    assert run("plan") == 0 and "has a new name in NEST" in capsys.readouterr().out
    assert run("finish") == 0 and stamp(ws)["version"] == "1.1.0"      # and it keeps the update open
    let_go()
    assert run("rename", OLD) == 0
    assert skills(ws) == under_the_new_name(before)        # the file in the subfolder and the last one too
    assert not (ws / OLD).exists() and not renames(ws)     # the empty folders went with it
    assert run("rename", OLD) == 1 and "Nothing open" in capsys.readouterr().err


class Killed(BaseException):
    """The process is gone: nothing after this runs, not even a `finally` that saves."""


@pytest.mark.parametrize("way", ["again", "undo"])
@pytest.mark.parametrize("when", ["before the move", "after the move"])
@pytest.mark.parametrize("nth", [1, 3, 4, 5, 7])
def test_a_rename_that_is_killed_between_two_moves(make_ws, monkeypatch, nth, when, way):
    ws = make_ws("full")
    write_tree(ws, OWN)
    before, stamp_before = skills(ws), json.loads((ws / "nest.json").read_text(encoding="utf-8"))
    assert run("plan", "--json") == 0
    real, calls = nu.move_file, []

    def dies(src, dst):
        calls.append(src)
        if len(calls) == nth and when == "after the move":
            real(src, dst)                                 # the file is at its new place, its record is not written
        if len(calls) == nth:
            raise Killed()
        return real(src, dst)

    monkeypatch.setattr(nu, "move_file", dies)
    with pytest.raises(Killed):
        run("rename", "kit/skills/idea")
    monkeypatch.setattr(nu, "move_file", real)
    assert in_both_places(ws) == []
    item, = renames(ws)                                    # whatever is left, the plan still shows the rename
    assert item["half"] and item["blocked"] == []
    if way == "again":
        assert run("rename", "kit/skills/idea") == 0
        assert skills(ws) == under_the_new_name(before) and not (ws / OLD).exists() and not renames(ws)
        files = stamp(ws)["files"]
        assert not [rel for rel in files if rel.startswith(OLD)] and "renaming" not in stamp(ws)
        assert {rel: entry["kit"] for rel, entry in files.items() if rel.startswith(NEW)} == {
            f"{NEW}/{name}": f"kit/skills/verdict/{name}" for name in ("SKILL.md", "formats.md", "reference.md", "old-notes.md")}
    assert run("restore") == 0
    assert skills(ws) == before and not (ws / NEW).exists()     # no empty folder of the new name either
    assert json.loads((ws / "nest.json").read_text(encoding="utf-8")) == stamp_before


def test_the_same_file_at_both_places_is_not_the_users_own(make_ws, capsys):
    """What an updater that copied and then could not delete left behind: the run goes on."""
    ws = make_ws("full")
    before = skills(ws)
    write_tree(ws, {f"{NEW}/reference.md": R110["kit/skills/idea/reference.md"]})
    item, = renames(ws)
    assert item["blocked"] == []
    assert run("plan", "--json") == 0
    assert run("rename", "kit/skills/idea") == 0
    assert skills(ws) == under_the_new_name(before) and not (ws / OLD).exists()
    assert stamp(ws)["files"][f"{NEW}/reference.md"]["kit"] == "kit/skills/verdict/reference.md"
    assert run("restore") == 0
    assert skills(ws) == before | {f"{NEW}/reference.md": R110["kit/skills/idea/reference.md"].encode()}


def test_a_file_in_the_way_of_a_begun_rename_is_named_without_pointing_at_decline(make_ws, monkeypatch, capsys):
    ws = make_ws("full")
    assert run("plan", "--json") == 0
    let_go = held(monkeypatch, "reference.md")
    assert run("rename", "kit/skills/idea") == 1
    let_go()
    write_tree(ws, {f"{NEW}/reference.md": "something else, put here by the user meanwhile\n"})
    state = skills(ws)
    capsys.readouterr()
    assert run("rename", "kit/skills/idea") == 1
    err = capsys.readouterr().err
    assert f"In the way: {NEW}/reference.md" in err and "restore" in err and "decline" not in err
    assert skills(ws) == state


def test_empty_folders_of_the_old_name_go_and_links_are_named(make_ws, tmp_path, capsys):
    ws = make_ws("full")
    outside = tmp_path / "outside"
    write_tree(outside, {"secret.md": "not NEST's\n", "folder/x.md": "x\n"})
    (ws / OLD / "empty/deeper").mkdir(parents=True)
    assert run("plan", "--json") == 0
    capsys.readouterr()
    assert run("rename", "kit/skills/idea") == 0
    assert "Left in place" not in capsys.readouterr().out and not (ws / OLD).exists()
    assert run("restore") == 0
    try:
        (ws / OLD / "link.md").symlink_to(outside / "secret.md")
        (ws / OLD / "linked").symlink_to(outside / "folder", target_is_directory=True)
    except OSError:
        pytest.skip("symbolic links need extra rights here")
    item, = renames(ws)
    assert item["links"] == [f"{OLD}/link.md", f"{OLD}/linked"] and not [m for m in item["moves"] if "link" in m[0]]
    assert run("plan", "--json") == 0
    capsys.readouterr()
    assert run("rename", "kit/skills/idea") == 0
    out = capsys.readouterr().out
    assert "Left in place" in out and f"{OLD}/link.md" in out and f"{OLD}/linked" in out
    assert (ws / OLD / "link.md").is_symlink() and (ws / OLD / "linked").is_symlink() and not (ws / NEW / "linked").exists()
    assert (outside / "secret.md").read_text(encoding="utf-8") == "not NEST's\n" and (outside / "folder/x.md").is_file()
    assert not renames(ws)                                 # a link does not keep the rename open


@pytest.mark.parametrize("which", ["old", "new"])
def test_a_rename_never_goes_through_a_link(make_ws, tmp_path, capsys, which):
    ws = make_ws("full")
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        if which == "old":
            shutil.move(str(ws / OLD), str(outside / "idea"))
            (ws / OLD).symlink_to(outside / "idea", target_is_directory=True)
        else:
            (ws / NEW).symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symbolic links need extra rights here")
    there = sorted(p.relative_to(outside).as_posix() for p in outside.rglob("*"))
    assert run("plan", "--json") == 0
    capsys.readouterr()
    stamp_before = (ws / "nest.json").read_bytes()
    assert run("rename", "kit/skills/idea") == 1
    assert "symbolic link" in capsys.readouterr().err
    assert (ws / "nest.json").read_bytes() == stamp_before and not (ws / nu.HISTORY_DIR).exists()   # refused before it began
    assert sorted(p.relative_to(outside).as_posix() for p in outside.rglob("*")) == there
    assert (ws / OLD / "SKILL.md").is_file()


# --- what an updater from before the rename table left in the stamp ------------------------------

def declined_by_the_old_updater(ws: Path) -> None:
    """The 1.1.0 updater showed the renamed skill as dropped files plus new ones. A user who said
    "keep mine, I do not need the new one" got exactly these records from its `decline`."""
    data = json.loads((ws / "nest.json").read_text(encoding="utf-8"))
    latest = Path(plan(ws)["latest_dir"])
    data["nest"]["declined"] = {
        **{f"kit/skills/idea/{name}": "removed" for name in ("SKILL.md", "formats.md", "reference.md", "old-notes.md")},
        **{f"kit/skills/verdict/{name}": nu.sha(latest / "kit/skills/verdict" / name)
           for name in ("SKILL.md", "formats.md", "reference.md", "seats.md")}}
    (ws / "nest.json").write_text(json.dumps(data), encoding="utf-8")


@pytest.mark.parametrize("choice, folder", [("rename", NEW), ("decline", OLD)])
def test_an_earlier_no_under_either_name_does_not_hide_the_merge(make_ws, choice, folder):
    ws = make_ws("full")
    declined_by_the_old_updater(ws)
    assert len(renames(ws)) == 1                           # the rename is offered all the same
    assert run("plan", "--json") == 0
    assert run(choice, "kit/skills/idea") == 0
    found = status(ws)
    assert found[f"{folder}/SKILL.md"] == "merge" and found[f"{folder}/reference.md"] == "replace"
    assert found[f"{folder}/seats.md"] == "new" and found[f"{folder}/old-notes.md"] == "removed"
    assert not [key for key in stamp(ws)["declined"] if "skills/idea" in key or "skills/verdict" in key]


# --- the name line belongs to the rename ---------------------------------------------------------

def test_the_name_line_of_a_renamed_skill_is_its_folder_name(make_ws):
    ws = make_ws("full")
    mine = "﻿---\r\ndescription: \"name: idea, in a sentence\"\r\nname:  'idea'  \r\n---\r\nBeoordeel het idee.\r\nname: idea\r\n"
    (ws / OLD / "SKILL.md").write_bytes(mine.encode("utf-8"))
    assert run("plan", "--json") == 0
    assert run("rename", "kit/skills/idea") == 0
    assert (ws / NEW / "SKILL.md").read_bytes() == mine.replace("name:  'idea'  \r\n", "name:  'verdict'  \r\n").encode("utf-8")
    assert status(ws)[f"{NEW}/SKILL.md"] == "merge"        # what NEST changed in it is still to come
    assert run("restore") == 0
    assert (ws / OLD / "SKILL.md").read_bytes() == mine.encode("utf-8")


def test_only_the_frontmatter_name_of_a_skill_file_is_touched(tmp_path):
    path = tmp_path / "SKILL.md"
    for text in ("no frontmatter\nname: idea\n", "---\ndescription: x\n---\nname: idea\n"):
        path.write_bytes(text.encode())
        assert nu.set_skill_name(path, "idea", "verdict") == "left" and path.read_bytes() == text.encode()
    path.write_bytes(b"---\nname: verdict\n---\nx\n")
    assert nu.set_skill_name(path, "idea", "verdict") == "already" and path.read_bytes() == b"---\nname: verdict\n---\nx\n"
    path.write_bytes(b"---\nname: idea\ndescription: x\n---\nbody\n")
    assert nu.set_skill_name(path, "idea", "verdict") == "set"
    assert path.read_bytes() == b"---\nname: verdict\ndescription: x\n---\nbody\n"
    assert nu.skill_folder_name(".claude/skills/verdict/SKILL.md") == "verdict"
    assert nu.skill_folder_name(".claude/skills/verdict/reference.md") is None and nu.skill_folder_name("scripts/SKILL.md") is None


@pytest.mark.parametrize("line, after", [
    (b"name: idea  # the council", b"name: verdict  # the council"),     # the rest of the line stays
    (b'name:\t"idea"   # mine', b'name:\t"verdict"   # mine'),
    (b"name:   'idea'", b"name:   'verdict'"),
    (b"name:idea", b"name:verdict"),
])
def test_the_name_line_keeps_everything_but_the_name(tmp_path, line, after):
    path = tmp_path / "SKILL.md"
    path.write_bytes(b"---\r\ndescription: x\r\n" + line + b"\r\n---\r\nbody\r\n")
    assert nu.set_skill_name(path, "idea", "verdict") == "set"
    assert path.read_bytes() == b"---\r\ndescription: x\r\n" + after + b"\r\n---\r\nbody\r\n"


@pytest.mark.parametrize("line", [b"name: idee", b"name: 'my idea'", b"name:", b"name: ", b"name: ideas", b"name: idea-two",
                                  b"name: idea#1", b"description: no name at all", b"Name: idea", b"  name: idea"])
def test_a_name_that_is_not_the_old_folder_name_is_left_alone(tmp_path, line):
    path = tmp_path / "SKILL.md"
    text = b"---\n" + line + b"\n---\nbody\n"
    path.write_bytes(text)
    assert nu.set_skill_name(path, "idea", "verdict") == "left" and path.read_bytes() == text


def test_a_rename_says_when_it_left_the_name_line(make_ws, capsys):
    ws = make_ws("full")
    mine = MY_SKILL.replace("name: idea", "name: idee  # zo heet hij bij mij")
    (ws / OLD / "SKILL.md").write_text(mine, encoding="utf-8")
    assert run("plan", "--json") == 0
    capsys.readouterr()
    assert run("rename", "kit/skills/idea") == 0
    out = capsys.readouterr().out
    assert (ws / NEW / "SKILL.md").read_text(encoding="utf-8") == mine      # a name of the user's own is theirs
    assert "name:" in out and "left as it is" in out and f"{NEW}/SKILL.md" in out
    ws2 = ws.parent / "second"
    ws.rename(ws2)                                         # the ordinary case says nothing about it
    ws = make_ws("full")
    assert run("plan", "--json") == 0
    capsys.readouterr()
    assert run("rename", "kit/skills/idea") == 0 and "left as it is" not in capsys.readouterr().out


def test_a_declined_rename_keeps_the_name_line(make_ws):
    ws = make_ws("full")
    before = skills(ws)
    assert run("plan", "--json") == 0
    assert run("decline", "kit/skills/idea") == 0
    assert skills(ws) == before


# --- a part installed somewhere of its own -------------------------------------------------------

def test_a_skill_under_a_translated_folder_name_is_not_asked_about(make_ws, capsys):
    ws = make_ws(None)
    write_tree(ws, {".claude/skills/idee/SKILL.md": MY_SKILL.replace("name: idea", "name: idee"),
                    ".claude/skills/idee/formats.md": R110["kit/skills/idea/formats.md"],
                    ".claude/skills/idee/reference.md": R110["kit/skills/idea/reference.md"]})
    assert run("stamp", *(arg for name in ("SKILL.md", "formats.md", "reference.md")
                          for arg in ("--map", f".claude/skills/idee/{name}=kit/skills/idea/{name}"))) == 0
    before = skills(ws)
    assert not renames(ws)                                 # nothing changes for this user: no question
    found = {item["path"]: (item["status"], item["kit"]) for item in plan(ws)["items"] if "idee" in str(item["path"])}
    assert found == {".claude/skills/idee/SKILL.md": ("merge", "kit/skills/verdict/SKILL.md"),
                     ".claude/skills/idee/formats.md": ("unchanged", "kit/skills/verdict/formats.md"),
                     ".claude/skills/idee/reference.md": ("replace", "kit/skills/verdict/reference.md"),
                     ".claude/skills/idee/seats.md": ("new", "kit/skills/verdict/seats.md")}
    assert run("plan") == 0
    out = capsys.readouterr().out
    assert "new name" not in out and "no longer in NEST" not in out
    assert run("rename", "kit/skills/idea") == 1 and skills(ws) == before
    capsys.readouterr()
    assert run("diff", "kit/skills/verdict/SKILL.md") == 0
    assert "NEST 1.1.0/kit/skills/idea/SKILL.md" in capsys.readouterr().out
    assert run("apply", ".claude/skills/idee/reference.md") == 0       # the stamp follows the new kit path as it goes
    assert stamp(ws)["files"][".claude/skills/idee/reference.md"]["kit"] == "kit/skills/verdict/reference.md"
    assert not (ws / NEW).exists() and not (ws / OLD).exists()


def test_a_recorded_file_under_another_name_moves_with_its_folder(make_ws):
    ws = make_ws("full")
    shutil.move(str(ws / OLD / "formats.md"), str(ws / OLD / "formaten.md"))
    data = json.loads((ws / "nest.json").read_text(encoding="utf-8"))
    data["nest"]["files"][f"{OLD}/formaten.md"] = data["nest"]["files"].pop(f"{OLD}/formats.md")
    (ws / "nest.json").write_text(json.dumps(data), encoding="utf-8")
    item, = renames(ws)
    assert [f"{OLD}/formaten.md", f"{NEW}/formaten.md"] in item["moves"] and f"{OLD}/formaten.md" not in item["also"]
    assert run("plan", "--json") == 0
    assert run("rename", "kit/skills/idea") == 0
    assert not (ws / OLD).exists() and (ws / NEW / "formaten.md").is_file()
    assert stamp(ws)["files"][f"{NEW}/formaten.md"]["kit"] == "kit/skills/verdict/formats.md"
    assert status(ws)[f"{NEW}/formaten.md"] == "unchanged"


def test_a_later_rename_of_a_part_that_kept_its_old_name_is_not_asked_about(make_ws, rename_repo, tmp_path, monkeypatch):
    ws = make_ws("full")
    assert run("plan", "--json") == 0
    assert run("decline", "kit/skills/idea") == 0
    monkeypatch.setitem(nu.RENAMES, "kit/skills/verdict", "kit/skills/ruling")
    newer = add_release(rename_repo, tmp_path, "1.3.0", {
        "SETUP.md": "# NEST setup prompt\n\nVersion 1.3.0 · New Environment Setup Toolkit\n",
        **{rel: None for rel in R120 if rel.startswith("kit/skills/verdict/")},
        "kit/skills/ruling/SKILL.md": "---\nname: ruling\n---\nJudge the idea, and rule.\n",
        "kit/skills/ruling/formats.md": "full formats\n", "kit/skills/ruling/reference.md": "reference 2\n"})
    point_at(ws, newer)
    items = nu.current_plan(ws, nu.load_stamp(ws), fresh=True)["items"]
    assert "rename" not in {item["status"] for item in items}
    found = {item["path"]: (item["status"], item["kit"]) for item in items if OLD in str(item["path"])}
    assert found[f"{OLD}/SKILL.md"] == ("merge", "kit/skills/ruling/SKILL.md")
    assert found[f"{OLD}/formats.md"] == ("unchanged", "kit/skills/ruling/formats.md")


def test_stamp_leaves_a_skill_of_the_users_own_with_an_old_name_alone(tmp_path, monkeypatch, rename_repo):
    root = tmp_path / "workspace"
    root.mkdir()
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(root))
    new_kit = {rel: text for rel, text in (R110 | R120).items() if text is not None}
    write_tree(root / "_setup" / "nest", new_kit)
    write_tree(root, {f"{OLD}/SKILL.md": "---\nname: idea\n---\nMy own skill for jotting ideas down.\n",
                      f"{OLD}/reference.md": "my own reference\n", "scripts/wiki.py": new_kit["kit/scripts/wiki.py"]})
    assert run("stamp", "--source", str(rename_repo)) == 0
    assert list(stamp(root)["files"]) == ["scripts/wiki.py"]          # nothing in it was made from the kit
    write_tree(root, {f"{OLD}/formats.md": new_kit["kit/skills/verdict/formats.md"]})
    assert run("stamp") == 0                               # one file that is the kit's own: this is the kit's skill
    assert stamp(root)["files"][f"{OLD}/SKILL.md"]["kit"] == "kit/skills/verdict/SKILL.md"


def test_a_renamed_wiki_file_is_compared_with_its_old_name(ws, nest_repo, tmp_path, monkeypatch):
    monkeypatch.setitem(nu.RENAMES, "kit/wiki/_templates/note.md", "kit/wiki/_templates/page.md")
    same = add_release(nest_repo, tmp_path, "1.2.0", {"kit/wiki/_templates/note.md": None,
                                                      "kit/wiki/_templates/page.md": V100["kit/wiki/_templates/note.md"]})
    point_at(ws, same)
    found = {item["kit"]: item["status"] for item in nu.current_plan(ws, nu.load_stamp(ws), fresh=True)["items"]}
    assert "kit/wiki/_templates/page.md" not in found      # another name, the same text: nothing to tell
    changed = add_release(nest_repo, tmp_path, "1.3.0", {"kit/wiki/_templates/note.md": None,
                                                         "kit/wiki/_templates/page.md": "note template 3\n"})
    point_at(ws, changed)
    found = {item["kit"]: item["status"] for item in nu.current_plan(ws, nu.load_stamp(ws), fresh=True)["items"]}
    assert found["kit/wiki/_templates/page.md"] == "wiki"


# --- what the review of the rename asked for ----------------------------------------------------

def untouched(ws: Path, source: Path) -> None:
    """The skill file and a file of another skill exactly as the kit has them, recorded as copies."""
    write_tree(ws, {f"{OLD}/SKILL.md": R110["kit/skills/idea/SKILL.md"],
                    ".claude/skills/blueprint/reference.md": R110["kit/skills/blueprint/reference.md"]})
    assert run("stamp", "--map", f"{OLD}/SKILL.md=kit/skills/idea/SKILL.md") == 0
    files = stamp(ws)["files"]
    assert files[f"{OLD}/SKILL.md"]["kind"] == files[".claude/skills/blueprint/reference.md"]["kind"] == "copy"


@pytest.mark.parametrize("decided", ["kept the old name", "not decided yet"])
def test_a_workspace_with_the_old_name_never_gets_the_new_one_from_the_script(make_ws, rename_repo, capsys, decided):
    ws = make_ws("full")
    untouched(ws, rename_repo)
    assert run("plan", "--json") == 0
    if decided == "kept the old name":
        assert run("decline", "kit/skills/idea") == 0
    here = OLD if decided == "kept the old name" else NEW
    found = {item["path"]: item for item in plan(ws)["items"] if item["path"]}
    other = found[".claude/skills/blueprint/reference.md"]
    assert other["status"] == "merge" and other["name_kept"] == "kit/skills/idea"      # it points at ../verdict/
    if decided == "kept the old name":
        own = found[f"{OLD}/SKILL.md"]
        assert own["status"] == "merge" and own["name_kept"] == "kit/skills/idea"      # its name: line is the new name
        assert found[f"{OLD}/reference.md"]["status"] == "replace" and "name_kept" not in found[f"{OLD}/reference.md"]
    before = skills(ws)
    capsys.readouterr()
    for path in (".claude/skills/blueprint/reference.md", *([f"{OLD}/SKILL.md"] if here == OLD else [])):
        assert run("apply", path) == 1
        err = capsys.readouterr().err
        assert "`verdict` where it said `idea`" in err and "changed in this workspace" not in err
        if decided == "kept the old name":                 # the name stays: the change is carried in by hand
            assert "by hand and leave the name as it is" in err and "mark " in err and "rename" not in err
        else:                                              # the rename is still open: it comes first, no hand merge
            assert "Run `rename kit/skills/idea` first" in err and "ordinary replace" in err
            assert "Do not merge it by hand" in err and "mark " not in err
    assert skills(ws) == before
    assert not [rel for rel, data in before.items() if b"../verdict/" in data or b"name: verdict" in data]
    if decided == "kept the old name":
        assert run("apply", f"{OLD}/reference.md") == 0    # a change that does not name the part is still safe
        # carried in by hand with the name left as it is, and it is level
        assert run("backup", ".claude/skills/blueprint/reference.md") == 0
        (ws / ".claude/skills/blueprint/reference.md").write_text(
            "The idea page is specified in `../idea/reference.md`.\nSection 11, revised.\n", encoding="utf-8")
        assert run("mark", ".claude/skills/blueprint/reference.md=kit/skills/blueprint/reference.md") == 0
        assert status(ws)[".claude/skills/blueprint/reference.md"] == "unchanged"


def test_a_file_that_waits_for_a_half_done_rename_says_to_finish_it(make_ws, rename_repo, monkeypatch, capsys):
    ws = make_ws("full")
    untouched(ws, rename_repo)
    assert run("plan", "--json") == 0
    held(monkeypatch, "old-notes.md")
    assert run("rename", "kit/skills/idea") == 1           # stopped halfway
    before = skills(ws)
    capsys.readouterr()
    assert run("apply", ".claude/skills/blueprint/reference.md") == 1
    err = capsys.readouterr().err
    assert "Finish the rename first, `rename kit/skills/idea`" in err and "ordinary replace" in err
    assert "Do not merge it by hand" in err and "mark " not in err and skills(ws) == before


def test_the_skill_text_puts_the_rename_before_the_merges():
    skill = (Path(nu.__file__).resolve().parent.parent / "skills/nest-update/SKILL.md").read_text(encoding="utf-8")
    step4 = skill.split("## 4. Merges and new parts", 1)[1].split("\n## ", 1)[0]
    assert step4.index("### A part with a new name") < step4.index("For each `merge` item")
    assert "never merged by hand while the rename" in step4.split("### A part with a new name", 1)[0]
    step3 = skill.split("## 3. A restore point", 1)[1].split("\n## ", 1)[0]
    assert step3.index("A part with a new name") < step3.index("Safe replacements")


def test_after_the_rename_a_file_that_names_the_part_is_safe_to_replace(make_ws, rename_repo):
    ws = make_ws("full")
    untouched(ws, rename_repo)
    assert run("plan", "--json") == 0
    assert run("rename", "kit/skills/idea") == 0
    item = next(i for i in plan(ws)["items"] if i["path"] == ".claude/skills/blueprint/reference.md")
    assert item["status"] == "replace" and "name_kept" not in item
    assert run("apply", ".claude/skills/blueprint/reference.md") == 0
    assert "../verdict/reference.md" in (ws / ".claude/skills/blueprint/reference.md").read_text(encoding="utf-8")


def test_a_deleted_file_is_not_brought_back_with_the_new_name_either(make_ws, rename_repo, capsys):
    ws = make_ws("full")
    untouched(ws, rename_repo)
    assert run("plan", "--json") == 0
    assert run("decline", "kit/skills/idea") == 0
    (ws / ".claude/skills/blueprint/reference.md").unlink()
    capsys.readouterr()
    assert run("apply", ".claude/skills/blueprint/reference.md") == 1
    assert "old name" in capsys.readouterr().err and not (ws / ".claude/skills/blueprint/reference.md").exists()


def test_which_changes_name_a_renamed_part():
    names = ("kit/skills/idea", "kit/skills/verdict")
    assert nu.names_the_rename("---\nname: idea\n---\nJudge the idea.\n", "---\nname: verdict\n---\nJudge the idea.\n", *names)
    assert nu.names_the_rename("See `../idea/reference.md`.\n", "See `../verdict/reference.md`.\n", *names)
    assert nu.names_the_rename("x\nFor the idea skill.\ny\n", "x\nFor the verdict skill.\ny, changed\n", *names)
    assert nu.names_the_rename(None, "Then run /verdict.\n", *names)                    # nothing to compare with: any mention
    assert not nu.names_the_rename(None, "Then run it.\n", *names)
    assert not nu.names_the_rename("The idea gets a verdict.\n", "The idea gets a verdict and a score.\n", *names)
    assert not nu.names_the_rename("Judge the idea.\nA.\n", "Judge the idea.\nA verdict follows.\n", *names)   # a new line, nothing replaced
    assert not nu.names_the_rename("The idea-note snippet, idea_page.py.\n", "The verdict-note snippet, verdict_page.py.\n", *names)
    assert not nu.names_the_rename("same\n", "same\n", *names)


def test_a_rename_that_stopped_before_the_first_file_is_not_begun(make_ws, monkeypatch, capsys):
    ws = make_ws("full")
    before, stamp_before = skills(ws), stamp(ws)
    assert run("plan", "--json") == 0
    let_go = held(monkeypatch, "SKILL.md")                 # the first file of the part
    capsys.readouterr()
    assert run("rename", "kit/skills/idea") == 1
    err = capsys.readouterr().err
    assert "Nothing was moved" in err and skills(ws) == before and not (ws / NEW).exists()
    assert "renaming" not in stamp(ws) and stamp(ws)["files"] == stamp_before["files"]
    item, = renames(ws)                                    # the ordinary offer again, not a half rename
    assert not item["half"] and "decline kit/skills/idea" in item["how"]
    assert run("decline", "kit/skills/idea") == 0          # so the old name can still be kept
    assert skills(ws) == before and not renames(ws)
    let_go()


def test_the_text_plan_says_when_a_rename_is_half_done(make_ws, monkeypatch, capsys):
    ws = make_ws("full")
    assert run("plan") == 0
    assert "begun" not in capsys.readouterr().out          # an ordinary offer has no such line
    held(monkeypatch, "reference.md")
    assert run("rename", "kit/skills/idea") == 1
    capsys.readouterr()
    assert run("plan") == 0
    out = capsys.readouterr().out
    assert "has a new name in NEST" in out and "begun and not finished" in out
    assert "`rename kit/skills/idea`" in out and "restore" in out


def test_a_script_is_never_held_back_for_a_name(make_ws, rename_repo):
    """Scripts read both names of a part, so a new version that says the new name is still a plain replace."""
    ws = make_ws("full")
    write_tree(ws, {"scripts/idea_page.py": R110["kit/scripts/idea_page.py"]})
    assert run("stamp") == 0
    assert run("plan", "--json") == 0
    assert run("decline", "kit/skills/idea") == 0
    item = next(i for i in plan(ws)["items"] if i["path"] == "scripts/idea_page.py")
    assert item["status"] == "replace" and "name_kept" not in item
    assert run("apply", "scripts/idea_page.py") == 0
