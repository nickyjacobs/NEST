"""Tests for skills_catalog.py on a fixture workspace."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import skills_catalog as sk

EM = "\u2014"


def skill(root: Path, name: str, front: str, body: str = "Do the thing.\n") -> Path:
    p = root / ".claude/skills" / name / "SKILL.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\n{front}---\n\n{body}", encoding="utf-8")
    return p


def agent(root: Path, name: str, front: str) -> Path:
    p = root / ".claude/agents" / f"{name}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\n{front}---\n\nYou review.\n", encoding="utf-8")
    return p


@pytest.fixture
def ws(tmp_path):
    skill(tmp_path, "weekly-review", "name: weekly-review\ndescription: Reviews the week. Use on Fridays.\n"
          "argument-hint: '[week]'\nmetadata:\n  does: Walks through the week's notes and open items.\n"
          "  try:\n    - review my week\n    - /weekly-review 47\n")
    skill(tmp_path, "deploy", "description: Deploys the site. Only by hand.\ndisable-model-invocation: true\n")
    agent(tmp_path, "researcher", "name: researcher\ndescription: Looks things up on the web. Cites sources.\n"
          "tools: Read, WebFetch\nmodel: sonnet\n")
    return tmp_path


def test_clean_workspace_passes(ws):
    assert sk.check(ws) == []


def test_render_rows(ws):
    block = sk.render(ws)
    assert block.startswith(sk.BEGIN) and block.endswith(sk.END)
    assert "| `weekly-review` | `/weekly-review [week]` or on its own | Walks through the week's notes and open items. " \
           "| review my week; /weekly-review 47 |" in block
    assert "| `deploy` | only `/deploy` | Deploys the site |  |" in block
    assert "| `researcher` | sonnet | Read, WebFetch | Looks things up on the web |" in block


def test_write_creates_catalog_and_check_sees_it_current(ws):
    assert "updated" in sk.write(ws)
    text = (ws / sk.CATALOG).read_text(encoding="utf-8")
    assert sk.BEGIN in text and "weekly-review" in text
    assert sk.check(ws) == []
    skill(ws, "new-one", "description: A new skill.\n")
    assert any("stale" in p for p in sk.check(ws))


def test_write_keeps_text_around_markers(ws):
    (ws / "docs").mkdir()
    (ws / sk.CATALOG).write_text(f"# Mine\n\nIntro.\n\n{sk.BEGIN}\nold\n{sk.END}\n\nOutro.\n", encoding="utf-8")
    sk.write(ws)
    text = (ws / sk.CATALOG).read_text(encoding="utf-8")
    assert text.startswith("# Mine\n\nIntro.") and text.endswith("Outro.\n") and "old" not in text


def test_write_refuses_file_without_markers(ws):
    (ws / "docs").mkdir()
    (ws / sk.CATALOG).write_text("# No markers\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        sk.write(ws)


@pytest.mark.parametrize("front,problem", [
    ("name: x\n", "no description"),
    ("description: ok\ncolour: red\n", "does not know: colour"),
    ("description: ok\nname: other\n", "must equal the folder name"),
    ("description: ok\nmetadata: just text\n", "metadata must be a map"),
    ("description: ok\nmetadata:\n  try: one\n", "metadata.try must be a non-empty list"),
    (f"description: ok {EM} with a dash\n", "em dash on line"),
    ("description: " + "x" * 1600 + "\n", "over 1536"),
])
def test_skill_problems(tmp_path, front, problem):
    p = skill(tmp_path, "my-skill", front)
    assert any(problem in msg for msg in sk.check_skill(p)), sk.check_skill(p)


def test_skill_fields_from_the_docs_are_accepted(tmp_path):
    front = ("description: ok\nwhen_to_use: on request\nargument-hint: '[x]'\narguments: a b\n"
             "disable-model-invocation: false\nuser-invocable: true\nallowed-tools: Read\ndisallowed-tools: Bash\n"
             "model: sonnet\neffort: high\ncontext: fork\nagent: Explore\nbackground: false\nhooks: {}\n"
             "paths: '*.md'\nshell: bash\nlicense: MIT\ncompatibility: any\nmetadata: {}\n")
    assert sk.check_skill(skill(tmp_path, "full", front)) == []


def test_bad_folder_name(tmp_path):
    assert any("lowercase" in m for m in sk.check_skill(skill(tmp_path, "Bad_Name", "description: ok\n")))


def test_missing_frontmatter(tmp_path):
    p = tmp_path / ".claude/skills/bare/SKILL.md"
    p.parent.mkdir(parents=True)
    p.write_text("# Just text\n", encoding="utf-8")
    assert sk.check_skill(p) == ["needs frontmatter between --- lines that parses as a YAML map"]


def test_external_skill_keeps_its_own_fields(tmp_path):
    p = skill(tmp_path, "Their_Skill", "description: theirs\nversion: 2\n")
    (p.parent / "NOTICE.md").write_text("From elsewhere, MIT.\n", encoding="utf-8")
    assert sk.check_skill(p) == []


def test_agent_problems(tmp_path):
    assert any("no name" in m for m in sk.check_agent(agent(tmp_path, "a", "description: x\n")))
    assert any("does not know: allowed-tools" in m
               for m in sk.check_agent(agent(tmp_path, "b", "name: b\ndescription: x\nallowed-tools: Read\n")))
    front = ("name: c\ndescription: x\ntools: Read\ndisallowedTools: Bash\nmodel: haiku\npermissionMode: default\n"
             "maxTurns: 5\nskills: []\nmcpServers: []\nhooks: {}\nmemory: project\nbackground: false\n"
             "omitClaudeMd: false\neffort: low\nisolation: worktree\ncolor: blue\ninitialPrompt: hi\n"
             "autoCompactWindow: 100000\nexperimental: {}\nmetadata: {}\n")
    assert sk.check_agent(agent(tmp_path, "c", front)) == []


def test_crlf_frontmatter(tmp_path):
    p = tmp_path / ".claude/skills/win/SKILL.md"
    p.parent.mkdir(parents=True)
    p.write_bytes(b"---\r\ndescription: Written on Windows.\r\n---\r\n\r\nBody\r\n")
    assert sk.check_skill(p) == []


def test_cli_check_exit_codes(ws, capsys):
    assert sk.main(["--root", str(ws), "--check"]) == 0
    skill(ws, "broken", "name: x\n")
    assert sk.main(["--root", str(ws), "--check"]) == 1
    assert "no description" in capsys.readouterr().out


# The catalogue line, a root that is not there, and markers the setup left behind

def test_first_sentence_does_not_stop_at_an_abbreviation():
    assert sk.first_sentence("Does a thing, e.g. this one. Second sentence.") == "Does a thing, e.g. this one"
    assert sk.first_sentence("Reads v1.2 files. Then more.") == "Reads v1.2 files"


def test_a_root_that_does_not_exist_is_a_usage_error(tmp_path, capsys):
    assert sk.main(["--root", str(tmp_path / "nowhere"), "--check"]) == 2
    assert "nowhere" in capsys.readouterr().err
    assert sk.main(["--root", str(tmp_path / "nowhere")]) == 2
    assert not (tmp_path / "nowhere").exists()


def test_installed_check_finds_leftover_markers(ws, capsys):
    p = skill(ws, "half-built", "description: Does things. Use it when asked.\n",
              "Read `<!-- customise: wiki index path -->` first.\n")
    (p.parent / "reference.md").write_text("Author: <fill in: user author value>\n", encoding="utf-8")
    agent(ws, "helper", "name: helper\ndescription: Helps.\n").write_text(
        "---\nname: helper\ndescription: Helps.\n---\n\nWrite in English <!-- customise: output language -->.\n",
        encoding="utf-8")
    external = skill(ws, "borrowed", "description: From elsewhere.\n", "They say customise: freely.\n")
    (external.parent / "NOTICE.md").write_text("Taken over as is.\n", encoding="utf-8")
    sk.write(ws)
    assert sk.main(["--root", str(ws), "--check"]) == 0  # reference files may carry markers
    capsys.readouterr()
    assert sk.main(["--root", str(ws), "--check", "--installed"]) == 1
    out = capsys.readouterr().out
    assert ".claude/skills/half-built/SKILL.md:5: leftover marker 'customise:'" in out
    assert ".claude/skills/half-built/reference.md:1: leftover marker '<fill in:'" in out
    assert ".claude/agents/helper.md:6: leftover marker 'customise:'" in out
    assert "borrowed" not in out and "skills: 3 problems" in out
