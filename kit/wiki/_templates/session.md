<%*
// customise: sessions folder (default 30-sessions), prompt text
const focus = await tp.system.prompt("Focus of the session?", "", true);
await tp.file.move("/30-sessions/" + tp.date.now("YYYY-MM-DD") + "-" + tp.user.slug(focus));
-%>
---
title: "Session <% tp.date.now("YYYY-MM-DD") %>: <% focus.replace(/"/g, "'") %>"
date: <% tp.date.now("YYYY-MM-DD") %>
status: done
focus: <% tp.user.slug(focus) %>
tags: []
category: 30-sessions
author: claude
---

# Session <% tp.date.now("YYYY-MM-DD") %>: <% focus %>

## Goal


## Before

## What was done

## Decisions

## Insights

## Open

## Next steps

%% Normally `/session-end` writes this log. Leave out empty sections. Decisions with their rationale go to
[[50-decisions/log]]; only the summary goes here. %%
