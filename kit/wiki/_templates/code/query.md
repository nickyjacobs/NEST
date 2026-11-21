---
title: "{{question}}"
created: {{date}}
updated: {{date}}
category: 26-research
status: done
author: claude
tags: [research, query]
sources: ["20-knowledge/<page>", "10-projects/<project>/README"]
---

%% Mirror of what the `wiki-query` skill (step 3, "Save") and `/wiki-inbox` (question notes) write when
an answer from the wiki is filed back. File name `26-research/YYYY-MM-DD-HHMM-<slug>.md`; the time keeps
two answers on one day apart. The tags `research, query` set filed answers apart from the user's own
research in the same folder (the dashboard views Answers and Research rely on that). The skill is the
source of truth: change the skill, then change this mirror. Nothing reads this file. %%
%% customise: answers folder (default 26-research), language of the headings %%

# {{question}}

> [!abstract] Answer from the wiki
> Answered from the wiki on {{date}} {{time}}; the pages consulted are listed at the bottom.

## Answer

<the answer as given, cleaned up, as Markdown>

## Sources

- [[20-knowledge/<page>|<title of the page>]]
- Question: [[90-archives/inbox/<question note>]] (only when the answer came from a question note)
