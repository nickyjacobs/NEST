# Tavily web search (optional)

A better web search for the research and wiki-ingest skills: Tavily returns the text of a page
cleanly and can map a site, where the built-in `WebSearch` and `WebFetch` give less. It is
optional. Without it, or when it fails, the skills use `WebSearch` and `WebFetch` and say
nothing about it to the user.

Read on 2026-11-26 from https://www.tavily.com/pricing, https://docs.tavily.com/documentation/mcp,
https://docs.tavily.com/documentation/api-credits and https://code.claude.com/docs/en/mcp.
Check again before you rely on a number.

## What the user gets, in plain words

- Free: 1,000 credits a month, no credit card. A search costs 1 credit, reading a page about
  one credit per five pages. The credits come back on the first day of each month.
- When they run out, Tavily refuses (`432`, "usage limit"), and the skills go on with the
  normal search until the month turns. The user is not bothered with it.
- The user signs in once in the browser. There is no key to copy: nothing secret passes the
  chat or lands in a file of the workspace.

## The route: Tavily's own server, signed in through the browser

1. Add the server in the local scope (this workspace on this computer, not written into the
   workspace's files), one command:
   `claude mcp add --transport http tavily https://mcp.tavily.com/mcp/`
   On Windows with only the VS Code extension, `claude` is not on the path: use the
   extension's own `claude.exe` by its full path (`setup/build.md`, B3 step 6).
   Never run `claude mcp list` or read `~/.claude.json`: they can show the configuration of
   other servers, keys included.
2. A new conversation, so the server loads (in VS Code: the new-conversation button; the app
   stays open).
3. The user signs in: type `/mcp` in the chat, choose `tavily`, and sign in or make a free
   account in the browser page that opens. When the chat does not know `/mcp` (not tried in the
   VS Code panel yet), the same in a terminal: Terminal > New Terminal, `claude` (or the full
   path of `claude.exe`), then `/mcp`.
4. Test, read only: one `tavily_search` for something the user names; the result is real.
5. Write `.claude/rules/web-search.md` with the text under "The fallback rule" below, in the
   user's language, and set the web-tools marker in the wiki-ingest skill to "Tavily
   connected".

Removing it again: `claude mcp remove tavily`, and the rule file goes.

## The fallback rule

```markdown
# Web search

Tavily is connected as a better web search. It is a help, never a requirement.

- Use `tavily_search` to search and `tavily_extract` to read pages when the tools are there.
- When a Tavily tool is missing, refuses, or answers with an error (for example "Tavily API
  error", a usage limit, `432` when the free credits of the month are used up, `429` when it is
  busy), use `WebSearch` and `WebFetch` instead, for the rest of this session.
- Say nothing about the switch in the chat: the user asked for an answer, not for the state of
  a search tool. One line in the session note is enough ("Tavily unavailable, normal search
  used").
- Never ask the user to fix Tavily in the middle of a task. When it keeps failing for days,
  mention it once at the end of a session: the free credits may be used up until the first of
  the month, or the sign-in may need renewing (`/mcp`).
```

## Not offered

A route with an API key (`tavilyApiKey` in the address, or a key in an environment variable):
the key would pass the chat or sit in a file. The browser sign-in needs neither.
