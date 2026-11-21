# The Council: report formats (full)

How each seat writes its report. The agent files say how a seat thinks; the form lives
here, so a reworded agent can't break the board, the jury's sums or the saved review.

When you write a seat's run file, copy that seat's block below verbatim (without the
fence) under the run file's `## Format` heading, and the length line above it. The agents
write their reports in the user's language, but the field names (`Best version:`,
`Risks:`, `Verdict:` and so on), the verdict labels and the JSON keys stay as written here:
the skill, `council_score.py` and The Architects read them back by these names.

<!-- customise: currency (the € signs in the investor and judge formats, in the user's currency) -->

## The source line

Every `Sources:` list in every format uses this line, one per page:

```text
1 | title | publisher | YYYY-MM-DD, or undated | url | "a sentence from the page, word for word, that backs your claim"
```

## believer

Length: at most 180 words, not counting the Sources lines.

```text
Best version: the strongest form of the idea, one sentence
Upsides:
- an upside in under 20 words (fact) or (assumption)
- a second one
- a third one
Ceiling: how far it could go if it works, one sentence
First step: one thing the user can do within a week that tells them whether it's worth more, one sentence
Assumptions: what you assumed, under 20 words
Load-bearing:
- the claim your report rests on most that a page can confirm or refute (a fact, a price, a rule, what a tool does; a figure for demand or income first), under 25 words | its source number, or unchecked
- a second one, or leave it at one
Sources: only pages you opened and read, one line each, in the source-line form
```

## skeptic

Length: at most 180 words, not counting the Sources lines.

```text
Risks:
- [high] the most serious risk, how likely and how bad together, in under 20 words (fact) or (assumption)
- [medium] the next one
- [low] three or four in all, most serious first; a single "- none serious" when there aren't any
Pre-mortem: it is six months later and it failed; the most likely reason, one sentence
First version: hours until a first working version, as a range, nothing else
Upkeep: hours per month to keep it running, nothing else
Competes with: what those hours come out of when they'd spend them, now unless the idea says when (their job, study, training, family, rest), and whether that hurts, one sentence
Ruin risk: none, possible or likely, only for harm they can't undo (their job, money they can't spare, their data, legal trouble)
Assumptions: what you assumed, under 20 words
Load-bearing:
- the claim your report rests on most that a page can confirm or refute (a fact, a price, a rule, what a tool does; a figure for demand or income first), under 25 words | its source number, or unchecked
- a second one, or leave it at one
Sources: only pages you opened and read, one line each, in the source-line form
```

## investor

Length: at most 180 words, not counting the Sources lines.

```text
One-off: € amount only, 0 when there's nothing to buy
Monthly: € amount only, 0 when nothing recurs
First year: € amount (careful case € amount)
Costs:
- item | € amount | one-off, monthly or yearly | source number, or estimate (at most four lines)
Free route: how to do it for 0 in one sentence, or none
Already paid: what they already have or pay that covers part of it, one sentence, or nothing
Earns or saves: one sentence with its basis (what comparable offers charge, with its source number), or nothing claimed
Break-even: how many customers at their price, or at what comparable offers charge, cover the first year, one sentence, or not for sale
Load-bearing:
- the claim your report rests on most that a page can confirm or refute (a fact, a price, a rule, what a tool does; a figure for demand or income first), under 25 words | its source number, or unchecked
- a second one, or leave it at one
Sources: only pages you opened and read, one line each, in the source-line form
```

## outsider

Length: at most 120 words.

```text
First look: what someone with no context makes of the idea, one sentence
Unclear:
- what the pitch leaves open, or what only makes sense to the person behind it, under 20 words
- one or two more, or a single "- nothing"
Who else: who else would want this, or nobody, one sentence
Plainer way: the simplest way to get the same result, one sentence
Assumptions: what you assumed, under 20 words
```

## verifier

Length: at most 220 words, not counting the Sources lines.

```text
Checks:
- 1 | confirmed, contradicted or unclear | what the page says about it, under 25 words | the source number of the page you read
- one line per claim in the run file, numbered as there
Sources: only pages you opened and read, one line each, in the source-line form
```

## judge

Length: at most 300 words, not counting the JSON block.

```text
Verdict: GO, GO WITH CONDITIONS, RESHAPE, PARK or DROP
Score: 0.0 to 10.0
Idea alone: 0.0 to 10.0, the same score with Time left out
Worth it: one sentence under 30 words that opens with yes, no or only if and sets the hours and the money against what they get
Criteria:
- Value: 1-5 | why, under 15 words | rests on: the member and source number (skeptic [2]), the fact check (check 3), the lens, or nothing checked
- Fit: 1-5 | why | rests on: ...
- Time: 1-5 | the hours and why | rests on: ...
- Risk: 1-5 | why | rests on: ...
- Cost: 1-5 | why | rests on: ...
Strongest for: one sentence
Biggest risk: the one most likely to sink it or hurt them, one sentence
Clash: where the members disagree most, whose side you take and why, one sentence, or none when they agree
Missed by all four: one sentence
Rests on: the one or two facts or assumptions your verdict rests on most, each marked (checked), (contradicted) or (unchecked) as the fact check has them
Flips if: what, if it turned out otherwise, would move your verdict to another band, one sentence
Conditions: what must hold, one sentence, or none; a condition that goes against something the user decided says so in its own words: "(against their choice: the reason)"
Kill criteria: a measurable state plus a date at which they stop, one sentence
Next step: one concrete step within a week that tests this idea, taken from a member's report, one sentence; when a condition holds their hours back until a date, either date this step after it or call it the exception there and say how long it takes
Revisit: YYYY-MM, only for PARK
Confidence: low, medium or high, then why in a few words
```

Then, as the very last thing, the JSON block below with the same values as the lines
above (the labels in English as listed, the scores as numbers):

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
