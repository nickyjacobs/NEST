---
title: "Templates: overview"
category: _templates
status: active
tags: [index]
---

# Templates

%% customise: translate this page, the template names in the tables and the folder names to the user's folder design and language; drop the rows of templates the user does not get %%

A new note: a tile under **Capture** on [[Home]], or **`Alt+N`** (Templater: *Create new note from template*) and pick a template. The template then asks for a title, moves the note to the right folder with a kebab-case file name and fills in the dates.
Every template you use sets `author: <fill in: user author value>` (`session` and `audit` set `author: claude`): who wrote a page is in its frontmatter.
Optional field `summary`: one sentence that becomes the page's line in the section index; without it, `reindex` takes the first paragraph after the H1.

## For you (Templater)

| Template | Makes | Lands in |
|---|---|---|
| `note` | A quick capture (`kind: capture`): a thought, something you read or heard | `_inbox/<title>` |
| `question` | A question for the wiki (`kind: question`, `status: question`); `/wiki-inbox` or <assistant-name> answers it with file-back | `_inbox/question-<title>` |
| `source` | A URL to ingest later (`kind: link`, `source-url`) | `_inbox/source-<title>` |
| `research` | Looking something up: options, findings and a choice | `26-research/YYYY-MM-DD-<title>` |
| `knowledge-note` | Knowledge about a concept (`kind: concept`) | `20-knowledge/<title>` |
| `knowledge-tool` | A tool, technique, procedure or skill, with a cheat sheet | `20-knowledge/<title>` |
| `project-readme` | A new project with its own folder | `10-projects/<name>/README` |
| `reference-page` | An outside source with a review date three months on (no raw copy; `/wiki-ingest` makes a reference with one) | `40-references/<title>` |
| `audit` | An audit with findings and a roadmap | `60-audits/audit-YYYY-MM-DD-<subject>` |
| `session` | A session log (normally written by `/session-end`) | `30-sessions/YYYY-MM-DD-<focus>` |

## For the skills

- Skills skip the Templater block `<%* … -%>` and fill in the frontmatter themselves, with `author: claude`.
- `query`, `knowledge-tool`, `knowledge-note`, `research`, `project-readme`: `/wiki-inbox`. `project-readme`, `knowledge-note`: `/study-inbox`. `reference-page`: `/wiki-ingest`. `query`: `/wiki-query`. `session`: `/session-end`.

## Mirrors, not for new notes

- `code/`: `query` (an answer from the wiki, filed back), `knowledge` (a knowledge note or a dated addition), `reference` (an ingest with its raw copy) and `idea` (the dashboard page of one idea of The Council and The Architects). They show what the skills write; nothing reads them. Change a skill, then change its mirror.
- `_scripts/slug.js`: the Templater user script (`tp.user.slug`) for file names: lower case with hyphens, in any script.
