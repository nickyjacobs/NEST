# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Keeps a workspace in step with new NEST releases, without touching what the user changed.

A workspace is built once from the NEST kit and then lives its own life. NEST keeps getting fixes
and features. This script does the exact part of bringing them over; the `nest-update` skill does
the talking and the judgement.

The stamp. `nest.json` at the workspace root records what the workspace was built from:

  {"nest": {
      "version": "1.0.0",                       the NEST release this workspace is level with
      "source": "https://github.com/...",       where releases come from (git URL or local path)
      "update_check": true,                     false silences the session-start line
      "files": {"scripts/wiki.py": {"kit": "kit/scripts/wiki.py", "kind": "copy", "sha256": "...",
                                    "version": "1.0.0"}},
      "declined": {"kit/skills/mail/SKILL.md": "<sha256>"}
  }}

`kind` is "copy" (the file is the kit file, byte for byte) or "adapted" (rewritten for this user).
`sha256` is the hash of the kit file the workspace file was made from, never of the user's file.
`version` is the release that kit file came from; `diff` starts there, so a file that was already
brought over is never compared from an older release again.

Commands:
  stamp     Write the stamp by comparing the workspace with a kit copy (default `_setup/nest`).
            Run by the setup after each build phase, and once for a workspace without a stamp.
            It only adds files that are not recorded yet; `--map` records one again.
  check     Is there a newer release? `--quiet` prints one line only when there is one, and looks
            online at most once per `--max-age-days` (default 7).
  plan      Fetch the installed and the newest release and say, per file, what changed:
              replace   changed in NEST, untouched here: safe to replace
              merge     changed in NEST, and adapted or edited here: needs a careful merge
              new       new in NEST
              removed   no longer part of NEST
              wiki      a wiki reference file changed (wiki files are never mapped one to one)
              reference an example or reference file without a fixed place here changed
              missing   changed in NEST, deleted here
            A `new` item carries `exists`: true means a file is already at that place, and it
            may be the user's own.
            `--json` for the skill; without it a short text overview.
  diff      The change NEST made to one kit file, as a unified diff.
  backup    Keep the current version of workspace files in this update's history folder. Always
            before a file is written; a file that does not exist yet is noted as new.
  apply     Replace `replace` files with the new kit file, bring back a deleted copy file, or add
            a new copy file with `--new KIT=PATH`. Refuses a file the user changed, and never
            overwrites a file.
  mark      After a merge or a new adapted file: record that PATH now reflects the new kit file.
            Refuses a file that was not backed up in this update.
  decline   Remember that the user does not want a change, so it is not offered again.
  done      The same record for a change that was dealt with by hand (a wiki file, a deleted file).
  retire    Take a file NEST dropped out of the workspace; its last version stays in the history.
  finish    Close the update: set the version when nothing is left open; `--skip` silences the
            session-start line for this release.
  restore   Put back what the last update changed. Files the user changed after the update
            finished are left alone unless `--force`; what it replaces is kept in `undone/`.
            `--list` shows the updates in the history, `--dry-run` what would be put back. An
            older update is only ever put back by name, with `--run`.

Backups go to `.claude/.history/nest-update-<time>/`; fetched releases to `.claude/.nest-update/`;
the check cache to `.claude/.nest-update.json`. All three are gitignored and local.

The workspace root is $CLAUDE_PROJECT_DIR, else the current directory. Needs `git` on the PATH.
Exit codes: 0 fine, 1 a problem (the message says what), 2 wrong usage.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

DEFAULT_SOURCE = "https://github.com/nickyjacobs/NEST.git"
STAMP_FILE = Path("nest.json")
CACHE_FILE = Path(".claude/.nest-update.json")
WORK_DIR = Path(".claude/.nest-update")
HISTORY_DIR = Path(".claude/.history")
KIT_COPY = Path("_setup/nest")
CHECK_TIMEOUT = 4.0
FETCH_TIMEOUT = 120.0
VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
SKIP_NAMES = {"README.md", ".gitkeep", "uv.lock", "pyproject.toml", ".DS_Store"}
SKIP_PARTS = {"tests", "__pycache__", ".venv", ".pytest_cache", ".ruff_cache"}
OPEN_STATUSES = ("replace", "merge", "new", "removed", "wiki", "reference", "missing")
RUN_HOURS = 12
RETRY_DAYS = 1.0  # after a check that could not reach the source, look again this soon
SIZE_FILES = ("SKILL.md", "SKILL.light.md", "formats.md", "formats.light.md")


class Problem(Exception):
    """Something the user or the skill has to know about; the message is the output."""


# --- small helpers -------------------------------------------------------------------------------

def workspace_root() -> Path:
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    return Path(env) if env and Path(env).is_dir() else Path.cwd()


def read_json(path: Path) -> dict:
    """A JSON object from a file, or {} when it is missing or unreadable. For caches and records."""
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def read_stamp_file(root: Path) -> dict:
    """nest.json as a dict; {} when there is none. A file that is there but broken is a Problem:
    treating it as empty would make the next write wipe every other setting in it."""
    path = root / STAMP_FILE
    try:
        text = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        return {}
    except (OSError, UnicodeError) as exc:
        raise Problem(f"{STAMP_FILE} could not be read ({exc.__class__.__name__}). Nothing was changed.") from exc
    try:
        data = json.loads(text)
    except ValueError as exc:
        where = f" (line {exc.lineno}, column {exc.colno})" if isinstance(exc, json.JSONDecodeError) else ""
        raise Problem(f"{STAMP_FILE} is not valid JSON{where}: {getattr(exc, 'msg', exc)}. Fix that spot (often a "
                      "missing or extra comma or quote) and run this again. Nothing was changed.") from exc
    if not isinstance(data, dict):
        raise Problem(f"{STAMP_FILE} does not hold a JSON object. Nothing was changed.")
    return data


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def sha(path: Path) -> str | None:
    """Hash of a file with line endings normalised, so a CRLF checkout equals an LF one."""
    try:
        return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    except OSError:
        return None


def parse_version(text: str) -> tuple[int, int, int] | None:
    m = VERSION_RE.match(str(text).strip())
    return (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def show(version: tuple[int, int, int]) -> str:
    return ".".join(str(n) for n in version)


def run_bounded(cmd: list[str], timeout: float, cwd: Path | None = None,
                env: dict | None = None) -> subprocess.CompletedProcess:
    """Run a command and be back within about `timeout` seconds, whatever its children do.

    `subprocess.run(timeout=...)` kills only the direct child and then waits for the pipes to
    close. A helper the child started (git's remote helper) can keep them open, which on Windows
    stretches the wait far past the timeout and elsewhere leaves that helper running. So the
    command gets its own process group, the whole group is stopped, and the pipes get one more
    second at most. Raises subprocess.TimeoutExpired like `subprocess.run`.
    """
    options: dict = {"start_new_session": True} if os.name != "nt" else \
        {"creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)}
    proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            encoding="utf-8", errors="replace", cwd=cwd, env=env, **options)
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            try:
                subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True, timeout=5, check=False)
            except (OSError, subprocess.SubprocessError):
                pass
        else:
            try:
                os.killpg(proc.pid, 9)
            except OSError:
                pass
        try:
            proc.kill()
        except OSError:
            pass
        try:
            proc.communicate(timeout=1)
        except (subprocess.TimeoutExpired, OSError, ValueError):
            for pipe in (proc.stdout, proc.stderr):
                try:
                    if pipe:
                        pipe.close()
                except OSError:
                    pass
        raise
    return subprocess.CompletedProcess(cmd, proc.returncode, out, err)


def git(*args: str, timeout: float, cwd: Path | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    return run_bounded(["git", *args], timeout, cwd=cwd, env=env)


def git_trouble(exc: BaseException) -> str:
    """Why a git call did not come back, in words a user can act on."""
    if isinstance(exc, FileNotFoundError):
        return "git was not found on this computer (NEST needs git to look for releases)"
    if isinstance(exc, subprocess.TimeoutExpired):
        return "no answer in time (no internet, or a slow connection)"
    return exc.__class__.__name__


def check_source(source: str) -> str:
    """The source as git may use it: never something git would read as an option."""
    source = str(source).strip()
    if not source or source.startswith("-"):
        raise Problem(f"`{source}` is not a usable NEST source. Set `nest.source` in nest.json to a git URL or a folder.")
    return source


def force_rmtree(path: Path) -> None:
    """Remove a folder, also when git left read-only files in it (Windows)."""
    def retry(func, target, _exc):
        try:
            os.chmod(target, 0o700)
            func(target)
        except OSError:
            pass
    shutil.rmtree(path, onerror=retry)


def no_symlink(root: Path, ws_rel: str) -> None:
    """Refuse a path that is, or goes through, a symbolic link: it could point outside the workspace."""
    here = root
    for part in ws_rel.split("/"):
        here = here / part
        if here.is_symlink():
            raise Problem(f"{ws_rel} is or goes through a symbolic link; NEST leaves it alone.")


def safe_rel(text: str) -> str:
    """A workspace-relative path with / separators; refuses anything that leaves the workspace."""
    rel = str(text).replace("\\", "/").strip()
    while rel.startswith("./"):
        rel = rel[2:]
    parts = rel.split("/")
    if not rel or rel.startswith("/") or re.match(r"^[A-Za-z]:", rel) or ".." in parts:
        raise Problem(f"Not a path inside the workspace: {text}")
    return rel


# --- the stamp -----------------------------------------------------------------------------------

def load_stamp(root: Path) -> dict:
    stamp = read_stamp_file(root).get("nest")
    stamp = stamp if isinstance(stamp, dict) else {}
    stamp.setdefault("files", {})
    stamp.setdefault("declined", {})
    return stamp


def save_stamp(root: Path, stamp: dict) -> None:
    data = read_stamp_file(root)
    stamp["files"] = dict(sorted(stamp.get("files", {}).items()))
    stamp["declined"] = dict(sorted(stamp.get("declined", {}).items()))
    data["nest"] = stamp
    write_json(root / STAMP_FILE, data)


def stamp_key(stamp: dict, ws_rel: str) -> str:
    """The recorded spelling of a path: on macOS and Windows `Scripts/x.py` is `scripts/x.py`."""
    if ws_rel in stamp["files"]:
        return ws_rel
    for key in stamp["files"]:
        if key.lower() == ws_rel.lower():
            return key
    return ws_rel


def need_stamp(root: Path) -> dict:
    stamp = load_stamp(root)
    if not parse_version(stamp.get("version", "")):
        raise Problem("This workspace has no NEST stamp yet. Run `nest_update.py stamp` first "
                      "(it needs the kit copy in _setup/nest, or `--version` with the release it was built from).")
    return stamp


def kit_files(kit_root: Path) -> dict[str, Path]:
    """Every kit file worth tracking: 'kit/...' (posix) -> the file."""
    base = kit_root / "kit"
    found = {}
    if base.is_dir():
        for path in sorted(base.rglob("*")):
            if path.is_symlink() or not path.is_file() or path.name in SKIP_NAMES:
                continue
            rel = path.relative_to(kit_root).as_posix()
            if SKIP_PARTS & set(rel.split("/")):
                continue
            found[rel] = path
    return found


def group_of(kit_rel: str) -> str:
    parts = kit_rel.split("/")
    if len(parts) >= 3 and parts[1] == "skills":
        return f"skill {parts[2]}"
    if len(parts) >= 2 and parts[1] == "agents":
        name = parts[-1]
        return "agents council" if name.startswith("council-") else "agents architects" if name.startswith("architect-") else "agents"
    if len(parts) >= 3 and parts[1] == "claude":
        return "rules" if parts[2] == "rules" else "settings"
    return parts[1] if len(parts) >= 2 else "kit"


def target_for(kit_rel: str, light: set[str]) -> str | None:
    """Where a kit file lands in a workspace by default, or None when there is no fixed place."""
    parts = kit_rel.split("/")[1:]
    if not parts:
        return None
    top, name = parts[0], parts[-1]
    if top == "scripts" and len(parts) == 2 and name.endswith(".py"):
        return f"scripts/{name}"
    if kit_rel == "kit/integrations/microsoft-graph/graph.py":
        return "scripts/graph.py"
    if kit_rel == "kit/integrations/tool-map.example.md":
        return "tool-map.md"
    if top == "github":
        if kit_rel == "kit/github/pre-commit":
            return ".githooks/pre-commit"
        if kit_rel == "kit/github/gitignore.template":
            return ".gitignore"
        if kit_rel == "kit/github/gitattributes.template":
            return ".gitattributes"
        if kit_rel == "kit/github/dependabot.yml":
            return ".github/dependabot.yml"
        if len(parts) == 3 and parts[1] == "workflows":
            return f".github/workflows/{name}"
        return None
    if top == "claude":
        if len(parts) == 3 and parts[1] == "rules":
            return f".claude/rules/{name}"
        if kit_rel == "kit/claude/settings.reference.json":
            return ".claude/settings.json"
        return None
    if top == "skills" and len(parts) >= 3:
        skill, rest = parts[1], parts[2:]
        if len(rest) == 1 and rest[0] in ("SKILL.light.md", "SKILL.md", "formats.md", "formats.light.md"):
            has_light = skill in ("idea", "blueprint")
            is_light = has_light and skill in light
            if rest[0] == "SKILL.light.md":
                return f".claude/skills/{skill}/SKILL.md" if is_light else None
            if rest[0] == "formats.light.md" and not is_light:
                return None
            if rest[0] in ("SKILL.md", "formats.md") and is_light:
                return None
        return f".claude/skills/{skill}/" + "/".join(rest)
    if top == "agents":
        if len(parts) == 2:
            return f".claude/agents/{name}"
        if len(parts) == 3 and parts[1] in ("full", "light"):
            team = "idea" if name.startswith("council-") else "blueprint"
            return f".claude/agents/{name}" if (parts[1] == "light") == (team in light) else None
    return None


def detect_light(root: Path) -> set[str]:
    return {skill for skill in ("idea", "blueprint") if (root / ".claude/skills" / skill / "formats.light.md").is_file()}


def kit_version(kit_root: Path) -> str | None:
    try:
        head = (kit_root / "SETUP.md").read_text(encoding="utf-8", errors="replace")[:2000]
    except OSError:
        return None
    m = re.search(r"^Version (\d+\.\d+\.\d+)", head, re.MULTILINE)
    return m.group(1) if m else None


def state_version(root: Path) -> str | None:
    try:
        head = (root / "_setup/STATE.md").read_text(encoding="utf-8", errors="replace")[:2000]
    except OSError:
        return None
    m = re.search(r"^nest_version:\s*['\"]?(\d+\.\d+\.\d+)", head, re.MULTILINE)
    return m.group(1) if m else None


def cmd_stamp(root: Path, args) -> int:
    kit_root = (root / args.kit_root) if not Path(args.kit_root).is_absolute() else Path(args.kit_root)
    files = kit_files(kit_root)
    stamp = load_stamp(root)
    version = args.version or stamp.get("version") or kit_version(kit_root) or state_version(root)
    if not version or not parse_version(version):
        raise Problem("Cannot tell which NEST release this workspace was built from: pass `--version X.Y.Z`.")
    source = check_source(args.source or stamp.get("source") or DEFAULT_SOURCE)
    if not files:
        # No kit copy on disk: use the release itself as the reference. Every file found in its
        # default place is then recorded as adapted unless it is byte for byte the kit file.
        try:
            fetched = fetch_release(root, source, parse_version(version))
        except Problem:
            fetched = None
        if fetched is not None:
            kit_root, files = fetched, kit_files(fetched)
        elif not stamp["files"]:
            raise Problem(f"There is no kit copy at {args.kit_root} and release {version} could not be fetched from "
                          f"{source}, so NEST cannot tell which files it installed here. Try again when online.")
    light = set(args.light or []) | detect_light(root)
    pairs: dict[str, str] = {}
    for kit_rel in files:
        target = target_for(kit_rel, light)
        if target and (root / target).is_file():
            pairs[target] = kit_rel
    for item in args.map or []:
        ws_rel, _, kit_rel = item.partition("=")
        ws_rel, kit_rel = safe_rel(ws_rel), kit_rel.strip().replace("\\", "/")
        if kit_rel not in files:
            raise Problem(f"--map {item}: {kit_rel} is not a file in the kit copy.")
        if not (root / ws_rel).is_file():
            raise Problem(f"--map {item}: {ws_rel} does not exist in the workspace.")
        pairs[stamp_key(stamp, ws_rel)] = kit_rel
    explicit = {stamp_key(stamp, safe_rel(item.partition("=")[0])) for item in args.map or []}
    made_from = kit_version(kit_root) or version  # the release the kit copy on disk really is
    copies = adapted = 0
    for ws_rel, kit_rel in pairs.items():
        if ws_rel in stamp["files"] and ws_rel not in explicit:
            continue  # already recorded: a later run must not reset it to an older kit copy
        kit_sha = sha(files[kit_rel])
        kind = "copy" if sha(root / ws_rel) == kit_sha else "adapted"
        stamp["files"][ws_rel] = {"kit": kit_rel, "kind": kind, "sha256": kit_sha, "version": made_from}
        copies += kind == "copy"
        adapted += kind == "adapted"
    stamp["version"] = version
    stamp["source"] = source
    stamp.setdefault("update_check", True)
    save_stamp(root, stamp)
    total = len(stamp["files"])
    print(f"Stamp written to {STAMP_FILE}: NEST {version}, {total} files recorded "
          f"({copies} unchanged kit files and {adapted} adapted files added now).")
    return 0


# --- looking for a newer release -----------------------------------------------------------------

def remote_versions(source: str, timeout: float) -> list[tuple[int, int, int]]:
    try:
        out = git("ls-remote", "--tags", "--refs", "--", check_source(source), timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        raise Problem(f"Could not reach {source}: {git_trouble(exc)}.") from exc
    if out.returncode != 0:
        raise Problem(f"Could not reach {source}: {out.stderr.strip().splitlines()[-1] if out.stderr.strip() else 'git failed'}")
    versions = []
    for line in out.stdout.splitlines():
        version = parse_version(line.rsplit("refs/tags/", 1)[-1]) if "refs/tags/" in line else None
        if version:
            versions.append(version)
    return sorted(set(versions))


def latest_version(root: Path, stamp: dict, max_age_days: float | None, timeout: float) -> tuple[int, int, int] | None:
    """The newest release tag. With `max_age_days` a recent answer comes from the cache."""
    cache = read_json(root / CACHE_FILE)
    now = time.time()
    if max_age_days is not None and isinstance(cache.get("checked"), (int, float)):
        # A check that failed (offline, a slow line) must not silence the notice for a whole week.
        window = min(max_age_days, RETRY_DAYS) if cache.get("failed") else max_age_days
        if now - cache["checked"] < window * 86400:
            return parse_version(cache.get("latest") or "")
    try:
        versions = remote_versions(str(stamp.get("source") or DEFAULT_SOURCE), timeout)
    except Problem:
        if max_age_days is None:
            raise
        versions = []
        latest = parse_version(cache.get("latest") or "")
        cache["failed"] = True
    else:
        latest = versions[-1] if versions else None
        cache.pop("failed", None)
    cache["checked"] = now
    if latest:
        cache["latest"] = show(latest)
    try:
        write_json(root / CACHE_FILE, cache)
    except OSError:
        pass
    return latest


def notice(root: Path, max_age_days: float = 7, timeout: float = CHECK_TIMEOUT) -> str:
    """One line when a newer release exists and the user did not skip it; else an empty string."""
    try:
        stamp = load_stamp(root)
    except Problem:
        return f"{STAMP_FILE} cannot be read (it is not valid JSON), so its settings and the NEST update check are off"
    installed = parse_version(stamp.get("version", ""))
    if not installed or stamp.get("update_check") is False:
        return ""
    latest = latest_version(root, stamp, max_age_days, timeout)
    if not latest or latest <= installed or show(latest) == stamp.get("skipped_version"):
        return ""
    return (f"NEST {show(latest)} is available (this workspace is on {show(installed)}); "
            "the nest-update skill shows what is new")


def cmd_check(root: Path, args) -> int:
    if args.quiet:
        try:
            line = notice(root, args.max_age_days)
        except Exception:
            line = ""
        if line:
            print(line)
        return 0
    stamp = need_stamp(root)
    installed = parse_version(stamp["version"])
    latest = latest_version(root, stamp, None, FETCH_TIMEOUT)
    if not latest:
        print(f"No release found at {stamp.get('source') or DEFAULT_SOURCE}. This workspace is on NEST {show(installed)}.")
    elif latest < installed:
        print(ahead_line(installed, latest))
    elif latest == installed:
        print(f"Up to date: this workspace is on NEST {show(installed)}, the newest release.")
    else:
        print(f"NEST {show(latest)} is available. This workspace is on {show(installed)}.")
    return 0


def ahead_line(installed: tuple[int, int, int], latest: tuple[int, int, int]) -> str:
    return (f"Up to date: this workspace is on NEST {show(installed)}, which is newer than the newest release "
            f"({show(latest)}). It was built from a version that is not released yet; there is nothing to bring over.")


# --- comparing releases --------------------------------------------------------------------------

def fetch_release(root: Path, source: str, version: tuple[int, int, int]) -> Path | None:
    """One release tag in the work folder, or None when the tag does not exist.

    Only `kit/` and `CHANGELOG.md` are kept, without symbolic links: nothing else of a release is
    needed, and files such as a CLAUDE.md must not sit where a session could load them.
    """
    dest = root / WORK_DIR / show(version)
    marker = f"{show(version)}\n{check_source(source)}\n"
    try:
        if (dest / ".fetched").read_text(encoding="utf-8") == marker:
            return dest
    except OSError:
        pass
    if dest.exists():
        force_rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        out = git("-c", "core.autocrlf=false", "-c", "core.symlinks=false", "-c", "advice.detachedHead=false", "clone",
                  "--quiet", "--depth", "1", "--branch", f"v{show(version)}", "--", check_source(source), str(dest),
                  timeout=FETCH_TIMEOUT)
    except (OSError, subprocess.SubprocessError) as exc:
        raise Problem(f"Could not fetch NEST {show(version)} from {source}: {git_trouble(exc)}.") from exc
    if out.returncode != 0:
        if dest.exists():
            force_rmtree(dest)
        return None
    # With core.symlinks=false a link in the release arrives as a small text file holding its target.
    # Such an entry is no kit file: drop it, so nothing a link points at can ever be offered.
    try:
        listing = git("ls-files", "-s", "-z", timeout=FETCH_TIMEOUT, cwd=dest).stdout
    except (OSError, subprocess.SubprocessError):
        listing = ""
    for entry in listing.split("\0"):
        meta, _, name = entry.partition("\t")
        if meta.startswith("120000") and name:
            try:
                (dest / name).unlink()
            except OSError:
                pass
    for child in list(dest.iterdir()):
        if child.name in ("kit", "CHANGELOG.md") and not child.is_symlink():
            continue
        if child.is_dir() and not child.is_symlink():
            force_rmtree(child)
        else:
            child.unlink()
    for path in sorted(dest.rglob("*"), reverse=True):
        if not os.path.lexists(path):
            continue  # went with a folder that was removed just before
        if path.is_dir() and not path.is_symlink():
            if path.name in (".claude", "CLAUDE.md", "CLAUDE.local.md"):
                force_rmtree(path)
        elif path.is_symlink() or path.name in ("CLAUDE.md", "CLAUDE.local.md"):
            path.unlink()
    (dest / ".fetched").write_text(marker, encoding="utf-8")
    return dest


def release_notes(changelog: Path, installed: tuple[int, int, int], latest: tuple[int, int, int]) -> list[dict]:
    """The changelog sections newer than `installed`, newest first."""
    try:
        text = changelog.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    notes = []
    sections = re.split(r"(?m)^## \[", text)[1:]
    for section in sections:
        head, _, body = section.partition("\n")
        m = re.match(r"(\d+\.\d+\.\d+)\]\s*(?:-\s*(\S+))?", head)
        version = parse_version(m.group(1)) if m else None
        if not version or not installed < version <= latest:
            continue
        body = re.split(r"(?m)^\[[^\]]+\]:\s", body)[0]
        body = re.sub(r"(?m)^---\s*$", "", body).strip()
        short = re.search(r"(?m)^(?:>\s*)?\*\*In short:?\*\*:?\s*(.+)$", body)
        yours = re.search(r"(?ms)^### (?:\S+ )?For your workspace\s*\n(.*?)(?=^### |\Z)", body)
        notes.append({"version": m.group(1), "date": m.group(2) or "", "in_short": short.group(1).strip() if short else "",
                      "for_your_workspace": yours.group(1).strip() if yours else "", "body": body})
    return sorted(notes, key=lambda n: parse_version(n["version"]), reverse=True)


def build_plan(root: Path, stamp: dict, latest: tuple[int, int, int]) -> dict:
    installed = parse_version(stamp["version"])
    source = str(stamp.get("source") or DEFAULT_SOURCE)
    latest_dir = fetch_release(root, source, latest)
    if latest_dir is None:
        raise Problem(f"Could not fetch NEST {show(latest)} from {source}.")
    base_dir = fetch_release(root, source, installed)
    base_note = ""
    if base_dir is None:
        if (root / KIT_COPY / "kit").is_dir():
            base_dir, base_note = root / KIT_COPY, f"Release {show(installed)} has no tag; compared with the kit copy in {KIT_COPY.as_posix()}."
        else:
            base_note = (f"Release {show(installed)} has no tag and there is no kit copy: new files are only "
                         "reported inside parts this workspace already has.")
    new_files = kit_files(latest_dir)
    base_files = kit_files(base_dir) if base_dir else {}
    declined = stamp.get("declined", {})
    light = detect_light(root)
    items = []

    def add(status: str, kit_rel: str, path: str | None, kind: str | None) -> None:
        latest_sha = sha(new_files[kit_rel]) if kit_rel in new_files else None
        if status in OPEN_STATUSES and declined.get(kit_rel) == (latest_sha or "removed"):
            status = "declined"
        item = {"status": status, "kit": kit_rel, "path": path, "kind": kind, "group": group_of(kit_rel)}
        if status == "new":
            item["exists"] = bool(path) and os.path.lexists(root / path)
        items.append(item)

    mapped = set()
    for ws_rel, entry in sorted(stamp["files"].items()):
        kit_rel, kind, recorded = entry.get("kit", ""), entry.get("kind", "adapted"), entry.get("sha256")
        mapped.add(kit_rel)
        if kit_rel not in new_files:
            add("removed" if os.path.lexists(root / ws_rel) else "gone", kit_rel, ws_rel, kind)
        elif sha(new_files[kit_rel]) == recorded:
            add("unchanged", kit_rel, ws_rel, kind)
        elif not (root / ws_rel).is_file():
            add("missing", kit_rel, ws_rel, kind)
        elif sha(root / ws_rel) in (sha(new_files[kit_rel]), recorded if kind == "copy" else None):
            # Untouched, or already the new kit file (an update that stopped before it was recorded).
            add("replace", kit_rel, ws_rel, kind)
        else:
            add("merge", kit_rel, ws_rel, kind)

    have_groups = {group_of(kit_rel) for kit_rel in mapped} | {"scripts"}
    base_groups = {group_of(kit_rel) for kit_rel in base_files}
    has_wiki = (root / "wiki.config.json").is_file() or (root / "wiki").is_dir()
    for kit_rel in sorted(set(new_files) - mapped):
        group = group_of(kit_rel)
        if group == "wiki":
            if has_wiki and base_dir and sha(new_files[kit_rel]) != (sha(base_files[kit_rel]) if kit_rel in base_files else None):
                add("wiki", kit_rel, None, None)
            continue
        target = target_for(kit_rel, light)
        parts = kit_rel.split("/")
        other_size = target is None and ((parts[1] == "agents" and len(parts) == 4)
                                         or (parts[1] == "skills" and parts[-1] in SIZE_FILES))
        if other_size:
            continue  # the full file of a team this workspace has in light, or the other way round
        if target is None and kit_rel in base_files:
            # An example or reference file with no fixed place here (the setup made something of
            # its own from it): say that it changed, for the parts this workspace has.
            if group in have_groups and sha(new_files[kit_rel]) != sha(base_files[kit_rel]):
                add("reference", kit_rel, None, None)
            continue
        if kit_rel in declined and declined[kit_rel] != sha(new_files[kit_rel]):
            add("new", kit_rel, target, "copy" if group == "scripts" else "adapted")  # declined before, changed since
            continue
        if kit_rel in base_files or (base_dir is None and group not in have_groups):
            continue
        if group in have_groups or (base_dir is not None and group not in base_groups):
            add("new", kit_rel, target, "copy" if group == "scripts" else "adapted")

    return {"installed": show(installed), "latest": show(latest), "source": source,
            "base_dir": base_dir.as_posix() if base_dir else None, "latest_dir": latest_dir.as_posix(),
            "note": base_note, "notes": release_notes(latest_dir / "CHANGELOG.md", installed, latest), "items": items}


def open_items(plan: dict) -> list[dict]:
    return [item for item in plan["items"] if item["status"] in OPEN_STATUSES]


def current_plan(root: Path, stamp: dict, fresh: bool = False, latest: tuple[int, int, int] | None = None) -> dict:
    """The plan against the release this update was started for; `fresh` looks for a newer one
    (or takes `latest` when the caller looked already)."""
    installed = parse_version(stamp["version"])
    cache = read_json(root / CACHE_FILE)
    if latest is None and not fresh:
        latest = parse_version(cache.get("planned") or "")
    if latest is None:
        latest = latest_version(root, stamp, None, FETCH_TIMEOUT)
    if not latest:
        raise Problem(f"No release found at {stamp.get('source') or DEFAULT_SOURCE}, so there is nothing to compare "
                      f"with. This workspace is on NEST {show(installed)}.")
    if latest < installed:
        latest = installed
    return build_plan(root, stamp, latest)


def run_started(name: str) -> float | None:
    try:
        return datetime.strptime(name.removeprefix("nest-update-").split(".")[0], "%Y%m%d-%H%M%S").timestamp()
    except ValueError:
        return None


def current_run(root: Path, begin: bool = False) -> str:
    """The history folder name of the update in progress.

    `begin` (the `plan` command) starts a new one when the last one changed nothing or is older
    than RUN_HOURS: an update someone walked away from must not swallow a later one.
    """
    cache = read_json(root / CACHE_FILE)
    run = cache.get("run") if isinstance(cache.get("run"), str) else None
    if run and begin:
        started = run_started(run)
        if not (root / HISTORY_DIR / run).is_dir():
            run = None
        elif started is None or time.time() - started > RUN_HOURS * 3600:
            end_run(root)
            cache, run = read_json(root / CACHE_FILE), None
    if not run:
        run = "nest-update-" + datetime.now().strftime("%Y%m%d-%H%M%S")
        n = 2
        while (root / HISTORY_DIR / run).exists():
            run = f"{run.rsplit('.', 1)[0]}.{n}"
            n += 1
        cache["run"] = run
        write_json(root / CACHE_FILE, cache)
    return run


def run_paths(folder: Path) -> tuple[list[str], list[str]]:
    """What a run touched: the files it kept an earlier version of, and the files it added."""
    files = folder / "files"
    kept = sorted(p.relative_to(files).as_posix() for p in files.rglob("*") if p.is_file()) if files.is_dir() else []
    created = folder / "created.txt"
    made = [line for line in created.read_text(encoding="utf-8").splitlines() if line.strip()] if created.is_file() else []
    return kept, made


def end_run(root: Path) -> None:
    """Close the update: remember what every touched file looks like now, so a later `restore`
    can tell the update's own work from changes the user made afterwards."""
    cache = read_json(root / CACHE_FILE)
    run = cache.pop("run", None)
    cache.pop("planned", None)
    if isinstance(run, str):
        folder = root / HISTORY_DIR / run
        if folder.is_dir() and not (folder / "written.json").is_file():
            kept, made = run_paths(folder)
            write_json(folder / "written.json", {rel: sha(root / rel) for rel in [*kept, *made]})
    write_json(root / CACHE_FILE, cache)


def cmd_plan(root: Path, args) -> int:
    stamp = need_stamp(root)
    installed = parse_version(stamp["version"])
    newest = latest_version(root, stamp, None, FETCH_TIMEOUT)
    if newest and newest < installed:
        # Built from a version that has no release yet: nothing to compare, and nothing to fetch.
        line = ahead_line(installed, newest)
        if args.json:
            print(json.dumps({"installed": show(installed), "latest": show(newest), "source": stamp.get("source"),
                              "items": [], "notes": [], "note": line, "ahead": True, "up_to_date": True}, indent=2))
        else:
            print(line)
        return 0
    plan = current_plan(root, stamp, fresh=True, latest=newest)
    plan["run"] = current_run(root, begin=True)
    cache = read_json(root / CACHE_FILE)
    cache["planned"] = plan["latest"]
    write_json(root / CACHE_FILE, cache)
    todo = open_items(plan)
    plan["up_to_date"] = plan["installed"] == plan["latest"] and not todo
    if args.json:
        print(json.dumps(plan, indent=2, ensure_ascii=False))
        return 0
    if plan["up_to_date"]:
        print(f"Up to date: this workspace is on NEST {plan['installed']}, the newest release.")
        return 0
    print(f"NEST {plan['latest']} is available. This workspace is on {plan['installed']}.")
    if plan["note"]:
        print(plan["note"])
    for note in plan["notes"]:
        print(f"\n{note['version']}: {note['in_short'] or '(no summary)'}")
    labels = {"replace": "safe to replace", "merge": "needs a merge", "new": "new", "removed": "no longer in NEST",
              "wiki": "wiki reference changed", "reference": "example or reference file changed",
              "missing": "changed in NEST, deleted here"}
    for status in OPEN_STATUSES:
        rows = [item for item in todo if item["status"] == status]
        if rows:
            print(f"\n{labels[status]} ({len(rows)}):")
            for item in rows:
                print(f"  {item['path'] or item['kit']}  [{item['group']}]")
    return 0


def diff_base(root: Path, stamp: dict, plan: dict, kit_rel: str) -> tuple[str | None, str, str]:
    """Where the diff of one kit file starts: (folder, version label, warning).

    Normally the installed release. A file that was already brought over while other parts stayed
    open is level with a newer release than the stamp's version; comparing it from the old one
    would show changes that are in the user's file already, and a merge would add them twice.
    """
    base_dir, label = plan["base_dir"], plan["installed"]
    entries = [entry for entry in stamp["files"].values() if entry.get("kit") == kit_rel]
    if not entries:
        return base_dir, label, ""
    recorded = entries[0].get("sha256")
    if base_dir and sha(Path(base_dir) / kit_rel) == recorded:
        return base_dir, label, ""
    made_from = parse_version(entries[0].get("version") or "")
    candidates = [made_from] if made_from else []
    if not candidates:  # a stamp from before `version` was recorded: look through the releases in between
        try:
            between = remote_versions(plan["source"], FETCH_TIMEOUT)
        except Problem:
            between = []
        low, high = parse_version(plan["installed"]), parse_version(plan["latest"])
        candidates = [v for v in between if low < v < high]
    for version in candidates:
        try:
            folder = fetch_release(root, plan["source"], version)
        except Problem:
            folder = None
        if folder and sha(folder / kit_rel) == recorded:
            return folder.as_posix(), show(version), ""
    return base_dir, label, (f"Note: the file in this workspace was made from a later version of {kit_rel} than "
                             f"NEST {label}, and that version could not be fetched. Part of this diff may be in "
                             "the user's file already: compare before you merge.\n")


def cmd_diff(root: Path, args) -> int:
    stamp = need_stamp(root)
    plan = current_plan(root, stamp)
    kit_rel = args.kit.replace("\\", "/")
    base_dir, label, warning = diff_base(root, stamp, plan, kit_rel)
    if base_dir is None:
        print(f"There is no copy of release {plan['installed']} to compare with; read the new file instead: "
              f"{plan['latest_dir']}/{kit_rel}")
        return 0

    def lines(folder: str) -> list[str]:
        try:
            return (Path(folder) / kit_rel).read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        except OSError:
            return []

    old, new = lines(base_dir), lines(plan["latest_dir"])
    if not old and not new:
        raise Problem(f"{kit_rel} is in neither release.")
    out = "".join(difflib.unified_diff(old, new, f"NEST {label}/{kit_rel}", f"NEST {plan['latest']}/{kit_rel}"))
    sys.stdout.buffer.write((warning + (out or "No difference.\n")).encode("utf-8"))
    return 0


# --- changing the workspace ----------------------------------------------------------------------

def run_dir(root: Path) -> Path:
    folder = root / HISTORY_DIR / current_run(root)
    if not (folder / "nest.json").is_file() and not (folder / "no-stamp").is_file():
        folder.mkdir(parents=True, exist_ok=True)
        if (root / STAMP_FILE).is_file():
            shutil.copy2(root / STAMP_FILE, folder / "nest.json")
        else:
            (folder / "no-stamp").write_text("", encoding="utf-8")
    return folder


def backup(root: Path, ws_rel: str) -> str:
    """Keep the first version of a file this update touches. Returns what happened:
    "kept", "already" (an earlier version of this update is kept) or "new" (it does not exist yet)."""
    no_symlink(root, ws_rel)
    target = root / ws_rel
    if target.is_dir():
        raise Problem(f"{ws_rel} is a folder: back up the files in it one by one.")
    folder = run_dir(root)
    kept = folder / "files" / ws_rel
    _, made = run_paths(folder)
    if kept.exists() or ws_rel in made:
        return "already"
    if target.is_file():
        kept.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, kept)
        return "kept"
    (folder / "created.txt").write_text("\n".join([*made, ws_rel]) + "\n", encoding="utf-8")
    return "new"


def backed_up(root: Path, ws_rel: str) -> bool:
    folder = root / HISTORY_DIR / current_run(root)
    kept, made = run_paths(folder)
    return ws_rel.lower() in {rel.lower() for rel in [*kept, *made]}


def cmd_backup(root: Path, args) -> int:
    results = {"kept": [], "already": [], "new": []}
    stamp = load_stamp(root)
    for item in args.paths:
        ws_rel = stamp_key(stamp, safe_rel(item))
        results[backup(root, ws_rel)].append(ws_rel)
    where = run_dir(root).relative_to(root).as_posix()
    if results["kept"]:
        print(f"Kept the current version of {len(results['kept'])} file(s) in {where}/files/: {', '.join(results['kept'])}")
    if results["already"]:
        print(f"Already kept earlier in this update (the first version stays): {', '.join(results['already'])}")
    if results["new"]:
        print(f"Does not exist yet, noted as new so an undo takes it away again: {', '.join(results['new'])}")
    return 0


def split_pair(item: str) -> tuple[str, str]:
    left, sep, right = item.partition("=")
    if not sep or not left.strip() or not right.strip():
        raise Problem(f"Expected KIT=PATH or PATH=KIT, got: {item}")
    return left.strip().replace("\\", "/"), right.strip().replace("\\", "/")


def copy_exec_bit(kit_file: Path, target: Path) -> None:
    """A kit file that is executable (the pre-commit hook) stays so; git skips a hook that is not."""
    if os.name == "nt":
        return
    try:
        if kit_file.stat().st_mode & 0o111:
            target.chmod(target.stat().st_mode | 0o755)
    except OSError:
        pass


def cmd_apply(root: Path, args) -> int:
    stamp = need_stamp(root)
    plan = current_plan(root, stamp)
    new_files = kit_files(Path(plan["latest_dir"]))
    by_path = {item["path"]: item for item in plan["items"] if item["path"]}
    jobs: list[tuple[str, str]] = []
    for item in args.paths:
        ws_rel = stamp_key(stamp, safe_rel(item))
        no_symlink(root, ws_rel)
        found = by_path.get(ws_rel)
        if not found or ws_rel not in stamp["files"]:
            raise Problem(f"{ws_rel} is not a file NEST installed here.")
        if found["status"] == "unchanged":
            continue
        entry = stamp["files"][ws_rel]
        if not os.path.lexists(root / ws_rel):
            if entry.get("kind") != "copy":
                raise Problem(f"{ws_rel} was deleted in this workspace and was adapted for it, so there is no file to "
                              f"copy. To bring it back: `backup {ws_rel}`, write it again from {found['kit']} the way "
                              f"the setup would, then `mark {ws_rel}={found['kit']}`. To leave it out: `done {found['kit']}`.")
        elif sha(root / ws_rel) == sha(new_files.get(found["kit"], Path())):
            pass  # already the new kit file: only the record is behind
        elif found["status"] not in ("replace", "declined") or entry.get("kind") != "copy" \
                or sha(root / ws_rel) != entry.get("sha256"):
            raise Problem(f"{ws_rel} was changed in this workspace or was adapted for it: it needs a merge, not a replace.")
        jobs.append((ws_rel, found["kit"]))
    for item in args.new or []:
        kit_rel, ws_raw = split_pair(item)
        ws_rel = safe_rel(ws_raw)
        no_symlink(root, ws_rel)
        if kit_rel not in new_files:
            raise Problem(f"{kit_rel} is not a file in NEST {plan['latest']}.")
        if os.path.lexists(root / ws_rel):
            raise Problem(f"{ws_rel} already exists here; NEST will not overwrite it. It may be the user's own: "
                          "show both, merge only after a yes (`backup` first), then `mark`.")
        jobs.append((ws_rel, kit_rel))
    done = 0
    try:
        for ws_rel, kit_rel in jobs:
            backup(root, ws_rel)
            (root / ws_rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(new_files[kit_rel], root / ws_rel)
            copy_exec_bit(new_files[kit_rel], root / ws_rel)
            stamp["files"][ws_rel] = {"kit": kit_rel, "kind": "copy", "sha256": sha(new_files[kit_rel]),
                                      "version": plan["latest"]}
            stamp["declined"].pop(kit_rel, None)
            done += 1
            print(f"Updated {ws_rel}")
    except OSError as exc:
        raise Problem(f"Stopped at {jobs[done][0]}: {exc.strerror or exc}. {done} file(s) before it were updated "
                      "and recorded; nothing else was changed.") from exc
    finally:
        if done:
            save_stamp(root, stamp)
    if not jobs:
        print("Nothing to replace.")
    return 0


def cmd_mark(root: Path, args) -> int:
    stamp = need_stamp(root)
    plan = current_plan(root, stamp)
    new_files = kit_files(Path(plan["latest_dir"]))
    for item in args.pairs:
        ws_raw, kit_rel = split_pair(item)
        ws_rel = stamp_key(stamp, safe_rel(ws_raw))
        no_symlink(root, ws_rel)
        if kit_rel not in new_files:
            raise Problem(f"{kit_rel} is not a file in NEST {plan['latest']}.")
        if not (root / ws_rel).is_file():
            raise Problem(f"{ws_rel} does not exist in the workspace.")
        if not backed_up(root, ws_rel):
            raise Problem(f"{ws_rel} was not backed up in this update. Run `backup {ws_rel}` before writing a file, "
                          "so an undo knows what was there; then `mark` it.")
        kit_sha = sha(new_files[kit_rel])
        kind = args.kind or ("copy" if sha(root / ws_rel) == kit_sha else "adapted")
        stamp["files"][ws_rel] = {"kit": kit_rel, "kind": kind, "sha256": kit_sha, "version": plan["latest"]}
        stamp["declined"].pop(kit_rel, None)
        print(f"Recorded {ws_rel} as level with NEST {plan['latest']} ({kind}).")
    save_stamp(root, stamp)
    return 0


def cmd_decline(root: Path, args) -> int:
    stamp = need_stamp(root)
    plan = current_plan(root, stamp)
    new_files = kit_files(Path(plan["latest_dir"]))
    todo = open_items(plan)
    count = 0
    for raw in args.kits:
        wanted = raw.replace("\\", "/").rstrip("/")
        hits = [item for item in todo if item["kit"] == wanted or item["kit"].startswith(wanted + "/") or item["path"] == wanted]
        if not hits:
            raise Problem(f"Nothing open matches {raw}.")
        for item in hits:
            stamp["declined"][item["kit"]] = sha(new_files[item["kit"]]) if item["kit"] in new_files else "removed"
            count += 1
    run_dir(root)  # keeps the stamp as it was, so an undo of this update puts these choices back too
    save_stamp(root, stamp)
    if args.command == "done":
        print(f"Noted: {count} change(s) are dealt with.")
    else:
        print(f"Noted: {count} change(s) will not be offered again unless NEST changes them once more.")
    return 0


def cmd_retire(root: Path, args) -> int:
    """Take a file NEST dropped out of the workspace; its last version stays in the history folder."""
    stamp = need_stamp(root)
    plan = current_plan(root, stamp)
    removed = {item["path"] for item in plan["items"] if item["status"] in ("removed", "declined") and item["path"]
               and item["kit"] not in kit_files(Path(plan["latest_dir"]))}
    for item in args.paths:
        ws_rel = stamp_key(stamp, safe_rel(item))
        no_symlink(root, ws_rel)
        if ws_rel not in removed:
            raise Problem(f"{ws_rel} is not a file NEST dropped; nothing was moved.")
        backup(root, ws_rel)
        folder = run_dir(root)
        if not (folder / "files" / ws_rel).is_file():
            raise Problem(f"{ws_rel} could not be kept in the history folder, so it stays where it is.")
        (root / ws_rel).unlink()
        kit_rel = stamp["files"].pop(ws_rel, {}).get("kit")
        stamp["declined"].pop(kit_rel, None)
        print(f"Moved {ws_rel} out; its last version is in {folder.relative_to(root).as_posix()}/files/")
    save_stamp(root, stamp)
    return 0


def cmd_finish(root: Path, args) -> int:
    stamp = need_stamp(root)
    plan = current_plan(root, stamp)
    todo = open_items(plan)
    if args.skip:
        run_dir(root)
        end_run(root)
        stamp["skipped_version"] = plan["latest"]
        save_stamp(root, stamp)
        print(f"NEST {plan['latest']} will not be mentioned at session start again. `nest-update` still shows it.")
        return 0
    if not stamp["files"]:
        raise Problem("The stamp records no files, so NEST cannot know whether this workspace is level with a "
                      "release. Run `stamp` again (online, or with the kit copy in _setup/nest) before finishing.")
    if not todo and plan["installed"] != plan["latest"]:
        run_dir(root)  # the version is about to change: an undo must be able to put it back
    end_run(root)
    if todo:
        print(f"{len(todo)} change(s) are still open, so the workspace stays on NEST {plan['installed']}:")
        for item in todo:
            print(f"  {item['status']}: {item['path'] or item['kit']}")
        return 0
    for item in plan["items"]:
        if item["status"] == "gone":
            stamp["files"].pop(item["path"], None)
    stamp["version"] = plan["latest"]
    stamp.pop("skipped_version", None)
    save_stamp(root, stamp)
    print(f"This workspace is now on NEST {plan['latest']}.")
    return 0


def history_runs(root: Path) -> list[Path]:
    """The update folders in the history, oldest first."""
    history = root / HISTORY_DIR
    if not history.is_dir():
        return []
    return sorted((p for p in history.glob("nest-update-*") if p.is_dir()), key=lambda p: (run_started(p.name) or 0, p.name))


def describe_run(root: Path, folder: Path) -> str:
    kept, made = run_paths(folder)
    before = read_json(folder / "nest.json").get("nest")
    was_on = before.get("version") if isinstance(before, dict) else None
    started = run_started(folder.name)
    when = datetime.fromtimestamp(started).strftime("%Y-%m-%d %H:%M") if started else "unknown time"
    if (folder / "restored").is_file():
        left = read_json(folder / "left.json").get("left") or []
        state = "put back" + (f", {len(left)} file(s) left alone" if left else "")
    elif read_json(root / CACHE_FILE).get("run") == folder.name:
        state = "in progress"
    else:
        state = "finished"
    return (f"{folder.name}  {when}  {state}; the workspace was on NEST {was_on or '?'} before it; "
            f"{len(kept)} file(s) changed, {len(made)} added")


def prune_empty(root: Path, folder: Path) -> None:
    """Remove folders an undo left empty, never the workspace root or anything outside it."""
    while folder != root and root in folder.parents:
        try:
            folder.rmdir()
        except OSError:
            return
        folder = folder.parent


def cmd_restore(root: Path, args) -> int:
    runs = history_runs(root)
    if args.list:
        if not runs:
            print("There is no update in the history.")
        for folder in reversed(runs):
            print(describe_run(root, folder))
        return 0
    if args.run:
        runs = [p for p in runs if p.name == args.run]
        if not runs:
            raise Problem(f"There is no update named {args.run}. `restore --list` shows the ones there are.")
    if not runs:
        raise Problem("There is no update to put back.")
    # Always the newest update, never silently an older one: putting back an update that was
    # followed by another would also undo choices and edits made since.
    folder = runs[-1]
    only: list[str] | None = None
    if (folder / "restored").is_file():
        left_before = [rel for rel in read_json(folder / "left.json").get("left") or [] if isinstance(rel, str)]
        if args.force and left_before:
            only = left_before  # the files a first `restore` left alone, and nothing else
        else:
            older = "" if args.run or len(runs) < 2 else \
                " An older update is only put back by name: `restore --list` shows them, `restore --run <name>` picks one."
            raise Problem(f"{folder.name} was already put back.{older}")
    cache = read_json(root / CACHE_FILE)
    in_progress = cache.get("run") == folder.name
    # An update in progress: everything in it is the update's own work.
    written = None if in_progress or not (folder / "written.json").is_file() else read_json(folder / "written.json")
    kept, made = run_paths(folder)
    if only is not None:
        kept, made = [rel for rel in kept if rel in only], [rel for rel in made if rel in only]

    def changed_since(ws_rel: str) -> bool:
        """Did the user change this file after the update finished?"""
        return written is not None and not args.force and ws_rel in written and sha(root / ws_rel) != written[ws_rel]

    if args.dry_run:
        print(describe_run(root, folder))
        back = [rel for rel in kept if not changed_since(rel)]
        away = [rel for rel in made if (root / rel).is_file() and not changed_since(rel)]
        stay = [rel for rel in [*kept, *made] if changed_since(rel)]
        print(f"Would put back {len(back)} file(s): {', '.join(back) or 'none'}")
        print(f"Would take away {len(away)} file(s) the update added: {', '.join(away) or 'none'}")
        if stay:
            print(f"Would leave alone, because they were changed after the update finished: {', '.join(stay)}")
        print("Nothing was changed.")
        return 0

    if in_progress:
        cache.pop("run", None)
        cache.pop("planned", None)
        write_json(root / CACHE_FILE, cache)

    def keep_current(ws_rel: str) -> None:
        """Today's version goes to `undone/` once: a second try must not overwrite it with a file
        that was put back in the first."""
        aside = folder / "undone" / ws_rel
        if (root / ws_rel).is_file() and not aside.exists():
            aside.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / ws_rel, aside)

    def put_back(ws_rel: str) -> None:
        target = root / ws_rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_file() and not os.access(target, os.W_OK):
            target.chmod(target.stat().st_mode | 0o200)
        shutil.copy2(folder / "files" / ws_rel, target)

    restored, moved, left, failed = [], [], [], []
    for ws_rel in kept:
        no_symlink(root, ws_rel)
        if changed_since(ws_rel):
            left.append(ws_rel)
            continue
        try:
            keep_current(ws_rel)
            put_back(ws_rel)
            restored.append(ws_rel)
        except OSError as exc:
            failed.append(f"{ws_rel} ({exc.strerror or exc})")
    for ws_rel in made:
        if not (root / ws_rel).is_file() or (root / ws_rel).is_symlink():
            continue
        if changed_since(ws_rel):
            left.append(ws_rel)
            continue
        target = folder / "created" / ws_rel
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                target = target.with_name(f"{target.name}.{int(time.time())}")
            shutil.move(str(root / ws_rel), str(target))
            prune_empty(root, (root / ws_rel).parent)
            moved.append(ws_rel)
        except OSError as exc:
            failed.append(f"{ws_rel} ({exc.strerror or exc})")
    failed_paths = {item.rsplit(" (", 1)[0] for item in failed}
    before = read_json(folder / "nest.json").get("nest") if (folder / "nest.json").is_file() else None
    if isinstance(before, dict):
        now = load_stamp(root)
        stamp = dict(now)  # settings such as source and update_check stay as they are today
        if only is None:
            for key in ("version", "files", "declined", "skipped_version"):
                if key in before:
                    stamp[key] = before[key]
                else:
                    stamp.pop(key, None)
            stamp["files"] = dict(before.get("files") or {})
            for ws_rel in [*left, *failed_paths]:  # a file that was not put back keeps today's record
                if ws_rel in now["files"]:
                    stamp["files"][ws_rel] = now["files"][ws_rel]
            stamp["declined"] = dict(before.get("declined") or {})
        else:  # the second pass: only the records of the files that are put back now
            stamp["files"] = dict(now["files"])
            for ws_rel in [*restored, *moved]:
                if ws_rel in (before.get("files") or {}):
                    stamp["files"][ws_rel] = before["files"][ws_rel]
                else:
                    stamp["files"].pop(ws_rel, None)
        save_stamp(root, stamp)
    where = folder.relative_to(root).as_posix()
    print(f"Put back {len(restored)} file(s) from {where}; {len(moved)} file(s) the update had added were moved "
          f"into that folder. The versions that were replaced just now are in {where}/undone/.")
    if failed:
        # No marker: the same command can be run again once the cause is gone, and it picks up here.
        raise Problem(f"Could not put back: {', '.join(failed)}. Everything else was put back. Close the program "
                      "that has the file open (or make it writable) and run `restore` again.")
    write_json(folder / "left.json", {"left": left})
    (folder / "restored").write_text(datetime.now().isoformat(timespec="seconds") + "\n", encoding="utf-8")
    if left:
        print(f"Left alone, because they were changed after the update finished: {', '.join(left)}. "
              "`restore --force` puts those back too (today's versions are kept in the history folder first).")
    return 0


# --- command line --------------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Bring a workspace in step with a newer NEST release.")
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("stamp", help="Write or refresh the stamp in nest.json")
    p.add_argument("--kit-root", default=KIT_COPY.as_posix(), help="Folder holding kit/ and SETUP.md (default _setup/nest)")
    p.add_argument("--version", help="The NEST release the workspace was built from")
    p.add_argument("--source", help="Git URL or path releases come from")
    p.add_argument("--map", action="append", metavar="PATH=KIT", help="A workspace file made from a kit file under another name")
    p.add_argument("--light", action="append", metavar="SKILL", help="idea or blueprint was built in its light size")

    p = sub.add_parser("check", help="Is there a newer release?")
    p.add_argument("--quiet", action="store_true", help="One line, only when there is a newer release; never fails")
    p.add_argument("--max-age-days", type=float, default=7, help="With --quiet: look online at most this often")

    p = sub.add_parser("plan", help="What changed between the installed and the newest release")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("diff", help="The change NEST made to one kit file")
    p.add_argument("kit", metavar="KIT")

    p = sub.add_parser("backup", help="Keep the current version of workspace files before editing them")
    p.add_argument("paths", nargs="+", metavar="PATH")

    p = sub.add_parser("apply", help="Replace unchanged kit copies; add new copy files with --new")
    p.add_argument("paths", nargs="*", metavar="PATH")
    p.add_argument("--new", action="append", metavar="KIT=PATH")

    p = sub.add_parser("mark", help="Record that a merged or new adapted file reflects the new kit file")
    p.add_argument("pairs", nargs="+", metavar="PATH=KIT")
    p.add_argument("--kind", choices=("copy", "adapted"))

    p = sub.add_parser("decline", help="Do not offer these changes again")
    p.add_argument("kits", nargs="+", metavar="KIT")

    p = sub.add_parser("done", help="A change that was dealt with by hand (a wiki file, a deleted file)")
    p.add_argument("kits", nargs="+", metavar="KIT")

    p = sub.add_parser("retire", help="Take a file NEST dropped out of the workspace, keeping its last version")
    p.add_argument("paths", nargs="+", metavar="PATH")

    p = sub.add_parser("finish", help="Set the version when nothing is open")
    p.add_argument("--skip", action="store_true", help="Leave this release for now and silence the session-start line")

    p = sub.add_parser("restore", help="Put back what the last update changed")
    p.add_argument("--run", help="A history folder name (see --list); default the newest update")
    p.add_argument("--force", action="store_true", help="Also put back files the user changed after the update")
    p.add_argument("--list", action="store_true", help="Show the updates in the history, newest first; changes nothing")
    p.add_argument("--dry-run", action="store_true", help="Say what would be put back; changes nothing")

    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass
    commands = {"stamp": cmd_stamp, "check": cmd_check, "plan": cmd_plan, "diff": cmd_diff, "backup": cmd_backup,
                "apply": cmd_apply, "mark": cmd_mark, "decline": cmd_decline, "done": cmd_decline, "retire": cmd_retire,
                "finish": cmd_finish, "restore": cmd_restore}
    try:
        return commands[args.command](workspace_root(), args)
    except Problem as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except OSError as exc:  # a full disk, a read-only folder, a file another program holds open
        print(f"Stopped: {exc.strerror or exc}{f' ({exc.filename})' if exc.filename else ''}. Run the command again "
              "once that is solved; `restore` puts back what this update changed so far.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
