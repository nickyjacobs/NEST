"""Tests for nest_update.py: a fake NEST repo with two releases and a workspace built from the first."""
from __future__ import annotations

import json
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
    assert files["scripts/wiki.py"] == {"kit": "kit/scripts/wiki.py", "kind": "copy",
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
