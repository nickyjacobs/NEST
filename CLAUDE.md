# NEST: working on this repo

You are Claude Code working on NEST itself: the setup prompt (`SETUP.md`) and its reference kit
(`kit/`). You are not running the setup here; a user runs it in their own folder.

## Layout

- `SETUP.md`: the prompt. Sections 0-10 plus appendices; section 7 is the answer routing table.
- `kit/`: reference files the setup adapts per user (`kit/README.md` explains each folder).
  `kit/scripts/` holds the Python tools and their tests; `kit/skills/`, `kit/agents/`,
  `kit/wiki/`, `kit/claude/`, `kit/integrations/`, `kit/github/` the rest.
- `assets/`: banner and the quick start GIF (source in `assets/quickstart-src/`).
  `assets/roadmap.png` is drawn from `assets/roadmap.svg`: when `ROADMAP.md` changes, change the
  SVG to match and render it again with headless Chrome at twice the size
  (`--headless=new --force-device-scale-factor=2 --default-background-color=00000000
  --window-size=1600,772 --screenshot=assets/roadmap.png file://<path>/assets/roadmap.svg`).
- `docs/project/backlog.md`: what is known to be open. `docs/reference/hooks-notes.md`: the hook facts
  the scripts rely on. `CHANGELOG.md`: Keep a Changelog, in the template of `docs/project/releasing.md`.
- `tools/`: checks for this repo itself (`release_check.py`); not part of the kit.

## Branches, commits and releases

- Never commit to `main` or `develop`. Work starts from `develop` on `feature/<short-name>` or
  `fix/<short-name>` (or `hotfix/<short-name>` from `main` for an urgent fix to a release) and
  goes back through a pull request against `develop`, merged with a squash.
- Commits and pull request titles share one format: `Prefix: imperative`, at most 70 characters,
  with `Add:`, `Update:`, `Fix:`, `Refactor:`, `Docs:` or `Release:`.
- A release is a `release/<x.y.z>` branch from `develop`, merged into `main` with a merge commit
  `Release: vX.Y.Z`, tagged `vX.Y.Z`, then `main` merged back into `develop`. Pushing the tag
  publishes the GitHub release from the changelog block. Never move or delete a tag: built
  workspaces compare tags to update themselves.
- The templates: `CONTRIBUTING.md` (branches, commits, pull requests, merging) and
  `docs/project/releasing.md` (versions, the changelog template, the release steps).

## Before every commit

1. `uv run --project kit/scripts pytest -q kit/scripts/tests` passes.
2. Skills changed: copy `kit/skills` and the agents into a temporary `.claude/` and run
   `uv run --script kit/scripts/skills_catalog.py --root <tmp> --check`.
3. `uv run --script kit/scripts/validate.py --staged` reports no hard findings.
4. `uv run --script tools/release_check.py` passes (changelog template, version numbers).
5. Stage explicit files; commit only when asked; no `Co-Authored-By` or "Generated with" lines.

## Rules for kit content

- Generic and English. No real names, employers, paths, IPs or accounts; fictional people only.
- Every point the setup must personalise carries `<!-- customise: ... -->`; placeholders look like
  `<fill in: ...>`.
- No em dashes in docs. Scripts are single-file, PEP 723, cross-platform (pathlib, utf-8).
- Never tell a setup to run `claude mcp list` or read MCP config files: they print keys.
- A change to the interview or the build keeps section 7 (routing) and Appendix B consistent.
- The version lives in four places: the README badge, the `SETUP.md` header, the STATE template
  in `SETUP.md` and the newest heading in `CHANGELOG.md`. `tools/release_check.py` checks them.
- A kit change reaches workspaces that already exist, through `kit/scripts/nest_update.py` and
  the `nest-update` skill. Say what it means for them under `### For your workspace` in the
  changelog, in plain words. A new always-installed file goes into the list in `kit/README.md`,
  and a kit file with a fixed place in a workspace into `target_for` in `nest_update.py`.

## Trial runs

The setup is tested by driving it with a fictional persona in an empty scratch folder: one
`claude -p` call per user message, isolated with
`--setting-sources project,local --strict-mcp-config --permission-mode acceptEdits`, an allow list
for local commands, and a deny list for `gh`, `git push`, `rm`, installs, `claude mcp` and reads of
`~/.claude.json`, `~/.claude/**` and `.mcp.json`. Findings go into `CHANGELOG.md` and fixes into a
feature branch.

A skill that writes under `.claude/` (the nest-update skill, the skill builder) cannot be tried
that way: in a folder whose trust dialog was never accepted, a `-p` session refuses those writes
under `acceptEdits`, whatever the allow list says. Try such a skill with
`--permission-mode bypassPermissions` in a throwaway folder, keep the deny list, and give the
session a fixed `--session-id` so later turns can `--resume` it. For an update trial, build a
local NEST source with two tags and point the workspace's `nest.source` at it.
