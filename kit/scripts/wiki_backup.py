# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Back up the wiki (an Obsidian vault) to a private git remote, without a .git folder in it.

The repository lives in a separate git directory (default ~/.<workspace-name>-wiki.git) with the
wiki as its work tree, so the vault stays a plain folder and the workspace repository never
sees the wiki's history. Every git call is `git --git-dir=<dir> --work-tree=<wiki> ...`, with
no shell in between.

Usage:
  wiki_backup.py init <remote-url> [--yes]   create the git directory, set the remote, write the
                                             excludes, show what the first commit will hold, and
                                             commit and push it after confirmation
       --set-remote                          point an existing backup at another remote
       --rebind                              the wiki moved: this git directory now follows it
  wiki_backup.py push ["message"]            add everything, commit ("Backup <date time>" or the
                                             message) when something changed, push only when the
                                             local branch is ahead of the remote
       --allow-empty                         back up a wiki folder that has become empty
  wiki_backup.py status                      uncommitted files and commits not yet pushed
init and push take --no-scan to skip the secret scan (see below).

Safeguards:
  - A git directory belongs to one wiki folder (git records it as core.worktree). init, push and
    status refuse a git directory that belongs to another wiki: two workspaces whose folders
    share a name share the default git directory name. Pass --git-dir (or set git_dir in
    nest.json) to give this wiki its own, or run `init <remote-url> --rebind` after moving a wiki.
  - init never changes the remote of an existing backup unless --set-remote is given.
  - push refuses to commit "every file deleted" (an emptied or wrongly mounted wiki folder)
    unless --allow-empty is given.
  - Before a commit the files in it go through the secret scan when validate.py is installed
    (next to this script, or scripts/validate.py in the workspace). A real credential stops the
    commit; --no-scan skips the scan. Without validate.py there is no scan.
  - A folder inside the wiki with a .git of its own is named and left out: git would store only
    a pointer to it, not its files.
  - git never waits for a password (GIT_TERMINAL_PROMPT=0): sign in once with a credential
    helper or use an SSH remote.

Configuration, both at the workspace root ($CLAUDE_PROJECT_DIR, else the first folder from the
current directory upwards that holds nest.json or wiki.config.json, else the current directory):
  wiki.config.json   `wiki_dir`, relative to the config file's folder (default "wiki"); found as
                     wiki.py finds it: $NEST_WIKI_CONFIG, else the first one from the root upwards
  nest.json          {"wiki_backup": {"git_dir": "~/.<name>-wiki.git", "branch": "main"}}
Command-line --git-dir and --wiki override both.

Excludes go into <git-dir>/info/exclude (outside the vault): Obsidian's per-device workspace
files, caches, the trash folder and OS clutter. A .gitignore inside the wiki is honoured too.
A force push never happens: a rejected push prints the reason and stops.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

DEFAULT_EXCLUDES = """\
# Written by wiki_backup.py. Per-device and generated files stay out of the backup.
.obsidian/workspace.json
.obsidian/workspace-mobile.json
.obsidian/workspaces.json
.obsidian/cache/
.obsidian/plugins/*/data.json.bak
.obsidian/plugins/*/data.json.before-restore
# Plugin and theme code: other people's programs, put back by obsidian_setup.py install.
.obsidian/plugins/*/main.js
.obsidian/plugins/*/manifest.json
.obsidian/plugins/*/styles.css
.obsidian/themes/
.trash/
.DS_Store
Thumbs.db
desktop.ini
*.tmp
~$*
"""


def ensure_excludes(b) -> Path:
    """Write the default excludes once, and add lines a newer version of this script brought.

    Lines the user added or removed by hand stay as they are, except that a default line they
    removed comes back: the file has no way to tell "removed" from "not there yet".
    """
    exclude = b.git_dir / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    current = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
    if "wiki_backup.py" not in current:
        with exclude.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write("\n" + DEFAULT_EXCLUDES)
        return exclude
    have = {line.strip() for line in current.splitlines()}
    missing = [
        line for line in DEFAULT_EXCLUDES.splitlines()
        if line.strip() and not line.startswith("#") and line.strip() not in have
    ]
    if missing:
        with exclude.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(("" if current.endswith("\n") else "\n") + "\n".join(missing) + "\n")
    return exclude


SCAN_BATCH = 200
SCAN_TIMEOUT = 300


def workspace_root() -> Path:
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env and Path(env).is_dir():
        return Path(env)
    here = Path.cwd()
    for d in (here, *here.parents):
        if (d / "nest.json").is_file() or (d / "wiki.config.json").is_file():
            return d
    return here


def git_env() -> dict[str, str]:
    """git never stops to ask for a password: a backup that runs from a session cannot answer."""
    return {**os.environ, "GIT_TERMINAL_PROMPT": "0"}


def read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def find_config(root: Path) -> Path | None:
    """$NEST_WIKI_CONFIG, else the first wiki.config.json from the root upwards (as wiki.py)."""
    env = os.environ.get("NEST_WIKI_CONFIG")
    if env:
        p = Path(env).expanduser()
        return p if p.is_file() else None
    here = root.resolve()
    for d in (here, *here.parents):
        if (d / "wiki.config.json").is_file():
            return d / "wiki.config.json"
    return None


class Backup:
    def __init__(self, git_dir: Path, wiki: Path, branch: str = "main", root: Path | None = None):
        self.git_dir, self.wiki, self.branch = git_dir, wiki, branch
        self.root = root or wiki.parent

    @classmethod
    def from_config(cls, root: Path, git_dir: str | None, wiki: str | None) -> Backup:
        cfg = read_json(root / "nest.json").get("wiki_backup") or {}
        config_path = find_config(root)
        base = config_path.parent if config_path else root
        wiki_dir = wiki or (read_json(config_path).get("wiki_dir") if config_path else None) or "wiki"
        wiki_dir = os.path.expanduser(str(wiki_dir))
        wiki_path = Path(wiki_dir) if Path(wiki_dir).is_absolute() else (Path.cwd() if wiki else base) / wiki_dir
        gd = Path(os.path.expanduser(str(git_dir or cfg.get("git_dir") or f"~/.{root.resolve().name.lower()}-wiki.git")))
        if not gd.is_absolute():  # git runs inside the wiki, where a relative path would point elsewhere
            gd = (Path.cwd() if git_dir else root.absolute()) / gd
        return cls(gd, wiki_path, str(cfg.get("branch") or "main"), root)

    def git(self, *args: str, check: bool = True, timeout: float = 120) -> subprocess.CompletedProcess[str]:
        cmd = ["git", f"--git-dir={self.git_dir}", f"--work-tree={self.wiki}", *args]
        result = subprocess.run(cmd, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                timeout=timeout, cwd=self.wiki if self.wiki.is_dir() else None, env=git_env())
        if check and result.returncode != 0:
            raise GitError(" ".join(args[:2]), (result.stderr or result.stdout).strip())
        return result

    def exists(self) -> bool:
        return (self.git_dir / "HEAD").is_file()

    def has_commits(self) -> bool:
        return self.git("rev-parse", "--verify", "-q", "HEAD", check=False).returncode == 0

    def staged_changes(self) -> bool:
        return self.git("diff", "--cached", "--quiet", check=False).returncode == 1

    def remote_head(self) -> str | None:
        """The remote branch's commit, '' when the remote has no such branch, None when unreachable."""
        r = self.git("ls-remote", "origin", f"refs/heads/{self.branch}", check=False, timeout=60)
        if r.returncode != 0:
            return None
        return r.stdout.split("\t", 1)[0].strip() if r.stdout.strip() else ""

    def pending_files(self) -> list[str]:
        out = self.git("status", "--porcelain", check=False).stdout
        return [line for line in out.splitlines() if line.strip()]

    def ahead(self) -> int | None:
        r = self.git("rev-list", "--count", "@{u}..HEAD", check=False)
        return int(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip().isdigit() else None

    def recorded_tree(self) -> Path | None:
        """The wiki folder this git directory was made for (git writes it at init), if recorded."""
        out = self.git("config", "--get", "core.worktree", check=False).stdout.strip()
        return Path(out) if out else None

    def record_tree(self) -> None:
        self.git("config", "core.worktree", str(self.wiki.resolve()))

    def staged_files(self) -> list[str]:
        out = self.git("diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR").stdout
        return [name for name in out.split("\0") if name]

    def unstage(self) -> None:
        self.git("reset", "-q", check=False)


def same_place(a: Path, b: Path) -> bool:
    try:
        return os.path.samefile(a, b)
    except OSError:
        return os.path.normcase(str(a.resolve())) == os.path.normcase(str(b.resolve()))


def foreign(b: Backup) -> str | None:
    """Why this git directory must not be used for this wiki, or None when it is this wiki's own.
    A git directory without a recorded folder (made by hand) is taken as this wiki's."""
    tree = b.recorded_tree()
    if tree is None or same_place(tree, b.wiki):
        return None
    return (f"{b.git_dir} belongs to another wiki: {tree}\n"
            f"This wiki is {b.wiki}. Nothing was changed.\n"
            "Two workspaces whose folders share a name share the default git directory name. Give this "
            "wiki its own: pass --git-dir <path>, or set wiki_backup.git_dir in nest.json.\n"
            "If this is the same wiki and it moved here, run `wiki_backup.py init <remote-url> --rebind`.")


def nested_repositories(wiki: Path) -> list[str]:
    """Folders inside the wiki that are git repositories themselves. git stores only a pointer to
    such a folder, so its files are not in the backup."""
    found = []
    for root, dirs, files in os.walk(wiki):
        here = Path(root)
        if here != wiki and (".git" in dirs or ".git" in files):
            found.append(here.relative_to(wiki).as_posix())
            dirs[:] = []
            continue
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
    return found


def warn_nested(b: Backup, stream=None) -> list[str]:
    """Name the nested repositories and return them, so `git add` can leave them out."""
    nested = nested_repositories(b.wiki)
    for rel in nested:
        print(f"Warning: {rel}/ is a git repository of its own, so its files are not in the backup (git would "
              "keep only a pointer to it). Back it up through its own remote, or remove its .git folder.",
              file=stream or sys.stderr)
    return nested


def add_all(b: Backup, nested: list[str], *flags: str) -> subprocess.CompletedProcess[str]:
    """`git add -A` without the nested repositories: one without a commit makes a plain add fail."""
    return b.git("add", "-A", *flags, "--", ".", *(f":(exclude,top,literal){rel}" for rel in nested))


def find_scanner(root: Path) -> Path | None:
    """validate.py next to this script, else scripts/validate.py in the workspace; None: no scan."""
    for candidate in (Path(__file__).resolve().with_name("validate.py"), root / "scripts" / "validate.py"):
        if candidate.is_file():
            return candidate
    return None


def secrets_in(b: Backup, files: list[str]) -> str | None:
    """The secret scan's report on the files about to be committed, or None when they are clean
    (or when there is no scanner, or it could not run: the scan is a help, not a gate on its own)."""
    scanner = find_scanner(b.root)
    if scanner is None or not files:
        return None
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(b.root), "PYTHONIOENCODING": "utf-8"}
    report: list[str] = []
    for i in range(0, len(files), SCAN_BATCH):
        paths = [str(b.wiki / name) for name in files[i:i + SCAN_BATCH]]
        try:
            r = subprocess.run([sys.executable, str(scanner), "--file", *paths], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=SCAN_TIMEOUT, cwd=b.root, env=env,
                               check=False)
        except (OSError, subprocess.TimeoutExpired) as e:
            print(f"Warning: the secret scan could not run ({e}); continuing without it.", file=sys.stderr)
            return None
        if r.returncode != 2:
            continue
        keep = False
        for line in r.stderr.splitlines():  # only the blocking findings, not the soft warnings
            if line.startswith("[secret-scan]"):
                keep = "Secrets (blocked)" in line
            if keep and line.startswith(("[secret-scan]", "  ")):
                report.append(line)
    return "\n".join(report) if report else None


def scan_or_stop(b: Backup, no_scan: bool) -> bool:
    """True when the commit may go ahead."""
    if no_scan:
        return True
    report = secrets_in(b, b.staged_files())
    if report is None:
        return True
    b.unstage()
    print("The secret scan found what looks like a real credential in the files to back up; nothing was "
          f"committed or pushed.\n{report}\n"
          "Replace the value with a placeholder (the secret itself belongs in a password manager), or run "
          "again with --no-scan when it is a false alarm.", file=sys.stderr)
    return False


class GitError(RuntimeError):
    def __init__(self, what: str, detail: str):
        super().__init__(f"git {what} failed: {detail}")


def identity_missing(b: Backup) -> bool:
    name = b.git("config", "user.name", check=False).stdout.strip()
    email = b.git("config", "user.email", check=False).stdout.strip()
    return not (name and email)


def no_wiki(b: Backup) -> bool:
    if b.wiki.is_dir():
        return False
    print(f"No wiki folder at {b.wiki}.", file=sys.stderr)
    return True


def cmd_init(b: Backup, remote: str, yes: bool, set_remote: bool = False, rebind: bool = False,
             no_scan: bool = False) -> int:
    if no_wiki(b):
        return 1
    if (b.wiki / ".git").exists():
        print(f"{b.wiki} already has a .git folder of its own; this backup keeps its git directory outside "
              "the vault. Remove or move that .git first, or back it up with plain git.", file=sys.stderr)
        return 1
    if not b.exists():
        b.git_dir.parent.mkdir(parents=True, exist_ok=True)
        if b.git("init", "-q", "-b", b.branch, check=False).returncode != 0:  # git before 2.28 has no -b
            b.git("init", "-q")
            b.git("symbolic-ref", "HEAD", f"refs/heads/{b.branch}")
        print(f"Created {b.git_dir} (work tree {b.wiki}).")
    else:
        problem = None if rebind else foreign(b)
        if problem:
            print(problem, file=sys.stderr)
            return 1
        current = b.git("remote", "get-url", "origin", check=False)
        if current.returncode == 0 and current.stdout.strip() != remote and not set_remote:
            print(f"{b.git_dir} already backs up to {current.stdout.strip()}; the remote was not changed. "
                  "Run init again with --set-remote to point this backup at another remote.", file=sys.stderr)
            return 1
        print(f"{b.git_dir} already exists; updating its settings.")
    b.record_tree()
    b.git("config", "core.autocrlf", "false")
    b.git("config", "core.quotepath", "false")
    if b.git("remote", "get-url", "origin", check=False).returncode == 0:
        b.git("remote", "set-url", "origin", remote)
    else:
        b.git("remote", "add", "origin", remote)
    exclude = ensure_excludes(b)
    if b.has_commits():
        print("The backup already has commits; run `push` to back up new changes.")
        return 0

    nested = warn_nested(b)
    listing = add_all(b, nested, "--dry-run").stdout.splitlines()
    files = [line.removeprefix("add ").strip("'") for line in listing if line.startswith("add ")]
    print(f"The first commit will add {len(files)} file{'s' if len(files) != 1 else ''} to {remote}:")
    for f in files[:200]:
        print(f"  {f}")
    if len(files) > 200:
        print(f"  ... and {len(files) - 200} more")
    if not files:
        print("Nothing to commit yet.")
        return 0
    if not yes:
        try:
            answer = input("Commit and push these files? [y/N] ").strip().lower()
        except EOFError:
            answer = ""
        if answer not in ("y", "yes"):
            print("Stopped before the first commit. Adjust the excludes in "
                  f"{exclude} and run init again, or run it with --yes.")
            return 1
    if identity_missing(b):
        print("git has no user.name / user.email; set them with `git config --global user.name ...` first.",
              file=sys.stderr)
        return 1
    add_all(b, nested)
    if not scan_or_stop(b, no_scan):
        return 1
    b.git("commit", "-q", "-m", "Initial wiki backup")
    return push_if_ahead(b)


def push_failure(detail: str) -> str:
    """What to tell the user when a push fails; only a real rejection points at another device."""
    if any(mark in detail for mark in ("[rejected]", "non-fast-forward", "fetch first")):
        return ("Push rejected; nothing was forced. The remote has commits this machine lacks "
                "(another device backed up). Pull those first:\n{pull}\n" + f"git said: {detail}")
    return ("Push failed; nothing was forced and the commit stays local. Fix what git reports, then run "
            f"push again.\ngit said: {detail}")


def push_if_ahead(b: Backup) -> int:
    local = b.git("rev-parse", "HEAD").stdout.strip()
    remote = b.remote_head()
    if remote is None:
        print("The remote is unreachable (offline, no access, or git needs a sign-in it could not ask for here); "
              "the commit stays local until the next push.", file=sys.stderr)
        return 1
    if remote == local:
        print("Nothing to push; the remote is up to date.")
        return 0
    r = b.git("push", "-q", "-u", "origin", b.branch, check=False, timeout=300)
    if r.returncode != 0:
        pull = f'  git --git-dir="{b.git_dir}" --work-tree="{b.wiki}" pull --rebase origin {b.branch}'
        print(push_failure((r.stderr or r.stdout).strip()).replace("{pull}", pull), file=sys.stderr)
        return 1
    print(f"Pushed to {b.git('remote', 'get-url', 'origin').stdout.strip()}.")
    return 0


def cmd_push(b: Backup, message: str | None, allow_empty: bool = False, no_scan: bool = False) -> int:
    if not b.exists():
        print(f"No backup at {b.git_dir}; run `wiki_backup.py init <remote-url>` first.", file=sys.stderr)
        return 1
    if no_wiki(b):
        return 1
    problem = foreign(b)
    if problem:
        print(problem, file=sys.stderr)
        return 1
    if b.recorded_tree() is None:
        b.record_tree()
    ensure_excludes(b)
    add_all(b, warn_nested(b))
    if b.staged_changes():
        if (not allow_empty and b.has_commits() and not b.git("ls-files").stdout.strip()
                and b.git("ls-tree", "-r", "--name-only", "HEAD").stdout.strip()):
            b.unstage()
            print(f"{b.wiki} holds no files, while the backup does: this commit would record every page as "
                  "deleted. Nothing was committed. Check that the wiki folder is the right one (a drive that "
                  "is not mounted, a moved folder); run push --allow-empty when the wiki really is empty now.",
                  file=sys.stderr)
            return 1
        if identity_missing(b):
            print("git has no user.name / user.email; set them first.", file=sys.stderr)
            return 1
        if not scan_or_stop(b, no_scan):
            return 1
        msg = message or f"Backup {datetime.now():%Y-%m-%d %H:%M}"
        b.git("commit", "-q", "-m", msg)
        print(f"Committed: {msg}")
    if not b.has_commits():
        print("Nothing to back up yet.")
        return 0
    return push_if_ahead(b)


def cmd_status(b: Backup) -> int:
    if not b.exists():
        print(f"No backup at {b.git_dir}.")
        return 1
    if no_wiki(b):
        return 1
    problem = foreign(b)
    if problem:
        print(problem, file=sys.stderr)
        return 1
    files = b.pending_files()
    ahead = b.ahead() if b.has_commits() else None
    print(f"Wiki backup {b.git_dir} -> {b.git('remote', 'get-url', 'origin', check=False).stdout.strip() or 'no remote'}")
    print(f"  {len(files)} uncommitted file{'s' if len(files) != 1 else ''}")
    for line in files[:20]:
        print(f"    {line}")
    if ahead is not None:
        print(f"  {ahead} commit{'s' if ahead != 1 else ''} not pushed")
    elif b.has_commits():
        print("  no upstream yet: the next push sets it")
    warn_nested(b, sys.stdout)
    return 0


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Back up the wiki through a separate git directory.")
    ap.add_argument("--git-dir", help="The backup's git directory (default from nest.json)")
    ap.add_argument("--wiki", help="The wiki folder (default from wiki.config.json)")
    sub = ap.add_subparsers(dest="command", required=True)
    p_init = sub.add_parser("init", help="Create the backup and make the first commit")
    p_init.add_argument("remote", help="The private remote URL")
    p_init.add_argument("--yes", action="store_true", help="Skip the confirmation before the first commit")
    p_init.add_argument("--set-remote", action="store_true", help="Point an existing backup at another remote")
    p_init.add_argument("--rebind", action="store_true",
                        help="The wiki moved: let this git directory follow it to the new folder")
    p_push = sub.add_parser("push", help="Commit changes and push when ahead")
    p_push.add_argument("message", nargs="?", help="Commit message (default: Backup <date time>)")
    p_push.add_argument("--allow-empty", action="store_true", help="Back up a wiki folder that has become empty")
    for p in (p_init, p_push):
        p.add_argument("--no-scan", action="store_true", help="Skip the secret scan before the commit")
    sub.add_parser("status", help="Show what is not backed up yet")
    args = ap.parse_args(argv)

    b = Backup.from_config(workspace_root(), args.git_dir, args.wiki)
    try:
        if args.command == "init":
            return cmd_init(b, args.remote, args.yes, args.set_remote, args.rebind, args.no_scan)
        if args.command == "push":
            return cmd_push(b, args.message, args.allow_empty, args.no_scan)
        return cmd_status(b)
    except GitError as e:
        print(str(e), file=sys.stderr)
        return 1
    except subprocess.TimeoutExpired as e:
        print(f"wiki backup failed: git took longer than {e.timeout:.0f} seconds and was stopped. If the next run "
              f"reports a lock, remove {b.git_dir / 'index.lock'} first.", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"wiki backup failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
