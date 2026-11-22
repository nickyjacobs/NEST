# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Secret scanner for a Claude Code workspace: hook, file check and git pre-commit in one.

Usage:
  validate.py --hook pre        PreToolUse hook (Edit|Write|NotebookEdit): reads the hook JSON on
                                stdin and blocks (exit 2, reason on stderr) when the new content
                                holds a hard secret, or a private term when configured to block.
                                Hook input that cannot be read is refused too.
  validate.py --hook post       PostToolUse hook: rescans the written file. A hard secret or a
                                private term goes back to Claude through exit 2 (the only way
                                Claude sees PostToolUse stderr); soft warnings on the new content
                                go back as additionalContext (exit 0, JSON on stdout).
  validate.py --hook shell      PostToolUse and PostToolUseFailure hook (Bash|PowerShell): a shell
                                command can write a file without the edit tools, so this scans
                                the files git reports as changed or untracked (not ignored) that
                                were written in the last two minutes. Same findings and exit
                                codes as --hook post, without the soft warnings. Silent outside
                                a git work tree or without git. It also looks at the files of
                                commits made since its previous run, and at the wiki's own
                                backup repository when nest.json names one (wiki_backup.git_dir).
                                Bounded per call (50 files, 8 MB, 15 seconds); what was left
                                out is said.
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

Files that are meant to hold private things are left alone after writing: CLAUDE.local.md, the
terms file itself, and a .env file that git ignores (any .env* file where git cannot say). The
private terms and the scans after a write skip them; a new secret written with an edit tool is
still blocked, and a commit that stages one of them is still scanned.

A file over 2 MB is not scanned and is named as skipped. A binary file is skipped silently.

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
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

TERMS_FILE = Path(".claude/sensitive-terms.txt")
CONFIG_FILE = Path("nest.json")
MAX_BYTES = 2_000_000
MAX_REPORT = 10
SHELL_WINDOW = 120  # seconds: how recently a file must be written for --hook shell to scan it
SHELL_MAX_FILES = 50
SHELL_MAX_BYTES = 8_000_000  # per run, so one command that wrote a lot cannot run the hook into its timeout
SHELL_SECONDS = 15.0
SHELL_STATE = Path(".claude/.session/shell-scan.json")  # the last HEAD seen, and files already scanned clean
SHELL_CACHE = 500
PRIVATE_HOMES = ("claude.local.md",)  # by file name, lower case; plus the terms file and ignored .env files

# Built from two halves: written whole, the hook would block every edit of this file.
SELF_TEST_TERM = "ZZ-NEST" + "TESTTERM-ZZ"

# Values that mark a placeholder, checked against the matched text only (not the whole line),
# so an "example" elsewhere on the line cannot hide a real key.
PLACEHOLDER_MARKERS = (
    "your-", "your_", "<", "${", "{{", "xxxx", "example", "placeholder", "changeme",
    "redacted", "dummy-", "dummy_", "fake-", "fake_", "-fake", "_fake", "sample",
    "replace-me", "replaceme", "replace_me", "change-me", "change_me", "insecure", "todo",
)


def _entropy(s: str) -> float:
    if not s:
        return 0.0
    counts = {c: s.count(c) for c in set(s)}
    return -sum(n / len(s) * math.log2(n / len(s)) for n in counts.values())


def _has_marker(value: str) -> bool:
    low = value.lower()
    return any(m in low for m in PLACEHOLDER_MARKERS)


def _real_looking(value: str) -> bool:
    """A credential-shaped value: letters and digits mixed, not a placeholder, some entropy."""
    v = value.strip("'\"")
    if _has_marker(v):
        return False
    if not (re.search(r"[A-Za-z]", v) and re.search(r"\d", v)):
        return False
    return _entropy(v) >= 3.0


STOCK_PASSWORDS = {"password", "pass", "passwd", "secret", "pwd", "pw", "changeme", "xxx", "***", "user", "admin",
                   "username", "token", "key", "apikey", "api_key", "root", "test", "guest", "default", "postgres",
                   "mysql", "redis", "mongo", "rabbitmq", "anonymous", "letmein", "qwerty"}
STOCK_PARTS = ("password", "passwd", "secret", "example", "changeme", "letmein")


def _literal_password(pw: str, user: str = "") -> bool:
    """A password written out in a URL or a command, not a stock word, a variable or a placeholder.

    A password equal to the user name (postgres:postgres), a stock word, or one built around
    "password" or "secret" is what an example file holds, not a credential."""
    low = pw.strip("'\"").lower()
    if not low or low in STOCK_PASSWORDS or low.startswith(("$", "%", "<", "{", "your")) or not low.strip(".*x"):
        return False
    name = user.strip("'\"").lower()
    if (name and (low == name or (len(name) >= 3 and name in low))) or any(part in low for part in STOCK_PARTS):
        return False
    return not _has_marker(low)


MANAGERS = {"1password", "bitwarden", "keepass", "keepassxc", "lastpass", "dashlane", "vault", "kluis", "tresor",
            "keychain", "safe"}


def _pointer(value: str) -> bool:
    """A value that says where the secret is, not what it is: an address (https://vault.example/...,
    file:///run/secrets/x) or a phrase that names a password manager (stored-in-1Password,
    staat-in-de-kluis-2024, ZieBitwarden2024)."""
    if re.match(r"[A-Za-z][A-Za-z0-9+.-]{1,30}://", value):
        return True
    words = re.split(r"[-_./\s]+|(?<=[a-z])(?=[A-Z])|(?<=[A-Za-z])(?=\d{2,}$)", value)
    return any(word.lower() in MANAGERS for word in words)


def _mixed_case(value: str) -> bool:
    """Upper case, lower case and a digit: what a generated key has and a hyphenated slug has not."""
    return bool(re.search(r"[A-Z]", value) and re.search(r"[a-z]", value) and re.search(r"\d", value))


def _wordy(value: str) -> bool:
    """Lower-case words with separators and at most a digit or two: a path or a phrase, not a token."""
    return bool(re.fullmatch(r"[a-z/._-]*\d{0,2}", value)) or bool(re.fullmatch(r"(?:[a-z]+[/._-])+[a-z]*\d{0,2}", value))


# A value that is code, not a literal: an attribute (settings.API_KEY), a call (hashlib.sha256(x)),
# a lookup (os.environ[...]), a list or a pattern, a constant's name (TELEGRAM_BOT_TOKEN) or a
# shell variable. Only unquoted values are judged this way.
CODE_LIKE = re.compile(r"^(?:[$%\[({]|[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+$|[A-Za-z_][\w.]*[(\[]|[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$)")
PATH_LIKE = re.compile(r"^(?:[/~]|\.{1,2}/|[A-Za-z]:\\)")


def _value(m: re.Match[str]) -> tuple[str, bool]:
    """The value of a match and whether it stood in quotes."""
    groups = m.groupdict()
    for name in ("dq", "sq", "bq"):
        if groups.get(name):
            return groups[name], True
    return (groups.get("raw") or groups.get("v") or "").rstrip(".,;)"), False


def _assigned_secret(m: re.Match[str]) -> bool:
    """A value after `password:`/`API_KEY=` etc. that looks like a secret, not a path or code.

    `pwd: /Users/x/project` in a log is the working directory, not a password, and
    `password = hashlib.sha256(raw)` is a call. The placeholder test looks at the value alone, so
    a name such as `example_password` cannot hide a real value."""
    value, quoted = _value(m)
    if len(value) < 10 or PATH_LIKE.match(value) or _pointer(value):
        return False
    if not quoted and CODE_LIKE.match(value):
        return False
    return _real_looking(value)


# What a private key block is, for the scan and for session_guard.py alike: the header, then key
# material, then the END line when there is one. A header with nothing after it is a sentence
# that quotes the header. Each line may start with what surrounds a pasted key: indentation (a
# YAML block), a Markdown quote mark, a quote, a line number with a bar. The line break may be a
# real one, an escaped one (JSON), or a space (a key on one line).
_KEY_PREFIX = r"""[ \t>|"'\d]{0,20}"""
_KEY_BREAK = r"""(?:["',]{0,2}[ \t]*\r?\n""" + _KEY_PREFIX + r"|\\r\\n|\\n)"
_KEY_CHUNK = r"[A-Za-z0-9+/=]"
KEY_BLOCK = re.compile(
    r"-----BEGIN [^-\n]{0,40}PRIVATE KEY[^-\n]{0,20}-----"
    r"(?:" + _KEY_BREAK + r"(?:Proc-Type|DEK-Info|Version|Comment|Charset|Hash):[^\n\\]{0,200})*"
    r"(?:" + _KEY_BREAK + r"{1,2}|[ \t]+)" + _KEY_CHUNK + r"{16,}"
    # A following line counts when it is key material to its end; on one line, only long runs do.
    r"(?:" + _KEY_BREAK + _KEY_CHUNK + r"{4,}(?![A-Za-z0-9+/=])(?=[ \t]*(?:\r?\n|\\r|\\n|\Z|[\"'`,]))"
    r"|[ \t]+" + _KEY_CHUNK + r"{16,})*"
    r"(?:(?:" + _KEY_BREAK + r"|[ \t]+)?-----END [^-\n]{0,60}-----)?")


def key_blocks(text: str) -> list[tuple[int, int]]:
    """Where the private key blocks in the text start and end."""
    return [m.span() for m in KEY_BLOCK.finditer(text)]


@dataclass(frozen=True)
class Rule:
    name: str
    regex: re.Pattern[str]
    check: Callable[[re.Match[str]], bool] | None = None  # None: any match that holds no placeholder marker

    def accepts(self, m: re.Match[str]) -> bool:
        return self.check(m) if self.check else not _has_marker(m.group(0))


def _r(name: str, pattern: str, check: Callable[[re.Match[str]], bool] | None = None, flags: int = 0) -> Rule:
    return Rule(name, re.compile(pattern, flags), check)


# The name before : or = ends in one of these, so DB_PASSWORD, JWT_SECRET and bot_token count too.
# pass and pw only as the end of a longer name (DB_PASS, smtp.pw) or straight before an = (PASS=x):
# "Boarding pass: KL1234" and "compass:" are not about a password.
SECRET_NAMES = (r"(?:password|passwd|passphrase|wachtwoord|passwort|kennwort|pwd|secret|token|apikey|api[ _-]?key|"
                r"(?:secret|access|private|account|auth|signing|encryption)[_-]?key|"
                r"""(?<=[_.-])(?:pass|pw)|(?<![A-Za-z])(?:pass|pw)(?=["']?=))""")
# After the name: an optional closing quote or Markdown emphasis, the separator, optional emphasis.
# White space is bounded: an open-ended \\s* on both sides makes a long run of spaces take minutes.
SEPARATOR = r"""["'*`]{0,3}[ \t]{0,4}(?::=|=>|[:=])[ \t]{0,4}(?:\*{1,2}[ \t]{0,4})?"""
VALUE = r"""(?:"(?P<dq>[^"\s]{10,200})"|'(?P<sq>[^'\s]{10,200})'|`(?P<bq>[^`\s]{10,200})`|(?P<raw>[^\s'"`]{10,200}))"""
DB_SCHEMES = r"(?:postgres(?:ql)?|mysql|mariadb|mongodb(?:\+srv)?|redis|amqps?)"
NOT_IN_WORD = r"(?<![A-Za-z0-9_-])"

HARD_RULES: tuple[Rule, ...] = (
    _r("anthropic_key", r"\bsk-ant-[A-Za-z0-9_-]{32,}"),
    # A generated key mixes cases and digits; a slug such as sk-learn-is-a-library does not.
    _r("openai_key", r"\bsk-(?!ant-)(?:proj-|svcacct-|admin-)?[A-Za-z0-9_-]{40,}",
       lambda m: _mixed_case(m.group(0)) and not _has_marker(m.group(0))),
    _r("github_token", r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    _r("github_fine_grained", r"\bgithub_pat_[A-Za-z0-9_]{60,}\b"),
    _r("gitlab_token", r"\bgl(?:pat|dt)-[A-Za-z0-9_-]{20,}"),
    _r("aws_access_key", r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    _r("aws_secret_key", r"(?i)\baws_secret_access_key\b\s*[:=]\s*['\"]?[A-Za-z0-9/+]{40}\b"),
    _r("azure_storage_key", r"(?i)\bAccountKey=[A-Za-z0-9+/]{60,}={0,2}"),
    _r("google_api_key", r"\bAIza[0-9A-Za-z_-]{35}\b"),
    _r("google_oauth_secret", r"\bGOCSPX-[A-Za-z0-9_-]{28}\b"),
    _r("slack_token", r"\bxox[abposr]-[0-9]{6,}-[A-Za-z0-9-]{10,}"),
    _r("slack_app_token", r"\bxapp-\d-[A-Z0-9]+-\d+-[A-Za-z0-9]{32,}"),
    _r("slack_webhook", r"https://hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[A-Za-z0-9]{20,}"),
    _r("discord_webhook", r"https://(?:\w+\.)?discord(?:app)?\.com/api/webhooks/\d+/[A-Za-z0-9_-]{30,}"),
    _r("stripe_secret", r"\b[sr]k_(?:live|test)_[A-Za-z0-9]{20,}\b"),
    _r("stripe_webhook_secret", r"\bwhsec_[A-Za-z0-9]{24,}\b"),
    _r("huggingface_token", r"\bhf_[A-Za-z0-9]{34,}\b"),
    _r("npm_token", r"\bnpm_[A-Za-z0-9]{36}\b"),
    _r("pypi_token", r"\bpypi-AgEIcHlwaS5vcmc[A-Za-z0-9_-]{50,}"),
    _r("docker_token", r"\bdckr_pat_[A-Za-z0-9_-]{27,}"),
    _r("digitalocean_token", r"\bdo[por]_v1_[a-f0-9]{64}\b"),
    _r("vault_token", r"\bhvs\.[A-Za-z0-9_-]{24,}"),
    # SK plus 32 hex is also what a stock number looks like: not after the word SKU.
    _r("twilio_key", r"\bSK[0-9a-f]{32}\b", lambda m: not re.search(r"(?i)\bsku\b[^A-Za-z0-9]*$", m.string[:m.start()])),
    _r("telegram_bot_token", r"\b\d{8,10}:AA[A-Za-z0-9_-]{33}\b"),
    _r("tavily_key", r"\btvly-[A-Za-z0-9_-]{20,}"),
    _r("notion_token", r"\b(?:ntn_|secret_)[A-Za-z0-9]{40,}\b"),
    _r("age_secret_key", r"\bAGE-SECRET-KEY-1[QPZRY9X8GF2TVDW0S3JN54KHCE6MUA7L]{58}\b"),
    _r("linear_key", r"\blin_api_[A-Za-z0-9]{40}\b"),
    _r("figma_token", r"\bfigd_[A-Za-z0-9_-]{40,}"),
    _r("shopify_token", r"\bshp(?:at|ss|ca|pa)_[a-f0-9]{32}\b"),
    _r("atlassian_token", r"\bATATT3xFfGF0[A-Za-z0-9_=-]{40,}"),
    _r("square_token", r"\bsq0(?:atp|csp)-[A-Za-z0-9_-]{22,}"),
    _r("sendgrid_key", r"\bSG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}\b"),
    # A private key block spans lines and is found by key_blocks(), not by a rule per line.
    _r("putty_private_key", r"^\s*PuTTY-User-Key-File-\d+:\s*[A-Za-z0-9@._-]+\s*$", lambda m: True),
    _r("jwt", NOT_IN_WORD + r"eyJ[A-Za-z0-9_-]{15,2000}\.eyJ[A-Za-z0-9_-]{15,4000}\.[A-Za-z0-9_-]{15,2000}"),
    _r("bearer_token", r"(?i)\bbearer\s+(?P<v>[A-Za-z0-9_\-.=~+/]{24,2000})",
       lambda m: _real_looking(m.group("v")) and not _wordy(m.group("v"))),
    _r("basic_auth_header", r"(?i)\bauthorization:\s*basic\s+(?P<v>[A-Za-z0-9+/]{16,2000}={0,2})",
       lambda m: not _has_marker(m.group("v"))),
    _r("db_url_credentials", r"(?i)\b" + DB_SCHEMES + r"://(?P<u>[^\s/:@]{0,200}):(?P<v>[^\s@]{1,200})@",
       lambda m: _literal_password(m.group("v"), m.group("u"))),
    # Any other scheme with user:password@, such as an https clone address or mssql+pyodbc://.
    # Digits alone between : and @ are a port.
    _r("url_credentials", r"(?i)\b(?!" + DB_SCHEMES + r"://)[a-z][a-z0-9+.-]{1,30}://(?P<u>[^\s/:@]{0,200}):(?P<v>[^\s/@]{3,200})@",
       lambda m: _literal_password(m.group("v"), m.group("u")) and not m.group("v").isdigit()),
    # A token alone before the @, as in a clone address.
    _r("url_token", r"(?i)\bhttps?://(?P<v>[A-Za-z0-9_-]{20,200})@", lambda m: _real_looking(m.group("v"))),
    _r("curl_credentials", r"\bcurl\b[^\n]{0,300}?\s(?:-u|--user)[\s=]+['\"]?(?P<u>[^\s:'\"]{1,100}):(?P<v>[^\s'\"]{6,200})",
       lambda m: _literal_password(m.group("v"), m.group("u"))),
    # --password value, sshpass -p value: the value follows a space, not a separator.
    _r("cli_password", r"(?i)(?:(?<![\w-])--(?:password|passwd|pass|token|secret|api-key|auth-token)|\bsshpass\s+-p)\s+"
       r"""['"]?(?P<v>[^\s'"]{8,200})""",
       lambda m: not m.group("v").startswith(("-", "$", "<", "%")) and not PATH_LIKE.match(m.group("v"))
       and not CODE_LIKE.match(m.group("v")) and not _pointer(m.group("v"))
       and not any(part in m.group("v").lower() for part in STOCK_PARTS) and _real_looking(m.group("v"))),
    _r("xml_secret", r"(?i)<[\w.:-]{0,60}?(?:password|passwd|secret|token|api[_-]?key)>(?P<v>[^<\s]{8,200})</",
       lambda m: _real_looking(m.group("v")) and not _pointer(m.group("v"))),
    _r("xml_secret", r"""(?i)\bkey=["'][\w.:-]{0,60}?(?:password|passwd|secret|token|api[_-]?key)["']\s+value=["'](?P<v>[^"'\s]{8,200})""",
       lambda m: _real_looking(m.group("v"))),
    # A Markdown table row: | API key | value |
    _r("table_secret", r"(?i)\|[^|\n]{0,40}?(?:password|wachtwoord|passwort|kennwort|secret|token|api[ _-]?key)[^|\n]{0,20}\|\s*`?"
       r"(?P<v>[^\s|`]{10,200})`?\s*\|",
       lambda m: _mixed_case(m.group("v")) and not _has_marker(m.group("v")) and not PATH_LIKE.match(m.group("v"))
       and not _pointer(m.group("v"))),
    _r("secret_assignment", r"(?i)" + SECRET_NAMES + SEPARATOR + VALUE, _assigned_secret),
)

SOFT_RULES: tuple[Rule, ...] = (
    _r("home_path", r"(?:/Users/|/home/)[A-Za-z][A-Za-z0-9._-]*/|\b[A-Za-z]:\\Users\\[A-Za-z][A-Za-z0-9._-]*\\"),
    # Bounded on both sides: an unbounded local part makes a long dotted line take seconds.
    _r("email", r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9.-]{1,255}\.[A-Za-z]{2,}\b",
       lambda m: not re.search(r"(?i)@(?:example\.(?:com|org|net)|users\.noreply\.github\.com)$|^noreply@|^no-reply@",
                               m.group(0))),
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
    return git_top() or Path.cwd()


def decode(data: bytes) -> str | None:
    """Bytes as text, or None for binary content. A byte order mark is honoured, so a file saved
    as UTF-16 (Windows PowerShell's `>` does that) or as UTF-8 with a mark reads like any other."""
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", errors="replace")
    head = data[:8192]
    if b"\x00" in head:
        # UTF-16 without a mark: every other byte of plain text is zero, on one side only.
        even, odd = head[0::2].count(0), head[1::2].count(0)
        half = max(len(head) // 2, 1)
        if odd / half > 0.5 and even / half < 0.05:
            return data.decode("utf-16-le", errors="replace")
        if even / half > 0.5 and odd / half < 0.05:
            return data.decode("utf-16-be", errors="replace")
        return None
    return data.decode("utf-8-sig", errors="replace")


def git(args: list[str], cwd: Path | str | None = None, timeout: float = 10) -> subprocess.CompletedProcess[bytes] | None:
    """A git call, or None when git is missing, hangs or cannot start in `cwd`."""
    try:
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True, timeout=timeout, check=False)
    except (OSError, subprocess.SubprocessError):
        return None


def git_top(cwd: Path | str | None = None) -> Path | None:
    out = git(["rev-parse", "--show-toplevel"], cwd, timeout=5)
    top = os.fsdecode(out.stdout).strip() if out and out.returncode == 0 else ""
    return Path(top) if top else None


def load_config(root: Path) -> dict:
    try:
        data = json.loads((root / CONFIG_FILE).read_text(encoding="utf-8-sig"))
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
        text = decode(path.read_bytes())
    except OSError:
        return rules, warnings
    if text is None:
        warnings.append(f"{TERMS_FILE.as_posix()} is not a text file, so no private term is checked; save it as UTF-8")
        return rules, warnings
    lines = text.splitlines()
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

    def globs(self, key: str) -> list[str]:
        """A list option from nest.json. One glob written as a plain string counts as a list of
        one (iterating it per character would turn `*` into "skip everything")."""
        value = self.config.get(key)
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            wrong = [item for item in value if not isinstance(item, str)]
            if wrong:
                self.warn(f'secret_scan.{key} in nest.json holds something that is not text; that entry is ignored')
            return [item for item in value if isinstance(item, str)]
        self.warn(f'secret_scan.{key} in nest.json must be a list of globs; it is ignored')
        return []

    def warn(self, message: str) -> None:
        if message not in self.warnings:
            self.warnings.append(message)

    def skipped(self, rel: str) -> bool:
        return matches_any(rel, self.globs("skip"))

    def soft_silent(self, rel: str) -> bool:
        # The scanner's own file holds the patterns it looks for; a warning about those is noise.
        if rel.replace("\\", "/").endswith("scripts/validate.py"):
            return True
        return matches_any(rel, self.globs("soft_skip"))

    @property
    def block_private(self) -> bool:
        return str(self.config.get("private_terms", "warn")).lower() == "block"

    def private_home(self, path: Path | str, rel: str) -> bool:
        """A file that is meant to hold private things: CLAUDE.local.md, the terms file, and a
        .env file that git ignores (any .env* file where git cannot say)."""
        name = rel.replace("\\", "/").rsplit("/", 1)[-1].lower()
        if name in PRIVATE_HOMES or rel.replace("\\", "/").lower() == TERMS_FILE.as_posix().lower():
            return True
        if name != ".env" and not name.startswith(".env."):
            return False
        target = Path(str(path).replace("\\", "/"))
        if not target.is_absolute():
            target = self.root / target
        folder = target.parent if target.parent.is_dir() else self.root
        out = git(["check-ignore", "-q", "--", str(target)], folder, timeout=5)
        return out.returncode == 0 if out and out.returncode in (0, 1) else True

    def scan(self, content: str, kinds: tuple[str, ...] = ("hard", "private", "soft")) -> list[Finding]:
        found: list[Finding] = []
        key_lines = ({content.count("\n", 0, start) + 1 for start, _ in key_blocks(content)}
                     if "hard" in kinds and "PRIVATE KEY" in content else set())
        for n, line in enumerate(content.splitlines(), 1):
            hard_here = False
            if n in key_lines:
                found.append(Finding("hard", n, "private_key_block", "-----B..."))
                hard_here = True
            if "hard" in kinds:
                for rule in HARD_RULES:
                    for m in rule.regex.finditer(line):
                        if rule.accepts(m):
                            found.append(Finding("hard", n, rule.name, _mask(m.group(0))))
                            hard_here = True
                            break
            if "private" in kinds:
                for rule in self.private_rules:
                    if rule.regex.search(line):
                        found.append(Finding("private", n, rule.name, "(term not repeated)"))
            if "soft" in kinds and not hard_here:
                for rule in SOFT_RULES:
                    if rule.name == "email" and "@" not in line:
                        continue
                    m = rule.regex.search(line)
                    if m and rule.accepts(m):
                        found.append(Finding("soft", n, rule.name, _mask(m.group(0))))
        return found


TOO_LARGE = f"larger than {MAX_BYTES // 1_000_000} MB"


def load_text(path: Path) -> tuple[str | None, str]:
    """The file as text, or None with the reason: "" for a binary or unreadable file (nothing to
    say), TOO_LARGE for a file that was skipped for its size (worth saying)."""
    try:
        if not path.is_file():
            return None, ""
        if path.stat().st_size > MAX_BYTES:
            return None, TOO_LARGE
        data = path.read_bytes()
    except OSError:
        return None, ""
    return decode(data), ""


def skipped_line(rel: str, reason: str) -> str:
    return f"[secret-scan] {rel} was not scanned: {reason}"


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


def read_hook_input() -> dict | None:
    """The hook JSON, read as UTF-8 bytes whatever the console code page is. None when it is not
    a JSON object with a `tool_input` object: the caller decides what an unreadable call means."""
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8", errors="replace"))
    except (ValueError, OSError, AttributeError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("tool_input", {}), dict):
        return None
    return data


def hook_context(text: str, event: str = "PostToolUse") -> None:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}))


def hook_pre(data: dict | None) -> int:
    if data is None:
        # Failing open here would let a write through unscanned, without anyone noticing.
        print("[secret-scan] the hook input could not be read, so this write is refused. Try the call again.",
              file=sys.stderr)
        return 2
    tool_input = data.get("tool_input") or {}
    content = new_content(tool_input)
    if not content:
        return 0
    scanner = Scanner(workspace_root(data.get("cwd")))
    path = target_path(tool_input)
    rel = relative(path, scanner.root) if path else "<new content>"
    if path and scanner.skipped(rel):
        return 0
    private = scanner.block_private and not (path and scanner.private_home(path, rel))
    findings = scanner.scan(content, ("hard", "private") if private else ("hard",))
    if findings:
        print(format_findings(findings, rel), file=sys.stderr)
        return 2
    return 0


def hook_post(data: dict | None) -> int:
    if data is None:
        return 0
    tool_input = data.get("tool_input") or {}
    path = target_path(tool_input)
    if not path:
        return 0
    scanner = Scanner(workspace_root(data.get("cwd")))
    rel = relative(path, scanner.root)
    if scanner.skipped(rel) or scanner.private_home(path, rel):
        return 0
    text, reason = load_text(Path(path))
    serious = scanner.scan(text, ("hard", "private")) if text is not None else []
    soft = [] if scanner.soft_silent(rel) else scanner.scan(new_content(tool_input), ("soft",))
    if serious:
        print("[secret-scan] Found after writing; fix the file now.\n" + format_findings(serious + soft, rel),
              file=sys.stderr)
        return 2
    notes = ([skipped_line(rel, reason)] if reason else []) + ([format_findings(soft, rel)] if soft else [])
    if notes:
        hook_context("\n".join(notes))
    return 0


def touched(path: Path) -> tuple[float, int, int] | None:
    """When the file last changed, its size and a stamp for the cache; None when it is not a
    plain file. The newer of the modification time and the status change time: a copied, moved or
    unpacked file keeps an old modification time, but its status change is from now."""
    try:
        if path.is_symlink() or not path.is_file():
            return None
        st = path.stat()
    except OSError:
        return None
    return max(st.st_mtime, st.st_ctime), st.st_size, max(st.st_mtime_ns, st.st_ctime_ns)


def status_files(top: Path, repo: list[str] | None = None) -> list[Path]:
    """The files git reports as changed or untracked; ignored files are not listed. `repo` points
    git at a separate git dir and work tree (the wiki backup)."""
    out = git([*(repo or []), "--no-optional-locks", "status", "--porcelain", "-z", "--untracked-files=all",
               "--no-renames"], top)
    if not out or out.returncode != 0:
        return []
    return [top / os.fsdecode(entry[3:]) for entry in out.stdout.split(b"\0") if len(entry) >= 4]


SHELL_MAX_COMMITS = 20


def new_commits(top: Path, state: dict, now: float) -> tuple[list[tuple[str, str]], int]:
    """(commit, path) for every file added or changed by the commits made since the previous run
    of the hook, newest commit first, and how many older commits were left unread because there
    were more than SHELL_MAX_COMMITS. A command that writes a file and commits it in one go leaves
    nothing for `git status` to report, and the file may be overwritten or removed right after,
    so the commit itself is read. Without a remembered HEAD: the newest commit, when it is
    younger than SHELL_WINDOW. Other branches and stashes are not looked at."""
    out = git(["rev-parse", "--verify", "-q", "HEAD"], top, timeout=5)
    head = out.stdout.decode("ascii", errors="replace").strip() if out and out.returncode == 0 else ""
    heads = state.setdefault("heads", {})
    old = heads.get(str(top))
    if head:
        heads[str(top)] = head
    if not head or old == head:
        return [], 0
    unread = 0
    if isinstance(old, str) and re.fullmatch(r"[0-9a-f]{7,64}", old):
        listed = git(["rev-list", f"--max-count={SHELL_MAX_COMMITS}", f"{old}..{head}"], top)
        commits = listed.stdout.decode("ascii", errors="replace").split() if listed and listed.returncode == 0 else []
        if len(commits) >= SHELL_MAX_COMMITS:
            counted = git(["rev-list", "--count", f"{old}..{head}"], top)
            total = counted.stdout.decode("ascii", errors="replace").strip() if counted and counted.returncode == 0 else ""
            unread = max(int(total) - len(commits), 0) if total.isdigit() else 0
    else:
        when = git(["log", "-1", "--format=%ct", head], top, timeout=5)
        stamp = when.stdout.decode("ascii", errors="replace").strip() if when and when.returncode == 0 else ""
        commits = [head] if stamp.isdigit() and now - int(stamp) <= SHELL_WINDOW else []
    found: list[tuple[str, str]] = []
    for commit in commits:
        names = git(["diff-tree", "--no-commit-id", "--name-only", "-r", "-z", "--root", "--no-renames",
                     "--diff-filter=ACMR", commit], top)
        if names and names.returncode == 0:
            found += [(commit, os.fsdecode(name)) for name in names.stdout.split(b"\0") if name]
    return found, unread


def backup_repo(root: Path) -> tuple[Path, list[str]] | None:
    """The wiki folder and the git options for its own backup repository, when nest.json names
    one: the workspace ignores that folder, so the workspace's own status never lists it."""
    try:
        conf = json.loads((root / CONFIG_FILE).read_text(encoding="utf-8-sig"))
        raw = (conf.get("wiki_backup") or {}).get("git_dir") if isinstance(conf, dict) else None
    except (OSError, ValueError, AttributeError):
        return None
    if not isinstance(raw, str) or not raw:
        return None
    git_dir = Path(os.path.expanduser(raw))
    if not git_dir.is_absolute():
        git_dir = root / git_dir
    wiki = root / "wiki"
    try:
        env = os.environ.get("NEST_WIKI_CONFIG")
        config_path = Path(env).expanduser() if env else root / "wiki.config.json"
        wiki_conf = json.loads(config_path.read_text(encoding="utf-8-sig"))
        if isinstance(wiki_conf, dict) and isinstance(wiki_conf.get("wiki_dir"), str) and wiki_conf["wiki_dir"]:
            wiki = config_path.parent / wiki_conf["wiki_dir"]
    except (OSError, ValueError):
        pass
    if not git_dir.is_dir() or not wiki.is_dir():
        return None
    return wiki, ["--git-dir", str(git_dir), "--work-tree", str(wiki)]


def load_shell_state(root: Path) -> dict:
    try:
        data = json.loads((root / SHELL_STATE).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_shell_state(root: Path, state: dict) -> None:
    """Best effort, and only in a workspace that has a .claude folder: no litter elsewhere."""
    try:
        if not (root / ".claude").is_dir():
            return
        clean = state.get("clean")
        if isinstance(clean, dict) and len(clean) > SHELL_CACHE:
            state["clean"] = dict(list(clean.items())[-SHELL_CACHE:])
        path = root / SHELL_STATE
        # The folder also holds the user's own messages (session_guard.py): for the user alone.
        path.parent.mkdir(parents=True, exist_ok=True)
        if os.name != "nt" and (path.parent.stat().st_mode & 0o077):
            path.parent.chmod(0o700)
        tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        with os.fdopen(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8") as fh:
            fh.write(json.dumps(state))
        tmp.replace(path)
    except OSError:
        pass


def hook_shell(data: dict | None) -> int:
    """After a shell command: scan what it may have written. A shell can write a file without the
    edit tools (a redirect, a heredoc, sed -i, Set-Content), and no hook sees that content.

    Looked at: files git reports as changed or untracked that changed within SHELL_WINDOW, the
    same in the wiki's own backup repository when nest.json names one, and the files of commits
    made since the previous run. Bounded by a number of files, a number of bytes and a time; what
    was left out is said. A file scanned clean is not read again until it changes."""
    if data is None:
        return 0
    cwd = data.get("cwd") if isinstance(data.get("cwd"), str) else None
    top = None
    for candidate in (cwd, os.environ.get("CLAUDE_PROJECT_DIR")):
        if candidate and Path(candidate).is_dir():
            top = git_top(candidate)
            if top:
                break
    root = workspace_root(cwd)
    backup = backup_repo(root)
    if top is None and backup is None:
        return 0
    started = time.monotonic()
    now = time.time()
    state = load_shell_state(root)
    before = json.dumps(state, sort_keys=True)
    recent = status_files(top) if top else []
    if backup:
        recent += status_files(backup[0], backup[1])
    committed, unread_commits = new_commits(top, state, now) if top else ([], 0)
    clean = state.get("clean") if isinstance(state.get("clean"), dict) else {}
    state["clean"] = clean
    todo: dict[Path, tuple[float, int, int]] = {}
    for path in recent:
        info = touched(path)
        if info is None or path in todo or now - info[0] > SHELL_WINDOW:
            continue
        if path == root / SHELL_STATE:
            continue
        if clean.get(str(path)) == [info[2], info[1]]:
            continue
        todo[path] = info
    if not todo and not committed and not unread_commits:
        if json.dumps(state, sort_keys=True) != before:
            save_shell_state(root, state)
        return 0
    scanner = Scanner(root)
    reports: list[str] = []
    notes: list[str] = []
    left_out = spent = done = 0

    def over_budget() -> bool:
        return done >= SHELL_MAX_FILES or spent > SHELL_MAX_BYTES or time.monotonic() - started > SHELL_SECONDS

    # The commits first: the working files are still there for the next run, a commit is not looked at again.
    for commit, name in committed:
        if over_budget():
            left_out += 1
            continue
        rel = relative(top / name, scanner.root)
        if scanner.skipped(rel):
            continue
        label = f"{rel} (in commit {commit[:10]})"
        shown = git(["show", f"{commit}:{name}"], top, timeout=10)
        if not shown or shown.returncode != 0:
            continue
        done += 1
        spent += len(shown.stdout)
        if len(shown.stdout) > MAX_BYTES:
            notes.append(skipped_line(label, TOO_LARGE))
            continue
        text = decode(shown.stdout)
        findings = scanner.scan(text, ("hard", "private")) if text is not None else []
        if findings:
            reports.append(format_findings(findings, label))
    if any("(in commit " in report for report in reports):
        reports.append("A secret in a commit stays in the history after the file is fixed: tell the user, "
                       "who decides whether to rewrite the commit and to replace the secret.")
    for path, info in sorted(todo.items(), key=lambda item: item[1][0], reverse=True):
        if over_budget():
            left_out += 1
            continue
        done += 1
        rel = relative(path, scanner.root)
        if scanner.skipped(rel) or scanner.private_home(path, rel):
            continue
        text, reason = load_text(path)
        if reason:
            notes.append(skipped_line(rel, reason))
        if text is None:
            continue
        spent += info[1]
        findings = scanner.scan(text, ("hard", "private"))
        if findings:
            reports.append(format_findings(findings, rel))
            clean.pop(str(path), None)
        else:
            clean.pop(str(path), None)
            clean[str(path)] = [info[2], info[1]]
    save_shell_state(root, state)
    if unread_commits:
        notes.append(f"[secret-scan] {unread_commits} older commit{'s were' if unread_commits != 1 else ' was'} not read "
                     f"after this command (at most {SHELL_MAX_COMMITS} new commits are read per run); the scan before "
                     "a commit covers them if the pre-commit scan is installed.")
    if left_out:
        notes.append(f"[secret-scan] {left_out} more changed file{'s were' if left_out != 1 else ' was'} not scanned "
                     "after this command (the scan after a shell command is bounded); the scan before a commit "
                     "covers them if the pre-commit scan is installed.")
    if reports:
        print("[secret-scan] Found after a shell command; fix the file now.\n" + "\n".join(reports + notes),
              file=sys.stderr)
        return 2
    if notes:
        event = data.get("hook_event_name")
        hook_context("\n".join(notes), event if event in ("PostToolUse", "PostToolUseFailure") else "PostToolUse")
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
        text, reason = load_text(path)
        if reason:
            print(skipped_line(rel, reason), file=sys.stderr)
        if text is None:
            continue
        kinds = ("hard", "private") + (() if scanner.soft_silent(rel) else ("soft",))
        findings = scanner.scan(text, kinds)
        if findings:
            print(format_findings(findings, rel), file=sys.stderr)
        if any(f.kind == "hard" or (private_blocks and f.kind == "private") for f in findings):
            worst = 2
    return worst


def staged_gitlinks(root: Path) -> set[str]:
    """Staged entries that are not files: a submodule is a commit reference (mode 160000)."""
    out = git(["ls-files", "--stage", "-z"], root, timeout=30)
    links: set[str] = set()
    for entry in (out.stdout if out and out.returncode == 0 else b"").split(b"\0"):
        meta, _, name = entry.partition(b"\t")
        if meta.startswith(b"160000 "):
            links.add(os.fsdecode(name))
    return links


def scan_staged() -> int:
    """Scan what is staged (the index), not the working tree: that is what the commit contains."""
    listed = git(["diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR"], timeout=30)
    if not listed or listed.returncode != 0:
        print("[secret-scan] not a git repository, nothing scanned", file=sys.stderr)
        return 0
    # The repository being committed, not $CLAUDE_PROJECT_DIR: a commit made from a session that
    # was started in another folder must still be scanned.
    root = git_top() or workspace_root()
    scanner = Scanner(root)
    for w in scanner.warnings:
        print(f"[secret-scan] {w}", file=sys.stderr)
    links = staged_gitlinks(root)
    worst = 0
    for raw in listed.stdout.split(b"\0"):
        rel = os.fsdecode(raw)
        if not rel or rel in links or scanner.skipped(rel):
            continue
        shown = git(["show", f":{rel}"], root, timeout=30)
        if not shown or shown.returncode != 0:
            print(f"[secret-scan] could not read the staged version of {rel}", file=sys.stderr)
            worst = 2
            continue
        blob = shown.stdout
        if len(blob) > MAX_BYTES:
            print(skipped_line(rel, TOO_LARGE), file=sys.stderr)
            continue
        text = decode(blob)
        if text is None:
            continue
        kinds = ("hard", "private") + (() if scanner.soft_silent(rel) else ("soft",))
        findings = scanner.scan(text, kinds)
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
    mode.add_argument("--hook", choices=("pre", "post", "shell"),
                      help="Run as a Claude Code hook: before a write, after a write, after a shell command")
    mode.add_argument("--file", nargs="+", metavar="PATH", help="Scan files on disk")
    mode.add_argument("--staged", action="store_true", help="Scan staged files (git pre-commit)")
    mode.add_argument("--stdin", action="store_true", help="Scan content from stdin")
    mode.add_argument("--self-test", action="store_true", help="Check that the built-in test term is caught")
    ap.add_argument("--path", default="<stdin>", help="Label for --stdin findings")
    ap.add_argument("--private-blocks", action="store_true", help="With --file/--stdin: exit 2 on a private term too")
    args = ap.parse_args(argv)

    if args.hook:
        return {"pre": hook_pre, "post": hook_post, "shell": hook_shell}[args.hook](read_hook_input())
    if args.file:
        return scan_paths(args.file, args.private_blocks)
    if args.staged:
        return scan_staged()
    if args.self_test:
        return self_test()
    if args.stdin:
        scanner = Scanner(workspace_root())
        findings = scanner.scan(decode(sys.stdin.buffer.read()) or "")
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
