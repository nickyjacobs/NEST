# NEST setup: the interview

Part of the NEST setup prompt. `SETUP.md`, one folder up, holds the rules for every part and says
when to read this one. Read `SETUP.md` first.

---

## 6. The interview

Question IDs (A1, B2 ...) are used in the routing table (section 7, `setup/routing.md`) and in
STATE.md. Ask in this order, but skip what is already answered. Appendix A and B are in
`setup/catalogue.md`: read it before block B ends.

### Block A: who you are

*Why:* every recommendation later (wiki sections, skills, the names) comes from this. *Lands in:*
the context pages of the wiki, the card in CLAUDE.md, `CLAUDE.local.md` for what is private.

- **A1** Tell me about yourself in a few sentences: what you do, where you live (country or time
  zone is enough), what a normal week looks like. Then confirm the local formats in one closed
  question, proposed from the country: time zone, 24-hour or AM/PM clock, date format, units,
  currency. Skills that show times, prices or weather use these.
- **A2** Work or study: your role, the kind of organisation, what you are responsible for. Will
  you use this workspace for work too? If yes: does your employer or school have rules about AI
  tools, and may work information be in here at all? (Unknown is fine: then work content stays
  out until it is known, as an open question.)
- **A3** Your days: fixed routines, the hours you have for your own projects per week, when you
  are at your best.
- **A4** The people around you that matter for planning (roles only: partner, kids, manager,
  team, clients). Names only if the user wants them in the private context.
- **A5** Interests and hobbies, and what you would like to learn.
- **A6** Where do you want to grow in the next one to three years? What would make this year a
  good year? Short-term goals (this quarter) and long-term ones.
- **A7** **Apps and software.** Go through the categories in two or three short rounds, never
  as one long table, and propose what is common so the user only corrects: mail, calendar, tasks or to-do, notes (where do notes live
  today?), chat (Teams, Slack, WhatsApp, Signal ...), cloud storage, browser, password manager,
  smart home, music, and the tools of their work or study. Per app: private or work account, and
  what they use it for. *This list feeds block D and, later, every new skill.*
- **A8** How should the assistant talk to you: formal or casual, short or explanatory, humour or
  none? What do you never want to see (long lists, emojis, flattery, jargon)?

Recap, yes (the answers are in `_setup/interview/A.md` already, see 4.2), and keep going.

### Block B: where you get stuck

*Why:* the workspace should fix real problems, not add a hobby. *Lands in:* the recommendations in
blocks C and D, and the first tasks at the end.

- **B1** What frustrates you most in how you work now? Offer the list below as a numbered list
  in plain text (it is too long for the choice dialog); they answer with the numbers and may
  add their own:
  writing notes at all · finding notes again · notes piling up unprocessed · Obsidian feels
  overwhelming · losing track of projects and priorities · forgetting what I learned · studying
  for a course or certification · ideas that never get worked out or decided · career or job
  search · mail chaos · calendar and day planning ·
  research takes long or sources are unreliable · writing sounds stiff or AI-like · repeating the
  same tasks · fear of leaking something sensitive · losing work (no backups) · every Claude session
  starts from zero · the assistant repeats a mistake · a long conversation forgets what I asked.
- **B2** For the top two or three: what does it look like in practice? A recent example.
- **B3** Rank them: which one would make the biggest difference if it were gone?
- **B4** What have you tried before that did not stick, and why? (This prevents rebuilding the
  thing that failed.)

Then show the matching recommendations from the matrix in Appendix A: per pain point one line
with what NEST would build for it. This is a preview, not a decision; blocks C and D decide.

### Block C: the wiki

*Why:* the wiki is the long-term memory; its shape decides whether the user keeps using it.
*Lands in:* `wiki.config.json`, the folder tree, templates, the CSS, the dashboard. The wiki is
part of every workspace: the assistant's context pages live in it. Say so at the start of this
block, with the small option next to it: a user who wants no notes beyond that gets the
backbone only (context, sessions, decisions, archive) and none of the wiki skills.

Explain the idea first in three lines, at the user's level: a vault in Obsidian; the user drops
things in an inbox; the assistant files them into sections, links and indexes them; nothing is
deleted.

- **C1** **Sections.** Propose a folder tree derived from A and B, with every folder name
  written exactly as it will be on disk (lowercase, hyphens, no spaces, for example
  `30-weiterbildung`) and the readable label next to it; what the user confirms is what you
  build, letter for letter. Letters of the user's language are fine in a folder name
  (`70-privé`); never drop an accent on your own. Keep the generic backbone:
  numbered sections with gaps (00, 10, 20 ...) so new ones fit between, plus `_inbox`,
  `_templates`, `_bases` and an archive section (90). Typical sections: context (who you are,
  goals, priorities), projects, knowledge, research, sessions, references, decisions, archive. Add
  domain sections from block A (for example study, family, health, clients, a hobby) and leave
  out what the user will not use. Show the tree; the user adjusts. At most about ten top-level
  sections: more is a list nobody uses.
- **C2** **Language of the wiki.** Folder names and labels in the user's language or English?
  (Recommend: page content in their language; folder names in whatever they find easiest to read
  in the file explorer.)
- **C3** **Kinds and status words.** Propose the `kind` values for knowledge notes (for example
  concept, tool, procedure, skill, recipe, person-free case) and the inbox (capture, question,
  link), and the closed set of status words (draft, active, done, parked, archived, question), in
  the chosen language. Confirm. Words in another language are fine: B2 maps them to their roles
  with `status_roles` and `question_kind` in `wiki.config.json` (see `kit/scripts/WIKI-CONFIG.md`).
- **C4** **The dashboard (Home).** Which tiles at the top (quick capture buttons, go-to buttons),
  which numbers (KPIs) matter to them (for example inbox count, active projects, a study or habit
  counter), which lists (new this week, open questions, projects). Propose from B.
- **C5** **Look.** Light, dark or both; an accent colour; one colour per section (propose a
  palette, show the hex codes). Keep the Minimal theme as a recommendation.
- **C6** **Plugins and snippets.** Present the recommended set from
  `kit/wiki/obsidian/PLUGINS.md` (Minimal and Minimal Settings, Style Settings, Templater, Meta
  Bind, Notebook Navigator; Bases is built in), one line each: what it does here and why. Ask
  once: all of them (recommended), or which to leave out. The same for the base look CSS
  snippet (the snippet for idea pages is asked in D2, with the teams). Mention the safety settings (Templater does not run on file
  creation; Meta Bind has JavaScript off) and why.
- **C7** **Existing notes.** Tell the user, whatever they have today: the wiki is always a new
  vault inside the workspace; NEST never writes into a vault they already have, and never
  changes its settings. Do they have notes
  elsewhere (an older vault, another app) they want in? Do not import now: record where (path
  in `CLAUDE.local.md`) and plan it as a first task with `/wiki-ingest` or a copy into the inbox.

Show the final tree and the dashboard sketch as text. Yes, then on.

### Block D: skills and agents

*Why:* skills are the assistant's routines. Only what fits gets built. *Lands in:*
`.claude/skills/`, `.claude/agents/`, permission rules, the skills list in CLAUDE.md.

Present the catalogue in Appendix B as a short table first, with a star on the skills that match
the user's pain points from B. Then go through them **one at a time, or in small groups of at most three**, with the choice dialog:
what it does, why it fits them (name the pain point), recommended yes or no. Group the small ones
(the wiki skills) to keep it short.

For each chosen skill, ask the customise questions listed for it in Appendix B (one or two each,
proposals first). Read the `<!-- customise: ... -->` markers in the skill's reference files in
`kit/skills/<name>/` to make sure every marker gets an answer.

- **D1** The wiki skills (inbox, ingest, query, maintenance) and the Obsidian skills. Recommended
  as a set, unless the user wants the backbone only (block C).
- **D2** The Council (`idea`) and The Architects (`blueprint`). For each team: **full** (more
  agents, a jury of three, checked sources, several minutes and more tokens per run) or **light**
  (four or five agents, one judge, faster and cheaper). Explain the trade-off in two lines and
  recommend full for someone who will use it for real decisions, light for curiosity. Use the
  names The Council and The Architects (and the seat names) as they are, in every language,
  unless the user asks for a translation here; then use that translation everywhere from then on.
  Record the choice in STATE.md by filling in the `teams:` line at the top (replace it, do not
  add a second one); the name of the ideas section is added to that line in D7.
  With a team chosen, ask here whether the idea pages get the styled look (the idea snippet
  from C6's list) or the plain one.
- **D3** career, study-inbox, research, session-end, writing-style, release, skill-builder: per
  skill yes or no and its customise questions.
- **D4** **Integration skills** (calendar, mail, mail-organizer, morning-briefing). These touch the
  user's real accounts, so each gets its own round:
  1. **Which app and account**, from the inventory in A7. A work account often cannot or may not
     be connected; ask explicitly and respect the answer from A2.
  2. **Which route exists today.** First check what this session already has (Phase 0.4). If
     nothing fits, research current options for that app: the vendor's own MCP server or connector,
     well-maintained community MCP servers, a CLI, or the proven script route in
     `kit/integrations/microsoft-graph/` for Microsoft accounts. Follow the verification rules in
     `kit/integrations/README.md`: find it in current docs or the maker's repo, check that it is
     maintained, how it signs in, which scopes it asks, and whether it can send mail. Present at most
     three routes with your recommendation and the trade-offs (safety, cost, maintenance). When
     the user wants to connect now or soon, do this research now. When they say "later" or
     "maybe", do not: the skill is built with its "not connected" path, and choosing a route
     becomes an open item. Never invent a package or a command.
  3. **What it may do:** read only, or also change things. Which actions always ask first (these
     become `permissions.ask` rules; see `kit/integrations/permissions.example.json`). Sending mail
     is never part of NEST: replies are drafts.
  4. **How they work:** for mail the folder layout and what each folder is for, and how a reply is
     signed and in what tone; for calendar the
     calendars to read and to write, working hours, appointment types; for the briefing which blocks
     in which order, and from which apps.
  If no route works now, the skill is still built with a "not connected" path and the connection
  becomes an open item in STATE.md.
- **D5** **How independent may the assistant be?** Propose three groups (Appendix B gives each
  skill a default): runs only on the user's command; the assistant may propose it and runs it
  after a yes; the assistant may just do it. Confirm or adjust. Claude Code has one switch per
  skill for this: "only on command" sets `disable-model-invocation: true`. The difference
  between "propose first" and "just do it", and a mixed default such as "reading freely,
  changes after a yes", is written in the "When you act on your own" section of `CLAUDE.md`
  and in the skill's own ask-first rules.
- **D6** **Permission mode.** Recommend Claude Code's default mode (it asks before risky actions).
  If the user prefers fewer prompts, explain the trade-off and propose a few read-only allow rules
  instead of skipping permissions altogether.
- **D7** **Check the wiki tree against the skills.** Block C came before the skill choices, so
  compare: session-end needs a sessions section and a decisions log; research and wiki-query need a
  research section; wiki-ingest needs a references section with a raw sources folder; idea and
  blueprint need an ideas section; career and study-inbox need a projects section, and study-inbox
  needs the inbox folder name in `raw_folders`. Propose what is missing in one message, update
  `_setup/interview/C.md` after the yes, and write the name of the ideas section into `teams:`
  in STATE.md.

- **D8** **Session guards and updates.** Two things always run and need no answer, so only tell
  the user in two lines: their own messages are kept word for word in a local file, so a long
  conversation that gets summarised does not lose what they asked; and the assistant is told when
  a second session is open in the same folder. Then ask, with a recommendation each:
  1. **Lessons** (recommended yes): when something goes wrong, the assistant records a one-line
     lesson and is reminded of it the next time the same kind of step comes up.
  2. **Plans into the inbox** (yes when they use plan mode): an approved plan is
     copied into the wiki inbox, so it is not lost with the session.
  3. **Morning nudge** (only with morning-briefing): before which hour a new session may end its
     start line with a reminder, and the wording in their language.
  4. **News about NEST** (recommended yes): one line at the start of a session, at most once a
     week checked online, when NEST has a newer release. Nothing is ever installed on its own;
     the nest-update skill shows what is new and they pick.

### Block E: GitHub and tooling

*Why:* backups and history, and the option to share later. *Lands in:* `.github/`,
`.githooks/`, the README, `nest.json`, the backup setup.

Explain in two lines what git and GitHub add for this workspace (history, a backup off the
machine, undo). Then:

- **E1** Do you have a GitHub account? (yes / no, I want one / no GitHub). "I want one": they
  make it themselves on github.com (free), then go on with E2. No GitHub, or "later":
  the workspace still gets local git, so skip E2, E3 and E6 and ask only what local git needs:
  E5 (a name and an address for the commits; any address works locally), E7 (the pre-commit
  scan only) and E8. E4 is then (b): the wiki lives inside the local repo, so it has a history;
  a backup off the machine becomes an open item.
- **E2** Is the GitHub CLI signed in (from Phase 0)? If not: the user runs `! gh auth login`.
  Is a GitHub MCP server connected (Phase 0.4)? Not needed: the CLI is enough.
- **E3** A repo for the workspace: private (recommended), named after the workspace.
- **E4** The wiki: (a) a separate private backup repo with its own git folder, while the workspace
  repo ignores `wiki/` (recommended: the wiki is the most personal part, and the workspace repo can
  then be shared later without it); or (b) the wiki inside the workspace repo (simpler).
- **E5** Commit identity: for anything that may ever be public, the GitHub noreply address
  (`<id>+<login>@users.noreply.github.com`, from `gh api user`). Set it per repo.
- **E6** README style: a plain README, or a styled one (centred title or banner, a row of badges,
  a short tagline, a feature table with one emoji per row, a "what it is not" section). Show a
  small example. Optional.
- **E7** Protections: a pre-commit secret scan (recommended), a gitleaks workflow on GitHub
  (recommended), a checks workflow that runs the skills catalogue check and the secret scan on
  every push (recommended), Dependabot for workflow updates. Rulesets and branch protection: explain that on
  a private repo they need a paid plan, so they are optional.
- **E8** Who commits: the assistant commits only when the user asks, with a short imperative
  message and a prefix (`Add:`, `Fix:`, `Update:`, `Docs:`). Confirm.

### Block F: names and personality (last on purpose)

*Why:* now you know what this workspace means to the user, so the names can say it. *Lands in:*
`CLAUDE.md`, STATE.md, the folder name, the README.

- **F1** **The workspace folder.** Propose two or three names (short, lowercase, no spaces; the
  assistant's name in lowercase is a good default once F3 is known, so you may ask F1 after F3) and
  where it goes. Default: next to the NEST folder, unless that is a downloads folder or a folder
  a cloud service syncs (iCloud Drive, OneDrive, Dropbox, Google Drive: the path usually says
  so); then propose a folder in the user's home, such as `~/Projects`. Sync services and git
  get in each other's way and can damage files; say so once when the user prefers a synced
  place, and respect the answer. Check the path is free. A path without spaces is easier to
  type in commands; the hooks work either way.
- **F2** **What the workspace is for, in one sentence**, in the user's words. Propose one from A
  and B. It becomes the first line of CLAUDE.md and the README tagline.
- **F3** **The assistant's name.** Propose four to six acronyms. Each one:
  - spells a short, pronounceable name (four to six letters works best);
  - has every letter written out, in English or the user's language;
  - carries what this workspace means for the user: their goals from A6, their pain points from
    B, their interests from A5;
  - avoids brand names, product names and the names of real people;
  - comes with one line on why it fits.
  Example of the shape (do not reuse it): **MAPLE**, "Memory, Agenda, Projects, Learning,
  Everyday", for someone whose main pains were forgetting and overview. Also offer "my own name".
- **F4** **Personality:** three adjectives, and how the assistant addresses the user (first name,
  formal or informal). Take the answers from A8 as the proposal.

Recap of the whole interview in at most ten lines. Yes, then the handover.

**The handover.** The workspace folder lies outside the folder this session was started in, and
Claude Code may not write there. So the user creates it with one command:

1. After the yes to the recap, update STATE.md first: `workspace:` the absolute path, `assistant:` the name,
   `next: handover (the user creates the workspace folder; then B1 there)`,
   `read: setup/build.md (B1)`, `trigger: Read _setup/nest/SETUP.md and follow it.`
2. Give the user one command for their OS that creates the folder and copies `_setup/` into it
   and `SETUP.md`, `setup/` and `kit/` into `_setup/nest/`, with the real paths filled in. For example
   macOS and Linux: `mkdir -p "<ws>/_setup/nest" && cp -R _setup/. "<ws>/_setup/" && cp -R SETUP.md setup kit "<ws>/_setup/nest/"`;
   Windows PowerShell: `New-Item -ItemType Directory -Force "<ws>\_setup\nest" | Out-Null; Copy-Item -Recurse -Force _setup\* "<ws>\_setup\"; Copy-Item -Recurse -Force SETUP.md,setup,kit "<ws>\_setup\nest\"`.
   They run it with `!` in front, or in their own terminal.
3. Tell them to close Claude Code, open it in the new folder (`cd "<ws>"` then `claude`), trust the
   folder when asked, and type the trigger line (quote it). The copy of `_setup/` next to NEST
   can go later; it is gitignored.

A session that starts while `next:` still says `handover`: if the current folder is the
workspace path from STATE.md and `_setup/nest/SETUP.md` and `_setup/nest/setup/build.md`
exist, the copy worked: set `next: B1` and go on with B1. If you are still in the NEST folder: check whether the workspace
folder exists. If it does, tell the user to open Claude Code there and type the new trigger
line; if it does not, give the copy command again. If you cannot look there, ask the user
whether they ran the command; never assume they did not. Never start B1 from the NEST folder.
