# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Checks that a NEST release is consistent, and prints the notes for one.

  release_check.py                  check the changelog template and the version numbers
  release_check.py --tag v1.2.0     the same, and the newest changelog version must be 1.2.0
  release_check.py --notes 1.2.0    print the GitHub release text for that version

The changelog template (docs/project/releasing.md has the full description):

  | Release | Date | In short |        one row per release, newest first
  ## [Unreleased]
  ---
  ## [1.2.0] - 2026-03-01
  > **In short:** one sentence.
  ### 🏠 For your workspace       plain words; the nest-update skill reads this to users
  ### ✨ Added / 🔧 Changed / 🐛 Fixed / 🗑️ Removed / 🔒 Security     in that order, empty ones left out
  ---
  ## [1.1.0] - ...
  [Unreleased]: .../compare/v1.2.0...HEAD
  [1.2.0]: .../releases/tag/v1.2.0

The version lives in the README badge, the SETUP.md header, the STATE template in SETUP.md and
the newest changelog heading; all four must agree. The setup prompt comes in parts (SETUP.md and
setup/*.md): every part SETUP.md names must exist, every part must be named, and none may be
larger than one read. Exit codes: 0 fine, 1 problems found.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ICONS = {"For your workspace": "🏠", "Added": "✨", "Changed": "🔧", "Fixed": "🐛", "Removed": "🗑️", "Security": "🔒"}
SECTIONS = list(ICONS)
IN_SHORT = re.compile(r"^> \*\*In short:\*\* \S")
HEADING = re.compile(r"^## \[(?P<name>[^\]]+)\](?: - (?P<date>.+?))?\s*$")
VERSION = re.compile(r"^\d+\.\d+\.\d+$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def split_blocks(text: str) -> tuple[list[tuple[str, str | None, list[str], int]], list[str]]:
    """The changelog as (name, date, lines, line number) per `## [...]` block, plus the link lines."""
    blocks, links = [], []
    current = None
    for number, line in enumerate(text.splitlines(), 1):
        m = HEADING.match(line)
        if m:
            current = (m.group("name"), m.group("date"), [], number)
            blocks.append(current)
        elif re.match(r"^\[[^\]]+\]:\s+\S+", line):
            links.append(line)
            current = None
        elif current is not None:
            current[2].append(line)
    return blocks, links


def version_key(name: str) -> tuple[int, ...]:
    return tuple(int(part) for part in name.split("."))


def check_changelog(text: str) -> list[str]:
    problems = []
    for number, line in enumerate(text.splitlines(), 1):
        if line.startswith("## ") and not HEADING.match(line):
            problems.append(f"CHANGELOG.md:{number}: a heading must be `## [Unreleased]` or `## [1.2.3] - YYYY-MM-DD`")
    blocks, links = split_blocks(text)
    if not blocks or blocks[0][0] != "Unreleased":
        return [*problems, "CHANGELOG.md: the first block must be `## [Unreleased]`"]
    versions = blocks[1:]
    if not versions:
        problems.append("CHANGELOG.md: no released version yet")
    names = [name for name, *_ in versions]
    for name, date, lines, number in blocks:
        where = f"CHANGELOG.md:{number} [{name}]"
        body = [line for line in lines if line.strip()]
        is_last = (name, date, lines, number) == blocks[-1]
        if not is_last and (not body or body[-1].strip() != "---"):
            problems.append(f"{where}: the block must end with a `---` divider before the next version")
        if is_last and body and body[-1].strip() == "---":
            problems.append(f"{where}: no divider after the last version")
        content = [line for line in body if line.strip() != "---"]
        raw_heads = [line[4:].strip() for line in content if line.startswith("### ")]
        heads = []
        for raw in raw_heads:
            icon, _, head = raw.partition(" ")
            if ICONS.get(head) != icon:
                wanted = ", ".join(f"`### {i} {n}`" for n, i in ICONS.items())
                problems.append(f"{where}: `### {raw}` is not one of {wanted}")
                head = raw
            heads.append(head)
        known = [head for head in heads if head in SECTIONS]
        if known != sorted(set(known), key=SECTIONS.index):
            problems.append(f"{where}: sections must appear once each, in the order {', '.join(SECTIONS)}")
        for i, line in enumerate(content):
            if line.startswith("### ") and (i + 1 == len(content) or content[i + 1].startswith("### ")):
                problems.append(f"{where}: `{line.strip()}` is empty; leave an empty section out")
        if name == "Unreleased":
            continue
        if not VERSION.match(name):
            problems.append(f"{where}: the version must look like 1.2.3")
            continue
        if not date or not DATE.match(date):
            problems.append(f"{where}: the heading must be `## [{name}] - YYYY-MM-DD`")
        if not any(IN_SHORT.match(line) for line in content):
            problems.append(f"{where}: needs a `> **In short:** ...` line")
        if not heads or heads[0] != "For your workspace":
            problems.append(f"{where}: the first section must be `### 🏠 For your workspace`")
        if not re.search(rf"(?m)^\| \[{re.escape(name)}\]\(#[^)]+\) \| {re.escape(date or '')} \| \S", text):
            problems.append(f"{where}: needs a row `| [{name}](#anchor) | {date} | in short |` in the table at the top")
        if any("—" in line for line in lines):
            problems.append(f"{where}: contains an em dash")
    valid = [name for name in names if VERSION.match(name)]
    if valid != sorted(valid, key=version_key, reverse=True) or len(set(valid)) != len(valid):
        problems.append("CHANGELOG.md: versions must be unique and newest first")
    linked = {re.match(r"^\[([^\]]+)\]", line).group(1): line for line in links}
    for name in ["Unreleased", *valid]:
        if name not in linked:
            problems.append(f"CHANGELOG.md: no link line for [{name}] at the bottom")
    if valid and "Unreleased" in linked and f"v{valid[0]}...HEAD" not in linked["Unreleased"]:
        problems.append(f"CHANGELOG.md: the [Unreleased] link must compare v{valid[0]}...HEAD")
    for name in valid:
        if name in linked and f"v{name}" not in linked[name]:
            problems.append(f"CHANGELOG.md: the [{name}] link must point at tag v{name}")
    return problems


def newest_version(text: str) -> str | None:
    for name, *_ in split_blocks(text)[0]:
        if VERSION.match(name):
            return name
    return None


def check_versions(root: Path, version: str) -> list[str]:
    problems = []
    places = {
        "README.md (badge)": (root / "README.md", r"badge/NEST_v(\d+\.\d+\.\d+)-"),
        "README.md (badge alt text)": (root / "README.md", r'alt="NEST v(\d+\.\d+\.\d+)"'),
        "SETUP.md (header)": (root / "SETUP.md", r"(?m)^Version (\d+\.\d+\.\d+)"),
        "SETUP.md (STATE template)": (root / "SETUP.md", r"(?m)^nest_version: (\d+\.\d+\.\d+)"),
    }
    for label, (path, pattern) in places.items():
        try:
            m = re.search(pattern, path.read_text(encoding="utf-8"))
        except OSError:
            m = None
        if not m:
            problems.append(f"{label}: no version found")
        elif m.group(1) != version:
            problems.append(f"{label}: says {m.group(1)}, the changelog says {version}")
    return problems


# One read of a file by Claude Code stops at about 25,000 tokens; the setup prompt measured about
# 2.8 bytes per token. A part above this size would be read in pieces again, each session.
PART_LIMIT = 45_000


def check_setup_parts(root: Path) -> list[str]:
    """Every part SETUP.md names exists, every file in setup/ is named, and none outgrows one read."""
    problems = []
    try:
        main_text = (root / "SETUP.md").read_text(encoding="utf-8")
    except OSError:
        return ["SETUP.md not found"]
    named = set(re.findall(r"`(setup/[a-z0-9-]+\.md)`", main_text))
    folder = root / "setup"
    present = {f"setup/{p.name}" for p in folder.glob("*.md")} if folder.is_dir() else set()
    for rel in sorted(named - present):
        problems.append(f"SETUP.md names {rel}, which does not exist")
    for rel in sorted(present - named):
        problems.append(f"{rel} is not named in SETUP.md, so no session would read it")
    for rel in ["SETUP.md", *sorted(present)]:
        size = (root / rel).stat().st_size
        if size > PART_LIMIT:
            problems.append(f"{rel} is {size} bytes, over the {PART_LIMIT} that fit in one read: split or shorten it")
    for rel in sorted(present):
        for ref in set(re.findall(r"`(setup/[a-z0-9-]+\.md)`", (root / rel).read_text(encoding="utf-8"))) - present:
            problems.append(f"{rel} names {ref}, which does not exist")
    return problems


def repo_url(text: str) -> str:
    m = re.search(r"(?m)^\[Unreleased\]:\s+(\S+?)/compare/", text)
    return m.group(1) if m else "https://github.com/nickyjacobs/NEST"


def notes(text: str, version: str) -> str | None:
    """The GitHub release text of one version: the banner, the changelog block with a divider
    between its sections, and a closing line that says where to go next."""
    for name, _, lines, _ in split_blocks(text)[0]:
        if name != version:
            continue
        url = repo_url(text)
        out = [f'<p align="center"><img src="{url}/raw/v{version}/assets/release-banner.png" '
               f'alt="NEST: New Environment Setup Toolkit" width="560"></p>', ""]
        body = "\n".join(line for line in lines if line.strip() != "---").strip().splitlines()
        for line in body:
            if line.startswith("### "):
                out += ["---", ""]
            out.append(line)
        out += ["", "---", "", "### 🔄 How to update", "",
                "Already have a workspace? Open it in Claude Code and type:", "", "```", "/nest-update", "```", "",
                "It shows what is new in plain words and changes only what you pick. "
                f"New here? Start with the [quick start]({url}#quick-start).", "", "---", "",
                '<p align="center">',
                f'<a href="{url}/blob/v{version}/CHANGELOG.md">Full changelog</a> &nbsp;·&nbsp; '
                f'<a href="{url}/blob/v{version}/docs/README.md">Docs</a> &nbsp;·&nbsp; '
                f'<a href="{url}/issues">Feedback</a>',
                "</p>", ""]
        return "\n".join(out)
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Check a NEST release, or print the notes for one.")
    ap.add_argument("--root", default=str(ROOT), help="Repository root (default: the folder above tools/)")
    ap.add_argument("--tag", help="The tag being released, for example v1.2.0")
    ap.add_argument("--notes", metavar="VERSION", help="Print the changelog block of this version")
    args = ap.parse_args(argv)
    root = Path(args.root)
    try:
        text = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    except OSError:
        print("CHANGELOG.md not found", file=sys.stderr)
        return 1
    if args.notes:
        body = notes(text, args.notes.removeprefix("v"))
        if body is None:
            print(f"CHANGELOG.md has no block for {args.notes}", file=sys.stderr)
            return 1
        sys.stdout.buffer.write(body.encode("utf-8"))
        return 0
    problems = check_changelog(text)
    problems += check_setup_parts(root)
    version = newest_version(text)
    if version:
        problems += check_versions(root, version)
        if args.tag and args.tag != f"v{version}":
            problems.append(f"The tag is {args.tag}, but the newest changelog version is {version}")
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    print(f"Release check: ok (NEST {version})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
