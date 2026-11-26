# NEST setup: pain points, the skill catalogue and the plugin catalogue

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

---

## Appendix C: the plugin catalogue

A plugin is a package for Claude Code made by someone else: skills, commands, sometimes hooks,
scripts or a server that come along with it. Unlike the skills in Appendix B, NEST does not
write or adapt a plugin: it is installed as its maker ships it and updated from its maker's
repository. A plugin can run programs on the user's computer, so NEST proposes only the ones
below. Each was read through by NEST (the manifest, the hooks, the servers, the scripts) on the
date in its card.

Rules for every plugin:

- **Only these.** A plugin the user names that is not in this appendix goes to
  `_setup/backlog.md`, with one line: NEST has not read it through, so it is not part of the
  setup. Being popular is not a review.
- **Propose by fit, never the whole list.** Each card says when it fits. Propose at most three,
  the ones that answer a pain point from block B or an app from A7, with your recommendation.
- **The card is the yes.** Before the yes, say in the user's words what the plugin does, what
  runs on their computer, what leaves it, and what it needs. A yes covers that card, nothing more.
- **Check before install.** B3 step 6 compares the card with the source at install time. A plugin
  that now brings a hook, a server or a script its card does not name is not installed: say so,
  and it becomes an open item.
- **Project scope.** Plugins are enabled in the workspace's `.claude/settings.json`, so they
  belong to the workspace and its backup. The marketplace itself is recorded in the user's own
  Claude Code settings; say so once.
- **Updates.** Plugins from `claude-plugins-official` update themselves (Claude Code's default
  for Anthropic's marketplace). The others stay at the version that was installed until the user
  updates them; never turn on auto-update for a marketplace that is not Anthropic's.

| Plugin | What it does for the user | Fits when |
|---|---|---|
| obsidian | Takes the place of the two Obsidian skills NEST would copy: the same skills, kept up to date by Obsidian itself, plus reading web pages as clean notes and working with the open Obsidian app | the wiki skills were chosen (D1); recommend yes, it is not a second copy |
| skill-creator | Tests a skill and sharpens when it starts, next to the skill builder | skill-builder was chosen |
| session-report | A page that shows where their usage went: which sessions and requests cost the most | they run into usage limits, or want to know what a session costs |
| claude-hud | A line under the chat that always shows how full the conversation is and how much of their usage is left | they work in Claude Code in a terminal (`surface: terminal`) and run into limits, lose track in long conversations, or are new to Claude Code. Never with `vscode` or `desktop`: those show no status line |
| diagram-design | Diagrams (a process, a timeline, a map of ideas) as a page or an image | they explain plans, processes or projects to others, or think in pictures |
| playground | A small interactive page: buttons and a live preview to try choices, then a prompt to copy back | they decide by seeing options (a design, a concept map, a document to review) |
| ppt-master | Real PowerPoint files that stay editable, from a document or a topic | presentations are part of their work or study |
| frontend-design | A clear visual direction for any page Claude makes, instead of a template look | they asked for diagram-design or playground, or Claude makes pages for them |
| dutchquill | Writes, rewrites, reviews and humanizes texts in Dutch and English, with templates per kind of text, APA 7 and export to Word and PDF | they write reports, papers or other long documents (especially in Dutch), need APA for their study, or want Word or PDF in a house style; next to writing-style, not instead of it |

### The cards

Each card: how it is installed (`<plugin>@<marketplace>`, and the marketplace source), what runs,
what leaves the machine, what it needs. Read through again on 2026-11-25.

**obsidian** · `obsidian@obsidian-skills`, marketplace `obsidianmd/obsidian-skills#1.2.3`
(Obsidian's own repository, MIT). Runs: skills only; no hooks, no server, no scripts. Chosen, it
replaces the copies of `obsidian-markdown` and `obsidian-bases` (B3 step 1 skips them), so the
user gets one set that Obsidian keeps up to date instead of a copy that stays as it was. Plus
`obsidian-cli` (uses the command line built into the Obsidian app, which the user turns on in
Obsidian), `defuddle` (reads a web page as clean Markdown; needs the `defuddle` program, installed
with npm only after its own yes), `json-canvas`, `knap` (fills note templates; needs the `knap`
program, Node 20 or newer, installed with npm only after its own yes) and `obsidian-headless`
(Obsidian Sync and Publish from the command line; needs the `ob` program, Node 22 or newer, and a
paid Sync or Publish plan; the user logs in in their own terminal). Leaves the machine: nothing,
except the web pages `defuddle` is asked to read, and the vault to Obsidian's servers when the
user runs Sync or Publish through `obsidian-headless`. Needs: nothing for the core; Node for
`defuddle`, `knap` and `obsidian-headless`. Read again on 2026-11-25.

**skill-creator** · `skill-creator@claude-plugins-official` (Anthropic). Runs: a skill with
Python scripts that run test prompts through Claude Code (`claude -p`); no hooks. To show the
results it starts a review page on 127.0.0.1, port 3117, and opens the browser; before it starts
it stops any program already using that port, so say that. With `--static` it writes an HTML file
instead. Leaves the machine: the test prompts, as any Claude Code request (a test run uses part
of the user's usage, so say so); the review page loads fonts from Google Fonts and a script from
`cdn.sheetjs.com`. Needs: Python (uv provides it), with PyYAML for checking and packaging a
skill. Read again on 2026-11-25.

**session-report** · `session-report@claude-plugins-official` (Anthropic). Runs: one local Node
script that reads the user's own Claude Code transcripts on this computer and writes an HTML
report; no hooks, no server. Leaves the machine: nothing, except that the report loads its font
from Google Fonts when it is opened. Needs: Node. Read again on 2026-11-25.

**claude-hud** · `claude-hud@claude-hud`, marketplace `jarrodwatts/claude-hud#v0.15.0` (MIT).
Runs: a status line program in a locked-down Node process with no network access; no hooks, no
server. Its `/hud` command sets Claude Code's status line in the user's own settings, after
asking: the line then shows in every Claude Code project on this computer, not only this
workspace. It shows only in Claude Code in a terminal: the Claude Code panel in VS Code and the
desktop app have no status line (a real setup in the VS Code panel installed it and saw nothing),
so it is never proposed there. Say that before the yes; an existing status line is only replaced after a second
yes. It reads the git status of the project folder. Leaves the machine: nothing; its bug report
command opens a GitHub issue only after the user's OK. Needs: Node 22.18 or newer. Read again on
2026-11-25.

**diagram-design** · `diagram-design@diagram-design`, marketplace `cathrynlavery/diagram-design`
(MIT). Has no release tags, so it is installed at the version of that day and stays there.
Runs: a skill with small local scripts (standard library Python); no hooks, no server, no
telemetry (its `PRIVACY.md`). Brand profiles are saved in `~/.diagram-design/profiles/`, outside
the workspace. Leaves the machine: a diagram loads its fonts from Google Fonts when it is opened;
setting up a brand profile fetches the user's website only when they give one. Needs: the
`python3` command; nothing else for a diagram as a page (an HTML file) or an SVG; a PNG image or
a PDF needs Playwright for Python and a Chromium browser, installed only after their own yes.
Read again on 2026-11-25: the PDF export (`export_pdf.py`) is new since 2026-11-24, so read the
scripts folder again on the day of the install.

**playground** · `playground@claude-plugins-official` (Anthropic). Runs: a skill only. Leaves the
machine: nothing. Needs: a browser to open the page.

**ppt-master** · `ppt-master@ppt-master`, marketplace `hugohe3/ppt-master#v6.10.0` (MIT). The
marketplace points at the plugin's own repository without a fixed version, so the install takes
the version of that day. Runs: a skill with Python scripts; no hooks. By default it opens local
pages in the browser, each from its own small server on 127.0.0.1: a two-step confirmation (from
port 5050) and a live preview of the slides (from port 6060). The user can ask to confirm in the
chat instead; without Flask it does that by itself. At every start
it runs a local integrity check (`attribution_guard.py`) that stops when a file of the skill was
changed, so its files are never edited. Needs: the `python3` command itself (`python` on
Windows) at version 3.10 to 3.14, because the skill calls that command. A second Python next to
it (from uv or elsewhere) does not help: when `python3` is another version, ppt-master is an open
item, and the user's default Python is never changed for it. With a fitting `python3`, four
packages for the core (`python-pptx`, `XlsxWriter`, `skia-pathops`, `uharfbuzz`), installed with pip
after their own yes, and `flask` only when the user wants the local pages; the other packages in its `requirements.txt` belong to one feature each
and are installed only when the user asks for that feature. Leaves the machine: images it
fetches from openly licensed sources when a slide needs one; slide notes read aloud go to
Microsoft's online speech service (`edge-tts`), so say that before narration is used; generated
images only with an image service key the user sets up themselves. Propose it only when
presentations are a real part of their work or study. Read again on 2026-11-25.

**frontend-design** · `frontend-design@claude-plugins-official` (Anthropic). Runs: nothing; it is
one skill file with design guidance. Leaves the machine: nothing. Needs: nothing.

**dutchquill** · `dutchquill@dutchquill`, marketplace `nickyjacobs/DutchQuill-AI#v2.1.0` (MIT, by
the maker of NEST; say so). Runs: six skills (`/dutchquill:schrijven`, `herschrijven`,
`reviewen`, `humaniseren`, `instellen`, `bijwerken`) and three subagents; local Python scripts
(`dq`) in their own environment in the plugin's data folder, made the first time a command needs
them; one hook at the start of a session (a small Python file, standard library only) that says
once that it is not set up yet and reminds once a month to check its guides; DutchQuill Studio,
a settings page on 127.0.0.1 with a one-time key, only when the user asks for it; it can open
the user's own documents and folders from the work folder. No server. It keeps a copy of each
text it makes in the work folder (history); the user can switch that off.
`/dutchquill:instellen` asks where its work folder for input and output goes. Leaves the machine:
its Python packages from PyPI the first time (and a Python download by uv when none fits); the
online language check only when the user switches it on, and then the checked text goes to
LanguageTool (`api.languagetool.org`); `/dutchquill:bijwerken` reads public pages (Scribbr NL,
APA Style, Wikipedia, GitHub) only when asked. Its privacy page is `docs/privacy.md` in its repository.
Needs: uv (the setup's own) or Python 3.10 or newer; the hook uses the `python3` command and stays
silent without it. LibreOffice is optional, for a PDF that looks exactly like the Word file.
Next to writing-style: that skill keeps the user's voice and word list for every text,
DutchQuill is for longer pieces, checks and documents. With both chosen, say which is for what.
