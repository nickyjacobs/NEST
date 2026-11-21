"""Tests for council_score.py: the rubric arithmetic, PARK, the RESHAPE cap and the jury."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import council_score as cs

SCRIPT = Path(cs.__file__)


def judge(value=4, fit=4, time=4, risk=4, cost=4, verdict=None, score=None, idea_alone=None) -> dict:
    j = {"criteria": {"Value": value, "Fit": fit, "Time": time, "Risk": risk, "Cost": cost}}
    if verdict is not None:
        j["verdict"] = verdict
    if score is not None:
        j["score"] = score
    if idea_alone is not None:
        j["idea_alone"] = idea_alone
    return j


def test_score_formula():
    # All fours: weighted average 4, (4 - 1) x 2.5 = 7.5
    r = cs.check_judge(judge(verdict="GO", score=7.5))
    assert r["score"] == 7.5 and r["verdict"] == "GO" and r["mismatches"] == []
    # 5,4,3,3,2: (125 + 80 + 60 + 60 + 30) = 355 -> (3.55 - 1) x 2.5 = 6.375 -> 6.4 (half up)
    r = cs.check_judge(judge(5, 4, 3, 3, 2, verdict="GO WITH CONDITIONS", score=6.4))
    assert r["score"] == 6.4 and r["verdict"] == "GO WITH CONDITIONS"


def test_rounds_half_up_not_to_even():
    # 4,3,3,3,4 -> 100+60+60+60+60 = 340 -> (3.4-1)*2.5 = 6.0 exactly
    assert cs.check_judge(judge(4, 3, 3, 3, 4))["score"] == 6.0
    # 3,3,3,3,4 -> 75+60+60+60+60 = 315 -> 5.375 -> 5.4
    assert cs.check_judge(judge(3, 3, 3, 3, 4))["score"] == 5.4


def test_idea_alone_leaves_time_out():
    # Value 5, Fit 5, Risk 4, Cost 4, Time 1: alone = ((125+100+80+60)/80 - 1) x 2.5 = 8.90625 -> 8.9
    r = cs.check_judge(judge(5, 5, 1, 4, 4, verdict="PARK", idea_alone=8.9))
    assert r["idea_alone"] == 8.9
    assert r["expected_verdict"] == "PARK" and r["verdict"] == "PARK" and r["mismatches"] == ["no score stated; the criteria give 7.1"]


def test_park_rule_overrides_band():
    r = cs.check_judge(judge(5, 5, 2, 4, 4, verdict="GO WITH CONDITIONS", score=7.0))
    assert r["expected_verdict"] == "PARK" and r["verdict"] == "PARK"
    assert any("PARK rule" in m for m in r["mismatches"])


def test_no_park_when_idea_alone_is_weak():
    r = cs.check_judge(judge(3, 3, 1, 3, 3))
    assert r["expected_verdict"] == band_of(r["score"]) != "PARK"


def band_of(score):
    return cs.band(score)


def test_reshape_cap_is_allowed():
    r = cs.check_judge(judge(verdict="RESHAPE", score=7.5))
    assert r["verdict"] == "RESHAPE" and r["mismatches"] == []


def test_label_outside_band_is_replaced():
    r = cs.check_judge(judge(2, 2, 2, 2, 2, verdict="GO", score=2.5))
    assert r["verdict"] == "DROP" and r["stated"]["verdict"] == "GO"
    assert any("does not fit" in m for m in r["mismatches"])


def test_wrong_sum_is_reported():
    r = cs.check_judge(judge(verdict="GO", score=8.2))
    assert r["score"] == 7.5 and "score 8.2 recomputed to 7.5 from the criteria" in r["mismatches"]


@pytest.mark.parametrize("score,label", [(7.5, "GO"), (7.4, "GO WITH CONDITIONS"), (6.0, "GO WITH CONDITIONS"),
                                         (5.9, "RESHAPE"), (4.5, "RESHAPE"), (4.4, "DROP"), (0.0, "DROP")])
def test_bands(score, label):
    assert cs.band(score) == label


def test_criteria_list_form_and_lowercase_verdict():
    j = {"criteria": [{"name": "value", "score": 4}, {"name": "Fit", "score": 4}, {"name": "Time", "score": 4},
                      {"name": "Risk", "score": 4}, {"name": "Cost (money)", "score": 4}],
         "verdict": "go", "score": "7.5/10"}
    r = cs.check_judge(j)
    assert r["checked"] and r["verdict"] == "GO" and r["mismatches"] == []


def test_missing_criteria_cannot_be_checked():
    r = cs.check_judge({"criteria": {"value": 4, "fit": 4}, "verdict": "GO", "score": 8.0})
    assert not r["checked"] and r["score"] == 8.0 and "could not be checked" in r["mismatches"][0]


@pytest.mark.parametrize("bad", [0, 6, 3.5, "4", True])
def test_invalid_criterion_scores(bad):
    with pytest.raises(cs.InvalidJudge):
        cs.check_judge(judge(value=bad))


def test_decide_median_unanimous():
    js = [judge(4, 4, 4, 4, 4, "GO", 7.5), judge(5, 4, 4, 4, 4, "GO", 8.1), judge(5, 5, 4, 5, 4, "GO", 8.9)]
    r = cs.decide(js)
    assert r["score"] == 8.1 and r["verdict"] == "GO" and r["median_judge"] == 2
    assert r["split"] is False and r["borderline"] is False and r["confidence"] == "normal"


def test_decide_split_is_borderline():
    js = [judge(3, 3, 3, 3, 3, "RESHAPE", 5.0), judge(4, 3, 3, 3, 4, "GO WITH CONDITIONS", 6.0),
          judge(4, 4, 4, 4, 4, "GO", 7.5)]
    r = cs.decide(js)
    assert r["verdict"] == "GO WITH CONDITIONS" and r["split"] and r["borderline"]
    assert r["borderline_with"] in ("RESHAPE", "GO") and r["confidence"] == "low"


def test_decide_near_edge_is_borderline_without_split():
    # 6.0 for all three, right on the GO WITH CONDITIONS edge
    js = [judge(4, 3, 3, 3, 4, "GO WITH CONDITIONS", 6.0)] * 3
    r = cs.decide(js)
    assert not r["split"] and r["borderline"] and r["borderline_with"] == "RESHAPE"


def test_decide_reports_mismatches_per_judge():
    js = [judge(verdict="GO", score=7.5), judge(verdict="GO", score=9.9), judge(verdict="GO", score=7.5)]
    r = cs.decide(js)
    assert r["mismatches"] == [{"judge": 2, "notes": ["score 9.9 recomputed to 7.5 from the criteria"]}]
    assert r["score"] == 7.5


def test_decide_light_single_judge():
    r = cs.decide([judge(5, 4, 4, 4, 4, verdict="GO", score=8.1)], light=True)
    assert r["verdict"] == "GO" and r["jury"] == [{"verdict": "GO", "score": 8.1}]
    assert r["jury_incomplete"] is False and r["borderline"] is False


def test_decide_two_judges_takes_the_mean_and_is_borderline():
    # 8.1 and 8.9 stated, recomputed to 8.1 and 9.1: mean 8.6, both GO
    r = cs.decide([judge(5, 4, 4, 4, 4, "GO", 8.1), judge(5, 5, 4, 5, 4, "GO", 9.1)])
    assert r["score"] == 8.6 and r["verdict"] == "GO" and r["median_judge"] is None
    assert r["jury_incomplete"] is True and r["borderline"] is True and r["split"] is False
    assert r["confidence"] == "low"


def test_decide_two_judges_disagreeing_use_the_band_of_the_mean():
    # 5.0 RESHAPE and 7.5 GO: mean 6.25 -> 6.3, GO WITH CONDITIONS; the borderline names a judge's verdict
    r = cs.decide([judge(3, 3, 3, 3, 3, "RESHAPE", 5.0), judge(4, 4, 4, 4, 4, "GO", 7.5)])
    assert r["score"] == 6.3 and r["verdict"] == "GO WITH CONDITIONS"
    assert r["split"] and r["borderline"] and r["borderline_with"] in ("RESHAPE", "GO")


def test_three_files_with_one_unusable_judge_is_incomplete():
    broken = {"criteria": {"value": 4}, "verdict": "GO"}
    r = cs.decide([judge(verdict="GO", score=7.5), broken, judge(verdict="GO", score=7.5)])
    assert r["jury_incomplete"] is True and r["score"] == 7.5 and r["borderline"] is True


def test_full_jury_is_complete():
    assert cs.decide([judge(verdict="GO", score=7.5)] * 3)["jury_incomplete"] is False


def test_cli_check_and_decide(tmp_path):
    paths = []
    for i, j in enumerate([judge(verdict="GO", score=7.5)] * 3):
        p = tmp_path / f"j{i}.json"
        p.write_text(json.dumps(j), encoding="utf-8")
        paths.append(str(p))
    r = subprocess.run(check=False, args=[sys.executable, str(SCRIPT), "check", paths[0]], capture_output=True, text=True)
    assert r.returncode == 0 and json.loads(r.stdout)["score"] == 7.5
    r = subprocess.run(check=False, args=[sys.executable, str(SCRIPT), "decide", *paths], capture_output=True, text=True)
    assert r.returncode == 0 and json.loads(r.stdout)["verdict"] == "GO"
    r = subprocess.run(check=False, args=[sys.executable, str(SCRIPT), "decide", paths[0]], capture_output=True, text=True)
    assert r.returncode == 1 and "needs 3" in r.stderr
    r = subprocess.run(check=False, args=[sys.executable, str(SCRIPT), "decide", "--light", paths[0]], capture_output=True, text=True)
    assert r.returncode == 0
    r = subprocess.run(check=False, args=[sys.executable, str(SCRIPT), "decide", *paths[:2]], capture_output=True, text=True)
    assert r.returncode == 0 and json.loads(r.stdout)["jury_incomplete"] is True
    r = subprocess.run(check=False, args=[sys.executable, str(SCRIPT), "decide", "--light", *paths[:2]],
                       capture_output=True, text=True)
    assert r.returncode == 1


def test_cli_invalid_json(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{nope", encoding="utf-8")
    r = subprocess.run(check=False, args=[sys.executable, str(SCRIPT), "check", str(p)], capture_output=True, text=True)
    assert r.returncode == 1 and "not valid JSON" in r.stderr
