# NEST setup: the final check and the wrap-up

Part of the NEST setup prompt. `SETUP.md`, one folder up, holds the rules for every part and says
when to read this one. Read `SETUP.md` first.

---

## 9. Final check

Go through this list and record each outcome in `_setup/log.md`. Say "done" only when the list is
done, and say what failed or was skipped.

1. `uv run scripts/wiki.py lint` reports zero errors; `reindex` runs.
2. The self-test of the secret guard passed and a fake key was blocked on write (B4.1), and on
   commit when the pre-commit scan was chosen.
3. `uv run scripts/skills_catalog.py --check` reports zero problems; the skills and agents that
   CLAUDE.md lists match what exists (count them).
4. `CLAUDE.md` is under 150 lines and holds no facts that change weekly.
5. Every answer from the interview is in the place section 7 names, or in the open questions.
6. Search the committed files for the user's full name, private names from `CLAUDE.local.md`, and
   absolute paths with a username: nothing outside `CLAUDE.local.md`, `_setup/` and ignored files.
7. Each chosen integration passed its read-only test, or is listed as open with the reason.
8. The security reviewer passed on the workspace (and on the wiki if it is backed up). It reads the
   "Approved to keep here" list in `CLAUDE.local.md`; a finding that is on that list, or a cost
   estimate inside an idea review, is not a reason to fail.
9. `git status` is clean after the last commit, or what is left is explained.

Say what this check does not cover: whether the answers describe the user well (that shows in the
first weeks), whether the Council's scores are well calibrated (that shows after about ten real
ideas), and whether an integration keeps working after its token expires.

---

## 10. Wrap-up

When you start the wrap-up, add its five points to STATE.md as checkboxes, plus every B4 test that
did not run yet. Tick each only when it is done; the wrap-up is not done while one is open.

1. Remove the "Setup in progress" line from `CLAUDE.md`. Keep `_setup/` as it is, with
   `_setup/nest/` in it: it is the history of how this workspace was made, it is gitignored, and
   the updater can fall back on that kit copy. When the wrap-up is done, set `next: done` in
   STATE.md.
2. Write `wiki/how-this-wiki-works.md` for real: how the workspace works, in plain words, on one
   page, in the user's language.
3. Give the user an overview in the chat itself, not as a pointer to a file: the folder tree two
   levels deep, one line per skill and agent with how to start it,
   the three commands they will use most, and what they maintain themselves (the context pages,
   the sensitive terms list, the open questions).
4. A cheat sheet: capture (drop it in the inbox), file (the inbox skill), find (the query skill),
   end of session, maintenance once a week.
5. Propose three or four **first tasks** that answer the top pain points from B3, for example:
   - "Notes pile up": put ten old notes in the inbox and run the inbox skill together.
   - "Ideas never get decided": run the idea skill on the idea they mentioned in block B.
   - "Mail chaos": a first organizer run on the inbox, board only, no moves.
   - "Every session starts from zero": end today with the session-end skill.
   Ask which one to start with. The first real task decides whether a workspace gets used.

From here the workspace is alive: a lesson or a rule gets added after something went wrong (a
lesson in `.claude/lessons.json` for one kind of step, a rule for a whole topic), a skill after a
task repeated three times (the skill builder helps), what stops being used moves to the archive,
and the nest-update skill brings over what NEST improves later.
