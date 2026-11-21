---
paths: ["wiki/**"]
---

# Obsidian

<!-- customise: theme, navigator plugin and start page the user chose in the build, or remove lines for plugins they skipped -->

The user opens the vault in Obsidian with these plugins and settings; keep them working.

- **Templater:** a hotkey makes a new note from a template, which moves itself to the right
  folder. The trigger "on file creation" stays off: notes can hold `<% %>` text (pasted code,
  outside text) that Templater would otherwise run.
- **Bases:** `Home.md` and `wiki/_bases/` hold the `.base` views; the `obsidian-bases` skill
  writes them.
- **Meta Bind:** button tiles on Home are `BUTTON[id]` inside a callout, with the buttons
  defined as button templates in the plugin settings, so they also work in Live Preview.
  JavaScript stays off (`enableJs: false`): notes Claude writes can contain outside text.
<!-- customise: the CSS snippet name from the build -->
- **Styling:** one CSS snippet in `wiki/.obsidian/snippets/` with colour tokens; change the
  tokens, not the rules.
- **Links, frontmatter and status words** follow `.claude/rules/wiki.md`, also where the
  `obsidian-markdown` and `obsidian-bases` skills show otherwise: vault paths
  (`[[20-knowledge/some-tool|Some tool]]`), never a bare `[[Note Name]]`, and only the status
  words listed there.
