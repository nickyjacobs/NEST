# Obsidian: theme and plugins

<!-- customise: say the user-facing parts in the user's language; drop a plugin the user declined from `community-plugins.json`, with its settings file and the Home buttons or icons that depend on it -->

The setup installs the theme and the plugins itself, with `scripts/obsidian_setup.py`. The user
does not click through a list, and never installs one of these from inside Obsidian.

## How it goes

1. The setup writes the settings files in this folder into the vault's `.obsidian/`, while the
   vault is not open in Obsidian. Obsidian rewrites `appearance.json` and
   `community-plugins.json` from memory, so a change made under an open vault is lost.
2. After one yes from the user, `uv run --script scripts/obsidian_setup.py install --vault wiki`
   (`wiki` is the wiki folder: `wiki_dir` in `wiki.config.json`, default `wiki`) downloads each plugin in `community-plugins.json` and the theme in `appearance.json` from its
   own project on GitHub, at the version in `scripts/obsidian.lock.json`, checks every file
   against the checksum in that lock file, and puts it next to the settings. A plugin the user
   declined is not in `community-plugins.json`, so it is not downloaded.
3. The user opens the wiki folder in Obsidian (*Open folder as vault*). Give them the full path
   of the wiki folder and tell them to paste it in the folder dialog, not to click their way
   there: macOS `Cmd+Shift+G` in the dialog, Windows the address bar at the top of the dialog,
   Linux `Ctrl+L`. In a trial an experienced user picked the workspace folder above it three
   times in a row.
4. They choose **Trust author and enable plugins**. That is the one step no file can take:
   Obsidian keeps the choice in the app, per vault and per device. If they close the question
   without an answer, Obsidian asks again the next time.
5. They quit Obsidian and open it again, once. The start page was drawn before the plugins
   loaded, so until then the buttons on Home show as text (`BUTTON[...]`).
6. `uv run --script scripts/obsidian_setup.py vaults` lists the vaults Obsidian knows. The wiki
   folder itself must be in it. `status --vault wiki` shows what is installed.

**No question about trusting the author appeared?** Then Obsidian opened another folder,
usually the workspace folder above the wiki: `vaults` shows that folder and not the wiki. That
made a new, empty vault there, with an `.obsidian` folder of its own in the workspace root. The
user removes that entry in Obsidian (the vault switcher, "Manage vaults", "Remove from list");
after a yes you remove the stray `.obsidian` in the workspace root, which holds only Obsidian's
defaults (never the one inside the wiki); then they open the wiki folder again by pasting the
path.

`install` ends with 0 when everything the vault asks for is in place and with 1 when something
was skipped, refused or failed; it says what and why per plugin, and one that fails does not
stop the others. `install --dry-run` writes nothing and ends with 1 when something would be
installed, as `status` does. `--only` takes at least one id or name; an empty one is refused.
It refuses a folder that already holds another plugin, and anything on its way under
`.obsidian` that is a link to another place or not a plain file or folder. A
`community-plugins.json` or `appearance.json` it cannot use (a link, not JSON, the wrong shape)
is named and counts as a failure, never as "nothing to install". Tell the user what it printed,
do not work around it. It also refuses while the vault is open in Obsidian, or may be: ask the user to quit
Obsidian and run it again. `--assume-closed` skips that check. Never add it on your own: only
after the user has confirmed that Obsidian is closed.

Why not let the user install them in Obsidian: when a plugin folder holds a `data.json` but no
`manifest.json`, Obsidian's installer sets the settings aside as `data.json.bak` and the plugin
starts with its defaults. If that happened in a vault (an older setup, or a plugin installed by
hand), `obsidian_setup.py restore --vault wiki` puts the settings back, with Obsidian closed.
It puts back the settings the setup wrote, over whatever the user set since; their current file
is kept next to it as `data.json.before-restore`. It works once: the backup is used up.
`restore` handles the plugins in the table below, the ones the setup wrote settings for or
installed. For a plugin the user added themselves, `status` only says that a `data.json.bak`
is there: that file is theirs to look at, and `restore` leaves it alone.

What to tell the user before the yes, in their language and at their level: these are five
widely used open source plugins and one theme; a plugin can do anything Obsidian itself can, so
they are downloaded from their makers at a fixed version and checked, never from anywhere else;
Obsidian updates them from then on, like any plugin.

On a second computer or a phone the vault arrives through the user's sync or backup. The git
backup leaves out only what `install` can put back: the code of the plugins and the theme in
the lock file, named one by one. Run `install` again on a computer, or let the sync service
carry `.obsidian/plugins`. A plugin or theme the user added themselves is not in the lock file,
so its code stays in the backup, next to its settings. A backup made before this existed
already holds the plugin code and keeps it; nothing is taken out of an existing backup. "Trust
author and enable plugins" is asked again on every device.

## Theme: Minimal

| | |
|---|---|
| What it does here | The look of the whole vault; `base.css` and `idea-note.css` build on it, and Home uses its helper classes `max` (full width) and `base-plain` (no Bases toolbars) |
| Why | Clean, fast, and well maintained; the snippets are tested against it |
| Settings | `appearance.json` sets the theme (`cssTheme`), light or dark (`theme`), the accent colour and the two snippets (`enabledCssSnippets`) |
| Needs | A recent Obsidian (the lock file names the version). `install` says so when Obsidian is too old: the user updates Obsidian and the setup runs `install` again |

## Plugins

The id is what `community-plugins.json` lists and what the lock file is keyed on.

| Plugin | Id | What it does here | Why this one |
|---|---|---|---|
| **Minimal Theme Settings** | `obsidian-minimal-settings` | Colour schemes, line width and contrast for Minimal | The supported way to tune Minimal without CSS |
| **Templater** | `templater-obsidian` | `Alt+N` and the Home tiles make a note from a template that asks for a title and moves itself to the right folder | The core Templates plugin cannot prompt or move a note |
| **Notebook Navigator** | `notebook-navigator` | The sidebar: folder tree with an icon and colour per section, pinned notes, `Home.md` as the start page | Replaces the file explorer and a separate homepage plugin in one |
| **Style Settings** | `obsidian-style-settings` | Sliders and toggles for the theme's CSS variables | Minimal exposes its options through it |
| **Meta Bind** | `obsidian-meta-bind-plugin` | The buttons on Home (`BUTTON[id]`), defined once as button templates, so they also work in Live Preview | Buttons without JavaScript |

Two settings follow Obsidian's own, not the plugin file: Minimal Theme Settings copies the font
size, folding, line numbers and readable line length from `app.json` into its `data.json` every
time it loads. Set those in `app.json`. "Colorful headings" is off in the kit: `base.css` does
not colour headings, and with it on Minimal paints each heading level in another colour.

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

## After the user opened the vault and restarted Obsidian, check

- `vaults` lists the wiki folder itself, not the folder above it.
- `status` lists every plugin as installed, each plugin the setup wrote settings for still has
  its settings file (Style Settings ships none, on purpose), and none has settings set aside.
- Home opens as the start page and shows tiles, panels and (when configured) the KPI row.
- A tile creates a note in the right folder with a kebab-case name.
- The sidebar shows an icon and colour per section, and hides `_bases` and `_templates`.
- Settings → Appearance → CSS snippets shows `base` switched on, and `idea-note` when you have The Council or The Architects with the styled look.

## Left out on purpose

Dataview (Bases covers it), Homepage (Notebook Navigator opens Home), Linter (it rewrites frontmatter
on save, behind the lint's back), Obsidian Git (the workspace has its own backup), Kanban and Projects
(Bases views do this). Optional for the user: the Obsidian Web Clipper browser extension, with a
template that saves to `_inbox` with `kind: link` and `source-url`.
