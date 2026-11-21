<%*
// customise: inbox folder (default _inbox), answers folder (default 26-research), prompt text
const question = await tp.system.prompt("What do you want to know?", "", true);
await tp.file.move("/_inbox/question-" + tp.user.slug(question));
-%>
---
title: "<% question.replace(/"/g, "'") %>"
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
tags: []
category: _inbox
status: question
kind: question
author: <fill in: user author value>
---

# <% question %>

> [!question] Question for the wiki
> <% question %>

%% Leave this as it is. `/wiki-inbox` (or <assistant-name>) answers it from the wiki and files the answer with its sources in `26-research/`; this note then moves to the archive. %%
