# Commits and pushes

<!-- customise: the repos this applies to (the workspace repo, and the wiki backup if the user has one) -->
Applies to this workspace's repo and to the wiki backup.

## Who saves a snapshot

<!-- customise: keep the one variant the user chose in the interview (E8) and remove the other, with this comment -->
**Variant "the assistant saves":** Save a snapshot (a commit) yourself when a piece of work is
done and at the end of a session, without asking: stage the files you changed by name, commit
with a message as described below, and tell the user in one line what was saved. Do not commit
work that is half done, a file the user is still editing, or anything the secret scan stopped.
Never push by yourself: sending to GitHub and the wiki backup are always a question.

**Variant "ask every time":** Commit only on an explicit request ("commit", "save a
snapshot") or after a yes to your own question. Offer a snapshot when a piece of work is done;
do not ask more than once for the same work.

## Hard rules

- Push only on an explicit request ("push") or a yes. `/release` is that request, for one
  branch.
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
