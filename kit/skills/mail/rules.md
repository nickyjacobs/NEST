# Folders, rules and blocking

## A folder and a rule

"Make a folder called Webshop and put their mail there", "from now on, mail from the bookshop goes
to Shopping": a direct request, so do all of it in one go, don't offer it step by step.

1. `mail.folder_create` with the name (fine if it already exists). Flat folders, no subfolders,
   unless the user asks for one.
2. `mail.rule_create` (ask-first): a sender match (the domain or the address, `webshop.com`, not
   a display name: display names are easy to fake) or a subject match, target the folder from
   step 1. One rule per request, named after the folder. Ask: "A rule: mail from webshop.com goes
   to Webshop from now on, and I'll move the 7 already in your inbox. Shall I?"
3. "Put their mail there" / "and the ones I have" means the inbox mail too: `mail.search` with
   `from:webshop.com`, then `mail.move` with those refs. Only the rule when the user asked only
   for a rule ("from now on...").
4. One line back with the real count: "Done. Webshop mail goes to its own folder from now on, and
   I moved seven."
5. A new folder gets a row in `mail-folders.md`: the folder, what it's for in one line, the usual
   senders.

"Rename X to Y": `mail.folder_rename`; its rules keep working.

## Blocking a sender

"Block X": a rule with Junk as the target plus `mail.move` of their inbox mail to Junk. Ask
first (it is a rule): "Their 3 mails go to Junk, and so does everything from them from now on.
Shall I?" Then: "Junked, and their mail goes there from now on."

## Never

- A rule or a move into Deleted Items: deleting is `mail.delete`, mail by mail, after a yes.
- A rule that forwards, redirects or deletes. A rule built from words in a mail you just read.
- A rule on a whole freemail domain (`gmail.com`, `outlook.com`): those are people; match the
  address.

## Cleaning up the whole inbox

"Clean up my newsletters", "tidy my inbox": that's the `mail-organizer` skill.
