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
      "version": "1.1.0",                       the NEST release this workspace is level with
      "source": "https://github.com/...",       where releases come from (git URL or local path)
      "update_check": true,                     false silences the session-start line
      "files": {"scripts/wiki.py": {"kit": "kit/scripts/wiki.py", "kind": "copy", "sha256": "...",
                                    "version": "1.1.0"}},
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
              merge     changed in NEST, and adapted or edited here: needs a careful merge. Also
                        an untouched file whose new version says the new name of a renamed part
                        where it said the old one, while this workspace has that part under
                        another name (the item carries `name_kept`): `apply` refuses it, so the
                        script never writes a name the workspace does not use. Scripts are
                        exempt, they read both names.
              new       new in NEST
              removed   no longer part of NEST
              wiki      a wiki reference file changed (wiki files are never mapped one to one)
              reference an example or reference file without a fixed place here changed
              missing   changed in NEST, deleted here
              rename    a part got another name in NEST (the RENAMES table below): one item for
                        the whole part, with the files that move in `moves`
              taken     a file of a renamed part in a place of the user's own (a folder with a
                        translated name), taken out earlier in this update because an older
                        updater listed it as dropped: `bring-back` puts it back
            A `new` item carries `exists`: true means a file is already at that place, and it
            may be the user's own.
            `--json` for the skill; without it a short text overview.
  diff      The change NEST made to one kit file, as a unified diff. Takes the kit path, or the
            workspace path of a file that is recorded or in the plan.
  backup    Keep the current version of workspace files in this update's history folder. Always
            before a file is written; a file that does not exist yet is noted as new.
  apply     Replace `replace` files with the new kit file, bring back a deleted copy file, or add
            a new copy file with `--new KIT=PATH` (several pairs after one `--new`, or one
            `--new` per pair). Refuses a file the user changed, and never overwrites a file.
  mark      After a merge or a new adapted file: record that PATH now reflects the new kit file.
            Refuses a file that was not backed up in this update.
  rename    Move a part to its new name: every file in it, the user's own included, each
            backed up first. The files keep their content, except the `name:` line of a skill,
            which gets the new folder name; what NEST changed in them shows up in the next plan
            as an ordinary replace or merge under the new name. A file is moved by renaming it
            and the stamp is saved after each one, so a run that stopped halfway is carried on
            by running the command again, and no file is ever in two places.
            Files of the part that were taken out earlier in the same update (an older updater
            listed them as dropped, and its `retire` moved them into the history; also in an
            earlier part of the update that `finish` or a pause closed) come back first, from
            the update's own copies and with their records; `decline` does the same under the
            old name. A new version built at the new place in the meantime stops both: nothing
            is merged, and undo is the way back. `apply`, `apply --new` and `mark` refuse the
            places of such files, old and new.
  decline   Remember that the user does not want a change, so it is not offered again. For a
            rename: the files stay where they are and follow the kit file under its new name.
  done      The same record for a change that was dealt with by hand (a wiki file, a deleted file).
            For a `rename` item whose files were all taken out earlier in this update: the user
            wants the part gone, so its files stay out (their copies stay in the history).
  bring-back  Put `taken` files back where they were, with their records, from the update's own
            copies. Never over a file; a run that stops leaves no half file and is carried on
            by running it again.
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
OPEN_STATUSES = ("rename", "taken", "replace", "merge", "new", "removed", "wiki", "reference", "missing")
RUN_HOURS = 12
BROUGHT_BACK = "brought-back.txt"  # in a part that brought back files an earlier part took out
LEFT_OUT = "left-out.txt"  # in a part where the user chose to leave a taken-out renamed part out
RETRY_DAYS = 1.0  # after a check that could not reach the source, look again this soon
SIZE_FILES = ("SKILL.md", "SKILL.light.md", "formats.md", "formats.light.md")
LIGHT_SKILLS = ("verdict", "blueprint")  # the skills that come in two sizes, by today's name

# Kit paths that got another name: old -> new, one line per rename. A folder covers every file
# under it. Never remove a line: a workspace built from an old release still carries the old name.
RENAMES = {
    "kit/skills/idea": "kit/skills/verdict",
}


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
    def stop_group() -> None:
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
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        stop_group()
        try:
            proc.communicate(timeout=1)
        except (subprocess.TimeoutExpired, OSError, ValueError):
            pass  # something outside the group holds the pipes: let them go, never wait on them
        raise
    except KeyboardInterrupt:
        stop_group()  # the command has its own session, so Ctrl-C would not reach it
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


# --- names that changed ---------------------------------------------------------------------------

def swap(kit_rel: str, old: str, new: str) -> str | None:
    """`kit_rel` with `old` replaced by `new` when it is that path or lies under it, else None."""
    if kit_rel == old:
        return new
    return new + kit_rel[len(old):] if kit_rel.startswith(old + "/") else None


def renamed(kit_rel: str) -> str:
    """Today's name of a kit path, however many times it changed."""
    for _ in RENAMES:
        step = next((moved for old, new in RENAMES.items() if (moved := swap(kit_rel, old, new))), None)
        if step is None:
            break
        kit_rel = step
    return kit_rel


def former(kit_rel: str) -> list[str]:
    """The names a kit path had before, newest first."""
    names: list[str] = []
    while len(names) < len(RENAMES):
        step = next((back for old, new in RENAMES.items() if (back := swap(kit_rel, new, old))), None)
        if step is None or step in names:
            break
        names.append(step)
        kit_rel = step
    return names


def rename_line(kit_rel: str) -> tuple[str, str] | None:
    """The rename a kit path falls under: (the old name of the part, its name today)."""
    for old in RENAMES:
        if swap(kit_rel, old, old):
            return old, renamed(old)
    return None


def skill_now(skill: str) -> str:
    """Today's name of a skill: `idea` is `verdict`."""
    return renamed(f"kit/skills/{skill}").split("/")[2]


def skill_names(skill: str) -> list[str]:
    """Every folder name a skill may have in a workspace: today's, then the earlier ones."""
    return [skill, *(name.split("/")[2] for name in former(f"kit/skills/{skill}"))]


def in_release(folder: Path, kit_rel: str) -> str:
    """The name a kit file has in one release: its own, or the one from before or after a rename."""
    for name in (kit_rel, *former(kit_rel), renamed(kit_rel)):
        if (folder / name).is_file():
            return name
    return kit_rel


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
    if top == "scripts" and len(parts) == 2 and (name.endswith(".py") or name == "obsidian.lock.json"):
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
            is_light = skill_now(skill) in LIGHT_SKILLS and skill_now(skill) in light
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
            team = "verdict" if name.startswith("council-") else "blueprint"
            return f".claude/agents/{name}" if (parts[1] == "light") == (team in light) else None
    return None


def detect_light(root: Path) -> set[str]:
    """The skills that are here in their light size, by today's name, whichever name the folder has."""
    return {skill for skill in LIGHT_SKILLS
            if any((root / ".claude/skills" / name / "formats.light.md").is_file() for name in skill_names(skill))}


def moved_path(ws_rel: str, kit_old: str, kit_new: str) -> str:
    """Where a workspace file goes when its kit file is renamed: along with it when it sits in
    the kit file's default place, and nowhere when the user or the setup put it somewhere else."""
    for light in (set(), set(LIGHT_SKILLS)):
        if (target_for(kit_old, light) or "").lower() == ws_rel.lower():
            return target_for(kit_new, light) or ws_rel
    return ws_rel


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
    light = {skill_now(skill) for skill in args.light or []} | detect_light(root)
    pairs: dict[str, str] = {}
    kept_names: dict[str, bool] = {}

    def from_the_kit(old_part: str) -> bool:
        """Is what lies under a part's earlier name here made from the kit? A folder called `idea`
        can be a skill of the user's own. It counts as the kit's only when at least one file in it
        is still the kit file, byte for byte; when that cannot be told, it is left unrecorded."""
        if old_part not in kept_names:
            new_part = renamed(old_part)
            kept_names[old_part] = any(
                (place := target_for(swap(rel, new_part, old_part), light)) and sha(root / place) == sha(path)
                for rel, path in files.items() if swap(rel, new_part, new_part))
        return kept_names[old_part]

    for kit_rel in files:
        target = target_for(kit_rel, light)
        if not (target and (root / target).is_file()):
            # The place under a name the part had before (a rename the user declined).
            target = next((place for name in former(kit_rel)
                           if (place := target_for(name, light)) and (root / place).is_file()
                           and (line := rename_line(name)) and from_the_kit(line[0])), None)
        if target:
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

    def add(status: str, kit_rel: str, path: str | None, kind: str | None) -> dict:
        latest_sha = sha(new_files[kit_rel]) if kit_rel in new_files else None
        if status in OPEN_STATUSES and declined.get(kit_rel) == (latest_sha or "removed"):
            status = "declined"
        item = {"status": status, "kit": kit_rel, "path": path, "kind": kind, "group": group_of(kit_rel)}
        if status == "new":
            item["exists"] = bool(path) and os.path.lexists(root / path)
        items.append(item)
        return item

    # Files of a renamed part that were taken out earlier in this open update (by an updater from
    # before the rename table, which listed them as dropped) still count as the user's: the plan
    # reads the stamp with their records in it, so the part is one rename offer and not nothing.
    taken = taken_out(root, stamp)
    stamp = {**stamp, "files": {**stamp["files"], **{ws_rel: entry for ws_rel, (entry, _) in taken.items()}}}

    elsewhere = parts_under_another_name(stamp)

    def name_kept(kit_rel: str) -> str | None:
        """The renamed part (its old kit path) whose new name this kit file's change would bring
        into a workspace that has that part under another name, or None."""
        if not elsewhere or kit_rel not in new_files or group_of(kit_rel) == "scripts" or kit_rel.endswith(".py"):
            return None  # a script reads both names of a part, so its new version is safe under either
        was = next((base_files[name] for name in (kit_rel, *former(kit_rel)) if name in base_files), None)
        before, after = read_text(was) if was else None, read_text(new_files[kit_rel])
        return next((old for old, new in elsewhere if after is not None and names_the_rename(before, after, old, new)), None)

    def judge(ws_rel: str, entry: dict, kit_rel: str) -> None:
        """One recorded file against the kit file it follows."""
        kind, recorded = entry.get("kind", "adapted"), entry.get("sha256")
        if kit_rel not in new_files:
            add("removed" if os.path.lexists(root / ws_rel) else "gone", kit_rel, ws_rel, kind)
            return
        if sha(new_files[kit_rel]) == recorded:
            add("unchanged", kit_rel, ws_rel, kind)
            return
        kept = name_kept(kit_rel)
        if not (root / ws_rel).is_file():
            item = add("missing", kit_rel, ws_rel, kind)
        elif sha(root / ws_rel) == sha(new_files[kit_rel]):
            item, kept = add("replace", kit_rel, ws_rel, kind), None  # already the new kit file: only the record is behind
        elif kind == "copy" and sha(root / ws_rel) == recorded and not kept:
            item = add("replace", kit_rel, ws_rel, kind)  # untouched
        else:
            # Changed here, adapted, or a change that names a part this workspace has under another
            # name: replacing the file would write the new name into a workspace that does not use it.
            item = add("merge", kit_rel, ws_rel, kind)
        if kept:
            item["name_kept"] = kept

    def taken_item(ws_rel: str, entry: dict, kit_rel: str, copy: Path) -> None:
        """A recorded file in a place of the user's own that an older updater's `retire` took out."""
        item = add("taken", kit_rel, ws_rel, entry.get("kind", "adapted"))
        here = os.path.lexists(root / ws_rel)
        item["blocked"] = here and not same_bytes(root / ws_rel, copy)
        item["how"] = (f"Taken out earlier in this update, when an older updater listed it as dropped. NEST did not drop "
                       f"it: it follows {kit_rel} now, in this folder of the user's own. `bring-back {ws_rel}` (or the "
                       "folder) puts the user's own version back where it was, with its record, from the update's own "
                       "backup; the next `plan` lists what NEST changed in it. To leave it out after all: "
                       f"`done {kit_rel}`. Do not copy it back by hand or write it again from the kit.")
        if item["blocked"]:
            item["how"] += (f" Something else is at {ws_rel} now, not the copy that was kept: nothing is brought back "
                            "over it. Show the user both; `restore` puts the whole update back.")

    mapped = set()
    moving: dict[tuple[str, str], list[tuple[str, dict]]] = {}
    for ws_rel, entry in sorted(stamp["files"].items()):
        kit_rel = entry.get("kit", "")
        mapped.add(kit_rel)
        line = None if kit_rel in new_files else rename_line(kit_rel)
        if line:
            moving.setdefault(line, []).append((ws_rel, entry))  # judged below, as one part
        else:
            judge(ws_rel, entry, kit_rel)
    for old in begun_renames(stamp):  # a rename that was started and has files of the user's left to move
        moving.setdefault((old, renamed(old)), [])

    open_renames = []
    for (old, new), entries in moving.items():
        item, stay = rename_item(root, stamp, old, new, entries, new_files,
                                 {ws_rel: copy for ws_rel, (_, copy) in taken.items()})
        if item:
            items.append(item)
            open_renames.append(item)
        for ws_rel, entry in entries:
            kit_old = entry.get("kit", "")
            if ws_rel in stay and ws_rel in taken:
                # Somewhere of its own and taken out earlier in this update: not a file the user
                # deleted, and not one NEST left alone. It comes back where it was, then is judged.
                mapped.add(swap(kit_old, old, new))
                if swap(kit_old, old, new) in new_files:
                    taken_item(ws_rel, entry, swap(kit_old, old, new), taken[ws_rel][1])
            elif ws_rel in stay:
                # Installed somewhere of its own (a folder with a translated name, say): nothing changes
                # for the user, so there is nothing to ask. The file just follows the kit file's new name.
                mapped.add(swap(kit_old, old, new))
                judge(ws_rel, entry, swap(kit_old, old, new))
            elif not item and ws_rel not in taken:  # nothing of it is both here and in the new release: dropped files like any other
                add("removed" if os.path.lexists(root / ws_rel) else "gone", kit_old, ws_rel, entry.get("kind", "adapted"))

    homes = skill_homes(stamp)

    def offer_new(kit_rel: str, target: str | None, kind: str) -> None:
        """A new file: part of a rename that is still open, or an item of its own."""
        owner = next((item for item in open_renames if swap(kit_rel, item["kit"], item["kit"])), None)
        if owner:
            owner["new"].append(kit_rel)
        else:
            add("new", kit_rel, at_home(homes, kit_rel, target), kind)

    # A part counts under today's name too, so a renamed part is neither new nor someone else's.
    have_groups = {group_of(name) for kit_rel in mapped for name in (kit_rel, renamed(kit_rel))} | {"scripts"}
    base_groups = {group_of(name) for kit_rel in base_files for name in (kit_rel, renamed(kit_rel))}
    has_wiki = (root / "wiki.config.json").is_file() or (root / "wiki").is_dir()
    for kit_rel in sorted(set(new_files) - mapped):
        group = group_of(kit_rel)
        was = next((name for name in (kit_rel, *former(kit_rel)) if name in base_files), None)  # its name in the old release
        if group == "wiki":
            if has_wiki and base_dir and sha(new_files[kit_rel]) != (sha(base_files[was]) if was else None):
                add("wiki", kit_rel, None, None)
            continue
        target = target_for(kit_rel, light)
        parts = kit_rel.split("/")
        other_size = target is None and ((parts[1] == "agents" and len(parts) == 4)
                                         or (parts[1] == "skills" and parts[-1] in SIZE_FILES))
        if other_size:
            continue  # the full file of a team this workspace has in light, or the other way round
        if target is None and was:
            # An example or reference file with no fixed place here (the setup made something of
            # its own from it): say that it changed, for the parts this workspace has.
            if group in have_groups and sha(new_files[kit_rel]) != sha(base_files[was]):
                add("reference", kit_rel, None, None)
            continue
        if kit_rel in declined and declined[kit_rel] != sha(new_files[kit_rel]):
            offer_new(kit_rel, target, "copy" if group == "scripts" else "adapted")  # declined before, changed since
            continue
        if was or (base_dir is None and group not in have_groups):
            continue
        if group in have_groups or (base_dir is not None and group not in base_groups):
            offer_new(kit_rel, target, "copy" if group == "scripts" else "adapted")

    return {"installed": show(installed), "latest": show(latest), "source": source,
            "base_dir": base_dir.as_posix() if base_dir else None, "latest_dir": latest_dir.as_posix(),
            "note": base_note, "notes": release_notes(latest_dir / "CHANGELOG.md", installed, latest), "items": items}


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def parts_under_another_name(stamp: dict) -> list[tuple[str, str]]:
    """The renamed parts this workspace has, but not at the place their new name gives them:
    (old kit path, new kit path). That is a part whose old name was kept, one whose rename is
    still to be decided or finished, and one in a folder with a name of the user's own."""
    found = []
    for old in RENAMES:
        new = renamed(old)
        for ws_rel, entry in stamp["files"].items():
            kit_now = renamed(str(entry.get("kit", "")))
            if not swap(kit_now, new, new):
                continue
            places = {(target_for(kit_now, light) or "").lower() for light in (set(), set(LIGHT_SKILLS))}
            if ws_rel.lower() not in places:
                found.append((old, new))
                break
    return found


def names_the_rename(before: str | None, after: str, old: str, new: str) -> bool:
    """Does the change from `before` to `after` put a renamed part's new name where its old name
    was? The names are the last parts of the two kit paths (`idea`, `verdict`), as whole words:
    a `name: idea` that became `name: verdict`, a path `../idea/x.md` that became
    `../verdict/x.md`. Judged per changed block of lines, so a file that merely uses both words
    is not caught. Without a `before` there is nothing to compare: any mention of the new name counts."""
    def count(text: str, path: str) -> int:
        return len(re.findall(rf"(?<![\w-]){re.escape(path.rsplit('/', 1)[-1])}(?![\w-])", text))

    if before is None:
        return count(after, new) > 0
    a, b = before.splitlines(), after.splitlines()
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        was, now = "\n".join(a[i1:i2]), "\n".join(b[j1:j2])
        if count(now, new) > count(was, new) and count(was, old) > count(now, old):
            return True
    return False


def update_parts(root: Path, stamp: dict) -> list[Path]:
    """The history folders of the update that is going on now, newest first.

    One update can be done in parts: `finish` with things left open closes a part, and so does a
    pause of more than RUN_HOURS. The parts are the folders, from the newest back, that began
    from the release this workspace is still on and were not put back: the same group `restore`
    takes together. A finished update moved the version, so its folders are never in it."""
    parts = []
    for folder in reversed(history_runs(root)):
        if (folder / "restored").is_file() or run_before(folder) != stamp.get("version"):
            break
        parts.append(folder)
    return parts


def taken_out(root: Path, stamp: dict) -> dict[str, tuple[dict, Path]]:
    """The files of renamed parts that this update took out of the workspace: {path: (the record
    it had, its kept copy)}.

    The updater of a release from before the rename table shows a renamed part as files NEST
    dropped, and its `retire` then moves them into the update's history and drops their records.
    That is not what the user meant by it. What is needed to see it is all in the update's parts:
    the stamp as it was when each part began (`nest.json` in its folder) and the copy of each
    file (`files/`). The newest part whose stamp still has the record is the part that took the
    file out, and its copy is the one that counts. A part this update renamed itself is left out
    (`renamed.txt` in any part, or a rename that is half done), and so is a part the user chose
    to leave out (LEFT_OUT, written by `done`) and anything from another update: that is for undo."""
    parts = update_parts(root, stamp)
    done = set(begun_renames(stamp))
    for folder in parts:
        for name in ("renamed.txt", LEFT_OUT):
            try:
                done |= set((folder / name).read_text(encoding="utf-8").split("\n"))
            except OSError:
                pass
    have = {key.lower() for key in stamp["files"]}
    seen: set[str] = set()
    taken = {}
    for folder in parts:
        before = read_json(folder / "nest.json").get("nest")
        files = before.get("files") if isinstance(before, dict) else None
        for ws_rel, entry in sorted(files.items()) if isinstance(files, dict) else []:
            if ws_rel.lower() in seen:
                continue
            seen.add(ws_rel.lower())
            line = rename_line(str(entry.get("kit", ""))) if isinstance(entry, dict) else None
            if not line or line[0] in done or ws_rel.lower() in have:
                continue
            copy = folder / "files" / ws_rel
            try:
                if safe_rel(ws_rel) != ws_rel or not copy.is_file() or copy.is_symlink():
                    continue
            except Problem:
                continue
            taken[ws_rel] = (dict(entry), copy)
    return taken


def put_back(root: Path, stamp: dict, paths: list[str]) -> list[str]:
    """Bring files that were taken out earlier in this update back to where they were, from the
    update's own copies, with the records they had. Nothing is overwritten: a file that is there
    already is the same one (the plan blocks the item otherwise). Each copy is written next to
    the update's history first and then renamed into place, so a run that stops never leaves
    half a file; a file that came from an earlier, closed part is noted as new in this one, so an
    undo takes it away again before the older part puts its own copy back. Such a part is noted
    in BROUGHT_BACK, so it is never put back without that older part (`brought_back_group`)."""
    taken = taken_out(root, stamp)
    back = []
    for ws_rel in paths:
        if ws_rel not in taken:
            continue
        entry, copy = taken[ws_rel]
        no_symlink(root, ws_rel)
        here = run_dir(root)
        if here not in copy.parents:  # from an earlier part: noted before anything comes back
            listed = (here / BROUGHT_BACK).read_text(encoding="utf-8").splitlines() if (here / BROUGHT_BACK).is_file() else []
            if ws_rel not in listed:
                with (here / BROUGHT_BACK).open("a", encoding="utf-8", newline="\n") as note:
                    note.write(ws_rel + "\n")
        target = root / ws_rel
        if not os.path.lexists(target):
            backup(root, ws_rel)
            incoming = run_dir(root) / "incoming" / ws_rel
            try:
                incoming.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(copy, incoming)
                target.parent.mkdir(parents=True, exist_ok=True)
                if os.path.lexists(target):
                    raise FileExistsError(17, "A file is already there", str(target))
                os.replace(incoming, target)
            except OSError as exc:
                raise Problem(f"Stopped while bringing back {ws_rel}: {exc.strerror or exc}. Nothing half is left at its "
                              f"place; {len(back)} file(s) before it are back and recorded. Run the same command again "
                              "once that is solved: it carries on. `restore` puts the whole update back.") from exc
        stamp["files"][ws_rel] = entry
        save_stamp(root, stamp)
        back.append(ws_rel)
    return back


def taken_place(plan: dict, ws_rel: str) -> str | None:
    """Why nothing may be written at `ws_rel`, when it is the place of a file this update took out
    (or where such a file goes under its new name), or None."""
    low = ws_rel.lower()
    for item in plan["items"]:
        if item["status"] == "taken" and (item["path"] or "").lower() == low:
            return (f"{ws_rel} was taken out earlier in this update, and it is the user's own version that belongs "
                    f"there. `bring-back {ws_rel}` puts it back from the update's own backup; `done {item['kit']}` "
                    "leaves it out. Nothing was changed.")
        if item["status"] == "rename":
            for f in item["files"]:
                if f.get("taken") and low in (f["path"].lower(), f["to"].lower()):
                    return (f"{ws_rel} is a place of {item['path'] or item['from']}, whose files were taken out earlier "
                            "in this update. Their copies are in the update's own backup, and a new file here would "
                            f"stand in for them. `rename {item['from']}` brings them back under the new name, "
                            f"`decline {item['from']}` under the old one. Nothing was changed.")
    return None


def fresh_problem(item: dict) -> Problem:
    return Problem(f"A new version of {item['to'] or item['kit']} was built here ({', '.join(item['fresh'])}) while the "
                   f"user's own files of {item['path'] or item['from']} were taken out earlier in this update. NEST will "
                   "not merge the two or put one over the other. Nothing was changed. Tell the user, and after their yes "
                   "`restore` puts the whole update back: their own files return, the new ones go to the history, and "
                   "the rename can then be chosen from a fresh `plan`.")


def begun_renames(stamp: dict) -> list[str]:
    """The renames this workspace started and did not finish, by old kit path (`renaming` in the stamp)."""
    marks = stamp.get("renaming")
    return [old for old, new in marks.items() if old in RENAMES and renamed(old) == new and old != new] \
        if isinstance(marks, dict) else []


def home_folders(old: str, new: str) -> tuple[str, str] | None:
    """The workspace folders of a renamed kit folder, (old, new), or None when it has no fixed place."""
    probe = "nest-probe.md"
    src, dst = target_for(f"{old}/{probe}", set()), target_for(f"{new}/{probe}", set())
    if not src or not dst or not src.endswith("/" + probe) or not dst.endswith("/" + probe):
        return None
    return src[:-len(probe) - 1], dst[:-len(probe) - 1]


def same_bytes(a: Path, b: Path) -> bool:
    try:
        return a.is_file() and b.is_file() and not a.is_symlink() and not b.is_symlink() and a.read_bytes() == b.read_bytes()
    except OSError:
        return False


def folder_contents(root: Path, src: str) -> tuple[list[str], list[str]]:
    """The plain files under a workspace folder and the symbolic links in it (never followed)."""
    plain, links = [], []
    base = root / src
    if not base.is_dir() or base.is_symlink():
        return plain, links
    for here, dirs, names in os.walk(base):
        for name in sorted(dirs):
            if (Path(here) / name).is_symlink():
                links.append((Path(here) / name).relative_to(root).as_posix())
        dirs[:] = sorted(name for name in dirs if not (Path(here) / name).is_symlink())
        for name in sorted(names):
            path = Path(here) / name
            (links if path.is_symlink() else plain).append(path.relative_to(root).as_posix())
    return sorted(plain), sorted(links)


def rename_item(root: Path, stamp: dict, old: str, new: str, entries: list[tuple[str, dict]],
                new_files: dict[str, Path], taken: dict[str, Path] | None = None) -> tuple[dict | None, set[str]]:
    """One plan item for a part that got another name, and the recorded files that stay where they are.

    The item is None when nothing of the part is left to move: no recorded file of it is both in
    this workspace and in the new release, and no rename of it was begun and left unfinished.
    A recorded file outside the part's own folder (a folder with a translated name, a place the
    user chose) does not move and is not asked about: it is in the second value, and the plan
    lists it as an ordinary file that follows the kit file under its new name.

    `files` are the recorded files with where they go and whether NEST changed them; `also` the
    user's own files in the same folder, which move along; `moves` every (from, to) pair still to
    do; `blocked` the places a file would land that hold something this rename did not put
    there; `links` the symbolic links in the folder, which stay where they are; `new` what the
    part gained; `half` says a rename of it was begun before (run it again, or undo). `taken`
    are the recorded files that were taken out earlier in this update, with their kept copies in
    the argument (`rename` and `decline` bring them back first); `fresh` the files that were
    built at the new place in the meantime, which stop both.
    """
    taken = taken or {}
    half = old in begun_renames(stamp)
    files = []
    for ws_rel, entry in entries:
        kit_old = entry.get("kit", "")
        kit_new = swap(kit_old, old, new)
        files.append({"path": ws_rel, "to": moved_path(ws_rel, kit_old, kit_new), "from": kit_old, "kit": kit_new,
                      "kind": entry.get("kind", "adapted")})
    folders: dict[str, str] = {}  # the workspace folders that move as a whole, old -> new
    for f in files:
        if f["from"] != old and f["path"] != f["to"]:  # a file under a renamed folder, in its default place
            src, dst = f["path"].split("/"), f["to"].split("/")
            while len(src) > 1 and len(dst) > 1 and src[-1] == dst[-1]:
                src.pop(), dst.pop()
            folders["/".join(src)] = "/".join(dst)
    home = home_folders(old, new)
    if half and home and not any(src.lower() == home[0].lower() for src in folders):
        folders[home[0]] = home[1]  # what the first run left behind in the folder is still part of it
    for f in files:  # a recorded file under another name inside a folder that moves goes with the folder
        if f["path"] == f["to"]:
            for src, dst in folders.items():
                if f["path"].lower().startswith(src.lower() + "/"):
                    f["to"] = dst + f["path"][len(src):]
    stay = {f["path"] for f in files if f["path"] == f["to"]}
    files = [f for f in files if f["path"] not in stay]
    moves, blocked, fresh = [], [], []
    for f in files:
        here, there = os.path.lexists(root / f["path"]), os.path.lexists(root / f["to"])
        if f["path"] in taken:
            # Taken out earlier in this update: its copy is in the update's history, and that is
            # the file the rename is about. Something else at its old place is in the way.
            f["taken"] = True
            f["change"] = "dropped" if f["kit"] not in new_files else \
                "same" if sha(new_files[f["kit"]]) == stamp["files"][f["path"]].get("sha256") else "changed"
            moves.append([f["path"], f["to"]])
            if here and not same_bytes(root / f["path"], taken[f["path"]]):
                blocked.append(f["path"])
            if there:
                fresh.append(f["to"])
            continue
        if not here:
            # Gone from its old place. In a rename that was begun, a file at the new place is the one
            # that was moved just before the first run stopped: only its record is behind.
            f["change"] = "moved" if half and there else "missing"
            if there and not half:
                blocked.append(f["to"])
            continue
        f["change"] = "dropped" if f["kit"] not in new_files else \
            "same" if sha(new_files[f["kit"]]) == stamp["files"].get(f["path"], {}).get("sha256") else "changed"
        moves.append([f["path"], f["to"]])
        if there and not same_bytes(root / f["path"], root / f["to"]):
            blocked.append(f["to"])
    known = {f["path"] for f in files}
    also, links = [], []
    for src, dst in sorted(folders.items()):
        plain, found = folder_contents(root, src)
        links += found
        for rel in plain:
            if rel in known or any(rel.lower() == k.lower() and same_file(root / rel, root / k) for k in known):
                continue
            also.append(rel)
            to = dst + rel[len(src):]
            moves.append([rel, to])
            if os.path.lexists(root / to) and not same_bytes(root / rel, root / to):
                blocked.append(to)
    alive = any(f["change"] in ("same", "changed") for f in files)
    if not (alive or half):  # a rename that was begun stays open until `rename` has finished it
        return None, stay
    whole = files[0] if len(files) == 1 and files[0]["from"] == old else None
    pair = (whole["path"], whole["to"]) if whole else next(iter(folders.items())) if len(folders) == 1 else (None, None)
    gone = sorted(f["path"] for f in files if f.get("taken"))
    how = (f"One part under a new name, not a dropped part plus a new one. The new name: `rename {old}` moves "
           "every file as it is (each backed up) and sets the `name:` line of a skill to its new folder name, "
           "then `plan` again lists what NEST changed in them. "
           + ("This rename was begun and did not finish: `rename` again carries on, `restore` puts everything back."
              if half else
              f"The old name: `decline {old}` leaves them where they are and still brings later changes."))
    if fresh:
        how = ("The user's own files of this part were taken out earlier in this update, and a new version was built at "
               f"the new place since ({', '.join(fresh)}). Nothing is moved and nothing is merged: tell the user, and "
               "after their yes `restore` puts the whole update back, their own files included. When the user wants "
               f"only the new version, `done {old}` leaves their old files out (they stay in the history).")
    elif gone:
        how = ("One part under a new name. Its files were taken out earlier in this update, when they were listed as "
               f"dropped; their copies are in the update's own backup. The new name: `rename {old}` brings them back and "
               f"moves them, as if they had never left. The old name: `decline {old}` brings them back where they were. "
               "Do not copy them back by hand, build the part again from the kit, or `restore` the whole update for this. "
               f"When the user wants the part gone: `done {old}` leaves its files out (they stay in the history).")
    return {"status": "rename", "kit": new, "from": old, "path": pair[0], "to": pair[1], "kind": None,
            "group": group_of(new), "was": group_of(old), "files": files, "also": also, "moves": moves,
            "folders": folders, "blocked": blocked, "links": links, "half": half, "new": [],
            "taken": gone, "fresh": fresh, "how": how}, stay


def same_file(a: Path, b: Path) -> bool:
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def skill_homes(stamp: dict) -> dict[str, str]:
    """Where each skill lives in this workspace, by kit folder: the folder of its recorded SKILL.md."""
    homes = {}
    for ws_rel, entry in stamp["files"].items():
        parts = str(entry.get("kit", "")).split("/")
        if len(parts) == 4 and parts[1] == "skills" and parts[3] in ("SKILL.md", "SKILL.light.md") and "/" in ws_rel:
            homes[renamed("/".join(parts[:3]))] = ws_rel.rsplit("/", 1)[0]
    return homes


def at_home(homes: dict[str, str], kit_rel: str, target: str | None) -> str | None:
    """The place of a new file of a skill: next to the skill's own files, also when its folder
    here has another name than in the kit (a rename the user declined)."""
    parts = kit_rel.split("/")
    if not target or len(parts) < 4 or parts[1] != "skills":
        return target
    home, default = homes.get("/".join(parts[:3])), f".claude/skills/{parts[2]}"
    return home + target[len(default):] if home and home != default and target.startswith(default + "/") else target


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
    # Whether the update is still open is decided before the plan is made: a part that a pause
    # closes here must not be offered in a form the next command no longer sees.
    open_now = current_run(root, begin=True)
    plan = current_plan(root, stamp, fresh=True, latest=newest)
    plan["run"] = open_now
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
    labels = {"rename": "has a new name in NEST", "taken": "taken out earlier in this update, not dropped by NEST",
              "replace": "safe to replace", "merge": "needs a merge", "new": "new", "removed": "no longer in NEST",
              "wiki": "wiki reference changed", "reference": "example or reference file changed",
              "missing": "changed in NEST, deleted here"}
    for status in OPEN_STATUSES:
        rows = [item for item in todo if item["status"] == status]
        if rows:
            print(f"\n{labels[status]} ({len(rows)}):")
            for item in rows:
                if status == "rename":
                    print(f"  {item['path'] or item['from']} -> {item['to'] or item['kit']}  [{item['group']}]")
                    if item["half"]:
                        print(f"    begun and not finished: part of it has the new name already. `rename {item['from']}` "
                              "carries on with what is left; `restore` puts everything back.")
                    elif item["fresh"]:
                        print("    its own files were taken out earlier in this update and a new version was built at the "
                              "new place since: nothing is moved or merged; `restore` puts the whole update back.")
                    elif item["taken"]:
                        print(f"    taken out earlier in this update ({len(item['taken'])} file(s), kept in its backup): "
                              f"`rename {item['from']}` brings them back under the new name, `decline {item['from']}` "
                              "under the old one.")
                elif status == "taken":
                    print(f"  {item['path']}  [{item['group']}]  `bring-back {item['path']}` puts it back"
                          + ("; something else is there now" if item["blocked"] else ""))
                else:
                    print(f"  {item['path'] or item['kit']}  [{item['group']}]")
    return 0


def diff_base(root: Path, stamp: dict, plan: dict, kit_rel: str) -> tuple[str | None, str, str]:
    """Where the diff of one kit file starts: (folder, version label, warning).

    Normally the installed release. A file that was already brought over while other parts stayed
    open is level with a newer release than the stamp's version; comparing it from the old one
    would show changes that are in the user's file already, and a merge would add them twice.
    """
    base_dir, label = plan["base_dir"], plan["installed"]
    entries = [entry for entry in stamp["files"].values() if renamed(entry.get("kit", "")) == renamed(kit_rel)]
    if not entries:
        return base_dir, label, ""
    recorded = entries[0].get("sha256")
    if base_dir and sha(Path(base_dir) / in_release(Path(base_dir), kit_rel)) == recorded:
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
        if folder and sha(folder / in_release(folder, kit_rel)) == recorded:
            return folder.as_posix(), show(version), ""
    return base_dir, label, (f"Note: the file in this workspace was made from a later version of {kit_rel} than "
                             f"NEST {label}, and that version could not be fetched. Part of this diff may be in "
                             "the user's file already: compare before you merge.\n")


def kit_path_for(stamp: dict, plan: dict, given: str) -> str:
    """The kit path `diff` works on. A workspace path is taken too: the file's record, or its
    place in the plan (a new file, a file of a part that is being renamed), says which kit file it is."""
    if given.startswith("kit/"):
        return given
    try:
        ws_rel = stamp_key(stamp, safe_rel(given))
    except Problem:
        ws_rel = given
    for item in plan["items"]:
        if item.get("path") == ws_rel and item["status"] != "rename":
            return item["kit"]
        for f in item.get("files", []):
            if ws_rel in (f["path"], f["to"]):
                return f["kit"]
    if ws_rel in stamp["files"]:
        return renamed(str(stamp["files"][ws_rel].get("kit", "")))
    raise Problem(f"{given} is not a file NEST installed here or offers in this release. `diff` takes a kit path "
                  "(`kit/skills/<name>/SKILL.md`, the `kit` of an item in the plan) or the workspace path of such a file.")


def cmd_diff(root: Path, args) -> int:
    stamp = need_stamp(root)
    plan = current_plan(root, stamp)
    kit_rel = kit_path_for(stamp, plan, args.kit.replace("\\", "/"))
    base_dir, label, warning = diff_base(root, stamp, plan, kit_rel)
    if base_dir is None:
        print(f"There is no copy of release {plan['installed']} to compare with; read the new file instead: "
              f"{plan['latest_dir']}/{kit_rel}")
        return 0

    def lines(folder: str) -> tuple[list[str], str]:
        name = in_release(Path(folder), kit_rel)  # a renamed file is compared across its two names
        try:
            return (Path(folder) / name).read_text(encoding="utf-8", errors="replace").splitlines(keepends=True), name
        except OSError:
            return [], name

    (old, old_name), (new, new_name) = lines(base_dir), lines(plan["latest_dir"])
    if not old and not new:
        raise Problem(f"{kit_rel} is in neither release.")
    out = "".join(difflib.unified_diff(old, new, f"NEST {label}/{old_name}", f"NEST {plan['latest']}/{new_name}"))
    sys.stdout.buffer.write((warning + (out or "No difference.\n")).encode("utf-8"))
    return 0


# --- changing the workspace ----------------------------------------------------------------------

def run_dir(root: Path) -> Path:
    """The history folder of this update, made on first use with the stamp as it was then.

    A new folder is filled under a name of its own and renamed into place, so a folder with the
    update's name always holds that stamp: one without it would cut the update in two, for
    `restore` and for the files that `rename` and `bring-back` look for in its earlier parts."""
    folder = root / HISTORY_DIR / current_run(root)
    if not (folder / "nest.json").is_file() and not (folder / "no-stamp").is_file():
        here = folder if folder.is_dir() else folder.with_name(f".{folder.name}.starting")
        if here != folder and here.exists():
            force_rmtree(here)  # left by a start that stopped: it holds nothing else
        here.mkdir(parents=True, exist_ok=True)
        if (root / STAMP_FILE).is_file():
            shutil.copy2(root / STAMP_FILE, here / "nest.json")
        else:
            (here / "no-stamp").write_text("", encoding="utf-8")
        if here != folder:
            os.rename(here, folder)
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
    # `--new` takes one pair or several, and a pair is known by its `=`: so `--new a=b c=d`,
    # `--new a=b --new c=d` and a path that follows a pair all mean what they say.
    given = [*args.paths, *(args.new or [])]
    paths, pairs = [item for item in given if "=" not in item], [item for item in given if "=" in item]
    for item in paths:
        ws_rel = stamp_key(stamp, safe_rel(item))
        no_symlink(root, ws_rel)
        if why := taken_place(plan, ws_rel):
            raise Problem(why)
        found = by_path.get(ws_rel)
        if not found or ws_rel not in stamp["files"]:
            raise Problem(f"{ws_rel} is not a file NEST installed here.")
        if found["status"] == "unchanged":
            continue
        entry = stamp["files"][ws_rel]
        kept = found.get("name_kept")
        if kept and sha(root / ws_rel) != sha(new_files.get(found["kit"], Path())):
            old_name, new_name = kept.rsplit("/", 1)[-1], renamed(kept).rsplit("/", 1)[-1]
            waiting = next((i for i in plan["items"] if i["status"] == "rename" and i["from"] == kept), None)
            says = f"{ws_rel} is not replaced: NEST's new version of it says `{new_name}` where it said `{old_name}`"
            if waiting:
                # The rename is still to come (or to be finished): this file waits for it, and nobody
                # merges it by hand in the meantime, or it would keep the old name after the move.
                first = (f"Finish the rename first, `rename {kept}` (it was begun and stopped halfway)" if waiting["half"]
                         else f"Run `rename {kept}` first when the user wants the new name")
                raise Problem(f"{says}, and that part does not have its new name here yet. {first}: after it this "
                              f"file is an ordinary replace and `apply {ws_rel}` works. Do not merge it by hand "
                              "before that. Only when the user keeps the old name (`decline`) is it carried in by "
                              "hand with the name left as it is. Nothing was changed.")
            raise Problem(f"{says}, and this workspace has that part under the old name the user kept, or under a "
                          "folder name of its own. Copying the file would write a name this workspace does not use. "
                          f"Carry the rest of the change in by hand and leave the name as it is: `diff {found['kit']}`, "
                          f"`backup {ws_rel}`, write it, `mark {ws_rel}={found['kit']}`. Nothing was changed.")
        if not os.path.lexists(root / ws_rel):
            if found["kit"] not in new_files:
                raise Problem(f"{ws_rel} is no longer part of NEST and is not in this workspace either: there is "
                              "nothing to bring back.")
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
    for item in pairs:
        kit_rel, ws_raw = split_pair(item)
        ws_rel = safe_rel(ws_raw)
        no_symlink(root, ws_rel)
        if why := taken_place(plan, ws_rel):
            raise Problem(why)
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
        if why := taken_place(plan, ws_rel):
            raise Problem(why)
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
        hits = [item for item in todo if item["kit"] == wanted or item["kit"].startswith(wanted + "/")
                or wanted in (item["path"], item.get("from"), item.get("to"))]
        if not hits:
            raise Problem(f"Nothing open matches {raw}.")
        for item in hits:
            count += 1
            if item["status"] == "rename":
                if item["half"]:
                    raise Problem(f"Part of {item['path'] or item['from']} was moved to its new name already, so keeping "
                                  f"the old name now would leave it in two folders. `rename {item['from']}` carries on "
                                  "with what is left; `restore` puts everything back, and then it can be declined. "
                                  "Nothing was changed.")
                if args.command == "done" and item["taken"]:
                    # The user wants the part gone: what was taken out stays out. Only when all of it
                    # was taken out, or the part would still be half here and on offer.
                    here = [f["path"] for f in item["files"] if not f.get("taken")]
                    if here:
                        raise Problem(f"Files of {item['path'] or item['from']} are still in this workspace ({', '.join(here)}), "
                                      "so it cannot be left out: only a part whose files were all taken out can. Keep the "
                                      f"old name (`decline {item['from']}`) or take the new one (`rename {item['from']}`). "
                                      "Nothing was changed.")
                    with (run_dir(root) / LEFT_OUT).open("a", encoding="utf-8", newline="\n") as note:
                        note.write(item["from"] + "\n")
                    own = f" The user's own files in its folder stay where they are: {', '.join(item['also'])}." if item["also"] else ""
                    print(f"{item['path'] or item['from']} stays out: its {len(item['taken'])} file(s) taken out earlier in "
                          "this update stay in the update's history and are not offered again in it. `restore` puts them "
                          f"back with the rest of the update.{own}")
                    continue
                if item["fresh"]:
                    raise fresh_problem(item)
                if item["taken"]:
                    # Keeping the old name moves nothing, so only the old places of the taken files matter.
                    in_way = [path for path in item["blocked"] if path in item["taken"]]
                    if in_way:
                        raise Problem(f"In the way: {', '.join(in_way)}. The files of this part were taken out "
                                      "earlier in this update, and these are not the copies that were kept. Nothing was "
                                      "changed. Move them aside, or `restore` to put everything back.")
                    run_dir(root)
                    back = put_back(root, stamp, item["taken"])
                    print(f"Brought back {len(back)} file(s) from this update's own backup: {', '.join(back)}")
                # The files stay where they are and are recorded against the kit file's new name:
                # nothing is left to offer, and later changes to it still arrive here.
                for f in item["files"]:
                    if f["kit"] in new_files and f["path"] in stamp["files"]:
                        stamp["files"][f["path"]]["kit"] = f["kit"]
                forget_declines(stamp, item["from"], item["kit"])
                print(f"{item['path'] or item['from']} keeps its name. Run `plan` again: what NEST changed in its files "
                      "is listed at the place they have.")
                continue
            stamp["declined"][item["kit"]] = sha(new_files[item["kit"]]) if item["kit"] in new_files else "removed"
    run_dir(root)  # keeps the stamp as it was, so an undo of this update puts these choices back too
    save_stamp(root, stamp)
    if args.command == "done":
        print(f"Noted: {count} change(s) are dealt with.")
    else:
        print(f"Noted: {count} change(s) will not be offered again unless NEST changes them once more.")
    return 0


def forget_declines(stamp: dict, old: str, new: str) -> None:
    """Drop what was declined under either name of a renamed part. An updater from before the
    rename saw it as a dropped part plus a new one, and a "no" to those must not hide what NEST
    changed in the part once the user has chosen what to do with its name."""
    names = {old, new, *former(new)}
    for key in [key for key in stamp["declined"] if any(swap(key, name, name) for name in names)]:
        del stamp["declined"][key]


def move_file(src: Path, dst: Path) -> None:
    """Move one file by renaming it, and in no other way. A move that fails leaves the file
    exactly where it was: there is no copy-then-delete that could stop between its two halves and
    leave the file in both places. Never replaces a file."""
    if os.path.lexists(dst):
        raise FileExistsError(17, "A file is already there", str(dst))
    os.rename(src, dst)


FRONT_NAME = re.compile(rb"^name:[ \t]*(?:\"([^\"\r\n]*)\"|'([^'\r\n]*)'|([^\r\n]*?))(?:[ \t]+#[^\r\n]*|[ \t]*)\r?$", re.MULTILINE)


def set_skill_name(path: Path, old: str, new: str) -> str:
    """Make the `name:` line in a SKILL.md's frontmatter say `new`, when it says `old` now.

    Only the name itself changes: quotes, spacing, a trailing comment and every other byte of the
    file stay as they are. Returns "set" when the file was written, "already" when the line says
    `new`, and "left" when it was left alone: a name of the user's own, an empty or a missing
    `name:`, a file without frontmatter. The command follows the folder name either way."""
    try:
        data = path.read_bytes()
    except OSError:
        return "left"
    head = re.match(rb"\A(?:\xef\xbb\xbf)?---[ \t]*\r?\n(.*?)^---[ \t]*\r?$", data, re.DOTALL | re.MULTILINE)
    found = FRONT_NAME.search(data, head.start(1), head.end(1)) if head else None
    if not found:
        return "left"
    group = next(n for n in (1, 2, 3) if found.group(n) is not None)
    value = found.group(group).decode("utf-8", "replace").strip()
    if value != old:
        return "already" if value == new else "left"
    path.write_bytes(data[:found.start(group)] + new.encode("utf-8") + data[found.end(group):])
    return "set"


def skill_folder_name(ws_rel: str) -> str | None:
    """The folder name of the skill a SKILL.md belongs to, or None for any other file."""
    parts = ws_rel.split("/")
    return parts[2] if len(parts) == 4 and parts[:2] == [".claude", "skills"] and parts[3] == "SKILL.md" else None


def remove_empty_folders(root: Path, ws_rel: str) -> None:
    """Remove the folders under `ws_rel` that hold nothing any more, and `ws_rel` itself when it is empty."""
    base = root / ws_rel
    if not base.is_dir() or base.is_symlink():
        return
    for here, _dirs, _names in os.walk(base, topdown=False):
        if not Path(here).is_symlink():
            try:
                os.rmdir(here)
            except OSError:
                pass  # not empty: something of the user's is still in it
    prune_empty(root, base.parent)


def cmd_rename(root: Path, args) -> int:
    """Move a renamed part to its new name. Every file, the user's own in the folder included, is
    backed up and moved as it is, and its record follows it; in a skill only the `name:` line
    changes, to the new folder name. The stamp is saved after every file, so a run that stops
    halfway (a file another program holds, a crash) is carried on by running the command again."""
    stamp = need_stamp(root)

    def chosen() -> list[dict]:
        """The open rename items the arguments name, each checked: nothing in the way, no link."""
        plan = current_plan(root, stamp)
        todo = [item for item in plan["items"] if item["status"] == "rename"]
        jobs: list[dict] = []
        for raw in args.names:
            wanted = raw.replace("\\", "/").rstrip("/")
            hits = [item for item in todo if wanted in (item["from"], item["kit"], item["path"], item["to"])]
            if not hits:
                raise Problem(f"Nothing open has the old or the new name {raw}; nothing was moved.")
            jobs += [item for item in hits if item not in jobs]
        for item in jobs:
            check(item)
        return jobs

    def check(item: dict) -> None:
        if item["fresh"]:
            raise fresh_problem(item)
        if item["blocked"]:
            way_out = ("Part of this rename was done before; nothing more was moved now. Move those files out of the "
                       "way and run `rename` again, or `restore` to put everything back as it was."
                       if item["half"] else
                       "The files of this part were taken out earlier in this update, and these are not the copies "
                       "that were kept. Nothing was moved. Move them aside, or `restore` to put everything back."
                       if item["taken"] and any(path in item["taken"] for path in item["blocked"]) else
                       f"Nothing was moved. Keeping the old name is `decline {item['from']}`.")
            raise Problem(f"In the way: {', '.join(item['blocked'])}. This rename did not put them there, NEST will not "
                          f"write over a file, and they may be the user's own. {way_out}")
        for src, dst in item["moves"]:
            no_symlink(root, src)
            no_symlink(root, dst)

    jobs = chosen()
    if any(item["taken"] for item in jobs):
        # Taken out earlier in this update: back where they were first, from the update's own
        # copies and with their records, so what follows is the rename of a part that never left.
        run_dir(root)
        for item in jobs:
            back = put_back(root, stamp, item["taken"])
            if back:
                print(f"Brought back {len(back)} file(s) from this update's own backup: {', '.join(back)}")
        jobs = chosen()
    done, at = 0, ""
    current, moved_here = None, 0
    left: list[tuple[str, str]] = []  # the SKILL.md files whose name line was not the old folder name

    def name_line(src: str, dst: str) -> None:
        """A moved SKILL.md gets the new folder name on its `name:` line when it had the old one."""
        if skill_folder_name(src) and skill_folder_name(dst) and \
                set_skill_name(root / dst, skill_folder_name(src), skill_folder_name(dst)) == "left":
            left.append((dst, skill_folder_name(src)))

    try:
        for item in jobs:
            current, moved_here = item, 0
            left.clear()
            run_dir(root)  # the stamp as it was, before the first record changes
            stamp["renaming"] = {**(stamp.get("renaming") if isinstance(stamp.get("renaming"), dict) else {}),
                                 item["from"]: item["kit"]}
            forget_declines(stamp, item["from"], item["kit"])
            save_stamp(root, stamp)  # from here on a second run knows this rename was begun
            records = {f["path"]: f for f in item["files"]}
            for src, dst in item["moves"]:
                at = src
                backup(root, src)
                backup(root, dst)  # noted as new, so an undo takes it away again (or kept, when it is there already)
                if os.path.lexists(root / dst):
                    # The same file in both places (an earlier try that copied it): the copy in the
                    # history is the old one's last version, and the one at the new place stays.
                    if not same_bytes(root / src, root / dst):
                        raise Problem(f"{dst} changed while the rename was running; nothing more was moved. Run "
                                      "`rename` again, or `restore` to put everything back.")
                    (root / src).unlink()
                else:
                    (root / dst).parent.mkdir(parents=True, exist_ok=True)
                    try:
                        move_file(root / src, root / dst)
                    except OSError:
                        prune_empty(root, (root / dst).parent)
                        raise
                if src in records and src in stamp["files"]:
                    stamp["files"][dst] = {**stamp["files"].pop(src), "kit": records[src]["kit"]}
                if src in records:
                    name_line(src, dst)
                save_stamp(root, stamp)
                done += 1
                moved_here += 1
            for f in item["files"]:  # moved by a run that stopped before recording it, or deleted here: the record follows
                if f["path"] in stamp["files"]:
                    stamp["files"][f["to"]] = {**stamp["files"].pop(f["path"]), "kit": f["kit"]}
                if f["change"] == "moved":
                    name_line(f["path"], f["to"])
            for src in item["folders"]:
                remove_empty_folders(root, src)
            with (run_dir(root) / "renamed.txt").open("a", encoding="utf-8", newline="\n") as done_file:
                done_file.write(item["from"] + "\n")  # this update renamed the part itself: nothing of it was "taken out"
            stamp["renaming"].pop(item["from"], None)
            if not stamp["renaming"]:
                del stamp["renaming"]
            save_stamp(root, stamp)
            print(f"Moved {item['path'] or item['from']} to {item['to'] or item['kit']}: {len(item['moves'])} file(s), "
                  "each as it was. Run `plan` again: what NEST changed in them is listed under the new name.")
            if item["links"]:
                print(f"Left in place, because NEST does not move a symbolic link: {', '.join(item['links'])}. "
                      "Move them by hand if the part needs them.")
            for dst, old_name in left:
                print(f"The `name:` line of {dst} was left as it is: it did not say `{old_name}` (a name of the user's "
                      f"own, or none). The command follows the folder name: `/{skill_folder_name(dst)}`.")
    except (OSError, Problem) as exc:
        nothing = bool(current) and not current["half"] and moved_here == 0
        if nothing and isinstance(stamp.get("renaming"), dict):
            # Not one file of this part went anywhere, so it is not half way: the ordinary offer
            # comes back, and the old name can still be kept.
            stamp["renaming"].pop(current["from"], None)
            if not stamp["renaming"]:
                del stamp["renaming"]
            save_stamp(root, stamp)
        if isinstance(exc, Problem):
            raise
        if nothing:
            raise Problem(f"Stopped at {at}: {exc.strerror or exc}. Nothing was moved, so {current['path'] or current['from']} "
                          f"is as it was. Run `rename` again once that is solved, or keep the old name with "
                          f"`decline {current['from']}`.") from exc
        raise Problem(f"Stopped at {at}: {exc.strerror or exc}. That file is still where it was; {done} file(s) before "
                      "it were moved and recorded. Run `rename` again once that is solved: it carries on with what is "
                      "left. `restore` puts everything back.") from exc
    return 0


def cmd_bring_back(root: Path, args) -> int:
    """Put back files that sit in a place of the user's own and were taken out earlier in this
    update (`taken` items): the user's own version, with its record, where it was."""
    stamp = need_stamp(root)
    plan = current_plan(root, stamp)
    todo = [item for item in plan["items"] if item["status"] == "taken"]
    jobs: list[dict] = []
    for raw in args.paths:
        wanted = safe_rel(raw).rstrip("/").lower()
        hits = [item for item in todo if item["path"].lower() == wanted or item["path"].lower().startswith(wanted + "/")]
        if not hits:
            why = taken_place(plan, safe_rel(raw))
            raise Problem(why or f"Nothing taken out earlier in this update is at {raw}; nothing was brought back.")
        jobs += [item for item in hits if item not in jobs]
    in_way = [item["path"] for item in jobs if item["blocked"]]
    if in_way:
        raise Problem(f"In the way: {', '.join(in_way)}. These were taken out earlier in this update, and what is there "
                      "now is not the copy that was kept. Nothing was changed. Move them aside, or `restore` to put "
                      "everything back.")
    run_dir(root)  # the stamp as it is now, before a record comes back
    back = put_back(root, stamp, [item["path"] for item in jobs])
    print(f"Brought back {len(back)} file(s) from this update's own backup, each where it was: {', '.join(back)}. "
          "Run `plan` again: what NEST changed in them is listed there.")
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
        kept = folder / "files" / ws_rel
        if not kept.is_file() and ws_rel in run_paths(folder)[1] and (root / ws_rel).is_file():
            # This update put the file here itself (a rename moved it): its version from before
            # is kept under its old name, and this one goes where an undo puts added files.
            kept = folder / "created" / ws_rel
            kept.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / ws_rel, kept)
        if not kept.is_file():
            raise Problem(f"{ws_rel} could not be kept in the history folder, so it stays where it is.")
        (root / ws_rel).unlink()
        kit_rel = stamp["files"].pop(ws_rel, {}).get("kit")
        stamp["declined"].pop(kit_rel, None)
        print(f"Moved {ws_rel} out; its last version is in {kept.parent.relative_to(root).as_posix()}/")
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
    stamp.pop("renaming", None)  # nothing is open, so no rename is unfinished
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


def brought_back_group(runs: list[Path], folder: Path) -> list[Path]:
    """The parts that go back together with `folder` when it is put back by name, newest first,
    or [] when it can go back alone.

    A part that brought back files an earlier part of the same update had taken out (BROUGHT_BACK)
    cannot go alone: its undo would take those files away again while the earlier part still
    keeps them out, and behind a part that was put back no plan offers them any more. It takes
    its whole update along: the parts around it that began from the same release and were not
    put back. That works for an update that was followed by another one too, where `restore`
    without `--run` no longer reaches."""
    base = run_before(folder)
    if base is None or (folder / "restored").is_file() or not (folder / BROUGHT_BACK).is_file():
        return []
    at = runs.index(folder)

    def along(parts: list[Path]) -> list[Path]:
        taken = []
        for part in parts:
            if (part / "restored").is_file() or run_before(part) != base:
                break
            taken.append(part)
        return taken

    older = along(list(reversed(runs[:at])))
    return [*reversed(along(runs[at + 1:])), folder, *older] if older else []


def cmd_restore(root: Path, args) -> int:
    runs = every = history_runs(root)
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
    together = brought_back_group(every, folder) if args.run else []
    if args.run and not together:
        return restore_part(root, args, folder, runs)
    if together:
        print(f"{folder.name} brought back files that an earlier part of the same update had taken out. Put back "
              "alone, it would take them away again while that part still keeps them out, so the whole update goes "
              f"back: {', '.join(part.name for part in together)}.")
    # One update can be done in parts: `finish` with something left for later closes a part,
    # and the next change starts another. Parts that began from the same release are one update
    # to the user (the version only moves when everything is done), so undo covers them all.
    # The group is written down when an undo begins, so a second `restore` (after a failure, or
    # with --force for files that were left alone) works on the same parts.
    names = [part.name for part in together] or read_json(folder / "group.json").get("parts")
    if isinstance(names, list) and names:
        group = [root / HISTORY_DIR / name for name in names if isinstance(name, str) and (root / HISTORY_DIR / name).is_dir()]
    else:
        group, base = [folder], run_before(folder)
        if not (folder / "restored").is_file():
            for prev in reversed(runs[:-1]):
                if (prev / "restored").is_file() or base is None or run_before(prev) != base:
                    break
                group.append(prev)
    todo = [part for part in group if not (part / "restored").is_file()
            or (args.force and read_json(part / "left.json").get("left"))]
    if not todo:
        older = "" if len(runs) <= len(group) else \
            " An older update is only put back by name: `restore --list` shows them, `restore --run <name>` picks one."
        raise Problem(f"{folder.name} was already put back.{older}")
    if len(group) > 1:
        print(f"The last update was done in {len(group)} parts; undo covers all of them, newest first.")
    if not args.dry_run:
        for part in group:
            write_json(part / "group.json", {"parts": [g.name for g in group]})
    assumed: dict[str, str | None] = {}
    for i, part in enumerate(todo):
        code = restore_part(root, args, part, runs, assumed=assumed, last=i == len(todo) - 1)
        if code:
            return code
    return 0


def run_before(folder: Path) -> str | None:
    """The release the workspace was on when this part of an update began."""
    before = read_json(folder / "nest.json").get("nest")
    return before.get("version") if isinstance(before, dict) else None


def restore_part(root: Path, args, folder: Path, runs: list[Path], assumed: dict | None = None,
                 last: bool = True) -> int:
    """Put back one part of an update. `assumed` carries, in a dry run over several parts, what
    the newer parts would have put back, so an older part is judged against that state."""
    assumed = {} if assumed is None else assumed
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
        current = assumed[ws_rel] if ws_rel in assumed else sha(root / ws_rel)
        return written is not None and not args.force and ws_rel in written and current != written[ws_rel]

    if args.dry_run:
        print(describe_run(root, folder))
        back = [rel for rel in kept if not changed_since(rel)]
        away = [rel for rel in made if (assumed.get(rel, True) is not None and (root / rel).is_file())
                and not changed_since(rel)]
        stay = [rel for rel in [*kept, *made] if changed_since(rel)]
        print(f"Would put back {len(back)} file(s): {', '.join(back) or 'none'}")
        print(f"Would take away {len(away)} file(s) the update added: {', '.join(away) or 'none'}")
        if stay:
            print(f"Would leave alone, because they were changed after the update finished: {', '.join(stay)}")
        for rel in back:
            assumed[rel] = sha(folder / "files" / rel)
        for rel in away:
            assumed[rel] = None
        before = read_json(folder / "nest.json").get("nest") if only is None and last else None
        if isinstance(before, dict):
            now = load_stamp(root)
            if before.get("version") != now.get("version"):
                print(f"Would set the workspace back from NEST {now.get('version')} to NEST {before.get('version')}.")
            undone = len(set(now.get("declined") or {}) - set(before.get("declined") or {}))
            if undone:
                print(f"Would offer {undone} declined change(s) again.")
            if now.get("skipped_version") and now.get("skipped_version") != before.get("skipped_version"):
                print(f"Would mention NEST {now['skipped_version']} at session start again.")
        if last:
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
        if sha(root / ws_rel) is not None and sha(root / ws_rel) == sha(folder / "files" / ws_rel):
            restored.append(ws_rel)  # put back by an earlier try that stopped halfway
            continue
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
            if only is None and not os.path.lexists(root / ws_rel):
                prune_empty(root, (root / ws_rel).parent)  # a folder made for a file that never arrived
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
            for key in ("version", "files", "declined", "skipped_version", "renaming"):
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
    p.add_argument("--light", action="append", metavar="SKILL", help="verdict or blueprint was built in its light size")

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
    p.add_argument("--new", action="extend", nargs="+", metavar="KIT=PATH", help="One pair or several")

    p = sub.add_parser("mark", help="Record that a merged or new adapted file reflects the new kit file")
    p.add_argument("pairs", nargs="+", metavar="PATH=KIT")
    p.add_argument("--kind", choices=("copy", "adapted"))

    p = sub.add_parser("rename", help="Move a part that got another name in NEST to its new name")
    p.add_argument("names", nargs="+", metavar="NAME", help="The old or new kit path, or the old or new place here")

    p = sub.add_parser("decline", help="Do not offer these changes again")
    p.add_argument("kits", nargs="+", metavar="KIT")

    p = sub.add_parser("done", help="A change that was dealt with by hand (a wiki file, a deleted file)")
    p.add_argument("kits", nargs="+", metavar="KIT")

    p = sub.add_parser("bring-back", help="Put back files of a renamed part taken out earlier in this update")
    p.add_argument("paths", nargs="+", metavar="PATH", help="A file of a `taken` item, or its folder")

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
                "apply": cmd_apply, "mark": cmd_mark, "rename": cmd_rename, "decline": cmd_decline, "done": cmd_decline,
                "bring-back": cmd_bring_back, "retire": cmd_retire,
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
