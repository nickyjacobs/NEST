"""Tests for wiki_backup.py: real temporary git repositories, a bare one as the remote.

No test depends on the machine's git configuration: the global and system files are switched
off through the environment, and every repository gets its identity and branch name locally.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import wiki_backup as wb

SCRIPT = Path(wb.__file__)
IDENTITY = ("-c", "user.name=Test Person", "-c", "user.email=test@example.com")


def git(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True, encoding="utf-8")
    return result.stdout.strip()


def write(path: Path, text: str = "body\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def isolated_git(tmp_path_factory, monkeypatch):
    """An empty global config and no system config, so only what a test sets counts."""
    empty = tmp_path_factory.mktemp("gitconfig") / "global"
    empty.write_text("", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_TERMINAL_PROMPT", "0")
    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL",
                 "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL", "EMAIL", "NEST_WIKI_CONFIG"):
        monkeypatch.delenv(name, raising=False)
    return empty


@pytest.fixture
def ws(tmp_path, monkeypatch):
    """A workspace with a wiki folder; the script finds it through $CLAUDE_PROJECT_DIR."""
    root = tmp_path / "ws"
    (root / "wiki").mkdir(parents=True)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(root))
    monkeypatch.chdir(root)
    return root


@pytest.fixture
def remote(tmp_path) -> Path:
    path = tmp_path / "remote.git"
    git("init", "-q", "--bare", "-b", "main", str(path))
    return path


@pytest.fixture
def gd(tmp_path, ws) -> Path:
    """The backup's git directory, recorded in nest.json and not created yet."""
    path = tmp_path / "store" / "wiki.git"
    (ws / "nest.json").write_text(json.dumps({"wiki_backup": {"git_dir": str(path)}}), encoding="utf-8")
    return path


def prepare(gd: Path, wiki: Path, branch: str = "main") -> None:
    """Create the git directory by hand with a local identity, as a user's machine would have."""
    gd.parent.mkdir(parents=True, exist_ok=True)
    git(f"--git-dir={gd}", f"--work-tree={wiki}", "init", "-q", "-b", branch)
    git(f"--git-dir={gd}", "config", "user.name", "Test Person")
    git(f"--git-dir={gd}", "config", "user.email", "test@example.com")


@pytest.fixture
def backup(ws, gd, remote) -> wb.Backup:
    """An initialised backup with one pushed commit."""
    write(ws / "wiki/notes/a.md")
    prepare(gd, ws / "wiki")
    assert wb.main(["init", str(remote), "--yes"]) == 0
    return wb.Backup(gd, ws / "wiki")


def remote_head(remote: Path, branch: str = "main") -> str:
    return git(f"--git-dir={remote}", "rev-parse", "-q", "--verify", f"refs/heads/{branch}")


def remote_files(remote: Path, branch: str = "main") -> list[str]:
    return git(f"--git-dir={remote}", "-c", "core.quotepath=false", "ls-tree", "-r", "--name-only", branch).splitlines()


def other_device_pushes(remote: Path, tmp_path: Path) -> str:
    """A second machine adds a commit to the remote; returns the new remote head."""
    clone = tmp_path / "other-device"
    git("clone", "-q", str(remote), str(clone))
    write(clone / "elsewhere.md")
    git("add", "-A", cwd=clone)
    git(*IDENTITY, "commit", "-q", "-m", "From another device", cwd=clone)
    git("push", "-q", "origin", "HEAD:main", cwd=clone)
    return remote_head(remote)


# --- configuration ---------------------------------------------------------------------------

def test_defaults_without_any_config(ws, monkeypatch, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    b = wb.Backup.from_config(ws, None, None)
    assert b.wiki == ws / "wiki"
    assert b.git_dir == home / ".ws-wiki.git"
    assert b.branch == "main"


def test_nest_json_and_wiki_config_are_used(ws, tmp_path):
    (ws / "wiki.config.json").write_text(json.dumps({"wiki_dir": "vault"}), encoding="utf-8")
    (ws / "nest.json").write_text(json.dumps({"wiki_backup": {"git_dir": str(tmp_path / "g.git"), "branch": "trunk"}}),
                                  encoding="utf-8")
    b = wb.Backup.from_config(ws, None, None)
    assert (b.git_dir, b.wiki, b.branch) == (tmp_path / "g.git", ws / "vault", "trunk")


def test_wiki_config_is_found_upwards_and_through_env(ws, tmp_path, monkeypatch):
    (ws / "wiki.config.json").write_text(json.dumps({"wiki_dir": "vault"}), encoding="utf-8")
    sub = ws / "deep" / "er"
    sub.mkdir(parents=True)
    assert wb.Backup.from_config(sub, None, None).wiki == ws.resolve() / "vault"

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "custom.json").write_text(json.dumps({"wiki_dir": "kb"}), encoding="utf-8")
    monkeypatch.setenv("NEST_WIKI_CONFIG", str(elsewhere / "custom.json"))
    assert wb.Backup.from_config(ws, None, None).wiki == elsewhere / "kb"
    monkeypatch.setenv("NEST_WIKI_CONFIG", str(elsewhere / "missing.json"))
    assert wb.Backup.from_config(ws, None, None).wiki == ws / "wiki"


def test_command_line_overrides_config(ws, gd, tmp_path, monkeypatch):
    (ws / "wiki.config.json").write_text(json.dumps({"wiki_dir": "vault"}), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    b = wb.Backup.from_config(ws, str(tmp_path / "cli.git"), "notes")
    assert b.git_dir == tmp_path / "cli.git"
    assert b.wiki == Path.cwd() / "notes"
    assert wb.Backup.from_config(ws, None, str(tmp_path / "abs")).wiki == tmp_path / "abs"


def test_relative_git_dir_is_anchored(ws, tmp_path, monkeypatch, remote):
    # git runs with the wiki as its directory, so a relative git dir must not be left relative.
    (ws / "nest.json").write_text(json.dumps({"wiki_backup": {"git_dir": "store/w.git"}}), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert wb.Backup.from_config(ws, None, None).git_dir == ws / "store" / "w.git"
    assert wb.Backup.from_config(ws, "cli.git", None).git_dir == Path.cwd() / "cli.git"

    write(ws / "wiki/a.md")
    prepare(tmp_path / "cli.git", ws / "wiki")
    assert wb.main(["--git-dir", "cli.git", "init", str(remote), "--yes"]) == 0
    assert wb.main(["--git-dir", "cli.git", "status"]) == 0
    assert not (ws / "wiki" / "cli.git").exists()
    assert remote_files(remote) == ["a.md"]


def test_broken_json_falls_back_to_defaults(ws):
    (ws / "nest.json").write_text("{not json", encoding="utf-8")
    (ws / "wiki.config.json").write_text("[1, 2]", encoding="utf-8")
    b = wb.Backup.from_config(ws, None, None)
    assert b.wiki == ws / "wiki" and b.branch == "main"


# --- init ------------------------------------------------------------------------------------

def test_init_creates_commits_and_pushes(ws, gd, remote, isolated_git, capsys):
    # A fresh machine: the identity comes from the (isolated) global config, the script makes the repo.
    isolated_git.write_text("[user]\n\tname = Test Person\n\temail = test@example.com\n", encoding="utf-8")
    write(ws / "wiki/notes/a.md")
    write(ws / "wiki/notes/with space.md")
    write(ws / "wiki/.obsidian/app.json", "{}")
    write(ws / "wiki/.obsidian/workspace.json", "{}")
    write(ws / "wiki/.obsidian/cache/x", "x")
    write(ws / "wiki/.trash/old.md")
    write(ws / "wiki/.DS_Store", "x")
    write(ws / "wiki/draft.tmp", "x")

    assert wb.main(["init", str(remote), "--yes"]) == 0
    out = capsys.readouterr().out
    assert f"Created {gd}" in out
    assert "The first commit will add 3 files" in out
    assert "  notes/with space.md" in out
    assert "Pushed to" in out

    assert not (ws / "wiki" / ".git").exists()
    assert sorted(remote_files(remote)) == [".obsidian/app.json", "notes/a.md", "notes/with space.md"]
    assert git(f"--git-dir={gd}", "log", "-1", "--format=%s") == "Initial wiki backup"
    assert git(f"--git-dir={gd}", "config", "core.autocrlf") == "false"
    assert git(f"--git-dir={gd}", "config", "core.quotepath") == "false"
    assert git(f"--git-dir={gd}", "symbolic-ref", "--short", "HEAD") == "main"
    assert remote_head(remote) == git(f"--git-dir={gd}", "rev-parse", "HEAD")


def test_init_uses_the_configured_branch(ws, tmp_path, remote):
    gd = tmp_path / "b.git"
    (ws / "nest.json").write_text(json.dumps({"wiki_backup": {"git_dir": str(gd), "branch": "backup"}}),
                                  encoding="utf-8")
    write(ws / "wiki/a.md")
    prepare(gd, ws / "wiki", branch="backup")
    assert wb.main(["init", str(remote), "--yes"]) == 0
    assert remote_files(remote, "backup") == ["a.md"]


def test_init_counts_a_single_file(ws, gd, remote, capsys):
    write(ws / "wiki/a.md")
    prepare(gd, ws / "wiki")
    assert wb.main(["init", str(remote), "--yes"]) == 0
    assert "will add 1 file to" in capsys.readouterr().out


def test_init_twice_keeps_one_exclude_block_and_updates_the_remote(backup, remote, tmp_path, capsys):
    capsys.readouterr()
    moved = tmp_path / "moved.git"
    assert wb.main(["init", str(moved), "--yes"]) == 1  # never repoints an existing backup by itself
    assert "--set-remote" in capsys.readouterr().err
    assert git(f"--git-dir={backup.git_dir}", "remote", "get-url", "origin") == str(remote)
    assert wb.main(["init", str(moved), "--yes", "--set-remote"]) == 0
    out = capsys.readouterr().out
    assert "already exists" in out and "already has commits" in out
    exclude = (backup.git_dir / "info" / "exclude").read_text(encoding="utf-8")
    assert exclude.count("Written by wiki_backup.py") == 1
    assert git(f"--git-dir={backup.git_dir}", "remote", "get-url", "origin") == str(moved)


def test_init_honours_a_gitignore_inside_the_wiki(ws, gd, remote):
    write(ws / "wiki/.gitignore", "private/\n")
    write(ws / "wiki/private/secret.md")
    write(ws / "wiki/a.md")
    prepare(gd, ws / "wiki")
    assert wb.main(["init", str(remote), "--yes"]) == 0
    assert sorted(remote_files(remote)) == [".gitignore", "a.md"]


@pytest.mark.parametrize("answer", ["n", "", None])
def test_init_stops_without_confirmation(ws, gd, remote, monkeypatch, capsys, answer):
    def fake_input(prompt: str = "") -> str:
        if answer is None:
            raise EOFError
        return answer
    monkeypatch.setattr("builtins.input", fake_input)
    write(ws / "wiki/a.md")
    prepare(gd, ws / "wiki")
    assert wb.main(["init", str(remote)]) == 1
    assert "Stopped before the first commit" in capsys.readouterr().out
    assert not wb.Backup(gd, ws / "wiki").has_commits()
    assert remote_head_or_none(remote) is None


def remote_head_or_none(remote: Path) -> str | None:
    r = subprocess.run(["git", f"--git-dir={remote}", "rev-parse", "-q", "--verify", "refs/heads/main"],
                       capture_output=True, text=True, check=False)
    return r.stdout.strip() or None


def test_init_commits_after_a_yes(ws, gd, remote, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt="": " Yes ")
    write(ws / "wiki/a.md")
    prepare(gd, ws / "wiki")
    assert wb.main(["init", str(remote)]) == 0
    assert remote_files(remote) == ["a.md"]


def test_init_with_an_empty_wiki(ws, gd, remote, capsys):
    assert wb.main(["init", str(remote), "--yes"]) == 0
    assert "Nothing to commit yet." in capsys.readouterr().out
    assert wb.main(["push"]) == 0
    assert "Nothing to back up yet." in capsys.readouterr().out
    assert remote_head_or_none(remote) is None


def test_init_without_wiki_folder(ws, gd, remote, capsys):
    (ws / "wiki").rmdir()
    assert wb.main(["init", str(remote), "--yes"]) == 1
    assert "No wiki folder" in capsys.readouterr().err
    assert not gd.exists()


def test_init_refuses_a_wiki_with_its_own_git_folder(ws, gd, remote, capsys):
    (ws / "wiki" / ".git").mkdir()
    assert wb.main(["init", str(remote), "--yes"]) == 1
    assert "already has a .git folder" in capsys.readouterr().err
    assert not gd.exists()


def test_init_without_identity(ws, gd, remote, capsys):
    write(ws / "wiki/a.md")
    assert wb.main(["init", str(remote), "--yes"]) == 1
    assert "user.name" in capsys.readouterr().err
    assert not wb.Backup(gd, ws / "wiki").has_commits()


# --- push ------------------------------------------------------------------------------------

def test_push_without_backup(ws, gd, capsys):
    assert wb.main(["push"]) == 1
    assert "run `wiki_backup.py init <remote-url>` first" in capsys.readouterr().err


def test_push_commits_changes_and_pushes(backup, remote, capsys):
    capsys.readouterr()
    write(backup.wiki / "notes/b.md")
    write(backup.wiki / "notes/a.md", "changed\n")
    assert wb.main(["push"]) == 0
    out = capsys.readouterr().out
    assert "Committed: Backup 20" in out and "Pushed to" in out
    assert sorted(remote_files(remote)) == ["notes/a.md", "notes/b.md"]
    assert remote_head(remote) == git(f"--git-dir={backup.git_dir}", "rev-parse", "HEAD")


def test_push_with_message_and_deletion(backup, remote):
    write(backup.wiki / "notes/b.md")
    (backup.wiki / "notes/a.md").unlink()
    assert wb.main(["push", "Tidy the notes"]) == 0
    assert git(f"--git-dir={remote}", "log", "-1", "--format=%s", "main") == "Tidy the notes"
    assert remote_files(remote) == ["notes/b.md"]


def test_push_with_nothing_new(backup, remote, capsys):
    capsys.readouterr()
    before = remote_head(remote)
    assert wb.main(["push"]) == 0
    out = capsys.readouterr().out
    assert "Committed" not in out and "Nothing to push" in out
    assert remote_head(remote) == before
    assert git(f"--git-dir={backup.git_dir}", "rev-list", "--count", "HEAD") == "1"


def test_push_skips_excluded_files(backup, remote, capsys):
    capsys.readouterr()
    write(backup.wiki / ".obsidian/workspace.json", "{}")
    write(backup.wiki / ".trash/gone.md")
    assert wb.main(["push"]) == 0
    assert "Committed" not in capsys.readouterr().out
    assert remote_files(remote) == ["notes/a.md"]


def test_push_sends_a_commit_that_stayed_local(backup, remote, capsys):
    write(backup.wiki / "b.md")
    backup.git("add", "-A")
    backup.git("commit", "-q", "-m", "Made offline")
    capsys.readouterr()
    assert wb.main(["push"]) == 0
    out = capsys.readouterr().out
    assert "Committed" not in out and "Pushed to" in out
    assert git(f"--git-dir={remote}", "log", "-1", "--format=%s", "main") == "Made offline"


def test_push_with_unreachable_remote_keeps_the_commit(backup, tmp_path, capsys):
    backup.git("remote", "set-url", "origin", str(tmp_path / "nowhere.git"))
    write(backup.wiki / "b.md")
    capsys.readouterr()
    assert wb.main(["push", "Offline work"]) == 1
    captured = capsys.readouterr()
    assert "Committed: Offline work" in captured.out
    assert "unreachable" in captured.err
    assert git(f"--git-dir={backup.git_dir}", "log", "-1", "--format=%s") == "Offline work"


def test_rejected_push_is_never_forced(backup, remote, tmp_path, capsys):
    theirs = other_device_pushes(remote, tmp_path)
    write(backup.wiki / "b.md")
    capsys.readouterr()
    assert wb.main(["push"]) == 1
    err = capsys.readouterr().err
    assert "Push rejected; nothing was forced" in err
    assert "pull --rebase origin main" in err
    assert remote_head(remote) == theirs


def test_push_without_identity(ws, gd, remote, capsys):
    write(ws / "wiki/a.md")
    gd.parent.mkdir(parents=True)
    git(f"--git-dir={gd}", f"--work-tree={ws / 'wiki'}", "init", "-q", "-b", "main")
    assert wb.main(["push"]) == 1
    assert "user.name" in capsys.readouterr().err
    assert not wb.Backup(gd, ws / "wiki").has_commits()


def test_push_reports_a_git_failure(backup, capsys):
    write(backup.wiki / "notes/b.md")
    (backup.git_dir / "index.lock").write_text("", encoding="utf-8")  # another git process, or a stopped one
    assert wb.main(["push"]) == 1
    assert "git add" in capsys.readouterr().err


# --- status ----------------------------------------------------------------------------------

def test_status_without_backup(ws, gd, capsys):
    assert wb.main(["status"]) == 1
    assert f"No backup at {gd}." in capsys.readouterr().out


def test_status_clean(backup, remote, capsys):
    capsys.readouterr()
    assert wb.main(["status"]) == 0
    out = capsys.readouterr().out
    assert f"Wiki backup {backup.git_dir} -> {remote}" in out
    assert "  0 uncommitted files" in out
    assert "  0 commits not pushed" in out


def test_status_uncommitted_files(backup, capsys):
    write(backup.wiki / "new.md")
    write(backup.wiki / "notes/a.md", "changed\n")
    write(backup.wiki / ".obsidian/workspace.json", "{}")
    capsys.readouterr()
    assert wb.main(["status"]) == 0
    out = capsys.readouterr().out
    assert "  2 uncommitted files" in out
    assert "?? new.md" in out and "M notes/a.md" in out
    assert "workspace.json" not in out

    (backup.wiki / "new.md").unlink()
    assert wb.main(["status"]) == 0
    assert "  1 uncommitted file\n" in capsys.readouterr().out


def test_status_unpushed_commits(backup, capsys):
    for name in ("b.md", "c.md"):
        write(backup.wiki / name)
        backup.git("add", "-A")
        backup.git("commit", "-q", "-m", f"Add {name}")
    capsys.readouterr()
    assert wb.main(["status"]) == 0
    out = capsys.readouterr().out
    assert "  0 uncommitted files" in out
    assert "  2 commits not pushed" in out

    assert wb.main(["push"]) == 0
    capsys.readouterr()
    assert wb.main(["status"]) == 0
    assert "  0 commits not pushed" in capsys.readouterr().out


def test_status_before_the_first_push(ws, gd, capsys):
    write(ws / "wiki/a.md")
    prepare(gd, ws / "wiki")
    assert wb.main(["status"]) == 0
    out = capsys.readouterr().out
    assert "-> no remote" in out and "  1 uncommitted file\n" in out
    assert "not pushed" not in out and "no upstream" not in out

    b = wb.Backup(gd, ws / "wiki")
    b.git("add", "-A")
    b.git("commit", "-q", "-m", "First")
    assert wb.main(["status"]) == 0
    assert "no upstream yet" in capsys.readouterr().out


# --- the script itself -----------------------------------------------------------------------

def test_cli_runs_as_a_script(ws, gd, remote, tmp_path):
    write(ws / "wiki/a.md")
    prepare(gd, ws / "wiki")
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}

    def run(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=tmp_path, env=env, check=False,
                              capture_output=True, text=True, encoding="utf-8")

    assert run("init", str(remote), "--yes").returncode == 0
    write(ws / "wiki/b.md")
    pushed = run("--git-dir", str(gd), "--wiki", str(ws / "wiki"), "push", "From the command line")
    assert pushed.returncode == 0, pushed.stderr
    assert "Committed: From the command line" in pushed.stdout
    assert sorted(remote_files(remote)) == ["a.md", "b.md"]
    status = run("status")
    assert status.returncode == 0 and "0 commits not pushed" in status.stdout
    assert run().returncode == 2


# --- real vaults: another wiki's git directory, nested repositories, an emptied folder, secrets ----

SECRET = "gh" + "p_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"  # assembled, so this file never holds it


def test_init_refuses_the_git_dir_of_another_wiki(backup, remote, tmp_path, monkeypatch, capsys):
    """Two workspaces whose folders share a name share the default git directory name."""
    other = tmp_path / "elsewhere" / "ws"
    write(other / "wiki" / "theirs.md")
    (other / "nest.json").write_text(json.dumps({"wiki_backup": {"git_dir": str(backup.git_dir)}}), encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(other))
    monkeypatch.chdir(other)
    second = tmp_path / "second.git"
    git("init", "-q", "--bare", "-b", "main", str(second))
    capsys.readouterr()
    assert wb.main(["init", str(second), "--yes"]) == 1
    err = capsys.readouterr().err
    assert "belongs to another wiki" in err and "--git-dir" in err
    assert wb.main(["push"]) == 1
    assert "belongs to another wiki" in capsys.readouterr().err
    assert wb.main(["status"]) == 1
    assert git(f"--git-dir={backup.git_dir}", "remote", "get-url", "origin") == str(remote)
    assert remote_files(remote) == ["notes/a.md"]
    assert git(f"--git-dir={second}", "for-each-ref") == ""


def test_init_rebind_takes_over_after_the_wiki_moved(backup, remote, tmp_path, monkeypatch, capsys):
    new_root = tmp_path / "renamed"
    monkeypatch.chdir(tmp_path)  # Windows cannot rename the folder a process stands in
    backup.wiki.parent.rename(new_root)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(new_root))
    monkeypatch.chdir(new_root)
    assert wb.main(["push"]) == 1
    assert "--rebind" in capsys.readouterr().err
    assert wb.main(["init", str(remote), "--rebind"]) == 0
    write(new_root / "wiki/notes/b.md")
    assert wb.main(["push"]) == 0
    assert sorted(remote_files(remote)) == ["notes/a.md", "notes/b.md"]


def test_backup_without_a_recorded_work_tree_is_adopted(backup, remote):
    git(f"--git-dir={backup.git_dir}", "config", "--unset", "core.worktree")
    write(backup.wiki / "notes/b.md")
    assert wb.main(["push"]) == 0
    assert Path(git(f"--git-dir={backup.git_dir}", "config", "core.worktree")).resolve() == backup.wiki.resolve()


def test_nested_repository_is_named_because_its_files_are_not_backed_up(backup, remote, capsys):
    inner = backup.wiki / "projects" / "cloned"
    write(inner / "notes.md")
    git("init", "-q", "-b", "main", cwd=inner)
    capsys.readouterr()
    assert wb.main(["push"]) == 0  # a repository without a commit would make a plain `git add -A` fail
    captured = capsys.readouterr()
    assert "projects/cloned" in captured.err and "not in the backup" in captured.err
    assert remote_files(remote) == ["notes/a.md"]  # left out, not stored as a pointer nobody can restore
    assert wb.main(["status"]) == 0
    assert "projects/cloned" in capsys.readouterr().out


def test_push_refuses_an_emptied_wiki(backup, remote, capsys):
    (backup.wiki / "notes/a.md").unlink()
    (backup.wiki / "notes").rmdir()
    head = remote_head(remote)
    capsys.readouterr()
    assert wb.main(["push"]) == 1
    assert "--allow-empty" in capsys.readouterr().err
    assert remote_head(remote) == head
    assert git(f"--git-dir={backup.git_dir}", f"--work-tree={backup.wiki}", "diff", "--cached", "--name-only") == ""
    assert wb.main(["push", "--allow-empty"]) == 0
    assert remote_files(remote) == []


def test_push_and_status_without_the_wiki_folder(backup, tmp_path, capsys):
    backup.wiki.rename(tmp_path / "gone")
    capsys.readouterr()
    assert wb.main(["status"]) == 1
    assert "No wiki folder" in capsys.readouterr().err
    assert wb.main(["push"]) == 1
    assert "No wiki folder" in capsys.readouterr().err


def test_wiki_config_with_a_bom_and_a_home_path(ws, tmp_path, monkeypatch):
    (ws / "wiki.config.json").write_bytes(b"\xef\xbb\xbf" + json.dumps({"wiki_dir": "vault"}).encode())
    assert wb.Backup.from_config(ws, None, None).wiki == ws / "vault"
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    (ws / "wiki.config.json").write_text(json.dumps({"wiki_dir": "~/vault"}), encoding="utf-8")
    assert wb.Backup.from_config(ws, None, None).wiki == tmp_path / "home" / "vault"


def test_workspace_root_is_found_from_a_subfolder(ws, gd, monkeypatch):
    monkeypatch.delenv("CLAUDE_PROJECT_DIR")
    monkeypatch.chdir(ws / "wiki")
    assert wb.workspace_root().resolve() == ws.resolve()
    assert wb.Backup.from_config(wb.workspace_root(), None, None).git_dir == gd


def test_git_never_waits_for_a_password(monkeypatch):
    monkeypatch.delenv("GIT_TERMINAL_PROMPT")
    assert wb.git_env()["GIT_TERMINAL_PROMPT"] == "0"


def test_push_failure_text_only_blames_another_device_on_a_rejection():
    assert "another device" in wb.push_failure("! [rejected] main -> main (fetch first)")
    other = wb.push_failure("remote: error: File big.bin is 120 MB; this exceeds the file size limit")
    assert "another device" not in other and "120 MB" in other
    assert "nothing was forced" in other


def test_secret_scan_stops_the_commit(backup, remote, capsys):
    write(backup.wiki / "notes/token.md", f"token: {SECRET}\n")
    head = remote_head(remote)
    capsys.readouterr()
    assert wb.main(["push"]) == 1
    err = capsys.readouterr().err
    assert "notes/token.md" in err and "--no-scan" in err and SECRET not in err
    assert remote_head(remote) == head
    assert git(f"--git-dir={backup.git_dir}", "rev-parse", "HEAD") == head
    assert wb.main(["push", "--no-scan"]) == 0
    assert "notes/token.md" in remote_files(remote)


def test_secret_scan_checks_the_first_commit_too(ws, gd, remote, capsys):
    write(ws / "wiki/token.md", f"token: {SECRET}\n")
    prepare(gd, ws / "wiki")
    assert wb.main(["init", str(remote), "--yes"]) == 1
    assert "--no-scan" in capsys.readouterr().err
    assert git(f"--git-dir={remote}", "for-each-ref") == ""


def test_no_validate_script_means_no_scan(backup, remote, monkeypatch):
    monkeypatch.setattr(wb, "find_scanner", lambda root: None)
    write(backup.wiki / "notes/token.md", f"token: {SECRET}\n")
    assert wb.main(["push"]) == 0
