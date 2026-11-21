---
title: "Operations log"
category: log
status: active
tags: []
author: claude
---

%% customise: translate the heading and the introduction; keep the marker line below exactly as it is (it must match "log.marker" in wiki.config.json) %%

# Operations log

Append-only, newest first. One block per operation, so you can follow how the wiki grows and search it with `grep`.

Format: `## YYYY-MM-DD HH:MM · <op> · <title>` with short bullets below (which pages were touched, the source). `<op>` is one of: `ingest` · `distill` · `query` · `lint` · `migrate`. Written by `uv run scripts/wiki.py log`, never by hand.

<!-- Begin of the log -->
