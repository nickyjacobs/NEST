---
title: "{{title}}"
kind: tool
created: {{date}}
updated: {{date}}
tags: [<topic>]
category: 20-knowledge
status: draft
sources: []
author: claude
---

%% Mirror of what the skills write into the knowledge section (`/wiki-inbox` from a capture, and any
skill that files a knowledge note after the user's yes). A new note follows `knowledge-tool` or
`knowledge-note` without the Templater block. An existing note is never rewritten: the skill adds a
dated section "## Addition YYYY-MM-DD (Claude)" at the bottom and sets `updated`. The user's own text
above it stays verbatim. The skills are the source of truth; nothing reads this file. %%
%% customise: knowledge folder (default 20-knowledge), kinds, language of the headings %%

# {{title}}

> [!cheatsheet] Cheat sheet
> <two or three sentences: what it is, when you use it>

## Key commands

> [!example]- <group>
> <explanation>
> ```bash
> <command>
> ```

## Gotchas

- <surprises, common mistakes>

## Sources

- [[20-knowledge/<page>|<page the note drew on>]]

## Addition {{date}} (Claude)

<only on an existing note: the addition, at the bottom; the text above it stays as it was>
