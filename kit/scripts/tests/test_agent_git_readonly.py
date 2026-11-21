"""Tests for agent_git_readonly.py: what a read-only agent may and may not run."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import agent_git_readonly as guard

SCRIPT = Path(guard.__file__)


@pytest.mark.parametrize("cmd", [
    "git status", "git status --short", "git diff", "git diff --cached -- src/a.py", "git diff HEAD~1 --stat",
    "git show --stat HEAD", "git log --oneline -n 20", "git ls-files", "git --no-pager log --oneline",
    "git -C sub status", "git --git-dir=/tmp/w.git --work-tree=/tmp/w status",
    "git --git-dir /tmp/w.git --work-tree /tmp/w diff --stat",
    "ls -la", "pwd", "cat README.md", "head -n 5 a.md", "tail -n 20 log.md", "wc -l a.md", "grep -rn TODO src",
    "rg -n secret docs", "find . -name '*.md' -type f", "file a.bin", "stat a.md", "du -sh wiki", "tree -L 2",
    "sort names.txt", "Get-ChildItem -Recurse", "Get-Content README.md", "Select-String -Pattern x a.md", "",
])
def test_allowed(cmd):
    assert guard.check(cmd) is None


@pytest.mark.parametrize("cmd,why", [
    ("git status > out.txt", "redirect"), ("cat < a.md", "redirect"), ("echo $(whoami)", "variable"),
    ("git diff `whoami`", "backticks"), ("git status; rm -rf x", "chaining"), ("git status && git push", "chaining"),
    ("git status || true", "pipe"), ("git log --oneline | head", "pipe"), ("sleep 100 &", "background"),
    ("git status\nrm a", "line break"), ("cat $HOME/.ssh/id_rsa", "variable"),
    ("git commit -m x", "not a read command"), ("git push", "not a read command"), ("git checkout main", "not a read"),
    ("git show HEAD", "only allowed with --stat"), ("git log", "only allowed with --oneline"),
    ("git -c core.pager=evil log --oneline", "option -c"), ("git log --oneline --output=x.txt", "can write"),
    ("git diff -oout.txt", "can write"), ("git diff --ext-diff", "can write"),
    ("GIT_EXTERNAL_DIFF=evil git diff", "not GIT_EXTERNAL_DIFF"), ("git", "bare git"),
    ("find . -exec rm {} +", "-exec"), ("find . -delete", "-delete"), ("rg --pre ./evil x", "--pre"),
    ("sort -o a.txt b.txt", "-o"), ("tail -f log.md", "-f"), ("python3 -c 'print(1)'", "not python3"),
    ("rm -rf /", "not rm"), ("echo 'unbalanced", "parsed"), ("Get-Content a.md -Wait", "-wait"),
])
def test_refused(cmd, why):
    reason = guard.check(cmd)
    assert reason is not None and why.lower() in reason.lower()


def run(payload: dict | str) -> subprocess.CompletedProcess[bytes]:
    data = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run(check=False, args=[sys.executable, str(SCRIPT)], input=data.encode(), capture_output=True)


def test_hook_blocks_with_exit_2():
    r = run({"tool_name": "Bash", "tool_input": {"command": "git push --force"}})
    assert r.returncode == 2 and b"git push" in r.stderr


def test_hook_allows_with_exit_0_and_no_output():
    r = run({"tool_name": "Bash", "tool_input": {"command": "git status"}})
    assert r.returncode == 0 and r.stdout == b"" and r.stderr == b""


def test_hook_covers_powershell():
    assert run({"tool_name": "PowerShell", "tool_input": {"command": "Remove-Item x"}}).returncode == 2


def test_hook_ignores_other_tools():
    assert run({"tool_name": "Read", "tool_input": {"file_path": "/a"}}).returncode == 0


def test_hook_refuses_garbage_input():
    assert run("not json").returncode == 2
