# NEST setup: the interview

Part of the NEST setup prompt. `SETUP.md`, one folder up, holds the rules for every part and says
when to read this one. Read `SETUP.md` first.

---

## 6. The interview

Question IDs (A1, B2 ...) are used in the routing table (section 7, `setup/routing.md`), in
STATE.md and in the interview files. They are your labels: the user never sees one. Ask in this
order, but skip what is already answered. Appendix A and B are in `setup/catalogue.md`: read it
before block B ends.

Each question below says how it is asked: **open** (the user's own words, one per message),
**choice** (the dialog), or **proposal** (you show what you would do and ask whether it is
right, with the two-option dialog). Section 4.2 has the rules; for a beginner more questions
become proposals or defaults, as each block says.

### Block A: who you are

*Why:* every recommendation later (wiki sections, skills, the names) comes from this. *Lands in:*
the context pages of the wiki, the card in CLAUDE.md, `CLAUDE.local.md` for what is private.

- **A1** *Open.* Tell me about yourself in a few sentences: what you do and where you live
  (country or time zone is enough). Say that a short answer is fine and that names of other
  people are not needed. Their week comes in A3; do not ask for it here. Then a *choice* to confirm the local formats,
  proposed from the country: time zone, 24-hour or AM/PM clock, date format, units, currency.
  Skills that show times, prices or weather use these.
- **A2** *Open:* work or study, your role, the kind of organisation, what you are responsible
  for. Then two *choices*: will you use this workspace for work too; and if yes, does your
  employer or school have rules about AI tools (yes, there are rules / no / I do not know).
  Unknown is fine: then work content stays out until it is known, as an open question.
- **A3** *Choices:* the hours you have for your own projects in a week, and when you are at
  your best (morning, afternoon, evening, it varies). Fixed routines only when the user brings
  them up.
- **A4** *Choice, several answers:* the people around you that matter for planning (partner,
  children, manager, team, clients, nobody in particular). Roles only. Names only if the user
  wants them in the private context.
- **A5** *Open.* What do you like to do outside work or study? (What they want to learn comes
  out of A6; do not add it as a second question here.)
- **A6** *Open.* What would make this year a good year? Follow up once for the longer view
  (one to three years) when the answer invites it; do not ask for goals per quarter.
- **A7** **Apps and software.** *Choices with several answers,* one dialog of up to four
  categories at a time, the common apps named and "Other" for the rest: mail, calendar, tasks or
  to-do, notes (where do notes live today? Obsidian is one of the options to name), chat, cloud storage, browser, password manager,
  smart home, music, and the tools of their work or study. Then one *choice* per app that has
  both kinds: a private or a work account. Skip a category the user clearly does not use. An
  app nobody answered for stays "unknown": do not ask again. *This list feeds block D and,
  later, every new skill.*
- **A8** *Choices:* how the assistant talks to you (formal or casual; short or explanatory;
  humour or none) and what you never want to see (long lists, emojis, flattery, jargon; several
  answers). From this answer on your own messages follow it.

Recap, yes (the answers are in `_setup/interview/A.md` already, see 4.2), and keep going.

### Block B: where you get stuck

*Why:* the workspace should fix real problems, not add a hobby. *Lands in:* the recommendations in
blocks C and D, and the first tasks at the end.

- **B1** *Choices with several answers.* What gets in your way today? Offer the list below in
  two dialogs, grouped as it is here, each group one question; they tick what they recognise
  and add their own under "Other":
  - notes: writing notes at all · finding notes again · notes piling up unprocessed · Obsidian
    feels overwhelming
  - overview: losing track of projects and priorities · ideas that never get worked out or
    decided · calendar and day planning · mail chaos
  - learning and work: forgetting what I learned · studying for a course or certification ·
    career or job search · research takes long or sources are unreliable
  - writing and routine: writing sounds stiff or AI-like · repeating the same tasks
  - safety: fear of leaking something sensitive · losing work (no backups)
  - working with an assistant: every Claude session starts from zero · the assistant repeats a
    mistake · a long conversation forgets what I asked
  A group has more than four entries only on paper: put the four likeliest for this user in the
  dialog and leave the rest to "Other".
- **B3** *Choice,* asked before B2: of the ones you ticked, which would make the biggest
  difference if it were gone?
- **B2** *Open.* For that one: what does it look like in practice? A recent example. One
  example is enough; do not ask for the others.
- **B4** *Open, and say it may be skipped.* What have you tried before that did not stick, and
  why? (This prevents rebuilding the thing that failed.)

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

- **C1** **Sections.** *Proposal.* First, in a message of its own, the idea of the wiki in
  three lines and the folder tree itself, each folder with a few words on what goes in it; then
  the dialog. The dialog's question says how many folders the user just saw ("these nine
  folders"), so you cannot ask it without having shown them. Propose a folder tree derived from A and B, with every folder name
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
- **C2** **Language of the wiki.** *Choice.* Folder names and labels in the user's language or English?
  (Recommend: page content in their language; folder names in whatever they find easiest to read
  in the file explorer.)
- **C3** **Kinds and status words.** *Proposal; for a beginner a default, not a question.*
  The `kind` values for knowledge notes (for example concept, tool, procedure, skill, recipe,
  person-free case) and the inbox (capture, question, link), and the closed set of status words
  (draft, active, done, parked, archived, question), in the chosen language. A beginner gets
  them as they are, with one line that says so. Words in another language are fine: B2 maps
  them to their roles with `status_roles` and `question_kind` in `wiki.config.json` (see
  `kit/scripts/WIKI-CONFIG.md`).
- **C4** **The dashboard (Home).** *Proposal,* built from B: which tiles at the top (quick
  capture buttons, go-to buttons), at most three numbers that matter to them (for example inbox
  count, active projects, a study or habit counter), which lists (new this week, open questions,
  projects). Home has room for three numbers: a fourth replaces one, it is not added.
- **C5** **Look.** First a *choice:* light, dark or both; and which colours they like (a few
  named families such as blue, green, purple, warm, plus "Other"). Then show, never describe:
  copy `kit/wiki/palette-preview.html` to `_setup/preview/palette.html`, fill it with two or
  three options (an accent colour and one colour per section from C1, each option with a name
  in plain words), and open it in their browser (macOS `open`, Windows `start ""`, Linux
  `xdg-open`, with the full path). Say in one line, in the message before the dialog, that a
  page with the options has opened in their browser. The options in the dialog are in the order
  of the letters on the page. Then a
  *choice* between the letters on that page, with "something else" as the way to ask for another
  round. No colour code ever appears in a message or a dialog: the user cannot see `#8B5CF6`.
  Write the chosen palette, with its codes, into `_setup/interview/C.md`. Keep the Minimal theme
  as a recommendation. The preview file stays in `_setup/`; do not leave copies elsewhere.
- **C6** **Plugins and snippets.** *Choice:* all of them (recommended) or "let me choose", and
  only then one question with several answers. Before the dialog, one line each from
  `kit/wiki/obsidian/PLUGINS.md` on what a plugin does here (Minimal and Minimal Settings, Style
  Settings, Templater, Meta Bind, Notebook Navigator; Bases is built in). A beginner hears in
  two sentences what plugins are and that the setup installs them, and gets the recommended set
  without the list. The base look CSS snippet comes with the theme (the snippet for idea pages is
  asked in D2, with the teams). Mention the safety settings once (Templater does not run on file
  creation; Meta Bind has JavaScript off) and why.
- **C7** **Existing notes.** Tell the user, whatever they have today: the wiki is always a new
  vault inside the workspace; NEST never writes into a vault they already have, and never
  changes its settings. Then find out what exists, because a user who answers "no" here and has
  two hundred notes in an old vault starts with an empty wiki and a migration as their first
  task. *Choice:* do you keep notes somewhere today (an Obsidian vault, another app, loose
  files, nowhere)? With Obsidian installed, ask in the same dialog whether you may look at the
  list of vaults Obsidian knows on this computer: only the names of the folders, never the
  notes. After a yes: `uv run --script kit/scripts/obsidian_setup.py vaults`, then a *choice with
  several answers* of the vaults it found: which of these do you want to bring in. When the
  command finds nothing, or the notes are on another computer or in another app: one *open*
  question, where. An answer such as "in my documents, a folder called Notes" is enough for
  now: record it as they said it, with an open item to find the exact folder together when
  the move starts. Write down exactly what they said, word for word ("my documents, the folder
  Notes Jolien"), so nobody has to ask again. Do not import now and do not
  open any of those folders: record the paths, or their words, in `CLAUDE.local.md` and plan the move as the
  first task after the build (section 10).

- **C8** **Other devices.** *Choice, several answers, no recommended option:* where else do you
  want to read and write your notes (an iPhone, an Android phone, a tablet, a second computer
  such as a work laptop, nowhere else). "Nowhere else" ends the question. Otherwise read
  `kit/wiki/obsidian/DEVICES.md` and write a message of its own before the next dialog, four
  short lines in plain words:
  1. the route it gives for their devices, and what it is ("Obsidian's own service that keeps
     your notes the same on your computer and your phone");
  2. what it costs, as an amount: "about" the price, the month you read it, and that they should
     check it. "Paid" without an amount is not an answer;
  3. the free alternative, what it is and what it asks of them;
  4. what a sync route does not do: the assistant and its routines stay on this computer. A note
     made on the phone lands in the inbox and is filed the next time they sit down here.
  Be honest when the only route a beginner can manage costs money. Then a *choice,* without a
  recommended option, because it is their money and their time: this route, the alternative, or
  decide later. Nothing is installed or paid for during the interview: the route is set up
  after the build, with the user, and only when they want to. Never propose to put the
  workspace folder itself in a cloud folder (see F1).

Show the final tree and the dashboard sketch as text. Yes, then on.

### Block D: skills and agents

*Why:* skills are the assistant's routines. Only what fits gets built. *Lands in:*
`.claude/skills/`, `.claude/agents/`, permission rules, the skills list in CLAUDE.md.

Present the catalogue in Appendix B first, as a short list: one line per skill that says what
it does for this user, the ones that match their pain points from B on top. For a beginner
leave the skill names out of that list until they chose. Then go through them with the choice
dialog, **one dialog per group, at most three skills in it**: what it does, why it fits them
(name the pain point), recommended yes or no. Group the small ones (the wiki skills).

For each chosen skill, the customise questions listed for it in Appendix B are *proposals*: fill
in what earlier answers give you and ask only what is left, one dialog per skill at most. Read
the `<!-- customise: ... -->` markers in the skill's reference files in `kit/skills/<name>/` to
make sure every marker gets a value; a marker the interview cannot fill becomes a default you
name, or an open question, never a fifth question in one message.

- **D1** The wiki skills (inbox, ingest, query, maintenance) and the Obsidian skills. Recommended
  as a set, unless the user wants the backbone only (block C). A skill you leave out of a set is
  named with the reason; never drop one silently.
- **D2** The Council (`verdict`) and The Architects (`blueprint`). Recommend a team when a pain point from block B calls for it (ideas that never get decided: The Council; ideas that never get worked out: The Architects) and "no" otherwise; the size names are said in the user's language. They are two separate things and
  get two separate questions, each with its own options: "The Council, which judges an idea:
  no / light / full" and "The Architects, who work an idea out: no / light / full". Never one
  question "do you want the teams": in two trials that gave the user a team they did not want.
  For each team the sizes are **full** (more
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
- **D5** **How independent may the assistant be?** *Proposal; for a beginner the defaults.*
  Three groups (Appendix B gives each skill a default): runs only on the user's command; the
  assistant may propose it and runs it after a yes; the assistant may just do it. A beginner
  hears the idea in two sentences and gets the defaults, with "show me the list" as the other
  option. Claude Code has one switch per skill for this: "only on command" sets
  `disable-model-invocation: true`. The difference between "propose first" and "just do it", and
  a mixed default such as "reading freely, changes after a yes", is written in the "When you act
  on your own" section of `CLAUDE.md` and in the skill's own ask-first rules.
- **D6** **Permission mode.** *For a beginner no question.* Claude Code decides how often it
  asks before it acts, and the user set that themselves in the app; NEST does not change it.
  Do not describe the mode they are in unless you know it: a user who was never asked anything
  during this setup is not in the mode that "asks before risky actions". Say in one line that
  the workspace's own guards (the secret scan, the ask-first rules of the skills) work in every
  mode. A technical user who wants fewer prompts: explain the trade-off and propose a few
  read-only allow rules instead of skipping permissions altogether.
- **D7** **Check the wiki tree against the skills.** Block C came before the skill choices, so
  compare: session-end needs a sessions section and a decisions log; research and wiki-query need a
  research section; wiki-ingest needs a references section with a raw sources folder; verdict and
  blueprint need an ideas section; career and study-inbox need a projects section, and study-inbox
  needs the inbox folder name in `raw_folders`. Propose what is missing in one message, update
  `_setup/interview/C.md` after the yes, and write the name of the ideas section into `teams:`
  in STATE.md.

- **D8** **Session guards and updates.** Two things always run and need no answer, so only tell
  the user in two lines: their own messages are kept word for word in a local file, so a long
  conversation that gets summarised does not lose what they asked; and the assistant is told when
  a second session is open in the same folder. Then ask, in one dialog, with a recommendation each:
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
- **E2** Is the GitHub CLI signed in (from Phase 0)? If not: the user runs `gh auth login` themselves, in the form for where they work (section 3: `!` in front in a terminal session, a terminal window in VS Code).
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
- **E8** **Who saves the snapshots.** First three plain sentences, whatever the level: a
  snapshot (git calls it a commit) is a save point of the workspace on this computer that you
  can go back to; sending (a push) puts a copy of the snapshots on GitHub; nothing is ever sent
  without a yes. Then one *choice,* without a recommended option, because both are sound and it
  is about how the user likes to work:
  - **The assistant saves snapshots itself:** when a piece of work is done and at the end of a
    session, with one line that says so. It still never sends anything by itself.
  - **The assistant asks every time** before it saves a snapshot.
  Messages are short and imperative with a prefix (`Add:`, `Fix:`, `Update:`, `Docs:`) either
  way. The answer holds from this moment, so also for the rest of the setup: with the first
  choice you save a snapshot at each stop point and say so in one line; with the second you ask
  once per session, as section 8 says.

### Block F: names and personality (last on purpose)

*Why:* now you know what this workspace means to the user, so the names can say it. *Lands in:*
`CLAUDE.md`, STATE.md, the folder name, the README.

- **F1** **The workspace folder.** *Choice,* asked after F3: two or three names (short,
  lowercase, no spaces; the assistant's name in lowercase first) and where it goes. Default:
  next to the NEST folder, unless that is a downloads folder or a folder a cloud service syncs
  (iCloud Drive, OneDrive, Dropbox, Google Drive: the path usually says so); then propose a
  folder in the user's home, such as `~/Projects`. Sync services and git get in each other's way
  and can damage files; say so once when the user prefers a synced place, and respect the
  answer. Check the path is free. A path without spaces is easier to type in commands; the
  hooks work either way.
- **F2** **What the workspace is for, in one sentence**, in the user's words. *Proposal:* one from A
  and B. It becomes the first line of CLAUDE.md and the README tagline.
- **F3** **The assistant's name.** *Choice,* the first question of this block: four acronyms in the dialog, with "show me four others" among them; "Other" is their own name. At most three rounds, then ask what a good name would sound like. Each one:
  - spells a short, pronounceable name (four to six letters works best);
  - has every letter written out, in English or the user's language;
  - carries what this workspace means for the user: their goals from A6, their pain points from
    B, their interests from A5;
  - avoids brand names, product names and the names of real people;
  - comes with one line on why it fits.
  Example of the shape (do not reuse it): **MAPLE**, "Memory, Agenda, Projects, Learning,
  Everyday", for someone whose main pains were forgetting and overview.
- **F4** **Personality.** *Proposal* from A8: three adjectives, and how the assistant addresses
  the user (first name, formal or informal).

Recap of the whole interview in at most ten lines. Yes, then the handover.

**The handover.** The workspace is a new folder outside this one. You make it; the user opens it.

1. After the yes to the recap, update STATE.md first: `workspace:` the absolute path,
   `assistant:` the name, `next: handover (create the workspace folder; then B1 there)`,
   `read: setup/build.md (B1)`, `trigger: Read _setup/nest/SETUP.md and follow it.`
2. Create the folder and fill it yourself: the folder `<ws>/_setup/nest`, the contents of
   `_setup/` copied into `<ws>/_setup/`, and `SETUP.md`, `setup/` and `kit/` copied into
   `<ws>/_setup/nest/`. Use absolute paths for both sides (your shell may no longer be in the
   NEST folder), and a copy command of the user's system: macOS and Linux
   `mkdir -p "<ws>/_setup/nest" && cp -R "<nest>/_setup/." "<ws>/_setup/" && cp -R "<nest>/SETUP.md" "<nest>/setup" "<nest>/kit" "<ws>/_setup/nest/"`;
   Windows PowerShell `New-Item -ItemType Directory -Force "<ws>\_setup\nest" | Out-Null; Copy-Item -Recurse -Force "<nest>\_setup\*" "<ws>\_setup\"; Copy-Item -Recurse -Force "<nest>\SETUP.md","<nest>\setup","<nest>\kit" "<ws>\_setup\nest\"`.
   Claude Code may ask the user whether you may write outside this folder: tell them
   beforehand that this question comes and that yes is right here. Check the result:
   `<ws>/_setup/STATE.md`, `<ws>/_setup/nest/SETUP.md` and `<ws>/_setup/nest/setup/build.md`
   exist.
3. Only when the write was really refused (the tool result says so) does the user run that
   command themselves: give it with the real paths, in the form for where they work (section
   3), and check the result afterwards the same way.
4. Take the interview permission out again when the user said yes to it in Phase 0: remove
   the rule `Edit(/_setup/**)` from `.claude/settings.local.json` in the NEST folder, and the
   file itself when nothing else is in it and you created it. Tick the line in STATE.md (in
   both copies). The build has its own, separate list in the workspace.
5. Tell the user how to open the new folder and start there, in the form for where they work
   (section 3, "Open another folder"), with the path to paste and the trigger line quoted.
   This is the one moment in the interview where they must do something themselves: one short
   message, the steps numbered, nothing else in it (no recap, no warnings said before). With
   `restart_app: yes` they quit the app completely first. The copy of `_setup/` next to NEST can
   go later; it is gitignored.

A session that starts while `next:` still says `handover`: if the current folder is the
workspace path from STATE.md and `_setup/nest/SETUP.md` and `_setup/nest/setup/build.md`
exist, the copy worked: set `next: B1` and go on with B1. If you are still in the NEST folder:
check whether the workspace folder exists. If it does, tell the user how to open it and give
the trigger line; if it does not, do step 2. Never start B1 from the NEST folder.
