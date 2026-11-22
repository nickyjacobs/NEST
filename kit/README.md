# kit/

Reference material for `SETUP.md`. The setup reads these files and **adapts** them to the
user's answers; it does not copy them blindly. A file the user does not need is never
created in their workspace.

| Folder | What is in it | How the setup uses it |
|---|---|---|
| `scripts/` | Python tools: wiki lint and reindex, secret scan, session-start line, session guards, the updater, wiki backup, Council scoring, skills catalogue | Copied as files (`cp`, never retyped); configured through `wiki.config.json` and `nest.json` |
| `claude/` | `settings.json` reference with the hook wiring, rules, example lists of sensitive terms and style words | Merged into the workspace's `.claude/`, values from the interview |
| `agents/full/`, `agents/light/` | The Council and The Architects in two sizes, plus `researcher` and `security-reviewer` | Only the chosen team and size; names and output language adjusted |
| `skills/` | One reference `SKILL.md` per recommended skill, with "customise from the interview" points | Rewritten per user: paths, labels, apps, language |
| `integrations/` | Decision guide per app category (mail, calendar, tasks, weather, smart home) and one proven route (Microsoft Graph) | Used in interview block D and build step B3b; every route is verified before use |
| `wiki/` | Templates, base CSS with colour tokens, Bases views, Home and how-to skeletons, Obsidian plugin settings | Translated and restructured to the user's folder design |
| `github/` | Workspace README skeleton, `.gitignore`, `.gitattributes`, pre-commit hook, workflows | The ignore file always; the pre-commit hook when the user wants it; the README and the workflows only with GitHub |

Always part of a workspace, whatever the user chose: the scripts `validate.py`,
`session_context.py`, `session_guard.py`, `nest_update.py`, `agent_git_readonly.py`, `wiki.py` and
`skills_catalog.py`, the
`nest-update` skill and the `security-reviewer` agent. Everything else follows the interview.

A built workspace records in `nest.json` which release it came from and which kit file each
installed file was made from (`scripts/nest_update.py stamp`). That stamp is what lets the
`nest-update` skill bring a later release over without touching what the user changed. A change
to a kit file therefore reaches existing workspaces: say what it means for them under "For your
workspace" in `CHANGELOG.md`.

Rules for every file in here:

- Generic only: no real names, paths, IPs or accounts. Placeholders look like `<fill in: ...>`.
- English. The setup translates labels and folder names to the user's language at build time.
- A reference skill marks each point to customise with `<!-- customise: ... -->`, so the
  setup can find and resolve every one of them; a leftover marker fails the final check.
