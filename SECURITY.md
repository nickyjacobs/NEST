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
