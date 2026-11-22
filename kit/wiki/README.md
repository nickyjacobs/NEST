# kit/wiki/

Reference material for the user's Obsidian vault: templates, styling, Bases views, page skeletons
and Obsidian settings. The setup **adapts** these files to the interview (folder design, language,
palette, dashboard tiles, which teams the user has) and writes the result into `wiki/`; it does not
copy them blindly. Everything here is generic English.

## Markers

- `<!-- customise: ... -->` in Markdown that does not render in Obsidian (this README, `PLUGINS.md`).
- `%% customise: ... %%` inside Obsidian notes, where an HTML comment would show in the editor.
- `// customise: ...` inside a template's Templater block (JavaScript), `/* customise: ... */` in CSS,
  `# customise: ...` in a `.base` file (YAML).
- `<fill in: ...>` for a value the setup types in; `<assistant-name>` for the assistant's name.
- JSON cannot hold comments: its customise points are in the table below.

The setup resolves every marker and removes it; a leftover marker fails the final check.

## Files

| File | What it is for | Goes to |
|---|---|---|
| `_templates/note.md`, `question.md`, `source.md` | Capture into the inbox: `kind` capture, question, link | `wiki/_templates/` |
| `_templates/research.md` | Looking something up: options, findings, a choice | `wiki/_templates/` |
| `_templates/knowledge-note.md`, `knowledge-tool.md` | Knowledge notes (`kind` concept; tool, technique, procedure, skill with a cheat sheet) | `wiki/_templates/` |
| `_templates/project-readme.md`, `reference-page.md` | A project folder with its README; an outside source with a review date | `wiki/_templates/` |
| `_templates/session.md`, `audit.md` | A session log (`/session-end`), an audit (`author: claude`) | `wiki/_templates/` |
| `_templates/_scripts/slug.js` | Templater user script `tp.user.slug` for file names: lower case with hyphens, Latin accents dropped, every other script kept, a date-time name when nothing is left; copy as is | `wiki/_templates/_scripts/` |
| `_templates/code/*.md` | Mirrors of what the skills write (`query`, `knowledge`, `reference`, `idea`); nothing reads them | `wiki/_templates/code/` |
| `_templates/README.md` | The template catalogue the user sees | `wiki/_templates/README.md` |
| `decisions-log.md` | The decisions log with its format block; the session-end, inbox and career skills write entries in that format | `log.md` in the decisions section |
| `snippets/base.css` | Palette tokens, the dashboard callouts, `[!cheatsheet]`, Bases embed styling, light and dark | `wiki/.obsidian/snippets/base.css` |
| `snippets/idea-note.css` | Callouts and labels for the styled mode of the idea pages of The Council and The Architects | `wiki/.obsidian/snippets/idea-note.css` (only with a team) |
| `_bases/dashboard.base` | The views Home embeds: KPIs, Inbox, Questions, New, Answers, Research, Projects, Ideas, Sessions | `wiki/_bases/` |
| `_bases/knowledge.base` | The knowledge overview: by kind, recently updated, concepts | `wiki/_bases/` |
| `Home.md` | The dashboard: nav row, capture tiles, KPI row, a two-column board of panels | `wiki/Home.md` |
| `how-this-wiki-works.md` | The user's how-to: three layers, capture, five operations, rules | `wiki/` (translated file name) |
| `index.md` | The catalogue: sections table and frontmatter per folder | `wiki/index.md` |
| `log.md` | The operations log with its marker | `wiki/log.md` |
| `section-index.md` | One `index.md` per section folder: intro, a Bases embed, the `AUTO-INDEX` marker | `wiki/<section>/index.md` |
| `obsidian/*.json` | Vault settings: files, appearance, core and community plugins | `wiki/.obsidian/` |
| `obsidian/plugins/*/data.json` | Settings for Templater, Meta Bind, Notebook Navigator, Minimal Theme Settings | `wiki/.obsidian/plugins/<id>/data.json` |
| `obsidian/PLUGINS.md` | Install guide and safety settings; the setup walks the user through it | not copied; used during the build |

## What the setup must customise

**Everywhere:** folder names to the user's folder design (defaults `00-context`, `10-projects`,
`20-knowledge`, `25-ideas`, `26-research`, `30-sessions`, `40-references`, `50-decisions`,
`60-audits`, `90-archives`, `_inbox`), labels and page text to the user's language, the user's
`author` value, and `<assistant-name>`. Folder names, `kind` values and status words must match
`wiki.config.json`. Drop what the user does not get: `25-ideas`, `idea-note.css`, `code/idea.md`
and the Ideas views and panel without The Council and The Architects; `60-audits` and `audit.md`
without an audits section; `<assistant-name>` lines with Claude Code only.

**JSON customise points** (no markers possible):

| File | Key | Customise |
|---|---|---|
| `app.json` | `newFileFolderPath` | The inbox folder |
| `app.json` | `attachmentFolderPath` | Default `./attachments` (next to the note); change only on request |
| `appearance.json` | `accentColor` | The user's accent, the same colour as `--nest-accent-rgb` in `base.css` |
| `appearance.json` | `enabledCssSnippets` | Drop `idea-note` without a team |
| `templater-obsidian/data.json` | `templates_folder`, `user_scripts_folder` | When the templates folder is renamed |
| `obsidian-meta-bind-plugin/data.json` | `buttonTemplates` | One `mk-*` per capture tile (label, icon, tooltip, `templateFile`, `folderPath`) and one `ga-*` per nav button (`link` as a vault path); labels and tooltips in the user's language; ids stay stable because Home uses them |
| `obsidian-meta-bind-plugin/data.json` | `firstWeekday`, `preferredDateFormat` | The user's locale |
| `obsidian-meta-bind-plugin/data.json` | `excludedFolders` | The templates folder plus every folder that holds raw outside text, as paths from the vault root, renamed with the folder design: the inbox, the references' raw-copy folder, the archive, and one line per extra raw folder (a project's own inbox, a scanner folder). Never drop a line: a Meta Bind button in outside text can run a Templater file |
| `notebook-navigator/data.json` | `folderIcons`, `folderColors` | One entry per section; colours identical to the `--nest-<section>-rgb` tokens in `base.css` |
| `notebook-navigator/data.json` | `fileIcons`, `fileColors`, `pinnedNotes` | Paths of Home, the how-to page, the inbox index, the priorities page and the logs, after renaming |
| `notebook-navigator/data.json` | `vaultProfiles[0].hiddenFolders` | `/_bases`, `/_templates`, `attachments`, renamed if needed |
| `notebook-navigator/data.json` | `dateFormat`, `timeFormat`, `calendarLocale` | The user's locale (defaults are US style) |
| `obsidian-minimal-settings/data.json` | `lightStyle`, `darkStyle`, schemes | Only when the user wants another contrast or scheme |

**Interview answers this folder needs:** folder design and language; accent colour and, optionally,
a palette per section; which capture tiles and nav buttons (default: all seven tiles and seven
buttons); up to three KPIs and the goal note they read (or none); the dashboard title; the
priorities page and heading the right column embeds; whether The Council or The Architects are
installed; whether there is an audits section.

## Notes for the build

- The plugin settings files are full settings objects, not fragments: a plugin that finds a key
  missing can fail on load. Write them while Obsidian is closed, then let the user install the
  plugins (`PLUGINS.md`); the plugin keeps the settings it finds.
- The KPI views read one note's frontmatter: `goal-done`, `goal-total` (numbers), `goal-date`
  (ISO date) and `next-step` (text), default path `00-context/goal.md`. Create that note with
  those fields when the user names a goal.
- `log.md` keeps the line `<!-- Begin of the log -->` exactly; it must match `log.marker` in
  `wiki.config.json`. Every section index keeps `<!-- AUTO-INDEX -->` (`index_marker`).
- `idea-note.css` styles the styled mode of the `idea` and `blueprint` skills: the callout types and
  `lbl-*` classes listed at its top are exactly the ones in their `reference.md` files. Ship the
  snippet and the styled mode together (the skills' "callout styling" / "callout types" markers), or
  neither: in plain mode the skills write quote and info callouts and need no CSS. The ideas section in `wiki.config.json` takes the
  status words `new`, `worked-out`, `reviewed`, `go`, `parked`, `dropped`, `done`
  (`{"index": "folders", "page": "idea.md", ...}`).
- After writing: `uv run scripts/wiki.py reindex && uv run scripts/wiki.py lint` must report zero.
