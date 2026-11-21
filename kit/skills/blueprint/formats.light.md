# The Architects: report formats (light)

The light team is four desks in a row: Foreman, Surveyor, Engineer, Draftsman. The blueprint
skill copies one block from this file to the end of each run file, under `## Format`. Field
names, tags, grades and labels are the same contract as in `formats.md`; the blueprint has
the same sixteen sections, so an idea's page looks the same whichever size drew it.

## Word limits

Not counting the Sources lines.

| Desk | Words |
|---|---|
| foreman | 180 |
| surveyor | 300 |
| engineer | 380 |
| draftsman | 1100 |

## Source line

Appended where a format says `<source line>`:

```
1 | title | publisher | YYYY-MM-DD, or undated | url | "a sentence from the page, word for word, that backs your claim"
```

## foreman

```
Settled:
- what the brief, their choices, their lens, their answers or their wiki already decide, under 20 words | where: brief, given, lens, answer or the wiki page's name
- two to five lines
Questions:
- the question to the user, under 25 words | recommended: the answer you'd give in their place, under 15 words | why: what it changes in the blueprint, under 15 words
- at most three, the one that changes the blueprint most first; a single "- none" when nothing only they can decide is still open
- when what the idea even is hangs on one answer, ask only that question, ending with "| first"; the rest comes in your second pass
```

On a rework that answers The Council's verdict, this line goes first:

```
Round one: keep, or again | why, under 20 words: keep when The Surveyor's market and first user still hold; again when the direction changed
```

## surveyor

```
Exists today:
- name | what it does | price, or free | same, partial or adjacent to the idea (fact) [n]
- two to five lines, the closest first; a single "- nothing close" when there's nothing
Closest: the name of the one that comes closest | the url of its own page that you opened; or "none"
Do nothing: what people do today without any product, one sentence
Why now: what changed in the last two years, one sentence (fact) [n], or "nothing specific"
Tooling:
- a library, API, device or service it would be built on | its current price or free | (fact) [n] or (assumption), at most three lines
First user: one concrete person by role and situation, one sentence, not a segment
Job: when [situation], I want to [progress], so I can [outcome]
Evidence:
- where people like that say the problem is real, under 20 words (fact) [n]
- one more, or a single "- none found"
Gaps: what the existing offers leave open, one sentence
Assumptions: what you assumed, under 25 words
Sources: only pages you opened and read, one line each
<source line>
```

## engineer

```
Variants:
- [inversion] a variant in under 25 words
- [constraint] one with no time or money at all
- [analogy] one borrowed from a distant field, the field named
- [smallest] what could exist by Friday
Direction: the line the blueprint takes, one sentence; end it with (yours), (yours, plus ...), (variant: ...) or (open)
Why this one: one sentence against the user's goal and The Surveyor's report (fact) or (assumption)
Already has: the wiki pages that cover part of this and what they cover, one sentence; or "nothing on this"
Beyond the rival: what the smallest version does that the rival's page does not show, one sentence; "nothing: ..." with the reason to build it anyway; or "no rival"
How it works:
- a moving part in plain words, under 20 words
- three to five lines in all
Smallest version: what exists after the first build and what it does, two sentences
Hours: a range to that smallest version, allowing for the half people forget
Needs:
- a tool, account, device, amount of money or person | has it (lens) or new | at most four lines
Rabbit holes:
- a part that could eat the hours, under 20 words
- one more
No-gos:
- what the first version leaves out on purpose, under 15 words
- one more
Monday: the first concrete step this week, under two hours, one sentence
Kill: a measurable state plus a date at which the user stops, one sentence
Sources: only pages you opened and read, one line each, or "- none"
<source line>
```

## draftsman: instructions

At the top of The Draftsman's run file:

> Write the blueprint in Markdown with exactly the '## ' headings of the format below, in
> that order, nothing before the title and nothing after the last section. Prose in short
> paragraphs or '- ' lists; no tables. Every claim carries whose it is: [yours], [proposed],
> [assumed], [open] (at most 3) or [fact n], one label per claim, not per sentence. Rewrite
> the two reports into one voice, keep their facts and sources, drop nothing the user said.
> At most 1100 words, not counting the Sources section.

## draftsman: the blueprint

```
# <the idea's title>

## One-liner
One sentence: what it is, for whom, and the one thing it does better than what they do today.

## Problem and job
Who wants what progress in what situation and what they do today instead; "As the team pictures it: ..." when the story isn't the user's.

## First user and buyer
The first user by role and situation, who pays and what they'd pay.

## Why now
What changed that makes this possible or wanted now, with sources; or one line that nothing specific did.

## Landscape
What exists (name, price, how close), the do-nothing option, the gap. For the closest rival: part by part what it already does of what this idea sells, and what is left.

## Directions explored
The Engineer's variants in one line each (lens in brackets), which one the blueprint takes and why.

## The solution
How it works, the moving parts, the smallest version and what it does.

## Scope
Hours, what the first version leaves out, the rabbit holes; a Boundary paragraph when the idea touches other people or their systems or data.

## Model
Only when there's something to sell or save; else "Not for sale: ..." in one line.

## Assumptions and risks
The load-bearing assumption first, then two or three more with their grade (fact, assumption, speculation); the pre-mortem's three reasons.

## Validation plan
Per assumption the cheapest test within a week; the kill criterion with its date.

## First step and resources
What the user does Monday, what they need (has / new), what their wiki already holds on this, hours to the smallest version.

## Open questions and tensions
At most three [open] points, each on one line: "- the decision, as a question to them | options: A or B | recommended: A, because ... [open]"; then the two questions The Council will ask, each with the blueprint's answer.

## Sources
The sources the desks read, renumbered 1..n, each with the desk's quote: n | title | publisher | YYYY-MM-DD | url | "quote"

## Council brief
A neutral brief for The Council in the third person, 60 to 100 words: what it is, who it's for, what the user said about goal, time and money, and the smallest version. No praise, no opinion.

## What changed
Only from version 2: what this version changes and the feedback it answers, one line each. For version 1: omit this section.
```
