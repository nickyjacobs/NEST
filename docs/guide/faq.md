<sub>[Docs](../README.md) · [What to expect](../guide/what-to-expect.md) · [Updating](../guide/updating.md) · [FAQ](../guide/faq.md) · [nest.json](../reference/nest-json.md) · [Hooks](../reference/hooks-notes.md) · [Releasing](../project/releasing.md) · [Backlog](../project/backlog.md)</sub>

# Questions people ask

**On this page:** [Before you start](#before-you-start) · [During the setup](#during-the-setup) · [Privacy and safety](#privacy-and-safety) · [Living with it](#living-with-it)

## Before you start

**What does it cost?**
NEST is free and open source (MIT). It runs inside Claude Code, which needs a paid Claude plan or
API access; the free Claude plan does not include it
([Claude Code's own requirements](https://code.claude.com/docs/en/setup)). The setup is a long conversation across several sessions, and
the two agent teams use more than a normal chat; the light size exists for that reason.

**How long does it take?**
About five sessions of 30 to 60 minutes. You can spread them over days:
[what to expect](what-to-expect.md).

**Do I need to be technical?**
No. The setup asks your level first and explains at that level. It gives you the exact command
when something needs installing. The one file you fill in yourself is a plain list of words
that must stay private, and the setup gives you the command that opens it.

**Does it work on Windows and Linux?**
Yes. The scripts are tested on macOS, Windows and Linux on every change. A complete setup has been
run from start to finish on macOS and on Linux, not yet on Windows, so tell us what you hit
there: an issue is welcome.

**Can I use my own language?**
Yes. The first question is which language you want. Your wiki, your assistant's instructions
and the skills are written in it. The files in this repository are English.

**I already have an Obsidian vault. Can I keep it?**
Yes. NEST builds a new vault inside your workspace and never writes into the one you have,
or changes its settings. The setup notes where your existing notes are and makes bringing them
in one of your first tasks. Nothing is imported during the setup.

**Does it work with other AI tools?**
No. NEST builds on Claude Code features: skills, agents, hooks and settings.

## During the setup

**What if I do not know an answer?**
Say "don't know yet". It becomes an open question and nothing waits on it.

**Can I stop halfway?**
Any time. The setup saves its progress after every step and continues in the next session.

**Will it install things without asking?**
No. Every install and every build step waits for your yes, and commands that need your own
login are yours to run. One thing happens with only a notice: the first time a script runs,
uv fetches the Python version it needs.

**Do I have to take everything?**
No. The assistant, the wiki and the guards are the base; how big the wiki is, is up to you.
Each skill, the agent teams, the integrations and GitHub are separate choices, and a part you
do not need is never created.

## Privacy and safety

**Where do my answers go?**
Into files in your own workspace folder. NEST has no server and collects nothing. What Claude
Code itself sends to Anthropic is covered by your Claude plan's terms, as in any Claude session.

**Does it see my passwords?**
No. NEST never asks for one. Integrations such as mail and calendar sign in through their own
login flow and keep their tokens outside the workspace.

**Can my assistant send mail in my name?**
No. Replies are drafts. Sending mail is not part of NEST.

**What stops a secret from ending up on GitHub?**
A scan for secrets at these moments:

- before and after every file your assistant writes with its edit tools;
- after every shell command it runs. A command can write a file too, and that is only visible
  afterwards. The scan then reads the files git reports as changed or new, in the workspace and
  in the wiki's own backup repository when you have one, plus the files of a commit the command
  made;
- before every commit in the workspace repository, when you chose the pre-commit hook;
- before every wiki backup commit.

Next to that: your own list of sensitive terms, and a read-only reviewer agent. Private context
lives in a file that git ignores. The scan knows the shapes of common keys, tokens and passwords;
it cannot recognise a password that looks like an ordinary word, so the reviewer and your own
eyes still count. Now and then it stops a harmless line that has the shape of a password, such
as one that gives `minimaal12tekens` as the value of `wachtwoord`: write the value with spaces, or
put it between `<` and `>`.
[SECURITY.md](../../SECURITY.md) lists what is covered and what is not.

## Living with it

**How do I get new versions?**
Your workspace tells you when there is one. `/nest-update` shows what is new and you pick:
[keeping your workspace up to date](updating.md).

**Can an update overwrite my own changes?**
No. Files you changed are merged, not replaced, and only after you see the result. Everything
is backed up first, and `/nest-update undo` puts it back.

**Can I change things myself afterwards?**
That is the idea. The skill builder makes or changes a skill with you, rules and lessons get
added when something goes wrong, and [nest.json](../reference/nest-json.md) holds the settings.

**How do I remove it?**
Delete the workspace folder. Everything NEST built lives inside it: the hooks, the skills, the
scripts and the wiki. Two things can live outside it: the data folder of a wiki backup (named
in `nest.json` under `wiki_backup`), and the sign-in of an integration you connected, which that
tool keeps in its own place; disconnect it there. The tools you installed (Claude Code,
Obsidian, git, uv) stay; remove those the usual way if you want.

**Something broke. Where do I go?**
Open an [issue](https://github.com/nickyjacobs/NEST/issues); a question fits better in
[Discussions](https://github.com/nickyjacobs/NEST/discussions). For a security problem, use a
[private report](https://github.com/nickyjacobs/NEST/security/advisories/new) instead.
