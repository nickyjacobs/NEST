<%*
// customise: inbox folder (default _inbox) and the prompt text in the user's language
const title = await tp.system.prompt("What is the note about?", "", true);
await tp.file.move("/_inbox/" + tp.user.slug(title));
-%>
---
title: "<% title.replace(/\\/g, "\\\\").replace(/"/g, "'") %>"
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
tags: []
category: _inbox
status: draft
kind: capture
author: <fill in: user author value>
---

# <% title %>

