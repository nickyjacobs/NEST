---
name: wiki-maint
description: Maintenance round for the wiki. Rebuilds the catalogues, runs the lint and the stats, fixes what is safe with --fix, reports expired references, a full inbox, stale context pages and an unbacked-up vault, and writes a line in the operations log. Only on /wiki-maint, or after a big writing round.
argument-hint: "[--fix]"
disable-model-invocation: true
metadata:
  does: "Maintenance round: reindex, lint, stats and signals (inbox, references, context, backup); safe fixes with --fix."
  try:
    - "/wiki-maint"
    - "/wiki-maint --fix"
---

# /wiki-maint

The lint operation of the wiki. The deterministic work is done by `scripts/wiki.py`; this skill
reads the outcome, fixes what is safe and reports the rest. Without `--fix`: report only. With
`--fix`: also the safe repairs below.

**Not for:** writing or moving content (`/wiki-inbox`, `/wiki-ingest`), or linting the whole vault
including templates, raw and archive (`uv run scripts/wiki.py lint --all`, only on request).

<!-- customise: output language for anything written into the wiki (the user's language) -->
Anything you write into the wiki (a fixed field, the log line) is in the user's language; follow
`.claude/rules/writing.md`.

<!-- customise: section paths from wiki.config.json -->
Paths used below: inbox `wiki/_inbox/`, references `wiki/40-references/`, context
`wiki/00-context/`, archive `wiki/90-archives/`, operations log `wiki/log.md`.

## 1. Catalogues, lint and stats

```bash
uv run scripts/wiki.py reindex && uv run scripts/wiki.py lint && uv run scripts/wiki.py stats
```

The lint checks the active content (no templates, raw or archive) and should report zero
everywhere, warnings included. The stats show per section the pages, pages without `author`,
short links and tags that occur once. Per finding:

<!-- customise: status words and their synonyms from wiki.config.json -->
| Finding | Safe fix (`--fix`) | Otherwise |
|---|---|---|
| Broken link or embed | Target found under another name or folder: link to its vault path | Report with source and target |
| Ambiguous or short link | `uv run scripts/wiki.py lint --fix` (resolves unique ones, sets `category` to the folder) | Report, the user chooses |
| Invalid YAML | Quote the value that holds a colon | Report |
| Unknown status | Clear synonyms (`complete`, `finished` to `done`; `in-progress`, `wip` to `active`) | Report |
| No frontmatter or missing fields | Add the core fields (`title` from the H1, `category` = folder, `status: active`, `tags: []`) | `author` only when it is certain from the context |
| Page without author from before the workspace existed | Nothing: not an error, no mass edit | Report as a count |
| Tag on one page | Nothing | Report; the user chooses (a judgement, not a fix) |

## 2. Signals (report only)

- **Inbox:** the number of notes in `_inbox/` (without `index.md`), the oldest, and how many have
  `status: question`. More than 10, older than 14 days, or an open question: propose `/wiki-inbox`.
- **Expired references:** pages in `40-references/` with a `review-date` before today. Propose
  `/wiki-ingest <source-url>` (re-ingest), or `status: parked` when the source no longer matters.
- **Context:** `00-context/*.md` with `updated` older than 30 days; the priorities page older than
  14 days.
<!-- customise: backup check (wiki backup repo from the interview, or remove this bullet) -->
- **Backup:** `uv run scripts/wiki_backup.py status` (uncommitted files, commits not pushed).
  Changes waiting: ask whether `uv run scripts/wiki_backup.py push` may run. Push only after a yes.
- **Skills catalogue:** `uv run scripts/skills_catalog.py --check`; stale: regenerate it and say so.

## 3. Close

- Only when something was repaired or found:
  `uv run scripts/wiki.py log lint "Maintenance round" "<counts and repairs>"`.
- Report short:

```
Wiki: lint 0 · reindex ok · stats: 40 without author (old), 0 short links, 9 single tags
Inbox 4 (oldest 9 days, 1 question) -> /wiki-inbox
References expired: some-docs (since 2026-01-10)
Backup: 37 changes since 2026-01-06 -> push?
```

## Rules

- Never delete anything; outdated material moves to `90-archives/`, and only after a yes.
- Raw (`_inbox/`, `40-references/sources/`) is never rewritten; the lint only checks the
  frontmatter of `sources/`.
- Conventions: `.claude/rules/wiki.md`; the how-to page in the wiki root.
