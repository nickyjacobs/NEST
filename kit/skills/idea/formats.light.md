# The Council: report formats (light)

The same fields as `formats.md`, shorter, with one load-bearing claim per web seat and no
fact check. Copy a seat's block verbatim (without the fence) under the run file's
`## Format` heading, with its length line. The agents write in the user's language; the
field names, the verdict labels and the JSON keys stay as written here.

<!-- customise: currency (the € signs in the investor and judge formats, in the user's currency) -->

## The source line

```text
1 | title | publisher | YYYY-MM-DD, or undated | url | "a sentence from the page, word for word, that backs your claim"
```

## believer

Length: at most 120 words, not counting the Sources lines.

```text
Best version: the strongest form of the idea, one sentence
Upsides:
- an upside in under 20 words (fact) or (assumption)
- one or two more
Ceiling: how far it could go if it works, one sentence
First step: one thing the user can do within a week that tells them whether it's worth more, one sentence
Load-bearing:
- the one claim your report rests on most that a page can settle, under 25 words | its source number, or unchecked
Sources: only pages you opened and read, one line each, in the source-line form, or none
```

## skeptic

Length: at most 120 words, not counting the Sources lines.

```text
Risks:
- [high] the most serious risk, how likely and how bad together, in under 20 words (fact) or (assumption)
- [medium] or [low], two or three in all, most serious first; a single "- none serious" when there aren't any
Pre-mortem: it is six months later and it failed; the most likely reason, one sentence
First version: hours until a first working version, as a range, nothing else
Upkeep: hours per month to keep it running, nothing else
Competes with: what those hours come out of, and whether that hurts, one sentence
Ruin risk: none, possible or likely
Load-bearing:
- the one claim your report rests on most that a page can settle, under 25 words | its source number, or unchecked
Sources: only pages you opened and read, one line each, in the source-line form, or none
```

## investor

Length: at most 120 words, not counting the Sources lines.

```text
One-off: € amount only, 0 when there's nothing to buy
Monthly: € amount only, 0 when nothing recurs
First year: € amount (careful case € amount)
Costs:
- item | € amount | one-off, monthly or yearly | source number, or estimate (at most three lines)
Free route: how to do it for 0 in one sentence, or none
Earns or saves: one sentence with its basis, or nothing claimed
Break-even: how many customers cover the first year, one sentence, or not for sale
Load-bearing:
- the one claim your report rests on most that a page can settle, under 25 words | its source number, or unchecked
Sources: only pages you opened and read, one line each, in the source-line form, or none
```

## outsider

Length: at most 80 words.

```text
First look: what someone with no context makes of the idea, one sentence
Unclear:
- what the pitch leaves open, or what only makes sense to the person behind it, under 20 words
- one more, or a single "- nothing"
Who else: who else would want this, or nobody, one sentence
Plainer way: the simplest way to get the same result, one sentence
```

## judge

Length: at most 220 words, not counting the JSON block.

```text
Verdict: GO, GO WITH CONDITIONS, RESHAPE, PARK or DROP
Score: 0.0 to 10.0
Idea alone: 0.0 to 10.0, the same score with Time left out
Worth it: one sentence under 30 words that opens with yes, no or only if and sets the hours and the money against what they get
Criteria:
- Value: 1-5 | why, under 15 words | rests on: the member and source number (skeptic [2]), the lens, or nothing checked
- Fit: 1-5 | why | rests on: ...
- Time: 1-5 | the hours and why | rests on: ...
- Risk: 1-5 | why | rests on: ...
- Cost: 1-5 | why | rests on: ...
Strongest for: one sentence
Biggest risk: the one most likely to sink it or hurt them, one sentence
Clash: where the members disagree most and whose side you take, one sentence, or none
Missed by all four: one sentence
Rests on: the one or two facts or assumptions your verdict rests on most, each marked (quote found), (quote not found) or (unchecked) as the spot check has them
Conditions: what must hold, one sentence, or none; "(against their choice: the reason)" where it goes against something the user decided
Kill criteria: a measurable state plus a date at which they stop, one sentence
Next step: one concrete step within a week that tests this idea, taken from a member's report, one sentence
Revisit: YYYY-MM, only for PARK
Confidence: low, medium or high, then why in a few words
```

Then, as the very last thing, the JSON block below with the same values as the lines
above:

```json
{
  "verdict": "the label from your Verdict line",
  "score": 0.0,
  "idea_alone": 0.0,
  "criteria": {"value": 1, "fit": 1, "time": 1, "risk": 1, "cost": 1}
}
```

Replace every value with your own: `verdict` exactly one of GO, GO WITH CONDITIONS,
RESHAPE, PARK or DROP; `score` and `idea_alone` as numbers with one decimal; each criterion
a whole number from 1 to 5. Nothing after the block.
