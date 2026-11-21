#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6"]
# ///
"""Deterministic maintenance for an Obsidian vault run as an LLM wiki: lint, fix, reindex, stats, log.

Usage (from anywhere inside the workspace that holds wiki.config.json):
    uv run scripts/wiki.py lint                 # links and frontmatter, active content only
    uv run scripts/wiki.py lint --all -v        # the whole vault, every finding listed
    uv run scripts/wiki.py lint --fix           # rewrite what is deterministic, reindex, then lint
    uv run scripts/wiki.py reindex [section]    # rebuild the AUTO-INDEX block of section indexes
    uv run scripts/wiki.py stats                # per section: pages, no author, short links, tags
    uv run scripts/wiki.py log <op> "<title>" ["<line>" ...]   # a block in the operations log

The config is found by --config, else the NEST_WIKI_CONFIG environment variable, else the
first wiki.config.json walking up from the current directory. WIKI-CONFIG.md documents it.

Errors (exit code 1): broken or ambiguous links, broken embeds, missing frontmatter or fields,
invalid YAML, an unknown status. Warnings (listed, exit code 0): a bare link in a content
section, a missing or unknown author, a stale active page, an unsourced page by an assistant,
repeated links in running text, the same title in several sections, an unknown kind.
Exit code 2: a usage or config problem.
"""
from __future__ import annotations

import argparse
import codecs
import fnmatch
import json
import os
import posixpath
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

CONFIG_NAME = "wiki.config.json"
CONFIG_ENV = "NEST_WIKI_CONFIG"
INDEX = "index.md"
INDEX_TYPES = ("manual", "none", "flat", "by_kind", "projects", "references", "folders")
COLLECTION_INDEXES = ("index", "00-index")

DEFAULTS: dict[str, Any] = {
    "wiki_dir": "wiki",
    "index_marker": "<!-- AUTO-INDEX -->",
    "index_empty": "_Nothing here yet._",
    "log": {
        "file": "log.md",
        "marker": "<!-- Begin of the log -->",
        "title": "Operations log",
        "ops": ["ingest", "distill", "query", "lint", "migrate"],
    },
    "status_words": ["draft", "active", "done", "parked", "archived", "question"],
    # Which of the status words plays which role, so the words can be in any language.
    "status_roles": {"active": "active", "draft": "draft", "question": "question"},
    # The inbox kind that marks a question (kinds can be in any language too).
    "question_kind": "question",
    "required_fields": ["title", "tags", "category", "status"],
    "authors": ["user", "assistant", "claude"],
    "author_required_from": None,
    "created_fields": ["created", "date", "ingest-date"],
    "unsourced_authors": [],
    "source_fields": ["sources", "source-url"],
    "stale_days": 90,
    "raw_folders": ["_inbox"],
    "nav_headings": ["related", "sources", "see also", "links", "references", "further reading"],
    "repeat_link_exempt": ["index.md", "*/index.md", "log.md", "*/log.md"],
    "sections": {},
    "content_sections": [],
}

SECTION_DEFAULTS: dict[str, Any] = {
    "index": "flat",
    "lint": True,
    "lint_active": True,
    "frontmatter": True,
    "raw": False,
    "archive": False,
    "dated": False,
    "stale": False,
    "sourced": False,
    "raw_subdirs": [],
    "kinds": {},
    "other_label": "Other",
    "readme": "README.md",
    "page": "README.md",
    "fields": ["status"],
    "heading": "",
    "labels": {},
    "ingest_log": "log.md",
    "status_words": None,
}

REFERENCE_LABELS = {
    "collections": "Collections and pages",
    "pages": "pages",
    "raw": "Raw sources",
    "ingest_log": "Ingest log",
}

ERROR_KEYS = ("broken-links", "ambiguous-links", "broken-embeds", "no-frontmatter",
              "missing-fields", "invalid-yaml", "unknown-status")
WARNING_KEYS = ("short-links", "no-author", "stale-active", "unsourced", "repeated-links",
                "duplicate-titles", "unknown-kind")


class ConfigError(Exception):
    """No config, or one that does not parse or validate."""


# Config

@dataclass
class Config:
    path: Path
    vault: Path
    data: dict[str, Any]
    sections: dict[str, dict[str, Any]] = field(default_factory=dict)

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    @property
    def marker(self) -> str:
        return self.data["index_marker"]

    @property
    def content(self) -> set[str]:
        return set(self.data["content_sections"])


def find_config(flag: str | None = None, cwd: Path | None = None) -> Path:
    """--config, else $NEST_WIKI_CONFIG, else the first wiki.config.json up from cwd."""
    if flag:
        p = Path(flag).expanduser()
        if not p.is_file():
            raise ConfigError(f"config not found: {p}")
        return p.resolve()
    env = os.environ.get(CONFIG_ENV)
    if env:
        p = Path(env).expanduser()
        if not p.is_file():
            raise ConfigError(f"config not found: {p} (from {CONFIG_ENV})")
        return p.resolve()
    here = (cwd or Path.cwd()).resolve()
    for d in (here, *here.parents):
        if (d / CONFIG_NAME).is_file():
            return d / CONFIG_NAME
    raise ConfigError(f"no {CONFIG_NAME} found from {here} upwards; pass --config or set {CONFIG_ENV} "
                      f"(start from wiki.config.example.json)")


def _check_list(name: str, value: Any) -> None:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ConfigError(f"'{name}' must be a list of strings")


def load_config(path: Path | str) -> Config:
    path = Path(path).expanduser().resolve()
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as e:
        raise ConfigError(f"cannot read {path}: {e}") from e
    if not isinstance(raw, dict):
        raise ConfigError(f"{path}: the config must be a JSON object")
    data = {**DEFAULTS, **{k: v for k, v in raw.items() if not k.startswith("_")}}
    data["log"] = {**DEFAULTS["log"], **(raw.get("log") or {})}
    roles = raw.get("status_roles") or {}
    if not isinstance(roles, dict) or not all(isinstance(v, str) for v in roles.values()):
        raise ConfigError("'status_roles' must be an object of role to status word")
    unknown_roles = sorted(set(roles) - set(DEFAULTS["status_roles"]))
    if unknown_roles:
        raise ConfigError(f"'status_roles': unknown role(s) {', '.join(unknown_roles)}; "
                          f"roles are {', '.join(DEFAULTS['status_roles'])}")
    data["status_roles"] = {**DEFAULTS["status_roles"], **roles}
    if not isinstance(data["question_kind"], str):
        raise ConfigError("'question_kind' must be a string")
    for key in ("status_words", "required_fields", "authors", "created_fields", "unsourced_authors",
                "source_fields", "raw_folders", "nav_headings", "repeat_link_exempt", "content_sections"):
        _check_list(key, data[key])
    _check_list("log.ops", data["log"]["ops"])
    missing = sorted({w for w in data["status_roles"].values() if w not in data["status_words"]})
    if missing:
        raise ConfigError(f"'status_roles' uses word(s) not in 'status_words': {', '.join(missing)}")
    if data["author_required_from"] is not None:
        try:
            date.fromisoformat(str(data["author_required_from"]))
        except ValueError as e:
            raise ConfigError("'author_required_from' must be an ISO date (YYYY-MM-DD) or null") from e
    if not isinstance(data["stale_days"], int):
        raise ConfigError("'stale_days' must be a whole number")
    if not isinstance(data["sections"], dict):
        raise ConfigError("'sections' must be an object of folder name to settings")
    sections: dict[str, dict[str, Any]] = {}
    for name, sec in data["sections"].items():
        if not isinstance(sec, dict):
            raise ConfigError(f"section '{name}' must be an object")
        s = {**SECTION_DEFAULTS, **sec}
        if s["index"] not in INDEX_TYPES:
            raise ConfigError(f"section '{name}': unknown index type '{s['index']}'; one of {', '.join(INDEX_TYPES)}")
        if not isinstance(s["kinds"], dict):
            raise ConfigError(f"section '{name}': 'kinds' must be an object of kind to label")
        for key in ("raw_subdirs", "fields"):
            _check_list(f"sections.{name}.{key}", s[key])
        if s["status_words"] is not None:
            _check_list(f"sections.{name}.status_words", s["status_words"])
        sections[name] = s
    unknown = [c for c in data["content_sections"] if c not in sections]
    if unknown:
        raise ConfigError(f"content_sections not in sections: {', '.join(unknown)}")
    vault = Path(str(data["wiki_dir"])).expanduser()
    if not vault.is_absolute():
        vault = path.parent / vault
    return Config(path=path, vault=vault.resolve(), data=data, sections=sections)


# Files (utf-8, line endings kept as they were)

def read_text(path: Path) -> str:
    """The file as text with \\n line endings, whatever the file uses; a BOM is dropped."""
    text = path.read_bytes().decode("utf-8", errors="replace")
    text = text.removeprefix("﻿")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def write_text(path: Path, text: str) -> None:
    """Write text, keeping the line endings (CRLF or LF) and BOM of the file it replaces."""
    nl, bom = "\n", b""
    if path.exists():
        old = path.read_bytes()
        if b"\r\n" in old:
            nl = "\r\n"
        if old.startswith(codecs.BOM_UTF8):
            bom = codecs.BOM_UTF8
    path.write_bytes(bom + text.replace("\n", nl).encode("utf-8"))


# Frontmatter, titles and summaries

def parse_frontmatter(text: str) -> dict | None:
    """The YAML between the opening --- lines, or None when there is none or it does not parse."""
    if not text.startswith("---\n") or "\n---" not in text[4:]:
        return None
    try:
        data = yaml.safe_load(text[4:].split("\n---", 1)[0])
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


def read_frontmatter(path: Path) -> dict:
    """The frontmatter of a page with scalar values as strings ({} when there is none)."""
    try:
        fm = parse_frontmatter(read_text(path)) or {}
    except OSError:
        return {}
    return {str(k): v if isinstance(v, (list, dict)) else str(v) for k, v in fm.items()}


def title_of(path: Path) -> str:
    return str(read_frontmatter(path).get("title") or path.stem)


SUMMARY_CHARS = 120
_LINK = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
_MDLINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")


def summary_of(path: Path) -> str:
    """One line for the index: the frontmatter `summary`, else the first plain paragraph or the
    text of the first callout after the frontmatter, whichever comes first. Headings, lists,
    tables, embeds and comments are skipped; cut at SUMMARY_CHARS on a word boundary."""
    try:
        text = read_text(path)
    except OSError:
        return ""
    fm = parse_frontmatter(text) or {}
    line = str(fm.get("summary") or "").strip()
    if not line:
        body = text[4:].split("\n---", 1)[1] if text.startswith("---\n") and "\n---" in text[4:] else text
        for pattern in (r"%%.*?%%", r"<!--.*?-->", r"<%.*?%>", r"```.*?```"):
            body = re.sub(pattern, "", body, flags=re.DOTALL)
        for block in (b.strip() for b in re.split(r"\n\s*\n", body) if b.strip()):
            first = block.splitlines()[0].strip()
            if first.startswith(">"):
                lines = [ln.strip().lstrip(">").strip() for ln in block.splitlines()]
                lines = [ln for ln in lines if ln and not re.match(r"^\[![\w-]+\][+-]?", ln)]
                line = " ".join(lines)
                if line:
                    break
                continue
            if first.startswith(("#", "|", "- ", "* ", "![[", "<", "---")) or re.match(r"^\d+\. ", first):
                continue
            line = " ".join(block.splitlines())
            break
    line = _LINK.sub(lambda m: (m.group(2) or m.group(1).rsplit("/", 1)[-1]), line)
    line = _MDLINK.sub(r"\1", line)
    line = " ".join(line.replace("`", "").replace("**", "").replace("*", "").split())
    if len(line) > SUMMARY_CHARS:
        line = line[:SUMMARY_CHARS].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return line


def page_line(vault_path: str, page: Path) -> str:
    """`- [[path|title]]: summary`, the line every index writes for a page."""
    s = summary_of(page)
    return f"- [[{vault_path}|{title_of(page)}]]" + (f": {s}" if s else "")


def field_line(link: str, page: Path, fields: list[str]) -> str:
    """`- [[path|title]]: *value · value*` from the page's frontmatter fields (projects, folders)."""
    fm = read_frontmatter(page)
    vals = [str(fm[f]) for f in fields if fm.get(f) not in (None, "", "None")]
    return f"- {link}" + (f": *{' · '.join(vals)}*" if vals else "")


# Indexes

def _pages(d: Path) -> list[Path]:
    return [p for p in d.glob("*.md") if p.name != INDEX]


def _dirs(d: Path) -> list[Path]:
    return sorted((p for p in d.iterdir() if p.is_dir() and not p.name.startswith(".")), key=lambda p: p.name)


def index_flat(cfg: Config, name: str, sec: dict, d: Path) -> str:
    pages = sorted(_pages(d), key=lambda p: p.name, reverse=bool(sec["dated"]))
    return "\n".join(page_line(f"{name}/{p.stem}", p) for p in pages)


def index_by_kind(cfg: Config, name: str, sec: dict, d: Path) -> str:
    """Grouped by the `kind` field in the order of `kinds`, the rest under `other_label`;
    alphabetical by title within a group."""
    kinds: dict[str, str] = sec["kinds"]
    groups: dict[str | None, list[tuple[str, Path]]] = {k: [] for k in kinds}
    groups[None] = []
    for p in sorted(_pages(d)):
        kind = str(read_frontmatter(p).get("kind") or "")
        groups[kind if kind in kinds else None].append((title_of(p), p))
    out = []
    for k, items in groups.items():
        if items:
            label = kinds[k] if k is not None else sec["other_label"]
            ordered = sorted(items, key=lambda x: (x[0].lower(), x[1].name))
            out.append(f"## {label}\n\n" + "".join(page_line(f"{name}/{p.stem}", p) + "\n" for _, p in ordered))
    return "\n".join(out)


def index_projects(cfg: Config, name: str, sec: dict, d: Path) -> str:
    """One line per project folder that has a README, with its `fields`."""
    readme = sec["readme"]
    stem = Path(readme).stem
    rows = []
    for sub in _dirs(d):
        rm = sub / readme
        if rm.exists():
            rows.append(field_line(f"[[{name}/{sub.name}/{stem}|{title_of(rm)}]]", rm, sec["fields"]))
    if not rows:
        return ""
    heading = sec["heading"] or "Projects"
    return f"## {heading}\n\n" + "\n".join(rows) + "\n"


def index_references(cfg: Config, name: str, sec: dict, d: Path) -> str:
    """Collections (folders) with their page count, the loose pages, the raw sources, the ingest log."""
    labels = {**REFERENCE_LABELS, **sec["labels"]}
    raw_subdirs = set(sec["raw_subdirs"])
    log_name = sec["ingest_log"]
    body = f"## {sec['heading'] or labels['collections']}\n\n"
    for item in sorted(d.iterdir(), key=lambda p: p.name):
        if item.name.startswith("."):
            continue
        if item.is_dir() and item.name not in raw_subdirs:
            idx = next((c for c in COLLECTION_INDEXES if (item / f"{c}.md").exists()), None)
            cnt = len(list(item.glob("*.md")))
            body += (f"- [[{name}/{item.name}/{idx}|{item.name}]] ({cnt} {labels['pages']})\n" if idx
                     else f"- `{item.name}/` ({cnt} {labels['pages']})\n")
        elif item.is_file() and item.suffix == ".md" and item.name not in (INDEX, log_name):
            body += page_line(f"{name}/{item.stem}", item) + "\n"
    for sub in sec["raw_subdirs"]:
        raw = sorted((d / sub).glob("*.md")) if (d / sub).is_dir() else []
        if raw:
            body += f"\n## {labels['raw']} (`{sub}/`)\n\n" + "".join(
                f"- [[{name}/{sub}/{p.stem}|{title_of(p)}]]\n" for p in raw)
    if log_name and (d / log_name).exists():
        body += f"\n- [[{name}/{Path(log_name).stem}|{labels['ingest_log']}]]\n"
    return body


def index_folders(cfg: Config, name: str, sec: dict, d: Path) -> str:
    """One line per subfolder that has the main `page`, most recently `updated` first, then the
    loose pages newest name first."""
    page = sec["page"]
    stem = Path(page).stem
    folders = sorted((f for f in _dirs(d) if (f / page).exists()),
                     key=lambda f: (str(read_frontmatter(f / page).get("updated") or ""), f.name), reverse=True)
    loose = sorted(_pages(d), key=lambda p: p.name, reverse=True)
    return "\n".join([field_line(f"[[{name}/{f.name}/{stem}|{title_of(f / page)}]]", f / page, sec["fields"])
                      for f in folders] + [page_line(f"{name}/{p.stem}", p) for p in loose])


INDEXERS = {"flat": index_flat, "by_kind": index_by_kind, "projects": index_projects,
            "references": index_references, "folders": index_folders}


def update_index(cfg: Config, name: str) -> bool:
    """Rebuild the block under the marker in <section>/index.md; the text above it stays.
    Left alone (False): a manual or none section, a section without index.md, and a
    hand-written index (links, no marker)."""
    sec = cfg.sections.get(name)
    if not sec or sec["index"] not in INDEXERS:
        return False
    d = cfg.vault / name
    idx = d / INDEX
    if not idx.is_file():
        return False
    cur = read_text(idx)
    marker = cfg.marker
    if marker not in cur and "[[" in cur:
        return False
    body = INDEXERS[sec["index"]](cfg, name, sec, d) or cfg["index_empty"]
    header = cur.split(marker)[0].rstrip()
    new = (header + "\n\n" if header else "") + marker + "\n\n" + body.rstrip() + "\n"
    if new != cur:
        write_text(idx, new)
    return True


def reindex(cfg: Config, only: str | None = None) -> list[str]:
    names = [only] if only else list(cfg.sections)
    return [n for n in names if update_index(cfg, n)]


# The operations log

def append_log(cfg: Config, op: str, title: str, lines: list[str] | tuple[str, ...] = (),
               when: datetime | None = None) -> Path:
    """One block right under the log marker, newest first: "## YYYY-MM-DD HH:MM · op · title"
    and a bullet per line. A vault without the log file gets one with a standard head."""
    lc = cfg["log"]
    if op not in lc["ops"]:
        raise ValueError(f"unknown log operation {op!r}; one of {', '.join(lc['ops'])}")
    when = when or datetime.now()
    log = cfg.vault / lc["file"]
    mark = lc["marker"]
    if log.exists():
        text = read_text(log)
    else:
        log.parent.mkdir(parents=True, exist_ok=True)
        text = (f"---\ntitle: {json.dumps(lc['title'], ensure_ascii=False)}\ncategory: log\nstatus: active\ntags: []\n---\n\n"
                f"# {lc['title']}\n\nAppend-only, newest first.\n\n{mark}\n")
    if mark not in text:
        m = re.match(r"---\n.*?\n---\n", text, re.DOTALL)
        cut = m.end() if m else 0
        text = text[:cut] + "\n" + mark + "\n" + text[cut:]
    title = " ".join(str(title).split())
    block = f"## {when:%Y-%m-%d %H:%M} · {op} · {title}\n" + "".join(
        f"- {' '.join(str(ln).split())}\n" for ln in lines if str(ln).strip())
    head, _, tail = text.partition(mark)
    write_text(log, head + mark + "\n\n" + block + "\n" + tail.lstrip("\n"))
    return log


# The vault catalogue and links

CF = re.compile(r"```.*?```", re.DOTALL)
IC = re.compile(r"`[^`\n]*`")  # inline code: a `[[link]]` quoted there is not one
WL = re.compile(r"(?<!\!)\[\[([^\]]+?)\]\]")
EM = re.compile(r"\!\[\[([^\]]+?)\]\]")
TOKEN = re.compile(r"```.*?```|`[^`\n]*`|(?<!\!)\[\[([^\]]+?)\]\]", re.DOTALL)


@dataclass
class Catalog:
    files: list[str]
    by_rel: set[str]
    by_base: dict[str, list[str]]
    roots: set[str]


def all_files(vault: Path) -> list[str]:
    """Every file as a vault path with forward slashes; hidden folders (.obsidian, .git, .trash) skipped."""
    out = []
    for root, dirs, files in os.walk(vault):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for fn in sorted(files):
            out.append((Path(root) / fn).relative_to(vault).as_posix())
    return out


def catalog(cfg: Config) -> Catalog:
    files = all_files(cfg.vault)
    by_rel: set[str] = set()
    by_base: dict[str, list[str]] = {}
    for rel in files:
        by_rel.add(rel)
        if rel.endswith(".md"):
            by_rel.add(rel[:-3])
        base = posixpath.basename(rel)
        key = (base.removesuffix(".md")).lower()
        by_base.setdefault(key, []).append(rel)
    roots = {p.stem.lower() for p in cfg.vault.glob("*.md")}
    return Catalog(files, by_rel, by_base, roots)


def is_short(target: str, roots: set[str]) -> bool:
    """A bare [[name]]: no folder in it, and not a page in the vault root (its vault path is its name)."""
    name = target.split("|")[0].split("#")[0].strip()
    return bool(name) and "/" not in name and not name.startswith(".") and name.lower() not in roots


def resolve(cat: Catalog, target: str, src: str = "") -> str:
    """'ok', 'ambiguous' or 'broken'. A link with a path is tried as a vault path and relative to
    the linking file; a bare name resolves when exactly one file carries it."""
    t = target.strip().rstrip("\\").split("#")[0].strip()  # [[page\|alias]] in a table: the pipe is escaped
    if not t:
        return "ok"
    here = posixpath.normpath(posixpath.join(posixpath.dirname(src), t)) if src and "/" in t else ""
    for c in (t, t + ".md", t.lstrip("./"), here, here + ".md" if here else ""):
        if c and c in cat.by_rel:
            return "ok"
    base = posixpath.basename(t)
    base = (base.removesuffix(".md")).lower()
    n = len(cat.by_base.get(base, []))
    return "ok" if n == 1 else ("ambiguous" if n > 1 else "broken")


def section_of(cfg: Config, rel: str) -> tuple[str | None, dict | None]:
    if "/" not in rel:
        return None, None
    top = rel.split("/", 1)[0]
    return top, cfg.sections.get(top)


def in_raw_folder(cfg: Config, rel: str) -> bool:
    """Below the section level, inside a folder named in raw_folders (a nested _inbox)."""
    return any(p in cfg["raw_folders"] for p in rel.split("/")[1:-1])


def is_raw(cfg: Config, rel: str) -> bool:
    _, sec = section_of(cfg, rel)
    parts = rel.split("/")
    if sec and (sec["raw"] or (len(parts) > 2 and parts[1] in sec["raw_subdirs"])):
        return True
    return in_raw_folder(cfg, rel)


# Fix

def fix(cfg: Config, verbose: bool = False) -> int:
    """Rewrite what needs no judgement: a bare [[name]] in a content section becomes the vault path
    when exactly one page carries the name, and `category` becomes the section folder. Code spans,
    embeds and raw material are left alone. Returns the number of files changed."""
    cat = catalog(cfg)
    changed = 0
    for rel in cat.files:
        name, sec = section_of(cfg, rel)
        if not rel.endswith(".md") or sec is None or not sec["lint"] or is_raw(cfg, rel):
            continue
        path = cfg.vault / rel
        text = read_text(path)
        new = text
        if name in cfg.content:
            def swap(m: re.Match) -> str:
                target = m.group(1)
                if target is None or not is_short(target, cat.roots):
                    return m.group(0)
                link, _, alias = target.partition("|")
                base, _, anchor = link.partition("#")
                hits = [h for h in cat.by_base.get(base.strip().lower(), []) if h.endswith(".md")]
                if len(hits) != 1:
                    return m.group(0)
                return ("[[" + hits[0][:-3] + ("#" + anchor if anchor else "")
                        + ("|" + alias if alias else "|" + base.strip()) + "]]")
            new = TOKEN.sub(swap, new)
        if sec["frontmatter"] and new.startswith("---"):
            fm = parse_frontmatter(new)
            if fm is None or not isinstance(fm.get("category"), (list, dict)):
                head, sep, body = new.partition("\n---")
                head = re.sub(r"(?m)^category:.*$", f"category: {name}", head, count=1)
                new = head + sep + body
        if new != text:
            write_text(path, new)
            changed += 1
            if verbose:
                print(f"  fixed: {rel}")
    return changed


# Lint

@dataclass
class LintResult:
    scope: str
    counts: dict[str, int] = field(default_factory=lambda: {k: 0 for k in ERROR_KEYS + WARNING_KEYS})
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(self.counts[k] for k in ERROR_KEYS)

    def error(self, key: str, msg: str) -> None:
        self.counts[key] += 1
        self.errors.append(msg)

    def warn(self, key: str, msg: str) -> None:
        self.counts[key] += 1
        self.warnings.append(msg)

    def report(self, verbose: bool = False) -> str:
        out = [f"lint ({self.scope}): " + " ".join(f"{k}={self.counts[k]}" for k in ERROR_KEYS),
               "  warnings: " + " ".join(f"{k}={self.counts[k]}" for k in WARNING_KEYS)]
        if verbose:
            out += [f"  - {e}" for e in self.errors] + [f"  ~ {w}" for w in self.warnings]
        return "\n".join(out)


def _prose_only(body: str, nav: re.Pattern | None) -> str:
    """The body without frontmatter, table rows and navigation sections (Related, Sources, ...):
    a second link there is a list entry, not a repeat in the running text."""
    if body.startswith("---"):
        end = body.find("\n---", 3)
        if end != -1:
            body = body[end + 4:]
    out, skip = [], False
    for line in body.splitlines():
        if line.startswith("#"):
            skip = bool(nav and nav.search(line))
            continue
        if skip or line.lstrip().startswith("|"):
            continue
        out.append(line)
    return "\n".join(out)


def lint(cfg: Config, all_pages: bool = False) -> LintResult:
    cat = catalog(cfg)
    res = LintResult("whole vault" if all_pages else "active content")
    content = cfg.content
    statuses = set(cfg["status_words"])
    authors = set(cfg["authors"])
    since = cfg["author_required_from"]
    stale_days = cfg["stale_days"]
    nav = re.compile("|".join(re.escape(h) for h in cfg["nav_headings"]), re.IGNORECASE) if cfg["nav_headings"] else None
    exempt = cfg["repeat_link_exempt"]
    titles: dict[str, list[str]] = {}
    today = date.today()
    for rel in (f for f in cat.files if f.endswith(".md")):
        name, sec = section_of(cfg, rel)
        if sec is not None and not sec["lint"]:
            continue
        if not all_pages and ((sec is not None and not sec["lint_active"]) or in_raw_folder(cfg, rel)):
            continue
        t = read_text(cfg.vault / rel)
        body = IC.sub("", CF.sub("", t))
        fname = rel.rsplit("/", 1)[-1]
        checked = sec is not None and sec["frontmatter"]
        if checked and not t.startswith("---"):
            res.error("no-frontmatter", f"no frontmatter: {rel}")
        elif checked:
            block = t.split("---", 2)[1]
            missing = [k for k in cfg["required_fields"] if not re.search(r"(?m)^" + re.escape(k) + r":", block)]
            if missing:
                res.error("missing-fields", f"missing fields ({', '.join(missing)}): {rel}")
            fm = parse_frontmatter(t)
            allowed = set(sec["status_words"]) if sec["status_words"] is not None else statuses
            if fm is None:
                res.error("invalid-yaml", f"invalid YAML (Obsidian shows no properties): {rel}")
            elif str(fm.get("status")) not in allowed:
                res.error("unknown-status", f"unknown status '{fm.get('status')}': {rel}")
            if fm is not None and fname != INDEX:
                author = fm.get("author")
                created = next((str(fm[k]) for k in cfg["created_fields"] if fm.get(k)), "")
                if authors and (since is None or created >= str(since)) and author not in authors:
                    res.warn("no-author", f"no author: {rel}" if not author else f"unknown author '{author}': {rel}")
                if not sec["raw"] and not sec["archive"] and fname not in (sec["readme"], cfg["log"]["file"], "log.md"):
                    titles.setdefault(str(fm.get("title") or "").strip().lower(), []).append(rel)
                if sec["stale"] and str(fm.get("status")) == cfg["status_roles"]["active"]:
                    try:
                        age = (today - date.fromisoformat(str(fm.get("updated"))[:10])).days
                    except (TypeError, ValueError):
                        age = -1
                    if age > stale_days:
                        res.warn("stale-active", f"{cfg['status_roles']['active']} but not updated for {age} days: {rel}")
                if (sec["sourced"] and author in cfg["unsourced_authors"]
                        and not any(fm.get(k) for k in cfg["source_fields"])):
                    res.warn("unsourced", f"by {author} without sources: {rel}")
                kind = fm.get("kind")
                if sec["kinds"] and kind not in (None, "") and str(kind) not in sec["kinds"]:
                    res.warn("unknown-kind", f"unknown kind '{kind}': {rel}")
        if name in content and not any(fnmatch.fnmatchcase(rel, p) for p in exempt):
            seen: dict[str, int] = {}
            for m in WL.finditer(_prose_only(body, nav)):
                key = m.group(1).split("|")[0].split("#")[0].strip().lower()
                seen[key] = seen.get(key, 0) + 1
            for key, n in seen.items():
                if n > 1:
                    res.warn("repeated-links", f"{n}x linked to [[{key}]] (the first mention is enough): {rel}")
        for m in WL.finditer(body):
            target = m.group(1).split("|")[0]
            if name in content and is_short(m.group(1), cat.roots):
                res.warn("short-links", f"short link [[{target}]]: {rel}")
            r = resolve(cat, target, rel)
            if r == "broken":
                res.error("broken-links", f"broken link [[{target}]]: {rel}")
            elif r == "ambiguous":
                res.error("ambiguous-links", f"ambiguous link [[{target}]]: {rel}")
        for m in EM.finditer(body):
            target = m.group(1).split("|")[0]
            if resolve(cat, target, rel) == "broken":
                res.error("broken-embeds", f"broken embed ![[{target}]]: {rel}")
    for title, rels in titles.items():
        if title and len({r.split("/")[0] for r in rels}) > 1:
            res.warn("duplicate-titles", f"same title in several sections: {', '.join(sorted(rels))}")
    return res


# Stats

def stats(cfg: Config) -> dict:
    """Per section: pages, pages without a known author, short links, unique tags; plus the tags used
    once (merge candidates), open questions and the size of the indexes."""
    cat = catalog(cfg)
    rows: dict[str, dict] = {}
    tags: dict[str, int] = {}
    questions = active = 0
    authors = set(cfg["authors"])
    idx_pages = [cfg.vault / INDEX] + [cfg.vault / n / INDEX for n, s in cfg.sections.items() if not s["archive"]]
    index_chars = sum(len(read_text(p)) for p in idx_pages if p.is_file())
    for rel in cat.files:
        name, sec = section_of(cfg, rel)
        if (not rel.endswith(".md") or sec is None or not sec["lint"] or sec["archive"]
                or in_raw_folder(cfg, rel) or rel.endswith("/" + INDEX)):
            continue
        row = rows.setdefault(name, {"pages": 0, "no_author": 0, "short_links": 0, "tags": set()})
        text = read_text(cfg.vault / rel)
        fm = parse_frontmatter(text) or {}
        status = str(fm.get("status"))
        row["pages"] += 1
        if name in cfg.content and status in set(cfg["status_roles"].values()):
            active += 1
        if fm.get("author") not in authors:
            row["no_author"] += 1
        if sec["raw"] and (status == cfg["status_roles"]["question"]
                           or str(fm.get("kind")) == cfg["question_kind"]):
            questions += 1
        for tag in fm.get("tags") if isinstance(fm.get("tags"), list) else []:
            tag = str(tag).strip().lower()
            if tag:
                row["tags"].add(tag)
                tags[tag] = tags.get(tag, 0) + 1
        if name in cfg.content:
            body = IC.sub("", CF.sub("", text))
            row["short_links"] += sum(1 for m in WL.finditer(body) if is_short(m.group(1), cat.roots))
    once = sorted(t for t, n in tags.items() if n == 1)
    return {"sections": {c: {**r, "tags": len(r["tags"])} for c, r in rows.items()}, "tags": tags,
            "once": once, "questions": questions, "active": active, "index_chars": index_chars}


def print_stats(s: dict) -> None:
    print(f"{'section':<18}{'pages':>7}{'no author':>11}{'short links':>13}{'tags':>6}")
    for name in sorted(s["sections"]):
        r = s["sections"][name]
        print(f"{name:<18}{r['pages']:>7}{r['no_author']:>11}{r['short_links']:>13}{r['tags']:>6}")
    once = s["once"]
    tail = (": " + ", ".join(once[:40]) + (" ..." if len(once) > 40 else "")) if once else ""
    print(f"tags: {len(s['tags'])} unique, {len(once)} used once{tail}")
    print(f"open questions (status question in raw sections): {s['questions']}")
    print(f"active pages: {s['active']} (around 300 a search index becomes worth considering); "
          f"index.md plus section indexes: {s['index_chars']} characters")


# CLI

def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", default=argparse.SUPPRESS,
                        help=f"path to {CONFIG_NAME} (else ${CONFIG_ENV}, else searched upwards from cwd)")
    p = argparse.ArgumentParser(prog="wiki.py", parents=[common],
                                description="Lint, fix, reindex and log an Obsidian LLM wiki, driven by wiki.config.json.")
    sub = p.add_subparsers(dest="cmd", required=True, metavar="command")
    pl = sub.add_parser("lint", parents=[common], help="check links and frontmatter (exit 1 on errors)")
    pl.add_argument("--all", action="store_true", help="the whole vault, not only active content")
    pl.add_argument("-v", "--verbose", action="store_true", help="list every finding")
    pl.add_argument("--fix", action="store_true", help="first rewrite bare links and category, then reindex")
    pr = sub.add_parser("reindex", parents=[common], help="rebuild the AUTO-INDEX block of section indexes")
    pr.add_argument("section", nargs="?", help="only this section")
    sub.add_parser("stats", parents=[common], help="pages, authors, short links and tags per section")
    pg = sub.add_parser("log", parents=[common], help="add a block to the operations log, newest first")
    pg.add_argument("op", help="the operation (log.ops in the config)")
    pg.add_argument("title", help="the block title")
    pg.add_argument("lines", nargs="*", help="one bullet per line")
    return p


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # Windows consoles default to a code page
        except (AttributeError, ValueError):
            pass
    args = build_parser().parse_args(argv)
    try:
        cfg = load_config(find_config(getattr(args, "config", None)))
    except ConfigError as e:
        print(f"wiki: {e}", file=sys.stderr)
        return 2
    if not cfg.vault.is_dir():
        print(f"wiki: vault not found: {cfg.vault} (wiki_dir in {cfg.path})", file=sys.stderr)
        return 2
    if args.cmd == "lint":
        if args.fix:
            print(f"fix: {fix(cfg, args.verbose)} files rewritten")
            print("reindex: " + (", ".join(reindex(cfg)) or "nothing to rebuild"))
        res = lint(cfg, args.all)
        print(res.report(args.verbose))
        return 1 if res.error_count else 0
    if args.cmd == "reindex":
        if args.section:
            sec = cfg.sections.get(args.section)
            if sec is None:
                print(f"wiki: unknown section '{args.section}'; one of {', '.join(cfg.sections)}", file=sys.stderr)
                return 2
            if sec["index"] not in INDEXERS:
                print(f"reindex: {args.section} has index type '{sec['index']}', left alone")
                return 0
        done = reindex(cfg, args.section)
        print("reindex: " + (", ".join(done) or "nothing to rebuild"))
        return 0
    if args.cmd == "stats":
        print_stats(stats(cfg))
        return 0
    if args.cmd == "log":
        if args.op not in cfg["log"]["ops"]:
            print(f"wiki: unknown operation '{args.op}'; one of {', '.join(cfg['log']['ops'])}", file=sys.stderr)
            return 2
        append_log(cfg, args.op, args.title, args.lines)
        print(f"log: {args.op} · {' '.join(args.title.split())}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
