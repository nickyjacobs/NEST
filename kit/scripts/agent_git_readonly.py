# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""PreToolUse hook for read-only agents: only git read commands and plain read commands pass.

Wire it in the agent's own frontmatter, so it runs only while that agent works:

  hooks:
    PreToolUse:
      - matcher: "Bash|PowerShell"
        hooks:
          - type: command
            command: uv
            args: ["run", "--quiet", "--script", "${CLAUDE_PROJECT_DIR}/scripts/agent_git_readonly.py"]
            onFailure: block

It works from allow lists, for commands and for their options alike: what is not named here is
refused. A deny list cannot keep up: in Claude Code `find` and `grep` are other programs (bfs and
ugrep) with options of their own, such as a `-rm` that deletes.

Allowed:
  git status | diff | show | log | ls-files | blame | grep | check-ignore | rev-parse, and
      `git branch` and `git remote` without a name (so they only list), optionally after --no-pager
  ls, pwd, cat, head, tail, wc, grep, rg, find, stat, du, diff
  in PowerShell: git, and Get-ChildItem (gci, dir, ls), Get-Content (gc, cat, type),
      Select-String (sls), Get-Location (gl, pwd)
  each with the options in the tables below and no others
  a pipe into head, tail, wc, sort or uniq (Bash), each judged on its own
  the endings 2>/dev/null and 2>&1
  a command written with its full path, when it sits in a system folder (/bin, /usr/bin,
      /usr/local/bin, /opt/homebrew/bin)

Refused:
  every other command and every other option; git options before the subcommand other than
      --no-pager (-C, --git-dir, --work-tree and -c point git at another repository or
      configuration, and a repository's own configuration can name programs to run)
  shell syntax outside quotes: every other redirect, chaining (; && ||), a background &,
      parentheses and braces (zsh runs =(...) and glob qualifiers, PowerShell runs (...)), and for
      PowerShell an @ and a pipe
  a variable or substitution ($, backticks) anywhere but inside single quotes
  a word that starts with = or ~, an unquoted #, a line break, and white space other than a space
      or a tab
  a word that starts with a wildcard (* ? [), or starts with - and holds one: the shell fills a
      wildcard in after this check, and a file named like an option would become one. Write ./*
  a path that starts with // or \\\\ (a network share)

Inside quotes a pattern may hold | < > ( ) * and the like, so `grep -E "a|b" notes` passes; a `$`
only inside single quotes, because double quotes still expand it.

This guards against writing and running things; which files an agent may read is the permission
system's job. Three things it cannot see. A read command without a file (`cat`, `grep pattern`,
`rg pattern` with its input left open) waits for input until the call times out. git runs what
the repository's own configuration names (a diff driver, a file system monitor), which is the
user's own setup. And the guard judges the text of the command, not what the user's own shell
makes of it: an alias or function of their own with the name of an allowed command, a zsh global
alias, or `setopt extendedglob` in their own start-up files is outside it. Exit 2 blocks the call (stderr is the reason
Claude sees); exit 0 leaves the call to the normal permission flow.
"""

from __future__ import annotations

import json
import posixpath
import re
import sys
import unicodedata
from dataclasses import dataclass

# Outside quotes these are shell syntax, in every shell the tools use.
SYNTAX = {";": "chaining (;)", "&": "&& chaining or a background &", "<": "a redirect", ">": "a redirect",
          "(": "parentheses", ")": "parentheses", "{": "braces", "}": "braces"}
# Active outside quotes and inside double quotes alike.
EXPANSION = {"$": "a variable or $( ) substitution", "`": "backticks"}
WORD_START = {"=": "a word that starts with =", "~": "a word that starts with ~"}
GLOB = "*?["
# With zsh's EXTENDED_GLOB these are pattern characters too: -dele^x matches a file named -delete.
# The third one, #, is refused outright wherever it stands unquoted (see scan).
EXTENDED_GLOB = "^~"
NO = "not allowed for a read-only agent: "
# Endings that only silence or merge the error stream. In PowerShell /dev/null would be a file.
TAILS = {False: ("2>/dev/null", "&>/dev/null", "2>&1"), True: ("2>&1", "2>$null")}

# PowerShell reads typographic quotes and dashes as the plain ones.
POWERSHELL_LOOKALIKES = str.maketrans({"‘": "'", "’": "'", "‚": "'", "‛": "'",
                                       "“": '"', "”": '"', "„": '"',
                                       "–": "-", "—": "-", "―": "-"})

SYSTEM_DIRS = {"/bin", "/usr/bin", "/usr/local/bin", "/opt/homebrew/bin"}


@dataclass(frozen=True)
class Word:
    text: str
    glob_start: bool = False  # its first character, once the quotes are gone, is an unquoted wildcard or ^
    glob: bool = False        # holds an unquoted wildcard somewhere
    extended: bool = False    # holds an unquoted ^, # or ~ somewhere


@dataclass(frozen=True)
class Spec:
    """The options one command may get. A word that starts with - must be one of these."""
    flags: str = ""                      # short letters without a value: -l, grouped as -la
    values: str = ""                     # short letters that take a value: -n 5 or -n5
    glued: str = ""                      # short letters whose value is optional and never a word of its own: -M90
    takes: frozenset[str] = frozenset()  # long options and whole words whose value is the next word
    longs: frozenset[str] = frozenset()  # --name or --name=value, matched whole
    words: frozenset[str] = frozenset()  # whole words: find's -name, PowerShell's -Recurse
    numeric: bool = False                # -5 (head -5, git log -5), and +5
    negative: bool = False               # -1, -10k as a value (find -mtime -1)
    positional: bool = True              # may it get file names or other plain words


def _l(text: str) -> frozenset[str]:
    return frozenset(text.split())


DIFF_LONGS = ("--stat --numstat --shortstat --name-only --name-status --cached --staged --patch --no-patch "
              "--color --no-color --word-diff --unified --ignore-all-space --ignore-space-change --ignore-blank-lines "
              "--no-renames --find-renames --diff-filter --summary --raw --abbrev --no-ext-diff --no-textconv "
              "--minimal --patience --histogram --function-context --exit-code --quiet --relative --text --check "
              "--compact-summary --dirstat --merge-base ")
LOG_LONGS = ("--oneline --graph --all --decorate --no-decorate --follow --since --until --after --before --author "
             "--committer --grep --max-count --skip --reverse --first-parent --merges --no-merges --format --pretty "
             "--date --abbrev-commit --no-abbrev-commit --branches --tags --remotes --invert-grep --regexp-ignore-case "
             "--all-match --topo-order --date-order --source --show-signature --left-right --cherry-pick --no-walk "
             "--name-only --name-status ")

# The value of these is the next word (or follows an =).
DIFF_TAKES = _l("--unified --diff-filter")
GIT_TAKES = DIFF_TAKES | _l("--since --until --after --before --author --committer --grep --max-count --skip --date")

GIT: dict[str, Spec] = {
    "status": Spec(flags="sbzv", glued="u", longs=_l("--short --branch --porcelain --untracked-files --ignored --long --no-renames "
                                         "--ahead-behind --no-ahead-behind --show-stash --verbose --column --no-column")),
    "diff": Spec(flags="pswbzRa", values="USGOl", glued="MC", longs=_l(DIFF_LONGS), takes=DIFF_TAKES),
    "show": Spec(flags="pswbzqa", values="USGn", glued="MC", numeric=True, longs=_l(DIFF_LONGS + LOG_LONGS), takes=GIT_TAKES),
    "log": Spec(flags="pswbzqaiEF", values="USGnL", glued="MC", numeric=True, longs=_l(DIFF_LONGS + LOG_LONGS), takes=GIT_TAKES),
    "ls-files": Spec(flags="ocmdsiztuvk", values="x", longs=_l(
        "--others --cached --modified --deleted --stage --ignored --exclude-standard --exclude --full-name --directory "
        "--unmerged --killed --abbrev --error-unmatch --deduplicate --eol --recurse-submodules"),
        takes=_l("--exclude")),
    "blame": Spec(flags="lswepctfnbk", values="L", glued="MC", takes=_l("--since --date"), longs=_l(
        "--porcelain --line-porcelain --since --date --root --show-name --show-number --show-email --abbrev "
        "--incremental --color-lines --color-by-age --minimal --first-parent")),
    "grep": Spec(flags="nilLcwvEFPGIhHzoqa", values="eABC", numeric=True, longs=_l(
        "--line-number --ignore-case --files-with-matches --files-without-match --count --word-regexp "
        "--invert-match --extended-regexp --fixed-strings --perl-regexp --basic-regexp --heading --break "
        "--max-depth --cached --untracked --name-only --only-matching --context --after-context --before-context "
        "--color --no-color --column --show-function --function-context --and --or --not --all-match --text "
        "--quiet --max-count --recurse-submodules"),
        takes=_l("--max-depth --context --after-context --before-context --max-count")),
    "check-ignore": Spec(flags="vnqz", longs=_l("--verbose --non-matching --quiet --no-index")),
    "rev-parse": Spec(flags="q", longs=_l(
        "--show-toplevel --abbrev-ref --short --verify --git-dir --absolute-git-dir --is-inside-work-tree "
        "--is-inside-git-dir --is-bare-repository --show-prefix --show-cdup --symbolic-full-name --symbolic "
        "--quiet --git-common-dir --show-superproject-working-tree --is-shallow-repository")),
    # Without a plain word these only list; with one they would create, rename or remove.
    "branch": Spec(flags="arv", longs=_l("--show-current --all --remotes --verbose --list --merged --no-merged "
                                         "--contains --no-contains --sort --format --color --no-color --column"),
                   words=_l("-vv"), positional=False,
                   takes=_l("--contains --no-contains --merged --no-merged --sort --format")),
    "remote": Spec(flags="v", longs=_l("--verbose"), positional=False),
}
GIT_GLOBAL_FLAGS = {"--no-pager"}

FIND_WORDS = _l(
    "-name -iname -path -ipath -wholename -iwholename -lname -ilname -type -xtype -size -empty "
    "-mtime -mmin -atime -amin -ctime -cmin -newer -anewer -cnewer -newermt -newerct -newerat -daystart "
    "-maxdepth -mindepth -depth -d -xdev -mount -follow -L -H -P -E -s -x -X "
    "-regex -iregex -regextype -user -group -uid -gid -nouser -nogroup -perm -links -inum -samefile "
    "-readable -writable -executable -true -false -not -a -and -o -or ! , "
    "-print -print0 -printf -ls -prune -quit -hidden -nohidden -unique -exclude -color -nocolor -noleaf")

FIND_TAKES = _l(
    "-name -iname -path -ipath -wholename -iwholename -lname -ilname -type -xtype -size -mtime -mmin -atime -amin "
    "-ctime -cmin -newer -anewer -cnewer -newermt -newerct -newerat -maxdepth -mindepth -regex -iregex -regextype "
    "-user -group -uid -gid -perm -links -inum -samefile -printf -exclude")

COMMANDS: dict[str, Spec] = {
    "ls": Spec(flags="1aAlhFGRrtSdpigknosuUcCxmLHTeO@", longs=_l(
        "--all --almost-all --human-readable --recursive --reverse --color --time-style --group-directories-first "
        "--classify --directory --sort --time --full-time --size --inode --numeric-uid-gid --no-group --si")),
    "pwd": Spec(flags="LP", positional=False),
    "cat": Spec(flags="nbsvetAETu", longs=_l(
        "--number --number-nonblank --show-all --show-ends --show-tabs --show-nonprinting --squeeze-blank")),
    "head": Spec(flags="qv", values="nc", numeric=True, longs=_l("--lines --bytes --quiet --silent --verbose"),
                 takes=_l("--lines --bytes")),
    "tail": Spec(flags="qvr", values="ncb", numeric=True, longs=_l("--lines --bytes --quiet --silent --verbose"),
                 takes=_l("--lines --bytes")),
    "wc": Spec(flags="lwcmL", longs=_l("--lines --words --bytes --chars --max-line-length")),
    "stat": Spec(flags="LlnqrsxFt", values="fc", longs=_l("--format --printf --dereference --terse --file-system"),
                 takes=_l("--format --printf")),
    "du": Spec(flags="achkmsxHLPgSl0b", values="dtBI", longs=_l(
        "--max-depth --summarize --human-readable --all --total --apparent-size --exclude --bytes --block-size --si "
        "--time --one-file-system --separate-dirs --dereference"), takes=_l("--max-depth --exclude --block-size")),
    "diff": Spec(flags="uqrNwbBiaEZsyt", values="UCxIW", longs=_l(
        "--unified --context --brief --recursive --ignore-all-space --ignore-space-change --ignore-blank-lines "
        "--ignore-case --side-by-side --color --new-file --exclude --text --strip-trailing-cr "
        "--report-identical-files --suppress-common-lines --width --minimal --ignore-matching-lines"),
        takes=_l("--exclude --width --ignore-matching-lines")),
    # grep is ugrep inside Claude Code: no --filter, --pager, --save-config, --view, --config, -Q.
    "grep": Spec(flags="inrRlLcvwxHhoEFGPsqIaTbyukX0", values="eABCmfgtO", numeric=True, longs=_l(
        "--include --exclude --exclude-dir --include-dir --ignore-case --no-ignore-case --smart-case --recursive "
        "--dereference-recursive --line-number --files-with-matches --files-without-match --count --invert-match "
        "--word-regexp --line-regexp --extended-regexp --fixed-strings --perl-regexp --basic-regexp "
        "--only-matching --no-filename --with-filename --context --after-context --before-context --max-count "
        "--color --colour --null --binary-files --text --no-messages --quiet --silent --regexp --file --hidden "
        "--ignore-binary --max-depth --glob --byte-offset --initial-tab --column-number --line-buffered"),
        takes=_l("--include --exclude --exclude-dir --include-dir --context --after-context --before-context "
                 "--max-count --binary-files --regexp --file --max-depth --glob")),
    # rg: no --pre, --pre-glob, --hostname-bin, --search-zip (-z), all of which run a program.
    "rg": Spec(flags="inlLcvwxHhoFPsSuUNIaqp0", values="eABCmgtTjfMdEr", longs=_l(
        "--line-number --no-line-number --files-with-matches --files-without-match --count --count-matches "
        "--invert-match --word-regexp --line-regexp --ignore-case --smart-case --case-sensitive --fixed-strings "
        "--hidden --no-ignore --no-ignore-vcs --glob --iglob --type --type-not --type-list --max-count --context "
        "--after-context --before-context --max-depth --files --no-heading --heading --with-filename "
        "--no-filename --only-matching --pretty --color --column --follow --multiline --multiline-dotall --pcre2 "
        "--text --null --sort --sortr --max-columns --regexp --file --no-messages --quiet --stats --json --trim "
        "--vimgrep --unrestricted --max-filesize --crlf --no-config --one-file-system --passthru --replace "
        "--encoding --threads --byte-offset --binary"),
        takes=_l("--glob --iglob --type --type-not --max-count --context --after-context --before-context "
                 "--max-depth --color --sort --sortr --max-columns --regexp --file --max-filesize --replace "
                 "--encoding --threads")),
    "find": Spec(words=FIND_WORDS, negative=True, takes=FIND_TAKES),
}
# What may stand after a pipe. sort and uniq only there: on their own they add nothing.
RECEIVERS: dict[str, Spec] = {
    "head": COMMANDS["head"], "tail": COMMANDS["tail"], "wc": COMMANDS["wc"],
    # sort: no -o / --output, no --compress-program, no -T, no --files0-from.
    "sort": Spec(flags="nrufbdigMhVsc", values="kt", longs=_l(
        "--numeric-sort --reverse --unique --ignore-case --human-numeric-sort --version-sort --key "
        "--field-separator --stable --check --general-numeric-sort --month-sort --dictionary-order "
        "--ignore-leading-blanks"), positional=False, takes=_l("--key --field-separator")),
    # uniq writes to its second file name, so it gets none at all.
    "uniq": Spec(flags="cdui", values="fsw", numeric=True, longs=_l(
        "--count --repeated --unique --ignore-case --skip-fields --skip-chars --check-chars"), positional=False,
        takes=_l("--skip-fields --skip-chars --check-chars")),
}

# PowerShell: parameter names are matched whole. PowerShell itself accepts any unambiguous
# prefix, so a short form such as -w is refused here rather than guessed at.
PS_COMMON = "-erroraction -ea -verbose -debug"
PS_TAKES = _l("-path -literalpath -filter -include -exclude -depth -attributes -totalcount -first -head -tail -last "
              "-encoding -readcount -delimiter -pattern -context -erroraction -ea")
POWERSHELL: dict[str, Spec] = {
    "get-childitem": Spec(words=_l("-path -literalpath -filter -include -exclude -recurse -depth -force -name -file "
                                   "-directory -hidden -readonly -system -attributes -followsymlink " + PS_COMMON),
                          takes=PS_TAKES),
    "get-content": Spec(words=_l("-path -literalpath -totalcount -first -head -tail -last -raw -encoding -readcount "
                                 "-delimiter -filter -include -exclude -force " + PS_COMMON), takes=PS_TAKES),
    "select-string": Spec(words=_l("-pattern -path -literalpath -simplematch -casesensitive -context -list -quiet "
                                   "-allmatches -notmatch -encoding -include -exclude -raw -noemphasis "
                                   + PS_COMMON), takes=PS_TAKES),
    "get-location": Spec(words=_l(PS_COMMON), positional=False, takes=PS_TAKES),
}
POWERSHELL = {name: Spec(words=spec.words, positional=spec.positional, takes=spec.takes & spec.words)
              for name, spec in POWERSHELL.items()}
POWERSHELL_ALIASES = {"gci": "get-childitem", "dir": "get-childitem", "ls": "get-childitem",
                      "gc": "get-content", "cat": "get-content", "type": "get-content",
                      "sls": "select-string", "gl": "get-location", "pwd": "get-location"}


def odd_space(ch: str) -> bool:
    """White space that is not a space or a tab. PowerShell splits words on it; no command needs it."""
    return ch in "\u0085  \u000b\u000c" or (ch != " " and unicodedata.category(ch) == "Zs")


def scan(command: str, powershell: bool) -> tuple[list[list[Word]], str | None]:
    """The words of the command, per part of a pipe, and why it is refused (None when the syntax
    is plain).

    Quotes are followed the way the shell follows them, so that a character is judged as syntax
    only where the shell would read it as syntax."""
    parts: list[list[Word]] = [[]]
    word: list[str] = []
    in_word = glob_start = glob = extended = False
    quote = ""
    i, n = 0, len(command)

    def close() -> None:
        nonlocal word, in_word, glob_start, glob, extended
        if in_word:
            parts[-1].append(Word("".join(word), glob_start, glob, extended))
        word, in_word, glob_start, glob, extended = [], False, False, False, False

    while i < n:
        ch = command[i]
        if ch in "\n\r":
            return parts, NO + "a line break"
        if quote == "'":
            if ch == "'":
                if powershell and command[i + 1:i + 2] == "'":
                    word.append("'")
                    i += 1
                else:
                    quote = ""
            else:
                word.append(ch)
        elif quote == '"':
            if ch in EXPANSION:
                return parts, NO + f"{EXPANSION[ch]} (use single quotes for a literal {ch})"
            if ch == '"':
                if powershell and command[i + 1:i + 2] == '"':
                    word.append('"')
                    i += 1
                else:
                    quote = ""
            elif ch == "\\" and not powershell and i + 1 < n:
                word.append(command[i + 1])
                i += 1
            else:
                word.append(ch)
        elif ch in " \t":
            close()
        else:
            if not in_word:
                tail = next((t for t in TAILS[powershell] if command.startswith(t, i)
                             and (i + len(t) == n or command[i + len(t)] in " \t|")), None)
                if tail:
                    i += len(tail)
                    continue
            if odd_space(ch):
                return parts, NO + "white space other than a space or a tab"
            if ch == "|":
                if powershell or command[i + 1:i + 2] == "|" or (not parts[-1] and not in_word):
                    return parts, NO + "a pipe or || chaining" + ("" if powershell else
                                                                 " (a single pipe into head, tail, wc, sort or uniq is fine)")
                close()
                parts.append([])
                i += 1
                continue
            if ch in SYNTAX:
                return parts, NO + SYNTAX[ch]
            if ch in EXPANSION:
                return parts, NO + EXPANSION[ch]
            if ch == "#":
                # A comment in most shells, and with zsh's EXTENDED_GLOB a pattern character that
                # makes what stands before it optional: a#-delete can expand to -delete.
                return parts, NO + "an unquoted # (put the word in quotes)"
            if powershell and ch == "@":
                return parts, NO + "an @ (splatting or an array)"
            if not in_word and ch in WORD_START:
                return parts, NO + WORD_START[ch]
            # "First" is the first character the shell is left with: empty quotes in front of a
            # wildcard (''?delete) do not make it any less the start of the word.
            if ch in GLOB:
                glob = True
                glob_start = glob_start or not word
            elif ch in EXTENDED_GLOB:
                extended = True
                glob_start = glob_start or (ch == "^" and not word)
            in_word = True
            if ch in "'\"":
                quote = ch
            elif ch == "\\" and not powershell:
                if i + 1 >= n:
                    return parts, "the command could not be parsed (it ends in a backslash)"
                if command[i + 1] in "\n\r":
                    return parts, NO + "a line break"
                word.append(command[i + 1])
                i += 1
            else:
                word.append(ch)
        i += 1
    if quote:
        return parts, "the command could not be parsed (unbalanced quotes)"
    close()
    if len(parts) > 1 and not parts[-1]:
        return parts, NO + "a pipe that leads nowhere"
    return parts, None


def command_name(first: str) -> str | None:
    """The allow-list name for the first word, or None when a path points outside the system folders."""
    low = first.lower()
    if "/" not in first and "\\" not in first:
        return low
    if "\\" in first or not first.startswith("/"):
        return None
    clean = posixpath.normpath(first)
    return posixpath.basename(clean).lower() if posixpath.dirname(clean) in SYSTEM_DIRS else None


def is_number(spec: Spec, text: str) -> bool:
    if spec.numeric and re.fullmatch(r"[-+]\d+", text):
        return True
    return spec.negative and bool(re.fullmatch(r"-\d[\d.]*[A-Za-z]?", text))


def check_words(label: str, spec: Spec, words: list[Word], powershell: bool = False, globs: bool = True) -> str | None:
    """Why one of the command's words is refused: an option that is not on its list, a wildcard
    that could turn into one, a network path.

    One rule carries the rest: a word that starts with - is always judged as an option, wherever
    it stands. The program may read it as a value or as a file name instead, but never as an
    option this list does not know. So `--` does not open the door to anything, and an option
    that takes a value cannot swallow a `--` and leave the next word to be read as an option."""
    expects = ""  # the option whose value the next word is
    after_dashes = False
    for index, w in enumerate(words):
        text = w.text
        if powershell:
            if re.search(r"(?:^|[:=])[\\/]{2}", text) or "::" in text or "\\\\" in text:
                return f"a path that starts with // or \\\\ reaches a network share, which is {NO.rstrip(': ')}"
        elif text.startswith(("//", "\\\\")):
            return f"a path that starts with // or \\\\ reaches a network share, which is {NO.rstrip(': ')}"
        if globs and not powershell and (w.glob_start or ((w.glob or w.extended) and text.startswith("-"))):
            return (f"the wildcard in {text} is filled in by the shell after this check, and a file named like an "
                    "option would become one: write ./* instead, or put the pattern in quotes")
        dashed = text.startswith("-") and len(text) > 1
        if expects:
            if dashed and not is_number(spec, text):
                return (f"{label} {expects} takes a value, and {text} starts with -: the program would read one of "
                        "them differently than this check. Write the value as ./-name or after an =")
            expects = ""
            continue
        if text == "-":
            return f"{label} - reads from the keyboard and would wait forever"
        if text == "--" and not powershell and label != "find":
            following = words[index + 1].text if index + 1 < len(words) else ""
            if not following or following.startswith("-"):
                return f"{label} -- must be followed by a name that does not start with - (write ./-name)"
            after_dashes = True
            continue
        if after_dashes and dashed:
            return f"{label} {text}: a name that starts with - is not accepted, also after --; write ./{text}"
        if not dashed and not (text.startswith("+") and spec.numeric and is_number(spec, text)):
            if not spec.positional and text not in spec.words:
                return f"{label} takes no name or file here (it would do more than read)"
            continue
        verdict = option_allowed(spec, text, powershell)
        if verdict is None:
            return f"{label} {text} is not on the list of options a read-only agent may use"
        if verdict:
            if index + 1 >= len(words):
                return f"{label} {text} takes a value, and none follows"
            expects = text
    return None


def option_allowed(spec: Spec, text: str, powershell: bool) -> bool | None:
    """None: not on the list. True: allowed, and its value is the next word. False: allowed."""
    if powershell:
        name, colon, _ = text.lower().partition(":")
        return (name in spec.takes and not colon) if name in spec.words else None
    if text in spec.words:
        return text in spec.takes
    if is_number(spec, text):
        return False
    if text.startswith("--"):
        name, equals, _ = text.partition("=")
        return (name in spec.takes and not equals) if name in spec.longs else None
    for i, letter in enumerate(text[1:], 1):
        if letter in spec.values:
            return i == len(text) - 1  # nothing glued on: the value is the next word
        if letter in spec.glued:
            return False               # the rest of the word, if any, is its value
        if letter not in spec.flags:
            return None
    return False if len(text) > 1 else None


def check(command: str, tool: str = "Bash") -> str | None:
    """Why the command is refused, or None when it may run."""
    powershell = tool == "PowerShell"
    cmd = command.strip()
    if powershell:
        cmd = cmd.translate(POWERSHELL_LOOKALIKES)
    if not cmd:
        return None
    parts, reason = scan(cmd, powershell)
    if reason:
        return reason
    if not parts[0]:
        return None
    for index, words in enumerate(parts):
        reason = check_part(words, powershell, receiver=index > 0)
        if reason:
            return reason
    return None


def check_part(words: list[Word], powershell: bool, receiver: bool) -> str | None:
    first = words[0]
    if first.glob:
        return NO + "a wildcard in the command name"
    name = command_name(first.text)
    if receiver:
        if name not in RECEIVERS:
            return f"after a pipe only head, tail, wc, sort and uniq are allowed, not {first.text}"
        return check_words(name, RECEIVERS[name], words[1:])
    if name == "git":
        return check_git(words[1:], powershell)
    if powershell:
        name = POWERSHELL_ALIASES.get(name or "", name)
        if name in POWERSHELL:
            return check_words(name, POWERSHELL[name], words[1:], powershell=True)
    elif name in COMMANDS:
        return check_words(name, COMMANDS[name], words[1:])
    return f"only git read commands and plain read commands are allowed, not {first.text}"


def check_git(args: list[Word], powershell: bool = False) -> str | None:
    i = 0
    while i < len(args):
        tok = args[i].text
        if tok in GIT_GLOBAL_FLAGS:
            i += 1
        elif tok.startswith("-"):
            key = tok.split("=", 1)[0]
            return (f"git option {key} before the subcommand is not allowed (only --no-pager): it can point git at "
                    "another repository or configuration")
        else:
            break
    if i >= len(args):
        return "a bare git call is not a read command"
    sub, rest = args[i].text, args[i + 1:]
    if sub not in GIT or args[i].glob:
        return (f"git {sub} is not a read command here (allowed: " + ", ".join(sorted(GIT)) + ")")
    # git is the same program in every shell, so its options are judged the same way in PowerShell;
    # only the wildcard rule is the shell's: PowerShell hands a * to git as it stands.
    return check_words(f"git {sub}", GIT[sub], rest, globs=not powershell)


def main() -> int:
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8", errors="replace") or "{}")
    except ValueError:
        print("read-only guard: the hook input was not JSON, so the call is refused", file=sys.stderr)
        return 2
    if not isinstance(data, dict) or data.get("tool_name") not in ("Bash", "PowerShell"):
        return 0
    tool_input = data.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if command is None and isinstance(tool_input, dict):
        command = ""
    if not isinstance(command, str):
        print("read-only guard: the hook input names no command text, so the call is refused", file=sys.stderr)
        return 2
    reason = check(command, str(data["tool_name"]))
    if reason:
        print(f"Read-only agent: {reason}. Refused: {command[:200]}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
