# Your notes on a phone or a second computer

<!-- customise: say the user-facing parts in the user's language; keep only the route they chose when you copy steps into their open items -->

The setup reads this file in the interview (C8) to propose a way to keep the wiki in step
across the user's devices, and in the build to walk them through it. Nothing here is installed
by NEST: a sync route is an account or an app of the user's own.

What a route does: the notes are on every device and stay the same everywhere. What it does not
do: the assistant, its routines and the guards live in the workspace on the first computer, and
stay there. A note written on a phone lands in the inbox (`newFileFolderPath` in
`.obsidian/app.json` points there), and the assistant files it the next time the user sits down
at that computer.

Prices and apps change. The facts below were read in November 2026, with the page each one
comes from. Check the page before you name a price, and say "about".

## Why the wiki can be synced at all

The wiki is a plain folder inside the workspace. Git's own folder is never inside it: with the
separate wiki backup it lives outside the vault, and with the wiki inside the workspace
repository it sits one level up. A sync service that carries the wiki folder therefore never
carries git data, which is where sync and git usually collide.

What does not fit this layout: a service that wants the vault inside its own folder (iCloud
Drive wants it under `iCloud Drive/Obsidian/`, and OneDrive, Dropbox and Google Drive sync only
their own folder). The wiki would have to move out of the workspace, and the workspace itself
must not live in a synced folder (interview F1). NEST does not offer those routes.

## Which route for which devices

| The user has | Propose | A free alternative, and what it asks |
|---|---|---|
| An iPhone or iPad | Obsidian Sync | For someone technical: Syncthing on the computer with an iOS app that speaks the same protocol. The apps there are third-party and iOS limits how often they may run in the background |
| An Android phone | Obsidian Sync | Syncthing on the computer and the community-maintained Syncthing app on the phone. Free; setting it up means pairing two devices and choosing a folder on each |
| A second computer, for the notes only | Obsidian Sync | Syncthing on both computers. One of them has to be on for the other to catch up |
| A work laptop where nothing may be installed | Obsidian Sync, when Obsidian itself is allowed there | None. Remind the user of what they said in A2 about their employer's rules before work notes go into a personal sync account |
| Nothing else | No route | |

For a beginner the honest answer is that the one route they can set up themselves costs money.
Say so, name the price, and offer "decide later": the wiki works without it.

Not offered, and why: git on a phone (the Obsidian Git plugin calls its own mobile support
unstable, and a separate git app means committing and pulling by hand); a plugin that syncs
through a cloud drive (the one most used has had no release since 2024); a self-hosted sync
server (it needs a server).

## Obsidian Sync

Obsidian's own service, for Windows, macOS, Linux, iOS and Android. It works on the wiki folder
where it is, merges changes to a note made on two devices, and skips files and folders whose
name starts with a dot, so it never touches git data.

- Cost: a paid subscription per account. In November 2026 the Standard plan was about 4 dollars
  a month when paid per year (one vault, 1 GB); see <https://obsidian.md/pricing>. There is no
  free trial; the pricing page says what the refund terms are.
- Source for how it behaves: <https://obsidian.md/help/sync/settings> and
  <https://obsidian.md/help/sync-notes>.

Steps, one at a time. The user does them; you only say what comes next and check what you can.

1. On the first computer, in Obsidian with the wiki open: Settings, Sync. Sign in or create an
   Obsidian account, choose a plan, and create a remote vault. They choose an encryption
   password there: it is theirs to keep, nobody can recover it, and it never goes into the chat.
2. Connect the wiki to that remote vault and let it upload.
3. Still in Settings, Sync, under what gets synced: switch on the settings for appearance,
   themes and snippets, and for community plugins (the list of active plugins and the installed
   plugins). They are off by default, and without them the phone shows a bare vault. These
   switches are set per device.
4. On the other device: install Obsidian, sign in, and connect to that remote vault with the
   password (Obsidian offers this when it starts without a vault). Let it download.
5. On that device too: the same switches as in step 3, then "Trust author and enable plugins"
   when Obsidian asks, then close and reopen Obsidian once. That question comes on every device.
6. Check together: Home shows its tiles on the other device, and a note made there appears in
   the inbox on the first computer.

On a phone the Home page is narrower: the tiles stack. Templater's own "run on new file"
switches stay off, as on the computer.

## Syncthing

A free program that keeps a folder the same on two devices, directly between them, without an
account. See <https://obsidian.md/help/sync-notes> for Obsidian's own notes on it. It suits a
user who is comfortable installing a program and reading its screen.

1. Install Syncthing on the first computer and on the other device (on Android the
   community-maintained app; on iOS a third-party app that speaks the same protocol).
2. Pair the two devices: each shows a device ID, and each accepts the other.
3. On the first computer, share the wiki folder, and only that folder: never the workspace
   above it. Add the ignore lines `.obsidian/workspace.json` and
   `.obsidian/workspace-mobile.json` (each device keeps its own window layout).
4. On the other device, accept the folder and choose where it lands; open that folder in
   Obsidian as a vault, choose "Trust author and enable plugins", close and reopen Obsidian.
5. When the same note changes on two devices before they meet, Syncthing keeps both and names
   one of them a conflict copy (the file name says so). The assistant can merge those on
   request.

## What to write down

On the "apps and tools" page of the context section: the devices, the route, and since when.
Never a password, a device ID or an account address. In `docs/next-session.md`: an open item
with the steps above when the route is not set up yet.
