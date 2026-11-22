"""Tests for idea_page.py: saving blueprints and reviews into a tmp vault and rebuilding idea.md."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import council_score
import idea_page
import wiki

EXAMPLE = Path(__file__).resolve().parent.parent / "wiki.config.example.json"
SCRIPT = Path(idea_page.__file__)
SLUG = "trail-log"
TITLE = "Trail log for small hiking groups"
IDEAS = "25-ideas"


def blueprint_md(changed: str = "", extra_open: str = "") -> str:
    lines = [
        f"# {TITLE}",
        "",
        "## One-liner",
        "A shared trail log for hiking groups of three to eight [yours]. It runs on a spreadsheet [proposed].",
        "",
        "## Problem and job",
        "Groups lose track of past routes [assumed]. Route apps cost money [fact 1].",
        "",
        "## Assumptions and risks",
        "- Groups keep logging after the first month [assumed]",
        "- The spreadsheet stays fast enough [assumed]",
        "",
        "## Validation plan",
        "- Habit: give two groups the sheet and count entries in week one [proposed]",
        "- Price: ask five leads what they would pay [proposed]",
        "",
        "## Open questions and tensions",
        "- Spreadsheet or a small app first? | options: A sheet, B app | recommended: A [open]",
        "- Charge per group, or free? | options: A per group, B free | recommended: B [open]",
    ]
    if extra_open:
        lines.append(f"- {extra_open} [open]")
    lines += [
        "- The habit and the price pull apart. [assumed]",
        "",
        "## Sources",
        '1 | Route app pricing | RouteCo | undated | https://example.com/pricing | "Plans from 5 a month" (quote checked)',
        '2 | Hiking survey | Hike Org | 2026-01-02 | https://example.org/survey | "Most groups plan by chat" (not verified: NOT FOUND)',
        "",
        "## Council brief",
        "The idea is a shared trail log for small hiking groups.",
    ]
    if changed:
        lines += ["", "## What changed", f"{changed}."]
    return "\n".join(lines) + "\n"


def write(p: Path, text: str) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


@pytest.fixture
def ws(tmp_path: Path, monkeypatch) -> Path:
    """A workspace: wiki.config.json with an ideas section, a vault that lints clean."""
    cfg = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    cfg["sections"][IDEAS] = {"index": "folders", "page": "idea.md", "fields": ["status", "verdict", "score"],
                              "status_words": ["new", "worked-out", "reviewed", "go", "parked", "dropped", "done"]}
    (tmp_path / "wiki.config.json").write_text(json.dumps(cfg), encoding="utf-8")
    v = tmp_path / "wiki"
    write(v / "index.md", "# Index\n\n- [[25-ideas/index|Ideas]]\n")
    write(v / IDEAS / "index.md", "---\ntitle: Ideas\ntags: [index]\ncategory: 25-ideas\nstatus: done\n---\n\n"
                                  "# Ideas\n\n<!-- AUTO-INDEX -->\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("NEST_WIKI_CONFIG", raising=False)
    return tmp_path


def architects_run(ws: Path, stamp: str = "20261121-1951", changed: str = "", extra_open: str = "") -> Path:
    run = ws / ".runs" / "architects" / f"{stamp}-{SLUG}"
    write(run / "meta.md", f"Title: {TITLE}\nSlug: {SLUG}\n")
    write(run / "blueprint.md", blueprint_md(changed, extra_open))
    write(run / "surveyor.report.md", "Closest: RouteCo | https://example.com\n")
    write(run / "dreamer.report.md", "Variants:\n- A paper logbook\n")
    write(run / "client.report.md", "I try it if it takes five minutes.\n")
    write(run / "engineer.report.md", "Direction: A shared sheet per group (yours, plus a template [proposed])\n"
                                      "Hours: 6 to 10 hours\nMonday: Make the sheet with five sample rows.\n")
    write(run / "inspector.report.md", "Overlap:\n- Route log | yes | RouteCo has it\n\n"
                                       "Load-bearing: Groups keep logging without a reminder (assumption)\n")
    head = ""
    if changed:
        head += f"Earlier version 1: {TITLE}. Changed: {changed}.\n"
    head += ("Closest rival: RouteCo (https://example.com), read again: WebFetch extract.\n\n"
             "## The brief\n\nThe user's idea is a shared trail log.\n\n"
             "The user's answers to the interview:\n\n- Paid or free? Their answer: free first.\n")
    write(run / "save-head.md", head)
    return run


def council_run(ws: Path, stamp: str = "20261121-2006", criteria: dict | None = None) -> Path:
    run = ws / ".runs" / "council" / f"{stamp}-{SLUG}"
    write(run / "meta.md", f"Title: {TITLE}\n")
    for seat in ("believer", "investor", "outsider"):
        write(run / f"{seat}.report.md", f"The {seat} report.\n\nSecond paragraph.\n")
    write(run / "skeptic.report.md", "Risks:\n- [high] Nobody logs. (assumption)\nFirst version: 8-12 hours\n")
    c = criteria or {"value": 3, "fit": 4, "time": 3, "risk": 3, "cost": 3}
    judges = [{"criteria": c, "verdict": None, "score": None} for _ in range(3)]
    for j in judges:
        checked = council_score.check_judge(j)
        j.update(verdict=checked["verdict"], score=checked["score"])
    judges[0]["score"] = 9.9  # one mismatch, so the score check line shows
    verdict = council_score.decide(judges)
    write(run / "verdict.json", json.dumps(verdict))
    write(run / "review.md", "The idea is a shared trail log for small hiking groups. It is free at first. "
                             "More text follows here.\n\n"
                             "## Verdict\n\n"
                             "- Jury: hand-typed, to be replaced\n"
                             "- Value 3/5: some value (rests on: believer [1])\n"
                             "- Biggest risk: Groups stop logging after two weeks | and forget it.\n"
                             "- Conditions: Test with two groups first.\n"
                             "- Kill criteria: Stop when fewer than two groups log weekly.\n"
                             "- Next step: Send the sheet to two group leads this week.\n"
                             "- Confidence: high, the reports agree\n\n"
                             "## The fact check\n\n1. Route apps cost money: CONFIRMED.\n\n"
                             "## The source check\n\n- believer [1]: quote found\n")
    return run


def cfg() -> wiki.Config:
    return wiki.load_config(Path("wiki.config.json"))


def lint_clean() -> None:
    c = cfg()
    wiki.reindex(c)
    res = wiki.lint(c, all_pages=True)
    assert res.error_count == 0, res.errors
    assert res.warnings == [], res.warnings


def save_blueprint(run: Path, *extra: str) -> int:
    return idea_page.main(["save-blueprint", "--slug", SLUG, "--title", TITLE, "--file", str(run / "blueprint.md"),
                           "--head", str(run / "save-head.md"), *extra])


def save_review(run: Path, *extra: str) -> int:
    return idea_page.main(["save-review", "--slug", SLUG, "--title", TITLE, "--file", str(run / "review.md"),
                           "--verdict", str(run / "verdict.json"), *extra])


def idea_text(ws: Path) -> str:
    return (ws / "wiki" / IDEAS / SLUG / "idea.md").read_text(encoding="utf-8")


def frontmatter(text: str) -> dict:
    return wiki.parse_frontmatter(text)


def test_save_blueprint_creates_v1_and_the_idea_page(ws: Path, capsys) -> None:
    run = architects_run(ws)
    assert save_blueprint(run) == 0
    folder = ws / "wiki" / IDEAS / SLUG
    bp = folder / "blueprints" / "2026-11-21-1951-v1.md"
    out = capsys.readouterr().out
    assert f"wrote {bp}" in out and f"wrote {folder / 'idea.md'}" in out

    text = bp.read_text(encoding="utf-8")
    fm = frontmatter(text)
    assert fm["title"] == f"Blueprint v1: {TITLE}" and fm["status"] == "done" and fm["version"] == 1
    assert fm["cssclasses"] == ["idea-note"] and fm["author"] == "claude" and fm["category"] == IDEAS
    assert fm["idea"] == f"[[{IDEAS}/{SLUG}/idea|{TITLE}]]"
    assert "Drawn by The Architects on 2026-11-21 19:51, version 1 (full)." in text
    assert ("Claims: 1 yours, 1 fact, 3 proposed, 4 assumed, 2 open. Source check: 1 of 2 quotes found.\n"
            "Closest rival: RouteCo") in text
    assert "### One-liner\nA shared trail log" in text and "\n## One-liner" not in text
    for d in ("Surveyor", "Dreamer", "Client", "Engineer", "Inspector"):
        assert f"### The {d}\n" in text
    assert text.index("## The brief") < text.index("## The blueprint") < text.index("## The desks")

    page = idea_text(ws)
    fm = frontmatter(page)
    assert fm["status"] == "worked-out" and fm["version"] == 1 and fm["blueprints"] == 1 and fm["reviews"] == 0
    assert "verdict" not in fm and fm["created"] == fm["updated"]
    heads = [ln for ln in page.splitlines() if ln.startswith("## ")]
    assert heads == ["## Core", "## Open points", "## Reviews", "## Blueprint", "## History"]
    assert "> [!blueprint] Worked out · v1 · not reviewed yet\n> Updated 2026-11-21 · Blueprints 1 · Reviews 0\n" \
           f"> [[{IDEAS}/{SLUG}/blueprints/2026-11-21-1951-v1|Blueprint v1]]\n" in page
    assert "> [!core] Core\n> **One-liner:** A shared trail log for hiking groups of three to eight.\n" in page
    assert "> **Line:** A shared sheet per group (yours, plus a template [proposed])" in page
    assert "> **Load-bearing assumption:** Groups keep logging without a reminder (assumption)\n>\n" in page
    assert "> **First test:** Habit: give two groups the sheet and count entries in week one\n" in page
    assert "> **Monday:** Make the sheet with five sample rows.\n> **Hours:** 6 to 10 hours\n" in page
    assert ("## Open points\n\n- [ ] Spreadsheet or a small app first? | options: A sheet, B app | recommended: A\n"
            "- [ ] Charge per group, or free? | options: A per group, B free | recommended: B\n\n") in page
    assert '_Not reviewed yet. Say "put it to the council"._' in page
    assert "<!-- BLUEPRINT -->\n> [!blueprint]- Full blueprint v1\n> > [!one-liner]+ One-liner\n" in page
    assert '<span class="lbl lbl-yours">yours</span>' in page and "<!-- /BLUEPRINT -->" in page
    assert "> 1. Route app pricing (https://example.com/pricing) (quote checked)" in page
    assert (f"| 2026-11-21 19:51 | v1 | blueprint by The Architects: first version | "
            f"[[{IDEAS}/{SLUG}/blueprints/2026-11-21-1951-v1\\|full run]] |") in page
    lint_clean()


def test_second_blueprint_is_v2_and_saving_the_same_run_again_keeps_its_version(ws: Path) -> None:
    assert save_blueprint(architects_run(ws)) == 0
    run2 = architects_run(ws, "20261122-0900", changed="Took variant 2, the paper logbook")
    assert save_blueprint(run2) == 0
    assert save_blueprint(run2) == 0  # "save it" twice: the same file, not a v3
    names = sorted(p.name for p in (ws / "wiki" / IDEAS / SLUG / "blueprints").iterdir())
    assert names == ["2026-11-21-1951-v1.md", "2026-11-22-0900-v2.md"]
    page = idea_text(ws)
    fm = frontmatter(page)
    assert fm["version"] == 2 and fm["blueprints"] == 2 and str(fm["created"]) == "2026-11-21" and str(fm["updated"]) == "2026-11-22"
    assert "> [!blueprint] Worked out · v2 · not reviewed yet" in page
    assert "| v2 | blueprint by The Architects: Took variant 2, the paper logbook |" in page
    assert page.index("| v2 |") < page.index("| v1 |")
    text = (ws / "wiki" / IDEAS / SLUG / "blueprints" / "2026-11-22-0900-v2.md").read_text(encoding="utf-8")
    assert text.count("Claims: ") == 1 and "Earlier version 1:" in text
    assert save_blueprint(run2, "--version", "5") == 1  # the same run cannot change its version
    lint_clean()


def test_save_review_takes_the_numbers_from_verdict_json(ws: Path) -> None:
    assert save_blueprint(architects_run(ws)) == 0
    run = council_run(ws)
    v = json.loads((run / "verdict.json").read_text(encoding="utf-8"))
    assert v["verdict"] == "RESHAPE" and v["score"] == 5.5
    assert save_review(run) == 0
    review = ws / "wiki" / IDEAS / SLUG / "reviews" / "2026-11-21-2006-council-v1.md"
    text = review.read_text(encoding="utf-8")
    fm = frontmatter(text)
    assert fm["verdict"] == "RESHAPE" and fm["score"] == 5.5 and fm["version"] == 1 and fm["status"] == "done"
    assert fm["title"] == f"Review v1: {TITLE}" and fm["tags"] == ["idea", "council"]
    assert "Judged by The Council on 2026-11-21 20:06, version 1 (full).\n\nThe idea is a shared trail log" in text
    assert "## Verdict: RESHAPE, 5.5/10 (confidence high)\n\n- Idea alone (without the timing): " in text
    assert "- Jury: RESHAPE 5.5 · RESHAPE 5.5 · RESHAPE 5.5; not a close call\n" in text
    assert "hand-typed" not in text
    assert "- Score check: judge 1: score 9.9 recomputed to 5.5" in text
    assert text.index("- Confidence:") < text.index("- Score check:") < text.index("## The fact check")
    assert "> [!skeptic]- The Skeptic\n> Risks:\n" in text and "> The believer report.\n>\n> Second paragraph." in text

    page = idea_text(ws)
    fm = frontmatter(page)
    assert fm["status"] == "reviewed" and fm["verdict"] == "RESHAPE" and fm["score"] == 5.5 and fm["reviews"] == 1
    assert "> [!verdict] Reviewed · v1 · RESHAPE 5.5\n" in page
    assert f"[[{IDEAS}/{SLUG}/reviews/2026-11-21-2006-council-v1|Review v1]]" in page
    assert "> **Next step:** Send the sheet to two group leads this week. *(The Council)*" in page
    assert "> **Conditions:** Test with two groups first. *(The Council)*" in page
    assert "> **Hours:** 8-12 hours *(The Skeptic)* · 6 to 10 hours *(The Architects)*" in page
    assert "**First test:**" not in page
    assert "| v1 | **RESHAPE** | 5.5 | Groups stop logging after two weeks \\| and forget it. |" in page
    assert "| 2026-11-21 20:06 | v1 | reviewed by The Council: RESHAPE 5.5 |" in page
    lint_clean()


def test_rebuild_keeps_ticks_answers_and_the_users_lines(ws: Path) -> None:
    assert save_blueprint(architects_run(ws, extra_open="Name it after the club?")) == 0
    page_path = ws / "wiki" / IDEAS / SLUG / "idea.md"
    page = page_path.read_text(encoding="utf-8")
    page = page.replace("- [ ] Spreadsheet or a small app first?", "- [x] spreadsheet  or a SMALL app first")
    page = page.replace("recommended: A\n", "recommended: A\n    - **Answer:** A sheet, they said.\n"
                                            "    - and ask Kim about the club drive\n", 1)
    page = page.replace("- [ ] Charge per group, or free?",
                        "- [ ] Charge per group, or free?") .replace(
        "recommended: B\n", "recommended: B\n    - **Still open:** depends on the club\n", 1)
    page = page.replace("- [ ] Name it after the club?", "- [x] Name it after the club?\n"
                                                         "    - **Answer:** Yes, call it Trailclub.")
    page = page.replace("## Reviews", "My own note in the section.\n\n## Reviews")
    page = page.replace("> **Monday:**", "> **Monday (edited by hand):**")
    page_path.write_text(page, encoding="utf-8")

    # A v2 that no longer has the club point: its answer is nowhere else, so it stays
    assert save_blueprint(architects_run(ws, "20261122-0900", changed="Dropped the name question")) == 0
    page = page_path.read_text(encoding="utf-8")
    opens = page.split("## Open points\n\n", 1)[1].split("\n## ", 1)[0]
    assert opens.startswith("- [x] Spreadsheet or a small app first? | options: A sheet, B app | recommended: A\n"
                            "    - **Answer:** A sheet, they said.\n    - and ask Kim about the club drive\n"
                            "- [ ] Charge per group, or free? | options: A per group, B free | recommended: B\n"
                            "    - **Still open:** depends on the club\n")
    assert "- [x] Name it after the club?\n    - **Answer:** Yes, call it Trailclub.\n" in opens
    assert "My own note in the section." in opens
    assert "Monday (edited by hand)" not in page and "> **Monday:**" in page

    # Once a blueprint file holds that answer, the dropped point leaves the page
    run3 = architects_run(ws, "20261123-1000", changed="Answered the name")
    head = (run3 / "save-head.md").read_text(encoding="utf-8")
    write(run3 / "save-head.md", head + "\nThe user's answers to open points of earlier versions:\n\n"
                                        "- Name it after the club? Their answer: Yes, call it Trailclub.\n")
    assert save_blueprint(run3) == 0
    assert idea_page.main(["rebuild", "--slug", SLUG]) == 0
    page = page_path.read_text(encoding="utf-8")
    assert "Name it after the club?" not in page.split("## Open points", 1)[1].split("## Reviews", 1)[0]
    assert "    - **Answer:** A sheet, they said." in page and "My own note in the section." in page
    assert frontmatter(page)["title"] == TITLE
    lint_clean()


def test_review_only_core_and_status_mapping(ws: Path) -> None:
    run = council_run(ws, criteria={"value": 5, "fit": 5, "time": 4, "risk": 4, "cost": 4})
    v = json.loads((run / "verdict.json").read_text(encoding="utf-8"))
    assert v["verdict"] == "GO"
    (ws / "wiki" / IDEAS / SLUG).mkdir(parents=True)
    assert save_review(run) == 0
    page = idea_text(ws)
    fm = frontmatter(page)
    assert fm["status"] == "go" and fm["blueprints"] == 0
    assert "> **The idea:** The idea is a shared trail log for small hiking groups. It is free at first." in page
    assert "> **Verdict:** GO " in page and "> **Kill criteria:** Stop when fewer" in page
    assert "_No open points: there is no blueprint yet._" in page
    assert '<!-- BLUEPRINT -->\n> [!open] No blueprint yet. The Architects can work it out: "work this idea out".\n' \
           "<!-- /BLUEPRINT -->" in page
    # A what-if run is the next version; a blueprint after it is one higher again
    assert save_review(council_run(ws, "20261122-1000")) == 0
    assert (ws / "wiki" / IDEAS / SLUG / "reviews" / "2026-11-22-1000-council-v2.md").is_file()
    assert save_blueprint(architects_run(ws, "20261123-0800")) == 0
    assert (ws / "wiki" / IDEAS / SLUG / "blueprints" / "2026-11-23-0800-v3.md").is_file()
    assert "> [!blueprint] Worked out · v3 · RESHAPE 5.5 (v2)\n" in idea_text(ws)
    lint_clean()


def test_plain_style_and_labels(ws: Path, tmp_path: Path) -> None:
    labels = write(tmp_path / "labels.json", json.dumps({"headings": {"open": "Open punten"},
                                                         "status_shown": {"worked-out": "Uitgewerkt"}}))
    assert save_blueprint(architects_run(ws), "--style", "plain", "--labels", str(labels)) == 0
    page = idea_text(ws)
    types = {ln.split("]")[0] for ln in page.splitlines() if ln.startswith("> [!")}
    assert types == {"> [!info", "> [!quote"}
    assert "## Open punten\n\n- [ ] Spreadsheet" in page and "> [!info] Uitgewerkt · v1" in page
    assert "> ## One-liner" in page and "<span" not in page
    # Ticks survive under the translated heading too
    page = page.replace("- [ ] Spreadsheet", "- [x] Spreadsheet")
    (ws / "wiki" / IDEAS / SLUG / "idea.md").write_text(page, encoding="utf-8")
    assert idea_page.main(["rebuild", "--slug", SLUG, "--style", "plain", "--labels", str(labels)]) == 0
    assert "- [x] Spreadsheet" in idea_text(ws)
    lint_clean()


def test_light_blueprint_takes_the_first_assumption(ws: Path) -> None:
    run = architects_run(ws)
    (run / "inspector.report.md").unlink()
    assert save_blueprint(run, "--size", "light") == 0
    text = next((ws / "wiki" / IDEAS / SLUG / "blueprints").glob("*.md")).read_text(encoding="utf-8")
    assert "version 1 (light)" in text and "### The Inspector" not in text and "### The Dreamer" not in text
    assert "> **Load-bearing assumption:** Groups keep logging after the first month [assumed]" in idea_text(ws)


def test_errors_and_exit_codes(ws: Path, tmp_path: Path, monkeypatch) -> None:
    run = architects_run(ws)
    assert idea_page.main(["save-blueprint", "--slug", "Bad Slug", "--title", "x", "--file", "x"]) == 2
    assert idea_page.main(["save-blueprint", "--slug", "a" * 51, "--title", "x", "--file", "x"]) == 2
    assert idea_page.main(["save-blueprint", "--slug", SLUG, "--title", "x", "--file", str(tmp_path / "no.md")]) == 1
    assert idea_page.main(["save-blueprint", "--slug", SLUG]) == 2
    assert idea_page.main(["rebuild", "--slug", SLUG]) == 1  # no folder yet
    assert save_blueprint(run, "--when", "2026-13-01-0900") == 2
    bad = write(tmp_path / "verdict.json", json.dumps({"verdict": None, "score": None}))
    assert idea_page.main(["save-review", "--slug", SLUG, "--title", TITLE, "--file", str(run / "blueprint.md"),
                           "--verdict", str(bad)]) == 1
    # A status word the section does not allow is a config problem, and nothing is written
    c = json.loads(Path("wiki.config.json").read_text(encoding="utf-8"))
    c["sections"][IDEAS]["status_words"] = ["new", "done"]
    Path("wiki.config.json").write_text(json.dumps(c), encoding="utf-8")
    assert save_blueprint(run) == 2
    assert not (ws / "wiki" / IDEAS / SLUG).exists()
    # No config anywhere
    monkeypatch.chdir(tmp_path.parent)
    assert idea_page.main(["rebuild", "--slug", SLUG, "--config", str(tmp_path / "none.json")]) == 2


def test_config_folder_names_and_cli(ws: Path) -> None:
    c = json.loads(Path("wiki.config.json").read_text(encoding="utf-8"))
    c["sections"][IDEAS]["idea_page"] = {"blueprints": "ontwerpen", "reviews": "oordelen", "style": "plain"}
    Path("wiki.config.json").write_text(json.dumps(c), encoding="utf-8")
    run = architects_run(ws)
    env = {k: v for k, v in os.environ.items() if k != "NEST_WIKI_CONFIG"}
    p = subprocess.run([sys.executable, str(SCRIPT), "save-blueprint", "--slug", SLUG, "--title", TITLE,
                        "--file", str(run / "blueprint.md"), "--head", str(run / "save-head.md")],
                       cwd=ws, capture_output=True, text=True, encoding="utf-8", env=env, check=False)
    assert p.returncode == 0, p.stderr
    assert p.stdout.count("wrote ") == 2
    assert (ws / "wiki" / IDEAS / SLUG / "ontwerpen" / "2026-11-21-1951-v1.md").is_file()
    assert f"[[{IDEAS}/{SLUG}/ontwerpen/2026-11-21-1951-v1|Blueprint v1]]" in idea_text(ws)
    assert "> [!info]" in idea_text(ws)
    lint_clean()
    shutil.rmtree(ws / ".runs")


# Real workspaces: status words from the top level, headings in desk reports, renamed labels, odd titles

def test_status_words_fall_back_to_the_top_level_list(ws: Path, capsys) -> None:
    c = json.loads((ws / "wiki.config.json").read_text(encoding="utf-8"))
    del c["sections"][IDEAS]["status_words"]
    (ws / "wiki.config.json").write_text(json.dumps(c), encoding="utf-8")
    assert save_blueprint(architects_run(ws)) == 2  # lint would refuse 'worked-out' afterwards
    assert "worked-out" in capsys.readouterr().err
    assert not (ws / "wiki" / IDEAS / SLUG).exists()


def test_a_heading_in_a_desk_report_does_not_cut_the_desks_off(ws: Path) -> None:
    run = architects_run(ws)
    write(run / "surveyor.report.md", "## Findings\n\nClosest: RouteCo | https://example.com\n\n# Loud\n")
    assert save_blueprint(run) == 0
    text = idea_text(ws)
    assert "**Line:** A shared sheet per group" in text and "**Monday:**" in text and "**Hours:**" in text
    bp = next((ws / "wiki" / IDEAS / SLUG / "blueprints").glob("*.md")).read_text(encoding="utf-8")
    assert "#### Findings" in bp and "\n## Findings" not in bp and "\n# Loud" not in bp


def test_ticks_survive_a_renamed_open_points_heading(ws: Path, tmp_path: Path) -> None:
    assert save_blueprint(architects_run(ws)) == 0
    page = ws / "wiki" / IDEAS / SLUG / "idea.md"
    page.write_text(idea_text(ws).replace("- [ ] Spreadsheet", "- [x] Spreadsheet", 1), encoding="utf-8")
    labels = write(tmp_path / "labels.json", json.dumps({"headings": {"open": "Open punten"}}))
    assert idea_page.main(["rebuild", "--slug", SLUG, "--labels", str(labels)]) == 0
    assert "## Open punten" in idea_text(ws) and "- [x] Spreadsheet" in idea_text(ws)


def test_written_pages_are_readable_like_any_other_file(ws: Path) -> None:
    if os.name == "nt":
        pytest.skip("POSIX permission bits")
    assert save_blueprint(architects_run(ws)) == 0
    page = ws / "wiki" / IDEAS / SLUG / "idea.md"
    plain = write(ws / "plain.txt", "x")
    assert page.stat().st_mode & 0o777 == plain.stat().st_mode & 0o777
    page.chmod(0o640)
    assert idea_page.main(["rebuild", "--slug", SLUG]) == 0
    assert page.stat().st_mode & 0o777 == 0o640


@pytest.mark.parametrize("title", ["Yes", "Null", "2026", "1.5", "2026-01-02", "~", "Two\nlines", "on"])
def test_titles_yaml_would_misread_are_quoted(ws: Path, title: str) -> None:
    run = architects_run(ws)
    assert idea_page.main(["save-blueprint", "--slug", SLUG, "--title", title, "--file", str(run / "blueprint.md")]) == 0
    assert frontmatter(idea_text(ws))["title"] == " ".join(title.split())
    assert f"# {' '.join(title.split())}\n" in idea_text(ws)


@pytest.mark.parametrize("verdict", [
    {"verdict": "GO", "score": 7.6, "jury": ["x"]}, {"verdict": "GO", "score": 7.6, "mismatches": ["x"]},
    {"verdict": "GO", "score": "abc"}, {"verdict": "GO", "score": 85}, {"verdict": "GO", "score": 7.6, "jury": {}},
    {"verdict": "GO", "score": 7.6, "mismatches": [{"judge": 1, "notes": "text"}]},
])
def test_a_malformed_verdict_file_is_an_input_error(ws: Path, capsys, verdict: dict) -> None:
    run = council_run(ws)
    write(run / "verdict.json", json.dumps(verdict))
    assert save_review(run) == 1
    assert "verdict.json" in capsys.readouterr().err
    assert not (ws / "wiki" / IDEAS / SLUG).exists()


def test_first_sentence_in_other_scripts() -> None:
    assert idea_page.first_sentences("Ça marche. Écrire vient après.") == "Ça marche."
    assert idea_page.first_sentences("Это работает. Потом пишем.") == "Это работает."
    assert idea_page.first_sentences("Costs e.g. five euros. Then more.") == "Costs e.g. five euros."
