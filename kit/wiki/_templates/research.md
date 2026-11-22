<%*
// customise: research folder (default 26-research), table columns, prompt text
const question = await tp.system.prompt("What are you looking into? (becomes the title)", "", true);
await tp.file.move("/26-research/" + tp.date.now("YYYY-MM-DD") + "-" + tp.user.slug(question));
-%>
---
title: "<% question.replace(/\\/g, "\\\\").replace(/"/g, "'") %>"
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
tags: []
category: 26-research
status: active
sources: []
author: <fill in: user author value>
---

# <% question %>

> [!question] What I want to know
> 

## Options

| Option | Pros | Cons | Cost | Link |
|---|---|---|---|---|
|  |  |  |  |  |

## Findings

-

## Conclusion

> [!success] Choice
> Still open.

## Sources

-
