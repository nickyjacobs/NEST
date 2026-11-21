---
title: {{title}}
created: {{date of the first run in the folder}}
updated: {{date of the latest run}}
tags: [idea]
category: 25-ideas
status: worked-out
version: 1
verdict:
score:
blueprints: 1
reviews: 0
author: claude
cssclasses: [idea-note]
---

%% Mirror of the idea page, `25-ideas/<slug>/idea.md`, as The Council (`idea` skill) and The Architects
(`blueprint` skill) write it in their styled mode. The spec is "Idea page layout" in
`.claude/skills/idea/reference.md` plus "What the blueprint puts on idea.md" in
`.claude/skills/blueprint/reference.md`; the run files next to it, `blueprints/<YYYY-MM-DD-HHMM>-v<n>.md`
and `reviews/<YYYY-MM-DD-HHMM>-council-v<n>.md`, have their layouts in the same files. The page is rebuilt
from the run files on every save; only the ticks and the `**Answer:**` / `**Still open:**` lines under an
open point survive as hand edits.
Status words: new (only a brief), worked-out (a blueprint newer than the latest review), reviewed
(RESHAPE), go (GO or GO WITH CONDITIONS), parked (PARK), dropped (DROP); run files carry done or complete.
Callout types and `lbl-*` classes are styled by `.obsidian/snippets/idea-note.css`. Without that snippet
the skills write the plain mode (quote and info callouts, no spans). The skills are the source of truth;
nothing reads this file. %%
%% customise: ideas folder (default 25-ideas; drop this mirror when the user has neither The Council nor The Architects); plain or styled mode, the same choice as in the two skills %%

# {{title}}

> [!blueprint] Worked-out · v1 · not reviewed yet
> Updated {{date}} · Blueprints 1 · Reviews 0
> [[25-ideas/<slug>/blueprints/<YYYY-MM-DD-HHMM>-v1|Blueprint v1]]

%% When the latest run is a review, the stamp is [!verdict] <Status> · v<n> · <VERDICT score>, with a link to the review too. %%

## Core

> [!core] Core
> **One-liner:** <the blueprint's one-liner, labels stripped>
> **Line:** <The Engineer's Direction, with its tag>
> **Load-bearing assumption:** <The Inspector's Load-bearing>
>
> **First test:** <the first test under Validation plan>
> **Monday:** <The Engineer's Monday>
> **Hours:** <The Engineer's Hours>

%% When The Council judged this same version, the second group reads: **Next step:** <...> *(The Council)*,
**Conditions:** <...> *(The Council)*, **Hours:** <...> *(The Skeptic)* · <...> *(The Architects)*.
Without a blueprint: **The idea:**, **Verdict:**, **Biggest risk:**, **Next step:**, **Kill criteria:**. %%

## Open points

- [ ] <an [open] point of the latest blueprint, the label stripped>
- [x] <a point the user answered>
    - **Answer:** <their answer>
- [ ] <a point they spoke to without settling it>
    - **Still open:** <what they said>

## Reviews

_Not reviewed yet. Say "put it to the council"._

%% With reviews, newest first:
| Date | Version | Verdict | Score | Biggest risk | Full |
|---|---|---|---|---|---|
| <YYYY-MM-DD HH:MM> | v<n> | **<VERDICT>** | <score> | <at most 160 characters> | [[25-ideas/<slug>/reviews/<file stem>\|review]] | %%

## Blueprint

<!-- BLUEPRINT -->
> [!blueprint]- Full blueprint v1
> > [!one-liner]+ One-liner
> > <one sentence> <span class="lbl lbl-yours">yours</span>
>
> > [!problem]- Problem and job
> > <...> <span class="lbl lbl-assumed">assumed</span>
>
> > [!first-user]- First user and buyer
>
> > [!why-now]- Why now
> > <...> <span class="lbl lbl-fact">fact 1</span>
>
> > [!landscape]- Landscape
>
> > [!directions]- Directions explored
>
> > [!solution]+ The solution
> > <...> <span class="lbl lbl-proposed">proposed</span>
>
> > [!scope]- Scope
>
> > [!model]- Model
>
> > [!assumptions]+ Assumptions and risks
>
> > [!validation]- Validation plan
>
> > [!first-step]+ First step and resources
>
> > [!open]+ Open questions and tensions
> > - <a decision only the user can make> <span class="lbl lbl-open">open</span>
>
> ## Sources
>
> 1. <title> (<url>)
>
> > [!council-brief]- Council brief
>
> > [!changed]- What changed
<!-- /BLUEPRINT -->

%% Without a blueprint, between the same markers: > [!open] No blueprint yet. The Architects can work it out: "work this idea out". %%

## History

| Date | Version | Event | Full |
|---|---|---|---|
| {{date}} {{time}} | v1 | blueprint by The Architects: first version | [[25-ideas/<slug>/blueprints/<YYYY-MM-DD-HHMM>-v1\|full run]] |
