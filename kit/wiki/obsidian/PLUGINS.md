# Obsidian: theme and plugins

<!-- customise: translate the user-facing steps to the user's language; drop a plugin the user declined, and its settings file, the Home buttons or icons that depend on it -->

The setup cannot install Obsidian plugins or themes itself: Obsidian downloads them from inside the
app, and the setup never copies a plugin's `main.js` from anywhere. What the setup does is write the
settings files in this folder into the vault's `.obsidian/` (before the user opens the vault, or
while Obsidian is closed), and then walk the user through the installs below, one at a time,
checking after each one that it works.

## Before the first plugin

1. Open the vault folder in Obsidian (*Open folder as vault*).
2. Settings → Community plugins → **Turn on community plugins** (this switches off Restricted mode).
   Obsidian warns that plugins run code; the five below are widely used and open source.
3. Close and reopen Obsidian after the installs, so every plugin reads the settings file the setup wrote.

## Theme: Minimal

| | |
|---|---|
| What it does here | The look of the whole vault; `base.css` and `idea-note.css` build on it, and Home uses its helper classes `max` (full width) and `base-plain` (no Bases toolbars) |
| Why | Clean, fast, and well maintained; the snippets are tested against it |
| Install | Settings → Appearance → Themes → **Manage** → search **Minimal** → Install and use |
| Settings | `appearance.json` sets the theme, the accent colour and the two snippets |

## Plugins

Install each one through Settings → Community plugins → **Browse** → search the name → Install →
**Enable**. The id is what `community-plugins.json` lists; check it on the plugin's page if two
plugins have similar names.

| Plugin (search for) | Id | What it does here | Why this one |
|---|---|---|---|
| **Minimal Theme Settings** | `obsidian-minimal-settings` | Colour schemes, line width and contrast for Minimal | The supported way to tune Minimal without CSS |
| **Templater** | `templater-obsidian` | `Alt+N` and the Home tiles make a note from a template that asks for a title and moves itself to the right folder | The core Templates plugin cannot prompt or move a note |
| **Notebook Navigator** | `notebook-navigator` | The sidebar: folder tree with an icon and colour per section, pinned notes, `Home.md` as the start page | Replaces the file explorer and a separate homepage plugin in one |
| **Style Settings** | `obsidian-style-settings` | Sliders and toggles for the theme's CSS variables | Minimal exposes its options through it |
| **Meta Bind** | `obsidian-meta-bind-plugin` | The buttons on Home (`BUTTON[id]`), defined once as button templates, so they also work in Live Preview | Buttons without JavaScript |

## Safety settings (do not change)

- **Templater, "Trigger Templater on new file creation": off** (`trigger_on_file_creation_mode: "none"`).
  With it on, Templater runs any `<% %>` text in a new or moved note as code. Notes can hold code
  samples and pasted or fetched outside text; templates only run when the user picks one
  (`Alt+N` or a Home tile). Keep "Enable user system command functions" off as well.
- **Templater, folders:** templates folder `_templates`, user scripts folder `_templates/_scripts`
  (for `tp.user.slug`). Without the scripts folder every template fails on its first line.
- **Meta Bind, "Enable JavaScript": off** (`enableJs: false`). Pages the assistant writes can contain
  outside text (ingested documentation, answers from the web); with JavaScript on, a JavaScript
  button or view field in such a page could run in Obsidian. The buttons on Home need no JavaScript:
  their actions are "Templater create note" and "Open".
- **Meta Bind, excluded folders: the template folder and every folder that holds raw outside text**
  (`excludedFolders`: `_templates`, `_inbox`, `40-references/sources`, `90-archives`). The JavaScript
  switch does not cover everything: a Meta Bind button can also run a Templater file or an Obsidian
  command, and a button is plain text in a code block, so a page copied from the web can carry one.
  In an excluded folder Meta Bind renders nothing, so such a button stays text. Two limits to know:
  the setting matches a folder path from the vault root, so a raw folder deeper in the vault (a
  project's own inbox) needs its own line; and it protects folders, not pages, which is why the
  ingest and inbox skills also make `meta-bind` code blocks and Templater tags inert in outside
  text they copy into a wiki page. Do not click a button you did not put there yourself.
- **Core Templates plugin: off** (`core-plugins.json`). It would compete with Templater for the
  `_templates` folder.

## After the installs, check

- Home opens as the start page and shows tiles, panels and (when configured) the KPI row.
- A tile creates a note in the right folder with a kebab-case name.
- The sidebar shows an icon and colour per section, and hides `_bases` and `_templates`.
- Settings → Appearance → CSS snippets shows `base` switched on, and `idea-note` when you have The Council or The Architects with the styled look.

## Left out on purpose

Dataview (Bases covers it), Homepage (Notebook Navigator opens Home), Linter (it rewrites frontmatter
on save, behind the lint's back), Obsidian Git (the workspace has its own backup), Kanban and Projects
(Bases views do this). Optional for the user: the Obsidian Web Clipper browser extension, with a
template that saves to `_inbox` with `kind: link` and `source-url`.
