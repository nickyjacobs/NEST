# Building the board

How to turn the scan into folders, choices and rules, and how to run it without the CLI. Based
on how people keep a mailbox workable (few flat folders, one sorting principle per folder,
search for the rest), proven on a real inbox.

## Grouping (route B; route A's scan already does this)

- A sender at a freemail provider (gmail, outlook, hotmail, icloud, yahoo, proton, gmx and the
  like) is a person: one group per **address**.
- Everyone else: one group per **registrable domain** (`news.shop.com` and `shop.com` are one
  group; `mail.example.co.uk` is `example.co.uk`).
- An Apple Hide My Email relay (`..._at_shop_com_...@privaterelay.appleid.com`) belongs to the
  domain inside it.
- Per group keep: the label (most common display name), count, unread, the newest date, up to
  three subjects, and the refs.

## Folders

- **The user's folders first.** Use an existing folder when it fits: its row in
  `mail-folders.md`, and where the group's older mail already sits. Spell it exactly as listed.
- **One principle per folder: what the mail is to the user.** Follow the existing folders (by
  brand, by kind); where there are none, go by kind: Shopping, Travel, Bank, Health, Jobs,
  Newsletters, Social.
- **A folder per sender the user deals with, a kind for the rest** (when the customise block in
  SKILL.md says they file nearly everything): a sender with an ongoing relationship and about
  five mails or more gets its own folder; senders that only advertise go together by kind.
- **Topic over brand when the topic folder exists:** an insurer to "Insurance", a clinic to
  "Health", receipts to an existing receipts folder.
- **Flat.** No subfolders. Short names in the user's language.
- **Every new folder gets a note**: what it's for, one line. It goes into `mail-folders.md` after
  the run.
- **Leave in the inbox** what's live: a person the user still has to answer, a job application
  or payment plan in progress, one-off senders with no clear home. Name the most important one you
  left in one sentence.

## Choices (options A, B, C)

Offer a choice only where the grouping could reasonably go two or three ways; one to three per
run.

- A brand on its own or with its kind: the job site alone, or with the recruiters in "Jobs".
- Into an existing folder or a new one: the food delivery apps in "Shopping", or a new "Food".
- Two kinds that overlap: crypto newsletters with the other newsletters, or their own folder.

A group sits in one bucket or in one choice, never both. Each option is a short title plus its
own buckets. Say which you'd pick, with a reason in a few words. Picked options are merged into
the plan as normal buckets.

## Rules

`"rule": true` sends that folder's future mail there too. The rule is built from the groups'
senders (domains, or addresses for people), never from words you type and never from subjects.
An existing rule for the folder is extended rather than duplicated.

- Yes for senders that keep sending: newsletters, shops, notifications, about three mails or more.
- No for people, one-offs, and kinds where a mail sometimes needs the user (a bank's payment
  problem, a doctor's appointment): those stay visible.

Limits: at most 30 new folders per run, at most 60 senders per rule.

## The plan file

`.runs/organizer/plan.json` (`.runs/` is gitignored):

```json
{"buckets": [
  {"folder": "Shopping", "groups": ["g1", "g4"], "rule": true},
  {"folder": "Travel", "groups": ["g7"], "rule": true, "note": "Bookings and boarding passes"}
]}
```

Route A's `organizer.check` refuses: a group in two folders, an unknown group, Inbox, Deleted
Items, Sent, Drafts or Outbox as a target, a `/` in a new folder name, a new folder without a
note, more than 30 new folders, a rule over 60 senders. Fix the plan and check again.

## Before you show the board

Every group in at most one place; folder names exact; a note on every new folder; choices only
where it's a real call; the counts from the check, not your own.

## Route B run (no organizer rows in the tool map)

Same safety as route A, done by hand:

1. Check the plan yourself against the list above (route A's refusals are the rules).
2. **Write the journal before anything moves:** `.runs/organizer/run-<YYYYMMDD-HHMMSS>.json` with
   `at` (ISO time), `planned` (per bucket: folder, new or not, refs, rule senders), and empty
   `moves`, `folders`, `rules_added`, `rules_changed`, `undone: false`.
3. Per bucket: `mail.folder_create` for a new one (add it to `folders`), `mail.move` in chunks of
   at most 40 refs (append each moved ref with its target to `moves`), then the rule with
   `mail.rule_create` (add its name to `rules_added`; for an extended rule, the old senders to
   `rules_changed`). Save the journal after every step.
4. **Undo** (within 24 hours of `at`, the newest journal only, `undone` false): `mail.move` every
   ref in `moves` back to the inbox; rules and folders: when the tool map has no operation to
   remove a rule or an empty folder, list them for the user to remove in the mail app. Set
   `undone: true`.
