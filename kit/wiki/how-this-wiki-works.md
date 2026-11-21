---
title: "How this wiki works"
category: index
status: active
tags: [index]
author: claude
---

%% customise: translate to the user's language and write it in their voice; replace <assistant-name> with the assistant's name, or drop those lines when the user has only Claude Code; folder names to the user's folder design %%

# How this wiki works

**You supply, the LLM compiles.** The wiki follows Andrej Karpathy's LLM wiki pattern: you pick sources, ask questions and read; Claude Code and <assistant-name> write, link, index and maintain. Knowledge is processed once and then kept up to date, instead of being pulled from raw documents again for every question. You may always type in a note yourself: the LLM never rewrites your words, it structures around them.

## Three layers

| Layer | Where | Who touches it |
|---|---|---|
| **Raw** | `_inbox/` (captures, questions, links), `40-references/sources/` (raw copies of sources) | You and <assistant-name> drop things here. The LLM reads, copies and moves them after processing (to the archive), but never edits the content |
| **Wiki** | The numbered sections, see [[index]] | Claude Code (skills) and <assistant-name> write and maintain; you read and may add |
| **Schema** | [[index]] (catalogue), this page, `_templates/`, `wiki.config.json`, the wiki rules in `.claude/rules/` | Claude Code, together with you |

%% customise: add a raw folder per extra inbox the user has (course material, a scanner folder) %%

## Capture

- **On [[Home]]** a tile, or `Alt+N` and a template: *Note* (something you read or heard), *Question* (for the wiki), *Source* (a URL), *Research* (looking something up), *Knowledge* (a tool or a concept), *Project*.
- **In Claude Code:** `/wiki-inbox` processes the inbox, `/wiki-ingest <url>` brings in a source, `/wiki-query <question>` answers from the wiki.
- **To <assistant-name>:** "note that ..." (to `_inbox`), "read this and put it in the wiki" (a reference), "save that answer" (an answer from the wiki as a page).

## Five operations

| Operation | What | Who |
|---|---|---|
| `ingest` | Bring in a source: a raw copy in `sources/` plus a curated page that names it | `/wiki-ingest` |
| `distill` | Turn the inbox and raw material into notes in the right place, with links and an index line | `/wiki-inbox`, `/session-end` |
| `query` | Answer a question from the wiki; a good answer goes back with its sources as a page in `26-research` | `/wiki-query`, `/wiki-inbox` (question notes) |
| `lint` | Links, frontmatter, status words, tags, short links; deterministic, no model | `wiki.py lint`, `/wiki-maint` |
| `migrate` | Big rounds: structure, conventions, clean-up | Claude Code, after talking it through |

Every operation gets a line in [[log|the operations log]] (`## YYYY-MM-DD HH:MM · <op> · title`).

## Reading

Start at [[index]], open at most three pages, then search within one section folder. That goes for <assistant-name> and for Claude Code. Your dashboard is [[Home]].

## Rules in one breath

- **Frontmatter** at least `title`, `tags`, `category` (the folder name), `status`, `author` (<fill in: author values, for example the user's name, the assistant's name and claude>). A value with a colon goes between quotes.
- **Status:** `draft` (yours, or not finished), `active`, `done`, `parked`, `archived`; `question` for an open question in `_inbox`. The LLM sets `active` once a note is finished.
- **Links** as vault paths (`[[20-knowledge/some-tool|Some tool]]`); link the first mention on a page, not every one. Never inside code blocks.
- **Sources** on every page: `sources` in the frontmatter or a sources table; a reference links to its raw copy.
- **Tags** flat, kebab-case, sparing: a tag earns its place on three or more pages.
- **Never delete:** move to `90-archives/`.
- **Templates** put a note in the right place themselves; skills skip the Templater block `<%* … -%>` and fill in the frontmatter.
- **Afterwards:** `uv run scripts/wiki.py reindex && uv run scripts/wiki.py lint` must report zero.
