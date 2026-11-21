<!--
Reference for the workspace README (build step B5). Two styles, pick per answer E6:
- plain: keep only the title, the tagline, "What is in here" and "How I use it".
- styled: everything below. Badges only for things that are true (a workflow that exists).
Never personal details: no full name unless the user wants it, no employer, no paths, no IPs.
Every <fill in: ...> is resolved at build time; a leftover fails the final check.
-->

<h1 align="center"><fill in: assistant name></h1>

<p align="center">
  <img src="https://img.shields.io/badge/Claude_Code-workspace-d97757" alt="Claude Code workspace">
  <img src="https://img.shields.io/badge/Obsidian-wiki-7c3aed?logo=obsidian&logoColor=white" alt="Obsidian wiki">
  <img src="https://img.shields.io/badge/built_with-NEST-2ea44f" alt="Built with NEST">
  <!-- with the gitleaks workflow: -->
  <a href="https://github.com/<fill in: owner>/<fill in: repo>/actions/workflows/gitleaks.yml"><img src="https://github.com/<fill in: owner>/<fill in: repo>/actions/workflows/gitleaks.yml/badge.svg" alt="Secret scan"></a>
</p>

<p align="center">
  <b><fill in: the one sentence from F2></b><br>
  <fill in: what the name stands for, letter by letter, if it is an acronym>
</p>

## What is in here

| | Part | What it does |
|---|---|---|
| 🧭 | **<fill in: assistant name>** | The assistant: knows who I am and how I work (`CLAUDE.md`) |
| 📚 | **Wiki** | My Obsidian vault: inbox, knowledge, projects, research, decisions <!-- fill in: the real sections --> |
| 🧩 | **Skills** | <fill in: one line naming the chosen skills> |
| 🛡️ | **Guards** | Secret scan before every write and commit, a read-only security reviewer |

<!-- styled only: one row per chosen part, one emoji each, at most eight rows -->

## How I use it

- Drop anything in the inbox; the assistant files it.
- Ask a question; the answer comes from my own notes, with links.
- <fill in: two or three lines from the user's first tasks>

## Layout

```
<fill in: the top-level tree, two levels deep, without private folder names>
```

## Built with

[NEST](https://github.com/nickyjacobs/NEST), an interview-driven setup for Claude Code workspaces.
