<%*
// customise: knowledge folder (default 20-knowledge), prompt text
const title = await tp.system.prompt("Which topic?", "", true);
await tp.file.move("/20-knowledge/" + tp.user.slug(title));
-%>
---
title: "<% title.replace(/\\/g, "\\\\").replace(/"/g, "'") %>"
kind: concept
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
tags: []
category: 20-knowledge
status: draft
sources: []
author: <fill in: user author value>
---

# <% title %>

> [!abstract] In short
> 

## Why it matters

## Detail

## Sources

| Source | Note |
|---|---|
|  |  |

## Related

-
