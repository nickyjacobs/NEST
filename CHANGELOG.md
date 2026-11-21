<p align="center">
  <img src="assets/release-banner.png" alt="NEST: New Environment Setup Toolkit" width="520">
</p>

# Changelog

Every release of NEST, newest first. Each one starts with a sentence and a **For your workspace**
section in plain words: what it means if you already built a workspace with an earlier release.
`/nest-update` in your workspace reads that section to you.

| Release | Date | In short |
|---|---|---|
| [1.0.0](#100---2026-11-22) | 2026-11-22 | The first release: an interview that builds your own Claude Code workspace, and a way to keep it up to date afterwards. |

<sub>Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) · Versions: [Semantic Versioning](https://semver.org/) · How a release is made: [docs/project/releasing.md](docs/project/releasing.md)</sub>

## [Unreleased]

---

## [1.0.0] - 2026-11-22

> **In short:** The first release: an interview that builds your own Claude Code workspace, and a way to keep it up to date afterwards.

### 🏠 For your workspace

- This is the first release, so there is nothing to bring over.
- From now on your workspace tells you when a newer release is out. `/nest-update` then shows
  what is new in plain words and changes only the parts you pick.

### ✨ Added

- **The setup prompt.** `SETUP.md`: a machine check, an interview in six blocks, a table that
  says where every answer lands, build steps with a check each, a final test round and a wrap-up
  with first tasks. It keeps its progress in a state file, so you can stop and continue in a
  later session.
- **Skills.** Wiki inbox, ingest, query and maintenance, Obsidian Markdown and Bases, idea (The
  Council), blueprint (The Architects), career, study inbox, research, session end, writing
  style, release, calendar, mail, mail organizer, morning briefing and a skill builder. You
  choose them one by one.
- **Agents.** The Council and The Architects in a full and a light size, a researcher and a
  read-only security reviewer.
- **Guards.** A secret scan before and after every write, a session-start line, a pre-commit
  scan, a guard that keeps the read-only reviewer read-only, and a guard that keeps the blind
  seats of the two teams inside their own run file.
- **Session guards.** Your own messages are kept word for word across a compaction, the
  assistant is told when a second session is open in the same folder, recorded lessons are shown
  when they apply, and an approved plan can be copied into the wiki inbox.
- **Updates.** `nest.json` records which release a workspace was built from. The `nest-update`
  skill and `nest_update.py` bring over a newer release: untouched files are replaced, adapted
  files are merged with your changes kept, every file is backed up first, and one command puts
  everything back.
- **The wiki kit.** Templates, Bases views, a Home page, base CSS with colour tokens, Obsidian
  settings and a plugin guide.
- **Integrations.** A decision guide per app category, a tool map, permission rules and a
  Microsoft Graph route for mail and calendar that cannot send mail.
- **GitHub kit.** A README template, a gitignore, a pre-commit hook and workflows for a
  workspace repo, plus a separate backup for the wiki.
- **Scripts with tests.** Wiki lint, reindex, stats and log, the skills catalogue, Council
  scoring, the idea page builder, the writing-style check and the wiki backup, tested on macOS,
  Linux and Windows.

[Unreleased]: https://github.com/nickyjacobs/NEST/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/nickyjacobs/NEST/releases/tag/v1.0.0
