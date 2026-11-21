---
paths: ["wiki/**"]
---

# Writing

<!-- customise: the user's writing language(s); which text is written in it (wiki, mails, reports) and which stays English (code, repo docs, config) -->

For text other people or the user's future self will read: wiki pages, reports, READMEs, mails,
blog posts and job applications. Not for chat, and not for code or config. Heavy text work for
outside readers: `/writing-style`.

## Language

<!-- customise: language-specific rules (spelling and grammar pitfalls the user wants checked) -->
- Correct spelling and grammar for the language of the text.
- Active voice where it works.
- Direct phrasing instead of roundabout constructions.

## Banned

<!-- customise: the word list lives in .claude/style-words.txt (from kit/claude/style-words.example.txt), built in the interview in the user's language; [paths] excludes the raw folders -->
- **Words, overused connectors and openers:** the `[banned]`, `[connectors]` and `[openers]`
  sections of `.claude/style-words.txt`. The style hook flags hits after every write to a path
  under `[paths]`; `uv run --script scripts/check_style.py --strict <file>` checks a file by hand, and
  `... --strict -` checks text on stdin without writing a file.
  A flagged word in a wiki note: replace only that word, do not rewrite the note.
- **Em dashes and dashes as punctuation** in running text: use a comma, a full stop, or split the
  sentence.
- Platitudes, meta commentary and chatbot phrasing ("Great question", "In conclusion", "Let's
  dive in").

## Form

- Vary sentence length and word choice; a natural tone.
- Backticks for file paths, commands, variables and library names, also inside sentences.
- Dates in ISO (`2026-01-06`), times in 24-hour notation (`14:30`).
- An acronym in full on first use, then the short form.
- A source with every factual claim.
<!-- customise: the user's own style preferences from the interview (Oxford comma, formal or informal address, British or American spelling) -->
- Stay consistent within one document (spelling variant, list punctuation, address).
