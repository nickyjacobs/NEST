# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Advisory writing-style check against a word list, in any language.

Usage:
  check_style.py <file>...        report hits with line numbers; exit 0 (advisory)
  check_style.py --strict <file>  exit 1 when there is a hit (for CI), 2 when the check could not
                                  run (no word list, a file that cannot be read)
  check_style.py --text "<text>"  check a piece of text without writing a file
  check_style.py -                read the text from stdin (also: echo ... | check_style.py -)
  check_style.py --hook           PostToolUse hook: checks the written file when it matches the
                                  [paths] of the word list; hits go back to Claude through exit 2
  --words <path>                  another word list than .claude/style-words.txt

The word list (.claude/style-words.txt at the workspace root) has sections; # starts a comment:

  [banned]          words or phrases that should not appear at all
  [connectors]      linking words that are fine once but tiresome when repeated: flagged when a
                    file uses one of them connector_max times or more
  [openers]         phrases a line or sentence should not start with
  [paths]           globs of the files the hook checks (default **/*.md); a line starting with
                    ! excludes, e.g. !archive/**
  [options]         connector_max = 3     em_dash = true     spaced_hyphen = true

Entries match case-insensitively on word boundaries. A trailing * matches any word ending
("streamlin*" catches "streamlined" and "streamlining"). In scripts written without spaces
(Chinese, Japanese, Korean, Thai, Lao, Khmer, Burmese) an entry matches anywhere. A plain
apostrophe in an entry also matches a typographic one. Only the five section names above are
sections: any other line in brackets, such as [sic], is an entry. Frontmatter, fenced code blocks
(also inside > callouts) and `inline code` are skipped.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

WORDS_FILE = Path(".claude/style-words.txt")
EM_DASH = "\u2014"
SECTIONS = ("banned", "connectors", "openers", "paths", "options")


@dataclass
class WordList:
    banned: list[str] = field(default_factory=list)
    connectors: list[str] = field(default_factory=list)
    openers: list[str] = field(default_factory=list)
    include: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    connector_max: int = 3
    em_dash: bool = True
    spaced_hyphen: bool = True


def parse_words(text: str) -> WordList:
    wl = WordList()
    section = ""
    for raw in text.splitlines():
        line = raw.split(" #", 1)[0].strip() if not raw.lstrip().startswith("#") else ""
        if not line:
            continue
        m = re.fullmatch(r"\[([a-z_]+)\]", line.lower())
        if m and m.group(1) in SECTIONS:  # any other bracketed line, such as [sic], is an entry
            section = m.group(1)
            continue
        if section == "banned":
            wl.banned.append(line.lower())
        elif section == "connectors":
            wl.connectors.append(line.lower())
        elif section == "openers":
            wl.openers.append(line.lower())
        elif section == "paths":
            (wl.exclude if line.startswith("!") else wl.include).append(line.lstrip("!").strip("/"))
        elif section == "options" and "=" in line:
            key, value = (p.strip().lower() for p in line.split("=", 1))
            if key == "connector_max" and value.isdigit():
                wl.connector_max = max(1, int(value))
            elif key in ("em_dash", "spaced_hyphen"):
                setattr(wl, key, value in ("true", "yes", "1", "on"))
    if not wl.include:
        wl.include = ["**/*.md"]
    return wl


# Scripts written without spaces between words: a word boundary means nothing there.
UNSPACED = ((0x0E00, 0x0EFF), (0x1000, 0x109F), (0x1780, 0x17FF), (0x2E80, 0x9FFF), (0xAC00, 0xD7AF),
            (0xF900, 0xFAFF), (0xFF66, 0xFF9F), (0x20000, 0x3FFFF))


def unspaced(ch: str) -> bool:
    return any(lo <= ord(ch) <= hi for lo, hi in UNSPACED)


def entry_pattern(entry: str) -> re.Pattern[str]:
    stem, wild = (entry[:-1], True) if entry.endswith("*") else (entry, False)
    body = r"\s+".join(re.escape(part) for part in stem.split()).replace("'", "['\u2019\u2018]")
    tail = r"\w*" if wild else ""
    before = "" if stem[:1] and unspaced(stem[0]) else r"(?<!\w)"
    after = "" if stem[-1:] and unspaced(stem[-1]) and not wild else r"(?!\w)"
    return re.compile(before + body + tail + after, re.IGNORECASE)


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


def wanted(rel: str, wl: WordList) -> bool:
    def hit(globs: list[str]) -> bool:
        return any(glob_to_regex(g).match(rel) for g in globs if g)
    return hit(wl.include) and not hit(wl.exclude)


def prose_lines(text: str):
    """(line number, text) for the lines that are prose: no frontmatter, no code."""
    in_front = in_code = False
    for n, raw in enumerate(text.lstrip("\ufeff").splitlines(), 1):
        line = re.sub(r"^(\s*>\s*)+", "", raw)
        if n == 1 and line.strip() == "---":
            in_front = True
            continue
        if in_front:
            in_front = line.strip() != "---"
            continue
        if line.lstrip().startswith(("```", "~~~")):
            in_code = not in_code
            continue
        if in_code:
            continue
        yield n, re.sub(r"`[^`]*`", "", line)


def check_text(text: str, wl: WordList) -> list[tuple[int, str, str]]:
    hits: list[tuple[int, str, str]] = []
    banned = [(w, entry_pattern(w)) for w in wl.banned]
    connectors = {w: entry_pattern(w) for w in wl.connectors}
    openers = [(o, entry_pattern(o)) for o in wl.openers]
    seen: dict[str, list[tuple[int, str]]] = {c: [] for c in connectors}
    for n, line in prose_lines(text):
        snippet = line.strip()[:90]
        for word, pat in banned:
            m = pat.search(line)
            if m:
                form = m.group(0)
                hits.append((n, f"word '{word}'" + (f" (as '{form}')" if form.lower() != word.rstrip("*") else ""), snippet))
        body = re.sub(r"^\s*(?:[-*+]\s+|\d+[.)]\s+|#+\s+)", "", line)
        starts = [body] + [s for s in re.split(r"(?<=[.!?])\s+", body)[1:]]
        for opener, pat in openers:
            if any(pat.match(s.lstrip()) for s in starts):
                hits.append((n, f"opener '{opener}'", snippet))
        if wl.em_dash and EM_DASH in line:
            hits.append((n, "em dash", snippet))
        stripped = line.strip()
        if wl.spaced_hyphen and not stripped.startswith(("|", "-", "*", "+")) and re.search(r"[^\W\d_][,.)]?\s+-\s+[^\W\d_]", stripped):
            hits.append((n, "hyphen used as a dash ( - )", snippet))
        for c, pat in connectors.items():
            seen[c] += [(n, snippet)] * len(pat.findall(line))
    for c, found in seen.items():
        if len(found) >= wl.connector_max:
            hits.append((found[0][0], f"connector '{c}' {len(found)}x in this file", found[0][1]))
    return sorted(hits)


def workspace_root() -> Path:
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    return Path(env) if env and Path(env).is_dir() else Path.cwd()


def load_words(path: Path | None, root: Path) -> WordList | None:
    p = path or root / WORDS_FILE
    try:
        return parse_words(p.read_text(encoding="utf-8-sig"))
    except OSError:
        return None


def format_hits(label: str, hits: list[tuple[int, str, str]]) -> str:
    lines = [f"[style] {len(hits)} advisory hit{'s' if len(hits) != 1 else ''} in {label}:"]
    for n, issue, snippet in hits:
        lines.append(f"  {label}:{n} [{issue}]  {snippet}")
    return "\n".join(lines)


def run_hook(wl: WordList, root: Path) -> int:
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8", errors="replace") or "{}")
        path = Path(str((data.get("tool_input") or {}).get("file_path") or ""))
    except (ValueError, AttributeError):
        return 0
    if not path.name or not path.is_file():
        return 0
    try:
        rel = path.resolve().relative_to(root.resolve()).as_posix()
    except (ValueError, OSError):
        return 0
    if not wanted(rel, wl):
        return 0
    hits = check_text(path.read_text(encoding="utf-8", errors="replace"), wl)
    if hits:
        print(format_hits(rel, hits) + "\nAdvisory: rewrite where it reads better; quotes and names may stay.",
              file=sys.stderr)
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Advisory writing-style check against a word list.")
    ap.add_argument("files", nargs="*")
    ap.add_argument("--words", type=Path, help=f"Word list (default {WORDS_FILE.as_posix()})")
    ap.add_argument("--strict", action="store_true", help="Exit 1 when there is a hit")
    ap.add_argument("--hook", action="store_true", help="Run as a PostToolUse hook")
    ap.add_argument("--text", help="Check this text instead of files (no temp file needed)")
    args = ap.parse_args(argv)
    root = workspace_root()
    wl = load_words(args.words, root)
    if wl is None:
        if args.hook:
            return 0
        print(f"No word list at {(args.words or WORDS_FILE).as_posix()}; nothing to check.", file=sys.stderr)
        return 2 if args.strict else 0
    if args.hook:
        try:
            return run_hook(wl, root)
        except Exception:
            return 0
    total = unread = 0
    pieces: list[tuple[str, str]] = []
    if args.text is not None:
        pieces.append(("text", args.text))
    if "-" in args.files:
        raw = getattr(sys.stdin, "buffer", None)  # bytes as utf-8: a Windows console pipe says cp1252
        pieces.append(("stdin", raw.read().decode("utf-8", errors="replace") if raw else sys.stdin.read()))
    for label, text in pieces:
        hits = check_text(text, wl)
        if hits:
            print(format_hits(label, hits))
            total += len(hits)
    for f in [f for f in args.files if f != "-"]:
        p = Path(f)
        try:
            hits = check_text(p.read_text(encoding="utf-8", errors="replace"), wl)
        except OSError as e:
            print(f"[style] cannot read {f}: {e.strerror}", file=sys.stderr)
            unread += 1
            continue
        if hits:
            print(format_hits(f, hits))
            total += len(hits)
    if args.strict and unread:
        return 2
    return 1 if args.strict and total else 0


if __name__ == "__main__":
    sys.exit(main())
