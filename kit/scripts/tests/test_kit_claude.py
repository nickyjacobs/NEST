"""The permission rules the setup offers for the length of a build stay narrow.

kit/claude/setup-permissions.example.json is put into a workspace's local settings after one
yes from the user and taken out again at the wrap-up. This test keeps the list from growing
into something a user would not have agreed to.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent.parent
RULES = json.loads((KIT / "claude" / "setup-permissions.example.json").read_text(encoding="utf-8"))

EDIT = re.compile(r"Edit\(/(?!\.claude)(?!\.git/)[A-Za-z0-9_.\-]+(/\*\*)?\)")
BASH = (
    "Bash(uv run scripts/*)",
    "Bash(uv run --script scripts/*)",
    "Bash(git status*)",
    "Bash(git diff*)",
    "Bash(git add *)",
    "Bash(git check-ignore *)",
    "Bash(ls *)",
    "Bash(mkdir -p *)",
)
NEVER = ("rm", "push", "commit", "curl", "wget", "install", "sudo", "chmod", "mv ", "cp ", "gh ", "claude", "http", "WebFetch", "mcp__")


def test_only_an_allow_list():
    assert set(RULES) == {"permissions"}
    assert set(RULES["permissions"]) == {"allow"}
    assert RULES["permissions"]["allow"], "the list is empty"


def test_every_rule_is_an_edit_inside_the_workspace_or_a_known_harmless_command():
    for rule in RULES["permissions"]["allow"]:
        assert EDIT.fullmatch(rule) or rule in BASH, f"not a rule this list may hold: {rule}"


def test_nothing_that_deletes_sends_installs_or_reaches_the_assistant_settings():
    for rule in RULES["permissions"]["allow"]:
        assert not any(word in rule for word in NEVER), rule
        assert ".claude" not in rule, f"{rule}: the assistant's own settings stay a question"
        assert rule not in ("Bash", "Bash(*)", "Edit", "Edit(**)", "Edit(/**)", "Write"), rule


def test_no_rule_is_listed_twice():
    allow = RULES["permissions"]["allow"]
    assert len(allow) == len(set(allow))
