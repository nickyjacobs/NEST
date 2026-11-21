# Commits and pushes

<!-- customise: the repos this applies to (the workspace repo, and the wiki backup if the user has one) -->
Applies to this workspace's repo and to the wiki backup.

## Hard rules

- Commit or push only on an explicit request ("commit", "push"). `/release` is that request, for
  one branch.
- Never `--no-verify` and never skip a hook: when a hook fails, fix the cause.
- Never force-push `main`. A rejected push gets a diagnosis, not force.
- No `Co-Authored-By` trailer and no "Generated with" line: commits are the user's.

## How

- Stage specific files by name; no `git add -A` or `git add .` while other work is open.
<!-- customise: branch workflow (default: main for a personal workspace; feature branches when chosen in the interview) -->
- Experiments go on a feature branch (`feature/<short-name>`, `fix/<short-name>`).
- First line: imperative, at most 70 characters, with the prefix `Fix:`, `Add:`, `Update:`,
  `Refactor:` or `Docs:` where it fits.
- Body (optional): why, not what.
<!-- customise: remove this line when the user has no wiki backup -->
- The wiki backup goes with `uv run scripts/wiki_backup.py push ["message"]`, only when the user
  asks.
