<%*
// customise: knowledge folder (default 20-knowledge), the kinds (labels and values must match wiki.config.json), prompt text
const title = await tp.system.prompt("Which tool, technique or procedure?", "", true);
const kind = await tp.system.suggester(["Tool", "Technique", "Procedure", "Skill"], ["tool", "technique", "procedure", "skill"], true, "Kind");
await tp.file.move("/20-knowledge/" + tp.user.slug(title));
-%>
---
title: "<% title.replace(/\\/g, "\\\\").replace(/"/g, "'") %>"
kind: <% kind %>
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
tags: []
category: 20-knowledge
status: draft
sources: []
author: <fill in: user author value>
---

# <% title %>

> [!cheatsheet] Cheat sheet
> 

## Key commands

> [!example]- Group 1
> A short explanation of what this does.
> ```bash
> command
> ```

## Gotchas

-

## More methods and sources

| Source | Note |
|---|---|
|  |  |

## Related

-

%% Rules (also for the skills that write knowledge notes):
- Status: draft while the note is yours; a skill sets active once the note is finished.
- Cheat sheet: two or three sentences, what it is and when you use it; not collapsible.
- Key commands: one [!example]- per group, collapsed by default; one command per code block,
  the explanation as plain text above it, no inline # comment (it gets copied along).
- Gotchas: your own experience, surprises, common mistakes.
- Links as vault paths: `[[20-knowledge/<note>]]`, `[[10-projects/<project>/README]]`. %%
