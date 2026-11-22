"""Tests for agent_git_readonly.py: what a read-only agent may and may not run."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import agent_git_readonly as guard

SCRIPT = Path(guard.__file__)


@pytest.mark.parametrize("cmd", [
    "git status", "git status --short", "git status -uno", "git diff", "git diff --cached -- src/a.py",
    "git diff HEAD~1 --stat", "git show --stat HEAD", "git show HEAD", "git show HEAD~2:docs/a.md", "git log",
    "git log --oneline -n 20", "git log -5", "git log -5 --oneline", "git log --stat -3", "git ls-files",
    "git --no-pager log --oneline", "git ls-files -o --exclude-standard", "git blame -L 1,20 a.md",
    "git grep -n TODO", "git check-ignore -v wiki/a.md", "git rev-parse --show-toplevel", "git rev-parse HEAD",
    "git branch --show-current", "git branch -a", "git remote -v",
    "ls -la", "pwd", "cat README.md", "head -n 5 a.md", "head -5 a.md", "tail -n 20 log.md", "tail +3 log.md",
    "wc -l a.md", "grep -rn TODO src", "grep -c -i todo a.md", "grep -A3 -B 2 x a.md", "rg -n secret docs",
    "rg --pretty secret docs", "find . -name '*.md' -type f", "find . -name \"*.md\" -mtime -1 -size -10k",
    "find wiki -type f -newer a.md -print", "find . \\( -name a -o -name b \\) -prune", "stat a.md", "du -sh wiki",
    "diff -u a.md b.md", "", "cat 'a file.md'", "cat a\\ file.md", "/bin/cat a.md", "/usr/bin/grep -rn TODO src",
    "ls ./*.md", "cat docs/*.md", "ls sub/[ab]*.md",
    # Shell characters inside quotes are a pattern, not syntax.
    'grep -rnE "password|secret" .', "grep -rn 'token$' wiki", 'rg -n "AKIA|ghp_" .', "grep -rn '(a|b){2}' docs",
    'grep -n "a < b; c > d & e" notes.md', "find . -name '*.{md,txt}'", "grep -rn '*' docs", "grep -e './-x' a.md", "grep --regexp=-x a.md",
    # What a model types by habit.
    "ls missing 2>/dev/null", "git status 2>&1", "grep -rn x . 2>/dev/null | head -5", "git log --oneline | head",
    "git log --oneline | wc -l", "cat a.md | sort -u | uniq -c | head -3", "git ls-files | tail -n 4",
    "git status &>/dev/null", "ls missing &>/dev/null | wc -l", "git branch --contains HEAD", "git branch --merged main",
    "git diff -- src/a.py", "git log --oneline -- ./-odd-name.md", "head -n -5 a.md", "tail -n +3 a.md",
    "cat 'notes#1.md'", 'grep -n "#include" a.c', "grep -rn '^# ' docs", "cat notes\\#1.md",
    "git log -n 5 --since 2026-01-01", "git log HEAD^ HEAD~2", "find . -mtime -1 -size -10k", "cat ''a.md",
])
def test_allowed(cmd):
    assert guard.check(cmd) is None


@pytest.mark.parametrize("cmd", [
    "Get-ChildItem -Recurse", "Get-Content README.md", "Select-String -Pattern x a.md", "gci .",
    r"Get-Content C:\work\notes.md", 'Select-String -Pattern "password|secret" notes.md',
    "Get-Content 'notes#1.md'", 'Select-String -Pattern "#include" a.c',
    "Select-String -Pattern 'it''s; (a|b)' notes.md", "Get-Location", "cat a.md", "type a.md", "gc a.md -Tail 5",
    "ls -Recurse", "Get-ChildItem *.md", "git status", "git diff -- *.md", "git status 2>&1", "git log -5 2>$null",
    "Get-Content -Path:a.md -TotalCount 5",
])
def test_allowed_powershell(cmd):
    assert guard.check(cmd, "PowerShell") is None


@pytest.mark.parametrize("cmd,why", [
    ("git status > out.txt", "redirect"), ("cat < a.md", "redirect"), ("echo $(whoami)", "variable"),
    ("git diff `whoami`", "backticks"), ("git status; rm -rf x", "chaining"), ("git status && git push", "chaining"),
    ("git status || true", "pipe"), ("sleep 100 &", "background"), ("git status 2>err.txt", "redirect"),
    ("git status 2>/dev/nullx", "redirect"), ("git status &>out.txt", "background"),
    ("git status\nrm a", "line break"), ("cat $HOME/.ssh/id_rsa", "variable"),
    ("git commit -m x", "not a read command"), ("git push", "not a read command"), ("git checkout main", "not a read"),
    ("git -c core.pager=evil log --oneline", "option -c"), ("git log --oneline --output=x.txt", "--output=x.txt"),
    ("git diff -oout.txt", "-oout.txt"), ("git diff --ext-diff", "--ext-diff"), ("git log -p --textconv", "--textconv"),
    ("GIT_EXTERNAL_DIFF=evil git diff", "not GIT_EXTERNAL_DIFF"), ("git", "bare git"),
    ("find . -exec rm {} +", "braces"), ("find . -exec rm x +", "-exec"), ("find . -delete", "-delete"),
    ("rg --pre ./evil x", "--pre"), ("tail -f log.md", "-f"), ("python3 -c 'print(1)'", "not python3"),
    ("rm -rf /", "not rm"), ("echo 'unbalanced", "parsed"),
    # zsh runs what stands in =( ) and in a glob qualifier.
    ("cat =(touch pwned)", "starts with ="), ("ls *(e:'touch pwned':)", "parentheses"), ("cat =ls", "starts with ="),
    ("cat ~/notes.md", "starts with ~"), ("cat {a,b}.md", "braces"),
    # A quote that the shell reads as escaped does not hide what follows it.
    ('cat \\" ; rm -rf x ; \\"', "chaining"), ('cat "a\\\\" ; rm x ; "b"', "chaining"),
    ('grep "$HOME" a.md', "variable"), ('grep "`id`" a.md', "backticks"), ("cat a.md \\", "parsed"),
    # A repository's own configuration can name programs to run.
    ("git -C sub status", "option -C"), ("git --git-dir=/tmp/w.git status", "option --git-dir"),
    ("git --work-tree /tmp/w diff", "option --work-tree"),
    ("git diff --outpu=x.txt", "--outpu=x.txt"), ("git diff --ext", "--ext"), ("git grep -O x", "-O"),
    ("git grep --open-files-in-pager x", "--open-files-in-pager"), ("git branch -D main", "-D"),
    ("git branch new-branch", "takes no name"), ("git remote add x https://x.test", "takes no name"),
    ("git check-ignore --stdin", "--stdin"),
    # Commands that cannot be made safe are off the list; sort and uniq only after a pipe.
    ("sort names.txt", "not sort"), ("sort -oout.txt in.txt", "not sort"), ("file -C -m magic", "not file"),
    ("tree -R -o out.html", "not tree"), ("tree -L 2", "not tree"),
    # Options go through an allow list: find is bfs and grep is ugrep inside Claude Code.
    ("find . -name victim.txt -rm", "-rm"), ("find . -execdir rm x +", "-execdir"), ("find . -okdir rm x +", "-okdir"),
    ("find . -fprintf out.txt %p", "-fprintf"), ("find . -fprint out.txt", "-fprint"), ("find . -exit", "-exit"),
    ("find -files0-from list .", "-files0-from"), ("tail -qf log.md", "-qf"), ("tail --follow=name log.md", "--follow"),
    ("grep --filter=sh:evil x a.md", "--filter"), ("grep --pager=evil x a.md", "--pager"),
    ("grep --save-config=x x a.md", "--save-config"), ("grep -rQ x", "-rQ"), ("grep --view=evil x", "--view"),
    ("rg --pre=./evil x", "--pre"), ("rg --pre-glob '*.md' x", "--pre-glob"), ("rg --hostname-bin ./evil x", "--hostname-bin"),
    ("rg -z x", "-z"), ("rg --search-zip x", "--search-zip"), ("cat -", "wait forever"),
    # The shell fills a wildcard in after the check, and a file named like an option becomes one.
    ("find sub -name n.md -de*", "wildcard"), ("rg hi --pre*", "wildcard"), ("cat *", "write ./*"),
    ("find . -name *.md", "wildcard"), ("ls -?", "wildcard"), ("grep x [-]*", "wildcard"), ("git diff -- *.md", "wildcard"),
    ("l? a.md", "wildcard in the command name"),
    # A pipe only into a few readers, each judged on its own.
    ("git log --oneline | sh", "after a pipe"), ("ls | grep x", "after a pipe"), ("ls | sort -o out.txt", "-o"),
    ("ls | sort --compress-program=evil", "--compress-program"), ("ls | uniq - out.txt", "wait forever"),
    ("ls | uniq in.txt out.txt", "takes no name"), ("ls | sort -T /tmp", "-T"), ("ls | tail -f", "-f"),
    ("ls |", "leads nowhere"), ("| head", "pipe"), ("ls | | head", "pipe"), ("ls | head ; rm x", "chaining"),
    # A full path only into a system folder.
    ("/tmp/evil/cat a.md", "not /tmp/evil/cat"), ("./cat a.md", "not ./cat"), ("/bin/../tmp/evil/cat a.md", "not /bin/"),
    ("/bin/rm -rf x", "not /bin/rm"), ("cat //server/share/a.md", "network share"),
    ("cat a.md\u00a0b.md", "white space"),
    # After an option that takes a value, -- is that value to the program, not the end of options.
    ("rg -e -- --pre=sh", "takes a value"), ("git grep -e -- '-Otouch GG_RAN'", "takes a value"),
    ("grep -e -- --filter=txt:sh .", "takes a value"), ("git blame -L -- --contents x", "takes a value"),
    ("git ls-files -x -- --with-tree=x", "takes a value"), ("grep -e '-x' a.md", "takes a value"),
    ("grep -e", "none follows"), ("git log --since", "none follows"),
    # A word that starts with - is an option wherever it stands, also after --.
    ("rg x -- --pre=sh", "must be followed"), ("git diff -- --output=x", "must be followed"),
    ("cat -- a.md --evil", "also after --"), ("git log --oneline -- a.md -Sx", "also after --"), ("cat --", "must be followed"),
    # Empty quotes do not hide the start of a word from the shell.
    ("find sub -name victim.md ''?delete", "wildcard"), ('find sub -name victim.md ""*', "wildcard"),
    ("cat ''\"\"[-]x", "wildcard"), ("cat ^a.md", "wildcard"), ("cat ''^a.md", "wildcard"),
    # zsh EXTENDED_GLOB: ^, # and ~ are pattern characters.
    ("find . -name a.md -dele^x", "wildcard"), ("find . -name a.md -delet#e", "unquoted #"),
    # With EXTENDED_GLOB a # makes what stands before it optional: a#-delete can become -delete.
    ("find sub -name v.md a#-delete", "unquoted #"), ("ls :#'-''-'", "unquoted #"), ("tail .#^\\---output", "unquoted #"),
    ("du %#-f", "unquoted #"), ("cat notes#1.md", "unquoted #"), ("git status # look", "unquoted #"),
    ("rg x --pr~x", "wildcard"),
])
def test_refused(cmd, why):
    reason = guard.check(cmd)
    assert reason is not None and why.lower() in reason.lower()


@pytest.mark.parametrize("cmd,why", [
    ("Get-Content a.md -Wait", "-Wait"), ("Get-Content a.md -wa", "-wa"), ("Get-Content a.md \u2013Wait", "-Wait"),
    ("cat a.md -Wait", "-Wait"), ("gc a.md -w", "-w"), ("type a.md -Wait", "-Wait"),
    # PowerShell runs what stands in parentheses, without a dollar sign.
    (r"Get-Content (Remove-Item -Recurse -Force C:\work)", "parentheses"),
    ("Get-ChildItem -Path (Set-Content x.txt pwned -PassThru)", "parentheses"),
    ("Get-Content @args", "@"), ("Get-ChildItem . -Filter {x}", "braces"), ('Get-Content "$env:USERPROFILE\\x"', "variable"),
    # A backslash escapes nothing in PowerShell, so the string ends at the quote.
    ('Get-Content "C:\\dir\\" ; Remove-Item x ; "y"', "chaining"),
    # PowerShell reads a typographic quote as a quote.
    ("Get-Content 'a \u2019 ; Remove-Item x ; \u2018 b'", "chaining"),
    (r".\evil.ps1", "not"), ("Remove-Item x", "not Remove-Item"),
    # A network path makes Windows sign in to that machine.
    (r"Get-Content \\server\share\a.md", "network share"), ("Get-Content //server/share/a.md", "network share"),
    (r"Get-Content -Path:\\server\share\a.md", "network share"),
    (r"Get-ChildItem Microsoft.PowerShell.Core\FileSystem::\\server\share", "network share"),
    # PowerShell splits words on other white space too.
    ("Get-Content a.md\u00a0-Wait", "white space"), ("Get-Content a.md\u2003-Wait", "white space"),
    ("Get-Content a.md\u0085-Wait", "white space"),
    ("Get-Content a.md | Out-File x", "pipe"), ("head -5 a.md", "not head"), ("find . -delete", "not find"),
    ("git status 2>/dev/null", "redirect"),
    ("Get-Content -Path://host/share/x", "network share"), ("Get-Content FileSystem:://host/share/x", "network share"),
    ("Get-Content -Path=//host/share/x", "network share"), ("Get-Content Microsoft.PowerShell.Core\\FileSystem::C:\\x", "network share"),
    ("Get-Content a.md # -Wait", "unquoted #"), ("Get-Content a#b.md", "unquoted #"),
    ("Get-Content -Path -Wait", "takes a value"), ("Get-Content a.md -Tail", "none follows"),
])
def test_refused_powershell(cmd, why):
    reason = guard.check(cmd, "PowerShell")
    assert reason is not None and why.lower() in reason.lower()


def run(payload: dict | str) -> subprocess.CompletedProcess[bytes]:
    data = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run(check=False, args=[sys.executable, str(SCRIPT)], input=data.encode(), capture_output=True)


def test_hook_blocks_with_exit_2():
    r = run({"tool_name": "Bash", "tool_input": {"command": "git push --force"}})
    assert r.returncode == 2 and b"git push" in r.stderr


def test_hook_allows_with_exit_0_and_no_output():
    r = run({"tool_name": "Bash", "tool_input": {"command": "git status"}})
    assert r.returncode == 0 and r.stdout == b"" and r.stderr == b""


def test_hook_covers_powershell():
    assert run({"tool_name": "PowerShell", "tool_input": {"command": "Remove-Item x"}}).returncode == 2


def test_hook_ignores_other_tools():
    assert run({"tool_name": "Read", "tool_input": {"file_path": "/a"}}).returncode == 0


def test_hook_refuses_garbage_input():
    assert run("not json").returncode == 2


def test_hook_refuses_input_without_command_text():
    assert run({"tool_name": "Bash", "tool_input": ["ls"]}).returncode == 2
    assert run({"tool_name": "Bash", "tool_input": {"command": ["rm", "-rf", "x"]}}).returncode == 2


def test_hook_reads_powershell_rules_from_the_tool_name():
    # In PowerShell a backslash escapes nothing, so this string ends at the second quote.
    command = r'Get-Content "C:\dir\" ; Remove-Item x ; "y"'
    assert guard.check(command, "PowerShell") and guard.check('cat "a\\" ; rm x ; "b"', "Bash")
    assert run({"tool_name": "PowerShell", "tool_input": {"command": command}}).returncode == 2


def value_options():
    """Every command with every option that takes its value as the next word."""
    cases = []
    tables = [(name, spec, "", "Bash") for name, spec in guard.COMMANDS.items()]
    tables += [(f"git {name}", spec, "", "Bash") for name, spec in guard.GIT.items()]
    tables += [(name, spec, "ls | ", "Bash") for name, spec in guard.RECEIVERS.items()]
    tables += [(name, spec, "", "PowerShell") for name, spec in guard.POWERSHELL.items()]
    for name, spec, prefix, tool in tables:
        for option in [*(f"-{letter}" for letter in spec.values), *sorted(spec.takes)]:
            cases.append((f"{prefix}{name} {option}", tool))
    return cases


def test_every_command_has_its_value_options_listed():
    cases = value_options()
    assert len(cases) > 150
    for name, spec in [*guard.COMMANDS.items(), *guard.GIT.items(), *guard.RECEIVERS.items(), *guard.POWERSHELL.items()]:
        assert spec.takes <= (spec.longs | spec.words), name  # no value option that is not on the list itself


@pytest.mark.parametrize("command,tool", value_options())
def test_value_option_never_swallows_what_follows(command, tool):
    for rest in ("-- --anything", "-x", "-- -x a.md", "--"):
        reason = guard.check(f"{command} {rest}", tool)
        assert reason is not None, f"{command} {rest}"
    assert guard.check(command, tool) is not None  # and without a value it is refused too
