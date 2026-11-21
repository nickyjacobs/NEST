---
title: Home
category: index
status: active
tags: [index]
cssclasses: [dashboard, max, base-plain]
author: claude
---

%% customise: translate every label and line on this page to the user's language; keep the callout types ([!nav], [!tiles], [!tile|...], [!kpis], [!kpi|...], [!divider], [!board], [!stack], [!panel|...]) and the button ids as they are, they are the contract with snippets/base.css and the Meta Bind button templates %%

%% customise: nav row, the pages the user opens most (button ids from obsidian/plugins/obsidian-meta-bind-plugin/data.json) %%
> [!nav]
> `BUTTON[ga-goal, ga-inbox, ga-research, ga-decisions, ga-log, ga-how, ga-templates]`

# <fill in: dashboard title, for example the assistant's name or "Home">

You supply, the wiki compiles. A tile or `Alt+N` to capture · `Cmd+O` to search · [[how-this-wiki-works|how it works]] · [[index|catalogue]]

%% customise: capture tiles, one per template the user gets; the metadata after the pipe picks the colour (base.css, section 2) %%
> [!tiles] Capture
> > [!tile|capture]
> > `BUTTON[mk-note]`
> > Something you read or heard
>
> > [!tile|question]
> > `BUTTON[mk-question]`
> > The answer comes back as a page
>
> > [!tile|link]
> > `BUTTON[mk-source]`
> > A URL, becomes a reference
>
> > [!tile|research]
> > `BUTTON[mk-research]`
> > Options, findings, a choice
>
> > [!tile|knowledge]
> > `BUTTON[mk-tool]`
> > A technique with a cheat sheet
>
> > [!tile|concept]
> > `BUTTON[mk-concept]`
> > A concept or an insight
>
> > [!tile|project]
> > `BUTTON[mk-project]`
> > A project with its own folder

%% customise: KPI row. Up to three numbers the user wants to see every day. The defaults read the frontmatter of one goal note (00-context/goal.md: goal-done, goal-total, goal-date, next-step) through the KPI views in _bases/dashboard.base. Point them at the user's own goal, or drop this divider and the [!kpis] block when the user named no goal %%
> [!divider] Where things stand

> [!kpis]
> > [!kpi|progress] <fill in: goal name>
> > ![[_bases/dashboard.base#KPI progress]]
>
> > [!kpi|date] <fill in: target date label>
> > ![[_bases/dashboard.base#KPI date]]
>
> > [!kpi|next] Next step
> > ![[_bases/dashboard.base#KPI next]]

> [!divider] Overview

%% customise: the panels. Left column: what moves daily; right column: priorities and projects. Drop a panel whose section the user does not have (Ideas without The Council or The Architects). The Priorities panel embeds one heading of 00-context/current-priorities.md: point it at the user's own priorities page and heading, or drop it %%
> [!board]
> > [!stack]
> > > [!panel|inbox] Inbox
> > > ![[_bases/dashboard.base#Inbox]]
> > > Process: `/wiki-inbox` in Claude Code.
> >
> > > [!panel|question] Open questions
> > > ![[_bases/dashboard.base#Questions]]
> >
> > > [!panel|recent] New since yesterday
> > > ![[_bases/dashboard.base#New]]
> >
> > > [!panel|answers] Answers from the wiki
> > > ![[_bases/dashboard.base#Answers]]
> >
> > > [!panel|research] Research
> > > ![[_bases/dashboard.base#Research]]
> >
> > > [!panel|ideas] Ideas
> > > ![[_bases/dashboard.base#Ideas]]
> >
> > > [!panel|sessions] Latest sessions
> > > ![[_bases/dashboard.base#Sessions]]
>
> > [!stack]
> > > [!panel|context] Priorities
> > > ![[00-context/current-priorities#Top priorities]]
> >
> > > [!panel|projects] Projects
> > > ![[_bases/dashboard.base#Projects]]

%% How to add a button: buttons (BUTTON[id]) are Meta Bind button templates, in Settings -> Meta Bind -> Button templates (stored in .obsidian/plugins/obsidian-meta-bind-plugin/data.json). Add a template with a new id there: type "Templater create note" with a template file and folder for a capture button (id mk-...), or type "Open" with a [[vault/path]] link for a page button (id ga-...). Then put BUTTON[id] in a new [!tile|<kind>] above, or add the id to the nav row. A new tile colour is one line in snippets/base.css, section 2. %%
