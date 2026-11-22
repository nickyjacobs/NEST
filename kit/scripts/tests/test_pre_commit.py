"""Tests for kit/github/pre-commit: the hook runs for real, through git and through sh.

The fake secret is built from pieces so this file holds none. The tests need git, uv and a
POSIX sh (Git for Windows ships one); without them they skip, unless NEST_REQUIRE_HOOK_TEST is
set (as in CI), where a missing tool is a failure instead of a silent skip.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

KIT = Path(__file__).resolve().parent.parent.parent
HOOK = KIT / "github" / "pre-commit"
VALIDATE = KIT / "scripts" / "validate.py"

FAKE_TOKEN = "gh" + "p_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"


def find_sh() -> str | None:
    """sh on PATH, else the one bundled with Git for Windows (git runs hooks with that one)."""
    found = shutil.which("sh")
    git = shutil.which("git")
    if found or not git or os.name != "nt":
        return found
    for base in list(Path(git).resolve().parents)[:3]:
        for rel in ("bin/sh.exe", "usr/bin/sh.exe"):
            if (base / rel).is_file():
                return str(base / rel)
    return None


SH = find_sh()
MISSING = [name for name, found in (("git", shutil.which("git")), ("uv", shutil.which("uv")), ("sh", SH)) if not found]


@pytest.fixture(autouse=True)
def tools():
    if MISSING:
        message = f"pre-commit hook test needs {', '.join(MISSING)} on PATH"
        if os.environ.get("NEST_REQUIRE_HOOK_TEST"):
            pytest.fail(message)
        pytest.skip(message)


@pytest.fixture
def env(tmp_path_factory) -> dict[str, str]:
    """The machine's git config and the caller's workspace stay out of the test."""
    empty = tmp_path_factory.mktemp("gitconfig") / "global"
    empty.write_text("", encoding="utf-8")
    drop = {"CLAUDE_PROJECT_DIR", "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"}
    return {**{k: v for k, v in os.environ.items() if k not in drop},
            "GIT_CONFIG_GLOBAL": str(empty), "GIT_CONFIG_NOSYSTEM": "1"}


def run(cmd: list[str], cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, env=env, check=False, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=300)


@pytest.fixture
def repo(tmp_path, env) -> Path:
    """A workspace laid out as the setup builds it: scripts/validate.py and .githooks/pre-commit."""
    root = tmp_path / "workspace"
    (root / "scripts").mkdir(parents=True)
    (root / ".githooks").mkdir()
    shutil.copyfile(VALIDATE, root / "scripts" / "validate.py")
    hook = root / ".githooks" / "pre-commit"
    hook.write_bytes(HOOK.read_bytes())
    hook.chmod(0o755)
    for args in (["init", "-q", "-b", "main"], ["config", "user.name", "Test Person"],
                 ["config", "user.email", "test@example.com"], ["config", "core.autocrlf", "false"],
                 ["config", "core.hooksPath", ".githooks"]):
        done = run(["git", *args], root, env)
        assert done.returncode == 0, done.stderr
    return root


def commit(repo: Path, env: dict[str, str], message: str) -> subprocess.CompletedProcess[str]:
    assert run(["git", "add", "-A"], repo, env).returncode == 0
    return run(["git", "commit", "-q", "-m", message], repo, env)


def commit_count(repo: Path, env: dict[str, str]) -> int:
    done = run(["git", "rev-list", "--count", "HEAD"], repo, env)
    return int(done.stdout.strip()) if done.returncode == 0 else 0


def test_hook_file_has_unix_line_endings():
    # sh reads a trailing carriage return as part of the last argument, which breaks the hook.
    data = HOOK.read_bytes()
    assert data.startswith(b"#!/bin/sh\n")
    assert b"\r" not in data


def test_clean_commit_passes(repo, env):
    (repo / "notes.md").write_text("# Notes\n\nNothing secret here.\n", encoding="utf-8")
    done = commit(repo, env, "Add notes")
    assert done.returncode == 0, done.stderr
    assert commit_count(repo, env) == 1


def test_commit_with_a_secret_is_refused(repo, env):
    (repo / "notes.md").write_text("# Notes\n", encoding="utf-8")
    assert commit(repo, env, "Add notes").returncode == 0

    (repo / "config.md").write_text(f"token: {FAKE_TOKEN}\n", encoding="utf-8")
    refused = commit(repo, env, "Add config")
    assert refused.returncode != 0
    assert "Commit blocked" in refused.stderr
    assert "config.md" in refused.stderr
    assert FAKE_TOKEN not in refused.stderr
    assert commit_count(repo, env) == 1

    (repo / "config.md").write_text("token: <fill in: token>\n", encoding="utf-8")
    fixed = commit(repo, env, "Add config")
    assert fixed.returncode == 0, fixed.stderr
    assert commit_count(repo, env) == 2


def test_hook_scans_the_index_not_the_working_tree(repo, env):
    (repo / "notes.md").write_text("# Notes\n", encoding="utf-8")
    assert run(["git", "add", "-A"], repo, env).returncode == 0
    (repo / "notes.md").write_text(f"token: {FAKE_TOKEN}\n", encoding="utf-8")
    done = run(["git", "commit", "-q", "-m", "Add notes"], repo, env)
    assert done.returncode == 0, done.stderr


def test_hook_runs_under_sh_from_a_subfolder(repo, env):
    sub = repo / "deep" / "er"
    sub.mkdir(parents=True)
    (sub / "clean.md").write_text("fine\n", encoding="utf-8")
    assert run(["git", "add", "-A"], repo, env).returncode == 0
    hook = (repo / ".githooks" / "pre-commit").as_posix()
    assert run([SH, hook], sub, env).returncode == 0

    (sub / "leak.md").write_text(f"token: {FAKE_TOKEN}\n", encoding="utf-8")
    assert run(["git", "add", "-A"], repo, env).returncode == 0
    blocked = run([SH, hook], sub, env)
    assert blocked.returncode == 2
    assert "deep/er/leak.md" in blocked.stderr


def test_secret_is_refused_when_the_session_lives_in_another_folder(repo, env, tmp_path):
    elsewhere = tmp_path / "another-project"
    elsewhere.mkdir()
    (repo / "config.md").write_text(f"token: {FAKE_TOKEN}\n", encoding="utf-8")
    refused = commit(repo, {**env, "CLAUDE_PROJECT_DIR": str(elsewhere)}, "Add config")
    assert refused.returncode != 0
    assert "Commit blocked" in refused.stderr
    assert commit_count(repo, env) == 0


@pytest.mark.skipif(os.name == "nt", reason="builds a PATH out of symlinks")
def test_missing_uv_gives_one_clear_line(repo, env, tmp_path):
    # A git client started outside a terminal often has a PATH without uv.
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "git").symlink_to(shutil.which("git"))
    (repo / "notes.md").write_text("# Notes\n", encoding="utf-8")
    assert run(["git", "add", "-A"], repo, env).returncode == 0
    done = run([SH, (repo / ".githooks" / "pre-commit").as_posix()], repo, {**env, "PATH": str(bin_dir)})
    assert done.returncode == 1
    assert done.stderr.count("\n") == 1 and "uv is not on PATH" in done.stderr and "commit is stopped" in done.stderr
