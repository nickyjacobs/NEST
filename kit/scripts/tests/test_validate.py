"""Tests for validate.py. Fake secrets are built from pieces so this file holds none."""
from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import validate

SCRIPT = Path(validate.__file__)

ANTHROPIC = "sk-" + "ant-" + "api03-" + "aB3dE5gH7jK9mN1pQ3sT5vW7yZ9bC1dF3hJ5"
GITHUB = "gh" + "p_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"
AWS = "AK" + "IA" + "IOSFODNN7EXAMPL3"
PRIVATE_KEY = "-----BEGIN " + "RSA PRIVATE KEY-----"
SLACK = "xo" + "xb-" + "123456789012-1234567890123-AbCdEfGhIjKlMnOxYzStUvWx"
JWT = "ey" + "JhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9." + "ey" + "JzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4ifQ." + "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV"
PASSWORD_LINE = "pass" + "word = 'Tr0ub4dor-x9Kq2Lm7'"


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    (tmp_path / ".claude").mkdir()
    return tmp_path


def run_hook(mode: str, payload: dict, monkeypatch, capsys) -> tuple[int, str, str]:
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(json.dumps(payload).encode("utf-8"))))
    rc = validate.main(["--hook", mode])
    out = capsys.readouterr()
    return rc, out.out, out.err


def kinds(text: str, root: Path) -> list[tuple[str, str]]:
    return [(f.kind, f.rule) for f in validate.Scanner(root).scan(text)]


@pytest.mark.parametrize("secret,rule", [
    (ANTHROPIC, "anthropic_key"), (GITHUB, "github_token"), (AWS, "aws_access_key"),
    (PRIVATE_KEY, "private_key_block"), (SLACK, "slack_token"), (JWT, "jwt"),
    (PASSWORD_LINE, "secret_assignment"),
    ("Authorization: Bear" + "er " + "x7Kq2Lm9Np4Rs6Tv8Wy0Za3Bc5De", "bearer_token"),
    ("postgres://app:" + "s3cr3tPassw0rd@db.internal:5432/x", "db_url_credentials"),
])
def test_hard_patterns(root, secret, rule):
    assert ("hard", rule) in kinds(f"line one\nconfig {secret} end\n", root)


@pytest.mark.parametrize("text", [
    "api_key = '<api-key>'",
    "pass" + "word: ${DB_PASSWORD}",
    "pass" + "word = 'changeme-please1'",
    "token = os.environ['TOKEN']",
    "postgres://user:" + "password@localhost/db",
    "sk-" + "ant-your_key_here_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "secret_assignment in a sentence about secrets",
    "p" + "wd: /private/tmp/scratch/trial-2/kora/_setup",
    "p" + "wd=~/Projects/my-workspace/notes",
    "pass" + "word_file: ./secrets/db-pass-location.txt",
    "p" + "wd: C:\\Users\\sam\\workspace\\kora",
])
def test_placeholders_are_not_hard(root, text):
    assert not [k for k in kinds(text, root) if k[0] == "hard"]


def test_soft_warnings(root):
    found = kinds("see /Users/alice/notes and C:\\Users\\bob\\x and 192.168.1.20 and mail me@corp.io", root)
    assert ("soft", "home_path") in found
    assert ("soft", "private_ip") in found
    assert ("soft", "email") in found
    assert not kinds("write to someone@example.com or 8.8.8.8", root)


def test_private_terms_file(root):
    (root / ".claude/sensitive-terms.txt").write_text("# comment\nAcme Corp\n/\\bproj-[0-9]{3}\\b/\n", encoding="utf-8")
    found = kinds("we met acme corp about proj-123, not acmecorp", root)
    assert found.count(("private", "private_term_line_2")) == 1
    assert ("private", "private_term_line_3") in found


def test_self_test_term_is_split_in_source():
    assert validate.SELF_TEST_TERM not in SCRIPT.read_text(encoding="utf-8")
    assert validate.main(["--self-test"]) == 0


def test_scanner_passes_its_own_source(root):
    assert not [k for k in kinds(SCRIPT.read_text(encoding="utf-8"), root) if k[0] in ("hard", "private")]


def test_findings_never_repeat_the_secret(root):
    report = validate.format_findings(validate.Scanner(root).scan(f"key {ANTHROPIC}"), "a.md")
    assert ANTHROPIC not in report and "anthropic_key" in report


def test_hook_pre_blocks_write(root, monkeypatch, capsys):
    rc, _, err = run_hook("pre", {"tool_name": "Write", "cwd": str(root),
                                  "tool_input": {"file_path": str(root / "a.md"), "content": f"k={GITHUB}"}},
                          monkeypatch, capsys)
    assert rc == 2 and "github_token" in err


def test_hook_pre_scans_edit_multiedit_and_notebook(root, monkeypatch, capsys):
    for tool_input in ({"file_path": "x.md", "old_string": "a", "new_string": AWS},
                       {"file_path": "x.md", "edits": [{"old_string": "a", "new_string": "ok"}, {"new_string": AWS}]},
                       {"notebook_path": "n.ipynb", "new_source": AWS}):
        rc, _, _ = run_hook("pre", {"tool_name": "Edit", "tool_input": tool_input}, monkeypatch, capsys)
        assert rc == 2


def test_hook_pre_allows_clean_and_soft(root, monkeypatch, capsys):
    rc, out, err = run_hook("pre", {"tool_name": "Write", "tool_input": {"file_path": str(root / "a.md"),
                                                                         "content": "hello 10.0.0.1"}},
                            monkeypatch, capsys)
    assert rc == 0 and out == "" and err == ""


def test_hook_pre_private_terms_block_only_when_configured(root, monkeypatch, capsys):
    (root / ".claude/sensitive-terms.txt").write_text("Acme\n", encoding="utf-8")
    payload = {"tool_name": "Write", "tool_input": {"file_path": str(root / "a.md"), "content": "for Acme"}}
    assert run_hook("pre", payload, monkeypatch, capsys)[0] == 0
    (root / "nest.json").write_text(json.dumps({"secret_scan": {"private_terms": "block"}}), encoding="utf-8")
    rc, _, err = run_hook("pre", payload, monkeypatch, capsys)
    assert rc == 2 and "Acme" not in err


def test_hook_pre_skip_globs(root, monkeypatch, capsys):
    (root / "nest.json").write_text(json.dumps({"secret_scan": {"skip": ["vendor/**"]}}), encoding="utf-8")
    payload = {"tool_name": "Write", "tool_input": {"file_path": str(root / "vendor/lib/x.md"), "content": AWS}}
    assert run_hook("pre", payload, monkeypatch, capsys)[0] == 0
    payload["tool_input"]["file_path"] = str(root / "src/x.md")
    assert run_hook("pre", payload, monkeypatch, capsys)[0] == 2


def test_hook_post_feedback(root, monkeypatch, capsys):
    f = root / "notes.md"
    f.write_text(f"first\n{AWS}\n", encoding="utf-8")
    rc, _, err = run_hook("post", {"tool_name": "Edit", "tool_input": {"file_path": str(f), "new_string": "first"}},
                          monkeypatch, capsys)
    assert rc == 2 and "line 2: aws_access_key" in err

    f.write_text("mail bob@corp.io\n", encoding="utf-8")
    rc, out, _ = run_hook("post", {"tool_name": "Write", "tool_input": {"file_path": str(f),
                                                                        "content": "mail bob@corp.io"}},
                          monkeypatch, capsys)
    data = json.loads(out)
    assert rc == 0 and data["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    assert "email" in data["hookSpecificOutput"]["additionalContext"]


def test_hook_post_soft_skip(root, monkeypatch, capsys):
    (root / "nest.json").write_text(json.dumps({"secret_scan": {"soft_skip": ["wiki/_inbox/**"]}}), encoding="utf-8")
    f = root / "wiki/_inbox/clip.md"
    f.parent.mkdir(parents=True)
    f.write_text("from bob@corp.io\n", encoding="utf-8")
    rc, out, _ = run_hook("post", {"tool_name": "Write", "tool_input": {"file_path": str(f),
                                                                        "content": "from bob@corp.io"}},
                          monkeypatch, capsys)
    assert rc == 0 and out == ""


def test_hook_handles_garbage_input(root, monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(b"not json")))
    assert validate.main(["--hook", "pre"]) == 0


def test_windows_style_path_is_relative(root):
    assert validate.relative(str(root / "a" / "b.md"), root) == "a/b.md"


def test_glob_matching():
    assert validate.matches_any("wiki/_inbox/a.md", ["wiki/_inbox/**"])
    assert validate.matches_any("deep/x/archive/a.md", ["**/archive/**"])
    assert not validate.matches_any("wiki/notes/a.md", ["wiki/_inbox/**"])


def test_file_mode_skips_binary(root):
    b = root / "img.png"
    b.write_bytes(b"\x89PNG\x00\x00" + AWS.encode())
    assert validate.main(["--file", str(b)]) == 0


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def test_staged_scans_the_index_not_the_working_tree(root, monkeypatch):
    git(root, "init", "-q")
    monkeypatch.chdir(root)
    f = root / "config.md"
    f.write_text(f"key {AWS}\n", encoding="utf-8")
    git(root, "add", "config.md")
    f.write_text("clean now, but not staged\n", encoding="utf-8")
    assert validate.main(["--staged"]) == 2
    git(root, "add", "config.md")
    assert validate.main(["--staged"]) == 0


def test_staged_blocks_private_terms(root, monkeypatch):
    git(root, "init", "-q")
    monkeypatch.chdir(root)
    (root / ".claude/sensitive-terms.txt").write_text("Acme\n", encoding="utf-8")
    (root / "a.md").write_text("Acme rollout\n", encoding="utf-8")
    git(root, "add", "a.md")
    assert validate.main(["--staged"]) == 2


def test_runs_as_a_script_with_hook_json(root):
    payload = json.dumps({"tool_name": "Write", "tool_input": {"file_path": "a.md", "content": GITHUB}})
    r = subprocess.run(check=False, args=[sys.executable, str(SCRIPT), "--hook", "pre"], input=payload.encode(), capture_output=True,
                       cwd=root)
    assert r.returncode == 2 and b"github_token" in r.stderr
