# NEST setup: pain points and the skill catalogue

Part of the NEST setup prompt. `SETUP.md`, one folder up, holds the rules for every part and says
when to read this one. Read `SETUP.md` first.

---

## Appendix A: pain points and what NEST builds for them

| Pain point (B1, or heard elsewhere in the interview) | What NEST recommends |
|---|---|
| Writing notes at all | Capture-first: one inbox, a "new note" button and hotkey, no structure needed while writing; the inbox skill files it later; session-end writes the session note for you |
| Finding notes again | The query skill with lazy lookup (index first, at most three pages, then search one section); consistent links as vault paths; Bases views on Home; weekly lint |
| Notes piling up | The session-start line shows the inbox count; the maintenance skill signals an inbox over ten notes or older than two weeks; the inbox skill files a batch with one yes |
| Obsidian feels overwhelming | Few plugins, a Home dashboard with buttons, the file explorer coloured per section, the how-this-wiki-works page, and the assistant doing the filing |
| Losing track of projects and priorities | One README per project with phase and next step, a priorities page, Home panels, session-end updating the project, `docs/next-session.md` |
| Forgetting what was learned | Knowledge notes by kind, filed from the inbox, linked to at least two pages; the research skill saves answers back; the query skill finds them |
| Studying for a course or certification | The study inbox: one inbox per course, raw material into a module note in your words, your own answers kept word for word, a checklist per module |
| Ideas never worked out or decided | The Architects (blueprint) to work an idea out, The Council (verdict) to judge it, the decisions log |
| Career or job search | The career skill: tracks, a log, preparation for a vacancy against your own experience |
| Mail chaos | The mail skill (read, archive, move, draft replies, never send) and the mail organizer (a board first, then folders and rules on your go, undo within a day) |
| Calendar and day planning | The calendar skill and the morning briefing |
| Research takes long or sources are unreliable | The research skill and the researcher agent: primary sources first, independent sources, dates, numbered citations |
| Writing sounds stiff or AI-like | The writing-style skill with a word list in your language and a check script |
| Repeating the same tasks | The skill builder: describe the task, get a skill, test it |
| Fear of leaking something sensitive | The secret guard hooks, the sensitive terms list, the security reviewer, private context in a gitignored file |
| Losing work | Git for the workspace, a private GitHub repo, a separate wiki backup |
| Every Claude session starts from zero | The card in CLAUDE.md, the context pages, the session-start line, session-end and `docs/next-session.md` |
| The assistant repeats a mistake | Lessons: a one-line lesson in `.claude/lessons.json`, shown again at the moment the same kind of step comes up |
| A long conversation forgets what was asked | The user's own messages are kept word for word and handed to the summary when the conversation is compacted |
| Falling behind on improvements | The nest-update skill: what is new in plain words, only what they pick, a backup of every file it touches |

---

## Appendix B: the skill catalogue

Default independence: **C** = only on the user's command; **P** = the assistant may propose it and
runs it after a yes; **A** = the assistant may just do it.

| Skill | What it does | Needs | Default | Customise questions (ask only what is not known yet) |
|---|---|---|---|---|
| wiki-inbox | Files every inbox note into the right section, links it, archives the original | wiki | C | how often they want to process; which kinds go where if their sections differ |
| wiki-ingest | Reads a web page or document into the references: a raw copy plus a curated page | wiki; web | C | which sources they ingest most; whether a Tavily MCP is connected |
| wiki-query | Answers a question from the wiki with links, and can save the answer | wiki | A | none beyond the sections |
| wiki-maint | Reindex, lint, stats and signals (stale pages, big inbox, backups) | wiki | C | how often (weekly is recommended) |
| obsidian-markdown, obsidian-bases | Correct Obsidian syntax for notes and Bases views | wiki | A | none |
| verdict (The Council) | Judges an idea: four perspectives, a fact check, a jury, a verdict with a score and a next step | agents; web | P | full or light; which context pages hold their goals, time and money; currency; the ideas section name; whether The Architects are installed too |
| blueprint (The Architects) | Works a rough idea out into a blueprint: what exists, variants, the first user, the smallest version, risks | agents; web | P | full or light; same context pages; the ideas section name; whether The Council is installed too |
| career | Tracks applications and career moves, prepares for a vacancy | wiki | A for status, C for writing | which tracks (jobs, study, promotion, freelance); where their CV or experience lives |
| study-inbox | Turns raw course material into a module note, a file with their own answers kept verbatim, and a checklist per module | wiki | C | which courses or certifications, with exam dates; where course folders live if not under projects |
| research | Quick web research with numbered findings, deeper on request via the researcher agent, saved to the wiki | web | A | the domains they research most; source rules for their field; whether they want vacancies followed (`profile.md`) and news checked against their own devices (`stack.md`): each file is installed only on a yes |
| session-end | Closes a work session: session note, decisions, project status, next steps | wiki | C | which pages to update at the end of a session |
| writing-style | Rewrites text in their voice and checks a word list | none | C | the words, phrases and openers they dislike; their language; whether texts for others must be checked |
| release | Commits per topic, runs the checks, pushes after a yes | git | C | commit prefixes; whether to push to GitHub |
| skill-builder | Builds or changes a skill or agent with them, saves only after a yes to the full draft | none | C | none; it reads the apps page and the tool map |
| calendar | Reads, adds, moves and cancels appointments; handles invitations | an integration | A for reading, ask-first for changes | which calendars; working hours; which actions ask first |
| mail | Reads, searches, archives, moves, drafts replies; never sends | an integration | A for reading, ask-first for deleting and rules | which account; folder layout and purposes |
| mail-organizer | Sorts the whole inbox into folders and rules after a board and a go; undo within a day | mail | P | which folders exist and what they are for; what must always stay in the inbox |
| morning-briefing | A short start of the day from the chosen apps and the wiki | integrations as chosen | A on request | which blocks in which order; weather location; morning hours |
| nest-update (always included) | Looks for a newer NEST release, says in plain words what is new, and brings over only what they pick, with a backup and an undo | git | P | none beyond the language and level |

The `nest-update` skill and the `security-reviewer` agent are always included; the `researcher`
agent comes with research.
