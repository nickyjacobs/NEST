"""Tests for wiki.py on a fixture vault built in tmp_path from wiki.config.example.json."""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

import pytest
import wiki

EXAMPLE = Path(__file__).resolve().parent.parent / "wiki.config.example.json"


def page(title: str, *, category: str, status: str = "active", body: str = "", extra: str = "",
         tags: str = "[demo]", author: str = "claude") -> str:
    return (f"---\ntitle: {title}\ntags: {tags}\ncategory: {category}\nstatus: {status}\n"
            f"author: {author}\ncreated: 2026-01-01\nupdated: 2099-01-01\n{extra}---\n\n# {title}\n\n{body}\n")


def write(vault: Path, rel: str, text: str) -> Path:
    p = vault / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="")
    return p


def index_head(title: str, category: str) -> str:
    return f"---\ntitle: {title}\ntags: [index]\ncategory: {category}\nstatus: active\n---\n\n# {title}\n\nIntro text.\n\n"


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    """A clean vault: lint reports zero errors and zero warnings."""
    shutil.copy(EXAMPLE, tmp_path / "wiki.config.json")
    v = tmp_path / "wiki"
    write(v, "index.md", "# Index\n\n- [[20-knowledge/index|Knowledge]]\n")
    write(v, "00-context/index.md", index_head("Context", "00-context") + "- [[00-context/about|About]]\n")
    write(v, "00-context/about.md", page("About", category="00-context", body="Who this is for."))
    write(v, "20-knowledge/index.md", index_head("Knowledge", "20-knowledge") + "<!-- AUTO-INDEX -->\n\nold\n")
    write(v, "20-knowledge/nmap.md", page("Nmap", category="20-knowledge", extra="kind: tool\n",
                                          body="A port scanner."))
    write(v, "20-knowledge/pivoting.md", page("Pivoting", category="20-knowledge", extra="kind: technique\n",
                                              body="Moving through a network. Uses [[20-knowledge/nmap|Nmap]]."))
    return v


def cfg_for(vault: Path) -> wiki.Config:
    return wiki.load_config(vault.parent / "wiki.config.json")


def run(vault: Path, *args: str) -> int:
    return wiki.main(["--config", str(vault.parent / "wiki.config.json"), *args])


def test_example_config_loads_and_clean_vault_lints_zero(vault: Path) -> None:
    res = wiki.lint(cfg_for(vault), all_pages=True)
    assert res.error_count == 0, res.errors
    assert res.warnings == []
    assert run(vault, "lint") == 0


def test_lint_catches_every_error_kind(vault: Path, capsys) -> None:
    write(vault, "20-knowledge/broken.md", page("Broken", category="20-knowledge",
                                               body="See [[20-knowledge/missing|Missing]]."))
    write(vault, "26-research/dup.md", page("Dup one", category="26-research"))
    write(vault, "40-references/dup.md", page("Dup two", category="40-references", extra="sources: [x]\n"))
    write(vault, "index.md", "# Index\n\n- [[20-knowledge/index|Knowledge]]\n- [[dup]]\n")
    write(vault, "26-research/no-tags.md", "---\ntitle: No tags\ncategory: 26-research\nstatus: active\n"
                                           "author: claude\n---\n\nBody.\n")
    write(vault, "26-research/bad-status.md", page("Bad status", category="26-research", status="wip"))
    write(vault, "26-research/bad-yaml.md", page("Projects: overview", category="26-research"))
    write(vault, "26-research/no-frame.md", "Just text.\n")
    write(vault, "26-research/embed.md", page("Embed", category="26-research", body="![[missing.png]]"))
    res = wiki.lint(cfg_for(vault))
    c = res.counts
    assert (c["broken-links"], c["ambiguous-links"], c["missing-fields"], c["unknown-status"],
            c["invalid-yaml"], c["no-frontmatter"], c["broken-embeds"]) == (1, 1, 1, 1, 1, 1, 1)
    assert any("missing fields (tags): 26-research/no-tags.md" in e for e in res.errors)
    assert run(vault, "lint", "-v") == 1
    out = capsys.readouterr().out
    assert "broken link [[20-knowledge/missing]]: 20-knowledge/broken.md" in out
    assert "ambiguous link [[dup]]: index.md" in out


def test_lint_skips_inactive_sections_unless_all(vault: Path) -> None:
    write(vault, "90-archives/old.md", "No frontmatter, [[nowhere]].\n")
    write(vault, "_templates/note.md", "[[{{title}}]]\n")
    cfg = cfg_for(vault)
    assert wiki.lint(cfg).error_count == 0
    res = wiki.lint(cfg, all_pages=True)
    assert res.counts["broken-links"] == 1  # the archive; templates are never linted
    assert res.counts["no-frontmatter"] == 0  # the archive has frontmatter: false


def test_warnings_do_not_fail(vault: Path) -> None:
    write(vault, "20-knowledge/short.md", page("Short", category="20-knowledge", author="someone",
                                              extra="kind: gadget\n", body="Uses [[nmap]], again [[nmap]]."))
    res = wiki.lint(cfg_for(vault))
    assert res.error_count == 0
    assert res.counts["short-links"] == 2
    assert res.counts["repeated-links"] == 1
    assert res.counts["no-author"] == 1
    assert res.counts["unknown-kind"] == 1
    assert run(vault, "lint") == 0


def test_fix_rewrites_bare_link_and_category(vault: Path) -> None:
    p = write(vault, "20-knowledge/short.md",
              page("Short", category="wrong", body="Uses [[nmap]] and [[nmap#Flags|flags]], not `[[nmap]]`."))
    raw = write(vault, "_inbox/2026-01-01-capture.md", page("Capture", category="_inbox", body="[[nmap]]"))
    assert run(vault, "lint", "--fix") == 0
    text = p.read_text(encoding="utf-8")
    assert "Uses [[20-knowledge/nmap|nmap]] and [[20-knowledge/nmap#Flags|flags]], not `[[nmap]]`." in text
    assert "category: 20-knowledge\n" in text
    assert "[[nmap]]" in raw.read_text(encoding="utf-8")  # raw material stays as it is
    assert wiki.lint(cfg_for(vault)).counts["short-links"] == 0


def test_fix_leaves_ambiguous_links_alone(vault: Path) -> None:
    write(vault, "26-research/nmap.md", page("Nmap research", category="26-research"))
    p = write(vault, "20-knowledge/short.md", page("Short", category="20-knowledge", body="[[nmap]]"))
    wiki.fix(cfg_for(vault))
    assert "[[nmap]]" in p.read_text(encoding="utf-8")


def test_fix_keeps_crlf_line_endings(vault: Path) -> None:
    text = page("Crlf", category="wrong", body="Uses [[nmap]].").replace("\n", "\r\n")
    p = write(vault, "20-knowledge/crlf.md", text)
    assert wiki.fix(cfg_for(vault)) >= 1
    data = p.read_bytes()
    assert b"category: 20-knowledge\r\n" in data and b"[[20-knowledge/nmap|nmap]]" in data
    assert data.count(b"\n") == data.count(b"\r\n")


def test_reindex_writes_below_marker_and_keeps_header(vault: Path) -> None:
    write(vault, "26-research/index.md", index_head("Research", "26-research") + "<!-- AUTO-INDEX -->\n\nstale\n")
    write(vault, "26-research/2026-01-01-a.md", page("First", category="26-research", body="The older one."))
    write(vault, "26-research/2026-02-01-b.md", page("Second", category="26-research", extra="summary: Newer.\n"))
    assert run(vault, "reindex", "26-research") == 0
    text = (vault / "26-research/index.md").read_text(encoding="utf-8")
    head, _, body = text.partition("<!-- AUTO-INDEX -->")
    assert head == index_head("Research", "26-research")
    assert body == ("\n\n- [[26-research/2026-02-01-b|Second]]: Newer.\n"
                    "- [[26-research/2026-01-01-a|First]]: The older one.\n")


def test_reindex_leaves_manual_and_handwritten_indexes_alone(vault: Path) -> None:
    manual = index_head("Decisions", "50-decisions") + "<!-- AUTO-INDEX -->\n\n- [[50-decisions/log|Log]]\n"
    write(vault, "50-decisions/index.md", manual)
    write(vault, "50-decisions/log.md", page("Log", category="50-decisions"))
    hand = index_head("Research", "26-research") + "- [[26-research/x|X]]\n"
    write(vault, "26-research/index.md", hand)
    write(vault, "26-research/x.md", page("X", category="26-research"))
    before = (vault / "00-context/index.md").read_text(encoding="utf-8")
    done = wiki.reindex(cfg_for(vault))
    assert "50-decisions" not in done and "00-context" not in done and "26-research" not in done
    assert (vault / "50-decisions/index.md").read_text(encoding="utf-8") == manual
    assert (vault / "26-research/index.md").read_text(encoding="utf-8") == hand
    assert (vault / "00-context/index.md").read_text(encoding="utf-8") == before


def test_reindex_by_kind_groups_in_config_order(vault: Path) -> None:
    write(vault, "20-knowledge/awk.md", page("awk", category="20-knowledge", extra="kind: tool\n"))
    write(vault, "20-knowledge/misc.md", page("Misc", category="20-knowledge", body="No kind."))
    wiki.update_index(cfg_for(vault), "20-knowledge")
    body = (vault / "20-knowledge/index.md").read_text(encoding="utf-8").split("<!-- AUTO-INDEX -->")[1]
    assert body == ("\n\n## Tools\n\n- [[20-knowledge/awk|awk]]\n- [[20-knowledge/nmap|Nmap]]: A port scanner.\n\n"
                    "## Techniques\n\n- [[20-knowledge/pivoting|Pivoting]]: Moving through a network. Uses Nmap.\n\n"
                    "## Other\n\n- [[20-knowledge/misc|Misc]]: No kind.\n")


def test_reindex_projects_references_and_folders(vault: Path) -> None:
    write(vault, "10-projects/index.md", index_head("Projects", "10-projects"))
    write(vault, "10-projects/alpha/README.md", page("Alpha", category="10-projects", status="parked"))
    write(vault, "10-projects/beta/notes.md", page("Beta notes", category="10-projects"))
    write(vault, "40-references/index.md", index_head("References", "40-references") + "<!-- AUTO-INDEX -->\n")
    write(vault, "40-references/guide.md", page("Guide", category="40-references", body="A guide."))
    write(vault, "40-references/books/index.md", index_head("Books", "40-references"))
    write(vault, "40-references/books/one.md", page("One", category="40-references"))
    write(vault, "40-references/sources/guide.md", page("Guide raw", category="40-references"))
    write(vault, "40-references/log.md", page("Ingest log", category="40-references"))
    cfg = cfg_for(vault)
    cfg.sections["26-research"] = {**cfg.sections["26-research"], "index": "folders", "page": "idea.md",
                                   "fields": ["status", "version"]}
    write(vault, "26-research/index.md", index_head("Ideas", "26-research"))
    write(vault, "26-research/old/idea.md", page("Old idea", category="26-research", extra="version: 1\n")
          .replace("updated: 2099-01-01", "updated: 2026-01-01"))
    write(vault, "26-research/new/idea.md", page("New idea", category="26-research"))
    assert wiki.reindex(cfg) == ["10-projects", "20-knowledge", "26-research", "40-references"]
    projects = (vault / "10-projects/index.md").read_text(encoding="utf-8")
    assert projects.endswith("<!-- AUTO-INDEX -->\n\n## Projects\n\n- [[10-projects/alpha/README|Alpha]]: *parked*\n")
    refs = (vault / "40-references/index.md").read_text(encoding="utf-8").split("<!-- AUTO-INDEX -->")[1]
    assert refs == ("\n\n## Collections and pages\n\n- [[40-references/books/index|books]] (2 pages)\n"
                    "- [[40-references/guide|Guide]]: A guide.\n\n## Raw sources (`sources/`)\n\n"
                    "- [[40-references/sources/guide|Guide raw]]\n\n- [[40-references/log|Ingest log]]\n")
    ideas = (vault / "26-research/index.md").read_text(encoding="utf-8").split("<!-- AUTO-INDEX -->")[1]
    assert ideas == ("\n\n- [[26-research/new/idea|New idea]]: *active*\n"
                     "- [[26-research/old/idea|Old idea]]: *active · 1*\n")


def test_empty_section_gets_placeholder(vault: Path) -> None:
    write(vault, "26-research/index.md", index_head("Research", "26-research"))
    wiki.update_index(cfg_for(vault), "26-research")
    assert (vault / "26-research/index.md").read_text(encoding="utf-8").endswith(
        "<!-- AUTO-INDEX -->\n\n_Nothing here yet._\n")


def test_log_appends_after_marker_newest_first(vault: Path) -> None:
    cfg = cfg_for(vault)
    wiki.append_log(cfg, "ingest", "First", ["one", "  two  words "], when=datetime(2026, 1, 1, 9, 0))
    wiki.append_log(cfg, "lint", "Second", when=datetime(2026, 1, 2, 10, 30))
    text = (vault / "log.md").read_text(encoding="utf-8")
    assert text.startswith('---\ntitle: "Operations log"\n')
    assert wiki.parse_frontmatter(text)["category"] == "log"
    tail = text.split("<!-- Begin of the log -->")[1]
    assert tail == ("\n\n## 2026-01-02 10:30 · lint · Second\n\n"
                    "## 2026-01-01 09:00 · ingest · First\n- one\n- two words\n\n")


def test_log_cli_rejects_unknown_op(vault: Path, capsys) -> None:
    assert run(vault, "log", "nope", "Title") == 2
    assert "unknown operation 'nope'" in capsys.readouterr().err
    assert run(vault, "log", "query", "Asked", "a line") == 0
    assert "· query · Asked\n- a line\n" in (vault / "log.md").read_text(encoding="utf-8")


def test_config_discovery(vault: Path, tmp_path: Path, monkeypatch) -> None:
    sub = vault / "20-knowledge"
    monkeypatch.chdir(sub)
    monkeypatch.delenv(wiki.CONFIG_ENV, raising=False)
    assert wiki.find_config() == (tmp_path / "wiki.config.json").resolve()
    other = tmp_path / "elsewhere.json"
    other.write_text(json.dumps({"wiki_dir": "wiki"}), encoding="utf-8")
    monkeypatch.setenv(wiki.CONFIG_ENV, str(other))
    assert wiki.find_config() == other.resolve()
    assert wiki.find_config(str(tmp_path / "wiki.config.json")) == (tmp_path / "wiki.config.json").resolve()
    monkeypatch.delenv(wiki.CONFIG_ENV)
    monkeypatch.chdir(tmp_path.parent)
    if not any((d / wiki.CONFIG_NAME).is_file() for d in (tmp_path.parent, *tmp_path.parent.parents)):
        with pytest.raises(wiki.ConfigError):
            wiki.find_config()


def test_bad_config_is_a_usage_error(tmp_path: Path, capsys) -> None:
    bad = tmp_path / "wiki.config.json"
    bad.write_text(json.dumps({"sections": {"x": {"index": "magic"}}}), encoding="utf-8")
    assert wiki.main(["--config", str(bad), "stats"]) == 2
    assert "unknown index type 'magic'" in capsys.readouterr().err


def test_stats(vault: Path, capsys) -> None:
    write(vault, "_inbox/2026-01-01-q.md", page("Q", category="_inbox", status="question", author="user"))
    write(vault, "20-knowledge/short.md", page("Short", category="20-knowledge", tags="[once, demo]",
                                              author="nobody", body="[[nmap]]"))
    s = wiki.stats(cfg_for(vault))
    assert s["questions"] == 1
    assert s["sections"]["20-knowledge"] == {"pages": 3, "no_author": 1, "short_links": 1, "tags": 2}
    assert s["once"] == ["once"]
    assert run(vault, "stats") == 0
    assert "20-knowledge" in capsys.readouterr().out


def test_status_roles_in_another_language(tmp_path):
    """Status words in Dutch keep the stale warning and the question count working."""
    cfg = json.loads((Path(__file__).parent.parent / "wiki.config.example.json").read_text(encoding="utf-8"))
    cfg["status_words"] = ["concept", "actief", "klaar", "geparkeerd", "gearchiveerd", "vraag"]
    cfg["status_roles"] = {"active": "actief", "draft": "concept", "question": "vraag"}
    cfg["question_kind"] = "vraag"
    (tmp_path / "wiki.config.json").write_text(json.dumps(cfg), encoding="utf-8")
    vault = tmp_path / cfg.get("wiki_dir", "wiki")
    proj = vault / "10-projects" / "oud"
    proj.mkdir(parents=True)
    (proj / "README.md").write_text("---\ntitle: Oud\ntags: []\ncategory: 10-projects\nstatus: actief\n"
                                    "author: claude\nupdated: 2020-01-01\n---\nbody\n", encoding="utf-8")
    inbox = vault / "_inbox"
    inbox.mkdir(parents=True)
    (inbox / "q.md").write_text("---\ntitle: Q\ntags: []\ncategory: _inbox\nstatus: concept\nkind: vraag\n"
                                "author: claude\n---\nWaarom?\n", encoding="utf-8")
    conf = wiki.load_config(tmp_path / "wiki.config.json")
    res = wiki.lint(conf, all_pages=True)
    assert res.counts["stale-active"] == 1
    assert wiki.stats(conf)["questions"] == 1


def test_status_roles_must_be_known_words(tmp_path):
    cfg = {"wiki_dir": "wiki", "status_words": ["concept", "actief"], "sections": {}}
    (tmp_path / "wiki.config.json").write_text(json.dumps(cfg), encoding="utf-8")
    with pytest.raises(wiki.ConfigError):
        wiki.load_config(tmp_path / "wiki.config.json")
