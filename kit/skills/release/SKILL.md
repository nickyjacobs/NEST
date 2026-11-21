---
name: release
description: >-
  Puts workspace changes into git, the step after /session-end: shows status and diff, groups uncommitted work into one commit per topic with an explicit file list, runs the workspace check, and pushes only after the user's yes. Updates docs/next-session.md. Never --no-verify, never force-push main. Only on /release.
argument-hint: "[branch]"
disable-model-invocation: true
metadata:
  does: "Commits your workspace changes per topic, runs the check and pushes after your yes."
  try:
    - "/release"
    - "/release feature/<short-name>"
---

# /release

The commit rules (`.claude/rules/commits.md`) still apply: commit and push only on request.
`/release` is that request, for one branch, with one go on the plan up front.

**Not for:** the wiki (`uv run scripts/wiki_backup.py push`, separately, on request), a session log or
decisions (`/session-end` first).

## 1. Take stock

```bash
git status --short
git branch --show-current
git log --oneline @{u}..HEAD 2>/dev/null
git diff --stat
```

Group the uncommitted work per topic (files that together are one change) and propose one commit
line per group: imperative, at most 70 characters, prefix `Fix:`, `Add:`, `Update:`, `Refactor:`
or `Docs:` where it fits; a body only for the why. Sensitive files (`.env`, `*.local.md`,
`.claude/settings.local.json`, anything under `wiki/`) stay out of the commit: say so.

<!-- customise: branch workflow (default: work on main for a personal workspace; feature branches when the user chose them in the interview) -->
On a feature branch: the plan also holds the merge into `main` (fast-forward when possible,
otherwise a merge commit with the branch goal as its line).

Then `docs/next-session.md`: mark done what this release finishes and put the next open item at
the top, touching only what this release covers. The change joins the last commit group.

## 2. The plan, one go

Show in one block: the commits with their file lists, the merge if any, and whether a push
follows (only when a remote exists). Ask "OK?" and wait. No go: do nothing.

## 3. Execute

1. Per group: `git add <file> <file> ...` (never `git add -A` or `git add .`), then
   `git commit -m "<line>"`. A hook that fails: fix the cause (secret scan, lint), never
   `--no-verify`. No `Co-Authored-By` trailer and no "Generated with" line.
<!-- customise: the workspace check command (wiki lint, skills check, tests if the workspace has them) -->
2. The workspace check:
   `uv run scripts/wiki.py lint && uv run scripts/skills_catalog.py --check`, plus the tests when
   the workspace has them. Red: stop, show the error, merge and push nothing.
3. Feature branch: `git checkout main && git pull --ff-only && git merge <branch>`. A conflict:
   stop and show it, never resolve without the user.
4. Push only after the user's yes on the plan: `git push origin <branch>`. A rejected push gets a
   diagnosis (`git fetch`, `git status`), never `--force`, and never a force-push of `main`.

## 4. Close

- Report in three lines: commits (count and lines), merge (fast-forward or commit, hash), push
  (ok, skipped, or rejected with the reason). Deleting a branch: only as a question, never on
  your own.
