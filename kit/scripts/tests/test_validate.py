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
    (SLACK, "slack_token"), (JWT, "jwt"),
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


@pytest.mark.parametrize("raw", [b"not json", b"", b"[]", b'{"tool_input": "text"}', b"\xff\xfe{}"])
def test_hook_pre_refuses_input_it_cannot_read(root, monkeypatch, capsys, raw):
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(raw)))
    assert validate.main(["--hook", "pre"]) == 2
    assert "could not be read" in capsys.readouterr().err


@pytest.mark.parametrize("mode", ["post", "shell"])
def test_hooks_after_the_fact_stay_quiet_on_input_they_cannot_read(root, monkeypatch, capsys, mode):
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(b"not json")))
    assert validate.main(["--hook", mode]) == 0
    out = capsys.readouterr()
    assert out.out == "" and out.err == ""


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


# ---------------------------------------------------------------- names, values and prefixes

VALUE = "Tr0ub4dor" + "9Zq7Lm2Xv"
FILLER = "Zq7Lm2Xv9Kp4Wt8Rb3Ny6Hd1Gc5Js0FaUeTiOoPlMk"


@pytest.mark.parametrize("line", [
    "DB_PASSWORD=" + VALUE, "POSTGRES_PASSWORD=" + VALUE, "SECRET_KEY=" + FILLER, "JWT_SECRET=" + FILLER,
    "MY_API_KEY=" + FILLER[:32], "OPENAI_API_KEY=" + FILLER[:32], "GITHUB_TOKEN=" + FILLER[:32],
    "token: " + FILLER[:32], "bot_token = \"" + FILLER[:32] + "\"", "refresh_token=" + FILLER[:32],
    "passphrase: " + VALUE, "pass" + "word=" + VALUE[:10], "pass" + "word: P4ss$Word!99zz",
    "export PASSWORD='" + VALUE + "'", "{\"pass" + "word\": \"" + VALUE + "\"}", "Password=" + VALUE + ";",
    "https://api.test/v1?access_token=" + FILLER[:24],
])
def test_secret_name_may_be_the_end_of_a_longer_name(root, line):
    assert ("hard", "secret_assignment") in kinds(line, root)


@pytest.mark.parametrize("line,rule", [
    ("postgres://example_user:" + VALUE + "@db.internal.test:5432/app", "db_url_credentials"),
    ("sample_" + "pass" + "word=" + VALUE, "secret_assignment"),
    ("example." + "api_key: " + FILLER[:32], "secret_assignment"),
])
def test_placeholder_word_in_the_name_does_not_hide_the_value(root, line, rule):
    assert ("hard", rule) in kinds(line, root)


@pytest.mark.parametrize("line,rule", [
    ("https://deploy:" + VALUE + "@git.internal.test/repo.git", "url_credentials"),
    ("mssql+pyodbc://sa:" + VALUE + "@host/db", "url_credentials"),
    ("redis://:" + VALUE + "@cache.internal.test:6379/0", "db_url_credentials"),
    ("DefaultEndpointsProtocol=https;AccountName=acct;Account" + "Key=" + (FILLER * 3)[:86] + "==", "azure_storage_key"),
    ("123456789" + ":AA" + "H" + FILLER[:32], "telegram_bot_token"),
    ("Authorization: Ba" + "sic " + "ZGVwbG95OlRyMHViNGRvcjlacTdMbTJYdg==", "basic_auth_header"),
    ("curl -" + "u admin:" + VALUE + " https://x.test", "curl_credentials"),
    ("curl -s --us" + "er 'deploy:" + VALUE + "' https://x.test", "curl_credentials"),
    ("wh" + "sec_" + FILLER[:32], "stripe_webhook_secret"),
    ("dop" + "_v1_" + "a1b2c3d4" * 8, "digitalocean_token"),
    ("pypi-" + "AgEIcHlwaS5vcmc" + FILLER + FILLER, "pypi_token"),
    ("dckr" + "_pat_" + FILLER[:27], "docker_token"),
    ("hv" + "s." + FILLER + FILLER, "vault_token"),
    ("xapp" + "-1-A0123456789-1234567890123-" + "a1b2c3d4" * 8, "slack_app_token"),
    ("S" + "K" + "0123456789abcdef" * 2, "twilio_key"),
    ("AGE-SECRET" + "-KEY-1" + ("QPZRY9X8GF2TVDW0S3JN54KHCE6MUA7L" * 2)[:58], "age_secret_key"),
    ("tv" + "ly-" + FILLER[:32], "tavily_key"),
    ("nt" + "n_" + FILLER + FILLER[:8], "notion_token"),
])
def test_more_credential_shapes(root, line, rule):
    assert ("hard", rule) in kinds(line, root)


@pytest.mark.parametrize("line", [
    "pass" + "word = hashlib.sha256(raw).hexdigest()",
    "api_key = settings.OPENAI_API_KEY_V2",
    "secret = base64.b64decode(blob)",
    "auth_token=request.headers.get(\"X-Auth\")",
    "pass" + "word: z.string().min(12)",
    "apikey=process.env.NEXT_PUBLIC_API_KEY2",
    "PASSWORD=${{ secrets.DB_PASSWORD }}",
    "csrf_token = generate_csrf2()",
    "private_key = load_pem_private_key(data1)",
    "pass" + "word_hash: $2b$12$abcdefghijklmnopqrstuv",
    "max_tokens=4096 and token_count: 123456789012",
    "\"pass" + "word\": \"Password must be at least 8 characters\"",
    "git clone https://USERNAME:TOKEN@github.com/x/y.git",
    "http://localhost:8080/path@x and http://user:pass@host",
    "see ssh://git@github.com:22/x/y.git",
    "curl -u \"$USER:$PASS\" https://x.test",
    "Account" + "Key=[A-Za-z0-9+/]{60,}={0,2}",
])
def test_code_and_stock_values_are_not_secrets(root, line):
    assert not [k for k in kinds(line, root) if k[0] == "hard"]


def test_email_pattern_stays_fast_on_a_long_dotted_line(root):
    import time
    line = "a." * 150_000 + "@" + "b-" * 50_000
    started = time.monotonic()
    validate.Scanner(root).scan(line, ("soft",))
    assert time.monotonic() - started < 5


# ---------------------------------------------------------------- the terms file

@pytest.mark.parametrize("raw", [
    "Café Klant\nAcme\n".encode("cp1252"),
    "﻿Acme\nGlobex\n".encode("utf-8"),
    "Acme\r\nGlobex\r\n".encode("utf-16"),
])
def test_terms_file_in_another_encoding_still_works(root, raw):
    (root / ".claude/sensitive-terms.txt").write_bytes(raw)
    scanner = validate.Scanner(root)
    assert [f.rule for f in scanner.scan("we met Acme today", ("private",))]
    assert not scanner.warnings


def test_terms_file_that_is_binary_gives_a_warning_not_a_crash(root, capsys):
    (root / ".claude/sensitive-terms.txt").write_bytes(b"\x00\x01\x02Acme")
    scanner = validate.Scanner(root)
    assert scanner.warnings and "UTF-8" in scanner.warnings[0]
    assert validate.main(["--self-test"]) == 0


# ---------------------------------------------------------------- files that are meant to be private

def post(path: Path, content: str = "x") -> dict:
    return {"tool_name": "Edit", "tool_input": {"file_path": str(path), "new_string": content}}


def test_post_leaves_the_private_context_file_and_the_terms_file_alone(root, monkeypatch, capsys):
    (root / ".claude/sensitive-terms.txt").write_text("Acme\n", encoding="utf-8")
    local = root / "CLAUDE.local.md"
    local.write_text(f"Employer: Acme\nkey {AWS}\n", encoding="utf-8")
    for path in (local, root / ".claude/sensitive-terms.txt"):
        rc, out, err = run_hook("post", post(path), monkeypatch, capsys)
        assert (rc, out, err) == (0, "", "")


def test_pre_never_blocks_a_private_term_in_its_own_home(root, monkeypatch, capsys):
    (root / ".claude/sensitive-terms.txt").write_text("Acme\n", encoding="utf-8")
    (root / "nest.json").write_text(json.dumps({"secret_scan": {"private_terms": "block"}}), encoding="utf-8")
    for name in ("CLAUDE.local.md", ".claude/sensitive-terms.txt"):
        payload = {"tool_name": "Write", "tool_input": {"file_path": str(root / name), "content": "Acme\n"}}
        assert run_hook("pre", payload, monkeypatch, capsys)[0] == 0
    payload = {"tool_name": "Write", "tool_input": {"file_path": str(root / "CLAUDE.local.md"), "content": AWS}}
    assert run_hook("pre", payload, monkeypatch, capsys)[0] == 2  # a real key is still stopped


def test_post_leaves_an_ignored_env_file_alone_but_not_a_tracked_one(root, monkeypatch, capsys):
    env_file = root / ".env"
    env_file.write_text(f"KEY={AWS}\nDEBUG=1\n", encoding="utf-8")
    # No git here: the name decides.
    assert run_hook("post", post(env_file, "DEBUG=1"), monkeypatch, capsys) == (0, "", "")
    git(root, "init", "-q")
    rc, _, err = run_hook("post", post(env_file, "DEBUG=1"), monkeypatch, capsys)
    assert rc == 2 and "aws_access_key" in err  # in a repository and not ignored: it would be committed
    (root / ".gitignore").write_text(".env\n", encoding="utf-8")
    assert run_hook("post", post(env_file, "DEBUG=1"), monkeypatch, capsys) == (0, "", "")
    example = root / ".env.example"
    example.write_text(f"KEY={AWS}\n", encoding="utf-8")
    assert run_hook("post", post(example), monkeypatch, capsys)[0] == 2


def test_staged_still_scans_a_private_file_that_is_about_to_be_committed(root, monkeypatch):
    git(root, "init", "-q")
    monkeypatch.chdir(root)
    (root / "CLAUDE.local.md").write_text(f"key {AWS}\n", encoding="utf-8")
    git(root, "add", "CLAUDE.local.md")
    assert validate.main(["--staged"]) == 2


# ---------------------------------------------------------------- what is skipped is said

def big_file(path: Path) -> None:
    path.write_text(f"key {AWS}\n" + "a" * (validate.MAX_BYTES + 10), encoding="utf-8")


def test_oversized_file_is_named_as_skipped(root, monkeypatch, capsys):
    big = root / "big.txt"
    big_file(big)
    assert validate.main(["--file", str(big)]) == 0
    assert "big.txt was not scanned: larger than 2 MB" in capsys.readouterr().err
    rc, out, _ = run_hook("post", post(big), monkeypatch, capsys)
    assert rc == 0 and "was not scanned" in json.loads(out)["hookSpecificOutput"]["additionalContext"]
    git(root, "init", "-q")
    monkeypatch.chdir(root)
    git(root, "add", "big.txt")
    assert validate.main(["--staged"]) == 0
    assert "big.txt was not scanned" in capsys.readouterr().err


def test_utf16_file_is_scanned(root, monkeypatch, capsys):
    f = root / "export.txt"
    f.write_bytes(f"key {AWS}\n".encode("utf-16"))
    assert validate.main(["--file", str(f)]) == 2
    git(root, "init", "-q")
    monkeypatch.chdir(root)
    git(root, "add", "export.txt")
    assert validate.main(["--staged"]) == 2


def test_staged_submodule_does_not_block_the_commit(root, tmp_path_factory, monkeypatch, capsys):
    sub = tmp_path_factory.mktemp("sub")
    git(sub, "init", "-q")
    (sub / "f.txt").write_text("x\n", encoding="utf-8")
    git(sub, "add", "f.txt")
    git(sub, "-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-q", "-m", "s")
    git(root, "init", "-q")
    monkeypatch.chdir(root)
    git(root, "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(sub), "vendor/sub")
    assert validate.main(["--staged"]) == 0
    assert "could not read" not in capsys.readouterr().err


# ---------------------------------------------------------------- after a shell command

def shell(root: Path, event: str = "PostToolUse") -> dict:
    return {"hook_event_name": event, "tool_name": "Bash", "cwd": str(root),
            "tool_input": {"command": "cat > .env.production <<EOF ..."}}


@pytest.fixture
def repo(root):
    git(root, "init", "-q")
    (root / "tracked.md").write_text("clean\n", encoding="utf-8")
    git(root, "add", "tracked.md")
    git(root, "-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-q", "-m", "init")
    return root


def test_shell_hook_finds_a_secret_a_command_wrote(repo, monkeypatch, capsys):
    assert run_hook("shell", shell(repo), monkeypatch, capsys) == (0, "", "")  # nothing changed
    (repo / "notes dir").mkdir()
    (repo / "notes dir" / "new file.md").write_text(f"token {GITHUB}\n", encoding="utf-8")
    rc, _, err = run_hook("shell", shell(repo), monkeypatch, capsys)
    assert rc == 2 and "notes dir/new file.md" in err and "github_token" in err and GITHUB not in err
    assert "after a shell command" in err


def test_shell_hook_sees_an_edit_to_a_tracked_file_and_a_failed_command(repo, monkeypatch, capsys):
    (repo / "tracked.md").write_text(f"clean\n{AWS}\n", encoding="utf-8")
    rc, _, err = run_hook("shell", shell(repo, "PostToolUseFailure"), monkeypatch, capsys)
    assert rc == 2 and "tracked.md" in err and "line 2: aws_access_key" in err


def test_shell_hook_reports_private_terms(repo, monkeypatch, capsys):
    (repo / ".claude/sensitive-terms.txt").write_text("Acme\n", encoding="utf-8")
    (repo / ".gitignore").write_text(".claude/sensitive-terms.txt\n", encoding="utf-8")
    (repo / "a.md").write_text("for Acme\n", encoding="utf-8")
    rc, _, err = run_hook("shell", shell(repo), monkeypatch, capsys)
    assert rc == 2 and "a.md" in err and "Acme" not in err and "sensitive-terms.txt:" not in err


def test_shell_hook_ignores_ignored_private_and_skipped_files(repo, monkeypatch, capsys):
    (repo / ".gitignore").write_text(".env\nbuild/\n", encoding="utf-8")
    (repo / ".env").write_text(f"KEY={AWS}\n", encoding="utf-8")
    (repo / "build").mkdir()
    (repo / "build" / "out.txt").write_text(f"{AWS}\n", encoding="utf-8")
    (repo / "CLAUDE.local.md").write_text(f"{AWS}\n", encoding="utf-8")
    (repo / "vendor").mkdir()
    (repo / "vendor" / "lib.md").write_text(f"{AWS}\n", encoding="utf-8")
    (repo / "nest.json").write_text(json.dumps({"secret_scan": {"skip": ["vendor/**"]}}), encoding="utf-8")
    assert run_hook("shell", shell(repo), monkeypatch, capsys) == (0, "", "")


def test_shell_hook_leaves_a_file_alone_that_changed_long_ago(repo, monkeypatch, capsys):
    import time
    (repo / "old.md").write_text(f"{AWS}\n", encoding="utf-8")
    real = time.time
    monkeypatch.setattr(validate.time, "time", lambda: real() + validate.SHELL_WINDOW + 60)
    assert run_hook("shell", shell(repo), monkeypatch, capsys) == (0, "", "")


def test_shell_hook_sees_a_copied_file_with_an_old_modification_time(repo, monkeypatch, capsys):
    import os
    import time
    copied = repo / "unpacked.md"
    copied.write_text(f"{AWS}\n", encoding="utf-8")
    stale = time.time() - 30 * 86400
    os.utime(copied, (stale, stale))  # what cp -p, mv and an unpacked archive leave behind
    rc, _, err = run_hook("shell", shell(repo), monkeypatch, capsys)
    assert rc == 2 and "unpacked.md" in err


def test_shell_hook_sees_a_file_that_was_written_and_committed_in_one_command(repo, monkeypatch, capsys):
    assert run_hook("shell", shell(repo), monkeypatch, capsys)[0] == 0  # this run remembers HEAD
    (repo / "config.md").write_text(f"key {AWS}\n", encoding="utf-8")
    git(repo, "add", "config.md")
    git(repo, "-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-q", "-m", "add config")
    real = validate.time.time
    monkeypatch.setattr(validate.time, "time", lambda: real() + validate.SHELL_WINDOW + 60)  # and not by its age
    rc, _, err = run_hook("shell", shell(repo), monkeypatch, capsys)
    assert rc == 2 and "config.md" in err
    state = json.loads((repo / validate.SHELL_STATE).read_text(encoding="utf-8"))
    assert list(state["heads"].values())[0]


def test_shell_hook_looks_into_the_wikis_own_backup_repository(repo, tmp_path_factory, monkeypatch, capsys):
    monkeypatch.delenv("NEST_WIKI_CONFIG", raising=False)
    backup = tmp_path_factory.mktemp("backup") / "wiki.git"
    wiki = repo / "wiki"
    wiki.mkdir()
    (repo / ".gitignore").write_text("wiki/\n", encoding="utf-8")
    git(repo, f"--git-dir={backup}", f"--work-tree={wiki}", "init", "-q")
    (wiki / "note.md").write_text(f"token {GITHUB}\n", encoding="utf-8")
    assert run_hook("shell", shell(repo), monkeypatch, capsys)[0] == 0  # the workspace ignores wiki/
    (repo / "nest.json").write_text(json.dumps({"wiki_backup": {"git_dir": str(backup)}}), encoding="utf-8")
    rc, _, err = run_hook("shell", shell(repo), monkeypatch, capsys)
    assert rc == 2 and "wiki/note.md" in err and "github_token" in err


def test_shell_hook_does_not_read_a_clean_file_twice(repo, monkeypatch, capsys):
    (repo / "a.md").write_text("clean\n", encoding="utf-8")
    seen: list[str] = []
    real = validate.load_text
    monkeypatch.setattr(validate, "load_text", lambda path: (seen.append(path.name), real(path))[1])
    assert run_hook("shell", shell(repo), monkeypatch, capsys)[0] == 0
    assert run_hook("shell", shell(repo), monkeypatch, capsys)[0] == 0
    assert seen.count("a.md") == 1
    (repo / "a.md").write_text(f"now {AWS}\n", encoding="utf-8")
    assert run_hook("shell", shell(repo), monkeypatch, capsys)[0] == 2
    assert run_hook("shell", shell(repo), monkeypatch, capsys)[0] == 2  # a finding is repeated until it is fixed


def test_shell_hook_is_silent_outside_a_repository_and_without_git(root, monkeypatch, capsys):
    (root / "a.md").write_text(f"{AWS}\n", encoding="utf-8")
    assert run_hook("shell", shell(root), monkeypatch, capsys) == (0, "", "")
    monkeypatch.setattr(validate, "git", lambda *a, **k: None)
    assert run_hook("shell", shell(root), monkeypatch, capsys) == (0, "", "")


def test_shell_hook_is_bounded_and_says_what_it_left_out(repo, monkeypatch, capsys):
    monkeypatch.setattr(validate, "SHELL_MAX_FILES", 3)
    for i in range(6):
        (repo / f"f{i}.md").write_text("clean\n", encoding="utf-8")
    rc, out, _ = run_hook("shell", shell(repo), monkeypatch, capsys)
    note = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert rc == 0 and "more changed files were not scanned" in note and "if the pre-commit scan is installed" in note
    monkeypatch.setattr(validate, "SHELL_MAX_FILES", 50)
    monkeypatch.setattr(validate, "SHELL_MAX_BYTES", 10)
    (repo / "g1.md").write_text("clean " * 10, encoding="utf-8")
    (repo / "g2.md").write_text("clean " * 10, encoding="utf-8")
    rc, out, _ = run_hook("shell", shell(repo), monkeypatch, capsys)
    assert rc == 0 and "more changed file" in out
    monkeypatch.setattr(validate, "SHELL_MAX_BYTES", 8_000_000)
    big_file(repo / "big.txt")
    rc, out, _ = run_hook("shell", shell(repo), monkeypatch, capsys)
    assert rc == 0 and "big.txt was not scanned" in json.loads(out)["hookSpecificOutput"]["additionalContext"]


def test_hook_input_is_read_as_utf8_whatever_the_console_says(root):
    payload = json.dumps({"tool_name": "Write", "tool_input": {"file_path": str(root / "café “x”.md"),
                                                               "content": GITHUB}}, ensure_ascii=False)
    r = subprocess.run(check=False, args=[sys.executable, str(SCRIPT), "--hook", "pre"], input=payload.encode("utf-8"),
                       capture_output=True, cwd=root, env={**__import__("os").environ, "PYTHONIOENCODING": "cp1252"})
    assert r.returncode == 2 and b"github_token" in r.stderr


def test_nest_json_with_a_byte_order_mark_is_read(root):
    (root / "nest.json").write_bytes(b"\xef\xbb\xbf" + json.dumps({"secret_scan": {"private_terms": "block"}}).encode("utf-8"))
    assert validate.Scanner(root).block_private


# ---------------------------------------------------------------- what the review of the guards found

KEY_BODY = "MIIEvQIBADANBgkq" + "hkiG9w0BAQEFAASC" + "BKcwggSjAgEAAoIB" + "AQC7"


@pytest.mark.parametrize("text", [
    PRIVATE_KEY + "\n" + KEY_BODY + "\n",
    PRIVATE_KEY + "\nProc-Type: 4,ENCRYPTED\nDEK-Info: AES-128-CBC,ABCDEF\n\n" + KEY_BODY + "\n",
    '"private_key": "' + PRIVATE_KEY + "\\n" + KEY_BODY + '\\n"',
    "-----BEGIN " + "PGP PRIVATE KEY BLOCK-----\nVersion: x\n\n" + KEY_BODY + "\n",
])
def test_private_key_with_key_material_is_hard(root, text):
    assert ("hard", "private_key_block") in kinds(text, root)


@pytest.mark.parametrize("text", [
    "See the " + PRIVATE_KEY + " header in a PEM file",
    "A PEM private key starts with `" + PRIVATE_KEY + "`.\n\nThen the next paragraph follows.",
    PRIVATE_KEY + "\n<fill in: the key>\n",
])
def test_sentence_that_quotes_a_key_header_is_not_a_key(root, text):
    assert not [k for k in kinds(text, root) if k[0] == "hard"]


@pytest.mark.parametrize("line,rule", [
    ("**Pass" + "word:** " + VALUE, "secret_assignment"), ("Pass" + "word: `" + VALUE + "`", "secret_assignment"),
    ("Wacht" + "woord: " + VALUE, "secret_assignment"), ("Pass" + "wort: " + VALUE, "secret_assignment"),
    ("Kenn" + "wort = " + VALUE, "secret_assignment"), ("PA" + "SS=" + VALUE, "secret_assignment"),
    ("smtp_pa" + "ss: " + VALUE, "secret_assignment"),
    ("p" + "w=" + VALUE, "secret_assignment"), ("DB_PA" + "SS=" + VALUE, "secret_assignment"),
    ("api k" + "ey : " + FILLER[:32], "secret_assignment"),
    ("tool --pass" + "word " + VALUE, "cli_password"), ("sshpa" + "ss -p " + VALUE + " ssh root@h", "cli_password"),
    ("<pass" + "word>" + VALUE + "</pass" + "word>", "xml_secret"),
    ('<add key="Api' + 'Key" value="' + FILLER[:32] + '"/>', "xml_secret"),
    ("| API k" + "ey | " + FILLER[:32] + " |", "table_secret"),
    ("https://" + "ghx" + FILLER[:22] + "@github.com/x/y.git", "url_token"),
    ("GOC" + "SPX-" + FILLER[:28], "google_oauth_secret"), ("sk_" + "test_" + FILLER[:24], "stripe_secret"),
    ("https://discord.com/api/web" + "hooks/123456789012345678/" + FILLER + FILLER[:28], "discord_webhook"),
    ("PuTTY-User-Key-" + "File-3: ssh-ed25519", "putty_private_key"), ("gl" + "dt-" + FILLER[:20], "gitlab_token"),
    ("lin_" + "api_" + FILLER[:40], "linear_key"), ("fig" + "d_" + FILLER[:40], "figma_token"),
    ("shp" + "at_" + "a1b2c3d4" * 4, "shopify_token"),
])
def test_shapes_the_review_found_missing(root, line, rule):
    assert ("hard", rule) in kinds(line, root)


@pytest.mark.parametrize("line", [
    "DATABASE_URL=postgres://postgres:postgres@localhost:5432/app",
    "DATABASE_URL=postgresql://myuser:mypassword@localhost/db",
    "REDIS_URL=redis://default:secret123@localhost:6379",
    "mongodb://root:rootpassword@mongo:27017",
    "url: http://proxy:8080@internal",
    "curl -u username:password123 https://api.example.com",
    "SECRET_KEY=django-insecure-change-me-in-production-1234",
    "TELEGRAM_BOT_TOKEN=123456:replace-me",
    "bot_token = TELEGRAM_BOT_TOKEN2",
    "api_key: todo-ask-anna-for-the-key-2",
    "sk-learn-is-a-python-library-for-machine-learning-and-data-science",
    "[link](https://example.com/sk-this-is-a-very-long-slug-about-something-or-other-2025)",
    "SKU: S" + "K" + "0123456789abcdef" + "0123456789abcdef",
    "bearer token/authentication/authorization2",
    "My pass" + "word is long and I changed it yesterday2",
    "Wacht" + "woord: staat in de kluis onder Ziggo",
    "p" + "wd: /private/tmp/scratch/trial-2/kora/_setup",
    "compass: north-by-northwest-2024",
    "--pass" + "word-stdin2 < file",
    "tool --pass" + "word $DB_PASSWORD2",
    "| Token | see the vault entry |",
])
def test_ordinary_writing_the_review_found_blocked(root, line):
    assert not [k for k in kinds(line, root) if k[0] == "hard"]


def test_patterns_stay_fast_on_long_runs(root):
    import time
    scanner = validate.Scanner(root)
    for line in ("pass" + "word:" + " " * 200_000 + "x", ("eyJ" + "a" * 15 + ".") * 10_000, "eyJ-" * 50_000,
                 "pass" + "word=" + "*" * 100_000):
        started = time.monotonic()
        scanner.scan(line, ("hard",))
        assert time.monotonic() - started < 5


def test_skip_written_as_one_string_is_one_glob(root, monkeypatch, capsys):
    (root / "nest.json").write_text(json.dumps({"secret_scan": {"skip": "vendor/**", "soft_skip": "wiki/**"}}),
                                    encoding="utf-8")
    scanner = validate.Scanner(root)
    assert scanner.skipped("vendor/lib/x.md") and not scanner.skipped("src/x.md")
    assert scanner.soft_silent("wiki/a.md") and not scanner.soft_silent("docs/a.md")
    payload = {"tool_name": "Write", "tool_input": {"file_path": str(root / "src/x.md"), "content": AWS}}
    assert run_hook("pre", payload, monkeypatch, capsys)[0] == 2


@pytest.mark.parametrize("value", [5, {"a": 1}, True, ["vendor/**", 7]])
def test_skip_of_another_type_warns_and_skips_nothing_extra(root, value):
    (root / "nest.json").write_text(json.dumps({"secret_scan": {"skip": value}}), encoding="utf-8")
    scanner = validate.Scanner(root)
    assert not scanner.skipped("src/x.md")
    assert scanner.warnings and "secret_scan.skip" in scanner.warnings[0]


def test_utf16_without_a_mark_is_scanned(root):
    f = root / "export.txt"
    f.write_bytes(f"key {AWS}\n".encode("utf-16-le"))
    assert validate.main(["--file", str(f)]) == 2
    f.write_bytes(f"key {AWS}\n".encode("utf-16-be"))
    assert validate.main(["--file", str(f)]) == 2


def test_file_mode_keeps_the_heading_the_wiki_backup_reads(root, capsys):
    f = root / "a.md"
    f.write_text(f"key {AWS}\n", encoding="utf-8")
    assert validate.main(["--file", str(f)]) == 2
    assert "Secrets (blocked) in a.md:" in capsys.readouterr().err


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes")
def test_shell_state_file_is_for_the_user_alone(repo, monkeypatch, capsys):
    import os
    import stat
    old = os.umask(0o002)
    try:
        (repo / "a.md").write_text("clean\n", encoding="utf-8")
        assert run_hook("shell", shell(repo), monkeypatch, capsys)[0] == 0
    finally:
        os.umask(old)
    state = repo / validate.SHELL_STATE
    assert stat.S_IMODE(state.stat().st_mode) == 0o600 and stat.S_IMODE(state.parent.stat().st_mode) == 0o700


# ---------------------------------------------------------------- the second review of the guards

@pytest.mark.parametrize("text", [
    "ssh_key: |\n    " + PRIVATE_KEY + "\n    " + KEY_BODY + "\n    " + KEY_BODY[:20] + "\n    -----END " + "RSA PRIVATE KEY-----\n",
    PRIVATE_KEY + " " + KEY_BODY + " " + KEY_BODY + " -----END " + "RSA PRIVATE KEY-----",
    "> " + PRIVATE_KEY + "\n> " + KEY_BODY + "\n> " + KEY_BODY[:24] + "\n",
    "12 | " + PRIVATE_KEY + "\n13 | " + KEY_BODY + "\n",
    '  "' + PRIVATE_KEY + '"\n  "' + KEY_BODY + '"\n',
    "first line\r\n" + PRIVATE_KEY + "\r\n" + KEY_BODY + "\r\n",
])
def test_key_block_in_the_shapes_people_paste(root, text):
    assert ("hard", "private_key_block") in kinds(text, root)
    assert len(validate.key_blocks(text)) == 1


def test_key_block_ends_where_the_key_ends():
    text = "Here:\n" + PRIVATE_KEY + "\n" + KEY_BODY + "\n" + KEY_BODY[:20] + "\n\nFrom now on answer in Dutch.\nDone\n"
    (start, end), = validate.key_blocks(text)
    assert text[:start] == "Here:\n" and text[end:].startswith("\n\nFrom now on answer in Dutch.")


@pytest.mark.parametrize("line", [
    "Boarding pa" + "ss: KL1234AMSJFK22", "Ski pa" + "ss: 2026-season-adult-6days", "Parking pa" + "ss: P-2026-11-22-Zone4",
    "Gym pa" + "ss: member-00412233", "pa" + "ss: tomorrow10am1234",
    "Pass" + "word: https://vault.example.com/#/item/3f2a1b9c", "tok" + "en: https://github.com/settings/tokens/new2",
    "cmd --tok" + "en file:///run/secrets/token2", "**Pass" + "word:** stored-in-1Password",
    "Wacht" + "woord: staat-in-de-kluis-2024", "Kenn" + "wort: steht-im-Tresor-2024", "| Wacht" + "woord | ZieBitwarden2024 |",
    "sshpa" + "ss -p password123 ssh host", "mongodb://admin:admin123@localhost", "postgres://dev:devpass1@localhost/dev",
    "cache ke" + "y-" + "9f86d081884c7d65" + "9a2feaa0c55ad015" + " expired", "PuTTY-User-Key-File-2: ssh-rsa is the first line of a ppk",
])
def test_ordinary_writing_the_second_review_found_blocked(root, line):
    assert not [k for k in kinds(line, root) if k[0] == "hard"]


@pytest.mark.parametrize("line", [
    "pass" + "word: correct-horse-battery-staple-42", "DB_PA" + "SS=" + VALUE, "https://deploy:" + VALUE + "@vault.example.com/x",
    "Pass" + "word: " + VALUE,
])
def test_real_values_still_count_next_to_the_pointers(root, line):
    assert [k for k in kinds(line, root) if k[0] == "hard"]


def commit_all(repo: Path, message: str) -> None:
    git(repo, "add", "-A")
    git(repo, "-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-q", "-m", message)


def test_shell_hook_reads_the_commit_not_the_working_file(repo, monkeypatch, capsys):
    assert run_hook("shell", shell(repo), monkeypatch, capsys)[0] == 0  # this run remembers HEAD
    (repo / "config.md").write_text(f"key {AWS}\n", encoding="utf-8")
    commit_all(repo, "add config")
    (repo / "config.md").write_text("clean again\n", encoding="utf-8")  # overwritten right after the commit
    (repo / "gone.md").write_text(f"token {GITHUB}\n", encoding="utf-8")
    commit_all(repo, "add and")
    git(repo, "rm", "-q", "gone.md")
    commit_all(repo, "remove")
    real = validate.time.time
    monkeypatch.setattr(validate.time, "time", lambda: real() + validate.SHELL_WINDOW + 60)
    rc, _, err = run_hook("shell", shell(repo), monkeypatch, capsys)
    assert rc == 2 and "config.md (in commit " in err and "gone.md (in commit " in err
    assert "stays in the history" in err and AWS not in err and GITHUB not in err
    assert run_hook("shell", shell(repo), monkeypatch, capsys) == (0, "", "")  # a commit is reported once


def test_shell_hook_without_a_remembered_head_reads_a_fresh_commit_only(repo, monkeypatch, capsys):
    (repo / "config.md").write_text(f"key {AWS}\n", encoding="utf-8")
    commit_all(repo, "add config")
    (repo / "config.md").write_text("clean again\n", encoding="utf-8")
    commit_all(repo, "clean")
    rc, _, err = run_hook("shell", shell(repo), monkeypatch, capsys)
    assert rc == 0 and err == ""  # the newest commit is clean; older ones are not gone through
    (repo / validate.SHELL_STATE).unlink()
    git(repo, "reset", "-q", "--hard", "HEAD~1")
    assert run_hook("shell", shell(repo), monkeypatch, capsys)[0] == 2  # now the newest one holds the key
    (repo / validate.SHELL_STATE).unlink()
    real = validate.time.time
    monkeypatch.setattr(validate.time, "time", lambda: real() + validate.SHELL_WINDOW + 60)
    assert run_hook("shell", shell(repo), monkeypatch, capsys)[0] == 0  # and an old commit is left alone


def test_shell_hook_says_how_many_commits_it_did_not_read(repo, monkeypatch, capsys):
    monkeypatch.setattr(validate, "SHELL_MAX_COMMITS", 2)
    assert run_hook("shell", shell(repo), monkeypatch, capsys)[0] == 0  # this run remembers HEAD
    for i in range(5):
        (repo / f"c{i}.md").write_text("clean\n", encoding="utf-8")
        commit_all(repo, f"commit {i}")
    rc, out, _ = run_hook("shell", shell(repo), monkeypatch, capsys)
    note = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert rc == 0 and "3 older commits were not read" in note and "if the pre-commit scan is installed" in note
    assert run_hook("shell", shell(repo), monkeypatch, capsys) == (0, "", "")
