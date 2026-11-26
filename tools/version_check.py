# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Weekly look at what NEST installs at a fixed version: is there something newer upstream?

NEST pins what it installs, so every new workspace gets a version someone read and tried: the
Claude Code plugins in Appendix C of `setup/catalogue.md` and the Obsidian plugins and theme in
`kit/scripts/obsidian.lock.json`. Pinning means falling behind unless someone looks. This script
looks, and prints a short Markdown report of what moved. It changes nothing: moving a pin stays
a human step (read the change, try it, release it).

Per plugin card in Appendix C:
  - pinned (`owner/repo#tag`): is there a newer release or tag than the one on the card?
  - not pinned (`owner/repo`): commits on the default branch since the card's "Read again on"
  - Anthropic's own (`<name>@claude-plugins-official`): commits to `plugins/<name>` since then.
    These update themselves in a workspace; the report says when their card wants reading again.
Then the Obsidian lock file: `tools/obsidian_lock.py --check` next to this script.

  uv run --script tools/version_check.py            print the report; exit 0
  uv run --script tools/version_check.py --strict   exit 1 when anything moved

Uses GITHUB_TOKEN when it is set (higher API limit). Not part of the kit: it never runs in a
workspace. `.github/workflows/versions.yml` runs it every week and keeps one issue up to date.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOGUE = ROOT / "setup" / "catalogue.md"
OFFICIAL = "anthropics/claude-plugins-official"

CARD_RE = re.compile(
    r"^\*\*(?P<name>[a-z0-9-]+)\*\* · `(?P<id>[^`@]+)@(?P<market>[^`]+)`"
    r"(?:, marketplace `(?P<source>[^`#]+)(?:#(?P<tag>[^`]+))?`)?",
    re.MULTILINE,
)
READ_RE = re.compile(r"Read\s+(?:again\s+)?on\s+(\d{4}-\d{2}-\d{2})")


@dataclass
class Card:
    name: str
    repo: str
    path: str | None      # folder inside the repo, for Anthropic's marketplace
    tag: str | None
    read_on: str | None


def parse_cards(text: str) -> list[Card]:
    """The plugin cards of Appendix C, each with its source, pin and last reading date."""
    start = text.find("## Appendix C")
    if start < 0:
        return []
    body = text[start:]
    matches = list(CARD_RE.finditer(body))
    cards = []
    for i, m in enumerate(matches):
        chunk = body[m.start(): matches[i + 1].start() if i + 1 < len(matches) else len(body)]
        dates = READ_RE.findall(chunk)
        read_on = max(dates) if dates else None
        if m.group("market") == "claude-plugins-official" and not m.group("source"):
            cards.append(Card(m.group("name"), OFFICIAL, f"plugins/{m.group('id')}", None, read_on))
        elif m.group("source"):
            cards.append(Card(m.group("name"), m.group("source"), None, m.group("tag"), read_on))
    return cards


def api(path: str) -> object | None:
    req = urllib.request.Request(f"https://api.github.com/{path}",
                                 headers={"Accept": "application/vnd.github+json",
                                          "User-Agent": "nest-version-check"})
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None


def version_key(tag: str) -> tuple:
    nums = re.findall(r"\d+", tag)
    return tuple(int(n) for n in nums) if nums else (-1,)


def newest_tag(repo: str) -> str | None:
    release = api(f"repos/{repo}/releases/latest")
    tags = api(f"repos/{repo}/tags?per_page=30")
    names = [t.get("name") for t in tags if isinstance(t, dict)] if isinstance(tags, list) else []
    if isinstance(release, dict) and release.get("tag_name"):
        names.append(release["tag_name"])
    names = [n for n in names if isinstance(n, str) and re.search(r"\d", n)]
    return max(names, key=version_key) if names else None


def commits_since(repo: str, since: str, path: str | None) -> list[str]:
    query = f"repos/{repo}/commits?since={since}T23:59:59Z&per_page=20"
    if path:
        query += f"&path={path}"
    data = api(query)
    if not isinstance(data, list):
        return []
    out = []
    for c in data:
        if isinstance(c, dict):
            sha = str(c.get("sha", ""))[:7]
            msg = str((c.get("commit") or {}).get("message", "")).splitlines()[0][:80]
            out.append(f"`{sha}` {msg}")
    return out


def check_card(card: Card) -> str | None:
    """One report line for a card whose source moved, or None."""
    if card.tag:
        latest = newest_tag(card.repo)
        if latest is None:
            return f"- **{card.name}**: could not read the tags of `{card.repo}`."
        if version_key(latest) > version_key(card.tag):
            return (f"- **{card.name}**: `{card.tag}` on the card, `{latest}` upstream "
                    f"(https://github.com/{card.repo}/releases).")
        return None
    if not card.read_on:
        return f"- **{card.name}**: the card has no \"Read again on\" date."
    commits = commits_since(card.repo, card.read_on, card.path)
    if not commits:
        return None
    where = f"`{card.repo}/{card.path}`" if card.path else f"`{card.repo}`"
    shown = "; ".join(commits[:5]) + (" …" if len(commits) > 5 else "")
    return f"- **{card.name}**: {len(commits)} commit(s) to {where} since {card.read_on}: {shown}"


def obsidian_lines() -> list[str]:
    script = ROOT / "tools" / "obsidian_lock.py"
    try:
        out = subprocess.run(["uv", "run", "--quiet", "--script", str(script), "--check"],
                             capture_output=True, text=True, encoding="utf-8", timeout=600)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return [f"- could not run `tools/obsidian_lock.py --check`: {exc}"]
    if out.returncode == 0:
        return []
    lines = [ln.strip() for ln in (out.stdout + out.stderr).splitlines() if ln.strip()]
    return [f"- {ln}" for ln in lines[:20]] or ["- `obsidian_lock.py --check` failed without output."]


def report(obsidian: list[str], card_lines: list[str]) -> str:
    if not card_lines and not obsidian:
        return ""
    parts = ["Something NEST installs at a fixed version moved upstream. Read the change, try it, "
             "and move the pin in a release (`docs/project/releasing.md`, step 4).", ""]
    if card_lines:
        parts += ["### Claude Code plugins (Appendix C)", "", *card_lines, ""]
    if obsidian:
        parts += ["### Obsidian plugins and theme (`kit/scripts/obsidian.lock.json`)", "", *obsidian, ""]
    return "\n".join(parts)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--strict", action="store_true", help="exit 1 when anything moved")
    ap.add_argument("--no-obsidian", action="store_true", help="skip the Obsidian lock check")
    args = ap.parse_args(argv)
    cards = parse_cards(CATALOGUE.read_text(encoding="utf-8"))
    if not cards:
        print("No plugin cards found in Appendix C of setup/catalogue.md.", file=sys.stderr)
        return 2
    card_lines = [line for line in (check_card(c) for c in cards) if line]
    obsidian = [] if args.no_obsidian else obsidian_lines()
    text = report(obsidian, card_lines)
    if text:
        print(text)
    return 1 if (args.strict and text) else 0


if __name__ == "__main__":
    sys.exit(main())
