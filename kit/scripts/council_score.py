# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""JUDGE JSON SHAPE

A council judge ends its report with one fenced ```json block holding exactly this object.
Keys are lowercase snake_case; any other key is ignored here.

  {
    "criteria": {"value": 4, "fit": 3, "time": 2, "risk": 3, "cost": 4},
    "idea_alone": 6.3,
    "verdict": "GO WITH CONDITIONS",
    "score": 6.1
  }

  criteria    required: value, fit, time, risk, cost, each a whole number 1 to 5
              (also accepted: capitalised keys, or a list [{"name": "value", "score": 4}, ...])
  idea_alone  optional: the judge's score for the idea with Time left out, 0 to 10
  verdict     required: "GO", "GO WITH CONDITIONS", "RESHAPE", "PARK" or "DROP"
  score       required: the judge's stated score, 0 to 10, one decimal

The criteria keys are the five English words, in any language of the report: a judge whose
criteria this script cannot read (a key missing, or translated) cannot be checked, and its own
score and verdict are not taken on trust. A score outside 0 to 10 is refused.

USAGE

  council_score.py check <judge.json>                     recompute one judge
  council_score.py decide <j1.json> <j2.json> <j3.json>   the full jury of three
  council_score.py decide <j1.json> <j2.json>             a jury of two, when a judge failed:
                                                          mean score, borderline, jury_incomplete
  council_score.py decide --light <judge.json>            the light Council: one judge
A path of "-" reads that judge from stdin. Output is JSON on stdout; exit 0 when the input could
be read (mismatches are part of the output, not an error), 1 with {"error": ...} on stderr for
unreadable or invalid input.

decide output keys: score, verdict, idea_alone, jury [{verdict, score}], split, borderline,
borderline_with, jury_incomplete, confidence, median_judge (null for a jury of two),
mismatches [{judge, notes}], judges (the full check of each judge).

THE RUBRIC

  weights     Value 25, Fit 20, Time 20, Risk 20, Cost 15
  score       (weighted average of the criteria - 1) x 2.5, rounded half up to one decimal
  idea alone  the same over Value, Fit, Risk and Cost only (weights 25, 20, 20, 15 out of 80)
  bands       GO >= 7.5, GO WITH CONDITIONS >= 6.0, RESHAPE >= 4.5, DROP below
  PARK        when idea alone >= 6.0 but Time <= 2: a good idea at the wrong moment
  RESHAPE cap a judge may always say RESHAPE where the band says GO, GO WITH CONDITIONS or PARK
              (a ruin risk caps the verdict); any other label outside the rubric is replaced

THE JURY

Each judge is checked first. A judge that could not be checked (criteria missing) counts as absent,
whatever score and verdict it states. Of three, the median judge by score gives the verdict. Of two, the
score is the mean of the two; the verdict is theirs when they agree, else the band of the mean;
the result is always borderline and carries "jury_incomplete": true. "split" is true when judges
land on different verdicts; "borderline" is true on a split, on a jury of two, or when the score
sits within 0.3 of its band's edge, and "borderline_with" names the verdict it could have been.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from fractions import Fraction
from pathlib import Path

WEIGHTS = {"value": 25, "fit": 20, "time": 20, "risk": 20, "cost": 15}
BANDS = ((7.5, "GO"), (6.0, "GO WITH CONDITIONS"), (4.5, "RESHAPE"), (0.0, "DROP"))
EDGES = ((7.5, "GO WITH CONDITIONS", "GO"), (6.0, "RESHAPE", "GO WITH CONDITIONS"), (4.5, "DROP", "RESHAPE"))
VERDICTS = ("GO", "GO WITH CONDITIONS", "RESHAPE", "PARK", "DROP")
PARK_IDEA_ALONE = 6.0
PARK_MAX_TIME = 2
BORDER = 0.3
TOLERANCE = 0.05
JURORS = 3


class InvalidJudge(ValueError):
    pass


def round_half_up(x: Fraction) -> float:
    return math.floor(x * 10 + Fraction(1, 2)) / 10


def band(score: float) -> str:
    return next((label for floor, label in BANDS if score >= floor), BANDS[-1][1])


def normalise_verdict(raw: object) -> str:
    text = " ".join(str(raw or "").upper().replace("_", " ").replace("-", " ").split())
    return text if text in VERDICTS else ""


def as_number(raw: object) -> float | None:
    if raw is None or raw == "":
        return None
    text = str(raw).split("/")[0].strip()
    if re.fullmatch(r"\d+,\d+", text):  # a decimal comma, as many languages write it
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def stated_number(judge: dict, key: str) -> float | None:
    """A score the judge states, refused when it is not a number from 0 to 10."""
    value = as_number(judge.get(key))
    if value is not None and not (math.isfinite(value) and 0 <= value <= 10):
        raise InvalidJudge(f"{key} must be a number from 0 to 10, got {judge.get(key)!r}")
    return value


def read_criteria(raw: object) -> tuple[dict[str, int], list[str]]:
    """The criteria scores by rubric key, plus problems with them."""
    pairs: list[tuple[str, object]] = []
    if isinstance(raw, dict):
        pairs = [(str(k), v) for k, v in raw.items()]
    elif isinstance(raw, list):
        pairs = [(str(c.get("name", "")), c.get("score")) for c in raw if isinstance(c, dict)]
    scores: dict[str, int] = {}
    problems: list[str] = []
    for name, value in pairs:
        key = next((k for k in WEIGHTS if name.strip().lower().startswith(k)), None)
        if key is None or key in scores:
            continue
        if (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
                or value != int(value) or not 1 <= value <= 5):
            problems.append(f"{key} must be a whole number from 1 to 5, got {value!r}")
            continue
        scores[key] = int(value)
    return scores, problems


def check_judge(judge: dict) -> dict:
    """One judge, checked against the rubric. The result keeps the judge's own figures beside
    the recomputed ones, and lists every mismatch."""
    if not isinstance(judge, dict):
        raise InvalidJudge("a judge must be a JSON object")
    scores, problems = read_criteria(judge.get("criteria"))
    if problems:
        raise InvalidJudge("; ".join(problems))
    stated_score = stated_number(judge, "score")
    stated_alone = stated_number(judge, "idea_alone")
    stated_verdict = normalise_verdict(judge.get("verdict"))
    out: dict = {
        "criteria": scores,
        "stated": {"score": stated_score, "idea_alone": stated_alone, "verdict": stated_verdict or None},
        "mismatches": [],
    }
    if judge.get("verdict") and not stated_verdict:
        out["mismatches"].append(f"verdict {judge.get('verdict')!r} is not one of {', '.join(VERDICTS)}")
    if len(scores) < len(WEIGHTS):
        missing = [k for k in WEIGHTS if k not in scores]
        raw = judge.get("criteria")
        names = list(raw) if isinstance(raw, dict) else [c.get("name", "") for c in raw or [] if isinstance(c, dict)]
        unknown = [str(n) for n in names if not any(str(n).strip().lower().startswith(k) for k in WEIGHTS)]
        hint = (f"; not recognised: {', '.join(unknown)} (the keys are {', '.join(WEIGHTS)}, in English "
                "whatever the language of the report)") if unknown else ""
        out["mismatches"].append(f"criteria missing ({', '.join(missing)}), so the score could not be checked "
                                 f"and this judge counts as absent{hint}")
        out.update(score=stated_score, idea_alone=stated_alone, verdict=stated_verdict or None,
                   expected_verdict=None, checked=False)
        return out

    weighted = sum(WEIGHTS[k] * scores[k] for k in WEIGHTS)
    score = round_half_up(Fraction(weighted - 100, 40))
    alone_weighted = weighted - WEIGHTS["time"] * scores["time"]
    alone = round_half_up(Fraction(alone_weighted - 80, 32))
    park = alone >= PARK_IDEA_ALONE and scores["time"] <= PARK_MAX_TIME
    expected = "PARK" if park else band(score)
    allowed = {expected} | ({"RESHAPE"} if expected in ("GO", "GO WITH CONDITIONS", "PARK") else set())

    if stated_score is None:
        out["mismatches"].append(f"no score stated; the criteria give {score}")
    elif abs(stated_score - score) > TOLERANCE:
        out["mismatches"].append(f"score {stated_score} recomputed to {score} from the criteria")
    if stated_alone is not None and abs(stated_alone - alone) > TOLERANCE:
        out["mismatches"].append(f"idea alone {stated_alone} recomputed to {alone}")
    verdict = stated_verdict if stated_verdict in allowed else expected
    if stated_verdict and stated_verdict not in allowed:
        why = (f"idea alone {alone} with Time {scores['time']} is the PARK rule" if park
               else f"the band for {score}")
        out["mismatches"].append(f"verdict {stated_verdict} does not fit the rubric ({why} gives {expected})")
    elif not stated_verdict:
        out["mismatches"].append(f"no verdict stated; the rubric gives {expected}")
    out.update(score=score, idea_alone=alone, verdict=verdict, expected_verdict=expected, checked=True)
    return out


def neighbour(score: float | None, verdict: str | None) -> str:
    """The band next door when the score sits within BORDER of an edge, only when the verdict
    follows the score (a PARK or a RESHAPE cap is a rule, not a close call)."""
    if score is None or verdict != band(score):
        return ""
    for edge, below, above in EDGES:
        if abs(score - edge) <= BORDER + 1e-9:
            return above if score < edge else below
    return ""


def decide(judges: list[dict], light: bool = False) -> dict:
    checked = [check_judge(j) for j in judges]
    usable = [c for c in checked if c["checked"]]  # an unchecked judge's own figures are not taken on trust
    incomplete = not light and len(usable) < JURORS
    result: dict = {"judges": checked, "jury_incomplete": incomplete,
                    "mismatches": [{"judge": i + 1, "notes": c["mismatches"]} for i, c in enumerate(checked) if c["mismatches"]]}
    jury = [{"verdict": c["verdict"], "score": c["score"]} for c in checked]
    if not usable:
        result.update(score=None, verdict=None, idea_alone=None, median_judge=None, jury=jury, split=False,
                      borderline=False, borderline_with="", confidence="none")
        return result
    if len(usable) == 2:
        a, b = usable
        score = round_half_up(Fraction(str(a["score"])) / 2 + Fraction(str(b["score"])) / 2)
        alones = [c["idea_alone"] for c in usable if c["idea_alone"] is not None]
        alone = round_half_up(sum(Fraction(str(x)) for x in alones) / len(alones)) if alones else None
        verdict = a["verdict"] if a["verdict"] and a["verdict"] == b["verdict"] else band(score)
        others = [c["verdict"] for c in usable if c["verdict"] and c["verdict"] != verdict]
        borderline_with = others[0] if others else neighbour(score, verdict)
        result.update(score=score, verdict=verdict, idea_alone=alone, median_judge=None, jury=jury,
                      split=bool(others), borderline=True, borderline_with=borderline_with, confidence="low")
        return result
    ranked = sorted(usable, key=lambda c: c["score"])
    mid = ranked[(len(ranked) - 1) // 2]
    others = [c["verdict"] for c in usable if c["verdict"] and c["verdict"] != mid["verdict"]]
    split = bool(others)
    borderline_with = max(set(others), key=others.count) if others else neighbour(mid["score"], mid["verdict"])
    result.update(
        score=mid["score"],
        verdict=mid["verdict"],
        idea_alone=mid["idea_alone"],
        median_judge=checked.index(mid) + 1,
        jury=jury,
        split=split,
        borderline=bool(borderline_with) or incomplete,
        borderline_with=borderline_with,
        confidence="low" if split or incomplete else ("medium" if borderline_with else "normal"),
    )
    return result


def load(path: str) -> dict:
    try:
        text = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
        data = json.loads(text)
    except OSError as e:
        raise InvalidJudge(f"{path}: {e.strerror or e}") from e
    except ValueError as e:
        raise InvalidJudge(f"{path}: not valid JSON ({e})") from e
    if not isinstance(data, dict):
        raise InvalidJudge(f"{path}: a judge must be a JSON object")
    return data


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Check The Council's arithmetic.")
    sub = ap.add_subparsers(dest="command", required=True)
    p_check = sub.add_parser("check", help="Recompute one judge's score and verdict")
    p_check.add_argument("judge")
    p_decide = sub.add_parser("decide", help="The jury's verdict from three judges (or one with --light)")
    p_decide.add_argument("judges", nargs="+")
    p_decide.add_argument("--light", action="store_true", help="The light Council: exactly one judge")
    args = ap.parse_args(argv)
    try:
        if args.command == "check":
            result = check_judge(load(args.judge))
        else:
            allowed = (1,) if args.light else (JURORS - 1, JURORS)
            if len(args.judges) not in allowed:
                raise InvalidJudge("decide needs 3 judge files (2 when one judge failed), or --light with one; "
                                   f"got {len(args.judges)}")
            result = decide([load(p) for p in args.judges], light=args.light)
    except InvalidJudge as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 1
    except (ValueError, TypeError, OverflowError, AttributeError) as e:  # a shape no judge should have
        print(json.dumps({"error": f"a judge file is not in the judge JSON shape ({e})"}), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
