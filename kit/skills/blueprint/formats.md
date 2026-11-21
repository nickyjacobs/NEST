# The Architects: report formats (full)

The blueprint skill copies one block from this file to the end of each run file, under
`## Format`. The agents say how a desk thinks; the form lives here, so the skill can read the
reports by their field names and a reworded agent can't break the flow. Field names, lens
tags, grades and labels are a contract between this file, `reference.md` and the agents:
when the setup translates them, it translates them everywhere at once.

## Word limits

Not counting the Sources lines.

| Desk | Words |
|---|---|
| foreman | 260 |
| surveyor | 260 |
| dreamer | 280 |
| client | 220 |
| engineer | 370 |
| inspector | 460 |
| draftsman | 1800 (the blueprint is a page: 1700 to 2300 words in practice) |

## Source line

Every desk with web access ends its report with this block. The skill appends this line to
each of those formats where it says `<source line>`:

```
1 | title | publisher | YYYY-MM-DD, or undated | url | "a sentence from the page, word for word, that backs your claim"
```

## foreman

```
Settled:
- what the brief, their choices, their lens, their answers or their wiki already decide that the blueprint needs, under 20 words | where: brief, given, lens, answer or the wiki page's name
- three to six lines
Questions:
- the question to the user, under 25 words | recommended: the answer you'd give in their place from what you know of them, under 15 words | why: what it changes in the blueprint, under 15 words
- at most five, the one that changes the blueprint most first; a single "- none" when nothing only they can decide is still open
- when the idea is so open that what it even is hangs on an answer (what it sells, who it's for), ask only that question, at most two, each ending with "| first"; the questions that hang on it come in your second pass, after their answer
```

## foreman, rework

On a rework that answers The Council's verdict, this line goes first, above the foreman block:

```
Round one: keep, or again | why, under 20 words: keep when the market, the variants and the first user of the earlier version still hold for what this version becomes; again when the direction changed (another product, another first user, free instead of paid)
```

## surveyor

```
Exists today:
- name | what it does | price, or free | same, partial or adjacent to the idea (fact) [n]
- three to six lines, the closest first; a single "- nothing close" when there's nothing
Closest: the name of the one that comes closest | the url of its own page that you opened (its repository, docs or product page); or "none" when nothing is close
Do nothing: what people in this situation do today without any product, one sentence
Tried before: an earlier attempt at this and why it died or stalled, one sentence (fact) [n] or (assumption), or "none found"
Why now: what changed in the last two years that makes this possible or wanted, one sentence (fact) [n], or "nothing specific"
Tooling:
- a library, API, device or service it would be built on today | its current price or free | (fact) [n] or (assumption), at most four lines
Reference prices: what comparable things sell or rent for today, one or two lines with [n]
Gaps: what the existing offers leave open, one sentence
Assumptions: what you assumed, under 25 words
Sources: only pages you opened and read, one line each
<source line>
```

## dreamer

```
Problem as I read it: one sentence: who wants what progress, in what situation
Variants:
- [inversion] a variant in under 25 words
- [constraint] one with ten times the time or money, and one with none at all (two lines)
- [analogy] one borrowed from a distant field with the same structure, the field named
- [perspective] one seen from another user, buyer or operator
- [scamper] one that substitutes, combines, removes or reverses a part
- [tail] one that sounds implausible and would be remarkable if it worked
- eight to twelve in all, at least one per lens, no ranking and no favourite
Sharpest: the one variant that changes the idea most, and what it changes, one sentence, no verdict on whether it's better
Smallest: the variant that could exist by Friday, one sentence
Question: the one question whose answer picks between the variants, one sentence
```

## client

```
Who I am: the first user, concrete (role, situation, what my week looks like), one sentence, not a segment
My job: when [situation], I want to [progress], so I can [outcome]
Today I: what I do now, with what, and what it costs me in time, money or annoyance, one or two sentences
Try it if: what would make me try this, one sentence
Stay if: what would make me keep using it after a month, one sentence
Deal-breakers:
- what makes me drop it in week one, under 20 words
- one or two more
Would pay: whether I'd pay, how much and how (one-off, monthly, nothing), one sentence; or "not me, but ... would"
Buyer: who pays when it isn't me, one sentence, or "same"
Evidence:
- where people like me say this problem is real (a thread, a review, a job post, a question), under 20 words (fact) [n]
- one or two more, or a single "- none found"
Ask me:
- a question about my past behaviour, not about the idea (how I handled it last time, what I paid, what I tried)
- a second
- a third
Sources: only pages you opened and read, one line each
<source line>
```

## engineer

```
Direction: the line the blueprint takes, one sentence; end it with (yours) when it's the user's own idea exactly as pitched, (yours, plus ...) when you added a part they never named, (variant: ...) when it's one of The Dreamer's, or (open) when two lines are equally good and the user has to pick
Why this one: one sentence against their goal and the three reports (fact) or (assumption)
Already has: what the user's wiki already holds that covers part of this, from the pages the run file lists and you opened: the page's name and what it covers, one or two sentences; "nothing on this" when it lists none or none fits
Settled: the one thing your direction rests on that a page can settle today, and what that page says (fact) [n], from the rival's page, their wiki or a page you opened; "nothing a page settles" when it rests on the user or on people
Beyond the rival: what the smallest version does that the closest rival's page does not show, one sentence, (fact) when the run file has that page, else (assumption); "nothing: ..." with the reason to build it anyway when the page covers it all; "no rival" when The Surveyor named none
How it works:
- a moving part in plain words, under 20 words
- three to five lines in all
Smallest version: what exists after the first build and what it does, two sentences
Hours: a range to that smallest version, allowing for the half people forget, nothing else
Appetite: how much of the user's time this deserves before it has to prove something, one sentence
Needs:
- a tool, account, device, amount of money or person | has it (lens) or new | one line each, at most five
Rabbit holes:
- a part that could eat the hours, under 20 words
- one or two more
No-gos:
- what the first version leaves out on purpose, under 15 words
- one or two more
Monday: the first concrete step the user takes this week, under two hours, one sentence
Kill: a measurable state plus a date at which the user stops, one sentence
Assumptions: what you assumed, under 25 words
Sources: only pages you opened and read (tooling, prices), one line each, or "- none"
<source line>
```

## inspector

```
Overlap:
- a part the idea sells as its own (from the brief, the user's choices and the round-one reports), under 12 words | yes, partly, no, or not on the page | where the rival's page says so: the heading, option or file it names, or "-"
- one line per part, four to eight lines, the parts the idea leans on most first; a single "- no rival page" when the run file has no rival page
Checked:
- a claim of the reports the blueprint leans on that a page can settle, under 20 words | confirmed, contradicted or unclear | what the page says, under 20 words [n]
- two to four lines, the claim most rests on first; a single "- nothing a page settles" when none is left
Load-bearing: the one assumption that, if false, makes the rest pointless, one sentence (fact), (assumption) or (speculation); what the rival's page in the run file settles is a (fact), never a test to hand the user
Assumptions:
- the assumption in under 20 words | how to test it within a week for next to nothing | fact, assumption or speculation
- four to six lines in all, the most load-bearing first; a test is for what only the user or other people can show, never for what a page in the run file already settles
Boundary: only for an idea that touches other people or their systems or data: where the line runs between what uses only public or own data and what reaches others directly or needs their consent or permission, and which side each moving part falls on, one or two sentences; "not applicable" otherwise
Pre-mortem:
- it is a year later and it failed; the most likely reason, under 20 words
- the second most likely
- the third
Unknowns:
- what none of the reports knows and the user should find out before building, under 20 words
- one or two more, or a single "- none"
Council:
- a question The Council will ask that the blueprint must already answer, under 20 words
- a second
Tension: where the reports disagree, both sides in one sentence, no side taken; or "none"
Sources: only pages you opened and read for Checked, one line each, or "- none"
<source line>
```

## draftsman: instructions

These go at the top of The Draftsman's run file, in place of the plain-text instruction the
other desks get:

> Write the blueprint in Markdown with exactly the '## ' headings of the format below, in
> that order, nothing before the title and nothing after the last section. Prose in short
> paragraphs or '- ' lists; no tables. Every claim carries whose it is: [yours] for what the
> brief says the user said or decided, or what they answered (the interview, their answers
> to earlier points), [proposed] for a choice the team makes for them that they can take or
> leave (a variant, the scope, the hours planned, a tool, a step, a test), [assumed] for a
> claim about the world no read page backs (what users do, what a market pays, what a tool or
> a rule allows), [open] for a decision only the user can make (never a fact a page could
> settle; at most 5); a fact from a read page carries its source number as [fact n]. A
> desk's words are material: rewrite them into one voice, keep its facts and its sources,
> drop nothing the user said. One label per claim, not per sentence: a paragraph or list
> item that is wholly the team's carries one [proposed] or [assumed] at its end; a label only
> changes where the owner changes. Where two desks disagree, keep both sides under Open
> questions and tensions; don't smooth it over. At most 1800 words, not counting the Sources
> section.

## draftsman: the blueprint

```
# <the idea's title>

## One-liner
One sentence: what it is, for whom, and the one thing it does better than what they do today. Then one short paragraph as if it already exists and is being announced.

## Problem and job
Who wants what progress in what situation, what they do today instead and what that costs them. One concrete story; when the story is the team's and not the user's, its first words say so ("As the team pictures it: ...").

## First user and buyer
The first user by role and situation; who pays and what they'd pay; what makes them try it and stay.

## Why now
What changed that makes this possible or wanted now, with sources.

## Landscape
What exists (name, price, how close), the do-nothing option, what was tried before and why it died, the gap this fills. For the closest rival: part by part what it already does of what this idea sells (The Inspector's Overlap, with where its page says so), and what is left after that.

## Directions explored
The variants looked at in one line each (lens in brackets), which one the blueprint takes and why, and which were set aside and why. When the choice is the user's: say so and give the two lines.

## The solution
How it works in plain words, the moving parts, the smallest version and what it does.

## Scope
Appetite (hours and weeks), what the first version leaves out on purpose, the rabbit holes. When The Inspector drew a Boundary: that, as its own paragraph.

## Model
Only when there's something to sell or save: channels, price, costs, what the user already has, the unfair advantage. Else: "Not for sale: ..." in one line.

## Assumptions and risks
The load-bearing assumption first, then the ranked list, each with its grade (fact, assumption, speculation); the pre-mortem's three reasons.

## Validation plan
Per assumption the cheapest test and what result ends it; the kill criterion with its date.

## First step and resources
What the user does Monday, what they need (marked: has / new), what their wiki already holds on this (The Engineer's Already has, with the page names), hours to the smallest version.

## Open questions and tensions
Only what the user alone can decide, at most five [open] points, the one that changes the blueprint most first, each on one line: "- the decision, as a question to them | options: A or B | recommended: A, because ... [open]". The Client's Ask me questions count among them only when the user is the first user themselves; when the first user is someone else they are a test under Validation plan. What a page could settle but no desk read is never open here: it is [assumed] under Assumptions and risks, with "to check:" and the page that would settle it. Where the desks disagreed: as a decision for the user with options and a recommendation when it's theirs to make, else both sides in one line, [assumed].

## Sources
The sources the desks read, renumbered 1..n, each with the desk's quote: n | title | publisher | YYYY-MM-DD | url | "quote"

## Council brief
A neutral brief for The Council in the third person, 80 to 120 words: what it is, who it's for, what the user said about goal, time and money, and the smallest version. No praise, no opinion, no hint of what to weigh.

## What changed
Only from version 2: what this version changes against the earlier one and the feedback it answers, one line each. For version 1: omit this section.
```
