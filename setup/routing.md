# NEST setup: where every answer lands

Part of the NEST setup prompt. `SETUP.md`, one folder up, holds the rules for every part and says
when to read this one. Read `SETUP.md` first.

---

## 7. Where every answer lands

Walk this table at the end of each block and again before B4. Every ID points at a file or is an
open question.

| IDs | Lands in |
|---|---|
| language, level, OS, surface | `_setup/STATE.md`; the language and level lines in `CLAUDE.md`; `surface` decides the form of every instruction to open a folder or start a session, and the line in `CLAUDE.md` that says how this workspace is opened |
| A1 local formats | profile page; the formats line in `CLAUDE.md`; currency in the idea skill; units and time format in the calendar and briefing skills |
| A1, A3, A5, A6 | wiki context pages (profile, goals, priorities), the card in `CLAUDE.md` (at most 10 lines) |
| A2 | profile page (role, without employer name unless the user wants it); employer, school and AI rules in `CLAUDE.local.md`; a "work content" line in `.claude/rules/privacy.md` |
| A4 | roles in the profile page; names, if wanted, only in `CLAUDE.local.md` |
| A7 | wiki context page "apps and tools"; `kit/integrations/tool-map.example.md` adapted as `tool-map.md` for chosen integrations |
| A8, F4 | the "How you talk" section of `CLAUDE.md`; `.claude/rules/writing.md` if writing-style was chosen |
| B1 to B4 | `_setup/interview/B.md`; the recommendations in C and D; the first tasks in the wrap-up; tried-and-failed things as a line in the profile page |
| C1, C3 | `wiki.config.json` (sections, kinds, status words), the folder tree, section indexes |
| C2 | `wiki.config.json` labels, templates, `how-this-wiki-works` page |
| C4 | `wiki/Home.md`, `_bases/dashboard.base`, Meta Bind button templates |
| C5 | the palette, with its colour codes, in `_setup/interview/C.md` (the user chose it from `_setup/preview/palette.html`); then `wiki/.obsidian/snippets/base.css` tokens, `appearance.json`, Notebook Navigator colours |
| C6 | `wiki/.obsidian/` settings (`community-plugins.json`, the enabled snippets in `appearance.json`); what `obsidian_setup.py install` downloads in B2 |
| C7 | `CLAUDE.local.md` (where the old notes are, as paths); the first of the first tasks in the wrap-up. The old vault itself is never opened or touched during the setup |
| C8 | the devices and the chosen sync route on the "apps and tools" context page; an open item in `docs/next-session.md` with the steps from `kit/wiki/obsidian/DEVICES.md` when the route is not set up during the build; never a file inside `.obsidian/` |
| D1 to D3 | `.claude/skills/`, `.claude/agents/`, the skills list in `CLAUDE.md`, `docs/skills.md`; the course list in the study-inbox skill |
| D4 | the integration skill files, `tool-map.md`, `.claude/settings.json` permissions, `mail-folders.md` in the workspace root (gitignored), the blocks in the morning-briefing skill; failed or postponed routes in STATE.md "Open" |
| D5 | `disable-model-invocation` per skill; the "When you act on your own" section of `CLAUDE.md` |
| D6 | `.claude/settings.json` (`permissions`). The short list for the build is something else: it lives in `.claude/settings.local.json` from before B1 until the wrap-up, after its own yes |
| D7 | `_setup/interview/C.md`, then `wiki.config.json` and the tree in B2 |
| D8 | the `lesson` and `plan` hooks in `.claude/settings.json`; `morning_nudge` and `nest.update_check` in `nest.json`; a line in `CLAUDE.md` that lessons go into `.claude/lessons.json` |
| team names and sizes (D2) | `teams:` in STATE.md; every skill, agent and wiki page that names the teams |
| E1 to E7 | `nest.json` (backup git dir, next to the stamp from B1), `.github/`, `.githooks/`, README, `.gitignore`, repo settings, `.claude/rules/commits.md` |
| E8 | the "Who saves a snapshot" part of `.claude/rules/commits.md` and the closing step of the session-end skill, each in the variant the user chose; a line in the "When you act on your own" section of `CLAUDE.md` |
| F1 | the workspace path in STATE.md |
| F2, F3 | `CLAUDE.md` title and first lines, README title and tagline, `assistant:` in STATE.md |
| skipped questions | `_setup/open-questions.md`, later `wiki/<context>/open-questions.md` |
