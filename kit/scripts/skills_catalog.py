# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6"]
# ///
"""The skills catalogue: one generated table of the workspace's skills and agents, and checks on
their frontmatter.

Usage:
  skills_catalog.py            rewrite the block between <!-- AUTO-CATALOG --> and
                               <!-- /AUTO-CATALOG --> in docs/skills.md (created when missing)
  skills_catalog.py --check    check every skill and agent file, and that the catalogue is
                               current; exit 1 with one line per problem
  skills_catalog.py --check --installed
                               the same, for a workspace the setup has finished: also fail on a
                               marker the setup should have resolved (`customise:`, `<fill in:`)
                               in any file of a skill folder or in an agent file
  skills_catalog.py --root P   work on another workspace than $CLAUDE_PROJECT_DIR / the cwd
Exit codes: 0 fine, 1 problems found, 2 the root folder does not exist.

Sources: .claude/skills/<name>/SKILL.md and .claude/agents/<name>.md. The catalogue shows name,
description, metadata.does (one sentence; falls back to the description's first sentence) and
metadata.try (a list of ways to start the skill).

The checks:
  - frontmatter between --- lines that parses as a YAML map
  - a description; description plus when_to_use at most 1,536 characters (Claude Code cuts the
    skill listing there)
  - only fields Claude Code documents for that file type, plus `metadata` (field lists taken from
    code.claude.com/docs/en/skills and /sub-agents on 2026-11-21)
  - skill names: lowercase letters, digits and hyphens, at most 64 characters, equal to the
    folder name when set; agent names required
  - metadata is a map; metadata.try, when present, a non-empty list
  - no em dash anywhere in the file (the writing rules want a comma, a colon or two sentences)
A skill folder with a NOTICE.md was taken over from someone else as is: only its description is
checked, its frontmatter stays theirs, and its text is not searched for markers.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import yaml

BEGIN, END = "<!-- AUTO-CATALOG -->", "<!-- /AUTO-CATALOG -->"
CATALOG = Path("docs/skills.md")
SKILLS_DIR = Path(".claude/skills")
AGENTS_DIR = Path(".claude/agents")
EM_DASH = "\u2014"
LISTING_CAP = 1536
SKILL_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

SKILL_FIELDS = {
    "name", "description", "when_to_use", "argument-hint", "arguments", "disable-model-invocation",
    "user-invocable", "allowed-tools", "disallowed-tools", "model", "effort", "context", "agent",
    "background", "hooks", "paths", "shell", "license", "compatibility", "metadata",
}
AGENT_FIELDS = {
    "name", "description", "tools", "disallowedTools", "model", "permissionMode", "maxTurns",
    "autoCompactWindow", "skills", "mcpServers", "hooks", "memory", "background", "omitClaudeMd",
    "effort", "isolation", "color", "initialPrompt", "experimental", "metadata",
}

NEW_CATALOG = f"""# Skills and agents

Generated from the frontmatter by `scripts/skills_catalog.py`; edit the skill files, not this table.

{BEGIN}
{END}
"""


def parse_frontmatter(text: str) -> dict | None:
    """The YAML map between the opening and closing --- lines, or None."""
    text = text.lstrip("\ufeff").replace("\r\n", "\n")
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    try:
        data = yaml.safe_load(text[4:end])
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


def read(path: Path) -> tuple[str, dict]:
    text = path.read_text(encoding="utf-8")
    return text, parse_frontmatter(text) or {}


def is_external(skill_file: Path) -> bool:
    return (skill_file.parent / "NOTICE.md").exists()


def check_skill(path: Path) -> list[str]:
    name = path.parent.name
    text = path.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    problems: list[str] = []
    if fm is None:
        return ["needs frontmatter between --- lines that parses as a YAML map"]
    description = str(fm.get("description") or "").strip()
    if not description:
        problems.append("has no description")
    if len(description) + len(str(fm.get("when_to_use") or "")) > LISTING_CAP:
        problems.append(f"description plus when_to_use is over {LISTING_CAP} characters")
    if is_external(path):
        return problems
    if not SKILL_NAME.match(name) or len(name) > 64:
        problems.append("folder name must be lowercase words with hyphens, at most 64 characters")
    if "name" in fm and fm["name"] != name:
        problems.append(f"name in the frontmatter must equal the folder name ({name})")
    problems += common_checks(fm, text, SKILL_FIELDS)
    return problems


def check_agent(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    if fm is None:
        return ["needs frontmatter between --- lines that parses as a YAML map"]
    problems: list[str] = []
    if not str(fm.get("name") or "").strip():
        problems.append("has no name (required for agents)")
    if not str(fm.get("description") or "").strip():
        problems.append("has no description")
    problems += common_checks(fm, text, AGENT_FIELDS)
    return problems


def common_checks(fm: dict, text: str, allowed: set[str]) -> list[str]:
    problems: list[str] = []
    unknown = sorted(set(fm) - allowed)
    if unknown:
        problems.append(f"fields Claude Code does not know: {', '.join(unknown)} (custom data goes under metadata)")
    meta = fm.get("metadata")
    if meta is not None and not isinstance(meta, dict):
        problems.append("metadata must be a map")
    elif isinstance(meta, dict) and "try" in meta and not (isinstance(meta["try"], list) and meta["try"]):
        problems.append("metadata.try must be a non-empty list")
    if EM_DASH in text:
        line = next(i for i, ln in enumerate(text.splitlines(), 1) if EM_DASH in ln)
        problems.append(f"em dash on line {line}; use a comma, a colon or two sentences")
    return problems


def first_sentence(text: str) -> str:
    """Up to the first full stop that ends a sentence: the next word does not start in lower case,
    so "e.g. this" and "v1.2" do not cut it short."""
    text = " ".join(str(text).split())
    for m in re.finditer(r"[.!?](?:\s+|$)", text):
        nxt = text[m.end():m.end() + 1]
        if not nxt or not nxt.islower():
            return text[:m.start() + 1].rstrip(".")
    return text.rstrip(".")


def cell(text: object) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ").strip()


def skill_rows(root: Path) -> list[str]:
    rows = []
    for path in sorted((root / SKILLS_DIR).glob("*/SKILL.md")):
        _, fm = read(path)
        meta = fm.get("metadata") if isinstance(fm.get("metadata"), dict) else {}
        name = str(fm.get("name") or path.parent.name)
        hint = f" {fm['argument-hint']}" if fm.get("argument-hint") else ""
        if fm.get("user-invocable") is False:
            call = "Claude only"
        elif fm.get("disable-model-invocation"):
            call = f"only `/{name}{hint}`"
        else:
            call = f"`/{name}{hint}` or on its own"
        does = meta.get("does") or first_sentence(fm.get("description") or "")
        tries = meta.get("try") if isinstance(meta.get("try"), list) else []
        rows.append(f"| `{name}` | {cell(call)} | {cell(does)} | {cell('; '.join(map(str, tries)))} |")
    return rows


def agent_rows(root: Path) -> list[str]:
    rows = []
    for path in sorted((root / AGENTS_DIR).glob("*.md")):
        _, fm = read(path)
        meta = fm.get("metadata") if isinstance(fm.get("metadata"), dict) else {}
        tools = fm.get("tools") or "all"
        tools = ", ".join(map(str, tools)) if isinstance(tools, list) else tools
        does = meta.get("does") or first_sentence(fm.get("description") or "")
        rows.append(f"| `{fm.get('name') or path.stem}` | {cell(fm.get('model') or 'inherit')} | {cell(tools)} | {cell(does)} |")
    return rows


def render(root: Path) -> str:
    skills, agents = skill_rows(root), agent_rows(root)
    lines = [BEGIN, "", f"### Skills ({len(skills)}, `.claude/skills/`)", ""]
    lines += ["| Skill | Call | Does | Try |", "|---|---|---|---|", *skills] if skills else ["No skills yet."]
    lines += ["", f"### Agents ({len(agents)}, `.claude/agents/`)", ""]
    lines += ["| Agent | Model | Tools | Does |", "|---|---|---|---|", *agents] if agents else ["No agents yet."]
    lines += ["", END]
    return "\n".join(lines)


def current_block(text: str) -> str | None:
    m = re.search(re.escape(BEGIN) + r".*?" + re.escape(END), text, re.DOTALL)
    return m.group(0) if m else None


def write(root: Path) -> str:
    path = root / CATALOG
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(NEW_CATALOG, encoding="utf-8", newline="\n")
    text = path.read_text(encoding="utf-8")
    block = current_block(text)
    if block is None:
        raise SystemExit(f"{CATALOG.as_posix()} has no {BEGIN} ... {END} markers; add them where the table goes.")
    path.write_text(text.replace(block, render(root)), encoding="utf-8", newline="\n")
    return f"catalog: {CATALOG.as_posix()} updated"


MARKERS = ("customise:", "<fill in:")
TEXT_SUFFIXES = {".md", ".txt", ".json", ".yaml", ".yml", ".py", ".sh", ".js", ".toml"}


def leftover_markers(root: Path) -> list[str]:
    """Markers the setup resolves while it installs a skill or an agent, still present in a
    workspace. Reference files (the kit) carry them on purpose, so this runs only on request."""
    files: list[Path] = []
    for skill_file in sorted((root / SKILLS_DIR).glob("*/SKILL.md")):
        if not is_external(skill_file):
            files += sorted(p for p in skill_file.parent.rglob("*") if p.is_file() and p.suffix in TEXT_SUFFIXES)
    files += sorted((root / AGENTS_DIR).glob("*.md"))
    problems = []
    for path in files:
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for n, line in enumerate(lines, 1):
            for marker in MARKERS:
                if marker in line:
                    problems.append(f"{path.relative_to(root).as_posix()}:{n}: leftover marker '{marker}'; "
                                    "resolve it and remove the marker")
    return problems


def check(root: Path, installed: bool = False) -> list[str]:
    problems = []
    for path in sorted((root / SKILLS_DIR).glob("*/SKILL.md")):
        problems += [f"{path.relative_to(root).as_posix()}: {p}" for p in check_skill(path)]
    for path in sorted((root / AGENTS_DIR).glob("*.md")):
        problems += [f"{path.relative_to(root).as_posix()}: {p}" for p in check_agent(path)]
    catalog = root / CATALOG
    if catalog.exists():
        block = current_block(catalog.read_text(encoding="utf-8"))
        if block is None:
            problems.append(f"{CATALOG.as_posix()}: no {BEGIN} markers")
        elif block != render(root):
            problems.append(f"{CATALOG.as_posix()}: stale, run scripts/skills_catalog.py")
    if installed:
        problems += leftover_markers(root)
    return problems


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Generate and check the skills catalogue.")
    ap.add_argument("--check", action="store_true", help="Check the frontmatter and that the catalogue is current")
    ap.add_argument("--installed", action="store_true",
                    help="With --check, in a built workspace: also fail on a leftover customise: or <fill in: marker")
    ap.add_argument("--root", help="Workspace root (default: $CLAUDE_PROJECT_DIR or the current directory)")
    args = ap.parse_args(argv)
    root = Path(args.root or os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd())
    if not root.is_dir():
        print(f"skills: no such folder: {root}", file=sys.stderr)
        return 2
    if args.check or args.installed:
        problems = check(root, args.installed)
        for p in problems:
            print(p)
        print("skills: ok" if not problems else f"skills: {len(problems)} problem{'s' if len(problems) != 1 else ''}")
        return 1 if problems else 0
    print(write(root))
    return 0


if __name__ == "__main__":
    sys.exit(main())
