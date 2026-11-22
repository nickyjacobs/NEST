#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Save Council reviews and Architects blueprints into an idea's folder, and rebuild its idea.md.

The layouts are the ones in .claude/skills/idea/reference.md ("Review layout", "Idea page layout")
and .claude/skills/blueprint/reference.md ("Blueprint layout", "What the blueprint puts on idea.md").
This script writes them deterministically, so the skills never hand-write these files.

USAGE (from the workspace root)

  uv run --script scripts/idea_page.py save-blueprint --slug <slug> --title "<title>" \\
      --file <run>/blueprint.md [--head <run>/save-head.md] [--run <run>] [--size full|light]
  uv run --script scripts/idea_page.py save-review --slug <slug> --title "<title>" \\
      --file <run>/review.md --verdict <run>/verdict.json [--run <run>]
  uv run --script scripts/idea_page.py rebuild --slug <slug> [--title "<title>"]

Common options: --ideas <section> (else the one section in wiki.config.json with index "folders"
and page "idea.md"), --config <wiki.config.json>, --style plain|styled, --labels <json file>,
--blueprints-dir <name>, --reviews-dir <name>, --when YYYY-MM-DD-HHMM (save only), --version <n>
(save only).

save-blueprint
  --file   the checked blueprint (blueprint.md: a '# <title>' line, then the '## ' sections). It
           goes in verbatim under '## The blueprint', every heading one level deeper.
  --head   optional Markdown that goes between the 'Drawn by' line and '## The blueprint': the
           header lines that apply ('Earlier version ...', 'Answers The Council's verdict ...',
           'Closest rival: ...') and the '## The brief' section. The script adds the 'Claims:' line
           itself (counted from the blueprint, before 'Closest rival:' or else after the other
           header lines); a 'Claims:' line in the head is replaced.
  --run    the run folder; the desks come from its <desk>.report.md files (full: surveyor,
           dreamer, client, engineer, inspector; light: surveyor, engineer). Default: the folder
           of --file when it holds a meta.md. Without a run folder there is no '## The desks'.
  --size   full (default) or light: the header word and the desks.
save-review
  --file   the review body the skill wrote: the brief, an optional 'Earlier version' line, a
           '## Verdict' heading with the '- Label: value' lines, '## The fact check' (light:
           '## The spot check') and '## The source check'. The script writes the '## Verdict: ...'
           heading, the 'Idea alone', 'Jury' and 'Score check' lines from --verdict (any the skill
           wrote are replaced), and '## The reports' from the run folder unless the file has one.
  --verdict  the verdict.json council_score.py decide printed (verdict, score, idea_alone, jury,
           borderline, borderline_with, confidence, mismatches).
  --run    the run folder with <seat>.report.md; default: the folder of --verdict when it holds a
           meta.md. A missing seat reads "(no report)".
rebuild    rebuild idea.md from the files in the idea's folder. Every save ends with a rebuild.

The stamp (--when) defaults to the run folder's name (<YYYYMMDD-HHMM>-<slug>), else now. The
version (--version) defaults to: a blueprint one above the highest version in the folder; a review
the newest blueprint's version when no review has judged it yet, else one above the highest.
Saving the same run again (the same stamp) rewrites that run's file, with its version.

What survives a rebuild of idea.md: per open point (matched by its text, case, whitespace and
punctuation ignored) the tick and every line nested under it. A point that left the latest
blueprint drops off unless the user wrote something under it that no blueprint file holds yet;
such a point stays at the end of the list. Other lines the user typed in the Open points section
stay too, also after the section's heading label was changed. Everything else on the page is rebuilt.

SETTINGS, in this order: the options above, then the ideas section's "idea_page" object in
wiki.config.json ({"style": "styled", "blueprints": "blueprints", "reviews": "reviews",
"labels": {...}}), then the defaults (styled, blueprints, reviews, English labels). --labels
merges over the config's labels. Label keys (only idea.md uses them; the run files keep their
English field names, which the skills read back):

  headings      core, open, reviews, blueprint, history          (the '## ' headings of idea.md)
  status        new, worked-out, reviewed, go, parked, dropped, done   (the frontmatter words)
  status_shown  the same keys: the word on the stamp ("Worked out")
  core          one_liner, line, load_bearing, next_step, conditions, hours, first_test, monday,
                idea, verdict, biggest_risk, kill_criteria, council, skeptic, architects
  text          not_reviewed, no_open_points, no_reviews, no_blueprint, full_blueprint, updated,
                blueprints, reviews, blueprint_link, review_link, full_run, review, reviewed_event,
                blueprint_event, first_version, answers_event, table_date, table_version,
                table_verdict, table_score, table_risk, table_full, table_event

OUTPUT AND EXIT CODES

Prints one 'wrote <path>' line per file written. Writes atomically (a temp file, then a replace);
never deletes a file. Afterwards the skill runs wiki.py log, reindex and lint; this script doesn't.
Exit 0 on success, 1 on an input problem (a missing or unreadable file, a verdict.json without a
verdict or not in the shape council_score.py decide prints, a run file in the wrong shape), 2 on a
usage or config problem. The status words it writes must be allowed where it writes them: the ideas
section's own "status_words", else the top-level list; if not, it stops with exit 2 before writing.
A heading inside a desk report is moved below the desk's own heading, so it cannot end the section.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

CONFIG_NAME = "wiki.config.json"
CONFIG_ENV = "NEST_WIKI_CONFIG"
PAGE = "idea.md"
MARK_OPEN, MARK_CLOSE = "<!-- BLUEPRINT -->", "<!-- /BLUEPRINT -->"
SLUG_MAX = 50
RISK_MAX = 160

FULL_DESKS = ("surveyor", "dreamer", "client", "engineer", "inspector")
LIGHT_DESKS = ("surveyor", "engineer")
SEATS = ("believer", "skeptic", "investor", "outsider")
STATUS_BY_VERDICT = {"GO": "go", "GO WITH CONDITIONS": "go", "RESHAPE": "reviewed", "PARK": "parked",
                     "DROP": "dropped"}
CONFIDENCE_ORDER = {"low": 0, "medium": 1, "normal": 2, "high": 2}
# wiki.py's default status_words, for a config that names none: what lint accepts there.
TOP_LEVEL_STATUS_WORDS = ("draft", "active", "done", "parked", "archived", "question")

# The styled folded blueprint: one nested callout per section, as idea-note.css styles them.
SECTION_CALLOUTS = {
    "one-liner": ("one-liner", "+"), "problem and job": ("problem", "-"),
    "first user and buyer": ("first-user", "-"), "why now": ("why-now", "-"),
    "landscape": ("landscape", "-"), "directions explored": ("directions", "-"),
    "the solution": ("solution", "+"), "scope": ("scope", "-"), "model": ("model", "-"),
    "assumptions and risks": ("assumptions", "+"), "validation plan": ("validation", "-"),
    "first step and resources": ("first-step", "+"), "open questions and tensions": ("open", "+"),
    "council brief": ("council-brief", "-"), "what changed": ("changed", "-"),
}

DEFAULT_LABELS: dict[str, dict[str, str]] = {
    "headings": {"core": "Core", "open": "Open points", "reviews": "Reviews", "blueprint": "Blueprint",
                 "history": "History"},
    "status": {"new": "new", "worked-out": "worked-out", "reviewed": "reviewed", "go": "go",
               "parked": "parked", "dropped": "dropped", "done": "done"},
    "status_shown": {"new": "New", "worked-out": "Worked out", "reviewed": "Reviewed", "go": "Go",
                     "parked": "Parked", "dropped": "Dropped", "done": "Done"},
    "core": {"one_liner": "One-liner", "line": "Line", "load_bearing": "Load-bearing assumption",
             "next_step": "Next step", "conditions": "Conditions", "hours": "Hours",
             "first_test": "First test", "monday": "Monday", "idea": "The idea", "verdict": "Verdict",
             "biggest_risk": "Biggest risk", "kill_criteria": "Kill criteria", "council": "The Council",
             "skeptic": "The Skeptic", "architects": "The Architects"},
    "text": {"not_reviewed": "not reviewed yet",
             "no_open_points": "_No open points: there is no blueprint yet._",
             "no_reviews": "_Not reviewed yet. Say \"put it to the council\"._",
             "no_reviews_plain": "_Not reviewed._",
             "no_blueprint": "No blueprint yet. The Architects can work it out: \"work this idea out\".",
             "full_blueprint": "Full blueprint", "updated": "Updated", "blueprints": "Blueprints",
             "reviews": "Reviews", "blueprint_link": "Blueprint", "review_link": "Review",
             "full_run": "full run", "review": "review", "reviewed_event": "reviewed by The Council",
             "blueprint_event": "blueprint by The Architects", "first_version": "first version",
             "answers_event": "answers The Council's", "table_date": "Date", "table_version": "Version",
             "table_verdict": "Verdict", "table_score": "Score", "table_risk": "Biggest risk",
             "table_full": "Full", "table_event": "Event"},
}


class UsageError(Exception):
    """A usage or config problem: exit 2."""


class InputError(Exception):
    """A missing or malformed input file: exit 1."""


# Settings

@dataclass
class Settings:
    vault: Path
    ideas: str
    blueprints: str
    reviews: str
    style: str
    labels: dict[str, dict[str, str]]
    allowed_status: list[str] | None

    def folder(self, slug: str) -> Path:
        return self.vault / self.ideas / slug

    def status(self, role: str) -> str:
        return self.labels["status"][role]


def find_config(flag: str | None) -> Path:
    """--config, else $NEST_WIKI_CONFIG, else the first wiki.config.json up from cwd (as wiki.py)."""
    for value, origin in ((flag, "--config"), (os.environ.get(CONFIG_ENV), CONFIG_ENV)):
        if value:
            p = Path(value).expanduser()
            if not p.is_file():
                raise UsageError(f"config not found: {p} (from {origin})")
            return p.resolve()
    here = Path.cwd().resolve()
    for d in (here, *here.parents):
        if (d / CONFIG_NAME).is_file():
            return d / CONFIG_NAME
    raise UsageError(f"no {CONFIG_NAME} found from {here} upwards; pass --config or set {CONFIG_ENV}")


def merge_labels(base: dict, extra: Any, origin: str) -> dict:
    if extra in (None, {}):
        return base
    if not isinstance(extra, dict):
        raise UsageError(f"{origin}: labels must be an object of group to {{key: text}}")
    out = {k: dict(v) for k, v in base.items()}
    for group, values in extra.items():
        if group.startswith("_"):
            continue
        if group not in out or not isinstance(values, dict):
            raise UsageError(f"{origin}: unknown label group '{group}'; one of {', '.join(out)}")
        unknown = sorted(set(values) - set(out[group]))
        if unknown:
            raise UsageError(f"{origin}: unknown label(s) in '{group}': {', '.join(unknown)}")
        out[group].update({k: str(v) for k, v in values.items()})
    return out


def load_settings(args: argparse.Namespace) -> Settings:
    path = find_config(args.config)
    try:
        cfg = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as e:
        raise UsageError(f"cannot read {path}: {e}") from e
    sections = cfg.get("sections") if isinstance(cfg, dict) else None
    if not isinstance(sections, dict):
        raise UsageError(f"{path}: no 'sections' object")
    vault = Path(str(cfg.get("wiki_dir", "wiki"))).expanduser()
    vault = (vault if vault.is_absolute() else path.parent / vault).resolve()
    if not vault.is_dir():
        raise UsageError(f"vault not found: {vault} (wiki_dir in {path})")
    ideas = args.ideas
    if not ideas:
        found = [n for n, s in sections.items()
                 if isinstance(s, dict) and s.get("index") == "folders" and s.get("page") == PAGE]
        if len(found) != 1:
            raise UsageError(f"{path}: expected one section with index \"folders\" and page \"{PAGE}\", "
                             f"found {len(found)}; pass --ideas")
        ideas = found[0]
    sec = sections.get(ideas)
    if not isinstance(sec, dict):
        raise UsageError(f"section '{ideas}' is not in {path}")
    if sec.get("index") != "folders" or sec.get("page") != PAGE:
        raise UsageError(f"section '{ideas}' needs \"index\": \"folders\" and \"page\": \"{PAGE}\" in {path}")
    own = sec.get("idea_page") or {}
    if not isinstance(own, dict):
        raise UsageError(f"{path}: sections.{ideas}.idea_page must be an object")
    labels = merge_labels(DEFAULT_LABELS, own.get("labels"), f"{path} (sections.{ideas}.idea_page.labels)")
    if args.labels:
        lp = Path(args.labels).expanduser()
        try:
            extra = json.loads(lp.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as e:
            raise UsageError(f"cannot read labels {lp}: {e}") from e
        labels = merge_labels(labels, extra, str(lp))
    style = args.style or own.get("style") or "styled"
    if style not in ("styled", "plain"):
        raise UsageError(f"style must be 'styled' or 'plain', not '{style}'")
    blueprints = args.blueprints_dir or own.get("blueprints") or "blueprints"
    reviews = args.reviews_dir or own.get("reviews") or "reviews"
    for name in (blueprints, reviews):
        if not re.fullmatch(r"[^/\\]+", str(name)) or name in (".", ".."):
            raise UsageError(f"folder name must be one plain name: '{name}'")
    words = sec.get("status_words")
    if not isinstance(words, list):  # as wiki.py lint: the section's own list, else the top-level one
        words = cfg.get("status_words")
    if not isinstance(words, list):
        words = list(TOP_LEVEL_STATUS_WORDS)
    return Settings(vault=vault, ideas=ideas, blueprints=str(blueprints), reviews=str(reviews), style=style,
                    labels=labels, allowed_status=[str(w) for w in words])


def check_status_words(s: Settings) -> None:
    """Every status word this script may write must be one the ideas section allows, checked before
    anything is written."""
    if s.allowed_status is None:
        return
    missing = [w for w in s.labels["status"].values() if w not in s.allowed_status]
    if missing:
        raise UsageError(f"status word(s) {', '.join(missing)} are not allowed in section '{s.ideas}' "
                         f"({', '.join(s.allowed_status)}), so lint would refuse the pages. Give the section "
                         "its own \"status_words\" in wiki.config.json (see the idea skill's reference.md), "
                         "or change the status labels")


# Files

def read_text(path: Path) -> str:
    try:
        text = path.read_bytes().decode("utf-8", errors="replace")
    except OSError as e:
        raise InputError(f"cannot read {path}: {e.strerror or e}") from e
    return text.removeprefix("﻿").replace("\r\n", "\n").replace("\r", "\n")


def write_atomic(path: Path, text: str) -> None:
    """Write via a temp file in the same folder, then replace; CRLF kept when the old file had it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and b"\r\n" in path.read_bytes():
        text = text.replace("\n", "\r\n")
    if path.exists():
        mode = path.stat().st_mode & 0o777
    else:  # what a plain open() would give: mkstemp makes the file private (0600)
        umask = os.umask(0)
        os.umask(umask)
        mode = 0o666 & ~umask
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(text.encode("utf-8"))
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """The simple 'key: value' frontmatter these files carry, and the body after it."""
    m = re.match(r"---\n(.*?)\n---\n?", text, re.DOTALL)
    if not m:
        return {}, text
    fm: dict[str, str] = {}
    for line in m.group(1).splitlines():
        kv = re.match(r"([\w-]+):\s*(.*)$", line)
        if not kv:
            continue
        value = kv.group(2).strip()
        if value.startswith('"'):
            try:
                value = str(json.loads(value))
            except ValueError:
                value = value.strip('"')
        elif value.startswith("'") and value.endswith("'") and len(value) > 1:
            value = value[1:-1].replace("''", "'")
        fm[kv.group(1)] = value
    return fm, text[m.end():]


def yaml_str(value: str) -> str:
    """A YAML scalar: bare when that is safe, else a JSON string (which YAML reads as well)."""
    reads_as_other = (value.lower() in ("y", "n", "yes", "no", "true", "false", "on", "off", "null", "none")
                      or re.fullmatch(r"[0-9][0-9._:eE+\- TZ]*", value))  # a bool, null, number or date to YAML
    if (re.fullmatch(r"[A-Za-z0-9À-￿][^:#\[\]{}&*!|>'\"%@`,]*", value) and value == value.strip()
            and not reads_as_other):
        return value
    return json.dumps(value, ensure_ascii=False)


def one_line(text: str) -> str:
    return " ".join(str(text).split())


def alias(text: str) -> str:
    """Text that is safe as a link alias."""
    return " ".join(text.replace("|", "-").replace("[", "(").replace("]", ")").split())


def cell(text: str) -> str:
    """One table cell: on one line, pipes escaped."""
    return " ".join(text.split()).replace("|", "\\|")


def quote_lines(text: str, prefix: str = "> ") -> list[str]:
    return [(prefix + line).rstrip() if line.strip() else prefix.rstrip() for line in text.strip("\n").splitlines()]


# Markdown reading

def sections(text: str, level: int) -> list[tuple[str, str]]:
    """(heading, content) for each heading of exactly this level; a higher heading ends a section.
    Lines inside code fences are never headings."""
    out: list[tuple[str, list[str]]] = []
    fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fence = not fence
        m = None if fence else re.match(r"(#{1,6}) (.*)$", line)
        if m and len(m.group(1)) == level:
            out.append((m.group(2).strip(), []))
        elif m and len(m.group(1)) < level:
            out.append(("", []))
        elif out:
            out[-1][1].append(line)
    return [(h, "\n".join(body).strip("\n")) for h, body in out if h]


def section(text: str, level: int, name: str, prefix: bool = False) -> str:
    key = name.casefold()
    for h, body in sections(text, level):
        if h.casefold() == key or (prefix and h.casefold().startswith(key)):
            return body
    return ""


def field_value(text: str, key: str) -> str:
    """The value of the first 'Key: value' (or '- Key: value') line."""
    m = re.search(r"(?m)^(?:[-*] )?" + re.escape(key) + r":[ \t]*(.+)$", text)
    return m.group(1).strip() if m else ""


LABEL = re.compile(r"\[(yours|proposed|assumed|open|fact \d+(?:\s*,\s*\d+)*)\]")


def strip_labels(text: str) -> str:
    return " ".join(LABEL.sub("", text).split()).replace(" .", ".").replace(" ,", ",")


def first_sentences(text: str, n: int = 1) -> str:
    para = " ".join(text.strip().split("\n\n")[0].split())
    parts, start = [], 0
    for m in re.finditer(r"(?<=[.!?])\s+", para):
        nxt = para[m.end():m.end() + 1]
        if nxt and not nxt.islower():  # a capital in any script, a digit, a quote; never "e.g. five"
            parts.append(para[start:m.start()])
            start = m.end()
    parts.append(para[start:])
    return " ".join(parts[:n]).strip()


def council_installed() -> bool:
    """Is the idea skill (The Council) part of this workspace? Unknown counts as yes: the script
    runs from the workspace root, and a folder without `.claude/skills` is a test or a kit copy."""
    skills = Path.cwd() / ".claude" / "skills"
    return not skills.is_dir() or (skills / "idea").is_dir()


def lead_item(text: str) -> str:
    """What a block opens with: its first line, without a list marker. The format asks for "the
    load-bearing assumption first"; some desks write it as a sentence above the list."""
    for line in text.splitlines():
        if line.strip():
            return re.sub(r"^\s*(?:[-*+]|\d+\.) ", "", line).strip()
    return ""


def first_item(text: str) -> str:
    """The first list item of a block, else its first line."""
    for line in text.splitlines():
        if re.match(r"\s*(?:[-*+]|\d+\.) ", line):
            return re.sub(r"^\s*(?:[-*+]|\d+\.) ", "", line).strip()
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return ""


def callouts(text: str) -> dict[str, str]:
    """Title to body of each top-level callout ('> [!type]- Title' and its '> ' lines)."""
    out: dict[str, str] = {}
    title, body = None, []
    for line in text.splitlines() + [""]:
        m = re.match(r"> \[![\w-]+\][+-]?\s*(.*)$", line)
        if m:
            if title is not None:
                out.setdefault(title, "\n".join(body))
            title, body = m.group(1).strip(), []
        elif title is not None and line.startswith(">"):
            body.append(line[2:] if line.startswith("> ") else line[1:])
        elif title is not None:
            out.setdefault(title, "\n".join(body))
            title, body = None, []
    return out


def norm(text: str) -> str:
    return re.sub(r"[\W_]+", "", LABEL.sub("", text).casefold())


# The run files in an idea's folder

STAMP = r"(\d{4}-\d{2}-\d{2})-(\d{2})(\d{2})"


@dataclass
class Run:
    kind: str  # "blueprint" or "review"
    path: Path
    stamp: str
    version: int
    fm: dict[str, str]
    body: str

    @property
    def stem(self) -> str:
        return self.path.stem

    @property
    def date(self) -> str:
        return self.stamp[:10]

    @property
    def when(self) -> str:
        return f"{self.stamp[:10]} {self.stamp[11:13]}:{self.stamp[13:15]}"

    @property
    def order(self) -> tuple:
        return (self.stamp, 0 if self.kind == "blueprint" else 1, self.version)


def scan(folder: Path, kind: str) -> list[Run]:
    pattern = re.compile("^" + STAMP + (r"-v(\d+)\.md$" if kind == "blueprint" else r"-council-v(\d+)\.md$"))
    runs = []
    if folder.is_dir():
        for p in sorted(folder.glob("*.md")):
            m = pattern.match(p.name)
            if not m:
                print(f"idea_page: skipped {p} (not a {kind} file name)", file=sys.stderr)
                continue
            fm, body = split_frontmatter(read_text(p))
            runs.append(Run(kind, p, f"{m.group(1)}-{m.group(2)}{m.group(3)}", int(m.group(4)), fm, body))
    return sorted(runs, key=lambda r: r.order)


@dataclass
class Folder:
    slug: str
    path: Path
    blueprints: list[Run] = field(default_factory=list)
    reviews: list[Run] = field(default_factory=list)

    @property
    def runs(self) -> list[Run]:
        return sorted(self.blueprints + self.reviews, key=lambda r: r.order)


def load_folder(s: Settings, slug: str) -> Folder:
    path = s.folder(slug)
    return Folder(slug, path, scan(path / s.blueprints, "blueprint"), scan(path / s.reviews, "review"))


def blueprint_text(run: Run) -> str:
    """The blueprint as The Draftsman wrote it: '## The blueprint' with its headings one level up."""
    body = section(run.body, 2, "The blueprint")
    return re.sub(r"(?m)^#(#{2,}) ", r"\1 ", body)


def desk(run: Run, name: str) -> str:
    return section(section(run.body, 2, "The desks"), 3, f"The {name}")


def review_fields(run: Run) -> str:
    return section(run.body, 2, "Verdict", prefix=True)


def review_brief(run: Run) -> str:
    head = run.body.split("\n## ", 1)[0]
    lines = [ln for ln in head.splitlines()
             if not ln.startswith("# ") and not ln.startswith("Judged by ") and not ln.startswith("Earlier version ")]
    return "\n".join(lines).strip()


def none_like(text: str) -> bool:
    return norm(text) in ("", "none", "nothing", "na", "geen")


# The idea page

@dataclass
class Point:
    tick: str
    text: str
    children: list[str]


def parse_open_points(text: str, heading: str, placeholder: str) -> tuple[list[Point], list[str]]:
    """The points of the Open points section, each with its nested lines, and any other lines."""
    body = section(text, 2, heading) if text else ""
    if text and not body:
        # The heading label changed since the page was written. The page is built by this script,
        # so the open points are its second section whatever it is called.
        found = sections(split_frontmatter(text)[1], 2)
        if len(found) == 5 and found[0][0].casefold() != heading.casefold():
            body = found[1][1]
    points: list[Point] = []
    extra: list[str] = []
    pending_blank = 0
    for line in body.splitlines():
        m = re.match(r"[-*+] \[(.)\] (.*)$", line)
        if m:
            points.append(Point(m.group(1), m.group(2).strip(), []))
            pending_blank = 0
        elif not line.strip():
            pending_blank += 1
        elif line[:1] in (" ", "\t") and points:
            points[-1].children.extend([""] * pending_blank + [line.rstrip()])
            pending_blank = 0
        elif line.strip() != placeholder.strip():
            extra.append(line.rstrip())
            pending_blank = 0
    return points, extra


def open_points_of(run: Run | None) -> list[str]:
    if run is None:
        return []
    block = section(blueprint_text(run), 2, "Open questions and tensions")
    items: list[str] = []
    current: list[str] | None = None
    for line in block.splitlines():
        if re.match(r"[-*+] ", line):
            if current is not None:
                items.append(" ".join(current))
            current = [line[2:].strip()]
        elif current is not None and line.startswith((" ", "\t")) and line.strip():
            current.append(line.strip())
        elif current is not None:
            items.append(" ".join(current))
            current = None
    if current is not None:
        items.append(" ".join(current))
    return [strip_labels(i) for i in items if "[open]" in i]


def merge_points(new: list[str], old: list[Point], corpus: str) -> list[Point]:
    by_key: dict[str, Point] = {}
    for p in old:
        by_key.setdefault(norm(p.text), p)
    out, used = [], set()
    for text in new:
        prev = by_key.get(norm(text))
        if prev is not None:
            used.add(id(prev))
        out.append(Point(prev.tick if prev else " ", text, list(prev.children) if prev else []))
    for p in old:
        if id(p) in used:
            continue
        said = [re.sub(r"^\s*(?:[-*+]\s+)?(?:\*\*[^*]+:\*\*\s*)?", "", c) for c in p.children if c.strip()]
        if any(norm(c) and norm(c) not in corpus for c in said):
            out.append(p)  # the user's words are nowhere else yet: keep them on the page
    return out


def fold_blueprint(text: str, style: str) -> list[str]:
    """The latest blueprint as the inside of the folded callout, every line already prefixed."""
    if style == "plain":
        return quote_lines(text)
    out: list[str] = []
    head = text.split("\n## ", 1)[0] if not text.startswith("## ") else ""
    if head.strip():
        out += quote_lines(head) + [">"]
    for name, body in sections(text, 2):
        if name.casefold() == "sources":
            out += ["> ## Sources", ">"]
            for line in body.splitlines():
                m = re.match(r"(\d+) \| (.*?) \|.*?\| (https?://\S+) \|.*?((?:\((?:quote checked|not verified[^)]*)\))?)\s*$", line)
                if m:
                    mark = f" {m.group(4)}" if m.group(4) else ""
                    out.append(f"> {m.group(1)}. {m.group(2)} ({m.group(3)}){mark}")
                elif line.strip():
                    out.append(f"> {line}")
            out.append(">")
            continue
        kind, fold = SECTION_CALLOUTS.get(name.casefold(), ("note", "-"))
        out.append(f"> > [!{kind}]{fold} {name}")
        spanned = LABEL.sub(lambda m: f'<span class="lbl lbl-{m.group(1).split()[0]}">{m.group(1)}</span>', body)
        out += quote_lines(spanned, "> > ") if spanned.strip() else []
        out.append(">")
    while out and out[-1] == ">":
        out.pop()
    return out


def idea_title(f: Folder, given: str | None, existing: dict[str, str]) -> str:
    if given and one_line(given):
        return one_line(given)
    if existing.get("title"):
        return existing["title"]
    for run in reversed(f.runs):
        t = re.sub(r"^(Blueprint|Review) v\d+:\s*", "", run.fm.get("title", ""))
        if t:
            return t
    raise UsageError("no title: pass --title")


def build_idea(s: Settings, f: Folder, title: str, existing_text: str) -> tuple[str, str]:
    """The idea page, and its status word."""
    L = s.labels
    H, T, C = L["headings"], L["text"], L["core"]
    styled = s.style == "styled"
    runs = f.runs
    bp = f.blueprints[-1] if f.blueprints else None
    rv = f.reviews[-1] if f.reviews else None
    latest = runs[-1] if runs else None
    if latest is None:
        role = "new"
    elif latest.kind == "blueprint":
        role = "worked-out"
    else:
        verdict = rv.fm.get("verdict", "").upper()
        if verdict not in STATUS_BY_VERDICT:
            raise InputError(f"{rv.path}: unknown verdict '{rv.fm.get('verdict')}'")
        role = STATUS_BY_VERDICT[verdict]
    status = s.status(role)
    base = f"{s.ideas}/{f.slug}"

    def link(r: Run) -> str:
        return f"{base}/{s.blueprints if r.kind == 'blueprint' else s.reviews}/{r.stem}"

    version = max((r.version for r in runs), default=1)
    verdict_text = ""
    if rv:
        verdict_text = f"{rv.fm.get('verdict', '')} {rv.fm.get('score', '')}".strip()

    today = f"{datetime.now():%Y-%m-%d}"
    created = runs[0].date if runs else today
    updated = latest.date if latest else today
    fm = ["---", f"title: {yaml_str(title)}", f"created: {created}", f"updated: {updated}",
          "tags: [idea]", f"category: {s.ideas}", f"status: {status}", f"version: {version}"]
    if rv:
        fm += [f"verdict: {rv.fm.get('verdict', '')}", f"score: {rv.fm.get('score', '')}"]
    fm += [f"blueprints: {len(f.blueprints)}", f"reviews: {len(f.reviews)}", "cssclasses: [idea-note]",
           "author: claude", "---"]

    # The stamp
    kind = ("blueprint" if latest and latest.kind == "blueprint" else "verdict") if styled else "info"
    if rv and latest and rv.version != version:
        shown_verdict = f"{verdict_text} (v{rv.version})"
    else:
        shown_verdict = verdict_text or T["not_reviewed"]
    stamp = [f"> [!{kind}] {L['status_shown'][role]} · v{version} · {shown_verdict}",
             (f"> {T['updated']} {updated} · {T['blueprints']} {len(f.blueprints)} · "
              f"{T['reviews']} {len(f.reviews)}")]
    links = [f"[[{link(r)}|{T[k]} v{r.version}]]" for r, k in ((bp, "blueprint_link"), (rv, "review_link")) if r]
    if links:
        stamp.append("> " + " · ".join(links))

    # Core
    core: list[str] = []
    def add(group: list[str], label: str, value: str, by: str = "") -> None:
        if value and not none_like(value):
            group.append(f"**{label}:** {value}" + (f" *({by})*" if by else ""))
    groups: list[list[str]] = []
    if bp:
        bp_text = blueprint_text(bp)
        eng, insp = desk(bp, "Engineer"), desk(bp, "Inspector")
        first: list[str] = []
        add(first, C["one_liner"], strip_labels(first_sentences(section(bp_text, 2, "One-liner"))))
        add(first, C["line"], field_value(eng, "Direction"))
        load = field_value(insp, "Load-bearing") or lead_item(section(bp_text, 2, "Assumptions and risks"))
        add(first, C["load_bearing"], load)
        groups.append(first)
        second: list[str] = []
        if rv and rv.version == bp.version and rv.order > bp.order:
            fields = review_fields(rv)
            add(second, C["next_step"], field_value(fields, "Next step"), C["council"])
            add(second, C["conditions"], field_value(fields, "Conditions"), C["council"])
            skeptic = field_value(callouts(section(rv.body, 2, "The reports")).get("The Skeptic", ""), "First version")
            hours = [f"{v} *({who})*" for v, who in ((skeptic, C["skeptic"]),
                                                     (field_value(eng, "Hours"), C["architects"])) if v]
            if hours:
                second.append(f"**{C['hours']}:** " + " · ".join(hours))
        else:
            test = first_item(section(bp_text, 2, "Validation plan"))
            if not test:
                parts = first_item(field_after(insp, "Assumptions")).split(" | ")
                test = parts[1] if len(parts) > 1 else ""
            add(second, C["first_test"], strip_labels(test))
            add(second, C["monday"], field_value(eng, "Monday"))
            add(second, C["hours"], field_value(eng, "Hours"))
        groups.append(second)
    elif rv:
        fields = review_fields(rv)
        brief = review_brief(rv)
        one = first_sentences(brief)
        group: list[str] = []
        add(group, C["idea"], first_sentences(brief, 2) if len(one) < 120 else one)
        add(group, C["verdict"], verdict_text)
        add(group, C["biggest_risk"], field_value(fields, "Biggest risk"))
        add(group, C["next_step"], field_value(fields, "Next step"))
        add(group, C["kill_criteria"], field_value(fields, "Kill criteria"))
        groups.append(group)
    core_kind = "core" if styled else "info"
    core.append(f"> [!{core_kind}] {H['core']}")
    groups = [g for g in groups if g]
    for i, g in enumerate(groups):
        if i:
            core.append(">")
        core += [f"> {line}" for line in g]

    # Open points
    old_points, extra = parse_open_points(existing_text, H["open"], T["no_open_points"])
    corpus = norm("\n".join(read_text(r.path) for r in f.blueprints))
    points = merge_points(open_points_of(bp), old_points, corpus)
    open_lines: list[str] = []
    for p in points:
        open_lines.append(f"- [{p.tick}] {p.text}")
        open_lines += p.children
    if not points and not bp:
        open_lines.append(T["no_open_points"])
    if extra:
        open_lines += ([""] if open_lines else []) + extra

    # Reviews
    if f.reviews:
        rev = [(f"| {T['table_date']} | {T['table_version']} | {T['table_verdict']} | {T['table_score']} | "
                f"{T['table_risk']} | {T['table_full']} |"), "|---|---|---|---|---|---|"]
        for r in reversed(f.reviews):
            risk = " ".join(field_value(review_fields(r), "Biggest risk").split())
            if len(risk) > RISK_MAX:
                risk = risk[:RISK_MAX - 1].rsplit(" ", 1)[0].rstrip(",;:") + "…"
            rev.append(f"| {r.when} | v{r.version} | **{r.fm.get('verdict', '')}** | {r.fm.get('score', '')} | "
                       f"{cell(risk)} | [[{link(r)}\\|{T['review']}]] |")
    else:
        rev = [T["no_reviews"] if council_installed() else T["no_reviews_plain"]]

    # Blueprint
    if bp:
        fold = [f"> [!{'blueprint' if styled else 'quote'}]- {T['full_blueprint']} v{bp.version}"]
        fold += fold_blueprint(blueprint_text(bp), s.style)
    else:
        fold = [f"> [!{'open' if styled else 'info'}] {T['no_blueprint']}"]

    # History
    hist = [f"| {T['table_date']} | {T['table_version']} | {T['table_event']} | {T['table_full']} |",
            "|---|---|---|---|"]
    for r in reversed(runs):
        if r.kind == "review":
            event = f"{T['reviewed_event']}: {r.fm.get('verdict', '')} {r.fm.get('score', '')}"
        else:
            changed = ""
            m = re.search(r"(?m)^Earlier version .*?Changed:\s*(.+?)\s*$", r.body)
            if m:
                changed = m.group(1).rstrip(".")
            if not changed:
                changed = first_sentences(section(blueprint_text(r), 2, "What changed")).rstrip(".")
            event = f"{T['blueprint_event']}: {changed or (T['first_version'] if r.version == 1 else f'v{r.version}')}"
            m = re.search(r"(?m)^Answers The Council's verdict.*?:\s*([A-Z][A-Z ]+?)\s+\d", r.body)
            if m:
                event += f"; {T['answers_event']} {m.group(1)}"
        hist.append(f"| {r.when} | v{r.version} | {cell(event)} | [[{link(r)}\\|{T['full_run']}]] |")

    lines = fm + ["", f"# {title}", ""] + stamp + ["", f"## {H['core']}", ""] + core + [""]
    lines += [f"## {H['open']}", ""] + open_lines + [""]
    lines += [f"## {H['reviews']}", ""] + rev + [""]
    lines += [f"## {H['blueprint']}", "", MARK_OPEN] + fold + [MARK_CLOSE, ""]
    lines += [f"## {H['history']}", ""] + hist
    return "\n".join(lines) + "\n", status


def field_after(text: str, key: str) -> str:
    """The lines after a 'Key:' line, up to the next 'Key:' line."""
    m = re.search(r"(?ms)^" + re.escape(key) + r":[ \t]*\n(.*?)(?=^[A-Z][\w -]*:|\Z)", text)
    return m.group(1) if m else ""


def rebuild(s: Settings, slug: str, title: str | None) -> Path:
    f = load_folder(s, slug)
    if not f.path.is_dir():
        raise InputError(f"no idea folder: {f.path}")
    page = f.path / PAGE
    existing = read_text(page) if page.exists() else ""
    fm, _ = split_frontmatter(existing)
    text, _status = build_idea(s, f, idea_title(f, title, fm), existing)
    write_atomic(page, text)
    return page


# Saving

def stamp_of(when: str | None, run: Path | None) -> str:
    if when:
        m = re.fullmatch(r"(\d{4})-?(\d{2})-?(\d{2})-(\d{2}):?(\d{2})", when.strip())
        if not m:
            raise UsageError(f"--when must be YYYY-MM-DD-HHMM, not '{when}'")
        y, mo, d, h, mi = m.groups()
    elif run is not None and (m := re.match(r"(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})-", run.name)):
        y, mo, d, h, mi = m.groups()
    else:
        now = datetime.now()
        y, mo, d, h, mi = (f"{now:%Y}", f"{now:%m}", f"{now:%d}", f"{now:%H}", f"{now:%M}")
    try:
        datetime(int(y), int(mo), int(d), int(h), int(mi))
    except ValueError as e:
        raise UsageError(f"not a valid date and time: {y}-{mo}-{d} {h}:{mi}") from e
    return f"{y}-{mo}-{d}-{h}{mi}"


def run_folder(given: str | None, beside: Path) -> Path | None:
    if given:
        p = Path(given).expanduser()
        if not p.is_dir():
            raise InputError(f"run folder not found: {p}")
        return p
    return beside.parent if (beside.parent / "meta.md").is_file() else None


def check_slug(slug: str) -> str:
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug) or len(slug) > SLUG_MAX:
        raise UsageError(f"slug must be lowercase ASCII words joined by hyphens, at most {SLUG_MAX} "
                         f"characters: '{slug}'")
    return slug


def pick_version(runs: list[Run], stamp: str, given: int | None, auto: int) -> int:
    same = [r for r in runs if r.stamp == stamp]
    if same:
        if given is not None and given != same[0].version:
            raise InputError(f"{same[0].path} is this run (the same stamp) with version {same[0].version}, "
                             f"not {given}")
        return same[0].version
    return given if given is not None else auto


def report(path: Path) -> str:
    try:
        text = read_text(path).strip()
    except InputError:
        return "(no report)"
    return text or "(no report)"


def nested(text: str, under: int = 3) -> str:
    """A report that goes under a level-3 heading: its own headings move below that level (at most
    level 6), so one of them cannot end the section it sits in. Code fences are left alone."""
    out, fence = [], False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fence = not fence
        m = None if fence else re.match(r"(#{1,6}) ", line)
        out.append("#" * min(6, len(m.group(1)) + under) + line[len(m.group(1)):] if m else line)
    return "\n".join(out)


def count_claims(blueprint: str) -> str:
    body = re.split(r"(?m)^## Sources\s*$", blueprint)[0]
    counts = {"yours": 0, "fact": 0, "proposed": 0, "assumed": 0, "open": 0}
    for m in LABEL.finditer(body):
        counts[m.group(1).split()[0]] += 1
    srcs = section(blueprint, 2, "Sources")
    found = len(re.findall(r"\(quote checked\)", srcs))
    missed = len(re.findall(r"\(not verified", srcs))
    check = (f"Source check: {found} of {found + missed} quotes found." if found + missed
             else "Source check: no quotes checked.")
    return (f"Claims: {counts['yours']} yours, {counts['fact']} fact, {counts['proposed']} proposed, "
            f"{counts['assumed']} assumed, {counts['open']} open. {check}")


def save_blueprint(s: Settings, args: argparse.Namespace) -> list[Path]:
    slug, title = check_slug(args.slug), one_line(args.title)
    src = Path(args.file).expanduser()
    raw = read_text(src).strip("\n")
    if not re.search(r"(?m)^## ", raw):
        raise InputError(f"{src}: no '## ' sections; pass the blueprint.md The Draftsman wrote")
    blueprint = raw.split("\n", 1)[1].strip("\n") if raw.startswith("# ") else raw
    run = run_folder(args.run, src)
    stamp = stamp_of(args.when, run)
    f = load_folder(s, slug)
    auto = max((r.version for r in f.runs), default=0) + 1
    version = pick_version(f.blueprints, stamp, args.version, auto)
    when = f"{stamp[:10]} {stamp[11:13]}:{stamp[13:15]}"

    head = read_text(Path(args.head).expanduser()).strip("\n") if args.head else ""
    head_lines = [ln for ln in head.splitlines() if not ln.startswith("Claims: ")]
    cut = next((i for i, ln in enumerate(head_lines) if ln.startswith("## ")), len(head_lines))
    pre, rest = head_lines[:cut], head_lines[cut:]
    while pre and not pre[-1].strip():
        pre.pop()
    at = next((i for i, ln in enumerate(pre) if ln.startswith("Closest rival:")), len(pre))
    pre.insert(at, count_claims(blueprint))

    demoted = re.sub(r"(?m)^(#{2,5}) ", r"#\1 ", blueprint)
    desks = LIGHT_DESKS if args.size == "light" else FULL_DESKS
    link_title = alias(title)
    out = ["---", f"title: {json.dumps(f'Blueprint v{version}: {title}', ensure_ascii=False)}",
           f"created: {stamp[:10]}", f"updated: {stamp[:10]}", "tags: [idea, blueprint]",
           f"category: {s.ideas}", f"status: {s.status('done')}", "cssclasses: [idea-note]",
           f"version: {version}",
           f"idea: {json.dumps(f'[[{s.ideas}/{slug}/idea|{link_title}]]', ensure_ascii=False)}",
           "author: claude", "---", "", f"# Blueprint: {title}", "",
           f"Drawn by The Architects on {when}, version {version} ({args.size}).", ""]
    out += pre + [""]
    if rest:
        out += rest + [""]
    out += ["## The blueprint", "", demoted, ""]
    if run is not None:
        out += ["## The desks", ""]
        for d in desks:
            out += [f"### The {d.capitalize()}", "", nested(report(run / f"{d}.report.md")), ""]
    path = f.path / s.blueprints / f"{stamp}-v{version}.md"
    write_atomic(path, "\n".join(out).rstrip("\n") + "\n")
    return [path, rebuild(s, slug, title)]


def jury_line(v: dict) -> str:
    jury = v.get("jury") or []
    parts = [f"{j.get('verdict') or '-'} {fmt_score(j.get('score'))}" for j in jury]
    tail = []
    if v.get("jury_incomplete"):
        tail.append("two of three judges")
    if v.get("borderline"):
        tail.append(f"borderline, could have been {v['borderline_with']}" if v.get("borderline_with") else "borderline")
    else:
        tail.append("not a close call")
    return f"- Jury: {' · '.join(parts)}; {'; '.join(tail)}"


def fmt_score(x: Any) -> str:
    try:
        return f"{float(x):.1f}"
    except (TypeError, ValueError):
        return str(x)


def load_verdict(path: Path) -> dict:
    try:
        v = json.loads(read_text(path))
    except ValueError as e:
        raise InputError(f"{path}: not valid JSON ({e})") from e
    if not isinstance(v, dict) or not v.get("verdict") or v.get("score") is None:
        raise InputError(f"{path}: no verdict and score (did the jury complete?)")
    if str(v["verdict"]).upper() not in STATUS_BY_VERDICT:
        raise InputError(f"{path}: unknown verdict '{v['verdict']}'")
    for key in ("score", "idea_alone"):
        if v.get(key) is None:
            continue
        try:
            ok = not isinstance(v[key], bool) and 0 <= float(v[key]) <= 10
        except (TypeError, ValueError):
            ok = False
        if not ok:
            raise InputError(f"{path}: {key} must be a number from 0 to 10, not {v[key]!r}")
    jury = [] if v.get("jury") is None else v["jury"]
    notes = [] if v.get("mismatches") is None else v["mismatches"]
    if not isinstance(jury, list) or not all(isinstance(j, dict) for j in jury):
        raise InputError(f"{path}: 'jury' must be a list of {{verdict, score}} objects; write the file with "
                         "council_score.py decide, not by hand")
    if not isinstance(notes, list) or not all(isinstance(m, dict) and isinstance(m.get("notes") or [], list)
                                             for m in notes):
        raise InputError(f"{path}: 'mismatches' must be a list of {{judge, notes: [...]}} objects; write the file "
                         "with council_score.py decide, not by hand")
    return v


def save_review(s: Settings, args: argparse.Namespace) -> list[Path]:
    slug, title = check_slug(args.slug), one_line(args.title)
    vpath, src = Path(args.verdict).expanduser(), Path(args.file).expanduser()
    v = load_verdict(vpath)
    board = read_text(src).strip("\n")
    lines = board.splitlines()
    at = next((i for i, ln in enumerate(lines) if re.match(r"## Verdict\b", ln)), None)
    if at is None:
        raise InputError(f"{src}: no '## Verdict' heading; the review body needs one above the verdict lines")
    end = next((i for i in range(at + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    verdict_lines = [ln for ln in lines[at + 1:end]
                     if not re.match(r"- (Idea alone|Jury|Score check)\b", ln)]
    confidence = field_value("\n".join(verdict_lines), "Confidence")
    level = (re.match(r"[A-Za-z]+", confidence) or [""])[0].lower() if confidence else ""
    script = str(v.get("confidence") or "").lower()
    if script in ("low", "medium") and (not level or CONFIDENCE_ORDER.get(level, 2) > CONFIDENCE_ORDER[script]):
        level = script
    verdict, score = str(v["verdict"]).upper(), fmt_score(v["score"])
    heading = f"## Verdict: {verdict}, {score}/10" + (f" (confidence {level})" if level else "")
    computed = []
    if v.get("idea_alone") is not None:
        computed.append(f"- Idea alone (without the timing): {fmt_score(v['idea_alone'])}/10")
    computed.append(jury_line(v))
    items = [ln for ln in verdict_lines if ln.strip()]
    notes = []
    for m in v.get("mismatches") or []:
        if m.get("notes"):
            who = "judge" if len(v.get("jury") or []) == 1 else f"judge {m.get('judge')}"
            notes.append(f"{who}: {'; '.join(str(n) for n in m['notes'])}")
    if notes:
        items.append(f"- Score check: {' | '.join(notes)}")
    body_lines = lines[:at] + [heading, ""] + computed + items + [""] + lines[end:]
    size = args.size or ("light" if len(v.get("jury") or []) == 1 else "full")

    run = run_folder(args.run, vpath)
    stamp = stamp_of(args.when, run)
    f = load_folder(s, slug)
    if args.version is None and f.blueprints and not any(r.version == f.blueprints[-1].version for r in f.reviews):
        auto = f.blueprints[-1].version
    else:
        auto = max((r.version for r in f.runs), default=0) + 1
    version = pick_version(f.reviews, stamp, args.version, auto)
    when = f"{stamp[:10]} {stamp[11:13]}:{stamp[13:15]}"
    out = ["---", f"title: {json.dumps(f'Review v{version}: {title}', ensure_ascii=False)}",
           f"created: {stamp[:10]}", f"updated: {stamp[:10]}", "tags: [idea, council]",
           f"category: {s.ideas}", f"status: {s.status('done')}", f"version: {version}",
           f"verdict: {verdict}", f"score: {score}",
           f"idea: {json.dumps(f'[[{s.ideas}/{slug}/idea|{alias(title)}]]', ensure_ascii=False)}",
           "cssclasses: [idea-note]", "author: claude", "---", "", f"# Idea: {title}", "",
           f"Judged by The Council on {when}, version {version} ({size}).", ""]
    out += ["\n".join(body_lines).strip("\n"), ""]
    if not re.search(r"(?m)^## The reports\s*$", board):
        if run is None:
            print("idea_page: no run folder, so the review has no '## The reports' (pass --run)", file=sys.stderr)
        else:
            out += ["## The reports", ""]
            for seat in SEATS:
                kind = seat if s.style == "styled" else "quote"
                out += [f"> [!{kind}]- The {seat.capitalize()}"] + quote_lines(report(run / f"{seat}.report.md")) + [""]
    path = f.path / s.reviews / f"{stamp}-council-v{version}.md"
    write_atomic(path, "\n".join(out).rstrip("\n") + "\n")
    return [path, rebuild(s, slug, title)]


# CLI

def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", help=f"path to {CONFIG_NAME} (else ${CONFIG_ENV}, else searched upwards)")
    common.add_argument("--ideas", help="the ideas section (else the one folders section with page idea.md)")
    common.add_argument("--slug", required=True, help=f"the idea's folder name, at most {SLUG_MAX} characters")
    common.add_argument("--style", choices=("plain", "styled"), help="callout look (else config, else styled)")
    common.add_argument("--labels", help="a JSON file with label overrides for idea.md")
    common.add_argument("--blueprints-dir", help="folder name for blueprints (else config, else blueprints)")
    common.add_argument("--reviews-dir", help="folder name for reviews (else config, else reviews)")
    save = argparse.ArgumentParser(add_help=False)
    save.add_argument("--title", required=True, help="the idea's title")
    save.add_argument("--file", required=True, help="the text to save (see the module help)")
    save.add_argument("--run", help="the run folder (default: the input's folder when it holds meta.md)")
    save.add_argument("--when", help="the run's start, YYYY-MM-DD-HHMM (default: from the run folder, else now)")
    save.add_argument("--version", type=int, help="the version (default: see the module help)")
    p = argparse.ArgumentParser(prog="idea_page.py", description="Save blueprints and reviews into an idea's "
                                "folder and rebuild its idea.md.", epilog="Details: the module docstring.")
    sub = p.add_subparsers(dest="cmd", required=True, metavar="command")
    pb = sub.add_parser("save-blueprint", parents=[common, save], help="save a blueprint, then rebuild idea.md")
    pb.add_argument("--head", help="the header lines and '## The brief' section, as Markdown")
    pb.add_argument("--size", choices=("full", "light"), default="full")
    pr = sub.add_parser("save-review", parents=[common, save], help="save a Council review, then rebuild idea.md")
    pr.add_argument("--verdict", required=True, help="verdict.json from council_score.py decide")
    pr.add_argument("--size", choices=("full", "light"), help="default: light for a jury of one, else full")
    pq = sub.add_parser("rebuild", parents=[common], help="rebuild idea.md from the folder")
    pq.add_argument("--title", help="the idea's title (else from idea.md or the newest run file)")
    return p


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as e:  # --help exits 0, a usage error 2
        return 0 if not e.code else 2
    try:
        s = load_settings(args)
        check_slug(args.slug)
        check_status_words(s)
        if args.cmd == "save-blueprint":
            written = save_blueprint(s, args)
        elif args.cmd == "save-review":
            written = save_review(s, args)
        else:
            written = [rebuild(s, args.slug, args.title)]
    except UsageError as e:
        print(f"idea_page: {e}", file=sys.stderr)
        return 2
    except InputError as e:
        print(f"idea_page: {e}", file=sys.stderr)
        return 1
    for path in written:
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
