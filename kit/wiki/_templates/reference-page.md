<%*
// customise: references folder (default 40-references) and its raw-copy subfolder (default sources, named in the Source block below), review interval (default P3M), prompt text
const title = await tp.system.prompt("Title of the source?", "", true);
const url = await tp.system.prompt("URL (leave empty when there is none)", "", false) || "n/a";
await tp.file.move("/40-references/" + tp.user.slug(title));
-%>
---
title: "<% title.replace(/\\/g, "\\\\").replace(/"/g, "'") %>"
source-url: "<% url.replace(/\\/g, "\\\\").replace(/"/g, "'") %>"
ingest-date: <% tp.date.now("YYYY-MM-DD") %>
review-date: <% tp.date.now("YYYY-MM-DD", "P3M") %>
tags: []
category: 40-references
status: active
supersedes: []
superseded-by:
author: <fill in: user author value>
---

# <% title %>

> [!info] Source
> <% url %> · ingested <% tp.date.now("YYYY-MM-DD") %> · review <% tp.date.now("YYYY-MM-DD", "P3M") %>
> Raw copy: none yet. `/wiki-ingest` keeps one in `40-references/sources/` and links it here.

## Overview


## Key concepts

-

## Most important pages

-

## When do I use this

## Notes
