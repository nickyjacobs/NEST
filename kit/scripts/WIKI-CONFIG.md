# wiki.config.json

`scripts/wiki.py` keeps an Obsidian vault in shape: it lints links and frontmatter, fixes what
needs no judgement, rebuilds section indexes and writes the operations log. Everything specific to
one vault lives in `wiki.config.json`. Start from `wiki.config.example.json`.

## Running it

```sh
uv run scripts/wiki.py lint                  # active content; exit 1 on errors
uv run scripts/wiki.py lint --all -v         # the whole vault, every finding listed
uv run scripts/wiki.py lint --fix            # fix, reindex, then lint
uv run scripts/wiki.py reindex [section]     # rebuild indexes below the marker
uv run scripts/wiki.py stats                 # pages, authors, short links and tags per section
uv run scripts/wiki.py log <op> "<title>" ["<line>" ...]
```

`--config <path>` works before or after the command. Without it the script reads the path in
`NEST_WIKI_CONFIG`, and otherwise walks up from the current directory to the first
`wiki.config.json`. Exit codes: 0 clean (warnings allowed), 1 lint errors, 2 usage or config error
(a value of the wrong kind is named in one line, never shown as a Python traceback).

The file is plain JSON: no comments. Keys that start with `_` are ignored, so `"_note": "..."` is a
place for a remark. Every key is optional; a missing key takes the default below.

## What lint checks

Errors (exit code 1):

| Count | Meaning |
|---|---|
| `broken-links` | `[[target]]` that matches no file |
| `ambiguous-links` | a bare `[[name]]` that more than one file carries |
| `broken-embeds` | `![[file]]` that matches no file |
| `no-frontmatter` | a page in a section with `frontmatter: true` that does not start with `---` |
| `missing-fields` | one of `required_fields` is absent from the frontmatter |
| `invalid-yaml` | the frontmatter does not parse (Obsidian then shows no properties) |
| `unknown-status` | `status` is not one of the status words |

Warnings (listed with `-v`, exit code 0):

| Count | Meaning |
|---|---|
| `short-links` | a bare `[[name]]` in a content section, where the convention is the vault path |
| `no-author` | `author` missing or not one of `authors` |
| `stale-active` | `status: active` and `updated` older than `stale_days`, in a section with `stale: true` |
| `unsourced` | a page by one of `unsourced_authors` without any `source_fields`, in a section with `sourced: true` |
| `repeated-links` | the same page linked more than once in the running text of a content page |
| `duplicate-titles` | the same title in more than one section |
| `unknown-kind` | a `kind` that is not a key of the section's `kinds` |

Links inside code (fenced with backticks or tildes, or inline) and inside comments (`%% ... %%`,
`<!-- ... -->`) are ignored. A link with a folder in it must be that path, from the vault root or
relative to the linking page: it never falls back to the file name alone, so a link to a folder
that was renamed or moved is broken, as it is in Obsidian. A bare name resolves when exactly one
file carries it. Upper and lower case are the same, and so are the two ways a file system can store
an accented letter. Pages in the vault root (`index.md`, `log.md`, `Home.md`) may be linked by
name. Hidden folders (`.obsidian`, `.git`, `.trash`) are never scanned.

`author` may be one name or a list (Obsidian writes a list once the property type is List); every
name in it must be one of `authors`.

`lint` without `--all` skips sections with `lint_active: false` and every folder named in
`raw_folders` below the section level. `--all` includes them. Sections with `lint: false` are never
linted.

`--fix` changes two things and leaves everything else to a person: a bare `[[name]]` in a content
section becomes `[[section/path|name]]` when exactly one page carries the name (an alias or anchor
is kept), and `category` becomes the section folder name. Inside a table the link is written
`[[section/path\|name]]`, since a bare pipe would split the cell. It never touches raw material (a
`raw: true` section, a `raw_subdirs` folder, a `raw_folders` folder), code spans, comments or
embeds. Line endings (LF or CRLF) and a BOM are kept as they were. Then it reindexes.

## Top-level keys

| Key | Default | Meaning |
|---|---|---|
| `wiki_dir` | `"wiki"` | The vault folder, relative to the config file (or absolute; `~` works). |
| `index_marker` | `"<!-- AUTO-INDEX -->"` | Reindex rewrites everything below this line of a section's `index.md`. The marker counts only on a line of its own; when the page has several such lines, the last one. |
| `index_empty` | `"_Nothing here yet._"` | What an index says when its section has no pages. |
| `log.file` | `"log.md"` | The operations log, relative to the vault. |
| `log.marker` | `"<!-- Begin of the log -->"` | New blocks go right below this line (the marker on a line of its own), newest first. |
| `log.title` | `"Operations log"` | Title and heading of a log file the script creates. |
| `log.ops` | `["ingest", "distill", "query", "lint", "migrate"]` | The operations `log` accepts. |
| `status_words` | `["draft", "active", "done", "parked", "archived", "question"]` | Allowed `status` values. A section can override them. |
| `required_fields` | `["title", "tags", "category", "status"]` | Frontmatter fields every checked page needs. |
| `authors` | `["user", "assistant", "claude"]` | Allowed `author` values. An empty list switches the author check off. |
| `author_required_from` | `null` | ISO date. Only pages created on or after it need an `author` (for a vault with older pages). `null`: every page needs one. |
| `created_fields` | `["created", "date", "ingest-date"]` | Where the creation date is read for `author_required_from`, first match wins. |
| `unsourced_authors` | `[]` | Authors whose pages in `sourced` sections must name a source. |
| `source_fields` | `["sources", "source-url"]` | Frontmatter fields that count as naming a source. |
| `stale_days` | `90` | Age in days after which an active page in a `stale` section warns. |
| `raw_folders` | `["_inbox"]` | Folder names that hold raw material when they sit inside a section (for example a project's own `_inbox`). |
| `nav_headings` | `["related", "sources", "see also", "links", "references", "further reading"]` | Heading words (case-insensitive) that start a navigation list; links under them do not count as repeats. |
| `repeat_link_exempt` | `["index.md", "*/index.md", "log.md", "*/log.md"]` | Vault-path glob patterns where repeated links are fine (`*` also matches `/`). |
| `sections` | `{}` | One entry per top-level folder, see below. A folder without an entry is linted for links only. |
| `content_sections` | `[]` | Sections where bare links warn and `--fix` rewrites them, and where repeated links warn. Each must be in `sections`. |

## Section keys

| Key | Default | Meaning |
|---|---|---|
| `index` | `"flat"` | The index type, see below. |
| `lint` | `true` | `false`: never linted (templates, bases). Its files still count as link targets. |
| `lint_active` | `true` | `false`: skipped by `lint`, included by `lint --all` (sessions, archive, inbox). |
| `frontmatter` | `true` | Check frontmatter, status, author and the other page rules here. `false`: links only. |
| `raw` | `false` | Raw material: `--fix` leaves it alone, it is left out of the duplicate-title check, and `stats` counts its open questions (`status: question`). |
| `archive` | `false` | Left out of `stats`, the index size and the duplicate-title check. |
| `dated` | `false` | Page names start with a date: the flat index lists newest first. |
| `stale` | `false` | Warn about active pages not updated for `stale_days`. |
| `sourced` | `false` | Pages by `unsourced_authors` must name a source. |
| `status_words` | `null` | A list replaces the top-level `status_words` for this section (a section whose pages carry their own workflow words). The section's own `index.md` is a catalogue page and keeps the top-level words. |
| `kinds` | `{}` | `kind` value to group label, in display order. Used by `by_kind`, and lint warns on any other `kind`. |
| `other_label` | `"Other"` | `by_kind`: the group for pages without a known `kind`. |
| `readme` | `"README.md"` | `projects`: the page that represents a project folder. |
| `page` | `"README.md"` | `folders`: the main page of each subfolder (for example `"idea.md"`). |
| `fields` | `["status"]` | `projects` and `folders`: frontmatter fields shown after the link, joined with ` · `. |
| `idea_page` | `{}` | The ideas section only, read by `idea_page.py` (wiki.py ignores it): `style` (`"styled"` or `"plain"`), `blueprints` and `reviews` (folder names), `labels` (idea.md headings, status words and texts; the keys are in the script's help). |
| `heading` | `""` | `projects`: the heading (default `Projects`); `references`: the first heading. |
| `labels` | `{}` | `references`: override `collections`, `pages`, `raw`, `ingest_log`. |
| `raw_subdirs` | `[]` | Subfolders with raw copies (`references` lists them apart; `--fix` leaves them alone). |
| `ingest_log` | `"log.md"` | `references`: the section's ingest log, linked at the end when it exists, and not listed as a page. |

## Index types

Every index line has the form `- [[section/path|Title]]: summary`. The summary is the frontmatter
`summary`, else the first plain paragraph or opening callout of the page, cut at 120 characters.
Reindex only writes a section that has an `index.md`, and only below the `index_marker` line: the
text above it stays, also when that text mentions the marker inside a sentence. An `index.md`
without a marker line gets one appended, unless it already holds links: then it counts as
hand-written and is left alone.

| Type | Writes |
|---|---|
| `manual` | Nothing. The index is written by hand. |
| `none` | Nothing. The section has no index. |
| `flat` | One line per page in the section folder, by file name (newest first with `dated`). |
| `by_kind` | A `## Label` group per `kinds` entry in config order, then `other_label`; alphabetical by title within a group. |
| `projects` | `## Projects`, then one line per subfolder that has `readme`: `- [[section/folder/README\|Title]]: *status*`. |
| `references` | Collections (subfolders that hold pages, linked to their `index.md` or `00-index.md`, with a page count; a folder without any page, such as `attachments`, is left out), loose pages, a `## Raw sources` list per `raw_subdirs` folder, and the ingest log. |
| `folders` | One line per subfolder that has `page`, most recently `updated` first, with its `fields`; then loose pages, newest file name first. |

## The log

`log` inserts a block right below `log.marker`, so the newest block is on top:

```markdown
## 2026-01-02 10:30 · lint · Weekly lint
- 0 errors, 3 short links fixed
```

A vault without the log file gets one with frontmatter (the status is the word in
`status_roles.active`), a heading and the marker. A log without a marker line gets one above its
first block, or at the end when it has no blocks yet: the heading and the introduction stay on top.

## Status words in another language

`status_words` may be in any language. Two keys tell the scripts which word plays which role:

| Key | Default | Used for |
|---|---|---|
| `status_roles.active` | `active` | the "not updated for `stale_days`" warning, the active page count |
| `status_roles.draft` | `draft` | the active page count |
| `status_roles.question` | `question` | the open question count (`stats`, the session-start line) |
| `question_kind` | `question` | an inbox note whose `kind` is this word also counts as a question |

Every word in `status_roles` must also be in `status_words`; otherwise the config is refused.
Example for Dutch: `"status_words": ["concept", "actief", "klaar", "geparkeerd", "gearchiveerd", "vraag"]`,
`"status_roles": {"active": "actief", "draft": "concept", "question": "vraag"}`, `"question_kind": "vraag"`.
