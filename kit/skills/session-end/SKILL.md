---
name: session-end
description: Closes a work session. Writes a session log in the wiki's sessions section, records real decisions in the decisions log, updates the touched project README ("Recent progress", "Next step") and the priorities page, parks new lasting knowledge as an inbox note, updates docs/next-session.md and adds a line to the operations log. Only on /session-end.
argument-hint: "[focus]"
disable-model-invocation: true
metadata:
  does: "Closes a work session: session log, decisions, project README, priorities and docs/next-session.md."
  try:
    - "/session-end"
    - "/session-end <focus>"
---

# /session-end

No hook or pipeline does this: this skill is the only way a session gets into the wiki.

**Not for:** trivial sessions (one question, a small fix): say so and stop. Not for pushing:
that is `/release`, on the user's request.

<!-- customise: output language for wiki pages (the user's language); repo docs language (default English) -->
Write every wiki page in the user's language and voice; follow `.claude/rules/writing.md`. Files
under `docs/` stay in the repo's language.

<!-- customise: section paths from wiki.config.json -->
Paths used below: sessions `wiki/30-sessions/`, decisions `wiki/50-decisions/log.md`, projects
`wiki/10-projects/`, priorities `wiki/00-context/current-priorities.md`, inbox `wiki/_inbox/`,
template `wiki/_templates/session.md`.

## 1. Confirm the focus

Derive the focus from the session's first question, the plan (if there was one) and the largest
cluster of changes. An argument given: that is the focus. Otherwise ask "The focus was <X>,
right?" and show in three to five lines what you are going to write.

## 2. Session log

Path: `30-sessions/YYYY-MM-DD-<focus-slug>.md`. The path exists with another focus: ask whether
this becomes `-2` or a merge. Follow the `session` template: skip its Templater block and fill the
frontmatter yourself. Write only what really happened; leave an empty section out instead of
writing "n/a".

- Frontmatter, exactly the template's fields: `title` ("Session YYYY-MM-DD: <focus>"), `date`,
  `status: done`, `focus` (the slug), `tags`, `category`, `author: claude`.
<!-- customise: session section headings in the user's language -->
- Sections: Goal, Before, What was done (per logical block), Decisions (summary), Insights, Open,
  Next steps.
- Links as vault paths (`[[10-projects/<project>/README]]`).

## 3. Decisions

Every real decision (a choice between alternatives, not "built X") gets an entry in
`50-decisions/log.md`. The log has a format block at its head with the allowed area values
(a log without one: add the block from the kit's `decisions-log.md` first, with the areas the
user's sections suggest, after a yes); follow it to the letter: a heading `## YYYY-MM-DD: <short title>`, then Area, Decision,
Rationale, Impact, Reference. Newest first, right under the format block. A decision that
replaces an older one says so, and the old entry gets a `**Status:** superseded by ...` line;
the old text itself is never rewritten.

## 4. Update the touched pages

Only what this session really touched, no broad sweep:

- **Project README** (`10-projects/<project>/README.md`): the headings "Recent progress" (one
  line with the date) and "Next step". A README without those headings: add them at the bottom.
  Update `updated`.
- **Priorities changed:** the priorities page, only the current state. No history and no
  progress numbers that live on another page.
- **New lasting knowledge:** an inbox note `_inbox/<slug>.md` (`kind: capture`,
  `author: claude`, `status: draft`, `created`, `updated`, `category`) with one line on why it
  matters; `/wiki-inbox` files it later after the user's go. Never straight into the knowledge
  section without a yes.
- **Workspace code or config changed:** update `docs/next-session.md` (mark done what is done,
  add new open work at the top).
<!-- customise: lessons (keep when the lesson hook was chosen in the setup; otherwise delete this bullet) -->
- **Something went wrong that can happen again at one kind of step** (a command that broke
  something, a file that must not be edited by hand): propose one line for `.claude/lessons.json`
  and add it after a yes, as `{"id": "<slug>", "on": "command" or "file", "match": "<regex on the
  command or the path>", "lesson": "<what happened and what to do instead>"}`. The session hook
  shows it the next time that step comes up. A mistake about a whole topic is a rule, not a lesson.

Then:

```bash
uv run scripts/wiki.py log distill "Session: <focus>" "<log>, <n> decisions, <updated pages>"
uv run scripts/wiki.py reindex && uv run scripts/wiki.py lint
```

## 5. Report

```
Session closed:
- Log: wiki/30-sessions/2026-01-08-<focus>.md
- Decisions: 1 in wiki/50-decisions/log.md
- Updated: wiki/10-projects/<project>/README.md, docs/next-session.md
- Lint: 0
```

## Behaviour

<!-- customise: the variant from `.claude/rules/commits.md` ("Who saves a snapshot"); keep one line -->
- Snapshots follow `.claude/rules/commits.md`. When the assistant saves them itself: after the
  lint, commit the workspace files this skill and this session changed, by name, and add the
  commit to the report as one line. When the user is asked every time: no commit here; offer one
  in the last line of the report.
- Never a push: the user decides (`/release` for the workspace,
  `uv run scripts/wiki_backup.py push` for the wiki).
- No memory work: Claude Code's own memory handles that.
- Called again in the same session: update the existing log and decisions and skip the
  `log` line (the first one is already there; the operations log is append-only).
