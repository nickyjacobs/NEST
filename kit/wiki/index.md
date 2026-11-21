---
title: "Wiki: index"
updated: <fill in: setup date, YYYY-MM-DD>
tags: [index]
category: index
status: active
author: claude
---

%% customise: one row per section in the user's folder design (folder names, descriptions and writers in the user's language); drop rows for sections the user does not have; replace <assistant-name> or drop it %%

# <fill in: wiki name>

The catalogue of the wiki. Start here, open at most three pages per question, then search within one section folder.
How the wiki works (three layers, capture, operations, rules): [[how-this-wiki-works]]. The dashboard: [[Home]]. What happened when: [[log]].

## Sections

| Folder | What is in it | Who writes (`author`) |
|---|---|---|
| [[00-context/index\|00-context]] | Who you are: profile, work, priorities, goals. Only the current state | claude (`/session-end`), you |
| [[10-projects/index\|10-projects]] | One folder per project with a `README.md` | claude (`/session-end`, `/wiki-inbox`), you |
| [[20-knowledge/index\|20-knowledge]] | Knowledge notes, flat, sorted by `kind:` (tool, technique, procedure, skill, concept) | claude (`/wiki-inbox`), <assistant-name> (after a yes), you |
| [[25-ideas/index\|25-ideas]] | One folder per idea: `idea.md`, `blueprints/`, `reviews/` | The Council and The Architects |
| [[26-research/index\|26-research]] | Research: a question looked into with options and sources; also answers from the wiki (`query`) | claude (`/wiki-query`, `/wiki-inbox`), <assistant-name>, you |
| [[40-references/index\|40-references]] | Outside documentation, curated, with a review date; raw copies in `sources/` | claude (`/wiki-ingest`) |
| [[50-decisions/index\|50-decisions]] | The decision log | claude (`/session-end`, `/wiki-inbox`), you |
| [[_inbox/index\|_inbox]] | Captures, questions and links, not yet processed (`kind: capture, question, link`) | you (tiles), <assistant-name>; `/wiki-inbox` processes |
| [[30-sessions/index\|30-sessions]] | Work logs of Claude Code sessions | claude (`/session-end`) |
| [[60-audits/index\|60-audits]] | Audits of the workspace and the wiki | claude, on request |
| [[90-archives/index\|90-archives]] | Finished or outdated, kept instead of deleted | everyone, by moving |

## Frontmatter per folder

Minimum everywhere: `title`, `tags`, `category` (the folder name), `status`, `author`. On top of that:

- `10-projects`, `20-knowledge`, `25-ideas`, `26-research`, `_inbox`: `created` and `updated`
- `20-knowledge` and `_inbox`: `kind`; `10-projects/*/README`: `phase` (planning, active, paused, finished) and `deadline`
- `40-references`: `source-url`, `ingest-date`, `review-date`
- `30-sessions`, `60-audits`: `date`
- index pages: no dates
- optional everywhere: `summary`, one sentence that becomes the page's line in its section index
