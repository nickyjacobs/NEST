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
  wiki_backup.py push ["message"]            add everything, commit ("Backup <date time>" or the
                                             message) when something changed, push only when the
                                             local branch is ahead of the remote
  wiki_backup.py status                      uncommitted files and commits not yet pushed

Configuration, both at the workspace root ($CLAUDE_PROJECT_DIR or the current directory):
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
.trash/
.DS_Store
Thumbs.db
desktop.ini
*.tmp
~$*
"""


def workspace_root() -> Path:
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    return Path(env) if env and Path(env).is_dir() else Path.cwd()


def read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
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
    def __init__(self, git_dir: Path, wiki: Path, branch: str = "main"):
        self.git_dir, self.wiki, self.branch = git_dir, wiki, branch

    @classmethod
    def from_config(cls, root: Path, git_dir: str | None, wiki: str | None) -> Backup:
        cfg = read_json(root / "nest.json").get("wiki_backup") or {}
        config_path = find_config(root)
        base = config_path.parent if config_path else root
        wiki_dir = wiki or (read_json(config_path).get("wiki_dir") if config_path else None) or "wiki"
        wiki_path = Path(wiki_dir) if Path(wiki_dir).is_absolute() else (Path.cwd() if wiki else base) / wiki_dir
        gd = Path(os.path.expanduser(str(git_dir or cfg.get("git_dir") or f"~/.{root.resolve().name.lower()}-wiki.git")))
        if not gd.is_absolute():  # git runs inside the wiki, where a relative path would point elsewhere
            gd = (Path.cwd() if git_dir else root.absolute()) / gd
        return cls(gd, wiki_path, str(cfg.get("branch") or "main"))

    def git(self, *args: str, check: bool = True, timeout: float = 120) -> subprocess.CompletedProcess[str]:
        cmd = ["git", f"--git-dir={self.git_dir}", f"--work-tree={self.wiki}", *args]
        result = subprocess.run(cmd, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                timeout=timeout, cwd=self.wiki if self.wiki.is_dir() else None)
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


class GitError(RuntimeError):
    def __init__(self, what: str, detail: str):
        super().__init__(f"git {what} failed: {detail}")


def identity_missing(b: Backup) -> bool:
    name = b.git("config", "user.name", check=False).stdout.strip()
    email = b.git("config", "user.email", check=False).stdout.strip()
    return not (name and email)


def cmd_init(b: Backup, remote: str, yes: bool) -> int:
    if not b.wiki.is_dir():
        print(f"No wiki folder at {b.wiki}.", file=sys.stderr)
        return 1
    if (b.wiki / ".git").exists():
        print(f"{b.wiki} already has a .git folder of its own; this backup keeps its git directory outside "
              "the vault. Remove or move that .git first, or back it up with plain git.", file=sys.stderr)
        return 1
    if not b.exists():
        b.git_dir.parent.mkdir(parents=True, exist_ok=True)
        b.git("init", "-q", "-b", b.branch)
        print(f"Created {b.git_dir} (work tree {b.wiki}).")
    else:
        print(f"{b.git_dir} already exists; updating its settings.")
    b.git("config", "core.autocrlf", "false")
    b.git("config", "core.quotepath", "false")
    if b.git("remote", "get-url", "origin", check=False).returncode == 0:
        b.git("remote", "set-url", "origin", remote)
    else:
        b.git("remote", "add", "origin", remote)
    exclude = b.git_dir / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    if "wiki_backup.py" not in (exclude.read_text(encoding="utf-8") if exclude.exists() else ""):
        with exclude.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write("\n" + DEFAULT_EXCLUDES)
    if b.has_commits():
        print("The backup already has commits; run `push` to back up new changes.")
        return 0

    listing = b.git("add", "-A", "--dry-run").stdout.splitlines()
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
    b.git("add", "-A")
    b.git("commit", "-q", "-m", "Initial wiki backup")
    return push_if_ahead(b)


def push_if_ahead(b: Backup) -> int:
    local = b.git("rev-parse", "HEAD").stdout.strip()
    remote = b.remote_head()
    if remote is None:
        print("The remote is unreachable (offline, or no access); the commit stays local until the next push.",
              file=sys.stderr)
        return 1
    if remote == local:
        print("Nothing to push; the remote is up to date.")
        return 0
    r = b.git("push", "-q", "-u", "origin", b.branch, check=False, timeout=300)
    if r.returncode != 0:
        print("Push rejected; nothing was forced. The remote probably has commits this machine lacks "
              "(another device backed up). Pull those first:\n"
              f"  git --git-dir={b.git_dir} --work-tree={b.wiki} pull --rebase origin {b.branch}\n"
              f"git said: {(r.stderr or r.stdout).strip()}", file=sys.stderr)
        return 1
    print(f"Pushed to {b.git('remote', 'get-url', 'origin').stdout.strip()}.")
    return 0


def cmd_push(b: Backup, message: str | None) -> int:
    if not b.exists():
        print(f"No backup at {b.git_dir}; run `wiki_backup.py init <remote-url>` first.", file=sys.stderr)
        return 1
    b.git("add", "-A")
    if b.staged_changes():
        if identity_missing(b):
            print("git has no user.name / user.email; set them first.", file=sys.stderr)
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
    p_push = sub.add_parser("push", help="Commit changes and push when ahead")
    p_push.add_argument("message", nargs="?", help="Commit message (default: Backup <date time>)")
    sub.add_parser("status", help="Show what is not backed up yet")
    args = ap.parse_args(argv)

    b = Backup.from_config(workspace_root(), args.git_dir, args.wiki)
    try:
        if args.command == "init":
            return cmd_init(b, args.remote, args.yes)
        if args.command == "push":
            return cmd_push(b, args.message)
        return cmd_status(b)
    except GitError as e:
        print(str(e), file=sys.stderr)
        return 1
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"wiki backup failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
