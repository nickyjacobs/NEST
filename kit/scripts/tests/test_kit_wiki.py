"""Checks on the reference vault in kit/wiki: the slug script, the templates, the settings and the bases.

slug.js runs inside Obsidian (Templater), so its test runs it with Node when Node is installed and is
skipped otherwise. Manual check without Node: in Obsidian, make a note from the `note` template with
the titles "Compare café options", "Заметка о тесте" and "???"; the files must be named
compare-cafe-options, заметка-о-тесте and a date-time such as 2026-01-02-103000.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import wiki

KIT = Path(__file__).resolve().parents[2] / "wiki"
SLUG = KIT / "_templates" / "_scripts" / "slug.js"

CASES = {
    "Compare café options": "compare-cafe-options",
    "Заметка о тесте": "заметка-о-тесте",
    "会議メモ": "会議メモ",
    "Ελληνικά": "ελληνικά",
    "हिन्दी नोट": "हिन्दी-नोट",
    "Straße & Größe": "strasse-grosse",
    "Smørrebrød på Ærø": "smorrebrod-pa-aero",
    "Łódź żółć": "lodz-zolc",
    "İstanbul": "istanbul",
    "C++ vs C#": "c-vs-c",
    "Don’t stop": "dont-stop",
    "2024/25 plan": "2024-25-plan",
    "???": "2026-01-02-030405",
    "": "2026-01-02-030405",
}


def test_slug_script_keeps_every_script_and_never_returns_nothing() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is not installed; see the manual check at the top of this file")
    program = ("const slug = require(process.argv[1]); const now = new Date(2026, 0, 2, 3, 4, 5);"
               "const out = {}; for (const t of JSON.parse(process.argv[2])) out[t] = slug(t, now);"
               "out.__long = slug('word '.repeat(40), now); process.stdout.write(JSON.stringify(out));")
    r = subprocess.run([node, "-e", program, str(SLUG), json.dumps(list(CASES))], capture_output=True,
                       text=True, encoding="utf-8", check=True)
    got = json.loads(r.stdout)
    long = got.pop("__long")
    assert got == CASES
    assert len(long) <= 80 and not long.endswith("-") and long.startswith("word-word")


def test_slug_script_has_the_parts_the_templates_rely_on() -> None:
    """Runs without Node: the Unicode classes, the fallback and the export are in the file."""
    text = SLUG.read_text(encoding="utf-8")
    assert r"[^\p{L}\p{N}\p{M}]+/gu" in text
    assert "|| stamp(" in text and "module.exports = slug;" in text
    assert "[^a-z0-9]" not in text


def rendered(template: Path) -> str:
    """A template as Templater leaves it: the script block gone, every tag filled with a word."""
    text = re.sub(r"<%\*.*?-%>\n", "", template.read_text(encoding="utf-8"), flags=re.DOTALL)
    return re.sub(r"<%.*?%>", "value", text)


@pytest.mark.parametrize("name", sorted(p.name for p in (KIT / "_templates").glob("*.md")) + ["Home.md"])
def test_kit_pages_hold_no_placeholder_links(name: str) -> None:
    """A note made from a template must not fail the lint by construction: every link in running
    text points at a real kind of page, never at an example such as [[vault/path]]."""
    path = KIT / name if name == "Home.md" else KIT / "_templates" / name
    for target in wiki.WL.findall(wiki.running_text(rendered(path))):
        assert "<" not in target and "vault/path" not in target and "value" not in target, target


# The tag every quoted frontmatter value uses: backslashes doubled, double quotes made single.
ESCAPED = '.replace(/\\\\/g, "\\\\\\\\").replace(/"/g, "\'") %>'


@pytest.mark.parametrize("name", sorted(p.name for p in (KIT / "_templates").glob("*.md") if p.name != "README.md"))
def test_template_frontmatter_survives_quotes_and_backslashes(name: str) -> None:
    text = (KIT / "_templates" / name).read_text(encoding="utf-8")
    quoted = re.findall(r'(?m)^[\w-]+: ".*<% .* %>.*"$', text)
    assert quoted, name
    for line in quoted:
        assert ESCAPED in line, line
    # What that tag gives for the input  C:\dir "x"  must be YAML Obsidian can read.
    filled = re.sub(r"<%\*.*?-%>\n", "", text, flags=re.DOTALL)
    filled = re.sub(r"<% \w+" + re.escape(ESCAPED), lambda m: "C:\\\\dir 'x'", filled)
    filled = re.sub(r"<%.*?%>", "2026-01-02", filled).replace("<fill in: user author value>", "user")
    fm = wiki.parse_frontmatter(filled)
    assert fm is not None and "C:\\dir 'x'" in str(fm["title"]), name


def test_obsidian_settings_are_valid_and_keep_code_from_running() -> None:
    for path in (KIT / "obsidian").rglob("*.json"):
        json.loads(path.read_text(encoding="utf-8"))
    bind = json.loads((KIT / "obsidian/plugins/obsidian-meta-bind-plugin/data.json").read_text(encoding="utf-8"))
    assert bind["enableJs"] is False
    # No Meta Bind button renders where outside text lands: a button can run a Templater file.
    assert {"_templates", "_inbox", "40-references/sources", "90-archives"} <= set(bind["excludedFolders"])
    templater = json.loads((KIT / "obsidian/plugins/templater-obsidian/data.json").read_text(encoding="utf-8"))
    assert templater["trigger_on_file_creation_mode"] == "none"
    ids = {b["id"] for b in bind["buttonTemplates"]}
    used = set(re.findall(r"\b(?:mk|ga)-[a-z]+", (KIT / "Home.md").read_text(encoding="utf-8")))
    assert used <= ids
    for b in bind["buttonTemplates"]:
        if b["action"]["type"] == "templaterCreateNote":
            assert (KIT / b["action"]["templateFile"]).is_file()


def test_bases_parse_and_do_not_fail_on_a_note_without_tags() -> None:
    for path in (KIT / "_bases").glob("*.base"):
        text = path.read_text(encoding="utf-8")
        data = yaml.safe_load(text)
        assert {"filters", "views"} <= set(data) and all(v.get("name") and v.get("type") for v in data["views"])
        assert "tags.contains(" not in text  # an error on a note without tags; file.hasTag is safe
    home = (KIT / "Home.md").read_text(encoding="utf-8")
    names = {v["name"] for v in yaml.safe_load((KIT / "_bases/dashboard.base").read_text(encoding="utf-8"))["views"]}
    assert set(re.findall(r"dashboard\.base#([^\]]+)\]\]", home)) <= names
