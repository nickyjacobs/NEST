<%*
// customise: inbox folder (default _inbox), references folder (default 40-references), prompt text
const url = await tp.system.prompt("URL of the source?", "", true);
const title = await tp.system.prompt("Title (empty: taken from the page later)", "", false) || url.replace(/^https?:\/\//, "").split("/")[0];
await tp.file.move("/_inbox/source-" + tp.user.slug(title));
-%>
---
title: "<% title.replace(/"/g, "'") %>"
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
tags: []
category: _inbox
status: draft
kind: link
source-url: <% url %>
author: <fill in: user author value>
---

# <% title %>

<% url %>

%% Why are you keeping this? One line is enough. `/wiki-inbox` turns it into a reference in `40-references/` through `/wiki-ingest`, or into a knowledge note when it is small. %%
