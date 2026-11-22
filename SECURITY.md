# Security policy

NEST is a setup prompt plus reference files. It runs inside your own Claude Code
session and writes only to folders you approve.

## Reporting a problem

Report a vulnerability privately through
[GitHub Security Advisories](https://github.com/nickyjacobs/NEST/security/advisories/new), not in an issue.
You get an answer within seven days.

Things worth reporting:

- a reference script or hook that could leak a secret or run something unexpected
- a prompt instruction that lets outside text (a mail, a web page, a note) steer an action
- a default that is less safe than the docs claim

## What NEST never does by design

- It never asks for, stores or prints a password, token or API key. Integrations sign in
  through their own login flow and keep tokens outside the work folder.
- The mail reference skills never send mail; a reply is always a draft.
- Nothing is deleted: the setup and the wiki move things to an archive folder.

## What the secret scan covers

The workspace NEST builds scans for secrets at these moments:

- **Edit tools (Write, Edit, NotebookEdit):** before the write, which is refused when the new
  text holds a secret, and again after it, on the whole file.
- **Shell commands (Bash, PowerShell):** after the command, also when it failed. A shell can
  write a file through a redirect or a heredoc, and nothing can read that text beforehand. The
  scan reads three things and tells the assistant to fix what it finds:
  - the files git reports as changed or untracked in the workspace that changed in the last two
    minutes (a file that was copied, moved or unpacked counts by the moment it arrived);
  - the same in the wiki's own backup repository, when `nest.json` names one under
    `wiki_backup.git_dir`: the workspace ignores that folder, so its own status never lists it;
  - the commits made since the previous command, read from the commits themselves (at most 20),
    so a command that writes a file, commits it and then overwrites or removes it is still seen.
    Only the branch that is checked out: commits on other branches and stashes are not read.
- **Commits in the workspace repository:** before the commit, on the staged files, when the
  pre-commit hook is installed. The hook only runs when its file is executable and
  `core.hooksPath` points at it, and it needs `uv` on the PATH of whatever makes the commit.
- **Wiki backup commits:** `wiki_backup.py` scans the files of a backup commit before it makes it.

What it does not do:

- It recognises shapes: the keys and tokens of common services, private key blocks, passwords
  in a URL or on a command line, and values after names such as `password`, `DB_PASSWORD`,
  `token` or `API_KEY`. A password without a digit, shorter than ten characters or with spaces
  in it looks like an ordinary word and passes.
- A value that is an address (`https://...`) or that names a password manager
  (`stored-in-1Password`) counts as a pointer to the secret, not as the secret, and passes.
- It can stop a harmless line by mistake: a line that gives `minimaal12tekens` as the value of
  `wachtwoord` has the shape of a password. Write such a value with spaces (`minimaal 12 tekens`)
  or put it between `<` and `>`. (This page cannot show the line itself: the scan would stop it.)
- After a shell command it does not see a file that git ignores (apart from the wiki backup
  above), a file outside a git repository, or a file that changed more than two minutes before
  the command ended. It reads the checked-out branch only: no other branch, no stash. One run
  reads at most 20 new commits, 50 files and 8 MB, and says how many commits and files it left
  out.
- After a write it leaves the files alone that are meant to hold private things:
  `CLAUDE.local.md`, the sensitive terms file and a `.env` file that git ignores. The scan
  before a write does not make that exception: the assistant cannot write a real key into any
  file, these included. When a key belongs in `.env` or `CLAUDE.local.md`, put it there yourself
  in an editor; the assistant can then edit the rest of the file around it. A commit that stages
  one of these files is still scanned.
- A file larger than 2 MB is not scanned; the scan says so.
- The guards of single agents (the read-only reviewer, the blind seats) live in the agent files
  and do not run in a headless `claude -p` session.
- The read-only reviewer's guard decides which commands and options may run; it does not decide
  which files may be read, and git still runs what your own repository's configuration names.
- That guard judges the text of a command, not what your own shell makes of it. An alias or
  function of your own with the name of an allowed command (`cat`, `grep`), a zsh global alias,
  or `setopt extendedglob` in your own shell start-up files is outside what it can see.
- A read command without a file (`cat`, `grep pattern`, `rg pattern` with its input left open)
  is allowed and then waits for input until the call times out.
