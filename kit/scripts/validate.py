# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Secret scanner for a Claude Code workspace: hook, file check and git pre-commit in one.

Usage:
  validate.py --hook pre        PreToolUse hook (Edit|Write|NotebookEdit): reads the hook JSON on
                                stdin and blocks (exit 2, reason on stderr) when the new content
                                holds a hard secret, or a private term when configured to block.
  validate.py --hook post       PostToolUse hook: rescans the written file. A hard secret or a
                                private term goes back to Claude through exit 2 (the only way
                                Claude sees PostToolUse stderr); soft warnings on the new content
                                go back as additionalContext (exit 0, JSON on stdout).
  validate.py --file <path>...  Scan files on disk. Exit 2 on a hard finding.
  validate.py --staged          Scan the staged version of every staged file (git pre-commit).
                                Exit 2 on a hard finding or a private term.
  validate.py --stdin --path P  Scan stdin, label findings with P.

Three kinds of findings:
  hard     real credentials (API keys, tokens, private keys, passwords with a real-looking
           value). Always block.
  private  terms from .claude/sensitive-terms.txt (gitignored): customer names, internal
           hostnames, anything that must not leave the workspace. One term per line, matched as
           a whole word, case-insensitive; a line written as /regex/ is used as a regex.
           Lines starting with # are comments.
  soft     home-directory paths, email addresses, private IPv4 addresses. Warn only.

Configuration (optional), in nest.json at the workspace root:
  {"secret_scan": {
      "skip": ["vendor/**"],              globs that are not scanned at all
      "soft_skip": ["wiki/_inbox/**"],    globs where soft warnings stay silent (hard still blocks)
      "private_terms": "warn"             "warn" (default: feedback after writing) or "block"
  }}
Globs are relative to the workspace root, with / as separator; ** matches any depth.

The workspace root is $CLAUDE_PROJECT_DIR, else the hook's cwd, else the git top level, else
the current directory. Exit codes: 0 = fine (warnings possible), 2 = block / feedback.

Self-test: `validate.py --self-test` checks that the built-in test term is caught. The term is
assembled from two halves so that this file itself never contains it.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

TERMS_FILE = Path(".claude/sensitive-terms.txt")
CONFIG_FILE = Path("nest.json")
MAX_BYTES = 2_000_000
MAX_REPORT = 10

# Built from two halves: written whole, the hook would block every edit of this file.
SELF_TEST_TERM = "ZZ-NEST" + "TESTTERM-ZZ"

# Values that mark a placeholder, checked against the matched text only (not the whole line),
# so an "example" elsewhere on the line cannot hide a real key.
PLACEHOLDER_MARKERS = (
    "your-", "your_", "<", "${", "{{", "xxxx", "example", "placeholder", "changeme",
    "redacted", "dummy-", "dummy_", "fake-", "fake_", "-fake", "_fake", "sample",
)


def _entropy(s: str) -> float:
    if not s:
        return 0.0
    counts = {c: s.count(c) for c in set(s)}
    return -sum(n / len(s) * math.log2(n / len(s)) for n in counts.values())


def _real_looking(value: str) -> bool:
    """A credential-shaped value: letters and digits mixed, not a placeholder, some entropy."""
    v = value.strip("'\"")
    low = v.lower()
    if any(m in low for m in PLACEHOLDER_MARKERS):
        return False
    if not (re.search(r"[A-Za-z]", v) and re.search(r"\d", v)):
        return False
    return _entropy(v) >= 3.0


def _db_password(value: str) -> bool:
    """The password part of user:password@ is not a stock placeholder."""
    m = re.search(r"//[^:/\s]+:([^@\s]+)@", value)
    if not m:
        return False
    pw = m.group(1).lower()
    if pw in {"password", "pass", "passwd", "secret", "pwd", "changeme", "xxx", "***", "user", "admin"}:
        return False
    return not any(m in pw for m in PLACEHOLDER_MARKERS)


def _assigned_secret(value: str) -> bool:
    """A value after `password:`/`pwd=` etc. that looks like a secret, not a path.

    `pwd: /Users/x/project` in a log is the working directory, not a password."""
    value = value.strip("'\" ")
    if re.match(r"^(?:[/~]|\.{1,2}/|[A-Za-z]:\\)", value):
        return False
    return _real_looking(value)


@dataclass(frozen=True)
class Rule:
    name: str
    regex: re.Pattern[str]
    check: Callable[[str], bool] | None = None  # extra test on the matched text


def _r(name: str, pattern: str, check: Callable[[str], bool] | None = None, flags: int = 0) -> Rule:
    return Rule(name, re.compile(pattern, flags), check)


HARD_RULES: tuple[Rule, ...] = (
    _r("anthropic_key", r"\bsk-ant-[A-Za-z0-9_-]{32,}"),
    _r("openai_key", r"\bsk-(?!ant-)(?:proj-|svcacct-|admin-)?[A-Za-z0-9_-]{40,}"),
    _r("github_token", r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    _r("github_fine_grained", r"\bgithub_pat_[A-Za-z0-9_]{60,}\b"),
    _r("gitlab_token", r"\bglpat-[A-Za-z0-9_-]{20,}"),
    _r("aws_access_key", r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    _r("aws_secret_key", r"(?i)\baws_secret_access_key\b\s*[:=]\s*['\"]?[A-Za-z0-9/+]{40}\b"),
    _r("google_api_key", r"\bAIza[0-9A-Za-z_-]{35}\b"),
    _r("slack_token", r"\bxox[abposr]-[0-9]{6,}-[A-Za-z0-9-]{10,}"),
    _r("slack_webhook", r"https://hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[A-Za-z0-9]{20,}"),
    _r("stripe_secret", r"\b[sr]k_live_[A-Za-z0-9]{20,}\b"),
    _r("huggingface_token", r"\bhf_[A-Za-z0-9]{34,}\b"),
    _r("npm_token", r"\bnpm_[A-Za-z0-9]{36}\b"),
    _r("sendgrid_key", r"\bSG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}\b"),
    _r("private_key_block", r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY(?: BLOCK)?-----"),
    _r("jwt", r"\beyJ[A-Za-z0-9_-]{15,}\.eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}"),
    _r("bearer_token", r"(?i)\bbearer\s+[A-Za-z0-9_\-.=~+/]{24,}", lambda m: _real_looking(m.split()[-1])),
    _r("db_url_credentials", r"(?i)\b(?:postgres(?:ql)?|mysql|mariadb|mongodb(?:\+srv)?|redis|amqps?)://[^\s/:@]*:[^\s@]+@",
       _db_password),
    _r("secret_assignment",
       r"(?i)\b(?:password|passwd|pwd|secret|client_secret|api[_-]?key|apikey|access[_-]?token|auth[_-]?token|private[_-]?token)"
       r"\b['\"]?\s*[:=]\s*['\"]?[A-Za-z0-9_\-+/=.!@#%^&*~]{12,}",
       lambda m: _assigned_secret(re.split(r"[:=]\s*", m, maxsplit=1)[-1])),
)

SOFT_RULES: tuple[Rule, ...] = (
    _r("home_path", r"(?:/Users/|/home/)[A-Za-z][A-Za-z0-9._-]*/|\b[A-Za-z]:\\Users\\[A-Za-z][A-Za-z0-9._-]*\\"),
    _r("email", r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
       lambda m: not re.search(r"(?i)@(?:example\.(?:com|org|net)|users\.noreply\.github\.com)$|^noreply@|^no-reply@", m)),
    _r("private_ip", r"\b(?:10\.(?:\d{1,3}\.){2}\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b"),
)


@dataclass
class Finding:
    kind: str  # hard | private | soft
    line: int
    rule: str
    shown: str  # what the report shows: a masked value, never the full secret or term


def _mask(value: str) -> str:
    return value[:6] + "..." if len(value) > 8 else "***"


# ---------------------------------------------------------------- workspace and config


def workspace_root(hook_cwd: str | None = None) -> Path:
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env and Path(env).is_dir():
        return Path(env)
    if hook_cwd and Path(hook_cwd).is_dir():
        return Path(hook_cwd)
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=5,
                             check=False)
        if out.returncode == 0 and out.stdout.strip():
            return Path(out.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    return Path.cwd()


def load_config(root: Path) -> dict:
    try:
        data = json.loads((root / CONFIG_FILE).read_text(encoding="utf-8"))
        cfg = data.get("secret_scan") or {}
        return cfg if isinstance(cfg, dict) else {}
    except (OSError, ValueError):
        return {}


def load_private_rules(root: Path) -> tuple[list[Rule], list[str]]:
    """The private terms as rules (named by line number only), plus any warnings about the file."""
    rules = [Rule("private_term_selftest", re.compile(re.escape(SELF_TEST_TERM)))]
    warnings: list[str] = []
    path = root / TERMS_FILE
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return rules, warnings
    for i, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if len(line) > 2 and line.startswith("/") and line.endswith("/"):
            pattern, flags = line[1:-1], 0
        else:
            pattern, flags = r"(?<!\w)" + re.escape(line) + r"(?!\w)", re.IGNORECASE
        try:
            rules.append(Rule(f"private_term_line_{i}", re.compile(pattern, flags)))
        except re.error:
            warnings.append(f"invalid regex on line {i} of {TERMS_FILE}, skipped")
    return rules, warnings


def glob_to_regex(glob: str) -> re.Pattern[str]:
    out, i = "", 0
    while i < len(glob):
        if glob.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif glob.startswith("**", i):
            out, i = out + ".*", i + 2
        elif glob[i] == "*":
            out, i = out + "[^/]*", i + 1
        elif glob[i] == "?":
            out, i = out + "[^/]", i + 1
        else:
            out, i = out + re.escape(glob[i]), i + 1
    return re.compile(out + r"(?:/.*)?\Z")


def matches_any(rel: str, globs: list[str]) -> bool:
    return any(glob_to_regex(g.strip("/")).match(rel) for g in globs if isinstance(g, str) and g.strip("/"))


def relative(path: Path | str, root: Path) -> str:
    p = Path(str(path).replace("\\", "/"))
    try:
        return p.resolve().relative_to(root.resolve()).as_posix()
    except (ValueError, OSError):
        return p.as_posix()


# ---------------------------------------------------------------- scanning


class Scanner:
    def __init__(self, root: Path):
        self.root = root
        self.config = load_config(root)
        self.private_rules, self.warnings = load_private_rules(root)

    def skipped(self, rel: str) -> bool:
        return matches_any(rel, list(self.config.get("skip") or []))

    def soft_silent(self, rel: str) -> bool:
        # The scanner's own file holds the patterns it looks for; a warning about those is noise.
        if rel.replace("\\", "/").endswith("scripts/validate.py"):
            return True
        return matches_any(rel, list(self.config.get("soft_skip") or []))

    @property
    def block_private(self) -> bool:
        return str(self.config.get("private_terms", "warn")).lower() == "block"

    def scan(self, content: str, kinds: tuple[str, ...] = ("hard", "private", "soft")) -> list[Finding]:
        found: list[Finding] = []
        for n, line in enumerate(content.splitlines(), 1):
            hard_here = False
            if "hard" in kinds:
                for rule in HARD_RULES:
                    for m in rule.regex.finditer(line):
                        text = m.group(0)
                        if any(mk in text.lower() for mk in PLACEHOLDER_MARKERS) and rule.name not in ("private_key_block",):
                            continue
                        if rule.check and not rule.check(text):
                            continue
                        found.append(Finding("hard", n, rule.name, _mask(text)))
                        hard_here = True
                        break
            if "private" in kinds:
                for rule in self.private_rules:
                    if rule.regex.search(line):
                        found.append(Finding("private", n, rule.name, "(term not repeated)"))
            if "soft" in kinds and not hard_here:
                for rule in SOFT_RULES:
                    m = rule.regex.search(line)
                    if m and not (rule.check and not rule.check(m.group(0))):
                        found.append(Finding("soft", n, rule.name, _mask(m.group(0))))
        return found


def read_text_file(path: Path) -> str | None:
    """The file as text, or None for a binary, unreadable or oversized file."""
    try:
        if not path.is_file() or path.stat().st_size > MAX_BYTES:
            return None
        data = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in data[:8192]:
        return None
    return data.decode("utf-8", errors="replace")


def format_findings(findings: list[Finding], label: str) -> str:
    lines = []
    for kind, title in (("hard", "Secrets (blocked)"), ("private", f"Private terms from {TERMS_FILE.as_posix()}"),
                        ("soft", "Warnings")):
        group = [f for f in findings if f.kind == kind]
        if not group:
            continue
        lines.append(f"[secret-scan] {title} in {label}:")
        for f in group[:MAX_REPORT]:
            lines.append(f"  line {f.line}: {f.rule} {f.shown}")
        if len(group) > MAX_REPORT:
            lines.append(f"  ... and {len(group) - MAX_REPORT} more")
    if any(f.kind == "hard" for f in findings):
        lines.append("Replace the value with a placeholder such as <api-key> or a reference to where the secret "
                     "is stored (a password manager entry or an environment variable name).")
    if any(f.kind == "private" for f in findings):
        lines.append("A private term does not belong here unless this file stays private; use a placeholder "
                     "such as <client-codename> otherwise.")
    return "\n".join(lines)


# ---------------------------------------------------------------- hook modes


def new_content(tool_input: dict) -> str:
    """The text a tool call is about to write: Write content, Edit new_string, a legacy MultiEdit's
    edits, or a NotebookEdit cell."""
    parts: list[str] = []
    for key in ("content", "new_string", "new_source"):
        if isinstance(tool_input.get(key), str):
            parts.append(tool_input[key])
    for edit in tool_input.get("edits") or []:
        if isinstance(edit, dict) and isinstance(edit.get("new_string"), str):
            parts.append(edit["new_string"])
    return "\n".join(parts)


def target_path(tool_input: dict) -> str:
    return str(tool_input.get("file_path") or tool_input.get("notebook_path") or "")


def read_hook_input() -> dict:
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8", errors="replace") or "{}")
        return data if isinstance(data, dict) else {}
    except ValueError:
        return {}


def hook_pre(data: dict) -> int:
    tool_input = data.get("tool_input") or {}
    content = new_content(tool_input)
    if not content:
        return 0
    scanner = Scanner(workspace_root(data.get("cwd")))
    path = target_path(tool_input)
    rel = relative(path, scanner.root) if path else "<new content>"
    if path and scanner.skipped(rel):
        return 0
    kinds = ("hard", "private") if scanner.block_private else ("hard",)
    findings = scanner.scan(content, kinds)
    if findings:
        print(format_findings(findings, rel), file=sys.stderr)
        return 2
    return 0


def hook_post(data: dict) -> int:
    tool_input = data.get("tool_input") or {}
    path = target_path(tool_input)
    if not path:
        return 0
    scanner = Scanner(workspace_root(data.get("cwd")))
    rel = relative(path, scanner.root)
    if scanner.skipped(rel):
        return 0
    text = read_text_file(Path(path))
    serious = scanner.scan(text, ("hard", "private")) if text is not None else []
    soft = [] if scanner.soft_silent(rel) else scanner.scan(new_content(tool_input), ("soft",))
    if serious:
        print("[secret-scan] Found after writing; fix the file now.\n" + format_findings(serious + soft, rel),
              file=sys.stderr)
        return 2
    if soft:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                                 "additionalContext": format_findings(soft, rel)}}))
    return 0


# ---------------------------------------------------------------- command-line modes


def scan_paths(paths: list[str], private_blocks: bool) -> int:
    scanner = Scanner(workspace_root())
    worst = 0
    for p in paths:
        path = Path(p)
        rel = relative(path, scanner.root)
        if scanner.skipped(rel):
            continue
        text = read_text_file(path)
        if text is None:
            continue
        kinds = ("hard", "private") + (() if scanner.soft_silent(rel) else ("soft",))
        findings = scanner.scan(text, kinds)
        if findings:
            print(format_findings(findings, rel), file=sys.stderr)
        if any(f.kind == "hard" or (private_blocks and f.kind == "private") for f in findings):
            worst = 2
    return worst


def scan_staged() -> int:
    """Scan what is staged (the index), not the working tree: that is what the commit contains."""
    try:
        names = subprocess.run(["git", "diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR"],
                               capture_output=True, check=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        print("[secret-scan] not a git repository, nothing scanned", file=sys.stderr)
        return 0
    # The repository being committed, not $CLAUDE_PROJECT_DIR: a commit made from a session that
    # was started in another folder must still be scanned.
    try:
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=5,
                             check=True, encoding="utf-8", errors="replace").stdout.strip()
    except (OSError, subprocess.SubprocessError):
        top = ""
    root = Path(top) if top else workspace_root()
    scanner = Scanner(root)
    worst = 0
    for raw in names.split(b"\0"):
        rel = raw.decode("utf-8", errors="replace")
        if not rel or scanner.skipped(rel):
            continue
        try:
            blob = subprocess.run(["git", "show", f":{rel}"], capture_output=True, check=True, timeout=30,
                                  cwd=root).stdout
        except (OSError, subprocess.SubprocessError):
            print(f"[secret-scan] could not read the staged version of {rel}", file=sys.stderr)
            worst = 2
            continue
        if len(blob) > MAX_BYTES or b"\x00" in blob[:8192]:
            continue
        kinds = ("hard", "private") + (() if scanner.soft_silent(rel) else ("soft",))
        findings = scanner.scan(blob.decode("utf-8", errors="replace"), kinds)
        if findings:
            print(format_findings(findings, rel), file=sys.stderr)
        if any(f.kind in ("hard", "private") for f in findings):
            worst = 2
    if worst:
        print("[secret-scan] Commit blocked. Fix the files, stage them again and commit.", file=sys.stderr)
    return worst


def self_test() -> int:
    scanner = Scanner(workspace_root())
    hit = scanner.scan(f"a line with {SELF_TEST_TERM} in it", ("private",))
    ok = bool(hit)
    for w in scanner.warnings:
        print(f"[secret-scan] {w}", file=sys.stderr)
    print("secret-scan self-test: ok" if ok else "secret-scan self-test: FAILED")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Secret scanner for Claude Code hooks and git pre-commit.")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--hook", choices=("pre", "post"), help="Run as a Claude Code PreToolUse/PostToolUse hook")
    mode.add_argument("--file", nargs="+", metavar="PATH", help="Scan files on disk")
    mode.add_argument("--staged", action="store_true", help="Scan staged files (git pre-commit)")
    mode.add_argument("--stdin", action="store_true", help="Scan content from stdin")
    mode.add_argument("--self-test", action="store_true", help="Check that the built-in test term is caught")
    ap.add_argument("--path", default="<stdin>", help="Label for --stdin findings")
    ap.add_argument("--private-blocks", action="store_true", help="With --file/--stdin: exit 2 on a private term too")
    args = ap.parse_args(argv)

    if args.hook == "pre":
        return hook_pre(read_hook_input())
    if args.hook == "post":
        return hook_post(read_hook_input())
    if args.file:
        return scan_paths(args.file, args.private_blocks)
    if args.staged:
        return scan_staged()
    if args.self_test:
        return self_test()
    if args.stdin:
        scanner = Scanner(workspace_root())
        findings = scanner.scan(sys.stdin.read())
        if findings:
            print(format_findings(findings, args.path), file=sys.stderr)
        bad = any(f.kind == "hard" or (args.private_blocks and f.kind == "private") for f in findings)
        return 2 if bad else 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
