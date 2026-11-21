---
name: writing-style
description: >-
  Writes or rewrites text for outside readers in the user's own style: reports, mails, READMEs, blog posts, job applications, letters. Applies the banned-word list, overused connectors, banned openers and the no-em-dash rule, then checks the result with the style script. Use on /writing-style or when the user asks to write, rewrite, polish or check a piece of text for others. Not for chat, code comments or quick notes in the wiki.
argument-hint: "<text | path> [--style=report|mail|readme|blog] [--keep-structure]"
metadata:
  does: "Writes or rewrites a piece for outside readers in your style, and checks it against your word list."
  try:
    - "/writing-style <text>"
    - "/writing-style path/to/text.md --style=mail"
    - "Polish this mail before I send it"
---

# /writing-style

The output is in the user's voice; `.claude/rules/writing.md` applies in full and wins on a
conflict with anything below.

**Not for:** chat, code comments, or wiki notes for the user's own use. When the style hook flags a
banned word in a wiki page, replace only that word; do not rewrite the note.

<!-- customise: default output language (the user's language) and any second language they write in -->
Write in the language of the input, or the user's language when there is no input text.

## 1. Load the rules

1. `.claude/rules/writing.md`: language rules, form, tone.
<!-- customise: the word list is built in the interview; it holds the user's banned words, overused connectors and banned openers -->
2. `.claude/style-words.txt`: the sections `[banned]`, `[connectors]` (flagged at
   `connector_max` or more per file) and `[openers]`; a trailing `*` matches any ending.
<!-- customise: extra style guides the user has (a path in the wiki's references section), or remove this line -->
3. Any style guide the user keeps in the wiki's references section; read only the relevant parts.

## 2. Input

Text in the prompt, or a path to a file. For a path: rewrite as a proposal, and overwrite the file
only after a yes.

## 3. Analysis

Mark: banned words, banned openers (the first sentence of every paragraph), em dashes and dashes
used as punctuation, overused connectors, AI tells (stacked connectors, vague abstractions,
platitudes, meta commentary), and spelling or grammar errors.

## 4. Rewrite

- Replace banned words with synonyms that are not on the list themselves.
- Rewrite a banned opener into a concrete first sentence.
- An em dash becomes a comma, a full stop or a split sentence.
- Vary sentence length; concrete numbers, names and dates where the text allows it.
- A factual claim without a source gets `[source needed]`.
- `--style` sets the tone (report, mail, readme, blog); `--keep-structure` leaves headings and
  lists exactly as they are.
- Technical terms stay as they are, also when they are in another language.

## 5. Tone

<!-- customise: tone rules from the interview (how formal, the user's field, what they never want to sound like) -->
- Skilled, not pretentious. Concrete cases over abstract claims.
- The user's own experience made explicit ("In my work at <fill in: workplace> I ...") instead of
  "We often see that ...".
- No exaggeration of urgency or importance.

## 6. Check

Check the rewritten text without writing a file anywhere, by passing it on stdin:

```bash
uv run --script scripts/check_style.py --strict - <<'TEXT'
<the rewritten text>
TEXT
```

(`--text "<text>"` works for a short piece.) Never write temporary files outside the workspace;
if a file is needed, use `.runs/style/` inside it, which git ignores.

`--strict` exits 1 on hits (frontmatter and code are skipped): one more rewrite round. Exit 0: the list is clean; tone, sentence length and concrete
cases remain your own check.

## 7. Output

```markdown
## Rewritten
<text>

## Changes
- "leverage" -> "use" (2x)
- Em dash on line 4 -> full stop
- Opener "In today's world ..." -> a concrete sentence

## Status
0 banned words · no em dashes · 2 claims without a source
```

In doubt about the context (mail tone or report tone): ask in one line.
