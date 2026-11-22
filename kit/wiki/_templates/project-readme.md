<%*
// customise: projects folder (default 10-projects), phase words, prompt text
const name = await tp.system.prompt("Name of the project?", "", true);
const dir = "10-projects/" + tp.user.slug(name);
if (!app.vault.getAbstractFileByPath(dir)) await app.vault.createFolder(dir);
await tp.file.move("/" + dir + "/README");
-%>
---
title: "<% name.replace(/\\/g, "\\\\").replace(/"/g, "'") %>"
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
tags: [<% tp.user.slug(name) %>]
category: 10-projects
status: active
phase: planning
deadline:
author: <fill in: user author value>
---

# <% name %>

> [!abstract] Goal
> 

## Why

## Scope

**In:**
-

**Out:**
-

## Milestones

- [ ] 

## Recent progress

-

## Next step

## Connected

- Decisions: [[50-decisions/log]]

%% phase: planning | active | paused | finished. deadline: an ISO date or empty. %%
