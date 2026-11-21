<%*
// customise: audits folder (default 60-audits; drop this template when the user has no audits section), prompt text
const subject = await tp.system.prompt("What is being audited?", "", true);
await tp.file.move("/60-audits/audit-" + tp.date.now("YYYY-MM-DD") + "-" + tp.user.slug(subject));
-%>
---
title: "Audit <% tp.date.now("YYYY-MM-DD") %>: <% subject.replace(/"/g, "'") %>"
date: <% tp.date.now("YYYY-MM-DD") %>
scope: <% tp.user.slug(subject) %>
previous:
tags: []
category: 60-audits
status: active
author: claude
---

# Audit <% tp.date.now("YYYY-MM-DD") %>: <% subject %>

> [!abstract] Summary
> 

## Findings

| # | Severity | Finding | Where | Action |
|---|---|---|---|---|
| 1 |  |  |  |  |

## Roadmap

- [ ] 

## Follow-up

%% status: active while findings are open, done once everything is handled. %%
